"""Source evidence for the first three chapters. No automatic semantic approval.

The agent reads sources and records a review; this module checks coverage,
literal traceability and freshness, not causality or scientific truth.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from paper_contract import balanced, commands, expand_fragment, strip_comments

REVIEW_DIMENSIONS = ('task_coverage', 'conditions_units_logic', 'source_attribution',
                     'method_assumption_result_separation', 'dependencies_outputs_validation',
                     'background_coherence', 'natural_expression', 'symbol_definitions')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(root, raw):
    path = (root / raw).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError('缺少证据文件: ' + str(path))
    return path


def source_bindings(manifest, paper_root, evidence):
    """Call only to prepare a new review, never to refresh a previous PASS."""
    workspace = paper_root.parent.resolve()
    paths = {local(workspace, s['path']) for s in evidence['sources']}
    # Bind all chapters: symbols removed from the table need local definitions.
    def add_tex(path):
        if path in paths:
            return
        paths.add(path)
        for c in commands(path.read_text(encoding='utf-8-sig'), ('input', 'include')):
            raw = Path(c.argument)
            add_tex(local(paper_root, str(raw if raw.suffix else raw.with_suffix('.tex'))))
    for c in manifest['chapters']:
        add_tex(local(paper_root, c['tex_path']))
    result = {p.relative_to(workspace).as_posix(): sha(p) for p in sorted(paths)}
    result['@evidence_content'] = hashlib.sha256(json.dumps(
        {k:v for k,v in evidence.items() if k != 'review'}, ensure_ascii=False,
        sort_keys=True).encode('utf8')).hexdigest()
    return result


def symbol_rows(text):
    rows = []
    clean = strip_comments(text)
    for cmd in commands(clean, ('GMCMSymbolRow',)):
        args, pos = [cmd.argument], cmd.end
        for _ in range(3):
            while pos < len(clean) and clean[pos].isspace():
                pos += 1
            arg, pos = balanced(clean, pos)
            args.append(arg)
        rows.append(dict(zip(('category', 'symbol', 'meaning', 'unit'), args)))
    return rows


def independent_symbol_error(symbol):
    # A subscript tuple is one object; top-level lists/equalities are not.
    symbol = symbol.strip().strip('$')
    if not symbol:
        return True
    depth = 0
    for c in symbol:
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        elif depth == 0 and c in ',，、;；=\n': return True
    return bool(re.search(r'\\(?:\\|newline|substack|begin|atop)\b|\\\\|[A-Za-z]\s+[A-Za-z]|\\[A-Za-z]+\s*\\[A-Za-z]+', symbol))


def symbol_source_errors(text):
    clean = strip_comments(text)
    errors = []
    if clean.count(r'\begin{GMCMSymbolTable}') != 1 or clean.count(r'\end{GMCMSymbolTable}') != 1:
        errors.append('符号章必须使用一个逻辑 GMCMSymbolTable')
    if re.search(r'\\(?:hline|cline|cmidrule|toprule|midrule|bottomrule|rowcolor|cellcolor|resizebox|scalebox|fontsize|small|tiny|scriptsize|GMCMTableNote)\b|\\begin\{(?:table|tabular|tabularx|minipage)', clean):
        errors.append('符号表不得增加表体线、底色、浮动/不可分页盒或覆盖字号/表注')
    try:
        rows = symbol_rows(clean)
        marker = r'\begin{GMCMSymbolTable}'
        if marker in clean:
            pos = clean.index(marker) + len(marker)
            while pos < len(clean) and clean[pos].isspace(): pos += 1
            note, pos = balanced(clean, pos)
            if not note.strip(): errors.append('关键符号表最终说明不能为空')
            body = clean[pos:clean.index(r'\end{GMCMSymbolTable}', pos)]
            for cmd in reversed(commands(body, ('GMCMSymbolRow',))):
                end = cmd.end
                for _ in range(3):
                    while end < len(body) and body[end].isspace(): end += 1
                    _, end = balanced(body, end)
                body = body[:cmd.start] + body[end:]
            if body.strip(): errors.append('表体只允许已登记的 GMCMSymbolRow；不得混入原始行、额外定义或样式覆盖')
        if not rows:
            errors.append('关键符号表不能为空')
        for row in rows:
            if independent_symbol_error(row['symbol']):
                errors.append('一个符号单元格只能定义一个独立对象: ' + row['symbol'])
            if any(not x.strip() for x in row.values()):
                errors.append('符号类别、含义和单位不得空缺；不适用单位写 —')
        if len({r['symbol'] for r in rows}) != len(rows):
            errors.append('关键符号表有重复对象')
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def audit_source(manifest, paper_root):
    errors, warnings = [], []
    paper_root = Path(paper_root).resolve()
    workspace = paper_root.parent
    try:
        raw = manifest['first_chapters_evidence_path']
        path = local(workspace, str((paper_root / raw).resolve().relative_to(workspace)))
        evidence = json.loads(path.read_text(encoding='utf-8-sig'))
        texts = [expand_fragment(paper_root, paper_root / c['tex_path']) for c in manifest['chapters']]
        errors.extend(symbol_source_errors(texts[2]))
        sources = {s['id']: s for s in evidence['sources']}
        if len(sources) != len(evidence['sources']) or not sources:
            errors.append('来源ID必须非空且唯一')
        for source in sources.values():
            local(workspace, source['path'])
            if source['kind'] not in ('problem', 'attachment', 'verified_external'):
                errors.append('题意来源不能由作者假设/方法/结果替代')
        if not any(s['kind'] == 'problem' for s in sources.values()):
            errors.append('必须登记原题来源')
        def check_ref(ref):
            if ref.get('source_id') not in sources or not ref.get('location') or not ref.get('quote'):
                errors.append('缺少可追溯的原文位置和摘录')
                return
            source = sources[ref['source_id']]
            p = local(workspace, source['path'])
            if p.suffix.lower() in ('.txt', '.md', '.tex') and ref['quote'] not in p.read_text(encoding='utf-8-sig'):
                errors.append('来源摘录与原文不匹配: ' + ref['quote'])
        context = evidence['context']
        for field in ('object_scene', 'difficulty_causes', 'scope_exclusions', 'shared_conditions'):
            if not isinstance(context.get(field), list):
                errors.append('context 缺少数组 ' + field)
                continue
            for fact in context[field]:
                check_ref(fact['source'])
                if not fact.get('text'): errors.append('背景事实为空')
        tasks = evidence['tasks']
        q = sum(c['role'] == 'problem' for c in manifest['chapters'])
        if len(tasks) != q or [t.get('order') for t in tasks] != list(range(1, q + 1)):
            errors.append('题目问数/顺序与论文问题章不一致')
        ids = [t['original_id'] for t in tasks]
        if len(set(ids)) != len(ids): errors.append('原题编号重复')
        for task in tasks:
            check_ref(task['source'])
            for field in ('inputs', 'action', 'object', 'conditions', 'outputs', 'validation', 'depends_on', 'subtasks', 'required_methods'):
                if field not in task: errors.append('题意依据缺少字段 ' + field)
            for dep in task.get('depends_on', []):
                if dep not in ids[:task['order'] - 1]: errors.append('前问依赖无效: ' + str(dep))
            for method in task.get('required_methods', []):
                if method not in task.get('coverage', {}).get('restatement_quote', ''):
                    errors.append('遗漏题目明确指定的方法: ' + method)
            for item in [task, *task.get('subtasks', [])]:
                check_ref(item['source'])
                coverage = item.get('coverage', {})
                if coverage.get('status') != 'verified' or not coverage.get('observation'):
                    errors.append('任务/子项尚未核验: ' + item.get('original_id', '?'))
                if not coverage.get('restatement_quote') or coverage['restatement_quote'] not in texts[0].split(r'\subsection{问题重述}')[-1]:
                    errors.append('任务/子项未绑定真实重述正文')
                for phrase in item.get('literal_requirements', []):
                    if phrase not in coverage.get('restatement_quote', ''):
                        errors.append('遗漏精确限定/题定方法: ' + phrase)
        if evidence.get('gaps'):
            errors.append('题意材料仍有待核验缺口')
        # Claims provide source attribution; semantic correctness remains an explicit review.
        if not evidence['claims']: errors.append('第一章关键事实主张尚未登记来源')
        for claim in evidence['claims']:
            if claim['kind'] not in ('problem', 'verified_external'):
                errors.append('背景/重述倒灌作者方法、假设或结果')
            check_ref(claim['source'])
            if claim['text'] not in texts[0]: errors.append('主张未对应当前第一章')
            source = sources.get(claim['source'].get('source_id'), {})
            if claim['kind'] == 'verified_external' and (source.get('kind') != 'verified_external' or not claim.get('citation_key')):
                errors.append('外部背景事实缺少核验来源及引用键')
            if claim['kind'] == 'verified_external' and claim.get('citation_key') not in texts[0]:
                errors.append('外部事实未在第一章实际引用')
        review = evidence['review']
        if review.get('bindings') != source_bindings(manifest, paper_root, evidence):
            errors.append('题意/符号审阅已过期，必须重读本次源文件')
        if not review.get('reviewer') or not review.get('reviewed_at'):
            errors.append('缺少实际审阅者或时间')
        for dim in REVIEW_DIMENSIONS:
            r = review.get(dim, {})
            if r.get('status') != 'verified' or not r.get('observation'):
                errors.append('待语义核验: ' + dim)
        for finding in review.get('findings', []):
            if finding.get('severity') == 'hard' and not finding.get('resolved'):
                errors.append(finding['message'])
            elif finding.get('severity') == 'style' and not finding.get('resolved'):
                warnings.append(finding['message'])
        symbols = evidence['symbols']
        rows = symbol_rows(texts[2])
        if len({s['symbol'] for s in symbols}) != len(symbols): errors.append('符号登记重复')
        core = {s['symbol']: s for s in symbols if s['in_core_table']}
        if set(core) != {r['symbol'] for r in rows}: errors.append('核心符号登记与实际表行不一致')
        for row in rows:
            s = core.get(row['symbol'], {})
            if any(s.get(k) != row[k] for k in ('category', 'meaning', 'unit')):
                errors.append('符号定义/单位与表中不一致: ' + row['symbol'])
        for s in symbols:
            if not s.get('scope') or not s.get('meaning'): errors.append('符号缺少含义/使用范围')
            definition = s['first_definition']
            tex = strip_comments(local(paper_root, definition['tex_path']).read_text(encoding='utf-8-sig'))
            if not definition.get('quote') or definition['quote'] not in tex:
                errors.append('符号缺少真实首次定义: ' + s['symbol'])
            uses = s.get('uses', [])
            if not uses: errors.append('符号未登记实际使用位置: ' + s['symbol'])
            for use in uses:
                used = strip_comments(local(paper_root, use['tex_path']).read_text(encoding='utf-8-sig'))
                if not use.get('quote') or use['quote'] not in used or s['symbol'] not in use['quote']:
                    errors.append('符号使用位置无效: ' + s['symbol'])
    except (KeyError, ValueError, OSError, TypeError, IndexError) as exc:
        errors.append('前三章证据缺失或无效: ' + str(exc))
    return {'status': 'FAIL' if errors else 'PASS', 'failures': errors, 'warnings': warnings,
            'assurance': '机械覆盖、源绑定与显式语义审阅记录；记录本身不证明实际阅读或自然度。'}
