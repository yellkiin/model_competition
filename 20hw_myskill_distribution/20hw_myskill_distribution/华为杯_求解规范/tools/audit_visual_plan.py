#!/usr/bin/env python3
"""Audit Huawei Cup visual evidence at plan, render, or paper stage."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import json
import re
from pathlib import Path


REQUIRED_CATEGORIES = {
    "mechanism_geometry",
    "main_result",
    "independent_validation",
    "sensitivity_robustness",
}
VISUAL_FIRST_SHAPES = {
    "multi_point_scan",
    "repeated_trials",
    "distribution",
    "error_structure",
    "matrix_surface",
    "spatial_geometry",
}
VECTOR_EXTENSIONS = {".pdf", ".svg"}
MIN_PROBLEM_FIGURES = 4
MAX_PROBLEM_FIGURES = 6
MIN_PAPER_FIGURES = 16


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def project_path(project_root: Path, raw: str) -> Path:
    candidate = (project_root / raw).resolve()
    candidate.relative_to(project_root.resolve())
    return candidate


def tex_closure(main: Path) -> str:
    # TeX resolves every nested input against the main working directory.
    # Missing inputs and cycles are errors, not silently missing body figures.
    import sys
    paper_tools = Path(__file__).resolve().parents[2] / '华为杯_论文规范模板/tools'
    if str(paper_tools) not in sys.path:
        sys.path.insert(0, str(paper_tools))
    from paper_contract import expand_fragment
    return expand_fragment(main.parent, main)



def body_tex(main: Path) -> str:
    text = tex_closure(main)
    if r"\begin{document}" in text:
        text = text.split(r"\begin{document}", 1)[1]
    if r"\maketoc" in text:
        text = text.split(r"\maketoc", 1)[1]
    return re.split(r"\\(?:appendix|bibliography|printbibliography)\b|\\begin\{thebibliography\}|\\section\*?\s*\{参考文献\}|\\end\{document\}", text, maxsplit=1)[0]


def audit(plan_path: Path, stage: str, project_root: Path, main_tex: Path | None,
          asset_references: Path | None = None, allow_demo: bool = False, runtime: str | None = None) -> dict:
    checks: list[dict] = []
    failures: list[dict] = []
    warnings: list[dict] = []

    def add(code: str, ok: bool, severity: str = "FAIL", **details) -> None:
        item = {"code": code, "ok": ok, "severity": "PASS" if ok else severity, **details}
        checks.append(item)
        if not ok:
            (failures if severity == "FAIL" else warnings).append(item)

    try:
        plan = load_json(plan_path)
    except Exception as exc:
        add("plan_is_valid_json", False, error=str(exc))
        return {"status": "FAIL", "stage": stage, "checks": checks, "failures": failures, "warnings": warnings}

    required_root = {"schema_version", "project_title", "plan_status", "visual_encoding_path",
                     "problems", "global_figures", "flowcharts"}
    add("root_fields_present", required_root <= set(plan), missing=sorted(required_root - set(plan)))
    if failures:
        return {"status": "FAIL", "stage": stage, "checks": checks, "failures": failures, "warnings": warnings}

    add("schema_version_supported", plan["schema_version"] in {"1.0", "1.1", "1.2"}, actual=plan["schema_version"])
    from visual_routes import primary_output, academic_panels, routing_errors
    from jsonschema import Draft202012Validator
    schema = load_json(Path(__file__).resolve().parents[1] / '视觉计划.schema.json')
    schema_failures = [e.message for e in Draft202012Validator(schema).iter_errors(plan)]
    add('visual_plan_schema', not schema_failures, errors=schema_failures)
    add("plan_marked_ready", plan["plan_status"] == "ready", actual=plan["plan_status"])
    problems = plan.get("problems", [])
    add("problems_present", bool(problems), count=len(problems))
    add("visual_encoding_declared", bool(str(plan.get("visual_encoding_path", "")).strip()))

    import sys
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_diagram_workflow import audit as audit_diagrams, sidecar, as_schematic
    dg = audit_diagrams(plan_path, stage, project_root, runtime, main_tex, allow_demo=allow_demo)
    add("diagram_workflow_gate", dg['status'] == 'PASS', failures=dg['failures'])
    accounting = dg.get('figure_accounting') or {}
    counts_by_problem = {r['problem_id']: r for r in accounting.get('questions', [])}
    diagram_rows = load_json(sidecar(plan_path)).get('diagrams', []) if sidecar(plan_path).is_file() else []
    diagram_rows = [d for d in diagram_rows if d.get('placement') == 'body']
    all_figures: list[dict] = list(plan.get("global_figures", []))
    all_schematics: list[dict] = [as_schematic(d) for d in diagram_rows if d.get('problem_id') is None]
    all_figure_ids: list[str] = []
    all_claim_ids: set[str] = set()
    all_evidence_ids: set[str] = set()
    problem_summaries: list[dict] = []

    for problem in problems:
        pid = str(problem.get("problem_id", ""))
        complexity = problem.get("complexity")
        figures = problem.get("figures", [])
        schematics = list(problem.get("schematics", [])) + [as_schematic(d) for d in diagram_rows if d.get('problem_id') == pid]
        evidence = problem.get("evidence_matrix", [])
        claims = problem.get("claims", [])
        all_figures.extend(figures)
        all_schematics.extend(schematics)

        add(f"{pid}:complexity_valid", complexity in {"simple", "standard", "complex"}, actual=complexity)
        claim_ids = [str(item.get("claim_id", "")) for item in claims]
        add(f"{pid}:claims_defined", bool(claim_ids) and all(str(item.get("text", "")).strip() for item in claims))
        add(f"{pid}:claim_ids_unique", len(claim_ids) == len(set(claim_ids)), ids=claim_ids)
        all_claim_ids.update(claim_ids)

        evidence_ids = [str(item.get("evidence_id", "")) for item in evidence]
        categories = {item.get("category") for item in evidence}
        add(f"{pid}:required_coverage_reviewed", REQUIRED_CATEGORIES <= categories,
            missing=sorted(REQUIRED_CATEGORIES - categories))
        add(f"{pid}:evidence_ids_unique", len(evidence_ids) == len(set(evidence_ids)), ids=evidence_ids)
        all_evidence_ids.update(evidence_ids)

        pending = [item.get("evidence_id") for item in evidence
                   if item.get("applicability") == "pending" or item.get("representation") == "pending"
                   or item.get("data_shape") == "pending"]
        add(f"{pid}:evidence_decisions_complete", not pending, pending=pending)
        unexplained_na = [item.get("evidence_id") for item in evidence
                          if item.get("applicability") in {"not_needed", "not_possible"}
                          and len(str(item.get("reason", "")).strip()) < 10]
        add(f"{pid}:inapplicability_explained", not unexplained_na, ids=unexplained_na)

        visual_misses = [item.get("evidence_id") for item in evidence
                         if item.get("applicability") == "applicable"
                         and item.get("data_shape") in VISUAL_FIRST_SHAPES
                         and item.get("representation") not in {"figure", "schematic"}]
        add(f"{pid}:visual_first_evidence_mapped", not visual_misses,
            severity="WARN", ids=visual_misses,
            message="多点扫描、重复试验、分布、误差结构、矩阵或空间数据默认优先图形表达")

        main_evidence = [item for item in evidence if item.get("category") == "main_result"]
        def has_evidence(item):
            return (item.get("applicability") == "applicable"
                    and ((item.get("representation") in {"figure", "schematic"} and bool(item.get("figure_ids")))
                         or (item.get("representation") in {"table", "text"} and bool(item.get("result_files")))))

        add(f"{pid}:main_result_has_evidence", any(has_evidence(item) for item in main_evidence))

        validation_evidence = [item for item in evidence if item.get("category") == "independent_validation"]
        limited_validation = any(item.get("applicability") in {"not_needed", "not_possible"}
                                 and len(str(item.get("reason", "")).strip()) >= 20 for item in validation_evidence)
        alternative = any(item.get("category") in {"theoretical_boundary", "counterexample", "comparison_ablation"}
                          and has_evidence(item) for item in evidence)
        validation_ok = any(has_evidence(item) for item in validation_evidence) or (limited_validation and alternative)
        add(f"{pid}:validation_has_evidence", validation_ok,
            message="独立验证可用图、表或解析证明；不可验证时须说明边界并登记替代证据，不得冒充准确率验证")
        if limited_validation and alternative:
            add(f"{pid}:validation_limitation_disclosed", False, severity="WARN",
                message="替代证据不证明未知真值；论文须保留该限制")
        if stage in {"render", "paper"}:
            for item in evidence:
                if not has_evidence(item) or item.get("representation") not in {"table", "text"}:
                    continue
                missing = []
                for raw in item.get("result_files", []):
                    try:
                        path = project_path(project_root, raw)
                        if not path.is_file() or path.stat().st_size == 0:
                            missing.append(raw)
                    except (ValueError, OSError):
                        missing.append(raw)
                add(f"{pid}:{item.get('evidence_id')}:evidence_files_exist", not missing, missing=missing)

        figure_count = counts_by_problem.get(pid, {}).get('independent_science_count', 0)
        add(f"{pid}:figure_count_range", MIN_PROBLEM_FIGURES <= figure_count <= MAX_PROBLEM_FIGURES,
            count=figure_count, minimum=MIN_PROBLEM_FIGURES, maximum=MAX_PROBLEM_FIGURES,
            message="每问4--6张独立科学图，另加1张主要综合图；综合图和内部Panel不抵扣额度")

        families = {panel.get("figure_family") for fig in figures for panel in fig.get("panels", [])}
        if len(figures) >= 3:
            add(f"{pid}:figure_family_diversity", len(families) >= 2, severity="WARN", families=sorted(f for f in families if f))

        for schematic in schematics:
            add(f"{pid}:{schematic.get('schematic_id')}:sources_traceable",
                bool(schematic.get("source_refs")) and bool(schematic.get("elements")))
            paper = schematic.get("paper", {})
            add(f"{pid}:{schematic.get('schematic_id')}:paper_contract_declared",
                str(paper.get("label", "")).startswith("fig:")
                and bool(str(paper.get("caption", "")).strip())
                and bool(str(paper.get("reference_context", "")).strip()))

            if stage in {"render", "paper"}:
                required_files = [schematic.get("tex_source"), schematic.get("output_pdf"),
                                  schematic.get("preview_png")]
                missing = []
                for raw in required_files:
                    try:
                        path = project_path(project_root, str(raw))
                    except (ValueError, OSError):
                        missing.append(str(raw))
                        continue
                    if not path.is_file() or path.stat().st_size == 0:
                        missing.append(str(raw))
                add(f"{pid}:{schematic.get('schematic_id')}:render_artifacts_exist",
                    not missing, missing=missing)
                add(f"{pid}:{schematic.get('schematic_id')}:qa_status_pass",
                    schematic.get("status") == "qa_pass", actual=schematic.get("status"))

        problem_summaries.append({
            "problem_id": pid,
            "complexity": complexity,
            "figures": len(figures),
            "schematics": len(schematics),
            "independent_science_count": figure_count,
            "overview_count": counts_by_problem.get(pid, {}).get('overview_count', 0),
            "families": sorted(f for f in families if f),
        })

    all_figure_ids = [str(fig.get("figure_id", "")) for fig in all_figures]
    add("figure_ids_unique", len(all_figure_ids) == len(set(all_figure_ids)), ids=all_figure_ids)
    figure_id_set = set(all_figure_ids)
    all_schematic_ids = [str(item.get("schematic_id", "")) for item in all_schematics]
    add("schematic_ids_unique", len(all_schematic_ids) == len(set(all_schematic_ids)),
        ids=all_schematic_ids)
    visual_items = all_figures + all_schematics
    visual_labels = [item.get("paper", {}).get("label", "") for item in visual_items]
    add("visual_labels_unique", len(visual_labels) == len(set(visual_labels)), labels=visual_labels)
    add("visual_ids_disjoint", not (figure_id_set & set(all_schematic_ids)))
    add("paper_figure_minimum", accounting.get('paper_eligible_count', 0) >= MIN_PAPER_FIGURES,
        count=accounting.get('paper_eligible_count', 0), minimum=MIN_PAPER_FIGURES,
        message="排除每问主要综合图后，正文至少16张合格独立图；总体路线可计全文，不计逐问")

    layouts: list[str] = []
    archetypes: list[str] = []
    output_paths: list[str] = [str(item.get(key, "")) for item in all_schematics for key in ("output_pdf", "preview_png")]
    for fig in all_figures:
        fid = str(fig.get("figure_id", ""))
        panels = fig.get("panels", [])
        panel_ids = [str(panel.get("panel_id", "")) for panel in panels]
        layouts.append(str(fig.get("layout", "")))
        archetypes.append(str(fig.get("archetype", "")))
        add(f"{fid}:panel_ids_unique", len(panel_ids) == len(set(panel_ids)), ids=panel_ids)
        add(f"{fid}:panel_count_range", 1 <= len(panels) <= 6, count=len(panels))
        hero = fig.get("hero_panel")
        asymmetric = fig.get("archetype") in {"schematic_led", "image_plate_quant", "asymmetric_mixed"}
        add(f"{fid}:hero_contract", (hero in panel_ids) if asymmetric and len(panels) >= 3 else hero in panel_ids or hero is None,
            hero=hero, archetype=fig.get("archetype"))
        add(f"{fid}:claim_links_resolve", set(fig.get("claim_ids", [])) <= all_claim_ids,
            unknown=sorted(set(fig.get("claim_ids", [])) - all_claim_ids))
        add(f"{fid}:evidence_links_resolve", set(fig.get("evidence_ids", [])) <= all_evidence_ids,
            unknown=sorted(set(fig.get("evidence_ids", [])) - all_evidence_ids))
        vector = primary_output(fig)
        preview = str(fig.get("outputs", {}).get("preview", ""))
        output_paths.extend(set(fig.get('outputs', {}).values()))
        add(f"{fid}:routing_valid", not routing_errors(fig), errors=routing_errors(fig))
        extensions = VECTOR_EXTENSIONS if academic_panels(fig) else {'.pdf', '.svg', '.png', '.jpg', '.jpeg'}
        add(f"{fid}:primary_and_preview_declared", Path(vector).suffix.lower() in extensions and Path(preview).suffix.lower() == ".png",
            vector=vector, preview=preview)
        paper = fig.get("paper", {})
        add(f"{fid}:paper_contract_declared", str(paper.get("label", "")).startswith("fig:")
            and bool(str(paper.get("caption", "")).strip()) and bool(str(paper.get("reference_context", "")).strip()))

        if stage in {"render", "paper"}:
            required_files = [fig.get("script"), vector, preview, fig.get("statistics_report"), fig.get("qa_report")]
            required_files += [panel.get("result_file") for panel in panels]
            missing = []
            for raw in required_files:
                try:
                    path = project_path(project_root, str(raw))
                except (ValueError, OSError):
                    missing.append(str(raw))
                    continue
                if not path.is_file() or path.stat().st_size == 0:
                    missing.append(str(raw))
            add(f"{fid}:render_artifacts_exist", not missing, missing=missing)
            add(f"{fid}:qa_status_pass", fig.get("status") == "qa_pass", actual=fig.get("status"))

    add("output_paths_unique", len(output_paths) == len(set(output_paths)), duplicates=sorted({p for p in output_paths if output_paths.count(p) > 1}))
    if len(all_figures) >= 4:
        add("layout_not_monoculture", len(set(layouts)) >= 2, severity="WARN", layouts=layouts)
    if len(all_figures) >= 6:
        add("archetype_not_monoculture", len(set(archetypes)) >= 2, severity="WARN", archetypes=archetypes)

    allowed_visual_ids = figure_id_set | set(all_schematic_ids)
    unknown_figure_links = []
    for problem in problems:
        for item in problem.get("evidence_matrix", []):
            unknown_figure_links.extend(fid for fid in item.get("figure_ids", []) if fid not in allowed_visual_ids)
    add("evidence_visual_links_resolve", not unknown_figure_links,
        unknown=sorted(set(unknown_figure_links)))

    flowcharts = plan.get("flowcharts", [])
    flow_pending = [item.get("scope") for item in flowcharts if item.get("needed") == "pending"]
    add("flowchart_decisions_complete", not flow_pending, pending=flow_pending)
    bad_flow = [item.get("scope") for item in flowcharts
                if item.get("needed") in {"yes", "no"} and len(str(item.get("reason", "")).strip()) < 10]
    add("flowchart_decisions_explained", not bad_flow, scopes=bad_flow)
    flow_contract_errors = [item.get("scope") for item in flowcharts
                            if (item.get("needed") == "yes" and not item.get("plan_id"))
                            or (item.get("needed") == "no" and
                                (item.get("plan_id") is not None or item.get("status") != "not_applicable"))]
    add("flowchart_plan_contracts_valid", not flow_contract_errors, scopes=flow_contract_errors,
        message="需要流程图时必须登记 plan_id；不需要时 plan_id 为空且状态为 not_applicable")
    if stage in {"render", "paper"}:
        flow_not_passed = [item.get("scope") for item in flowcharts
                           if item.get("needed") == "yes" and item.get("status") != "qa_pass"]
        add("required_flowcharts_qa_pass", not flow_not_passed, scopes=flow_not_passed)

    if stage == "paper":
        add("main_tex_provided", main_tex is not None and main_tex.is_file(), path=str(main_tex) if main_tex else None)
        if main_tex is not None and main_tex.is_file():
            tex = body_tex(main_tex)
            labels = set(re.findall(r"\\label\s*\{([^{}]+)\}", tex))
            graphics = {raw.replace("\\", "/") for raw in re.findall(r"\\includegraphics(?:\[[^]]*\])?\s*\{([^{}]+)\}", tex)}
            missing_labels = [fig.get("paper", {}).get("label") for fig in all_figures
                              if fig.get("paper", {}).get("label") not in labels]
            missing_labels.extend(item.get("paper", {}).get("label") for item in all_schematics
                                  if item.get("paper", {}).get("label") not in labels)
            add("planned_visual_labels_in_tex", not missing_labels,
                missing=sorted(set(label for label in missing_labels if label)))
            blocks = re.findall(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", tex, re.S)
            numbered = [block for block in blocks if re.search(r"\\caption(?:\[[^]]*\])?\s*\{", block)
                        and r"\includegraphics" in block]
            occurrences = {label: sum(label in re.findall(r"\\label\s*\{([^{}]+)\}", block) for block in numbered)
                           for label in visual_labels}
            multiple_labels = [sorted(set(visual_labels) & set(re.findall(r"\\label\s*\{([^{}]+)\}", block)))
                               for block in numbered]
            add("one_planned_figure_per_environment", all(len(items) <= 1 for items in multiple_labels),
                message="同一Figure中的多个Panel标签不能分别计为独立图号")
            add("planned_visuals_are_numbered_figures", all(count == 1 for count in occurrences.values()),
                occurrences=occurrences, message="每张计数图必须实际入文，有独立caption和唯一label；不得把Panel分别计数")
            # Resolve what the engine actually included, including graphicspath and
            # macro filenames. A same-basename PNG/PDF elsewhere is not a match.
            try:
                from collect_academic_paper_review import read_probe
                from prepare_academic_figure_review import sidecar_path
                from audit_diagram_workflow import sidecar
                ref_path = Path(asset_references or sidecar_path(plan_path))
                refs = json.loads((ref_path if ref_path.is_file() else sidecar(plan_path)).read_text(encoding="utf-8-sig"))
                evidence = json.loads(project_path(project_root, refs["paper_review_path"]).read_text(encoding="utf-8-sig"))
                actual = read_probe(project_path(project_root, evidence["probe_path"]), main_tex.parent)
                planned = {project_path(project_root, primary_output(fig)).resolve() for fig in all_figures}
                planned.update(project_path(project_root, item["output_pdf"]).resolve() for item in all_schematics)
                result_root = (project_root / "求解").resolve()
                unplanned = [str(row["path"]) for row in actual.values()
                             if row["path"].is_relative_to(result_root) and row["path"] not in planned]
                add("paper_result_graphics_are_planned", not unplanned, unplanned=unplanned)
            except (KeyError, ValueError, OSError) as exc:
                add("paper_result_graphics_are_planned", False, error=str(exc))

    # Mandatory sidecar gate. Imported locally for compatibility with direct and importlib callers.
    import sys
    tools_dir = str(Path(__file__).resolve().parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    from audit_academic_figure_assets import audit_assets
    assets = audit_assets(plan_path, stage, project_root, asset_references, allow_demo, runtime, main_tex)
    add("academic_asset_gate", assets["status"] == "PASS", failures=assets["failures"], assurance=assets["assurance"])
    from audit_media_figures import audit_media
    media = audit_media(plan_path, stage, project_root, runtime, allow_demo, main_tex)
    add('media_evidence_gate', media['status'] == 'PASS', failures=media['failures'])
    from modelviz_bridge import audit_modelviz
    modelviz = audit_modelviz(plan_path, stage, project_root, runtime, allow_demo, main_tex)
    add('modelviz_evidence_gate', modelviz['status'] == 'PASS', failures=modelviz['failures'])
    from chart_policy import audit_policy
    policy = audit_policy(plan, project_root, runtime)
    add('drawing_selection_policy', not policy, failures=policy)

    registry = plan_path.with_name('候选图清单.json')
    if registry.is_file() and stage in {'render', 'paper'}:
        from candidate_figures import audit_registry
        coverage = audit_registry(project_root, registry, runtime, 'final',
                                  allow_demo=allow_demo, paper_plan=plan_path)
        add('candidate_coverage_complete', coverage['status'] == 'PASS', failures=coverage['failures'])

    status = "FAIL" if failures else "PASS"
    return {
        "status": status,
        "stage": stage,
        "plan": str(plan_path),
        "project_root": str(project_root),
        "summary": {
            "problems": problem_summaries,
            "figures": len(all_figures),
            "schematics": len(all_schematics),
            "failures": len(failures),
            "warnings": len(warnings),
        },
        "figure_accounting": accounting,
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--stage", choices=("plan", "render", "paper"), default="plan")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--main-tex", type=Path)
    parser.add_argument("--asset-references", type=Path, help="Default: <plan stem>.assets.json")
    parser.add_argument("--runtime", choices=("codex", "claude"), required=True)
    parser.add_argument("--allow-demo", action="store_true", help="Isolated fixtures only; never accepted for paper")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    plan = args.plan.resolve()
    project_root = args.project_root.resolve() if args.project_root else (
        plan.parent.parent if plan.parent.name == "求解" else plan.parent
    )
    main_tex = args.main_tex.resolve() if args.main_tex else None
    result = audit(plan, args.stage, project_root, main_tex, args.asset_references, args.allow_demo, args.runtime)
    report = args.report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
