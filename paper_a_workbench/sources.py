"""Read an authorized Git cache in bounded batches; never execute research code."""
from __future__ import annotations
import concurrent.futures as cf
import json, os, re, subprocess
from pathlib import Path
from common import read,write,within,stamp,fresh

TEXT={'.py','.md','.json','.csv','.tex','.bib','.txt','.ps1','.toml','.yaml','.yml','.sty','.cls'}
IGNORE={'.git','__pycache__','.venv','node_modules','site-packages'}

class GitSource:
    def __init__(self, root):
        self.root=Path(root).resolve()
        self.run('rev-parse','--git-dir')
    def run(self,*args):
        p=subprocess.run(['git','-C',str(self.root),*args],capture_output=True,check=False)
        if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace')[-3000:])
        return p.stdout
    def resolve(self, ref, fetch=False):
        if ref.startswith('-'):raise ValueError('Invalid ref')
        if fetch:
            self.run('fetch','--filter=blob:none','--no-tags','origin',ref)
            ref='FETCH_HEAD'
        value=self.run('rev-parse','--verify',ref+'^{commit}').decode().strip()
        if not re.fullmatch('[0-9a-f]{40,64}',value):raise ValueError('Expected commit identifier')
        return value
    def entries(self,revision,prefix):
        within(self.root,prefix)
        raw=self.run('ls-tree','-r','-z',revision,'--',prefix or '.')
        out=[]
        for entry in raw.split(b'\0'):
            if not entry:continue
            meta,name=entry.split(b'\t',1);mode,kind,blob=meta.decode().split()
            if kind!='blob' or mode not in ('100644','100755'):continue
            path=name.decode('utf-8')
            if not IGNORE.intersection(Path(path).parts):out.append((path,blob))
        return out
    def get(self,revision,path):
        return self.run('show',revision+':'+path)
    def hydrate(self,revision,paths):
        # Only the selected source paths, never all LFS data in the repository.
        include=','.join(v for p in paths for v in (p,p.rstrip('/')+'/**'))
        self.run('lfs','fetch','--include='+include,'--exclude=','origin',revision)
    def lfs_data(self,data):
        match=re.search(rb'^oid sha256:([0-9a-f]{64})$',data,re.M)
        if not match:raise ValueError('Malformed LFS pointer')
        oid=match.group(1).decode()
        root=Path(self.run('rev-parse','--git-common-dir').decode().strip())
        root=root if root.is_absolute() else self.root/root
        obj=root/'lfs/objects'/oid[:2]/oid[2:4]/oid
        # Object ID is only used to locate Git LFS's downloaded original, not a test.
        return obj.read_bytes()


def sync(repo, profile_path, home, *, fetch=False, metadata_only=False, workers=4, lfs=False):
    """Resolve each mutable ref ONCE; keep every prior snapshot untouched."""
    profile=read(profile_path);git=GitSource(repo)
    sid=stamp();out=fresh(Path(home)/'数据'/'ORION_论文资料'/'snapshots'/sid)
    rows=[];resolved={};errors=[]
    batch_size=max(1,int(profile.get('batch_size',16)))
    for group in profile['sources']:
        ref=group['ref']
        if ref not in resolved:resolved[ref]=git.resolve(ref,fetch=fetch)
        rev=resolved[ref];items=[]
        for prefix in group['paths']:
            items.extend(git.entries(rev,prefix))
        selected={}
        for path,blob in items:
            parts=Path(path).parts
            if any(x in group.get('exclude_parts',[]) for x in parts):continue
            if group.get('text_only') and Path(path).suffix.lower() not in TEXT:continue
            if metadata_only and (Path(path).suffix.lower() in {'.pdf','.docx','.zip'} or '/data/case_' in path):continue
            selected[path]=blob
        if not selected:
            errors.append({'source':group['id'],'error':'no matching source files','required':group.get('required',True)})
            continue
        def copy(item):
            path,blob=item
            try:
                data=git.get(rev,path)
                if data.startswith(b'version https://git-lfs.github.com/spec/'):
                    if lfs:
                        pointer=data
                        try:data=git.lfs_data(pointer)
                        except FileNotFoundError:
                            git.hydrate(rev,[path]);data=git.lfs_data(pointer)
                    else:return dict(source=group['id'],path=path,revision=rev,blob=blob,status='lfs_pointer',bytes=len(data))
                dest=within(out,group['id']+'/'+path);dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(data)
                return dict(source=group['id'],path=path,revision=rev,blob=blob,status='present',
                            bytes=len(data),local=str(dest.relative_to(out)))
            except (OSError,RuntimeError,ValueError) as exc:
                return dict(source=group['id'],path=path,revision=rev,blob=blob,status='copy_error',error=str(exc))
        # Each batch issues at most four concurrent blob reads.
        items=list(selected.items())
        for start in range(0,len(items),batch_size):
            with cf.ThreadPoolExecutor(max_workers=max(1,min(4,workers))) as pool:
                rows.extend(pool.map(copy,items[start:start+batch_size]))
            write(out/'COPY_PROGRESS.json',{'files':rows,'errors':errors})
    manifest={'schema':1,'snapshot_id':sid,'profile':profile,'resolved_refs':resolved,'files':rows,'errors':errors,
              'mode':'metadata_only' if metadata_only else 'full','role':'source_material_not_experiment_verification'}
    write(out/'SOURCE_LOCK.json',manifest)
    write(Path(home)/'.orion_paper'/'latest_snapshot.json',{'snapshot':str(out),'snapshot_id':sid})
    return manifest,out


def discover(repo, ref='main', fetch=False):
    git=GitSource(repo);revision=git.resolve(ref,fetch=fetch)
    records=[]
    for path,blob in git.entries(revision,''):
        name=Path(path).name
        if name not in {'PAPER_EXPORT.json','PAPER_SOURCE.json','latest.json','LATEST.json','FINAL_PUBLICATION.json'}:continue
        if path.startswith('paper_a_workbench/'):continue
        data=git.get(revision,path)
        try:obj=json.loads(data.decode('utf-8-sig'))
        except (ValueError,UnicodeError):continue
        records.append({'path':path,'revision':revision,'blob':blob,'publication':obj})
    return {'revision':revision,'candidates':records,'selection':'Review publication state, cohort, method and raw-record completeness before choosing ONE result set.'}


def changes(old,new):
    def index(value):return {(r['source'],r['path']):r for r in value['files']}
    a,b=index(read(old)),index(read(new));diff=[]
    for key in sorted(a.keys()|b.keys()):
        x,y=a.get(key),b.get(key)
        if x and y and x.get('blob')==y.get('blob') and x.get('status')==y.get('status'):continue
        suffix=Path(key[1]).suffix.lower()
        role=('theory_and_implementation_review' if suffix=='.py' or any(t in key[1].lower() for t in ('theory','method')) else
              'metrics_figures_abstract_conclusions' if suffix in {'.csv','.json','.gz'} else 'source_and_citation_review')
        diff.append({'source':key[0],'path':key[1],'change':'added' if not x else 'removed' if not y else 'modified','review':role})
    return {'changed_files':diff,'action':'Reopen affected claims and derived outputs. Engineering-only changes require a human-readable semantic comparison; filenames alone do not establish it.'}
