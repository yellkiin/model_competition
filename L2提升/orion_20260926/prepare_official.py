"""Materialize only original A code/config and requested real cases, unchanged.

No evaluation, hashes, tests, other-question recovery, or large seed ZIP download.
Requires the existing repository's Git object access (lazy blob fetch supported).
"""
from pathlib import Path
import argparse,json,subprocess

PIN='b513a98f86183a8c1b41d67a547f06fa9d578e2a'
ATTACH='题目/A题/通用神经网络处理器下的多核调度问题  附件'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root',default='.')
    p.add_argument('--out',required=True)
    p.add_argument('--ref',default=PIN)
    p.add_argument('--cases',nargs='+',default=['001','026','030','033','080','083'])
    p.add_argument('--fetch',action='store_true')
    args=p.parse_args();repo=Path(args.repo_root).resolve();out=Path(args.out).resolve()
    if out.exists():raise FileExistsError('Choose a new output directory; existing input is preserved')
    if args.fetch:subprocess.run(['git','fetch','--filter=blob:none','--no-tags','origin',args.ref],cwd=repo,check=True)
    raw=subprocess.run(['git','ls-tree','-r','-z','--name-only',args.ref,'--',ATTACH+'/code'],cwd=repo,check=True,capture_output=True).stdout
    code=[s for s in raw.decode('utf8').split('\0') if s.endswith('.py')]
    if not code:raise FileNotFoundError('Original A code is unavailable at requested ref')
    paths=[(s,'code/'+s.split('/code/',1)[1]) for s in code]
    paths.append((ATTACH+'/data/config.txt','data/config.txt'))
    for case in args.cases:
        number=int(case.removeprefix('case_'))
        if not 1<=number<=100:raise ValueError('Official case outside 001..100')
        name=f'case_{number:03d}.json';paths.append((ATTACH+'/data/'+name,'data/'+name))
    out.mkdir(parents=True);completed=[]
    for src,dst in paths:
        target=out/dst;target.parent.mkdir(parents=True,exist_ok=True)
        tmp=target.with_name(target.name+'.part')
        with tmp.open('wb') as f:
            subprocess.run(['git','show',args.ref+':'+src],cwd=repo,stdout=f,check=True)
        with tmp.open('rb') as f:prefix=f.read(100)
        if prefix.startswith(b'version https://git-lfs.github.com'):
            raise RuntimeError('Original file is an LFS pointer; restore actual A attachment, do not substitute: '+src)
        tmp.replace(target);completed.append(dict(source=src,destination=dst))
        (out/'MATERIALIZED.json').write_text(json.dumps(dict(original_ref=args.ref,files=completed),ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(official_dir=str(out),files=len(completed),original_ref=args.ref),ensure_ascii=False))

if __name__=='__main__':main()
