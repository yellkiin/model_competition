"""Read-only source/evidence export for the independent recheck. No solver tests."""
from pathlib import Path
import json, re, shutil, subprocess, zipfile

ROOT=Path(__file__).resolve().parents[1]
CASES={'001','016','024','044','048','059','064','084'}

def main():
    target=Path('/tmp/orion_recheck_sources.zip')
    manifest={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), 'files':[], 'raw_archives':[]}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as out:
        def put(p, arc=None):
            name=arc or str(p.relative_to(ROOT))
            out.write(p,name); manifest['files'].append({'path':name,'bytes':p.stat().st_size})
        for dirname in ['research_a_orion_anytime','research_a_orion_track_structure','research_a_orion_review_3pc','tools']:
            d=ROOT/dirname
            if d.exists():
                for p in sorted(d.iterdir()):
                    if p.is_file() and p.suffix in ('.py','.md','.ps1','.json'):put(p)
        off=ROOT/'题目/A题/通用神经网络处理器下的多核调度问题  附件'
        for p in sorted((off/'code').rglob('*.py')):put(p)
        for p in sorted((off/'docs').rglob('*')) if (off/'docs').exists() else []:
            if p.is_file():put(p)
        for p in sorted((ROOT/'题目/A题').glob('*.docx')):put(p)
        if (off/'README.md').exists():put(off/'README.md')
        for c in sorted(CASES):put(off/'data'/f'case_{c}.json')
        put(off/'data/config.txt')
        lib=ROOT/'调研/A题_文献库'
        for p in sorted(lib.glob('*.md')):put(p)
        put(ROOT/'调研/A题_文献.json')
        for pattern in ('A01_*','A02_*','A08_*','A33_*','A39_*','A42_*','A49_*'):
            for p in (lib/'pdf').glob(pattern):put(p)
        day=ROOT/'research_a_orion_anytime/team_results/day01'
        put(day/'latest.json')
        for p in (day/'combined_final').iterdir():
            if p.is_file() and p.suffix in ('.csv','.json','.md','.zip'):put(p)
        for p in (ROOT/'research_a_orion_track_structure/results').rglob('*'):
            if p.is_file():put(p)
        for shard,mn in [('shard_0','TRANSFER_PARTS.json'),('shard_1','ARCHIVE_PARTS.json')]:
            d=day/shard/'final'; m=json.loads((d/mn).read_text(encoding='utf-8-sig'))
            temp=Path('/tmp')/(shard+'_raw.zip')
            with temp.open('wb') as w:
                for part in m['parts']:
                    with (d/part['name']).open('rb') as r:shutil.copyfileobj(r,w)
            entries=[]
            with zipfile.ZipFile(temp) as z:
                for inf in z.infolist():
                    match=re.search(r'case_(\d{3})',inf.filename)
                    if not inf.is_dir() and ((match and match[1] in CASES) or (not match and inf.file_size<250000 and inf.filename.endswith(('.json','.csv','.md')))):
                        arc='raw_day01/'+shard+'/'+inf.filename
                        out.writestr(arc,z.read(inf)); entries.append({'path':inf.filename,'bytes':inf.file_size})
            manifest['raw_archives'].append({'shard':shard,'archive_name':m['archive_name'],'entries':entries})
            temp.unlink()
        out.writestr('EXPORT_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({'archive':str(target),'bytes':target.stat().st_size,'files':len(manifest['files']),'source_commit':manifest['source_commit']}))

if __name__=='__main__':main()
