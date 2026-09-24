"""Recompute all three formal selections and independently recheck recorded traces.

Run inside one question's packaged 源码 directory. The two shared ZIP files
contain the unchanged official inputs and every formal candidate response.
This is a complete replay of candidate selection and independent verification;
it does not claim to rerun all expensive official event simulations.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

APP=Path(__file__).resolve().parent
SHARED=APP.parent.parent
ARCHIVES=(SHARED/'其他数据/官方输入.zip',
          SHARED/'其他支撑材料/正式候选评估.zip')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def unpack(path):
    with ZipFile(path) as archive:
        for info in archive.infolist():
            target=(APP/info.filename).resolve()
            target.relative_to(APP)
            if target.exists():
                raise RuntimeError('复现输入应从空目录解包：'+info.filename)
        archive.extractall(APP)

def solve():
    expected=APP/'求解/正式实验/总体摘要.json'
    if expected.exists():raise RuntimeError('复现输出运行前不得存在')
    for archive in ARCHIVES:
        if not archive.is_file():raise FileNotFoundError(archive)
        unpack(archive)
    subprocess.run([sys.executable,'-B',str(APP/'求解/collect_official_results.py'),
                    '--cases','100','--max-cores','5'],cwd=APP,check=True)

def validate():
    run_dir=APP/'求解/正式实验/候选评估'
    receipt_files=sorted(run_dir.rglob('*.receipt.json'))
    if len(receipt_files)!=2005:raise RuntimeError(f'候选评估收据数错误：{len(receipt_files)}')
    by_question={0:0,1:0,2:0,3:0}
    for receipt_file in receipt_files:
        row=json.loads(receipt_file.read_text(encoding='utf-8'))
        if row.get('status')!='PASS':raise RuntimeError('正式候选失败：'+str(receipt_file))
        result_file=receipt_file.with_name(receipt_file.name.replace('.receipt.json','.json.gz'))
        if digest(result_file)!=row['result_sha256']:
            raise RuntimeError('官方响应摘要不匹配：'+str(result_file))
        with gzip.open(result_file,'rt',encoding='utf-8') as stream:
            result=json.load(stream)
        if result['makespan']!=row['makespan']:
            raise RuntimeError('收据时长不匹配：'+str(receipt_file))
        by_question[int(row['problem'])]+=1
    if by_question!={0:100,1:577,2:664,3:664}:
        raise RuntimeError('候选分布不匹配：'+str(by_question))
    subprocess.run([sys.executable,'-B',str(APP/'求解/summarize_validations.py')],
                   cwd=APP,check=True)
    summary=json.loads((APP/'求解/正式实验/总体摘要.json').read_text(encoding='utf-8'))
    validation=json.loads((APP/'求解/正式实验/逐问核验摘要.json').read_text(encoding='utf-8'))
    if len(summary)!=15 or any(row['cases']!=100 for row in summary):
        raise RuntimeError('正式汇总不完整')
    if any(validation[q]['passed']!=500 for q in ('q1','q2','q3')):
        raise RuntimeError('所选时间线核验未全通过')
    report={'status':'PASS','candidate_receipts':len(receipt_files),
            'candidate_counts':by_question,'selected_configs_per_question':500,
            'aggregate_rows':len(summary),'official_inputs':str(ARCHIVES[0].name),
            'formal_candidate_archive':str(ARCHIVES[1].name),
            'limitation':'完整回放选择与独立核验；官方事件模拟的全部响应沿用正式运行保存的原始输出。'}
    out=APP/'求解/正式实验/复现校验.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(out)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('solve','validate'))
    args=parser.parse_args()
    (solve if args.action=='solve' else validate)()
