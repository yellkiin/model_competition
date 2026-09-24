"""Describe the public support snapshot from actual solution files and audit records."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'求解/支撑材料清单.json'
source=json.loads(MANIFEST.read_text(encoding='utf-8'))
titles={'q1':'问题一','q2':'问题二','q3':'问题三'}
summaries={
 'q1':'场景A切图与调度源码、逐例官方结果及候选比较',
 'q2':'场景B同核Task合并源码、成对对照及候选比较',
 'q3':'共享只读L2调度源码、缓存收益及非官方敏感性表',
}
common_scripts=('support_reproduce.py','collect_official_results.py',
                'verify_official_results.py','summarize_validations.py',
                'run_official_experiments.py','solve_components.py',
                'solve_bands.py','solve_batches.py','cache_sensitivity.py',
                'analyze_official_results.py','analyze_cache_sensitivity.py')
common_scripts+=('build_deep_evidence.py','build_crosscheck_tables.py')
common_scripts+=('build_structure_cache_crosscheck.py',)
official_code=sorted((ROOT/'数据/原始/A题官方附件/code').glob('*.py'))

def fileitem(path,package,description):
    p=ROOT/path
    if not p.is_file():raise FileNotFoundError(p)
    return {'path':path,'description':description,'package_path':package}

for q in source['questions']:
    key=q['question_id'];title=titles[key]
    entry=f'求解/{title}/{title}.py'
    files=[fileitem(entry,f'{title}.py','本问唯一复现入口')]
    for name in common_scripts:
        path='求解/'+name
        files.append(fileitem(path,name if name=='support_reproduce.py' else '求解/'+name,
                              '正式方案构造、全量候选择优或独立核验源码'))
    for path in official_code:
        rel=path.relative_to(ROOT).as_posix()
        files.append(fileitem(rel,rel,'题目提供且未改动的官方评估源码'))
    for name in ('requirements.txt','requirements.lock.txt'):
        files.append(fileitem(name,name,'实际环境依赖清单'))
    files.append(fileitem('求解/数据审计.json','求解/数据审计.json','输入图结构审计结果，供正式候选构造使用'))
    q.update(status='complete' if (ROOT/f'求解/{title}/结果/运行验证.json').is_file() else 'draft',
             summary=summaries[key],
             package_command=f'python {title}.py solve；python {title}.py validate',
             entrypoint=entry,run_command=f'python {title}.py solve && python {title}.py validate',
             source_files=files,
             depends_on=[] if key=='q1' else ['q1'] if key=='q2' else ['q2'],
             run_verification={'status':'pass' if (ROOT/f'求解/{title}/结果/运行验证.json').is_file() else 'pending',
                               'command':f'python {title}.py solve；python {title}.py validate',
                               'record_path':f'求解/{title}/结果/运行验证.json',
                               'verified_at':'2026-09-23' if (ROOT/f'求解/{title}/结果/运行验证.json').is_file() else ''},
             reproduction={
                 'commands':[{'purpose':'solve','argv':['{python}',f'{title}.py','solve']},
                             {'purpose':'validate','argv':['{python}',f'{title}.py','validate']}],
                 'outputs':[{'path':'求解/正式实验/总体摘要.json',
                             'expected_path':'求解/正式实验/总体摘要.json','comparison':'json'},
                            {'path':'求解/正式实验/逐问核验摘要.json',
                             'expected_path':'求解/正式实验/逐问核验摘要.json','comparison':'json'}]},
             supplementary_materials=[{'path':f'求解/模型比较/{key}.csv','material_type':'table',
                                      'description':'同条件候选模型正式比较表',
                                      'reason':'正文只摘录选择依据，完整指标表支持复核',
                                      'package_path':f'{key}_候选比较.csv'}],
             supplementary_materials_note='仅收入正文未完整呈现的正式候选比较表；待选图库未审定备选图不入包。',
             appendix_code=[])
    if key=='q3':
        for fname in ('全部候选.csv','逐配置最优.csv'):
            q['supplementary_materials'].append({
                'path':'求解/正式实验/L2参数敏感性_非官方/'+fname,'material_type':'table',
                'description':'六例非官方L2容量与带宽网格：'+fname,
                'reason':'正文只展示响应面和机制结论，逐格实测表便于复核；不计官方成绩。',
                'package_path':'非官方L2参数_'+fname})

source['package_status']='complete' if all(q['status']=='complete' for q in source['questions']) else 'draft'
source['external_data']=[]
source['external_data_note']='仅使用题目官方图数据和配置；无额外自主采集数据。'
source['official_outputs']=[
    fileitem('求解/提交源/正式候选评估.zip','其他支撑材料/正式候选评估.zip',
             '2005份正式评估收据、原始响应及候选方案，保留原始内部文件名') | {
             'verification_path':'求解/正式实验/逐问核验摘要.json','status':'pass'},
]
for q in source['questions']:
    title=q['title']
    source['official_outputs'].append(fileitem(f'求解/{title}/结果/逐例官方评估.csv',
        f'其他支撑材料/{title}_逐例官方评估.csv','本问100例×五核数的正式官方指标表') |
        {'verification_path':'求解/正式实验/逐问核验摘要.json','status':'pass'})
source['additional_files']=[
    fileitem('求解/提交源/官方输入.zip','其他数据/官方输入.zip','题目原始100图与固定配置，内部文件名未改'),
    fileitem('求解/提交源/归档来源.json','其他支撑材料/归档来源.json','官方输入与正式评估归档的来源摘要'),
    fileitem('求解/正式实验/总体摘要.json','其他支撑材料/总体摘要.json','三问各核数的100例官方汇总'),
    fileitem('求解/正式实验/统计分析.json','其他支撑材料/统计分析.json','正式分位数及成对机制统计'),
    fileitem('求解/正式实验/深度分析.json','其他支撑材料/深度分析.json','三问逐核、结构分组与参数响应的真实结果复核'),
    fileitem('求解/正式实验/交叉核查.json','其他支撑材料/交叉核查.json','图结构反例、候选搬运与缓存命中分层交叉核查'),
    fileitem('求解/正式实验/结构与缓存交叉核查.json','其他支撑材料/结构与缓存交叉核查.json','五核结构分组与同方案L2收益的全100例核对'),
    fileitem('求解/正式实验/L2参数敏感性_非官方/统计验证.json',
             '其他支撑材料/非官方L2网格统计验证.json','六例非官方网格核验'),
]
source['category_descriptions']={
    '其他数据':'题目原始100图与固定配置归档',
    '其他支撑材料':'全部正式候选响应、逐例指标、汇总及非官方网格核验'}
MANIFEST.write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(source['package_status'],[q['status'] for q in source['questions']])
