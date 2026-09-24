"""Split a completed standard transfer archive for GitHub's per-file limit."""
import json
import shutil
import sys
import zipfile
from pathlib import Path
from build_snapshot import BASE,read,put

stage=sys.argv[1]
root=BASE/'phase_publication_20260924/artifacts/shard_0'/stage
name=f'team_day01_shard0_{stage}.zip'
archive=root/name
with zipfile.ZipFile(archive) as z:
    names=z.namelist()
    assert 'TRANSFER.json' in names and 'run/campaign.json' in names
    assert 'run/'+('final_index.json' if stage=='final' else 'phase_index.json') in names
    assert len([n for n in names if n.startswith('run/coverage/') and n.endswith('/summary.json')])==700
    assert len([n for n in names if n.startswith('run/refinement/') and n.endswith('/summary.json')])==620
    assert len([n for n in names if n.startswith('run/pairs/') and n.endswith('/summary.json')])==(250 if stage=='final' else 0)
    assert not any(n.startswith(('run/data/','run/code/')) for n in names)
    total_entries=len(names)
limit=90*1024**2;parts=[]
with archive.open('rb') as src:
    i=1
    while src.tell()<archive.stat().st_size:
        part=root/f'{name}.part{i:03d}'
        if part.exists():raise ValueError('Existing immutable part: '+str(part))
        size=0
        with part.open('xb') as dst:
            while size<limit:
                block=src.read(min(1024**2,limit-size))
                if not block:break
                dst.write(block);size+=len(block)
        parts.append(dict(name=part.name,bytes=size));i+=1
assert sum(p['bytes'] for p in parts)==archive.stat().st_size
put(root/'TRANSFER_PARTS.json',dict(schema_version=1,format='ordered byte chunks of one standard TRANSFER.json + run/ ZIP',
    archive_name=name,archive_bytes=archive.stat().st_size,archive_entries=total_entries,parts=parts,
    reconstruction='Run python reassemble_transfer.py in this folder; then use the original transfer unpack into a new empty root.',
    note='All result entries, including failed jobs, are retained. Only byte counts and ZIP directory structure were checked; no additional experiment or signature test.'))
(root/'reassemble_transfer.py').write_text('''"""Join ordered release parts; preserve the original standard transfer format."""
import json
from pathlib import Path
r=Path(__file__).resolve().parent
m=json.loads((r/'TRANSFER_PARTS.json').read_text(encoding='utf8'))
out=r/m['archive_name']
if out.parent!=r or out.exists():raise ValueError('Output must be a new file beside the parts')
for p in m['parts']:
 f=r/p['name']
 if f.parent!=r or f.stat().st_size!=p['bytes']:raise ValueError('Missing or wrong-size part: '+p['name'])
with out.open('xb') as dst:
 for p in m['parts']:
  with (r/p['name']).open('rb') as src:
   while True:
    b=src.read(1024*1024)
    if not b:break
    dst.write(b)
if out.stat().st_size!=m['archive_bytes']:raise ValueError('Reconstructed size differs')
print(out)
''',encoding='utf8')
(root/'TRANSFER_README.md').write_text(f'''# 结果包重组与读取

本目录的 {len(parts)} 个 .part 文件是一个标准 transfer ZIP 的连续字节分卷，不是互相独立的ZIP。必须下载全部分卷以及 TRANSFER_PARTS.json、reassemble_transfer.py 到同一目录。完整ZIP大小 {archive.stat().st_size:,} 字节；目录内共 {total_entries:,} 项。所有失败证据均保留。

在该目录执行 `D:\\python\\python.exe reassemble_transfer.py`，生成 `{name}`；脚本拒绝覆盖已有输出。它按清单检查分卷字节数并顺序拼接，不启动任何求解。

回到原ORION运行包根，用已有模块解压到新空输出根：

```powershell
& 'D:\\python\\python.exe' -m research_a_orion_anytime.transfer unpack --zip '<本目录绝对路径>\\{name}' --root '<新的空接收根>'
```

阶段版使用 phase_index.json，缓存pending，不能冒充final；最终版保留 final_index.json 与原700项verification。正式合并两片需要各自最终包，使用原官方输入执行原campaign collect。包中不含官方图/config/evaluator，不要在接收根继续formal求解。

execution_provenance 是历史执行证据，其旧来源路径不用于继续运行。活动输出根内的可用主结果引用已按原transfer.rewrite重定位；接收机unpack再次重定位。不要为了快迭代修改或混入本轮成绩。
''',encoding='utf8')
print(json.dumps(dict(stage=stage,archive_bytes=archive.stat().st_size,parts=parts,entries=total_entries)))
