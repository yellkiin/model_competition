#!/usr/bin/env python3
"""Audit the generated appendix against paper, source, and submission facts."""
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
from typing import Any

from build_appendix import collect_attachment_inventory, load_json, project_path, sha256, internal_root, render_appendix_tex


PART_RE = re.compile(r"\\AppendixPart\{(\d+)\}\{([^{}]+)\}")
CODE_RE = re.compile(r"\\AppendixCodeFile(?:\[[^]]*\])?\{[^{}]*\}\{([^{}]+)\}\{([^{}]+)\}")


def audit_appendix(
    *,
    project_root: Path,
    paper_manifest_path: Path,
    supporting_manifest_path: Path,
    submission_dir: Path,
    appendix_manifest_path: Path,
    appendix_tex_path: Path,
    appendix_template_path: Path,
    main_tex_path: Path | None = None,
    runtime: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def add(code: str, ok: bool, **details: Any) -> None:
        row = {"code": code, "ok": ok, **details}
        checks.append(row)
        if not ok:
            failures.append(row)

    from workspace_context import shared_context, resource_path
    context = shared_context(project_root, runtime)
    template_path = (resource_path(project_root, appendix_template_path, context.runtime)
                     if context else project_path(project_root, appendix_template_path))
    paths = {
        "paper_manifest": project_path(project_root, paper_manifest_path),
        "supporting_manifest": project_path(project_root, supporting_manifest_path),
        "submission_dir": project_path(project_root, submission_dir),
        "appendix_manifest": project_path(project_root, appendix_manifest_path),
        "appendix_tex": project_path(project_root, appendix_tex_path),
        "appendix_template": template_path,
    }
    for name, path in paths.items():
        add(f"{name}_exists", path.is_dir() if name == "submission_dir" else path.is_file(), path=str(path))
    if failures:
        return {"status": "FAIL", "checks": checks, "failures": failures}

    paper = load_json(paths["paper_manifest"])
    support = load_json(paths["supporting_manifest"])
    manifest = load_json(paths["appendix_manifest"])
    add('appendix_runtime_current', runtime in ('codex', 'claude') and manifest.get('runtime') == runtime,
        requested=runtime, recorded=manifest.get('runtime'))
    paper_problems = [item for item in paper.get("chapters", []) if item.get("role") == "problem"]
    support_problems = support.get("questions", [])
    count = len(paper_problems)
    add("problem_counts_match", count == len(support_problems) == manifest.get("problem_count"),
        paper=count, supporting=len(support_problems), appendix=manifest.get("problem_count"))
    add("all_supporting_questions_complete", all(item.get("status") == "complete" for item in support_problems))
    add("appendix_part_count_is_n_plus_one", manifest.get("appendix_part_count") == count + 1)
    add("paper_manifest_hash_current", manifest.get("paper_manifest_sha256") == sha256(paths["paper_manifest"]))
    add("supporting_manifest_hash_current", manifest.get("supporting_manifest_sha256") == sha256(paths["supporting_manifest"]))
    add("generated_tex_hash_current", manifest.get("generated_tex_sha256") == sha256(paths["appendix_tex"]))

    from audit_supporting_materials import audit
    support_audit = audit(paths['supporting_manifest'], project_root, paths['submission_dir'], 'final', None, runtime)
    add('full_submission_inventory_and_sources_current', support_audit['status']=='PASS', failures=support_audit['failures'])
    actual_inventory = collect_attachment_inventory(paths["submission_dir"])
    add("attachment_inventory_matches_submission", manifest.get("attachments") == actual_inventory,
        expected_count=len(actual_inventory), actual_count=len(manifest.get("attachments", [])))

    build_path = internal_root(project_root) / "_支撑材料构建清单.json"
    build = load_json(build_path) if build_path.is_file() else {"entries": []}
    packaged = {item.get("source_path"): item for item in build.get("entries", []) if item.get("category") == "source_code"}
    bad_sources: list[dict[str, str]] = []
    for problem in manifest.get("problems", []):
        for item in problem.get("code", []):
            source = project_path(project_root, item.get("source_path", ""))
            package = packaged.get(item.get("source_path"))
            if not source.is_file() or sha256(source) != item.get("source_sha256"):
                bad_sources.append({"source": item.get("source_path", ""), "reason": "source_missing_or_changed"})
            elif not package or package.get("sha256") != item.get("source_sha256"):
                bad_sources.append({"source": item.get("source_path", ""), "reason": "submission_snapshot_mismatch"})
    add("appendix_code_matches_real_and_packaged_sources", not bad_sources, problems=bad_sources)

    tex = paths["appendix_tex"].read_text(encoding="utf-8-sig")
    add("generated_content_matches_inventory_and_code", tex == render_appendix_tex(actual_inventory, manifest["problems"]))
    parts = PART_RE.findall(tex)
    numbers = [int(item[0]) for item in parts]
    add("appendix_numbers_are_contiguous", numbers == list(range(1, count + 2)), actual=numbers)
    expected_titles = ["附件文件及内容"] + [f"问题{problem_number(index)}关键代码" for index in range(1, count + 1)]
    add("appendix_titles_are_dynamic", [item[1] for item in parts] == expected_titles,
        expected=expected_titles, actual=[item[1] for item in parts])
    add("attachment_rows_cover_inventory", tex.count(r"\AppendixAttachmentRow") == len(actual_inventory))
    code_calls = CODE_RE.findall(tex)
    selected_count = sum(len(item.get("code", [])) for item in manifest.get("problems", []))
    add("all_selected_code_is_inputminted_through_template", len(code_calls) == selected_count,
        expected=selected_count, actual=len(code_calls))
    add("generated_tex_has_no_raw_minted_style", "\\usepackage{minted}" not in tex and "\\begin{minted}" not in tex)

    template = paths["appendix_template"].read_text(encoding="utf-8-sig")
    required_tokens = [
        r"\usepackage{minted}", r"\usemintedstyle{lovelace}", "linenos", "breaklines",
        "breakanywhere", "autogobble", "frame=leftline", "framerule=0.55pt", r"\inputminted",
        r"\AppendixAttachmentTableBegin", r"\AppendixCodeFile",
        r"\AppendixPygmentsPalette", "8B4E8F", "4F8A55", "A06D20",
        "AppendixCodePageFrame", r"\AppendixZebraLine", "Consolas",
        "overlay={", "line width=0.5pt", "frame.north west", "frame.south west",
        r"fontsize=\fontsize{10.2pt}{13.5pt}\selectfont", "framerule=0.55pt",
        "leftrule=0pt", "rightrule=0pt", "sharp corners",
        "top=1.5pt", "bottom=1.5pt", "FFFFFF", "F8F8F8", "63B96C",
    ]
    missing_tokens = [token for token in required_tokens if token not in template]
    add("appendix_template_owns_minted_light_style", not missing_tokens, missing=missing_tokens)

    if main_tex_path is not None:
        main = project_path(project_root, main_tex_path)
        main_text = main.read_text(encoding="utf-8-sig") if main.is_file() else ""
        add("main_tex_calls_unified_template", r"\input{附录模板.tex}" in main_text)
        add("main_tex_calls_generated_appendix", r"\input{章节内容/99_附录.generated.tex}" in main_text)
        copied_template = main.parent / "附录模板.tex"
        add(
            "paper_uses_current_unified_template_copy",
            copied_template.is_file() and sha256(copied_template) == sha256(paths["appendix_template"]),
            copied=str(copied_template),
        )

    return {"status": "PASS" if not failures else "FAIL", "checks": checks, "failures": failures}


def problem_number(value: int) -> str:
    from build_appendix import chinese_number
    return chinese_number(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--paper-manifest", type=Path, default=Path("论文/论文输入.json"))
    parser.add_argument("--supporting-manifest", type=Path, default=Path("求解/支撑材料清单.json"))
    parser.add_argument("--submission-dir", type=Path, default=Path("提交附件"))
    parser.add_argument("--appendix-manifest", type=Path, default=Path("求解/附录清单.json"))
    parser.add_argument("--appendix-tex", type=Path, default=Path("论文/章节内容/99_附录.generated.tex"))
    parser.add_argument("--appendix-template", type=Path, default=Path("华为杯_论文规范模板/章节模板/附录模板.tex"))
    parser.add_argument("--main-tex", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--runtime", choices=("codex", "claude"))
    args = parser.parse_args()
    result = audit_appendix(
        project_root=args.project_root,
        paper_manifest_path=args.paper_manifest,
        supporting_manifest_path=args.supporting_manifest,
        submission_dir=args.submission_dir,
        appendix_manifest_path=args.appendix_manifest,
        appendix_tex_path=args.appendix_tex,
        appendix_template_path=args.appendix_template,
        main_tex_path=args.main_tex,
        runtime=args.runtime,
    )
    if args.report:
        report = project_path(args.project_root.resolve(), args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
