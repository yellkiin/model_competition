"""Publish one host's portable experiment evidence; never upload automatically."""
from __future__ import annotations
import argparse, shutil, zipfile
from pathlib import Path
from .io import read,write


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--out',required=True)
    p.add_argument('--include-all-candidates',action='store_true')
    a=p.parse_args(argv);root=Path(a.root).resolve();out=Path(a.out).resolve()
    if root==out or root in out.parents:raise ValueError('Publication must be outside the active run root')
    out.mkdir(parents=True,exist_ok=True)
    archive=out/'evidence.zip';tmp=out/'evidence.zip.tmp'
    # Keep every request, progress, selected response, failure and attempt metric.
    # Candidate plans/retained raw responses can be bulky; include them explicitly.
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for source in sorted(root.rglob('*')):
            if not source.is_file() or source.suffix=='.tmp':continue
            rel=source.relative_to(root)
            if not a.include_all_candidates and 'attempts' in rel.parts:continue
            z.write(source,str(Path('run')/rel))
        z.writestr('READ_ME.txt','Selected plans/results and progress are relative within each job. Source request paths are provenance only; collect uses the local --official root. Do not resume a moved run under its original absolute paths.\n')
    tmp.replace(archive)
    for name in ('per_case.csv','budget_prefixes.csv','report.json','verification.json'):
        source=root/'report'/name
        if source.is_file():shutil.copyfile(source,out/name)
    for name in ('run_settings.json','shard_status.json','diagnostic_queue.json','gate.json','clock.json','manifest.json'):
        source=root/name
        if source.is_file():shutil.copyfile(source,out/name)
    status=read(root/'shard_status.json') if (root/'shard_status.json').is_file() else {'complete':False}
    write(out/'PUBLICATION.json',{'source_run':str(root),'archive':'evidence.zip','shard_status':status,
        'all_candidate_files':a.include_all_candidates,'selected_outputs_complete':True,
        'automatic_upload':False})
    print(archive)

if __name__=='__main__':main()
