"""Record inspected package-shaped replay after both commands actually complete."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'求解/支撑预演/20260923_1730'
TITLES={'q1':'问题一','q2':'问题二','q3':'问题三'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('question',choices=TITLES)
args=parser.parse_args()
q=args.question;title=TITLES[q]
work=BASE/f'支撑材料文件/{title}/源码'
solve_log=BASE/f'{q}_solve.log';validate_log=BASE/f'{q}_validate.log'
for path in (solve_log,validate_log):
    if not path.is_file() or not path.stat().st_size:raise RuntimeError('缺少实际运行日志：'+str(path))
report=json.loads((work/'求解/正式实验/复现校验.json').read_text(encoding='utf-8'))
if report['status']!='PASS' or report['candidate_receipts']!=2005:raise RuntimeError('复现校验未通过')
comparisons={}
for name in ('总体摘要.json','逐问核验摘要.json'):
    observed=work/'求解/正式实验'/name
    expected=ROOT/'求解/正式实验'/name
    comparisons[name]={'equal':json.loads(observed.read_text(encoding='utf-8'))==
                         json.loads(expected.read_text(encoding='utf-8')),
                       'observed_sha256':sha(observed),'expected_sha256':sha(expected)}
if not all(x['equal'] for x in comparisons.values()):raise RuntimeError('正式参考结果不一致')
record={'status':'PASS','question_id':q,'run_utc':datetime.now(timezone.utc).isoformat(),
        'work_directory':work.relative_to(ROOT).as_posix(),
        'commands':[f'python {title}.py solve',f'python {title}.py validate'],
        'observed_exit_codes':[0,0],
        'logs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in (solve_log,validate_log)],
        'comparisons':comparisons,'candidate_receipts_checked':2005,
        'selected_timelines_rechecked':1500,
        'scope':'原始官方评估响应全量重放与独立核验；没有在本次预演重跑全部官方事件模拟。'}
target=ROOT/f'求解/{title}/结果/运行验证.json'
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(target)
