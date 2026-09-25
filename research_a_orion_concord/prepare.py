"""Portable graph-balanced shards and selective restoration of FINAL records.

Use a clean checkout of the delivery commit. Read only provided archives; no
network install, hash stage, input rewrite or experiment during preparation.
"""
from __future__ import annotations
import argparse
import bisect
import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from .io import ROOT,PACKAGE,read,write,csv_read,csv_write,utc,attachment
from .seeds import build

class SplitReader(io.RawIOBase):
    """Seek a split ZIP as one byte stream, without a second archive-sized copy."""
    def __init__(self,parts):
        super().__init__();self.parts=[Path(p) for p in parts];self.ends=[0];self.position=0
        for p in self.parts:self.ends.append(self.ends[-1]+p.stat().st_size)
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        target=offset if whence==0 else self.position+offset if whence==1 else self.ends[-1]+offset
        if target<0:raise ValueError('Negative archive seek')
        self.position=target;return target
    def read(self,size=-1):
        left=self.ends[-1]-self.position
        if size>=0:left=min(left,size)
        out=[]
        while left>0:
            i=bisect.bisect_right(self.ends,self.position)-1
            take=min(left,self.ends[i+1]-self.position)
            with self.parts[i].open('rb') as f:
                f.seek(self.position-self.ends[i]);b=f.read(take)
            if not b:raise OSError('Incomplete ZIP part')
            out.append(b);left-=len(b);self.position+=len(b)
        return b''.join(out)

def archive_source(path):
    path=Path(path)
    if path.name=='TRANSFER_PARTS.json':
        return SplitReader([path.parent/r['name'] for r in read(path)['parts']])
    return path

def extract_selected(path,out,cases):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);count=0
    tagged={'case_'+v for v in re.findall(r'case[-_]?(\d{3})',Path(path).name)}
    with zipfile.ZipFile(archive_source(path)) as z:
        for entry in z.infolist():
            name=entry.filename.replace('\\','/');p=Path(name)
            ids=set(re.findall(r'case_\d{3}',name))
            ids.update('case_'+c for c in re.findall(r'(?:^|/)(\d{3})_q[0123]_n[1-5]',name))
            if not (ids.intersection(cases) or (not ids and tagged.intersection(cases))) or entry.is_dir():continue
            if p.is_absolute() or '..' in p.parts:raise ValueError('Archive path escapes destination')
            target=out/p;target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(entry) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
            count+=1
    write(out/'restoration.json',dict(source=str(path),files=count,cases=sorted(cases)))
    return out

def manifest(publication,official,speeds=(1.,1.,1.)):
    times={f'case_{i:03d}':0. for i in range(1,101)}
    for r in csv_read(publication):
        times[r['case']]+=float(r.get('solve_seconds') or 0)
    weights={}
    for case,seconds in times.items():
        size=(official/'data'/f'{case}.json').stat().st_size
        # Historical machine seconds are for sharding ONLY, not algorithm speedup.
        weights[case]=max(1.,seconds)+size/50000.
    shards={str(i):dict(cases=[],weight=0.,relative_speed=speeds[i]) for i in range(3)}
    quotas=[34,33,33]
    for case in sorted(weights,key=lambda c:(-weights[c],c)):
        i=min((i for i in range(3) if len(shards[str(i)]['cases'])<quotas[i]),
              key=lambda i:shards[str(i)]['weight']/speeds[i])
        shards[str(i)]['cases'].append(case);shards[str(i)]['weight']+=weights[case]
    published={(r['case'],int(r['q']),int(r['n'])):r for r in csv_read(publication)}
    # Shorter first graph is a real full-protocol gate and is reused by full run.
    for row in shards.values():
        row['cases'].sort(key=lambda c:weights[c]);row['gate_case']=row['cases'][0]
        ranked=sorted(row['cases'],key=lambda c:float(published.get((c,3,5),{}).get('cache_speedup') or 1.),reverse=True)
        row['study_cases']=list(dict.fromkeys([ranked[0],row['cases'][len(row['cases'])//2]]))
    return dict(schema=1,created_utc=utc(),shards=shards,weights=weights,
        assignment='longest estimated work first; 34/33/33; entire graph stays on one host',
        source_revision='055bb20a3b660f23d2179d732c82234aa1e8ba0a',case_budget_seconds=600)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--official');p.add_argument('--shard',type=int,choices=[0,1,2],required=True)
    p.add_argument('--out',required=True);p.add_argument('--raw-roots',nargs='*',default=[])
    p.add_argument('--archives',nargs='*',default=[]);p.add_argument('--extra-index',nargs='*',default=[])
    p.add_argument('--manifest',default=str(PACKAGE/'SHARDS.json'))
    p.add_argument('--publication',default=str(ROOT/'research_a_orion_anytime/team_results/day01/combined_final/per_case.csv'))
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);official=attachment(a.official)
    assignment=read(a.manifest) if Path(a.manifest).is_file() else manifest(a.publication,official)
    write(out/'manifest.json',assignment);cases=set(assignment['shards'][str(a.shard)]['cases'])
    roots=list(a.raw_roots);archives=list(a.archives)
    if not roots and not archives:
        for i in (0,1):
            folder=ROOT/f'research_a_orion_anytime/team_results/day01/shard_{i}/final'
            chunks=folder/'TRANSFER_PARTS.json'
            if chunks.exists():archives.append(str(chunks))
            else:
                choices=list(folder.glob('*.zip'))
                if len(choices)!=1:raise FileNotFoundError(f'Supply FINAL archive or --raw-roots for shard {i}')
                archives.append(str(choices[0]))
    for i,path in enumerate(archives):
        dest=out/'raw'/f'archive_{i}'
        if not dest.exists():extract_selected(path,dest,cases)
        roots.append(str(dest))
    # Include all actually exported newer FIFO plans, not just one report winner.
    extra=list(a.extra_index)
    fifo=ROOT/'research_a_orion_track_anytime/results/reconcile_20260925_1012'
    if (fifo/'per_case.csv').exists():
        entries=[]
        for row in csv_read(fifo/'per_case.csv'):
            case=row['case'];num=case.removeprefix('case_')
            pp=fifo/'selected'/num/row['batch']/row['method']/'plan.json'
            if case in cases and pp.exists() and row.get('makespan'):
                entries.append(dict(case=case,q=int(row['q']),n=int(row['n']),plan_file=str(pp),recorded_makespan=float(row['makespan']),source='reconcile exported plan'))
        index=out/'newer_fifo_plans.json';write(index,entries);extra.append(str(index))
    catalog=out/'seeds/catalog.json'
    if not catalog.exists():build(roots,catalog.parent,cases,a.publication,extra_indices=extra)
    data=read(catalog);have={(r['case'],r['q'],r['n']) for r in data['entries']}
    from .run import required
    expected={(c,q,n) for c in cases for q,n in [(0,1)]+required()}
    missing=sorted(expected-have)
    report=dict(shard=a.shard,cases=sorted(cases),expected=len(expected),available=len(expected&have),missing=missing,
        catalog=str(catalog),ready=not missing,extra_index=a.extra_index,
        note='Full deployment requires all actual reference plans; numerical targets alone are not solutions.')
    write(out/'prepared.json',report);print(json.dumps(report,ensure_ascii=False))
    return 0 if report['ready'] else 3

if __name__=='__main__':raise SystemExit(main())
