"""Run an explicitly isolated DEMO with real Ridge/RF/MLP and negative audits."""
from pathlib import Path
import argparse
import copy
import json
import shutil
import sys
import subprocess
from model_selection import (read, write, sha, run_experiment, audit_report, publish,
                             paper_gate, supporting_gate, contract_errors, FACTORS)


def setup(root, context):
    import numpy as np
    qroot=root/'求解/问题一'
    qroot.mkdir(parents=True,exist_ok=True)
    for name in ('model_demo_train.py','model_demo_validate.py'):
        shutil.copy2(context.template_root/'华为杯_求解规范/tools'/name,qroot/name)
    rng=np.random.default_rng(42)
    x=rng.uniform(-2,2,(480,5)).astype('float32')
    y=(2*x[:,0]+np.sin(3*x[:,1])+x[:,2]**2+.15*rng.normal(size=480)).astype('float32')
    write(qroot/'data.json',{'purpose':'demo','provenance':'Seeded synthetic nonlinear regression; not contest data','x':x.tolist(),'y':y.tolist()})
    ids=rng.permutation(480)
    write(qroot/'split.json',dict(kind='iid',train=[str(i) for i in ids[:300]],validation=[str(i) for i in ids[300:400]],
        test=[str(i) for i in ids[400:]],preprocessing='Fit all statistics on train IDs only; no test inspection.'))
    evidence=root/'求解/数据审计.md'
    evidence.write_text('DEMO：480行5维合成连续输入，非线性目标；300训练/100验证/80封存测试。CPU轻量MLP用于B类可行性试验，结果不用于赛题论文。',encoding='utf-8')
    candidates=[]
    for kind,family,name,reason,complexity in [('ridge','baseline','Ridge','线性正则模型建立低复杂度基准','6个系数'),
            ('rf','ml','Random Forest','树集成拟合非线性和交互作用','50棵浅树'),
            ('mlp','dl','轻量 MLP','两层隐藏表征检验非线性拟合价值','16和8维隐藏层')]:
        prefix=f'求解/问题一/结果/{kind}'
        Path(root/prefix).mkdir(parents=True,exist_ok=True)
        cfg=dict(run_id=kind+'01',question_id='q1',candidate_id=kind,kind=kind,seed=42,
                 data='求解/问题一/data.json',split='求解/问题一/split.json',selection_partition='validation',
                 inputs=['求解/问题一/data.json'],sources=['求解/问题一/model_demo_train.py','求解/问题一/model_demo_validate.py'],
                 checkpoint=prefix+'/checkpoint.pkl',predictions=prefix+'/predictions.json',training_record=prefix+'/training.json',metrics=prefix+'/metrics.json')
        cfg_path=f'求解/问题一/{kind}_config.json'
        cfg['outputs']=[cfg[k] for k in ('checkpoint','predictions','training_record','metrics')]
        cfg['commands']=[dict(purpose=p,argv=['{python}',s,'--config',cfg_path]) for p,s in zip(('train','validate'),cfg['sources'])]
        write(root/cfg_path,cfg)
        run=run_experiment(root,cfg_path)
        if run['status']!='PASS':
            raise RuntimeError('DEMO training failed: '+kind)
        receipt=f'求解/实验运行/q1/{kind}01/receipt.json'
        candidates.append(dict(id=kind,name=name,family=family,rationale=reason,complexity=complexity,
                               decision='保留统一验证结果参与比较',runs=[receipt],selected_run=receipt,failures={}))
    scores={c['id']:read(root/f"求解/问题一/结果/{c['id']}/metrics.json")['metrics']['rmse'] for c in candidates}
    winner=min(scores,key=scores.get)
    factors=dict(zip(FACTORS,['回归任务，以RMSE和MAE衡量误差','连续表格数据，非图像或时序','480条合成独立样本，训练300条','5维连续特征，没有高维稀疏表示',
        '全部训练与验证标签可用，测试标签不评估','明确的随机生成过程，无缺失与重复','含正弦与平方项，存在非线性','没有时间或空间邻接结构','小型两层MLP具有合理函数拟合能力',
        '可能改善线性拟合，是否超过树模型不预设','CPU可运行337参数级小网络，无CUDA','三模型各一次试验，上限600秒，MLP最多80轮'] ))
    report=dict(schema_version='1.0',question_id='q1',purpose='demo',status='complete',applicable=True,
        eligibility={'class':'B','reason':'合成回归存在非线性，样本有限，使用轻量神经网络试验检验竞争价值。','factors':factors},
        evidence={'求解/数据审计.md':sha(evidence)},budget=dict(device='CPU fallback',vram_mb=4096,seconds=600,max_trials=3,
            strategy='先基线，再随机森林及小型MLP，80轮内早停；无大范围搜索',exception_reason=''),
        metrics=[dict(name='rmse',label='RMSE',direction='min'),dict(name='mae',label='MAE',direction='min')],
        candidates=candidates,comparison_conditions='所有候选共享300条训练和100条验证样本，标准化仅拟合训练集，80条测试样本封存。',
        main_model=winner,improved_model=None,selection_reason='根据实际验证RMSE最低的候选选择主模型：'+winner+'。',
        tradeoffs='本演练仅固定单次种子，未证明多次训练稳定性；保留所有候选，MAE同时用于误差解释，暂不增加结构模块。')
    report_path='求解/问题一/结果/model_selection_report.json'
    write(root/report_path,report)
    from init_supporting_materials import make_question
    q=make_question('q1','问题一');q.update(status='complete',summary='合成回归三模型竞争与复现',
        entrypoint='求解/问题一/reproduce_demo.py',package_command='python reproduce_demo.py train',run_command='python reproduce_demo.py train')
    # A portable package recipe restores no template paths and retrains every candidate.
    portable='''from pathlib import Path
import json
import sys
from model_demo_train import train
from model_demo_validate import validate

for kind in ('ridge','rf','mlp'):
    folder=Path('outputs')/kind
    folder.mkdir(parents=True,exist_ok=True)
    cfg=dict(kind=kind,seed=42,data='data.json',split='split.json',checkpoint=str(folder/'checkpoint.pkl'),
             predictions=str(folder/'predictions.json'),training_record=str(folder/'training.json'),metrics=str(folder/'metrics.json'))
    cfg_path=folder/'config.json'
    if sys.argv[1]=='train':
        cfg_path.write_text(json.dumps(cfg),encoding='utf-8')
        train(cfg)
    else:
        validate(cfg_path)
if sys.argv[1]=='validate':
    scores={kind:json.loads((Path('outputs')/kind/'metrics.json').read_text())['metrics'] for kind in ('ridge','rf','mlp')}
    Path('reproduced.json').write_text(json.dumps(scores,sort_keys=True),encoding='utf-8')
'''
    (qroot/'reproduce_demo.py').write_text(portable,encoding='utf-8')
    import importlib.metadata
    versions={name:importlib.metadata.version(name) for name in ('torch','numpy','scikit-learn','jsonschema')}
    (qroot/'requirements.txt').write_text('\n'.join(k+'=='+v for k,v in versions.items())+'\n',encoding='utf-8')
    q['source_files']=[dict(path='求解/问题一/'+p,description='三模型训练、独立验证及复现依赖',package_path=p)
                       for p in ['model_demo_train.py','model_demo_validate.py','reproduce_demo.py','data.json','split.json','requirements.txt']]
    q['supplementary_materials']=[dict(path='求解/模型比较/q1.csv',material_type='table',description='全部候选模型统一口径结果',reason='完整保留DL与传统候选结果',package_path='模型比较.csv')]
    q['supplementary_materials_note']='仅保留完整比较表，无科学图；本次是模型协议的专项演练。'
    summary={c['id']:read(root/f"求解/问题一/结果/{c['id']}/metrics.json")['metrics'] for c in candidates}
    write(qroot/'结果/expected.json',summary)
    q['reproduction']=dict(commands=[dict(purpose=p,argv=['{python}','reproduce_demo.py',a]) for p,a in [('solve','train'),('validate','validate')]],
        outputs=[dict(path='reproduced.json',expected_path='求解/问题一/结果/expected.json',comparison='json',abs_tol=1e-6,rel_tol=1e-6)])
    q['run_verification'].update(status='pass',verified_at='2026-09-11',command='三次独立训练和独立验证，见实验运行收据')
    write(root/q['run_verification']['record_path'],{'status':'PASS','metrics':summary})
    (root/q['environment_doc']).write_text('环境：Python '+sys.version.split()[0]+'，CPU。\n依赖：requirements.txt\n安装：pip install -r requirements.txt\n输入：data.json与split.json是DEMO合成数据。\n运行：在本目录执行 python reproduce_demo.py train，然后 python reproduce_demo.py validate。\n输出：outputs目录及reproduced.json。训练所有候选，固定seed=42；浮点复现容差1e-6。',encoding='utf-8')
    (root/'求解/支撑材料说明.md').write_text('DEMO专项材料，不是赛题提交成果。\n问题一：合成回归三模型竞争与复现\n其他数据：无\n其他支撑材料：无\n复现：先安装依赖，再按问题一代码环境说明运行；数据是合成输入，结果在outputs。',encoding='utf-8')
    manifest=dict(schema_version='2.0',project_title='DEMO模型竞赛',package_status='complete',questions=[q],external_data=[],external_data_note='只有明确标记的合成数据，无外部数据',official_outputs=[],readme_source='求解/支撑材料说明.md',additional_files=[],category_descriptions={'其他数据':'无','其他支撑材料':'无'})
    write(root/'求解/支撑材料清单.json',manifest)
    publish(root)
    fragment=root/'论文/章节内容/q1.tex'
    fragment.write_text('\\section{问题一求解与分析}\n\\subsection{问题的描述与分析}\n本节只演练模型选择链路。\n\\subsection{候选比较}\n\\input{章节内容/q1_模型比较.generated.tex}\n',encoding='utf-8')
    # Minimal model-paper interface fixture, not a full valid paper manifest.
    paper={'chapters':[dict(chapter_id='q1',role='problem',tex_path='章节内容/q1.tex')]}
    write(root/'论文/demo_model_manifest.json',paper)
    write(root/'求解/环境.json',dict(python=sys.executable,versions=versions,device='cpu',cuda=False,purpose='demo'))
    return report_path,report,paper


def negative_tests(root, ref, original, paper):
    tests=[]
    def check(name, mutate, contains):
        changed=copy.deepcopy(original);mutate(changed);write(root/ref,changed)
        result=audit_report(root,ref)
        ok=result['status']=='FAIL' and any(contains in e for e in result['errors'])
        tests.append(dict(name=name,passed=ok,errors=result['errors']))
        write(root/ref,original)
    check('A类缺少DL不得完成',lambda r:(r['eligibility'].update({'class':'A'}),r.update(candidates=[c for c in r['candidates'] if c['family']!='dl'])), 'DL pilot')
    check('B类缺少DL不得完成',lambda r:r.update(candidates=[c for c in r['candidates'] if c['family']!='dl']), 'DL pilot')
    check('伪造冠军ID被拒绝',lambda r:r.update(main_model='never-trained'), 'main model')
    check('缺少门控证据被拒绝',lambda r:r['eligibility']['factors'].update(architecture=''), 'ValidationError')
    check('数据审计变化被拒绝',lambda r:r.update(evidence={'求解/数据审计.md':'0'*64}), 'stale report')
    check('显存放大无依据被拒绝',lambda r:r['budget'].update(vram_mb=24000), '4GB')
    bad=copy.deepcopy(paper);bad['chapters'][0]['tex_path']='章节内容/missing.tex'
    qtex=root/'论文/章节内容/q1.tex';s=qtex.read_text(encoding='utf-8')
    qtex.write_text('%\\input{章节内容/q1_模型比较.generated.tex}\n',encoding='utf-8')
    errors=paper_gate(root,paper);tests.append(dict(name='注释掉比较表被拒绝',passed=bool(errors),errors=errors));qtex.write_text(s,encoding='utf-8')
    csv=root/'求解/模型比较/q1.csv';raw=csv.read_bytes();csv.write_text('modified',encoding='utf-8')
    result=audit_report(root,ref,'paper');tests.append(dict(name='比较CSV手改被拒绝',passed=result['status']=='FAIL',errors=result['errors']));csv.write_bytes(raw)
    for name,split in [('样本重叠',dict(kind='iid',train=['a'],validation=['a'],test=[],preprocessing='train only')),
        ('分组泄漏',dict(kind='group',train=['a'],validation=['b'],test=[],groups={'a':'same','b':'same'},preprocessing='train only')),
        ('未来泄漏',dict(kind='time',train=['a'],validation=['b'],test=[],times={'a':2,'b':1},preprocessing='train only'))]:
        errors=contract_errors(split);tests.append(dict(name=name,passed=bool(errors),errors=errors))
    # Isolated malformed fixtures, never create fictitious training receipts in the real run inventory.
    for family in ('ml','dl'):
        r=copy.deepcopy(original);r['main_model']=next(c['id'] for c in r['candidates'] if c['family']==family)
        r['selection_reason']='审计分支夹具：验证主模型可来自该家族；不是本次科学优选结论。'
        r['selection_override_reason']='仅用于规则分支测试：代表有明确部署约束的人工选择理由，不作为此次真实DEMO的选模结论。'
        write(root/ref,r);a=audit_report(root,ref)
        tests.append(dict(name=family+'可升级主模型（规则夹具）',passed=a['status']=='PASS',errors=a['errors']))
    write(root/ref,original)
    # Mutate one candidate's declared split and its receipt coherently. The
    # common-split rule must reject it even when all hashes are refreshed.
    receipt_file=root/original['candidates'][0]['selected_run']
    receipt=read(receipt_file);cfg_file=root/receipt['config'];cfg=read(cfg_file)
    old_receipt=receipt_file.read_bytes();old_config=cfg_file.read_bytes()
    altered=root/'求解/问题一/split_negative.json'
    sp=read(root/cfg['split']);sp['reason']='negative fixture distinct partition';sp['validation']=list(reversed(sp['validation']))
    write(altered,sp);old_split=cfg['split'];cfg['split']=altered.relative_to(root).as_posix();write(cfg_file,cfg)
    receipt['inputs'].pop(old_split);receipt['inputs'][cfg['split']]=sha(altered);receipt['inputs'][receipt['config']]=sha(cfg_file);write(receipt_file,receipt)
    result=audit_report(root,ref)
    tests.append(dict(name='跨模型不同划分被拒绝',passed=any('unfair split' in e for e in result['errors']),errors=result['errors']))
    cfg_file.write_bytes(old_config);receipt_file.write_bytes(old_receipt);altered.unlink()
    # Separate C question has no invented model results.
    c=copy.deepcopy(original);c.update(question_id='qC',applicable=False,candidates=[],main_model=None,improved_model=None)
    c['eligibility'].update({'class':'C','reason':'纯解析优化题，没有训练目标、标签或需要学习的映射，因此不训练神经网络。'})
    cref='求解/问题一/结果/c_gate_fixture.json';write(root/cref,c)
    result=audit_report(root,cref);tests.append(dict(name='C类有理由免训练',passed=result['status']=='PASS',errors=result['errors']))
    c['eligibility']['reason']='';write(root/cref,c);result=audit_report(root,cref)
    tests.append(dict(name='C类无理由被拒绝',passed=result['status']=='FAIL',errors=result['errors']))
    (root/cref).unlink()
    # Actual failing process in a separate fault-injection question; not a CUDA
    # failure or a scientific result. Retain its real log and retry decision.
    fault=root/'求解/问题一/fault_injection.py'
    if not fault.exists():
        fault.write_text("raise RuntimeError('DEMO controlled failure; not real CUDA OOM')\n",encoding='utf-8')
    fr='求解/实验运行/qFailure/fault01/receipt.json'
    fcfg='求解/问题一/fault_config.json'
    if not (root/fr).exists():
        cfg=dict(run_id='fault01',question_id='qFailure',candidate_id='fault',
            split='求解/问题一/split.json',selection_partition='validation',inputs=['求解/问题一/data.json'],
            sources=['求解/问题一/fault_injection.py','求解/问题一/model_demo_validate.py'],
            commands=[dict(purpose='train',argv=['{python}','求解/问题一/fault_injection.py']),
                      dict(purpose='validate',argv=['{python}','求解/问题一/model_demo_validate.py','--config',fcfg])],
            outputs=['求解/问题一/结果/fault_metrics.json'],metrics='求解/问题一/结果/fault_metrics.json')
        write(root/fcfg,cfg); run_experiment(root,fcfg)
    f=copy.deepcopy(original);f.update(question_id='qFailure',applicable=True,main_model=None)
    f['candidates']=[dict(id='fault',name='故障注入',family='dl',rationale='测试失败留档的真实异常进程',decision='此为故障测试，无性能结论',complexity='仅注入异常测试',runs=[fr],selected_run=None,failures={})]
    fref='求解/问题一/结果/fault_fixture.json';write(root/fref,f)
    result=audit_report(root,fref)
    tests.append(dict(name='真实异常缺失败记录被拒绝',passed=any('failure cause' in e for e in result['errors']),errors=result['errors']))
    f['candidates'][0]['failures']={'fault01':dict(cause='主动异常注入，不是训练资源不足',retry='单独正常三模型训练已经完成，无需修复故障注入',decision='保留异常进程日志，仅作为门禁负例')}
    write(root/fref,f);result=audit_report(root,fref)
    tests.append(dict(name='失败原因重试决定可被审计识别',passed=not any('failure cause' in e for e in result['errors']) and read(root/fr)['status']=='FAIL',errors=result['errors']))
    # Keep fixture explicitly named, never include it in public or paper results.
    return tests


def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,default=Path('.'));p.add_argument('--tests-only',action='store_true');a=p.parse_args()
    root=a.project_root.resolve()
    from workspace_context import shared_context
    context=shared_context(root)
    if not context or context.manifest['purpose']!='demo':
        raise ValueError('Requires an explicitly registered DEMO workshop')
    if a.tests_only:
        ref='求解/问题一/结果/model_selection_report.json';r=read(root/ref);paper=read(root/'论文/demo_model_manifest.json')
        publish(root)
    else:
        ref,r,paper=setup(root,context)
    tests=negative_tests(root,ref,r,paper)
    checks={stage:audit_report(root,ref,stage) for stage in ('plan','question','paper')}
    checks['paper_interface']={'errors':paper_gate(root,paper)}
    checks['support_interface']={'errors':supporting_gate(root,read(root/'求解/支撑材料清单.json'),package=True)}
    result=dict(purpose='demo',status='PASS' if all(t['passed'] for t in tests) and not any(c['errors'] for c in checks.values()) else 'FAIL',
        tests=tests,checks=checks,main_model=r['main_model'],scope='模型竞赛专项验证；不授予整篇论文、图件或正式提交通过')
    write(root/'求解/验收输出/模型竞赛DEMO.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result['status']!='PASS'


if __name__=='__main__':
    sys.dont_write_bytecode=True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    raise SystemExit(main())
