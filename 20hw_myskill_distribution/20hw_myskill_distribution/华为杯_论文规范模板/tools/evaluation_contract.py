"""Evaluation source structure; semantic claims still require actual review."""
from __future__ import annotations
import hashlib
import re
from paper_contract import commands, strip_comments, EVALUATION_SUBSECTIONS

REVIEW_DIMENSIONS = ('advantages_evidence', 'limitations_causes_impacts',
                     'transfer_conditions', 'improvement_paths',
                     'verified_vs_proposed', 'substance_without_padding')


def prose_text(text):
    text = re.sub(r'\\(?:label|ref|eqref|cite|citep|citet)\s*\{[^{}]*\}', '', text)
    text = re.sub(r'\\[A-Za-z@]+\*?', '', text)
    return re.sub(r'[\s{}~\[\]]', '', text)


def inspect_evaluation(text):
    text = strip_comments(text)
    errors, groups = [], {}
    heads = commands(text, ('subsection',))
    if tuple(h.argument for h in heads) != EVALUATION_SUBSECTIONS:
        return dict(failures=['评价章必须依次包含三个规定二级节'], groups={})
    if commands(text, ('subsubsection', 'paragraph', 'subparagraph')):
        errors.append('评价章只含三个二级节；条目不用下级标题代替')
    if re.search(r'\\(?:clearpage|newpage|pagebreak|vspace|vfill|fontsize|zihao|linespread|setstretch|geometry|newgeometry|resizebox|scalebox|parbox|hspace|hfill|small|large|Large|tiny|baselinestretch|setlength|addtolength)\b', text):
        errors.append('评价章不得强制分页或覆盖字号、行距、版心、间距来凑页')
    for index, head in enumerate(heads):
        body = text[head.end:heads[index+1].start if index+1 < len(heads) else len(text)]
        if index < 2:
            # One ordinary list per section; nested bullets do not inflate counts.
            envs = commands(body, ('begin', 'end'))
            if len(envs) != 2 or envs[0].name != 'begin' or envs[1].name != 'end' or envs[0].argument not in ('enumerate', 'itemize') or envs[1].argument != envs[0].argument:
                errors.append(head.argument + '须使用一个 enumerate/itemize 分点列表，不嵌套')
                groups[head.argument] = []
                continue
            inner = body[envs[0].end:envs[1].start]
            items = list(re.finditer(r'\\item(?![A-Za-z@])(?:\s*\[[^\]]*\])?\s*', inner))
            values = [inner[m.end():items[i+1].start() if i+1 < len(items) else len(inner)].strip() for i,m in enumerate(items)]
            if len(values) < 3:
                errors.append(head.argument + '至少3点')
            for i, value in enumerate(values, 1):
                # Bold/description labels alone are not explanatory content.
                explanation = value
                labels = commands(value, ('textbf',))
                if labels and not value[:labels[0].start].strip():
                    explanation = value[labels[0].end:]
                if not re.search(r'[\u4e00-\u9fffA-Za-z]', prose_text(explanation)):
                    errors.append(f'{head.argument}第{i}点缺少具体解释')
            groups[head.argument] = values
        else:
            if commands(body, ('begin', 'end')) or re.search(r'\\item\b|\\\\|\\(?:newline|linebreak)\b', body):
                errors.append('模型的推广与改进须使用自然段，不使用列表、盒子或换行冒充分段')
            values = [v.strip() for v in re.split(r'\n\s*\n|\\par(?![A-Za-z@])', body) if re.search(r'[\u4e00-\u9fffA-Za-z]', prose_text(v))]
            if len(values) < 2:
                errors.append('模型的推广与改进至少两个自然段')
            for v in values:
                plain = prose_text(v)
                if re.match(r'(?:[（(]?[0-9一二三四五六七八九]+[）).、]|[•●]|[-*])', plain):
                    errors.append('模型的推广与改进不得手写编号或项目符号分点')
            groups[head.argument] = values
    all_values = [prose_text(v) for values in groups.values() for v in values if prose_text(v)]
    if len(all_values) != len(set(all_values)):
        errors.append('评价章存在完全重复的条目或段落，不得重复凑页')
    return dict(failures=errors, groups=groups,
                counts={k:len(v) for k,v in groups.items()},
                source_sha256=hashlib.sha256(text.encode('utf8')).hexdigest(),
                assurance='仅核对结构和显式重复；科学依据、解释质量与未来设想须实际审阅。')
