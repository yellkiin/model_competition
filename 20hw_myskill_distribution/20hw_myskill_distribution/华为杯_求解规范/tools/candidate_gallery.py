"""Rebuildable display copies; scientific originals and approvals stay upstream."""
from collections import Counter
import html
import json
import os
from pathlib import Path
import shutil
from urllib.parse import quote

from filesystem_paths import native_path
from workspace_context import bounded, file_hash, atomic_json
from visual_routes import primary_output

QUALITY_ZH = {'planned': '待生成', 'review_required': '待复核', 'qualified': '合格', 'failed': '失败', 'stale': '过期'}
USE_ZH = {'paper': '正文', 'reserve': '待选', 'supplement': '补充材料', 'rejected': '淘汰'}


def token(value):
    """Deterministic safe filename; display names remain unmodified in HTML."""
    import hashlib
    import re
    text = str(value)
    return re.sub(r'[^\w\-\u3400-\u9fff]', '_', text)[:64] + '-' + hashlib.sha256(text.encode()).hexdigest()[:10]


def build(root, registry_path, output, runtime, audit_figure, *, allow_demo=False):
    root = Path(root).resolve()
    output = bounded(root, output)
    if output.name != '待选图库':
        raise ValueError('图库输出目录必须命名为待选图库')
    # Clear the current presentation before rebuilding: failures must not leave
    # an old "qualified" page representing missing or invalidated artifacts.
    page = bounded(root, output / 'index.html')
    index = bounded(root, output / 'index.json')
    status = bounded(root, output / '构建状态.json')
    native_path(output).mkdir(parents=True, exist_ok=True)
    native_path(page).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>待选图库正在重建</title><h1>待选图库正在重新核验</h1><p>当前尚无已发布的合格展示，完成核验后刷新。</p></html>', encoding='utf8')
    atomic_json(index, [])
    atomic_json(status, {'status': 'BUILDING'})
    try:
        result = _build(root, registry_path, output, runtime, audit_figure, allow_demo=allow_demo)
        atomic_json(status, result)
        return result
    except Exception as exc:
        atomic_json(status, {'status': 'FAILED', 'error': str(exc)})
        native_path(page).write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>待选图库待修复</title><h1>图库重建未通过</h1><p>旧合格展示已撤下，修复后重新构建。</p><p>' + html.escape(str(exc)) + '</p></html>', encoding='utf8')
        raise


def _build(root, registry_path, output, runtime, audit_figure, *, allow_demo=False):
    root = Path(root).resolve()
    output = bounded(root, output)
    if output.name != '待选图库':
        raise ValueError('图库输出目录必须命名为待选图库')
    registry = json.loads(native_path(bounded(root, registry_path)).read_text(encoding='utf-8-sig'))
    # Validate existing managed paths before any mutation; never follow a
    # junction or recursively delete an arbitrary directory supplied by JSON.
    old_manifest = output / '展示副本.json'
    old = json.loads(native_path(bounded(root, old_manifest)).read_text(encoding='utf8')) if old_manifest.is_file() else {'files': []}
    old_paths = []
    for entry in old['files']:
        path = bounded(output / '图片', entry['display_path'])
        old_paths.append((path, entry['sha256']))
    for name in ('index.html', 'index.json', '展示副本.json', '图片'):
        bounded(root, output / name)
    native_path(output).mkdir(parents=True, exist_ok=True)
    native_path(output / '图片').mkdir(exist_ok=True)
    records, copies, cards = [], [], []
    esc = html.escape

    def link(path):
        return quote(os.path.relpath(path, output).replace(os.sep, '/'), safe='/.-')

    def copy_asset(source, destination):
        source = bounded(root, source)
        destination = bounded(output / '图片', destination)
        if not native_path(source).is_file():
            raise FileNotFoundError('展示源图缺失: ' + str(source))
        digest = file_hash(source)
        if native_path(destination).exists() and not native_path(destination).is_file():
            raise ValueError('展示副本路径不是文件: ' + str(destination))
        native_path(destination.parent).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native_path(source), native_path(destination))
        if digest != file_hash(destination) or digest != file_hash(source):
            raise ValueError('展示复制期间源图发生变化: ' + str(source))
        copies.append({'source_path': source.relative_to(root).as_posix(),
                       'display_path': destination.relative_to(output / '图片').as_posix(), 'sha256': digest})
        return destination

    questions = {q['question_id']: q for q in registry['questions']}
    from supporting_contract import question_name
    question_folders = {qid: question_name(i) for i, qid in enumerate(questions, 1)}
    for c in registry['candidates']:
        gate = None
        if c['quality'] == 'qualified':
            try:
                gate = audit_figure(root, c['plan_path'], c['figure_id'], 'render', runtime, allow_demo)
            except (ValueError, OSError, KeyError, StopIteration) as exc:
                gate = {'status': 'FAIL', 'error': str(exc)}
        effective = c['quality'] if gate is None or gate['status'] == 'PASS' else 'stale'
        item = {**c, 'effective_quality': effective}
        if gate is not None and gate['status'] != 'PASS':
            item['current_render_failure'] = gate
        records.append(item)
        if c['destination'] not in {'paper', 'reserve', 'supplement'} or effective != 'qualified':
            continue
        from prepare_academic_figure_review import plan_figures
        plan = json.loads(native_path(bounded(root, c['plan_path'])).read_text(encoding='utf-8-sig'))
        f = next(f for f in plan_figures(plan) if f['figure_id'] == c['figure_id'])
        preview_source = bounded(root, f['outputs']['preview'])
        # PNG is an actual rendered preview, not a renamed JPEG/PDF.
        from PIL import Image
        with Image.open(native_path(preview_source)) as im:
            if im.format != 'PNG':
                raise ValueError('图库预览须为真实 PNG: ' + str(preview_source))
            im.verify()
        if c['question_id'] not in questions:
            raise ValueError('候选图所属问题未登记: ' + str(c['question_id']))
        q_name = questions[c['question_id']].get('display_name') or question_folders[c['question_id']]
        folder = Path(question_folders[c['question_id']])
        stem = token(c['figure_id'])
        preview = copy_asset(preview_source, folder / (stem + '.png'))
        source = bounded(root, primary_output(f))
        primary = preview if source == preview_source else copy_asset(source, folder / (stem + '-原图' + source.suffix.lower()))
        item['display_preview'] = preview.relative_to(output).as_posix()
        item['display_primary'] = primary.relative_to(output).as_posix()
        refs = ' · '.join('<a href="' + link(bounded(root, raw)) + '">' + label + '</a>'
                          for label, raw in [('计划', c['plan_path']), ('复核证据', f['qa_report']), ('源码', f['script'])])
        card = '<article><a href="' + link(primary) + '"><img loading="lazy" src="' + link(preview) + '" alt="' + esc(c['scientific_question'], quote=True) + '"></a>'
        card += '<h3>' + esc(c['figure_id'] + ' · ' + q_name + ' · ' + USE_ZH[c['destination']]) + '</h3>'
        for label, value in [('科学问题', c['scientific_question']), ('结论', c['conclusion']), ('限制', c['limitations']),
                             ('选用理由' if c['destination'] == 'paper' else '未入文原因', c['selection_reason']), ('推荐位置', c['recommended_section'])]:
            card += '<p>' + label + '：' + esc(value) + '</p>'
        card += '<p><a href="' + link(preview) + '">打开 PNG</a> · <a href="' + link(primary) + '">打开原图副本</a> · <a href="' + link(source) + '">权威源图</a></p>' + refs + '</article>'
        cards.append((c['destination'], card))
    desired = {bounded(output / '图片', e['display_path']) for e in copies}
    for path, expected in old_paths:
        if path not in desired and native_path(path).is_file():
            if file_hash(path) != expected:
                raise ValueError('旧展示副本被单独修改，停止自动移除: ' + str(path))
            native_path(path).unlink()
    counts = Counter(c['destination'] for c in records if c['effective_quality'] == 'qualified')
    pending = sum(c['effective_quality'] != 'qualified' for c in records)
    summary = f"候选总数：{len(records)}；合格正文：{counts['paper']}；合格补充：{counts['supplement']}；合格待选：{counts['reserve']}；合格淘汰：{counts['rejected']}；其他质量状态：{pending}。"
    empty = []
    for qid, question in questions.items():
        candidates = [c for c in records if c['question_id'] == qid]
        if any(c['effective_quality'] == 'qualified' and c['destination'] in {'reserve', 'supplement'} for c in candidates):
            continue
        review = question.get('completion_review') or {}
        from candidate_figures import review_inventory_current
        inventory_current = review_inventory_current(root, review)
        stale_figures = any(c['effective_quality'] == 'stale' for c in candidates)
        reviewed = inventory_current and not stale_figures
        review_status = ('关联图件或共享资源已过期，须重新复核' if stale_figures else
                         '文件清单当前一致；不等于科学完整性证明' if reviewed else '缺失或过期，仍需复查')
        reason = review.get('zero_remaining_reason') or '尚未填写零剩余原因；不能据此认定候选发现完整。'
        lines = ['<li><strong>' + esc(qid) + '：当前没有合格未入文图。</strong><p>' + esc(reason) + '</p>',
                 '<p>完成复查记录：' + review_status + '。</p>',
                 '<p>' + ('复查结论：' if reviewed else '历史复查结论（当前不可沿用）：') + esc(review.get('observation') or '尚未记录') + '</p>']
        lines += ['<p>' + esc(c['figure_id'] + '：' + USE_ZH.get(c['destination'], c['destination']) + '；' + c['selection_reason']) + '</p>' for c in candidates]
        empty.append(''.join(lines) + '</li>')
    style = 'body{margin:24px;font:16px/1.6 system-ui;color:#222;background:#fafafa}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:24px}article{padding:16px;background:white;border:1px solid #ddd}img{width:100%;height:auto;max-height:520px;object-fit:contain}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}a{color:#17615b}h3,p{overflow-wrap:anywhere}'
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>待选图库</title><style>' + style + '</style><h1>待选图库</h1><p>' + summary + '</p><p>此处展示副本可重建；科学数据、源码和权威成图在求解目录维护。文件审计不代替科学判断及实际看图。</p><h2>合格未入文图</h2><main>'
    page += ''.join(card for use, card in cards if use != 'paper') or '<p>当前没有合格未入文图，逐问原因与复查状态见下方。</p>'
    page += '</main><ul>' + ''.join(empty) + '</ul><details><summary>查看合格正文图（' + str(counts['paper']) + '）</summary><main>'
    page += ''.join(card for use, card in cards if use == 'paper') + '</main></details><h2>候选状态清单</h2><table><tr><th>编号</th><th>问题</th><th>质量</th><th>去向</th></tr>'
    for c in records:
        page += '<tr>' + ''.join('<td>' + esc(str(v)) + '</td>' for v in (c['figure_id'], c['question_id'], QUALITY_ZH.get(c['effective_quality'], c['effective_quality']), USE_ZH.get(c['destination'], c['destination']))) + '</tr>'
    page += '</table><p><a href="index.json">完整索引</a> · <a href="展示副本.json">展示副本来源与哈希</a></p></html>'
    atomic_json(output / '展示副本.json', {'schema_version': '1.0', 'files': copies})
    atomic_json(output / 'index.json', records)
    native_path(output / 'index.html').write_text(page, encoding='utf8')
    return {'status': 'BUILT', 'qualified_reserve_count': counts['reserve'], 'qualified_supplement_count': counts['supplement'],
            'display_copy_count': len(copies), 'path': str(output / 'index.html')}
