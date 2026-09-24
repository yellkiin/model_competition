"""Model competition evidence, executed experiments and generated paper tables.

Receipts prove file/command consistency, not scientific validity or honesty.
Use the project-specific independent validator for the task's actual metrics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

FACTORS = ('task_type', 'modality', 'sample_size', 'feature_dimension', 'labels',
           'quality', 'nonlinearity', 'structure', 'architecture', 'advantage',
           'resources', 'time_budget')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def path(root, raw):
    from workspace_context import bounded
    if not isinstance(raw, str) or not raw.strip() or Path(raw).is_absolute() or ':' in raw:
        raise ValueError('Evidence path must be a workspace-relative path: ' + str(raw))
    return bounded(root, raw)


def snapshot(root, paths):
    return {p: sha(path(root, p)) for p in paths}


def meaningful(value):
    return isinstance(value, str) and len(value.strip()) >= 4 and not any(
        v in value for v in ('待填写', '待补充', 'TODO'))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def contract_errors(split):
    """Check IDs plus group/time boundaries; interpretation still needs review."""
    errors = []
    portions = [split.get(k, []) for k in ('train', 'validation', 'test')]
    if any(not isinstance(p, list) for p in portions):
        return ['split partitions must be lists']
    if any(not p for p in portions[:2]):
        errors.append('train and validation must be nonempty')
    if any(any(not isinstance(i, str) for i in p) for p in portions):
        return errors + ['sample IDs must be strings']
    if any(len(p) != len(set(p)) for p in portions):
        errors.append('duplicate sample IDs')
    if any(set(portions[i]) & set(portions[j]) for i in range(3) for j in range(i)):
        errors.append('train/validation/test overlap')
    kind = split.get('kind')
    if kind not in ('iid', 'stratified', 'group', 'time', 'spatial', 'custom'):
        errors.append('unknown split kind')
    if kind in ('group', 'spatial'):
        groups = split.get('groups', {})
        if any(i not in groups for p in portions for i in p):
            errors.append('missing group/block IDs')
        else:
            sets = [{groups[i] for i in p} for p in portions]
            if any(sets[i] & sets[j] for i in range(3) for j in range(i)):
                errors.append('group/spatial leakage')
    if kind == 'time':
        times = split.get('times', {})
        if any(not finite(times.get(i)) for p in portions for i in p):
            errors.append('missing numeric timestamps')
        else:
            active = [p for p in portions if p]
            if any(max(times[i] for i in a) >= min(times[i] for i in b)
                   for a, b in zip(active, active[1:])):
                errors.append('future information crosses time split')
    if not meaningful(split.get('preprocessing')):
        errors.append('training-only preprocessing policy required')
    if kind == 'custom' and not meaningful(split.get('reason')):
        errors.append('custom split requires rationale')
    return errors


def run_experiment(root, config_path, timeout=600):
    """Run train then independent validate. Failed receipts are never overwritten."""
    root = Path(root).resolve()
    config = read(path(root, config_path))
    rid, qid = config['run_id'], config['question_id']
    if not all(re.fullmatch(r'[A-Za-z0-9_-]+', x) for x in (rid, qid)):
        raise ValueError('Invalid run/question ID')
    folder = path(root, f'求解/实验运行/{qid}/{rid}')
    if folder.exists():
        raise ValueError('Run already exists; use a new run_id, retain failures')
    inputs = list(dict.fromkeys([config_path, config['split'], *config['inputs'], *config['sources']]))
    before = snapshot(root, inputs)
    split = read(path(root, config['split']))
    errors = contract_errors(split)
    if errors:
        raise ValueError('; '.join(errors))
    commands = config['commands']
    if [c['purpose'] for c in commands] != ['train', 'validate']:
        raise ValueError('Exactly train then independent validate commands required')
    if commands[0]['argv'][1] == commands[1]['argv'][1]:
        raise ValueError('Independent validator must use a separate source file')
    for c in commands:
        if len(c['argv']) < 2 or c['argv'][0] != '{python}' or c['argv'][1] not in config['sources']:
            raise ValueError('Command must use {python} and a registered source')
    outputs = config['outputs']
    if config['metrics'] not in outputs or not outputs:
        raise ValueError('Metrics must be a registered output')
    for p in outputs:
        if path(root, p).exists():
            raise ValueError('Output already exists; stale output cannot be a new run: ' + p)
    folder.mkdir(parents=True)
    receipt = dict(schema_version='1.0', question_id=qid, run_id=rid, config=config_path,
                   status='RUNNING', started_at=datetime.now(timezone.utc).isoformat(),
                   inputs=before, outputs={}, processes=[])
    write(folder / 'receipt.json', receipt)
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    for c in commands:
        argv = [sys.executable if v == '{python}' else v for v in c['argv']]
        started = time.perf_counter()
        try:
            proc = subprocess.run(argv, cwd=root, env=env, capture_output=True,
                                  text=True, encoding='utf-8', errors='replace', timeout=timeout)
            code, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            code, out, err = 124, str(exc.stdout or ''), str(exc.stderr or '') + '\nTIMEOUT'
        except OSError as exc:
            code, out, err = 127, '', str(exc)
        log = folder / (c['purpose'] + '.log')
        log.write_text(out + '\n' + err, encoding='utf-8')
        receipt['processes'].append(dict(purpose=c['purpose'], argv=argv, returncode=code,
            elapsed_seconds=time.perf_counter()-started, log=log.relative_to(root).as_posix(), sha256=sha(log)))
        if code:
            break
    receipt['outputs'] = snapshot(root, [p for p in outputs if path(root, p).is_file()])
    receipt['status'] = 'PASS' if (len(receipt['processes']) == 2 and
        all(p['returncode'] == 0 for p in receipt['processes']) and
        set(receipt['outputs']) == set(outputs) and snapshot(root, inputs) == before) else 'FAIL'
    receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
    write(folder / 'receipt.json', receipt)
    return receipt


def audit_report(root, report_path, stage='question'):
    root = Path(root).resolve()
    errors = []
    try:
        report = read(path(root, report_path))
        import jsonschema
        jsonschema.Draft202012Validator(read(Path(__file__).parents[1] / '模型选择报告.schema.json')).validate(report)
        qid = report['question_id']
        gate = report['eligibility']
        if not all(meaningful(gate['factors'].get(f)) for f in FACTORS):
            errors.append('eligibility factors incomplete')
        if not meaningful(gate['reason']):
            errors.append('eligibility reason missing')
        for name, digest in report['evidence'].items():
            if sha(path(root, name)) != digest:
                errors.append('stale report evidence: ' + name)
        if not report['evidence']:
            errors.append('task/data audit evidence missing')
        if stage == 'plan':
            return dict(status='FAIL' if errors else 'PASS', errors=errors)
        if report['status'] != 'complete':
            errors.append('model selection not complete')
        candidates = report['candidates']
        ids = [c['id'] for c in candidates]
        if len(ids) != len(set(ids)):
            errors.append('duplicate candidate IDs')
        all_receipts, successful, rows = set(), {}, []
        split_hash = None
        data_hashes = None
        elapsed_total = 0
        trial_count = 0
        expected_metric_names = [m['name'] for m in report['metrics']]
        if len(expected_metric_names) != len(set(expected_metric_names)):
            errors.append('duplicate metrics')
        for c in candidates:
            if not meaningful(c['rationale']) or not meaningful(c['decision']):
                errors.append('candidate rationale/decision missing: ' + c['id'])
            for receipt_path in c['runs']:
                if receipt_path in all_receipts:
                    errors.append('receipt reused by candidates')
                all_receipts.add(receipt_path)
                r = read(path(root, receipt_path))
                cfg = read(path(root, r['config']))
                trial_count += 1
                elapsed_total += sum(p.get('elapsed_seconds', 0) for p in r['processes'])
                actual_data = snapshot(root, cfg['inputs'])
                if data_hashes is not None and actual_data != data_hashes:
                    errors.append('unfair input data across competing runs')
                data_hashes = actual_data
                if r['question_id'] != qid or cfg['question_id'] != qid or cfg['candidate_id'] != c['id']:
                    errors.append('run ownership mismatch')
                if r['run_id'] != cfg['run_id']:
                    errors.append('run identity mismatch')
                expected_inputs = {r['config'], cfg['split'], *cfg['inputs'], *cfg['sources']}
                if set(r['inputs']) != expected_inputs:
                    errors.append('run input inventory incomplete')
                for p, digest in {**r['inputs'], **r['outputs']}.items():
                    if sha(path(root, p)) != digest:
                        errors.append('stale run evidence: ' + p)
                for proc in r['processes']:
                    if sha(path(root, proc['log'])) != proc['sha256']:
                        errors.append('stale execution log')
                split = read(path(root, cfg['split']))
                errors.extend(contract_errors(split))
                digest = sha(path(root, cfg['split']))
                if split_hash is not None and digest != split_hash:
                    errors.append('unfair split across competing runs')
                split_hash = digest
                if r['status'] != 'PASS':
                    failure = c.get('failures', {}).get(r['run_id'], {})
                    if not all(meaningful(failure.get(k)) for k in ('cause', 'retry', 'decision')):
                        errors.append('failure cause/retry/decision missing')
                    if r['status'] != 'FAIL':
                        errors.append('unfinished experiment')
                    continue
                if set(r['outputs']) != set(cfg['outputs']):
                    errors.append('missing registered outputs')
                if [p['purpose'] for p in r['processes']] != ['train', 'validate'] or any(p['returncode'] for p in r['processes']):
                    errors.append('no real successful train and validation')
                if cfg['commands'][0]['argv'][1] == cfg['commands'][1]['argv'][1]:
                    errors.append('validator source not independent')
                for proc, command in zip(r['processes'], cfg['commands']):
                    if proc['argv'][1:] != command['argv'][1:]:
                        errors.append('executed command differs from config')
                values = read(path(root, cfg['metrics']))
                if values['split_sha256'] != digest or values['evaluated_ids'] != split['validation']:
                    errors.append('validator evaluated a different validation set')
                if set(values['metrics']) != set(expected_metric_names) or any(not finite(v) for v in values['metrics'].values()):
                    errors.append('metric contract mismatch/nonfinite values')
                if cfg.get('selection_partition') != 'validation':
                    errors.append('test set used for selection')
                if not all(meaningful(values.get(k)) for k in ('independence', 'leakage_review')):
                    errors.append('independent validation/leakage review missing')
                if c['family'] == 'dl':
                    training = read(path(root, cfg['training_record']))
                    required = ('seed', 'parameters', 'batch_size', 'input_shape', 'best_epoch', 'epochs',
                                'early_stopping', 'device', 'peak_memory_mb', 'elapsed_seconds')
                    if any(k not in training for k in required) or training.get('epochs', 0) < 1:
                        errors.append('DL training record incomplete')
                    if training.get('device', '').startswith('cuda') and training.get('peak_memory_mb', 999999) > report['budget']['vram_mb']:
                        errors.append('DL exceeds VRAM budget')
                    if cfg.get('checkpoint') not in r['outputs'] or cfg.get('training_record') not in r['outputs']:
                        errors.append('DL checkpoint/training record not captured')
                successful[receipt_path] = (c, values, cfg, r)
            if c.get('selected_run'):
                if c['selected_run'] not in c['runs'] or c['selected_run'] not in successful:
                    errors.append('selected run is not a successful candidate run')
                else:
                    rows.append(successful[c['selected_run']])
        found = {p.relative_to(root).as_posix() for p in (root / '求解/实验运行' / qid).glob('*/receipt.json')}
        if found != all_receipts:
            errors.append('unlisted or missing experiment receipts')
        if report['applicable']:
            families = {c['family'] for c, *_ in rows}
            if 'baseline' not in families:
                errors.append('successful baseline missing')
            if 'ml' not in families and not meaningful(report.get('ml_omission_reason')):
                errors.append('ML strong baseline missing without reason')
            if gate['class'] in ('A', 'B') and 'dl' not in families:
                blocked = report.get('pilot_blocked', {})
                if not any(c['family'] == 'dl' and c['runs'] for c in candidates) or not all(
                    meaningful(blocked.get(k)) for k in ('reason', 'lightweight_retry', 'cpu_assessment', 'cost_evidence')):
                    errors.append('eligible problem missing successful DL pilot or evidenced resource termination')
            if len(report['metrics']) < 2:
                errors.append('at least two task-relevant metrics required')
            selected = [r for r in rows if r[0]['id'] == report['main_model']]
            if len(selected) != 1:
                errors.append('main model must identify a successfully validated candidate')
            elif rows:
                metric = report['metrics'][0]
                sign = 1 if metric['direction'] == 'min' else -1
                best = min(sign * row[1]['metrics'][metric['name']] for row in rows)
                chosen = sign * selected[0][1]['metrics'][metric['name']]
                if chosen > best + report.get('selection_tolerance', 0) and not meaningful(report.get('selection_override_reason')):
                    errors.append('nonleading main model needs explicit scientific/cost tradeoff justification')
            if not meaningful(report['selection_reason']) or not meaningful(report['tradeoffs']):
                errors.append('model selection reasons/tradeoffs missing')
            improved = report.get('improved_model')
            if improved and improved not in {c['id'] for c, *_ in rows if c['family'] == 'improved'}:
                errors.append('improved model not validated')
            for c in candidates:
                if c['family'] == 'improved':
                    base = next((b for b in candidates if b['id'] == c.get('base_candidate')), None)
                    if base is None or not base.get('selected_run') or not meaningful(c.get('improvement_reason')):
                        errors.append('improved model missing validated base and motivation')
                    elif c.get('selected_run'):
                        first = read(path(root, base['selected_run']))['finished_at']
                        second = read(path(root, c['selected_run']))['started_at']
                        if first >= second:
                            errors.append('improvement preceded its validated baseline')
        elif gate['class'] != 'C' or candidates:
            errors.append('non-learning problem must explicitly explain C and have no learning runs')
        if report['budget']['vram_mb'] > 4096 and not meaningful(report['budget'].get('exception_reason')):
            errors.append('GTX 1650 4GB default exceeded without evidence')
        if (trial_count > report['budget']['max_trials'] or elapsed_total > report['budget']['seconds']) and not meaningful(report['budget'].get('exception_reason')):
            errors.append('trial/time budget exceeded without measured reason')
        if stage in ('paper', 'final'):
            for rel, content in generated_outputs(root, report, rows).items():
                if not path(root, rel).is_file() or path(root, rel).read_text(encoding='utf-8') != content:
                    errors.append('missing/stale generated comparison: ' + rel)
    except Exception as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    return dict(status='FAIL' if errors else 'PASS', errors=errors)


def tex(value):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
               '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(c, c) for c in str(value))


def generated_outputs(root, report, rows=None):
    """Deterministic output: source metrics only, never generated scores/prose claims."""
    if rows is None:
        rows = []
        for c in report['candidates']:
            if c.get('selected_run'):
                r = read(path(root, c['selected_run']))
                cfg = read(path(root, r['config']))
                rows.append((c, read(path(root, cfg['metrics'])), cfg, r))
    qid = report['question_id']
    lines = ['% Generated model comparison; edit scientific report and rerun the builder.']
    if report.get('purpose') == 'demo':
        lines.append(r'\noindent DEMO：合成数据流程演练，不代表赛题结果。\par')
    lines.extend([r'\noindent ' + tex(report['eligibility']['reason']) + r'\par'])
    if report['applicable']:
        lines += [r'\noindent ' + tex(report['comparison_conditions']) + r'\par',
                  r'\begin{longtable}{p{.27\textwidth}rrp{.28\textwidth}}',
                  r'\caption{候选模型性能比较}\label{tab:model-' + qid + r'}\\',
                  r'\toprule 模型 & ' + tex(report['metrics'][0]['label']) + ' & ' + tex(report['metrics'][1]['label']) + r' & 角色与复杂度\\\midrule\endfirsthead',
                  r'\toprule 模型 & ' + tex(report['metrics'][0]['label']) + ' & ' + tex(report['metrics'][1]['label']) + r' & 角色与复杂度\\\midrule\endhead']
        for c, values, cfg, r in rows:
            role = '主模型' if c['id'] == report['main_model'] else ('改进模型' if c['id'] == report.get('improved_model') else '候选')
            nums = [f"{values['metrics'][m['name']]:.6g}" for m in report['metrics'][:2]]
            lines.append(tex(c['name']) + ' & ' + ' & '.join(nums) + ' & ' + tex(role + '；' + c['complexity']) + r'\\')
        lines += [r'\bottomrule\end{longtable}', r'\noindent 表\ref{tab:model-' + qid + r'}列出统一验证口径的候选结果。\par']
        for c, values, cfg, r in rows:
            seconds = r['processes'][0]['elapsed_seconds']
            extras = '；'.join(m['label'] + '=' + f"{values['metrics'][m['name']]:.6g}" for m in report['metrics'][2:])
            lines.append(r'\noindent ' + tex(c['name'] + '：' + c['rationale'] + '；' + c['decision'] +
                f'；训练进程耗时 {seconds:.3f} 秒；' + extras) + r'\par')
        lines.append(r'\noindent ' + tex(report['selection_reason'] + ' ' + report['tradeoffs']) + r'\par')
        for c in report['candidates']:
            for f in c.get('failures', {}).values():
                lines.append(r'\noindent ' + tex(c['name'] + '试验异常：' + f['cause'] + '；' + f['retry'] + '；' + f['decision']) + r'\par')
    output = '\n'.join(lines) + '\n'
    # All metrics/costs go to an ordinary reusable result CSV, not an internal log.
    import csv
    import io
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['model', 'family', *[m['name'] for m in report['metrics']], 'train_seconds', 'complexity', 'main'])
    for c, values, cfg, r in rows:
        writer.writerow([c['name'], c['family'], *[values['metrics'][m['name']] for m in report['metrics']],
                         r['processes'][0]['elapsed_seconds'], c['complexity'], c['id'] == report['main_model']])
    return {f'论文/章节内容/{qid}_模型比较.generated.tex': output,
            f'求解/模型比较/{qid}.csv': stream.getvalue()}


def supporting_gate(root, manifest, question_id=None, stage='question', package=False):
    """Modern workspaces cannot omit declarations; legacy stays explicit/compatible."""
    root = Path(root).resolve()
    modern = (root / '工作区清单.json').is_file()
    errors = []
    for q in manifest['questions']:
        if question_id and q['question_id'] != question_id:
            continue
        ref = q.get('model_selection')
        if not ref:
            if modern:
                errors.append(q['question_id'] + ': model_selection declaration missing')
            continue
        result = audit_report(root, ref, stage)
        errors.extend(q['question_id'] + ': ' + e for e in result['errors'])
        if result['status'] == 'PASS':
            r = read(path(root, ref))
            if r['question_id'] != q['question_id']:
                errors.append('question/report ID mismatch')
            if modern and r['purpose'] != read(root / '工作区清单.json')['purpose']:
                errors.append('DEMO/production evidence cannot be interchanged')
            if package and r['applicable']:
                for rel, content in generated_outputs(root, r).items():
                    if rel.endswith('.csv') and (not path(root, rel).is_file() or path(root, rel).read_text(encoding='utf-8') != content):
                        errors.append('missing/stale public comparison CSV')
                listed = {s['path'] for s in q['source_files']}
                for c in r['candidates']:
                    for rp in c['runs']:
                        receipt = read(path(root, rp))
                        cfg = read(path(root, receipt['config']))
                        if not set(cfg['sources']) <= listed:
                            errors.append('candidate/validator source missing from public package')
                csv_path = f"求解/模型比较/{q['question_id']}.csv"
                if csv_path not in {s['path'] for s in q['supplementary_materials']}:
                    errors.append('full candidate comparison CSV missing from support manifest')
    return errors


def select_main(root, report_path):
    """Choose by declared validation metric; tie-break using declared simplicity.

Scientific overrides belong in the report, never in the test set.
"""
    report = read(path(root, report_path))
    metric = report['metrics'][0]
    choices = []
    rank = {'baseline': 0, 'ml': 1, 'dl': 2, 'improved': 3}
    for c in report['candidates']:
        if not c.get('selected_run'):
            continue
        receipt = read(path(root, c['selected_run']))
        if receipt['status'] != 'PASS':
            continue
        cfg = read(path(root, receipt['config']))
        value = read(path(root, cfg['metrics']))['metrics'][metric['name']]
        score = value if metric['direction'] == 'min' else -value
        choices.append((score, rank[c['family']], c['id']))
    if not choices:
        raise ValueError('No validated candidates')
    best = min(c[0] for c in choices)
    eligible = [c for c in choices if c[0] <= best + report.get('selection_tolerance', 0)]
    chosen = min(eligible, key=lambda c: (c[1], c[0], c[2]))
    report['main_model'] = chosen[2]
    report['selection_reason'] = '按预先登记的验证指标' + metric['label'] + '及实际差异容差选择' + chosen[2] + '；容差范围内优先较简单的候选家族。'
    # Audit the proposed selection before writing it permanently.
    old = path(root, report_path).read_bytes()
    try:
        write(path(root, report_path), report)
        result = audit_report(root, report_path)
        if result['status'] != 'PASS':
            raise ValueError('; '.join(result['errors']))
    except Exception:
        path(root, report_path).write_bytes(old)
        raise
    return {'status': 'SELECTED', 'main_model': chosen[2]}


def paper_gate(root, manifest):
    root = Path(root).resolve()
    sp = root / '求解/支撑材料清单.json'
    modern = (root / '工作区清单.json').is_file()
    if not sp.is_file():
        return ['support manifest required for model selection'] if modern else []
    supporting = read(sp)
    errors = supporting_gate(root, supporting, stage='paper')
    chapters = [c for c in manifest['chapters'] if c['role'] == 'problem']
    if [c['chapter_id'] for c in chapters] != [q['question_id'] for q in supporting['questions']]:
        errors.append('paper/support question mapping differs')
    for chapter, q in zip(chapters, supporting['questions']):
        if not q.get('model_selection'):
            continue
        fragment = path(root, '论文/' + chapter['tex_path']).read_text(encoding='utf-8-sig')
        active = re.sub(r'(?m)(?<!\\)%.*$', '', fragment)
        expected = r'\input{章节内容/' + q['question_id'] + '_模型比较.generated.tex}'
        if active.count(expected) != 1:
            errors.append(q['question_id'] + ': comparison must be included exactly once in its problem chapter')
    return errors


def publish(root, manifest_path='求解/支撑材料清单.json'):
    root = Path(root).resolve()
    manifest = read(path(root, manifest_path))
    errors = supporting_gate(root, manifest)
    if errors:
        raise ValueError('\n'.join(errors))
    index = root / '求解/结果索引.md'
    text = index.read_text(encoding='utf-8-sig') if index.exists() else '# 结果索引\n'
    block = ['<!-- MODEL_SELECTION_BEGIN -->']
    for q in manifest['questions']:
        if not q.get('model_selection'):
            continue
        r = read(path(root, q['model_selection']))
        for rel, content in generated_outputs(root, r).items():
            dest = path(root, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding='utf-8', newline='')
        block.append(f"- {q['question_id']}：模型选择报告 [{q['model_selection']}]({q['model_selection']})；Main Model={r['main_model']}；比较表：求解/模型比较/{q['question_id']}.csv")
    block.append('<!-- MODEL_SELECTION_END -->')
    replacement = '\n'.join(block)
    pattern = r'<!-- MODEL_SELECTION_BEGIN -->.*?<!-- MODEL_SELECTION_END -->'
    text = re.sub(pattern, lambda _: replacement, text, flags=re.S) if re.search(pattern, text, re.S) else text.rstrip()+'\n\n'+replacement+'\n'
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(text, encoding='utf-8')
    return {'status': 'GENERATED', 'questions': len(manifest['questions'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'audit', 'publish', 'select'))
    parser.add_argument('--project-root', type=Path, default=Path('.'))
    parser.add_argument('--config')
    parser.add_argument('--manifest', default='求解/支撑材料清单.json')
    parser.add_argument('--question-id')
    parser.add_argument('--stage', choices=('plan', 'question', 'paper', 'final'), default='question')
    parser.add_argument('--report', default='求解/验收输出/模型选择.audit.json')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    root = args.project_root.resolve()
    from workspace_context import shared_context
    context = shared_context(root)
    if context:
        context.write_path(args.report)
    if args.action == 'run':
        result = run_experiment(root, args.config, args.timeout)
    elif args.action == 'select':
        result = select_main(root, args.config)
    elif args.action == 'publish':
        result = publish(root, args.manifest)
    else:
        manifest = read(path(root, args.manifest))
        if args.question_id and args.question_id not in {q['question_id'] for q in manifest['questions']}:
            raise ValueError('unknown question ID')
        errors = supporting_gate(root, manifest, args.question_id, args.stage)
        if args.stage in ('paper', 'final'):
            errors += paper_gate(root, read(root/'论文/论文输入.json'))
        result = dict(status='FAIL' if errors else 'PASS', errors=errors,
                      assurance='执行证据与一致性检查；不替代适用性、代码独立性及论文科学审阅')
        write(path(root, args.report), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result['status'] == 'FAIL'


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    raise SystemExit(main())
