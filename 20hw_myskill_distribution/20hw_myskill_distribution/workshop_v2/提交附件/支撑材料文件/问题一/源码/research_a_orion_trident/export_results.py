"""Publish real shard records, plot tables and <=40 MiB archive parts."""
from __future__ import annotations
import argparse, shutil, zipfile
from pathlib import Path
from .io import read,write


def export(root, out, include_all=False, part_mib=40):
    root,out=Path(root).resolve(),Path(out).resolve()
    if root==out or root in out.parents:
        raise ValueError('Publication must be outside the active run root')
    if not 1<=part_mib<=80:raise ValueError('Archive part size must be 1..80 MiB')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'PUBLICATION.json').exists():
        raise FileExistsError('Publication already exists; choose a new round or publication directory')
    report=read(root/'report/report.json') if (root/'report/report.json').is_file() else {}
    status=read(root/'shard_status.json') if (root/'shard_status.json').is_file() else {'complete':False}
    archive=out/'evidence.zip';tmp=out/'evidence.zip.tmp'
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for source in sorted(root.rglob('*')):
            if not source.is_file() or source.suffix=='.tmp':continue
            rel=source.relative_to(root)
            if not include_all and 'attempts' in rel.parts:continue
            z.write(source,(Path('run')/rel).as_posix())
        z.writestr('READ_ME.txt','Run-relative plans/results are the evidence. Absolute request paths describe the original execution only. Unpack into a new directory; collect uses the receiving host official attachment. Do not resume a moved experiment.\n')
    tmp.replace(archive)
    parts=[];limit=int(part_mib*2**20)
    if archive.stat().st_size>limit:
        with archive.open('rb') as src:
            index=0
            while True:
                chunk=src.read(limit)
                if not chunk:break
                index+=1;part=out/f'evidence.zip.part{index:03d}';part.write_bytes(chunk)
                parts.append({'path':part.name,'bytes':len(chunk)})
        archive.unlink()
    else:parts=[{'path':archive.name,'bytes':archive.stat().st_size}]
    for name in ('per_case.csv','budget_prefixes.csv','report.json','verification.json'):
        source=root/'report'/name
        if source.is_file():shutil.copyfile(source,out/name)
    for name in ('run_settings.json','shard_status.json','diagnostic_queue.json','gate.json','clock.json','manifest.json','seed_catalogue.json'):
        source=root/name
        if source.is_file():shutil.copyfile(source,out/name)
    for directory in ('paper_data',):
        source=root/'report'/directory
        if source.is_dir():shutil.copytree(source,out/directory,dirs_exist_ok=True)
    for name in ('cache_parameter_grid.csv','mechanism_status.json'):
        source=root/'mechanisms'/name
        if source.is_file():shutil.copyfile(source,out/name)
    plan_root=root/'report/plans';count=0
    with zipfile.ZipFile(out/'selected_plans.zip','w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        if plan_root.is_dir():
            for p in sorted(plan_root.rglob('*.json')):
                z.write(p,p.relative_to(plan_root).as_posix());count+=1
    (out/'.gitattributes').write_text('*.zip -filter -diff -merge\n*.part* -filter -diff -merge\n',encoding='utf8')
    complete=bool(status.get('complete')) and count==status.get('expected_main') and report.get('paired')==status.get('expected_pairs')
    info={'source_run':str(root),'archive_parts':parts,'archive_format':'ZIP with run/ prefix; concatenate parts in listed order',
          'shard_status':status,'all_candidate_files':include_all,'selected_plan_count':count,
          'selected_outputs_complete':complete,'main_count':report.get('successful_main',0),
          'pair_count':report.get('paired',0),'formal_100_complete':report.get('formal_complete',False),
          'automatic_upload':False,'restore_command':'python -m research_a_orion_trident.unpack_results <this-directory> --out <new-directory>'}
    write(out/'PUBLICATION.json',info)
    (out/'README.md').write_text(f'# ORION Trident SMF publication\n\nSelected plans: {count}. Main records: {info["main_count"]}. Cache pairs: {info["pair_count"]}. This shard complete: {complete}. Full 100-case complete: {info["formal_100_complete"]}.\n\nSee per_case.csv and paper_data for plot tables. Raw records are in the archive parts listed by PUBLICATION.json. Partial publications retain their actual incomplete status.\n',encoding='utf8')
    return info


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--out',required=True)
    p.add_argument('--include-all-candidates',action='store_true');p.add_argument('--part-mib',type=int,default=40)
    a=p.parse_args(argv);print(export(a.root,a.out,a.include_all_candidates,a.part_mib))
if __name__=='__main__':main()
