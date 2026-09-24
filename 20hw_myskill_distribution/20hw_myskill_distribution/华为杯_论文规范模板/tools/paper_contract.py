"""Shared source contract for generation and audits; PDF layout is checked separately.

This module does not certify scientific evidence or infer physical pagination.
The canonical chapter policy lives in 华为杯_论文章节规范.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

HEADINGS = ('section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph')
FIRST_SUBSECTION = '问题的描述与分析'
PRELIMINARY = ('问题重述', '模型假设', '关键性符号说明')
RESTATEMENT_SUBSECTIONS = ('问题背景', '问题重述')
EVALUATION = '模型评价与展望'
EVALUATION_SUBSECTIONS = ('模型优点', '模型缺点', '模型的推广与改进')


def chinese_number(number: int) -> str:
    """Chinese chapter question ordinals, including Q > 10; no fixed Q."""
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError('问题序号必须为正整数')
    digits = '零一二三四五六七八九'
    if number < 10:
        return digits[number]
    if number < 20:
        return '十' + (digits[number % 10] if number % 10 else '')
    if number < 100:
        return digits[number // 10] + '十' + (digits[number % 10] if number % 10 else '')
    for size, unit in ((100000000, '亿'), (10000, '万'), (1000, '千'), (100, '百')):
        if number >= size:
            head, tail = divmod(number, size)
            return chinese_number(head) + unit + (
                ('零' if tail < size // 10 else '') + chinese_number(tail) if tail else '')
    raise AssertionError(number)


def chapter_blueprint(question_count: int) -> list[dict]:
    chinese_number(question_count)  # validate without a mechanical upper bound
    pairs = [(x, 'preliminary') for x in PRELIMINARY]
    pairs += [(f'问题{chinese_number(i)}求解与分析', 'problem') for i in range(1, question_count + 1)]
    pairs += [(EVALUATION, 'evaluation'), ('参考文献', 'references')]
    return [{'order': i, 'title': title, 'role': role} for i, (title, role) in enumerate(pairs, 1)]


def strip_comments(text: str) -> str:
    """Keep escaped percent signs, including the distinction between \\% and \\\\%."""
    return re.sub(r'(?m)(?<!\\)((?:\\\\)*)%[^\n]*', r'\1', text)


@dataclass(frozen=True)
class Command:
    name: str
    argument: str
    start: int
    end: int
    starred: bool = False
    optional: str | None = None


def balanced(text: str, start: int, opening: str = '{', closing: str = '}') -> tuple[str, int]:
    if start >= len(text) or text[start] != opening:
        raise ValueError(f'位置 {start} 缺少 {opening}')
    level, i = 1, start + 1
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        if text[i] == opening:
            level += 1
        elif text[i] == closing:
            level -= 1
            if not level:
                return text[start + 1:i], i + 1
        i += 1
    raise ValueError(f'位置 {start} 的 {opening} 未闭合')


def commands(text: str, names: tuple[str, ...]) -> list[Command]:
    """Parse literal commands and balanced arguments (no single-brace regex)."""
    text = strip_comments(text)
    pattern = re.compile(r'\\(' + '|'.join(map(re.escape, names)) + r')(?![A-Za-z@])(\*)?\s*')
    result, cursor = [], 0
    while match := pattern.search(text, cursor):
        pos, optional = match.end(), None
        if pos < len(text) and text[pos] == '[':
            optional, pos = balanced(text, pos, '[', ']')
            while pos < len(text) and text[pos].isspace():
                pos += 1
        argument, end = balanced(text, pos)
        result.append(Command(match[1], argument, match.start(), end, bool(match[2]), optional))
        cursor = end
    return result


def expand_fragment(paper_root: Path, path: Path, active: tuple[Path, ...] = ()) -> str:
    """Use TeX's main working directory for all explicit input paths; fail on cycles."""
    paper_root, path = paper_root.resolve(), path.resolve()
    path.relative_to(paper_root)
    if path in active:
        raise ValueError('章节输入循环: ' + str(path))
    if path.suffix != '.tex' or not path.is_file():
        raise ValueError('章节输入必须为存在的 .tex: ' + str(path))
    text = strip_comments(path.read_text(encoding='utf-8-sig'))
    calls = commands(text, ('input', 'include'))
    for call in reversed(calls):
        raw = Path(call.argument)
        child = paper_root / (raw if raw.suffix else raw.with_suffix('.tex'))
        text = text[:call.start] + expand_fragment(paper_root, child, (*active, path)) + text[call.end:]
    return text


def manifest_errors(manifest: dict) -> list[str]:
    chapters = manifest.get('chapters', [])
    if not isinstance(chapters, list) or not all(isinstance(c, dict) for c in chapters):
        return ['chapters 必须为对象数组']
    q = sum(c.get('role') == 'problem' for c in chapters)
    if not q:
        return ['论文必须包含实际问题章节']
    expected = chapter_blueprint(q)
    errors = []
    if len(chapters) != len(expected):
        errors.append(f'Q={q} 时 manifest 必须为 {q + 5} 章；附录由工具另行生成')
    ids = [c.get('chapter_id') for c in chapters]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(map(str, ids))):
        errors.append('chapter_id 必须非空且唯一')
    paths = [c.get('tex_path') for c in chapters]
    if len(paths) != len(set(map(str, paths))):
        errors.append('不同章节不能复用同一源文件')
    for index, (chapter, wanted) in enumerate(zip(chapters, expected), 1):
        for key in ('title', 'role', 'order'):
            if chapter.get(key) != wanted[key] or (key == 'order' and isinstance(chapter.get(key), bool)):
                errors.append(f'第 {index} 章 {key} 应为 {wanted[key]!r}，实际为 {chapter.get(key)!r}')
        if chapter.get('level', 1) != 1:
            errors.append(f'第 {index} 章 manifest level 必须为 1')
    return errors


def fragment_errors(text: str, chapter: dict) -> list[str]:
    text = strip_comments(text)
    errors = []
    if chapter.get('order') in (1, 2, 3) and re.search(r'\\(?:clearpage|cleardoublepage|newpage|pagebreak|include)\b', text):
        errors.append('前三章由共享类控制自然分页；章节不得强制分页或使用 include')
    try:
        headings = commands(text, HEADINGS)
    except ValueError as exc:
        return [str(exc)]
    sections = [h for h in headings if h.name == 'section']
    if chapter['role'] == 'references':
        # natbib's bibsection produces the numbered heading exactly once.
        if headings:
            errors.append('参考文献标题由统一 bibliography 样式生成，fragment 不得另写章节标题')
        if len(re.findall(r'\\bibliography\s*\{|\\begin\s*\{thebibliography\}', text)) != 1:
            errors.append('参考文献 fragment 必须且只能有一个 bibliography/thebibliography 入口')
        return errors
    if len(sections) != 1 or sections[0].argument != chapter['title'] or sections[0].starred:
        errors.append('fragment 必须且只能有一个与 manifest 完全一致的有编号一级标题')
    if headings and (not sections or headings[0] != sections[0]):
        errors.append('章节不能在一级标题前出现子标题')
    if any(h.starred or h.optional is not None for h in headings):
        errors.append('章节标题须有统一编号，不能用星号或另设目录短标题')
    # Literal titles make source/PDF comparison unambiguous; formatting belongs in the class.
    if any(re.search(r'[\\{}]', h.argument) for h in headings):
        errors.append('章节标题仅写文字，样式由统一配置处理')
    subsections = [h.argument for h in headings if h.name == 'subsection']
    if chapter['title'] == PRELIMINARY[0] and tuple(subsections) != RESTATEMENT_SUBSECTIONS:
        errors.append('问题重述章只能依次包含问题背景、问题重述两个二级标题')
    if chapter['role'] == 'problem' and (not subsections or subsections[0] != FIRST_SUBSECTION):
        errors.append('问题章第一个二级标题必须为问题的描述与分析')
    if chapter['role'] == 'evaluation' and tuple(subsections) != EVALUATION_SUBSECTIONS:
        errors.append('模型评价与展望只能依次包含模型优点、模型缺点、模型的推广与改进')
    if chapter['role'] == 'evaluation':
        from evaluation_contract import inspect_evaluation
        errors.extend(inspect_evaluation(text)['failures'])
    for caption in commands(text, ('caption',)):
        errors.extend(caption_errors(caption.argument))
    return errors


def audit_structure(manifest: dict, paper_root: Path) -> dict:
    errors = manifest_errors(manifest)
    from first_chapters import audit_source
    first = audit_source(manifest, paper_root)
    errors.extend(first['failures'])
    import sys
    shared_tools = Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'
    if str(shared_tools) not in sys.path:
        sys.path.insert(0, str(shared_tools))
    from model_selection import paper_gate
    try:
        errors.extend(paper_gate(paper_root.parent, manifest))
    except Exception as exc:
        errors.append('model selection: ' + str(exc))
    records = []
    for chapter in manifest.get('chapters', []):
        try:
            text = expand_fragment(paper_root, paper_root / chapter['tex_path'])
            failures = fragment_errors(text, chapter)
            headings = commands(text, HEADINGS)
            records.append({'chapter_id': chapter['chapter_id'],
                            'headings': [{'level': HEADINGS.index(h.name) + 1, 'title': h.argument} for h in headings]})
            errors.extend(f"{chapter['chapter_id']}: {e}" for e in failures)
        except (KeyError, OSError, ValueError, TypeError) as exc:
            errors.append(f"{chapter.get('chapter_id', '?')}: {exc}")
    return {'status': 'FAIL' if errors else 'PASS', 'failures': errors, 'chapters': records, 'first_chapters': first,
            'assurance': '仅验证源结构；实际 PDF 页数、起页、加粗与综合图位置另行核验'}


def require_structure(manifest: dict, paper_root: Path) -> None:
    report = audit_structure(manifest, paper_root)
    if report['failures']:
        raise ValueError('论文章节结构不合格：\n' + '\n'.join(report['failures']))


def caption_errors(caption: str) -> list[str]:
    """Early semantic/format warnings are hard errors; this does NOT measure a line."""
    errors = []
    if not caption.strip():
        errors.append('正式图表标题不能为空')
    if re.search(r'[。！？；]|\\\\|\\(?:newline|linebreak|par)\b', caption):
        errors.append('正式标题须为简短名词性短语，解释与条件移入正文或独立图注表注')
    if re.search(r'\\(?:tiny|small|scriptsize|footnotesize|fontsize|resizebox|scalebox|kern|hspace|makebox|mbox|parbox|hbox|vbox)\b', caption):
        errors.append('不得通过缩字、压距或越界盒子满足标题一行要求')
    return errors
