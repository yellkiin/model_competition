#!/usr/bin/env python3
"""Publish the derived figure ledger without approving scientific or visual QA."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import hashlib
import json
from pathlib import Path

from figure_accounting import audit_counts, inventory

START = '<!-- GMCM-FIGURE-ACCOUNTING:BEGIN -->'
END = '<!-- GMCM-FIGURE-ACCOUNTING:END -->'
LIST = '论文/图表清单.json'
INDEX = '求解/结果索引.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def path(root, raw):
    result=(root/raw).resolve()
    result.relative_to(root.resolve())
    return result


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def base_snapshot(root, plan, diagrams, accounting):
    by_id={r['figure_id']:r for r in inventory(plan,diagrams)}
    figures=[]
    for row in accounting['figures']:
        raw=by_id[row['figure_id']]
        vector=path(root,row['vector']) if row.get('vector') else None
        paper=raw['record'].get('paper',{})
        figures.append({key:row.get(key) for key in (
            'figure_id','problem_id','purpose','scientific_contribution','per_question','paper_total',
            'flow_total','status','body','vector')} | {
            'vector_sha256':sha(vector) if vector is not None and vector.is_file() else None,
            'label':paper.get('label'), 'caption':paper.get('caption')})
    return dict(schema_version='1.0', plan_content_sha256=canonical_hash(plan),
        diagrams_content_sha256=canonical_hash(diagrams), figures=figures,
        questions=accounting['questions'],paper_eligible_count=accounting['paper_eligible_count'],
        flow_count=accounting['flow_count'],
        assurance='额度来自计划和归属；不证明科学价值、来源、实际看图或正文验收通过。')


def paper_snapshot(root, plan_path, plan, diagrams, runtime):
    from collect_academic_paper_review import verify_evidence
    review_path=path(root,diagrams.get('paper_review_path',''))
    review=read(review_path)
    assets_path=plan_path.with_suffix('.assets.json')
    assets={f['figure_id']:f for f in read(assets_path).get('figures',[])} if assets_path.is_file() else {}
    from visual_routes import media_sidecar
    media_path = media_sidecar(plan_path)
    media = {f['figure_id']: f for f in read(media_path).get('figures', [])} if media_path.is_file() else {}
    from modelviz_bridge import sidecar as modelviz_sidecar
    modelviz_path=modelviz_sidecar(plan_path)
    modelviz={f['figure_id']: f for f in read(modelviz_path).get('figures', [])} if modelviz_path.is_file() else {}
    objects=[r for r in inventory(plan,diagrams) if r['body']]
    specs=[]
    for obj in objects:
        width=assets.get(obj['figure_id'],modelviz.get(obj['figure_id'],media.get(obj['figure_id'],{}))).get('target_width_mm',obj['record'].get('target_width_mm'))
        if not isinstance(width,(int,float)) or width<=0:
            raise ValueError('Missing planned paper width: '+obj['figure_id'])
        specs.append(dict(figure_id=obj['figure_id'],vector_path=obj['vector'],target_width_mm=width))
    failures=verify_evidence(root,review,path(root,review['main_tex']),runtime,specs,require_visual=False)
    if failures:
        raise ValueError('Paper measurements are stale or invalid: '+json.dumps(failures,ensure_ascii=False))
    return dict(review_path=review_path.relative_to(root).as_posix(),review_sha256=sha(review_path),
        pdf_path=review['pdf_path'],pdf_sha256=review['pdf_sha256'],
        occurrences={f['figure_id']:[{k:x[k] for k in ('page_number','pdf_bbox','probe_id')}
                     for x in f['occurrences']] for f in review['figures']})


def markdown(snapshot):
    def cell(value):
        if value is None:return '—'
        if isinstance(value,bool):return '是' if value else '否'
        return str(value).replace('|',r'\|').replace('\r',' ').replace('\n',' ')
    lines=[START,'','### 图数账表（自动生成）','',snapshot['assurance'],'',
        '| 图ID | 所属问题 | 用途 | 逐问额度 | 全文额度 | 流程额度 | 计划状态 | 图题 | 科学贡献 | 实际PDF页码 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    occurrences=(snapshot.get('paper') or {}).get('occurrences',{})
    for f in snapshot['figures']:
        pages=','.join(str(x['page_number']) for x in occurrences.get(f['figure_id'],[])) or '未采集'
        values=[f[k] for k in ('figure_id','problem_id','purpose','per_question','paper_total','flow_total','status','caption','scientific_contribution')]+[pages]
        lines.append('| '+' | '.join(cell(v) for v in values)+' |')
    lines += ['',f"排除逐问主要综合图后的全文计划额度：{snapshot['paper_eligible_count']}；具有流程语义的图：{snapshot['flow_count']}。",'',END]
    return '\n'.join(lines)


def block(text):
    lines=text.splitlines()
    starts=[i for i,line in enumerate(lines) if line==START]
    ends=[i for i,line in enumerate(lines) if line==END]
    if not starts and not ends:return None
    if len(starts)!=1 or len(ends)!=1 or starts[0]>=ends[0]:
        raise ValueError('Result index has ambiguous or broken accounting markers')
    return '\n'.join(lines[starts[0]:ends[0]+1])


def build(root, plan_path, stage, runtime, question_id=None):
    root=root.resolve();plan_path=path(root,str(plan_path))
    plan,diagrams=read(plan_path),read(plan_path.with_suffix('.diagrams.json'))
    if diagrams.get('runtime')!=runtime:
        raise ValueError('Runtime differs from diagram plan')
    accounting=audit_counts(plan,diagrams,stage,root,question_id)
    if accounting['status']!='PASS':
        raise ValueError('Quota contract failed: '+json.dumps(accounting['failures'],ensure_ascii=False))
    snapshot=base_snapshot(root,plan,diagrams,accounting)
    snapshot['paper']=paper_snapshot(root,plan_path,plan,diagrams,runtime) if stage=='paper' else None
    index=root/INDEX
    text=index.read_text(encoding='utf-8-sig') if index.is_file() else '# 结果索引\n'
    previous=block(text)
    fresh=markdown(snapshot)
    if previous is None:
        text=text.rstrip()+'\n\n'+fresh+'\n'
    else:
        # Normalize line endings, preserving all user-maintained content.
        text=text.replace('\r\n','\n').replace(previous,fresh,1)
    listing=root/LIST
    index.parent.mkdir(parents=True,exist_ok=True)
    listing.parent.mkdir(parents=True,exist_ok=True)
    listing.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    index.write_text(text,encoding='utf-8')
    return dict(status='GENERATED_NOT_QA',figure_list=LIST,result_index=INDEX,
        figure_count=len(snapshot['figures']),paper_eligible_count=snapshot['paper_eligible_count'])


def audit_publications(root, plan_path, plan, diagrams, accounting, stage, runtime):
    errors=[]
    try:
        root=root.resolve();plan_path=path(root,str(plan_path))
        current=read(root/LIST)
        expected=base_snapshot(root,plan,diagrams,accounting)
        if {k:v for k,v in current.items() if k!='paper'}!=expected:
            errors.append('Figure list differs from current plan, ownership, outputs or counts')
        if stage=='paper' or current.get('paper') is not None:
            if current.get('paper')!=paper_snapshot(root,plan_path,plan,diagrams,runtime):
                errors.append('Figure list does not contain current actual PDF occurrences')
        if block((root/INDEX).read_text(encoding='utf-8-sig'))!=markdown(current):
            errors.append('Result-index accounting block is missing or differs from figure list')
    except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
        errors.append(str(exc))
    return dict(status='FAIL' if errors else 'PASS',errors=errors,
        figure_list=LIST,result_index=INDEX,assurance='同步额度与实际页码；科学与视觉门禁仍由各自审计执行。')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,default=Path('.'))
    p.add_argument('--plan',type=Path,default=Path('求解/视觉计划.json'))
    p.add_argument('--stage',choices=['plan','question','render','tex','paper'],required=True)
    p.add_argument('--question-id')
    p.add_argument('--runtime',choices=['codex','claude'],required=True)
    a=p.parse_args()
    if (a.stage=='question') != bool(a.question_id):
        p.error('--question-id is required only for --stage question')
    print(json.dumps(build(a.project_root,a.plan,a.stage,a.runtime,a.question_id),ensure_ascii=False))


if __name__=='__main__':main()
