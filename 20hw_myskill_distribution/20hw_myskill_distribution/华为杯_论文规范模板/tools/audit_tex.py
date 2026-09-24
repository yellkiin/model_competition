#!/usr/bin/env python3
r"""Audit the TeX-only paper source and its generated ``\input`` chain."""
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
from pathlib import Path

from ai_disclosure import AI_TEX_HOOK
from audit_abstract import audit_abstract_manifest
from audit_citations import audit_source as audit_citation_source
from audit_appendix import audit_appendix
from paper_contract import audit_structure, caption_errors, commands, strip_comments


INPUT_RE = re.compile(r"\\input\s*\{([^{}]+)\}")
INPUTMINTED_RE = re.compile(r"\\inputminted(?:\[[^]]*\])?\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
APPENDIX_CODE_RE = re.compile(r"\\AppendixCodeFile(?:\[[^]]*\])?\s*\{[^{}]*\}\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^]]*\])?\s*\{([^{}]+)\}")
BEGIN_RE = re.compile(r"\\begin\s*\{([^{}]+)\}")
END_RE = re.compile(r"\\end\s*\{([^{}]+)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref)\s*\{([^{}]+)\}")
TOC_DEPTH_RE = re.compile(r"\\setcounter\s*\{tocdepth\}\s*\{\s*(\d+)\s*\}")
FORBIDDEN_UNICODE_MATH = set("ᐟ¹²³⁴⁵⁶⁷⁸⁹⁰⁻⁺Σ∑∫√∈∉≤≥≈μσπγδελρτφω̃ᵀĉŷ")


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def inside(root: Path, raw: str) -> Path:
    path = (root / raw).resolve()
    path.relative_to(root.resolve())
    return path


def remove_comments(text: str) -> str:
    return strip_comments(text)


def brace_balance(text: str) -> int:
    balance = 0
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
        elif char == "{":
            balance += 1
        elif char == "}":
            balance -= 1
    return balance


def expand_tex_inputs(root: Path, roots: list[Path]) -> tuple[list[Path], list[str]]:
    """Return manifest fragments plus every nested TeX input exactly once."""
    ordered: list[Path] = []
    errors: list[str] = []
    visited: set[Path] = set()

    def visit(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        ordered.append(resolved)
        text = resolved.read_text(encoding="utf-8-sig")
        for raw in INPUT_RE.findall(remove_comments(text)):
            candidates = [(root / raw).resolve(), (resolved.parent / raw).resolve()]
            nested = next((item for item in candidates if item.is_file()), candidates[0])
            try:
                nested.relative_to(root.resolve())
            except (ValueError, OSError):
                errors.append(f"{resolved}: nested input escapes paper root: {raw}")
                continue
            if nested.suffix.lower() != ".tex":
                errors.append(f"{resolved}: nested input is not .tex: {raw}")
            elif not nested.is_file():
                errors.append(f"{resolved}: nested input does not exist: {raw}")
            else:
                visit(nested)

    for path in roots:
        visit(path)
    return ordered, errors


def audit(manifest_path: Path, main_path: Path, runtime: str | None = None) -> dict:
    root = manifest_path.parent.resolve()
    project_root = root.parent
    manifest = read_manifest(manifest_path)
    checks: list[dict] = []
    failures: list[dict] = []

    def add(code: str, ok: bool, **details) -> None:
        item = {"code": code, "ok": ok, **details}
        checks.append(item)
        if not ok:
            failures.append(item)

    structure = audit_structure(manifest, root)
    add('fixed_chapter_structure', structure['status'] == 'PASS', audit=structure)
    citation_report = audit_citation_source(manifest_path)
    add('body_citation_source_gate', citation_report['status'] == 'PASS', audit=citation_report)

    abstract_report = audit_abstract_manifest(manifest_path)
    add(
        "abstract_content_gate",
        abstract_report["status"] == "PASS",
        audit=abstract_report,
        message="摘要须先通过六要素、逐问闭环、数字单位、加粗、关键词与内容边界审计。",
    )

    main_text = main_path.read_text(encoding="utf-8-sig") if main_path.is_file() else ""
    add('fixed_ai_disclosure_generation', remove_comments(main_text).count(AI_TEX_HOOK) == 1)
    add("main_exists", main_path.is_file(), path=str(main_path))
    if not main_path.is_file():
        return {"status": "FAIL", "manifest": str(manifest_path), "checks": checks, "failures": failures}
    add(
        "minted_shell_escape_declared",
        "% !TEX option = -shell-escape" in main_text,
        message="最终附录使用 minted；XeLaTeX 编译必须显式启用 -shell-escape。",
    )

    expected = ["附录模板.tex", str(manifest["abstract_tex_path"]).replace("\\", "/")]
    for chapter in manifest.get("chapters", []):
        expected.append(str(chapter["tex_path"]).replace("\\", "/"))
    expected.append("章节内容/99_附录.generated.tex")
    actual = INPUT_RE.findall(remove_comments(main_text))
    add("input_order_matches_manifest", actual == expected, expected=expected, actual=actual)
    add("main_has_no_markdown_input", not any(path.lower().endswith(".md") for path in actual), actual=actual)

    # The TOC is a production contract: it must follow the complete
    # abstract/keywords block and precede the first body input.
    clean_main = remove_comments(main_text)
    toc_match = re.search(r"\\maketoc\b", clean_main)
    abstract_end = clean_main.find(r"\end{abstract}")
    after_abstract = clean_main[abstract_end + len(r"\end{abstract}"):] if abstract_end >= 0 else ""
    first_input_match = re.search(r"\\input\s*\{", after_abstract)
    first_input_pos = abstract_end + len(r"\end{abstract}") + first_input_match.start() if abstract_end >= 0 and first_input_match else -1
    toc_order_ok = bool(toc_match and abstract_end >= 0 and first_input_pos >= 0 and abstract_end < toc_match.start() < first_input_pos)
    add("toc_command_order", toc_order_ok, maketoc_position=toc_match.start() if toc_match else None,
        abstract_end=abstract_end, first_body_input=first_input_pos)
    depth_values = [int(value) for value in TOC_DEPTH_RE.findall(clean_main)]
    add("toc_depth_is_three", depth_values == [3], values=depth_values)
    add("toc_hyperlinks_enabled", bool(re.search(r"\\hypersetup\s*\{[^}]*hidelinks", clean_main, re.S)),
        message="hyperref is configured for linked TOC/bookmarks")
    keyword_commands = re.findall(r"\\keywords\s*\{", clean_main)
    add(
        "keyword_command_is_unique",
        len(keyword_commands) == 1,
        actual=len(keyword_commands),
        required=1,
        message="关键词只能由主生成器输出一次；摘要 fragment 不得自行写关键词。",
    )

    fragment_paths: list[Path] = []
    fragment_errors: list[str] = []
    for raw in expected:
        try:
            path = inside(root, raw)
        except (ValueError, OSError) as exc:
            fragment_errors.append(f"{raw}: {exc}")
            continue
        if path.suffix.lower() != ".tex":
            fragment_errors.append(f"{raw}: suffix is not .tex")
        elif not path.is_file():
            fragment_errors.append(f"{raw}: file does not exist")
        else:
            fragment_paths.append(path)
    add("all_manifest_fragments_exist_and_are_tex", not fragment_errors, errors=fragment_errors)

    audit_paths, nested_input_errors = expand_tex_inputs(root, fragment_paths)
    add("nested_tex_inputs_resolve", not nested_input_errors, errors=nested_input_errors,
        count=max(0, len(audit_paths) - len(fragment_paths)))

    markdown_residue: list[str] = []
    document_commands: list[str] = []
    unbalanced: list[str] = []
    environment_errors: list[str] = []
    all_text = main_text
    for path in audit_paths:
        text = path.read_text(encoding="utf-8-sig")
        all_text += "\n" + text
        # Notes stay outside caption arguments. Physical one-line checks are made
        # by the engine and final PDF auditor, not this lexical preflight.
        try:
            bad_captions = [{'caption': c.argument, 'errors': caption_errors(c.argument)}
                            for c in commands(text, ('caption',)) if caption_errors(c.argument)]
            add('caption_short_title:' + path.name, not bad_captions, failures=bad_captions)
        except ValueError as exc:
            add('caption_parse:' + path.name, False, error=str(exc))
        if re.search(r"(?m)^\s*#{1,6}\s", text) or re.search(r"(?m)^\s*\|[^|]+\|", text) or "![" in text or chr(96) * 3 in text:
            markdown_residue.append(str(path))
        for command in ("\\documentclass", "\\begin{document}", "\\end{document}"):
            if command in text:
                document_commands.append(f"{path}: {command}")
        if brace_balance(remove_comments(text)) != 0:
            unbalanced.append(str(path))
        stack: list[str] = []
        cleaned = remove_comments(text)
        for match in re.finditer(r"\\begin\s*\{([^{}]+)\}|\\end\s*\{([^{}]+)\}", cleaned):
            begin, end = match.groups()
            if begin:
                stack.append(begin)
            elif not stack or stack.pop() != end:
                environment_errors.append(f"{path}: mismatched \\end{{{end}}}")
        environment_errors.extend(f"{path}: unclosed {env}" for env in stack)
    add("fragments_are_real_latex", not markdown_residue and not document_commands, markdown_residue=markdown_residue, document_commands=document_commands)
    add("fragment_braces_balanced", not unbalanced, files=unbalanced)
    add("fragment_environments_balanced", not environment_errors, errors=environment_errors)

    # After XeLaTeX, inspect the generated auxiliary file when it exists.  A
    # pre-compilation audit remains useful and reports this check as pending
    # rather than manufacturing a failure from a missing build artifact.
    toc_path = main_path.with_suffix(".toc")
    if toc_path.is_file():
        toc_text = toc_path.read_text(encoding="utf-8", errors="replace")
        toc_levels = {
            level: bool(re.search(rf"\\contentsline\s*\{{{level}\}}", toc_text))
            for level in ("section", "subsection", "subsubsection")
        }
        expected_levels = {
            level: bool(re.search(rf"\\{level}\*?\s*(?:\[[^]]*\])?\s*\{{", remove_comments(all_text)))
            for level in toc_levels
        }
        toc_content_ok = all((not expected_levels[level]) or toc_levels[level] for level in toc_levels)
        add("toc_auxiliary_content", toc_content_ok, path=str(toc_path), expected=expected_levels, found=toc_levels)
    else:
        add("toc_auxiliary_content", True, available=False, path=str(toc_path),
            message=".toc not present; run XeLaTeX before auxiliary-content validation")

    missing_graphics: list[str] = []
    for raw in GRAPHICS_RE.findall(all_text):
        try:
            # The paper source may reference real result figures stored in
            # the sibling 求解/ tree.  Inputs remain confined to 论文/;
            # graphics are allowed anywhere inside the project root.
            path = (root / raw).resolve()
            path.relative_to(project_root.resolve())
        except (ValueError, OSError):
            missing_graphics.append(raw)
            continue
        if not path.is_file():
            missing_graphics.append(raw)
    add("graphics_paths_exist", not missing_graphics, missing=missing_graphics)

    minted_sources: list[dict] = []
    missing_minted_sources: list[str] = []
    source_calls = [item for item in INPUTMINTED_RE.findall(all_text) if not item[1].startswith("#")]
    source_calls.extend(APPENDIX_CODE_RE.findall(all_text))
    for language, raw in source_calls:
        try:
            path = (root / raw).resolve()
            path.relative_to(project_root.resolve())
            exists = path.is_file()
        except (ValueError, OSError):
            exists = False
            path = root / raw
        minted_sources.append({"language": language, "path": raw})
        if not exists:
            missing_minted_sources.append(raw)
    add("inputminted_sources_exist_inside_project", not missing_minted_sources,
        sources=minted_sources, missing=missing_minted_sources)
    add("appendix_uses_inputminted", bool(minted_sources), count=len(minted_sources))

    identity_hits = sorted(set(re.findall(r"学校|学院|实验室|参赛队号|队员姓名|指导教师|学号|邮箱|C:\\Users\\", all_text, re.I)))
    add("anonymous_source", not identity_hits, matches=identity_hits)
    add("no_markdown_chapter_sources", not any(path.suffix.lower() == ".md" for path in audit_paths), files=[str(path) for path in audit_paths if path.suffix.lower() == ".md"])

    labels = LABEL_RE.findall(remove_comments(all_text))
    duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
    references = REF_RE.findall(remove_comments(all_text))
    missing_labels = sorted(set(references) - set(labels))
    add("labels_are_unique", not duplicate_labels, duplicates=duplicate_labels)
    add("references_resolve", not missing_labels, missing=missing_labels)

    unicode_math_hits = sorted(set(all_text) & FORBIDDEN_UNICODE_MATH)
    add(
        "math_uses_latex_commands",
        not unicode_math_hits,
        characters=unicode_math_hits,
        message="Unicode 上下标/运算符易落入西文字体并造成缺字；请改用 LaTeX 数学命令。",
    )

    italic_commands = sorted(set(re.findall(r"\\(?:itshape|textit|emph)\b", remove_comments(all_text))))
    add("no_explicit_body_italic", not italic_commands, commands=italic_commands)

    try:
        from audit_diagram_workflow import sidecar, load
        if runtime is None:
            runtime = load(sidecar(project_root / '求解/视觉计划.json'))['runtime']
        appendix_report = audit_appendix(
            project_root=project_root,
            paper_manifest_path=manifest_path.relative_to(project_root),
            supporting_manifest_path=Path("求解/支撑材料清单.json"),
            submission_dir=Path("提交附件"),
            appendix_manifest_path=Path("求解/附录清单.json"),
            appendix_tex_path=Path("论文/章节内容/99_附录.generated.tex"),
            appendix_template_path=Path("华为杯_论文规范模板/章节模板/附录模板.tex"),
            main_tex_path=main_path.relative_to(project_root),
            runtime=runtime,
        )
        add("dynamic_appendix_gate", appendix_report["status"] == "PASS", audit=appendix_report)
    except Exception as exc:
        add("dynamic_appendix_gate", False, error=str(exc))

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'))
        from audit_diagram_workflow import audit as audit_diagrams, sidecar, load
        plan = project_root / '求解/视觉计划.json'
        if runtime is None:
            runtime = load(sidecar(plan))['runtime']
        report = audit_diagrams(plan, 'tex', project_root, runtime, main_path, paper_manifest=manifest_path)
        add('question_comprehensive_diagram_gate', report['status'] == 'PASS', audit=report)
    except Exception as exc:
        add('question_comprehensive_diagram_gate', False, error=str(exc))
    return {"status": "PASS" if not failures else "FAIL", "manifest": str(manifest_path), "main": str(main_path), "checks": checks, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--runtime", choices=("codex", "claude"))
    args = parser.parse_args()
    result = audit(args.manifest.resolve(), args.main.resolve(), args.runtime)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
