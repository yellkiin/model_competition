#!/usr/bin/env python3
"""Create a draft Huawei Cup visual-evidence plan for a new problem set."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import json
from pathlib import Path


REQUIRED_EVIDENCE = (
    ("mechanism_geometry", "模型机理、几何或数据流是否需要可视解释？"),
    ("main_result", "本问最重要的定量结论是什么？"),
    ("independent_validation", "什么独立证据能够验证主结果？"),
    ("sensitivity_robustness", "哪些输入、参数或扰动会改变结论？"),
)


def make_problem(problem_id: str, complexity: str) -> dict:
    prefix = problem_id.replace(" ", "-")
    evidence = []
    for index, (category, question) in enumerate(REQUIRED_EVIDENCE, start=1):
        evidence.append({
            "evidence_id": f"{prefix}-E{index:02d}",
            "category": category,
            "question": question,
            "applicability": "pending",
            "reason": "",
            "data_shape": "pending",
            "representation": "pending",
            "result_files": [],
            "figure_ids": [],
        })
    return {
        "problem_id": problem_id,
        "complexity": complexity,
        "claims": [{"claim_id": f"{prefix}-C01", "text": "待填写：可复算的核心结论"}],
        "evidence_matrix": evidence,
        "figures": [],
        "schematics": [],
        "low_figure_exception": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project-title", required=True)
    parser.add_argument("--problem-id", action="append", required=True,
                        help="Repeat once per problem, for example --problem-id 问题一")
    parser.add_argument("--complexity", choices=("simple", "standard", "complex"), default="standard")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing draft")
    parser.add_argument("--runtime", choices=("codex", "claude"), required=True)
    parser.add_argument('--project-root', type=Path)
    args = parser.parse_args()

    from workspace_context import shared_context, bounded
    context = shared_context(args.project_root or Path.cwd(), args.runtime)
    if context:
        output = context.write_path(args.output)
        project_root = context.workspace_root
    elif args.project_root:
        project_root = args.project_root.resolve()
        output = bounded(project_root, args.output)
    else:
        output = args.output.resolve()
        project_root = output.parent.parent  # Explicit legacy CLI compatibility.
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite existing plan: {output}")
    plan = {
        "schema_version": "1.2",
        "drawing_preflight_path": "求解/绘图能力预检.json",
        "project_title": args.project_title,
        "plan_status": "draft",
        "visual_encoding_path": "求解/视觉编码表.md",
        "problems": [make_problem(pid, args.complexity) for pid in args.problem_id],
        "global_figures": [],
        "flowcharts": [{
            "scope": "全篇",
            "needed": "pending",
            "reason": "",
            "plan_id": None,
            "status": "pending",
        }],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    registry = output.with_name('候选图清单.json')
    if registry.exists():
        registered = json.loads(registry.read_text(encoding='utf-8-sig'))
        if [q['question_id'] for q in registered['questions']] != args.problem_id:
            raise SystemExit('Existing candidate questions differ; migrate explicitly without overwriting history')
    from audit_diagram_workflow import initialize, sidecar
    from visual_routes import media_sidecar
    if media_sidecar(output).exists():
        existing_media = json.loads(media_sidecar(output).read_text(encoding='utf-8-sig'))
        if existing_media.get('runtime') != args.runtime or existing_media.get('figures'):
            raise SystemExit('Existing media runtime or reviewed figure records require explicit migration')
    if sidecar(output).exists():
        existing = json.loads(sidecar(output).read_text(encoding='utf-8-sig'))
        if existing.get('runtime') != args.runtime or [q['problem_id'] for q in existing['questions']] != args.problem_id:
            raise SystemExit('Existing diagram runtime/questions differ; migrate explicitly without overwriting history')
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not sidecar(output).exists():
        initialize(output, args.runtime)
    from candidate_figures import initialize
    if not registry.exists():
        initialize(project_root, registry, args.problem_id)
    from audit_media_figures import prepare
    from visual_routes import media_sidecar
    if not media_sidecar(output).exists():
        media_sidecar(output).write_text(json.dumps(prepare(output, args.runtime), ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({"status": "DRAFT_CREATED", "output": str(output), "next": "Classify content routes, then complete drawing_sources.py dual-source preflight. Compare academic/modelviz per ordinary panel; record actual chart families and 3D assessment. Academic uses .assets.json; modelviz uses modelviz_bridge.py and .modelviz.json; native/domain uses .media.json. Initial records grant no approval."}, ensure_ascii=False))


if __name__ == "__main__":
    main()
