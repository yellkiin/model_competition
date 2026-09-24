"""Summarize the 1,500 independently checked official final timelines."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'求解/正式实验/逐问核验摘要.json'
result={}
for q,label in [('q1','一'),('q2','二'),('q3','三')]:
    files=sorted((ROOT/f'求解/问题{label}/结果/验证').glob('case_*_n*.json'))
    assert len(files)==500,(q,len(files))
    records=[json.loads(p.read_text(encoding='utf8')) for p in files]
    assert all(r['status']=='PASS' and r['makespan']>0 and 1<=r['num_cores']<=5 for r in records)
    digest=hashlib.sha256(''.join(hashlib.sha256(p.read_bytes()).hexdigest() for p in files).encode()).hexdigest()
    result[q]={'status':'verified','selected_configurations':len(files),
               'passed':sum(r['status']=='PASS' for r in records),
               'statement':'所选500组方案的覆盖、时间线及官方响应交叉核验全部通过',
               'files_digest_sha256':digest,
               'source_directory':f'求解/问题{label}/结果/验证'}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(OUT)
