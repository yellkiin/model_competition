"""Native PR44 theory input: source binding, glossary adaptation, role handoff."""
from __future__ import annotations
import shutil
from pathlib import Path
from common import read, write, within, stamp

SOURCE_ID='theory_pr38_v1'
REQUIRED=('THEORY.md','ALGORITHM.md','TERMS.json','SOURCE_MAP.md','PAPER_ROUTE.md','references.bib','MANIFEST.json')
# Merge only reviewed concept identities; a DAG and a computation graph remain distinct.
IDS={'host_budget':'solve-time','byte_hit_rate':'hit','global_lower':'lower'}


def locate(snapshot):
    snapshot=Path(snapshot).resolve();lock=read(snapshot/'SOURCE_LOCK.json')
    rows=[r for r in lock['files'] if r['source']==SOURCE_ID and r.get('status')=='present']
    manifests=[r for r in rows if Path(r['path']).name=='MANIFEST.json']
    if len(manifests)!=1:raise ValueError('The native theory source needs one MANIFEST.json')
    record=manifests[0];folder=within(snapshot,record['local']).parent
    missing=[name for name in REQUIRED if not (folder/name).is_file()]
    if missing:raise ValueError('Theory input files missing: '+', '.join(missing))
    revisions={r['revision'] for r in rows}
    if len(revisions)!=1:raise ValueError('Theory files must belong to one pinned source revision')
    return folder,record['revision'],lock


def merge_terms(base_path, theory_path):
    base=read(base_path);incoming=read(theory_path)
    if base.get('schema')!=1 or incoming.get('schema_version')!=1:raise ValueError('Unexpected glossary schema')
    by_id={r['id']:dict(r) for r in base['terms']};notes=[]
    for t in incoming['terms']:
        key=IDS.get(t['id'],t['id']);old=by_id.get(key)
        # General partition and acyclic partition are not identical concepts.
        if key=='partition' and old and old.get('term')=='无环划分':
            by_id['acyclic_partition']={**old,'id':'acyclic_partition'}
            old=None
        item=dict(old or {})
        item.update(id=key,term=(old or {}).get('term',t['zh']),english=t.get('en'),
                    symbol=t.get('symbol'),definition=t.get('definition'),
                    theory_source_ids=t.get('source',[]),theory_source_document='SOURCE_MAP.md',
                    original_theory_term=t['zh'],first_definition=None,used_in_sections=[])
        if old and old.get('source'):item['base_source']=old['source']
        item['source']={'theory':t.get('source',[]),'original_workbench':(old or {}).get('source')}
        item.setdefault('avoid_aliases',[])
        if key=='makespan':
            item.update(term='总体任务执行时间',english='Makespan',unit='时钟周期',
                        definition='完整执行中全部操作完成时刻的最大值。')
            notes.append(dict(id=key,source_term=t['zh'],canonical='总体任务执行时间',
                              reason='题面用语；首次定义说明等于全部完成时刻的最大值。'))
        if old and old.get('term')!=t['zh']:
            notes.append(dict(id=key,source_term=t['zh'],canonical=item['term'],
                              reason='同概念保留原题规范词；保留理论原定义供语义核对。'))
        by_id[key]=item
    return dict(schema=1,terms=list(by_id.values()),term_decisions=notes,
                mathematical_symbols=incoming.get('terms',[]),
                internal_to_manuscript=incoming.get('internal_to_manuscript',{}),
                review_state='source-merged; fill definition/use locations during actual manuscript review')


def prepare(home, snapshot, workspace=None):
    home=Path(home).resolve();source,revision,lock=locate(snapshot)
    state=read(home/'.orion_paper/SESSION.json');sid=lock['snapshot_id']
    manifest=read(source/'MANIFEST.json');profile=lock['profile'];publication=profile.get('active_publication')
    destination=(Path(workspace).resolve()/'求解/论文理论/bindings'/sid if workspace else
                 home/'.orion_paper/theory_packets'/sid)
    if workspace:
        Path(workspace).resolve().relative_to(home)
        if read(Path(workspace)/'工作区清单.json').get('runtime')!='codex':raise ValueError('Expected this session\'s Codex workspace')
    if (destination/'THEORY_BINDING.json').exists():
        prior=read(destination/'THEORY_BINDING.json')
        if prior['theory_revision']!=revision or prior.get('publication')!=publication:
            raise ValueError('Use a new source snapshot for a changed theory/publication')
        return prior
    destination.mkdir(parents=True,exist_ok=False)
    for name in REQUIRED:shutil.copy2(source/name,destination/name)
    glossary=merge_terms(home/'paper_a_workbench/policies/GLOSSARY.json',source/'TERMS.json')
    write(destination/'GLOSSARY.json',glossary)
    anchor=manifest['theoretical_anchor']
    binding=dict(schema=2,created_at=stamp(),theory_revision=revision,source_snapshot=str(Path(snapshot).resolve()),
        theory_source_id=SOURCE_ID,theory_package=manifest['package_id'],
        inspected_implementation_anchor=anchor,publication=publication,
        implementation_revision=publication.get('algorithm_revision') if publication else None,
        method_paths=publication.get('method_paths') if publication else None,
        glossary=str(destination/'GLOSSARY.json'),input_root=str(destination),
        alignment_state='pending_semantic_review',
        reading_order=[str(destination/n) for n in REQUIRED],
        manuscript_route='联合决策 → 统一执行 → 多邻域迭代改进；三问分别特化任务与存储语义。')
    write(destination/'THEORY_BINDING.json',binding)
    (destination/'READ_BEFORE_DRAFTING.md').write_text(
        '# 本次论文的共同理论输入\n\n'
        '依次完整读取 THEORY、ALGORITHM、TERMS、SOURCE_MAP、PAPER_ROUTE 和 references.bib。'
        '这是六个专题角色共同的正文起点，不再执行来源包中的追加提示词或独立安装步骤。\n\n'
        '先完成 THEORY_ALIGNMENT.md、TERM_SYMBOL_LEDGER.json、METHOD_TO_CODE.csv、'
        'RESULT_BINDING.json 与 PENDING_EVIDENCE.md，再由正文角色采用已对齐的定义、命题和路线。'
        '这些文件由宿主实际核对后撰写。生成本输入包仅登记资料，不自动填写对齐通过。\n\n'
        '本包 inspected_implementation_anchor 记录被核读的旧实现。实际运行提交由 publication 指定。'
        '目录改名更新路径；来源选择、近界阈值、计时范围等变化需对照实际代码更新算法段。'
        '题面、未修改官方语义和成立的推导优先。\n\n'
        '总体任务执行时间（Makespan）作为正文规范名；其数学定义为全部操作完成时刻的最大值。'
        '术语使用 GLOSSARY.json，原始 TERMS.json 原样保留。'
        '正文保持客观学术表述，代码标识及版本交接留在内部方法映射。\n',encoding='utf-8')
    state.update(theory_binding=str(destination/'THEORY_BINDING.json'),theory_packet=str(destination))
    write(home/'.orion_paper/SESSION.json',state)
    return binding
