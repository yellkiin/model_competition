"""Materialize only required original files from a pinned local/remote Git ref.

Git stdout is written as bytes, including the 19MB selected-plan ZIP. No shell
re-encoding, source patching, checksum scan or benchmark is performed. A partial
Git clone will lazily obtain the requested blobs; a full existing clone reuses
its object store. Run in a separate checkout, not an active experiment folder.
"""
from __future__ import annotations
import argparse, json, subprocess, shutil, time
from pathlib import Path
from .io import ROOT,read,write,install_plan_archive

PIN='b513a98f86183a8c1b41d67a547f06fa9d578e2a'
ATTACH='题目/A题/通用神经网络处理器下的多核调度问题  附件'
REF='research_a_orion_anytime/team_results/day01/combined_final'
TABLES=('per_case.csv','lower_tail.csv','improvements.csv','budget_prefixes.csv','cache_pairs.csv','selected_plans.zip')


def run(shard,assets,ref=PIN,git_root=None,fetch=False,literature=False):
    started=time.monotonic()
    repo=Path(git_root or ROOT).resolve();assets=Path(assets).resolve();assets.mkdir(parents=True,exist_ok=True)
    prior=assets/'INPUT_RECEIPT.json'
    if prior.is_file() and (read(prior)['original_ref']!=ref or read(prior)['shard']!=shard):
        raise ValueError('Input receipt differs; choose a new assets directory')
    if fetch:
        subprocess.run(['git','fetch','--filter=blob:none','--no-tags','origin',ref],cwd=repo,check=True)
    subprocess.run(['git','cat-file','-e',ref+'^{commit}'],cwd=repo,check=True)
    manifest=read(Path(__file__).parent/'SHARDS.json')
    cases=manifest['shards'][shard]['cases'];copied=[]
    def materialize(src,dst):
        dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.is_file() and dst.stat().st_size:
            with dst.open('rb') as f:first=f.read(100)
            if not first.startswith(b'version https://git-lfs.github.com'):
                return
        tmp=dst.with_name(dst.name+'.part')
        with tmp.open('wb') as output:
            subprocess.run(['git','show',ref+':'+src],cwd=repo,stdout=output,check=True)
        with tmp.open('rb') as f:first=f.read(100)
        if first.startswith(b'version https://git-lfs.github.com'):
            raise ValueError('Actual blob is still an LFS pointer: '+src)
        tmp.replace(dst);copied.append({'source':src,'destination':str(dst),'bytes':dst.stat().st_size})
    # -z avoids Git quotePath escaping Chinese path components.
    raw=subprocess.run(['git','ls-tree','-r','-z','--name-only',ref,'--',ATTACH+'/code'],cwd=repo,capture_output=True,check=True).stdout
    for name in raw.decode('utf8').split('\0'):
        if name.endswith('.py'):materialize(name,assets/'official/code'/Path(name).name)
    materialize(ATTACH+'/data/config.txt',assets/'official/data/config.txt')
    for c in cases:materialize(ATTACH+'/data/'+c+'.json',assets/'official/data'/(c+'.json'))
    for name in TABLES:materialize(REF+'/'+name,assets/'reference'/name)
    if not (assets/'reference_plans/INSTALLED.json').exists():
        count=install_plan_archive(assets/'reference/selected_plans.zip',assets/'reference_plans')
        write(assets/'reference_plans/INSTALLED.json',{'plans':count,'source':ref,'scope':'original byte-stream ZIP'})
    # Reading material is small and shared; never needed inside a solver clock.
    for src in ('调研/A题_文献.json','调研/A题_文献库/README.md','调研/A题_文献库/方法对照与阅读顺序.md','题目/A题/通用神经网络处理器下的多核调度问题.docx'):
        materialize(src,assets/'reading'/Path(src).name)
    if literature:
        for name in ('A12_2020_Ansor.pdf','A16_2023_COSMA.pdf','A39_2021.pdf','A42_2024.pdf'):
            materialize('调研/A题_文献库/pdf/'+name,assets/'reading'/name)
    receipt={'original_ref':ref,'shard':shard,'cases':cases,'copied':copied,
             'official':str(assets/'official'),'reference':str(assets/'reference'),
             'plans':str(assets/'reference_plans'),'transfer_is_outside_solve_clock':True,'input_setup_seconds':time.monotonic()-started}
    write(assets/'INPUT_RECEIPT.json',receipt);return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--shard-index',type=int,choices=range(3),required=True)
    p.add_argument('--out',required=True);p.add_argument('--git-root');p.add_argument('--ref',default=PIN)
    p.add_argument('--fetch',action='store_true');p.add_argument('--literature',action='store_true')
    a=p.parse_args();r=run(a.shard_index,a.out,a.ref,a.git_root,a.fetch,a.literature)
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
