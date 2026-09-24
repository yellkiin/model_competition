"""Bind abstract emphasis and statements to current structured results and body.

Hash/value equality proves traceability, not the truth of an experiment. The
solver's independent-validation gates and actual scientific review still apply.
"""
from __future__ import annotations
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from paper_contract import commands, expand_fragment, chinese_number


def pointer(data, raw):
    if raw == '':
        return data
    if not isinstance(raw, str) or not raw.startswith('/'):
        raise ValueError('source_pointer 必须为 RFC6901 JSON Pointer')
    for token in raw[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        data = data[int(token)] if isinstance(data, list) else data[token]
    return data


def evidence_gate(manifest, paper_root, raw, paragraphs, simplify):
    """No inferred PASS records and no reading numbers back from a plotted image."""
    failures, records = [], []
    def check(code, ok, **extra):
        row = {'code': code, 'ok': bool(ok), **extra}
        records.append(row)
        if not ok:
            failures.append(row)
    norm = lambda text: re.sub(r'\s+', '', simplify(text))
    try:
        evidence_path = (paper_root / manifest['abstract_evidence_path']).resolve()
        evidence_path.relative_to(paper_root)
        evidence = json.loads(evidence_path.read_text(encoding='utf-8-sig'))
        schema = json.loads((Path(__file__).resolve().parents[1] / '摘要证据.schema.json').read_text(encoding='utf-8'))
        from jsonschema import Draft202012Validator
        errors = [e.message for e in Draft202012Validator(schema).iter_errors(evidence)]
        check('abstract_evidence_schema', not errors, errors=errors)
        if errors:
            return {'checks': records, 'failures': failures}
        chapters = [c for c in manifest['chapters'] if c['role'] == 'problem']
        check('abstract_evidence_question_mapping', [q['chapter_id'] for q in evidence['questions']] ==
              [c['chapter_id'] for c in chapters])
        parts = [p.strip() for p in re.split(r'\n\s*\n+', raw) if p.strip()]
        all_bold = [norm(c.argument) for c in commands(raw, ('textbf',))]
        raw_by_question = {}
        for i in range(1, len(chapters)+1):
            marker = '针对问题'+chinese_number(i)
            matches = [p for p in parts if norm(p).startswith(marker+'，') or norm(p).startswith(marker+',')]
            if len(matches) == 1:
                raw_by_question[i] = matches[0]
        bound_values = []
        key_values = set()
        for i, (chapter, question) in enumerate(zip(chapters, evidence['questions']), 1):
            tag = f'problem_{i}'
            body = norm(expand_fragment(paper_root, paper_root / chapter['tex_path']))
            paragraph = raw_by_question.get(i, '')
            bold = [norm(c.argument) for c in commands(paragraph, ('textbf',))]
            check(tag+'_lead_is_bold', '针对问题'+chinese_number(i) in bold)
            kinds = [r['kind'] for r in question['statements']]
            has_numeric_result = False
            for kind in ('method', 'conclusion', 'validation'):
                check(tag+'_has_'+kind+'_evidence', kind in kinds)
            if chapter.get('abstract_result_mode', 'quantitative') == 'quantitative':
                check(tag+'_has_numeric_result_evidence', any(r['kind']=='value' and r.get('key', True)
                      for r in question['statements']))
            for j, item in enumerate(question['statements']):
                code = f'{tag}_statement_{j+1}'
                source = (paper_root.parent / item['source_path']).resolve()
                source.relative_to(paper_root.parent.resolve())
                check(code+'_source_current', source.suffix.lower()=='.json' and
                      hashlib.sha256(source.read_bytes()).hexdigest()==item['source_sha256'])
                value = pointer(json.loads(source.read_text(encoding='utf-8-sig')), item['source_pointer'])
                text = norm(item['text'])
                if item['kind'] == 'value':
                    if not isinstance(value, dict) or value.get('status') not in ('verified', 'prediction', 'setting'):
                        raise ValueError(code+': 数值源须含value/unit/status')
                    places = item.get('decimal_places', 2)
                    number = Decimal(str(value['value'])).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
                    if not number.is_finite():
                        raise ValueError(code+': 数值必须有限')
                    expected = format(number, f'.{places}f')+str(value['unit'])
                    check(code+'_value_and_unit_match', text == re.sub(r'\s+', '', expected), expected=expected, actual=text)
                    check(code+'_result_emphasized', value['status']=='setting' or item.get('key', True))
                    bound_values.append(text)
                    has_numeric_result |= value['status'] in ('verified', 'prediction')
                    if item.get('key', True):
                        key_values.add(text)
                elif item['kind'] == 'conclusion':
                    if not isinstance(value, dict) or value.get('status') not in ('verified', 'prediction', 'analytic'):
                        raise ValueError(code+': 结论源须含text/status')
                    check(code+'_conclusion_matches', text == norm(value['text']))
                    if chapter.get('abstract_result_mode') == 'analytic':
                        check(code+'_analytic_result_type', value['status']=='analytic')
                else:
                    check(code+'_source_text_matches', isinstance(value, str) and text == norm(value))
                check(code+'_in_corresponding_paragraph', text in norm(paragraph))
                check(code+'_in_corresponding_body', text in body)
                if item['kind'] in ('method', 'conclusion') or (item['kind']=='value' and item.get('key', True)):
                    check(code+'_short_span_bold', text in bold)
                if isinstance(value, dict) and value.get('status') == 'prediction':
                    sentences = [s for s in re.split(r'[。！？]', norm(paragraph)) if text in s]
                    check(code+'_prediction_not_ground_truth', bool(sentences) and all(
                        '预测' in s and not re.search(r'真实类别|已经证实|已证实|确诊|准确率|正确率', s) for s in sentences))
            if chapter.get('abstract_result_mode', 'quantitative') == 'quantitative':
                check(tag+'_numeric_evidence_is_result_not_setting', has_numeric_result)
        # Every emphasized number, including the opening and innovation, must
        # reuse an actual bound value, rather than acquire authority by bolding.
        for phrase in all_bold:
            if re.match(r'^[+-]?\d', phrase):
                check('bold_numeric_value_traceable:'+phrase, phrase in bound_values)
        from audit_abstract import numeric_tokens, UNIT_RE
        compact = norm(raw)
        spans = [(len(norm(raw[:c.start])), len(norm(raw[:c.start]))+len(norm(c.argument)))
                 for c in commands(raw, ('textbf',))]
        for match in numeric_tokens(compact):
            unit = UNIT_RE.match(compact[match.end():])
            if unit:
                end = match.end()+unit.end()
                literal = compact[match.start():end]
                check('numeric_statement_traceable:'+literal, literal in bound_values)
                if literal in key_values:
                    check('key_value_occurrence_bold:'+literal,
                          any(a <= match.start() and end <= b for a, b in spans))
    except (OSError, ValueError, KeyError, TypeError, IndexError, ArithmeticError, ImportError) as exc:
        check('abstract_evidence_readable', False, error=str(exc))
    return {'checks': records, 'failures': failures,
            'assurance': '核对当前源、JSON字段、数值单位与正文文字；不替代真实求解和独立科学验证。'}
