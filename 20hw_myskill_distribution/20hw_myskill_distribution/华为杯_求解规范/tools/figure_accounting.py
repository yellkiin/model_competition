"""One count contract shared by plan/question/render/paper gates.

Count metadata is checked against actual plan ownership and overview mappings;
the caller must ALSO run scientific, asset, source, render and visual QA gates.
No caption count or manually chosen eligibility flag proves scientific value.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
from visual_routes import primary_output, routed_panels

PURPOSES = {'independent_science', 'question_overview', 'global_roadmap', 'global_science', 'panel', 'illustration'}
FLOW_EDGES = {'data', 'derivation', 'sequence', 'validation'}


def normalize(text):
    return re.sub(r'[\s，。；、,:;.!?！?]+', '', str(text)).casefold()


def inventory(plan: dict, diagrams: dict) -> list[dict]:
    rows = []
    for owner, figures in [(None, plan.get('global_figures', [])), *[
            (p['problem_id'], p.get('figures', []) + p.get('schematics', [])) for p in plan['problems']]]:
        for figure in figures:
            rows.append({'figure_id': figure.get('figure_id', figure.get('schematic_id')),
                         'problem_id': owner, 'body': True, 'flow': False,
                         'vector': primary_output(figure) or figure.get('output_pdf'),
                         'scientific_question': figure.get('scientific_question'),
                         'status': figure.get('status'), 'kind': 'scientific', 'record': figure})
    for d in diagrams.get('diagrams', []):
        has_flow = d.get('flow_semantics') is True and any(
            c.get('type') in FLOW_EDGES and c.get('from') != c.get('to') for c in d.get('connections', []))
        rows.append({'figure_id': d['diagram_id'], 'problem_id': d.get('problem_id'),
                     'body': d.get('placement') == 'body', 'flow': has_flow,
                     'vector': d.get('outputs', {}).get('vector'), 'status': d.get('status'),
                     'scientific_question': d.get('scientific_question'), 'kind': d.get('kind'), 'record': d})
    return rows


def audit_counts(plan: dict, diagrams: dict, stage: str, root: Path,
                 question_id: str | None = None) -> dict:
    checks, failures = [], []

    def check(code, ok, **details):
        row = {'code': code, 'ok': bool(ok), **details}
        checks.append(row)
        if not ok:
            failures.append(row)

    pids = [p['problem_id'] for p in plan['problems']]
    from chart_policy import required, audit_diversity
    from visual_routes import figures
    if required(plan, root):
        diversity = audit_diversity(figures(plan), root)
        check('body_chart_family_diversity', not diversity, errors=diversity)
    mapping = diagrams.get('questions', [])
    if question_id:
        selected = [q['problem_id'] for q in mapping if question_id in (q['problem_id'], q.get('supporting_question_id'))]
        check('accounting_question_selected', len(selected) == 1)
    else:
        selected = pids
    objects = inventory(plan, diagrams)
    ids = [r['figure_id'] for r in objects]
    check('accounting_object_ids_unique', all(ids) and len(ids) == len(set(ids)))
    declarations = diagrams.get('figure_accounting', [])
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).resolve().parents[1] / '图数口径.schema.json').read_text(encoding='utf-8'))
    schema_errors = [e.message for e in Draft202012Validator(schema).iter_errors(declarations)]
    check('accounting_schema', not schema_errors, errors=schema_errors)
    check('accounting_declared_for_every_object', isinstance(declarations, list) and
          all(isinstance(d, dict) for d in declarations) and
          sorted(str(d.get('figure_id')) for d in declarations) == sorted(str(i) for i in ids))
    declared = {d.get('figure_id'): d for d in declarations if isinstance(d, dict)}
    overview_ids = [q.get('overview_id') for q in mapping]
    check('accounting_overview_mapping_unique', len(set(overview_ids)) == len(pids) and len(overview_ids) == len(pids))
    result = []
    for obj in objects:
        fid, owner = obj['figure_id'], obj['problem_id']
        row = declared.get(fid, {})
        overview = fid in overview_ids
        illustration = obj['record'].get('count_role') == 'illustration'
        if routed_panels(obj['record']):
            check(f'{fid}:explicit_scientific_role', obj['record'].get('count_role') in {'independent_science', 'illustration'})
        per_question = obj['body'] and not overview and not illustration and owner in pids
        paper_total = obj['body'] and not overview and not illustration
        flow_total = obj['body'] and obj['flow']
        allowed = {'panel'} if not obj['body'] else {'illustration'} if illustration else {'question_overview'} if overview else (
            {'independent_science'} if owner in pids else {'global_science', 'global_roadmap'})
        check(f'{fid}:purpose_and_owner', row.get('purpose') in allowed and 'problem_id' in row and row['problem_id'] == owner)
        for key, derived in [('per_question', per_question), ('paper_total', paper_total), ('flow_total', flow_total)]:
            check(f'{fid}:{key}_derived', isinstance(row.get(key), bool) and row[key] == derived, expected=derived)
        contribution = row.get('scientific_contribution', '')
        check(f'{fid}:scientific_contribution_declared', isinstance(contribution, str) and len(contribution.strip()) >= 10
              and not any(s in contribution.lower() for s in ('待填写', 'pending', 'todo', '凑数')))
        if overview:
            q = next((q for q in mapping if q.get('overview_id') == fid), {})
            check(f'{fid}:mapped_overview_is_comprehensive', obj['kind'] == 'comprehensive' and obj['body'] and q.get('problem_id') == owner)
        if row.get('purpose') == 'global_roadmap':
            check(f'{fid}:roadmap_is_global_flow', owner is None and obj['kind'] == 'flowchart' and flow_total)
        # At a per-question gate other questions may still be planned. Report
        # their planned counts without presenting them as completed QA evidence.
        must_be_rendered = stage != 'plan' and (not question_id or owner in selected)
        if must_be_rendered:
            check(f'{fid}:counted_output_qa_pass', obj['status'] == 'qa_pass')
        result.append({k: v for k, v in obj.items() if k != 'record'} | {
            'purpose': row.get('purpose'), 'scientific_contribution': contribution,
            'per_question': per_question, 'paper_total': paper_total, 'flow_total': flow_total,
            'assurance_stage': stage if must_be_rendered else 'plan'})

    summary = []
    for pid in pids:
        scientific = [r['figure_id'] for r in result if r['problem_id'] == pid and r['per_question']]
        overviews = [r['figure_id'] for r in result if r['problem_id'] == pid and r['purpose'] == 'question_overview']
        summary.append({'problem_id': pid, 'independent_science_count': len(scientific),
                        'independent_science_ids': scientific, 'overview_count': len(overviews), 'overview_ids': overviews})
        check(f'{pid}:independent_science_4_to_6', 4 <= len(scientific) <= 6, count=len(scientific))
        check(f'{pid}:one_extra_overview', len(overviews) == 1, ids=overviews)
    total = sum(r['paper_total'] for r in result)
    flows = sum(r['flow_total'] for r in result)
    check('paper_16_excluding_question_overviews', total >= 16, count=total)
    check('two_figures_with_real_flow_semantics', flows >= 2, count=flows)
    check('one_global_roadmap', sum(r['purpose'] == 'global_roadmap' for r in result) == 1)
    # Identical scientific-contribution claims and identical final vector bytes
    # cannot become independent evidence by changing the caption or figure ID.
    independent = [r for r in result if r['paper_total']]
    contributions = [normalize(r['scientific_contribution']) for r in independent]
    check('independent_contributions_not_repeated', len(contributions) == len(set(contributions)))
    digests = {}
    duplicates = []
    if stage != 'plan':
        for r in independent:
            if question_id and r['problem_id'] not in selected:
                continue
            raw = r.get('vector')
            if not isinstance(raw, str) or not raw:
                check(r['figure_id'] + ':counted_vector_exists', False)
                continue
            path = (root / raw).resolve()
            try:
                path.relative_to(root.resolve())
                valid = path.is_file() and path.stat().st_size > 0
            except ValueError:
                valid = False
            check(r['figure_id'] + ':counted_vector_exists', valid)
            if valid:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest in digests:
                    duplicates.append([digests[digest], r['figure_id']])
                digests[digest] = r['figure_id']
        check('independent_vectors_not_duplicates', not duplicates, duplicates=duplicates)
    return {'status': 'FAIL' if failures else 'PASS', 'checks': checks, 'failures': failures,
            'figures': result, 'questions': summary, 'paper_eligible_count': total, 'flow_count': flows,
            'assurance': '额度与版本检查；不替代独立科学信息、真实来源、实际看图及入文位置门禁。'}
