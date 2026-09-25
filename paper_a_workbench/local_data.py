"""Read local experiment folders/ZIP parts, without uploads or solver calls."""
from __future__ import annotations
import bisect, io, json, os, re, shutil, zipfile
from pathlib import Path
from common import read, write, fresh, within, stamp
from paths import DEFAULT_DATA_ROOT

PART = re.compile(r'^(.*\.zip)(?:\.part|\.)(\d+)$', re.I)
META = {'PUBLICATION.json','PAPER_EXPORT.json','MANIFEST.json','manifest.json',
        'run_status.json','run_summary.json','RUN_OUTCOME.md','HANDOFF_README.md',
        'BASELINE_ACCOUNTING.json','ACCOUNTING.json','BASELINE_REUSE_POLICY.json',
        'RECOVERY_ACCOUNTING.json','COMPLETION_EXPLANATION.md','EXPORT.json','PARTS.json','ARCHIVE_PARTS.json',
        'TRANSFER_PARTS.json','SOURCE_LOCK.json','FINAL_PUBLICATION.json'}
SKIP = {'.git','.venv','node_modules','__pycache__'}


class JoinedParts(io.RawIOBase):
    """Seekable, read-only view; ZIP parts are not copied to a second huge ZIP."""
    def __init__(self, paths):
        super().__init__()
        self.paths=[Path(p) for p in paths]
        self.ends=[];total=0
        for p in self.paths:
            total+=p.stat().st_size;self.ends.append(total)
        self.pos=0;self.total=total
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=io.SEEK_SET):
        value=offset if whence==io.SEEK_SET else self.pos+offset if whence==io.SEEK_CUR else self.total+offset
        if value<0: raise ValueError('Negative archive seek')
        self.pos=value;return value
    def read(self, size=-1):
        if self.closed: raise ValueError('Archive view is closed')
        stop=self.total if size is None or size<0 else min(self.total,self.pos+size)
        chunks=[]
        while self.pos<stop:
            i=bisect.bisect_right(self.ends,self.pos)
            begin=self.ends[i-1] if i else 0
            take=min(stop,self.ends[i])-self.pos
            with self.paths[i].open('rb') as f:
                f.seek(self.pos-begin);chunk=f.read(take)
            if len(chunk)!=take: raise OSError('Archive part changed while reading')
            chunks.append(chunk);self.pos+=take
        return b''.join(chunks)
    def readinto(self, target):
        data=self.read(len(target));target[:len(data)]=data;return len(data)


def _source_root(value):
    if os.name!='nt' and re.match(r'^[A-Za-z]:[\\/]',str(value)):
        return None
    return Path(value).expanduser().resolve()


def _small_metadata(raw, name):
    text=raw.decode('utf-8-sig')
    return json.loads(text) if name.lower().endswith('.json') else text[:16000]


def catalogue(root=DEFAULT_DATA_ROOT, destination=None):
    source=_source_root(root)
    result=dict(schema=2,source_root=str(root),created_at=stamp(),read_only=True,
                status='present' if source and source.is_dir() else 'not_found',entries=[],metadata=[])
    if result['status']=='present':
        files=[];directories=[source]
        for base,dirs,names in os.walk(source,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in SKIP and not (Path(base)/d).is_symlink())
            p=Path(base)
            if 'jobs' in dirs:
                directories.append(p)
            for name in sorted(names):
                f=p/name
                if f.is_symlink():continue
                if name in META and f.stat().st_size<=2_000_000:
                    try:result['metadata'].append(dict(path=str(f),content=_small_metadata(f.read_bytes(),name)))
                    except (ValueError,UnicodeError,OSError) as exc:
                        result['metadata'].append(dict(path=str(f),read_error=str(exc)))
                if name.lower().endswith('.zip') or PART.match(name):files.append(f)
                elif name.lower().endswith(('.7z','.rar')):
                    result['entries'].append(dict(kind='external_archive',paths=[str(f)],
                        status='extract_with_existing_local_archiver',bytes=f.stat().st_size))
        groups={}
        for f in sorted(files):
            m=PART.match(f.name)
            if m:groups.setdefault(str(f.parent/m.group(1))+'::parts',[]).append((int(m.group(2)),f))
            else:groups[str(f)+'::file']=[(None,f)]
        for key,parts in sorted(groups.items()):
            numbered=[p for p in parts if p[0] is not None]
            if numbered:
                numbered.sort();nums=[x[0] for x in numbered]
                consecutive=(nums[0] in (0,1) and nums==list(range(nums[0],nums[-1]+1)))
                paths=[str(x[1]) for x in numbered]
            else:consecutive=True;paths=[str(parts[0][1])]
            item=dict(kind='zip',paths=paths,bytes=sum(Path(x).stat().st_size for x in paths),
                      status='available' if consecutive else 'missing_numbered_parts',metadata=[])
            if consecutive:
                try:
                    with JoinedParts(paths) as stream,zipfile.ZipFile(stream) as z:
                        item['members']=len(z.infolist())
                        item['uncompressed_bytes']=sum(m.file_size for m in z.infolist())
                        for m in z.infolist():
                            if Path(m.filename.replace('\\','/')).name in META and m.file_size<=2_000_000:
                                item['metadata'].append(dict(member=m.filename,content=_small_metadata(z.read(m),m.filename)))
                except (ValueError,OSError,zipfile.BadZipFile,UnicodeError) as exc:
                    item.update(status='archive_read_error',error=str(exc))
            result['entries'].append(item)
        for p in sorted(set(directories)):
            result['entries'].append(dict(kind='directory',paths=[str(p)],status='available'))
        result['entries'].sort(key=lambda r:r['paths'][0])
        for i,e in enumerate(result['entries'],1):e['id']=f'local_{i:04d}'
    result['selection_rule']='Select one declared experiment cohort and disjoint shards; archive names and newer timestamps alone do not choose scientific results.'
    if destination:write(destination,result)
    return result


def scan(home, root=None):
    home=Path(home).resolve();session=read(home/'.orion_paper/SESSION.json')
    chosen=root or session.get('local_data_root') or DEFAULT_DATA_ROOT
    target=home/'数据/ORION_论文资料/local_catalogues'/f'{stamp()}.json'
    result=catalogue(chosen,target)
    session.update(local_data_root=str(chosen),local_catalogue=str(target))
    write(home/'.orion_paper/SESSION.json',session)
    return dict(catalogue=str(target),status=result['status'],entries=len(result['entries']),
                next='Read catalogue metadata, match the report publication, and select explicit entry IDs.')


def unpack_paths(parts, destination):
    out=Path(destination).resolve()
    for p in parts:
        if Path(p).resolve() in out.parents:raise ValueError('Extraction destination must differ from source')
    fresh(out);records=out/'records';records.mkdir();files=[];seen=set()
    try:
        with JoinedParts(parts) as stream,zipfile.ZipFile(stream) as z:
            for m in z.infolist():
                if m.is_dir():continue
                if ((m.external_attr>>16)&0o170000)==0o120000:raise ValueError('Symbolic link archive member')
                target=within(records,m.filename)
                key=str(target.relative_to(records)).casefold()
                if key in seen:raise ValueError('Duplicate/case-colliding archive member: '+m.filename)
                seen.add(key);target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(m) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                files.append(dict(path=m.filename,bytes=target.stat().st_size))
    except Exception as exc:
        write(out/'UNPACK_RECEIPT.json',dict(status='partial',error=str(exc),parts=list(map(str,parts)),files=files))
        raise
    runs=sorted({str(p.parent) for p in records.rglob('jobs') if p.is_dir()})
    nested=sorted(str(p) for p in records.rglob('*.zip'))
    receipt=dict(status='extracted',parts=[str(Path(p).resolve()) for p in parts],records=str(records),
                 files=files,run_candidates=runs,nested_archives=nested,
                 policy='Source archive bytes unchanged; original JSON and paths unchanged; no remote transfer.')
    write(out/'UNPACK_RECEIPT.json',receipt)
    return {k:v for k,v in receipt.items() if k!='files'}|{'file_count':len(files)}


def materialize(catalogue_path, entry_id, destination):
    c=read(catalogue_path);choices=[e for e in c['entries'] if e['id']==entry_id]
    if len(choices)!=1:raise ValueError('Select an existing local catalogue entry')
    e=choices[0]
    if e['status']!='available':raise ValueError('Entry requires resolution: '+e['status'])
    if e['kind']=='directory':
        return dict(status='read_in_place',records=e['paths'][0],originals_modified=False)
    if e['kind']!='zip':raise ValueError('Use the installed local archiver for this archive format')
    return unpack_paths(e['paths'],destination)


def make_spec(export_path, runs, config_local, out):
    from publication import validate
    value=validate(read(export_path))
    config=Path(config_local).resolve()
    if not config.is_file():raise FileNotFoundError(config)
    actual=[str(Path(p).resolve()) for p in runs]
    if any(not Path(p).is_dir() for p in actual):raise ValueError('Selected local run is absent')
    value.update(runs=actual,config_local=str(config),result_delivery='local',
                 local_source_rule='Explicit local runs; no raw download and no per-case best-of-versions selection')
    write(out,value)
    return dict(spec=str(Path(out).resolve()),runs=actual,publication_id=value['publication_id'])
