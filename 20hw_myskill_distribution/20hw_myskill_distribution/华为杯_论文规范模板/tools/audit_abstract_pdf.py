"""Match the actual abstract glyph stream and inspect each intended bold span."""
from __future__ import annotations
import json
from pathlib import Path
import pymupdf as fitz
from audit_abstract import audit_abstract_manifest, simplify_tex
from audit_pdf_layout import destination, glyphs, is_bold, find_glyph_text, norm
from paper_contract import commands, strip_comments


def audit_abstract_pdf(pdf_path: Path, manifest_path: Path):
    failures, checks = [], []
    def check(code, ok, **details):
        row = {'code': code, 'ok': bool(ok), **details}
        checks.append(row)
        if not ok:
            failures.append(row)
    source = audit_abstract_manifest(manifest_path)
    check('abstract_source_gate', source['status']=='PASS', failures=source['failures'])
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        raw = strip_comments((manifest_path.parent / manifest['abstract_tex_path']).read_text(encoding='utf-8-sig'))
        text = norm(simplify_tex(raw))
        with fitz.open(pdf_path) as doc:
            start = destination(doc, doc.resolve_names(), 'section.1')
            if start is None:
                raise ValueError('缺少实际正文开始位置')
            chars, traces = [], {}
            for page in range(start[0]):
                traces[page] = doc[page].get_texttrace()
                chars += [{**c, 'page': page} for c in glyphs(doc[page]) if c['bbox'][1] < doc[page].rect.height-65]
            matches = find_glyph_text(chars, text)
            check('complete_abstract_matches_actual_pdf', len(matches)==1,
                  message='无法可靠匹配的公式或宏必须修复映射并实际复核，不把文本猜测写为通过。')
            if len(matches)==1:
                cs = matches[0]
                expected_bold = set()
                for i, command in enumerate(commands(raw, ('textbf',)), 1):
                    offset = len(norm(simplify_tex(raw[:command.start])))
                    length = len(norm(simplify_tex(command.argument)))
                    span = cs[offset:offset+length]
                    expected_bold.update(range(offset, offset+length))
                    check(f'abstract_bold_span_{i}', len(span)==length and bool(span) and
                          all(is_bold(c, traces[c['page']]) for c in span),
                          text=simplify_tex(command.argument), pages=sorted({c['page']+1 for c in span}))
                # Global bfseries or a redefined textbf must not silently turn
                # the whole paragraph into a bold block or erase emphasis.
                unexpected = [i for i,c in enumerate(cs) if i not in expected_bold and
                              c['c'].isalnum() and is_bold(c, traces[c['page']])]
                check('abstract_prose_not_globally_bold', not unexpected, unexpected_glyph_count=len(unexpected))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        check('abstract_pdf_readable', False, error=str(exc))
    return {'status':'FAIL' if failures else 'PASS', 'checks':checks, 'failures':failures,
            'scope':'摘要源证据与实际字形；不替代科学结果真实性审查或整篇论文验收。'}
