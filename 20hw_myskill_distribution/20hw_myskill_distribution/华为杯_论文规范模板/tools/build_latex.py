#!/usr/bin/env python3
"""Build the single LaTeX paper entry point from a TeX-only manifest.

The manifest is metadata and ordering; chapter prose lives only in the
referenced ``.tex`` fragments.  This tool deliberately rejects Markdown
chapter paths and inline chapter content.
"""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import json
import re
import shutil
from pathlib import Path

from audit_abstract import require_abstract_pass
from audit_citations import require_source_pass as require_citations_pass
from ai_disclosure import ensure_evidence_record, AI_TEX_HOOK
from build_appendix import build_appendix
from paper_contract import manifest_errors, require_structure


ROLES = {"preliminary", "problem", "evaluation", "references"}
APPENDIX_STYLE_INPUT = "附录模板.tex"
APPENDIX_GENERATED_INPUT = "章节内容/99_附录.generated.tex"
IDENTITY_RE = re.compile(r"学校|学院|实验室|参赛队号|队员姓名|指导教师|学号|邮箱|C:\\Users\\|school|student|team|member|advisor", re.I)


def tex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def title_underlines(text: str, width: int = 18) -> str:
    """Render the paper title in at most two centered underlined lines.

    The production title area is intentionally compact.  An 18-character
    segment keeps the current competition title within two lines while still
    allowing shorter titles to remain on one line.
    """
    segments = [text[index:index + width] for index in range(0, len(text), width)] or [text]
    if len(segments) > 2:
        # Never emit a third explicit title paragraph.  For unusually long
        # titles, balance the complete string before TeX lays out the two
        # resulting lines.
        midpoint = width if len(text) <= 2 * width + 2 else (len(text) + 1) // 2
        segments = [text[:midpoint], text[midpoint:]]
    return r"\par".join(rf"\HuaweiTitleUnderline{{{tex_escape(segment)}}}" for segment in segments)


def relative_file(root: Path, raw: str, *, label: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} 必须位于论文工作目录内: {raw}") from exc
    if candidate.suffix.lower() != ".tex":
        raise ValueError(f"{label} 必须使用 .tex: {raw}")
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} 不存在: {candidate}")
    return candidate


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    required = {"title", "keywords", "abstract_tex_path", "abstract_evidence_path", "references_evidence_path", "first_chapters_evidence_path", "first_chapters_review_path", "chapters"}
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"manifest 缺少字段: {', '.join(missing)}")
    forbidden = {"abstract", "content", "content_file"} & set(data)
    if forbidden:
        raise ValueError(f"LaTeX-first manifest 禁止字段: {', '.join(sorted(forbidden))}")
    if not isinstance(data["keywords"], list) or not 3 <= len(data["keywords"]) <= 5:
        raise ValueError("关键词数量必须为 3–5 个")
    if any(not str(item).strip() for item in data["keywords"]):
        raise ValueError("关键词不能包含空字符串")
    normalized_keywords = [re.sub(r"[\s\-_]+", "", str(item)).casefold() for item in data["keywords"]]
    if len(set(normalized_keywords)) != len(normalized_keywords):
        raise ValueError("关键词不得重复")
    if not isinstance(data["chapters"], list) or not data["chapters"]:
        raise ValueError("chapters 不能为空")
    for index, chapter in enumerate(data["chapters"], start=1):
        required_chapter = {"chapter_id", "title", "role", "order", "tex_path"}
        missing_chapter = sorted(required_chapter - set(chapter))
        if missing_chapter:
            raise ValueError(f"第 {index} 个章节缺少字段: {', '.join(missing_chapter)}")
        if chapter["role"] not in ROLES:
            if chapter["role"] == "appendix":
                raise ValueError("附录已改由统一附录生成器负责，不得在 chapters 中手写 role=appendix")
            raise ValueError(f"章节角色无效: {chapter['role']}")
        if "content_file" in chapter or "content" in chapter:
            raise ValueError(f"章节 {chapter['chapter_id']} 仍使用旧 content/content_file 字段")
        if str(chapter["tex_path"]).lower().endswith(".md"):
            raise ValueError(f"章节 {chapter['chapter_id']} 禁止使用 Markdown 源文件")
    orders = [int(chapter["order"]) for chapter in data["chapters"]]
    if orders != sorted(orders) or len(set(orders)) != len(orders):
        raise ValueError("章节 order 必须严格递增且不重复")
    errors = manifest_errors(data)
    if errors:
        raise ValueError("\n".join(errors))
    return data


def check_fragment(path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if "\\documentclass" in text or "\\begin{document}" in text or "\\end{document}" in text:
        raise ValueError(f"章节 fragment 不得包含 document 级结构: {path}")
    if re.search(r"(?m)^\s*#{1,6}\s", text) or re.search(r"(?m)^\s*\|[^|]+\|", text) or "![" in text:
        raise ValueError(f"章节 fragment 残留 Markdown 语法: {path}")


def build_main(
    manifest: dict,
    root: Path,
    *,
    include_appendix: bool = True,
) -> tuple[str, list[str]]:
    if (root.parent / '工作区清单.json').is_file():
        import sys
        shared_tools = Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'
        if str(shared_tools) not in sys.path:
            sys.path.insert(0, str(shared_tools))
        from model_selection import publish
        publish(root.parent)
    require_structure(manifest, root)
    abstract = relative_file(root, manifest["abstract_tex_path"], label="abstract_tex_path")
    abstract_input = abstract.relative_to(root).as_posix()
    chapter_inputs: list[str] = []
    for chapter in manifest["chapters"]:
        fragment = relative_file(root, str(chapter["tex_path"]), label=f"章节 {chapter['chapter_id']}")
        check_fragment(fragment)
        chapter_inputs.append(fragment.relative_to(root).as_posix())
    if include_appendix:
        appendix = relative_file(root, APPENDIX_GENERATED_INPUT, label="自动附录")
        check_fragment(appendix)
    inputs = ([APPENDIX_STYLE_INPUT] if include_appendix else []) + [abstract_input] + chapter_inputs
    if include_appendix:
        inputs.append(APPENDIX_GENERATED_INPUT)

    raw_title = str(manifest["title"]).strip()
    title = tex_escape(raw_title)
    title_lines = manifest.get('title_lines')
    if title_lines is not None:
        if not isinstance(title_lines,list) or not 1 <= len(title_lines) <= 2 or ''.join(title_lines) != raw_title:
            raise ValueError('title_lines 必须为拼接后等于 title 的一至两行')
        display_title = r"\par".join(rf"\HuaweiTitleUnderline{{{tex_escape(line)}}}" for line in title_lines)
    else:
        display_title = title_underlines(raw_title)
    contest_edition = manifest.get('contest_edition', '二十三')
    if not re.fullmatch('[一二三四五六七八九十百]+',contest_edition):
        raise ValueError('contest_edition 必须使用中文数字')
    keywords = r"\quad ".join(tex_escape(str(item).strip()) for item in manifest["keywords"])
    lines = [
        "% !TEX program = xelatex",
        "% !TEX option = -shell-escape",
        "% Generated by tools/build_latex.py; edit chapter fragments, not Markdown.",
        r"\documentclass[bwprint]{gmcmthesis}",
        r"\geometry{top=25mm,bottom=25mm,left=25mm,right=25mm,headsep=15mm}",
        r"\renewcommand{\baselinestretch}{1.0}",
        r"\normalsize",
        rf"\def\GMCMEvaluationSection{{{next(c['order'] for c in manifest['chapters'] if c['role'] == 'evaluation')}}}",
        # Keep bookmarks enabled, but use plain numeric values for the
        # subsection counters so hyperref can serialize them without the
        # class's spacing commands.
        r"\hypersetup{hidelinks}",
        r"\renewcommand{\thesubsection}{\arabic{section}.\arabic{subsection}}",
        r"\renewcommand{\thesubsubsection}{\thesubsection.\arabic{subsubsection}}",
        r"\pagestyle{plain}",
        r"\usepackage[framemethod=TikZ]{mdframed}",
        r"\usepackage{subfig}",
        r"\usepackage{siunitx}",
        r"\usepackage{colortbl}",
        r"\usepackage{array}",
        r"\usepackage{tabularx}",
        r"\usepackage{longtable}",
        AI_TEX_HOOK,
        *([rf"\input{{{APPENDIX_STYLE_INPUT}}}"] if include_appendix else []),
        r"\newcommand{\codeid}[1]{\nolinkurl{#1}}",
        r"\usepackage{booktabs}",
        r"\usepackage{tikz}",
        r"\usetikzlibrary{arrows.meta,positioning,fit,calc,shapes.geometric,shapes.arrows}",
        r"\makeatletter",
        r"\newcommand{\HuaweiLabel}[1]{{\lishu\fontsize{18pt}{24pt}\selectfont #1}}",
        r"\newcommand{\HuaweiBodyFont}{\songti\fontsize{12pt}{18pt}\selectfont}",
        r"\newcommand{\HuaweiTitleUnderline}[1]{%",
        r"  \begingroup",
        r"  \renewcommand{\ULthickness}{1.2pt}%",
        r"  \setlength{\ULdepth}{4pt}%",
        r"  \uline{#1}%",
        r"  \endgroup",
        r"}",
        r"\newcommand{\HuaweiPaperTitle}[1]{%",
        r"  \begin{minipage}[t]{.9\textwidth}\centering",
        r"    \HuaweiLabel{题\quad 目：}\hspace{0.4em}{\zihao{3}\heiti #1}%",
        r"  \end{minipage}%",
        r"}",
        r"\newcommand{\HuaweiTitlePage}{%",
        r"  \clearpage\thispagestyle{plain}\setcounter{page}{1}%",
        rf"  \GMCMContestTitle{{{contest_edition}}}",
        r"  \vspace{8mm}\noindent",
        r"  \begin{center}",
        rf"    \HuaweiPaperTitle{{{display_title}}}",
        r"  \end{center}",
        r"  \vspace{3mm}",
        r"}",
        r"\renewenvironment{abstract}{%",
        r"  \begin{center}\GMCMAbstractHeading\end{center}\HuaweiBodyFont\quotation",
        r"}{%",
        # This break follows the complete abstract.  It does not constrain
        # the abstract to page one: it may flow naturally onto page two.
        r"  \endquotation\clearpage",
        r"}",
        r"\renewcommand{\keywords}[1]{\par\vspace{1ex}{\noindent\HuaweiLabel{关键词：}}~{\HuaweiBodyFont #1}\par}",
        r"\makeatother",
        rf"\title{{{title}}}",
        "",
        r"\begin{document}",
        r"\HuaweiTitlePage",
        r"\begin{abstract}",
        rf"\input{{{abstract_input}}}",
        rf"\keywords{{{keywords}}}",
        r"\end{abstract}",
        # Generate a linked three-level TOC between front matter and body.
        r"\setcounter{tocdepth}{3}",
        r"\clearpage",
        r"\maketoc",
        r"\clearpage",
        # Match the confirmed Word interpretation of small-four Songti with
        # an 18 pt single-line box.  This is the production body font, not a
        # page-count adjustment.
        r"\HuaweiBodyFont",
    ]
    for chapter, input_path in zip(manifest["chapters"], chapter_inputs, strict=True):
        if chapter["role"] == "references":
            lines.append(r"\clearpage")
        lines.append(rf"\input{{{input_path}}}")
        lines.append(rf"\GMCMChapterEnd{{{chapter['order']}}}")
    if include_appendix:
        lines.extend([r"\clearpage", rf"\input{{{APPENDIX_GENERATED_INPUT}}}"])
    lines.extend([r"\end{document}", ""])
    return "\n".join(lines), inputs


def copy_assets(template_dir: Path, output_dir: Path, *, include_appendix: bool = True, legacy_bibliography: bool = False) -> None:
    for name in ("gmcmthesis.cls", "gmcm.bst", "gmcm-title.sty", "gmcm-layout.sty"):
        source = template_dir / name
        if source.is_file():
            shutil.copy2(source, output_dir / name)
    # A project bibliography is scientific source, never a generated template asset.
    bibliography = output_dir / 'reference.bib'
    if legacy_bibliography and not bibliography.exists() and (template_dir / 'reference.bib').is_file():
        shutil.copy2(template_dir / 'reference.bib', bibliography)
    if include_appendix:
        appendix_template = template_dir / "章节模板" / "附录模板.tex"
        if not appendix_template.is_file():
            raise FileNotFoundError(f"统一附录模板不存在: {appendix_template}")
        shutil.copy2(appendix_template, output_dir / APPENDIX_STYLE_INPUT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--runtime", choices=("codex", "claude"))
    parser.add_argument(
        "--draft-without-appendix",
        action="store_true",
        help="仅供正文草稿编译；final audit 会拒绝缺失统一附录的论文",
    )
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    root = manifest_path.parent
    project_root = args.project_root.resolve() if args.project_root else root.parent.resolve()
    manifest = load_manifest(manifest_path)
    require_abstract_pass(manifest_path)
    ensure_evidence_record(manifest_path)
    require_citations_pass(manifest_path)
    output = args.output.resolve()
    if output.parent != root:
        raise ValueError("论文主文件必须与论文输入 manifest 位于同一目录")
    appendix_snapshot = None
    if not args.draft_without_appendix:
        appendix_snapshot = build_appendix(
            project_root=project_root,
            paper_manifest_path=manifest_path.relative_to(project_root),
            supporting_manifest_path=Path("求解/支撑材料清单.json"),
            submission_dir=Path("提交附件"),
            output_tex=Path("论文") / APPENDIX_GENERATED_INPUT,
            output_manifest=Path("求解/附录清单.json"),
            runtime=args.runtime,
        )
    main_text, inputs = build_main(manifest, root, include_appendix=not args.draft_without_appendix)
    output.parent.mkdir(parents=True, exist_ok=True)
    from workspace_context import shared_context
    context = shared_context(project_root, args.runtime)
    if context:
        if args.template_dir.resolve() != context.template_root / '华为杯_论文规范模板':
            raise ValueError('论文模板路径与工作区关联不一致')
        context.write_path(output)
    copy_assets(args.template_dir.resolve(), output.parent, include_appendix=not args.draft_without_appendix,
                legacy_bibliography=context is None)
    output.write_text(main_text, encoding="utf-8")
    out_manifest = args.manifest_out.resolve() if args.manifest_out else output.with_suffix(".inputs.json")
    out_manifest.write_text(json.dumps({
        "main": output.name,
        "inputs": inputs,
        "title": manifest["title"],
        "appendix_manifest": "../求解/附录清单.json" if appendix_snapshot else None,
        "requires_shell_escape": bool(appendix_snapshot),
        "pygments_style": "lovelace" if appendix_snapshot else None,
        "pygments_palette": "appendix_academic_light" if appendix_snapshot else None,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "inputs": inputs, "manifest": str(out_manifest)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
