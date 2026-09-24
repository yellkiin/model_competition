#!/usr/bin/env python3
"""Generate the Huawei Cup appendix from final submission facts and real source code.

The generated TeX is intentionally small: all visual decisions live in
``章节模板/附录模板.tex``.  This tool only selects verifiable content and emits
calls to that template's public macros.
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
import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'))
from supporting_contract import internal_root, attachment_summary, structure_errors


BUILD_MANIFEST_NAME = "_支撑材料构建清单.json"
APPENDIX_MANIFEST_VERSION = "1.0"
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".m": "matlab",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".r": "r",
    ".jl": "julia",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".sh": "bash",
    ".ps1": "powershell",
}
KEY_CODE_TERMS = (
    "preprocess", "clean", "feature", "model", "train", "fit", "predict",
    "solve", "solver", "optimiz", "objective", "loss", "constraint",
    "search", "calibrat", "evaluate", "validate", "decision", "simulate",
    "algorithm", "core", "main", "预处理", "特征", "模型", "训练", "预测",
    "求解", "优化", "目标", "约束", "搜索", "校准", "验证", "决策", "仿真",
)
IDENTITY_OR_ABSOLUTE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\Users\\|/Users/|/home/)[^\s\"']+|学校名称|参赛队号|队员姓名|指导教师"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(project_root: Path, raw: str | Path) -> Path:
    from workspace_context import bounded
    return bounded(project_root, raw)


def tex_escape(text: object) -> str:
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
    return "".join(replacements.get(char, char) for char in str(text))


def tex_file_argument(path: str) -> str:
    normalized = path.replace("\\", "/")
    if any(char in normalized for char in "{}%#~^"):
        raise ValueError(f"代码路径含 LaTeX/minted 不安全字符，请重命名: {path}")
    return normalized


def chinese_number(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value < 1:
        raise ValueError("问题编号必须从 1 开始")
    if value < 10:
        return digits[value]
    if value == 10:
        return "十"
    if value < 20:
        return "十" + digits[value % 10]
    if value < 100:
        return digits[value // 10] + "十" + (digits[value % 10] if value % 10 else "")
    return str(value)


def collect_attachment_inventory(submission_dir: Path) -> list[dict[str, Any]]:
    project_root = submission_dir.resolve().parent
    build = load_json(internal_root(project_root) / BUILD_MANIFEST_NAME)
    manifest = load_json(project_path(project_root, build['source_manifest']))
    errors = structure_errors(submission_dir, manifest)
    if errors: raise ValueError('提交目录结构不符：' + '; '.join(errors))
    return attachment_summary(manifest, submission_dir)


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8-sig", errors="replace").splitlines())


def keyword_score(text: str) -> int:
    lowered = text.casefold()
    return sum(1 for term in KEY_CODE_TERMS if term.casefold() in lowered)


def merge_ranges(ranges: list[tuple[int, int]], limit: int) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        start = max(1, start)
        end = max(start, end)
        if merged and start <= merged[-1][1] + 3:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    selected: list[tuple[int, int]] = []
    used = 0
    for start, end in merged:
        available = limit - used
        if available <= 0:
            break
        end = min(end, start + available - 1)
        selected.append((start, end))
        used += end - start + 1
    return selected


def python_key_ranges(path: Path, limit: int = 260) -> list[tuple[int, int]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    if len(lines) <= 150:
        return [(1, max(1, len(lines)))]
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return generic_key_ranges(lines, limit)
    candidates: list[tuple[int, int, int]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = min([node.lineno] + [item.lineno for item in getattr(node, "decorator_list", [])])
        end = int(getattr(node, "end_lineno", node.lineno))
        name = getattr(node, "name", "")
        score = keyword_score(name) * 100 + (30 if isinstance(node, ast.ClassDef) else 10)
        score += min(20, end - start + 1)
        candidates.append((score, start, end))
    if not candidates:
        return generic_key_ranges(lines, limit)
    chosen: list[tuple[int, int]] = []
    used = 0
    for _, start, end in sorted(candidates, key=lambda item: (-item[0], item[1])):
        span = min(end - start + 1, 150)
        if used >= limit:
            break
        span = min(span, limit - used)
        chosen.append((start, start + span - 1))
        used += span
        if len(chosen) >= 5:
            break
    return merge_ranges(chosen, limit)


def generic_key_ranges(lines: list[str], limit: int = 240) -> list[tuple[int, int]]:
    if len(lines) <= 180:
        return [(1, max(1, len(lines)))]
    hits = [index for index, value in enumerate(lines, start=1) if keyword_score(value)]
    if not hits:
        return [(1, min(len(lines), limit))]
    windows = [(max(1, line - 12), min(len(lines), line + 28)) for line in hits]
    return merge_ranges(windows, limit)


def validate_source_text(path: Path, firstline: int, lastline: int) -> None:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    excerpt = "\n".join(lines[firstline - 1:lastline])
    hit = IDENTITY_OR_ABSOLUTE_PATH_RE.search(excerpt)
    if hit:
        raise ValueError(f"附录代码含身份信息或绝对用户路径 ({hit.group(0)}): {path}")


def code_segment(
    project_root: Path,
    paper_root: Path,
    raw_path: str,
    description: str,
    *,
    firstline: int,
    lastline: int,
    firstnumber: int | None = None,
    language: str | None = None,
    caption: str | None = None,
    selection_mode: str,
) -> dict[str, Any]:
    source = project_path(project_root, raw_path)
    if not source.is_file():
        raise FileNotFoundError(f"附录源代码不存在: {source}")
    detected = LANGUAGE_BY_SUFFIX.get(source.suffix.lower())
    language = (language or detected or "text").lower()
    total = line_count(source)
    if not 1 <= firstline <= lastline <= max(1, total):
        raise ValueError(f"附录代码行号越界: {raw_path} ({firstline}-{lastline}, 共 {total} 行)")
    validate_source_text(source, firstline, lastline)
    relative_from_paper = os.path.relpath(source, paper_root).replace("\\", "/")
    return {
        "source_path": source.relative_to(project_root).as_posix(),
        "paper_relative_path": tex_file_argument(relative_from_paper),
        "language": language,
        "firstline": firstline,
        "lastline": lastline,
        "firstnumber": int(firstnumber or firstline),
        "caption": str(caption or description or source.name).strip(),
        "selection_mode": selection_mode,
        "source_sha256": sha256(source),
    }


def select_question_code(
    question: dict[str, Any], project_root: Path, paper_root: Path
) -> list[dict[str, Any]]:
    sources = question.get("source_files", [])
    if not sources:
        raise ValueError(f"{question.get('question_id')}: source_files 为空")
    source_map = {str(item["path"]): item for item in sources}
    overrides = question.get("appendix_code") or []
    if overrides:
        result = []
        for item in overrides:
            raw = str(item.get("file", ""))
            if raw not in source_map:
                raise ValueError(f"{question['question_id']}: appendix_code 文件未登记在 source_files: {raw}")
            source = project_path(project_root, raw)
            total = line_count(source)
            result.append(code_segment(
                project_root, paper_root, raw, source_map[raw].get("description", source.name),
                firstline=int(item.get("firstline", 1)),
                lastline=int(item.get("lastline", total)),
                firstnumber=int(item.get("firstnumber", item.get("firstline", 1))),
                language=item.get("language"), caption=item.get("caption"),
                selection_mode="manifest_override",
            ))
        return result

    entrypoint = str(question.get("entrypoint", ""))
    ordered = sorted(sources, key=lambda item: (str(item["path"]) != entrypoint, str(item["path"])))
    result: list[dict[str, Any]] = []
    remaining = 320
    for item in ordered:
        raw = str(item["path"])
        source = project_path(project_root, raw)
        if source.suffix.lower() not in LANGUAGE_BY_SUFFIX or not source.is_file() or remaining <= 0:
            continue
        lines = source.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        ranges = python_key_ranges(source, min(260, remaining)) if source.suffix.lower() == ".py" else generic_key_ranges(lines, min(240, remaining))
        for start, end in ranges:
            result.append(code_segment(
                project_root, paper_root, raw, item.get("description", source.name),
                firstline=start, lastline=end,
                selection_mode="auto_ast" if source.suffix.lower() == ".py" else "auto_keyword_window",
            ))
            remaining -= end - start + 1
            if remaining <= 0:
                break
    if not result:
        raise ValueError(f"{question['question_id']}: 没有可排版的已登记源代码")
    return result


def validate_problem_alignment(paper_manifest: dict[str, Any], supporting_manifest: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    paper_problems = [item for item in paper_manifest.get("chapters", []) if item.get("role") == "problem"]
    support_problems = list(supporting_manifest.get("questions", []))
    if not paper_problems:
        raise ValueError("论文 manifest 未识别到 role=problem 的问题章节")
    if len(paper_problems) != len(support_problems):
        raise ValueError(
            f"论文问题数 ({len(paper_problems)}) 与支撑材料问题数 ({len(support_problems)}) 不一致"
        )
    incomplete = [item.get("question_id") for item in support_problems if item.get("status") != "complete"]
    if incomplete:
        raise ValueError(f"附录只能在全部问题完成后生成，未完成: {', '.join(map(str, incomplete))}")
    return paper_problems, support_problems


def render_appendix_tex(inventory: list[dict[str, Any]], problems: list[dict[str, Any]]) -> str:
    lines = [
        "% Generated by tools/build_appendix.py; do not hand-edit.",
        "% Styling is owned exclusively by 章节模板/附录模板.tex.",
        r"\AppendixStart",
        r"\AppendixPart{1}{附件文件及内容}",
        r"\AppendixAttachmentTableBegin",
    ]
    for index, item in enumerate(inventory, start=1):
        lines.append(
            rf"\AppendixAttachmentRow{{{index}}}"
            rf"{{{tex_escape(item['path'])}}}{{{tex_escape(item['description'])}}}"
        )
    lines.append(r"\AppendixAttachmentTableEnd")
    for index, problem in enumerate(problems, start=1):
        numeral = chinese_number(index)
        lines.append(rf"\AppendixPart{{{index + 1}}}{{问题{numeral}关键代码}}")
        for code_index, segment in enumerate(problem["code"], start=1):
            caption = segment["caption"]
            if len(problem["code"]) > 1:
                caption = f"{caption}（片段 {code_index}）"
            options = ",".join([
                f"firstline={segment['firstline']}",
                f"lastline={segment['lastline']}",
                f"firstnumber={segment['firstnumber']}",
            ])
            lines.append(
                rf"\AppendixCodeFile[{options}]{{{tex_escape(caption)}}}"
                rf"{{{segment['language']}}}{{{segment['paper_relative_path']}}}"
            )
    lines.extend([r"\AppendixEnd", ""])
    return "\n".join(lines)


def build_appendix(
    *,
    project_root: Path,
    paper_manifest_path: Path,
    supporting_manifest_path: Path,
    submission_dir: Path,
    output_tex: Path,
    output_manifest: Path,
    runtime: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    paper_manifest_path = project_path(project_root, paper_manifest_path)
    supporting_manifest_path = project_path(project_root, supporting_manifest_path)
    submission_dir = project_path(project_root, submission_dir)
    output_tex = project_path(project_root, output_tex)
    output_manifest = project_path(project_root, output_manifest)
    paper_manifest = load_json(paper_manifest_path)
    supporting_manifest = load_json(supporting_manifest_path)
    paper_problems, support_problems = validate_problem_alignment(paper_manifest, supporting_manifest)
    from audit_supporting_materials import audit
    check = audit(supporting_manifest_path, project_root, submission_dir, 'final', None, runtime)
    if check['status'] != 'PASS':
        raise ValueError('支撑材料审计失败：' + json.dumps(check['failures'], ensure_ascii=False))
    inventory = collect_attachment_inventory(submission_dir)
    paper_root = paper_manifest_path.parent.resolve()

    problems = []
    for index, (paper_problem, support_problem) in enumerate(zip(paper_problems, support_problems, strict=True), start=1):
        problems.append({
            "index": index,
            "appendix_number": index + 1,
            "question_id": support_problem["question_id"],
            "paper_chapter_id": paper_problem["chapter_id"],
            "paper_title": paper_problem["title"],
            "supporting_title": support_problem["title"],
            "code": select_question_code(support_problem, project_root, paper_root),
        })

    snapshot = {
        "schema_version": APPENDIX_MANIFEST_VERSION,
        "runtime": runtime,
        "paper_manifest": paper_manifest_path.relative_to(project_root).as_posix(),
        "paper_manifest_sha256": sha256(paper_manifest_path),
        "supporting_manifest": supporting_manifest_path.relative_to(project_root).as_posix(),
        "supporting_manifest_sha256": sha256(supporting_manifest_path),
        "submission_dir": submission_dir.relative_to(project_root).as_posix(),
        "problem_count": len(problems),
        "appendix_part_count": len(problems) + 1,
        "attachments": inventory,
        "problems": problems,
    }
    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text(render_appendix_tex(inventory, problems), encoding="utf-8")
    snapshot["generated_tex"] = output_tex.relative_to(project_root).as_posix()
    snapshot["generated_tex_sha256"] = sha256(output_tex)
    output_manifest.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--paper-manifest", type=Path, default=Path("论文/论文输入.json"))
    parser.add_argument("--supporting-manifest", type=Path, default=Path("求解/支撑材料清单.json"))
    parser.add_argument("--submission-dir", type=Path, default=Path("提交附件"))
    parser.add_argument("--output", type=Path, default=Path("论文/章节内容/99_附录.generated.tex"))
    parser.add_argument("--manifest-out", type=Path, default=Path("求解/附录清单.json"))
    parser.add_argument("--runtime", choices=("codex", "claude"))
    args = parser.parse_args()
    result = build_appendix(
        project_root=args.project_root,
        paper_manifest_path=args.paper_manifest,
        supporting_manifest_path=args.supporting_manifest,
        submission_dir=args.submission_dir,
        output_tex=args.output,
        output_manifest=args.manifest_out,
        runtime=args.runtime,
    )
    print(json.dumps({
        "status": "BUILT",
        "problem_count": result["problem_count"],
        "appendix_part_count": result["appendix_part_count"],
        "attachment_rows": len(result["attachments"]),
        "output": result["generated_tex"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
