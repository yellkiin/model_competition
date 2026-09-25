"""Unpack actual selected plans from a compact, readable run-length record."""
from __future__ import annotations
import argparse, json, lzma
from pathlib import Path
from .io import ROOT, read, write, official_root


def run(official=None, destination=None):
    folder=Path(__file__).parent/'evidence'
    sources=sorted(list(folder.glob('compact_seeds*.json'))+list(folder.glob('compact_seeds*.json.xz')))
    out=Path(destination) if destination else Path(__file__).parent/'runs/installed_seeds'
    of,_=official_root(official);installed=[];missing=[]
    by_key={}
    for source in sources:
        data=json.loads(lzma.decompress(source.read_bytes()).decode('utf8')) if source.suffix=='.xz' else read(source)
        for row in data['plans']:
            key=row['case'],row['q'],row['n']
            if key not in by_key or row['makespan']<by_key[key]['makespan']:by_key[key]=row
    for key,row in sorted(by_key.items()):
        graph=of/'data'/(row['case']+'.json')
        if not graph.is_file():missing.append(row['case']);continue
        ids=sorted(o['id'] for o in read(graph)['ops'] if o['op'] not in ('COPY_IN','COPY_OUT'))
        if len(ids)!=row['op_count']:raise ValueError('Actual source graph does not match seed operation count')
        owners=[s for s,count in row['group_runs'] for _ in range(count)]
        if len(owners)!=len(ids):raise ValueError('Incomplete compact plan')
        plan={'node_to_subgraph':dict(zip(map(str,ids),owners)),'core_schedules':row['core_schedules']}
        path=out/f'q{row["q"]}'/f'n{row["n"]}'/(row['case']+'_multicore_res.json')
        write(path,plan)
        installed.append({'case':row['case'],'q':row['q'],'n':row['n'],'makespan':row['makespan'],'path':str(path.resolve())})
    write(out/'SEED_INDEX.json',{'entries':installed,'missing_source_graphs':sorted(set(missing)),
                                 'scores_are_prior_records':True})
    return installed


def main():
    p=argparse.ArgumentParser();p.add_argument('--official');p.add_argument('--out');a=p.parse_args()
    print('Restored',len(run(a.official,a.out)),'actual plans; the solver re-evaluates each accepted seed.')
if __name__=='__main__':main()
