#!/usr/bin/env python3
"""Audit Huawei Cup supporting materials at per-question or final stage."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import ast
import hashlib
import json
from pathlib import Path


from supporting_contract import (README_NAME, BUILD_MANIFEST_NAME, HASH_NAME, FORBIDDEN_PARTS,
    SUPPORT_DIR_NAME, internal_root, structure_errors, attachment_summary, validate_manifest, question_name)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(project_root: Path, raw: str) -> Path:
    candidate = (project_root / raw).resolve()
    candidate.relative_to(project_root)
    return candidate


def is_placeholder(text: object) -> bool:
    value = str(text or "").strip()
    return not value or "待审查" in value or "待补充" in value or value == "待填写"


def local_python_dependencies(path: Path, project_root: Path) -> set[Path]:
    """Return directly imported Python files that resolve inside the project."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return set()
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append((node.module, node.level))

    dependencies: set[Path] = set()
    for module, level in modules:
        module_parts = module.split(".")
        bases: list[Path]
        if level:
            base = path.parent
            for _ in range(level - 1):
                base = base.parent
            bases = [base]
        else:
            bases = [path.parent, project_root, project_root / "求解" / "公共"]
        for base in bases:
            stem = base.joinpath(*module_parts)
            for candidate in (stem.with_suffix(".py"), stem / "__init__.py"):
                candidate = candidate.resolve()
                try:
                    candidate.relative_to(project_root)
                except ValueError:
                    continue
                if candidate.is_file() and candidate != path.resolve():
                    dependencies.add(candidate)
    return dependencies


def audit(
    manifest_path: Path,
    project_root: Path,
    output_root: Path,
    stage: str,
    question_id: str | None,
    runtime: str | None = None,
) -> dict:
    checks: list[dict] = []
    failures: list[dict] = []
    warnings: list[dict] = []

    def add(code: str, ok: bool, severity: str = "FAIL", **details) -> None:
        item = {"code": code, "ok": ok, "severity": "PASS" if ok else severity, **details}
        checks.append(item)
        if not ok:
            (failures if severity == "FAIL" else warnings).append(item)

    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        add("manifest_is_valid_json", False, error=str(exc))
        return {"status": "FAIL", "stage": stage, "checks": checks, "failures": failures, "warnings": warnings}

    required_root = {
        "schema_version", "project_title", "package_status", "questions",
        "external_data", "external_data_note", "official_outputs",
    }
    add("root_fields_present", required_root <= set(manifest), missing=sorted(required_root - set(manifest)))
    if failures:
        return {"status": "FAIL", "stage": stage, "checks": checks, "failures": failures, "warnings": warnings}
    add("schema_version_supported", manifest["schema_version"] == "2.0", actual=manifest["schema_version"])

    questions = manifest["questions"] if isinstance(manifest["questions"], list) else []
    qids = [q.get("question_id") for q in questions if isinstance(q, dict)]
    add("questions_present", bool(questions))
    add("question_ids_unique", len(qids) == len(set(qids)) and all(qids), values=qids)
    qmap = {q.get("question_id"): q for q in questions if isinstance(q, dict)}
    if stage == "question":
        add("question_id_provided", bool(question_id))
        add("question_id_known", question_id in qmap if question_id else False, question_id=question_id)
        target_questions = [qmap[question_id]] if question_id in qmap else []
    else:
        target_questions = questions
        add("package_marked_complete", manifest["package_status"] == "complete", actual=manifest["package_status"])

    from model_selection import supporting_gate
    model_errors = supporting_gate(project_root, manifest, question_id if stage == 'question' else None, package=True)
    add('model_selection_gate', not model_errors, errors=model_errors)

    for question in target_questions:
        qid = question.get("question_id", "unknown")
        required = {
            "question_id", "title", "status", "entrypoint", "run_command", "source_files",
            "run_verification", "supplementary_materials", "supplementary_materials_note",
        }
        add(f"{qid}_fields_present", required <= set(question), missing=sorted(required - set(question)))
        if not required <= set(question):
            continue
        add(f"{qid}_marked_complete", question["status"] == "complete", actual=question["status"])
        add(f"{qid}_summary_ready", not is_placeholder(question.get('summary')))
        source_files = question["source_files"] if isinstance(question["source_files"], list) else []
        source_paths = [item.get("path") for item in source_files if isinstance(item, dict)]
        resolved_sources: set[Path] = set()
        add(f"{qid}_source_files_present", bool(source_files))
        add(f"{qid}_entrypoint_listed", question["entrypoint"] in source_paths, entrypoint=question["entrypoint"])
        add(f"{qid}_run_command_present", bool(str(question["run_command"]).strip()))
        for index, item in enumerate(source_files):
            raw = item.get("path", "") if isinstance(item, dict) else ""
            description = item.get("description", "") if isinstance(item, dict) else ""
            try:
                path = project_path(project_root, raw)
                allowed = not FORBIDDEN_PARTS.intersection(path.parts)
                exists = path.is_file()
                if exists:
                    resolved_sources.add(path.resolve())
            except Exception:
                allowed = False
                exists = False
            add(f"{qid}_source_{index}_safe", allowed, path=raw)
            add(f"{qid}_source_{index}_exists", exists, path=raw)
            add(f"{qid}_source_{index}_described", not is_placeholder(description), path=raw)

        missing_local_dependencies: list[str] = []
        for source in sorted(resolved_sources):
            if source.suffix.lower() != ".py":
                continue
            for dependency in local_python_dependencies(source, project_root):
                if dependency not in resolved_sources:
                    missing_local_dependencies.append(dependency.relative_to(project_root).as_posix())
        add(
            f"{qid}_direct_local_python_dependencies_listed",
            not missing_local_dependencies,
            missing=sorted(set(missing_local_dependencies)),
        )

        verification = question["run_verification"]
        add(f"{qid}_run_verified", verification.get("status") == "pass", actual=verification.get("status"))
        add(f"{qid}_verification_time_present", not is_placeholder(verification.get("verified_at")))
        try:
            record = project_path(project_root, verification.get("record_path", ""))
            record_exists = record.is_file() and record.stat().st_size > 0
        except Exception:
            record_exists = False
        add(f"{qid}_verification_record_exists", record_exists, path=verification.get("record_path"))
        from reproduce_supporting_materials import audit_reproduction
        reproduction = audit_reproduction(project_root, manifest_path, output_root,
                                          question, questions.index(question) + 1)
        add(f"{qid}_independent_reproduction", reproduction['status'] == 'PASS',
            errors=reproduction['errors'])
        add(
            f"{qid}_supplementary_reviewed",
            not is_placeholder(question["supplementary_materials_note"]),
            note=question["supplementary_materials_note"],
        )
        source_by_path = {
            item.get("path"): item for item in source_files if isinstance(item, dict)
        }
        for index, item in enumerate(question.get("appendix_code", [])):
            raw = item.get("file", "") if isinstance(item, dict) else ""
            listed = raw in source_by_path
            add(f"{qid}_appendix_code_{index}_listed_source", listed, path=raw)
            try:
                appendix_source = project_path(project_root, raw)
                total_lines = len(appendix_source.read_text(encoding="utf-8-sig", errors="replace").splitlines())
                firstline = int(item.get("firstline", 1))
                lastline = int(item.get("lastline", total_lines))
                valid_range = 1 <= firstline <= lastline <= max(1, total_lines)
            except Exception:
                valid_range = False
                total_lines = 0
            add(
                f"{qid}_appendix_code_{index}_range_valid",
                valid_range,
                path=raw,
                total_lines=total_lines,
            )
        for index, item in enumerate(question["supplementary_materials"]):
            raw = item.get("path", "")
            try:
                path = project_path(project_root, raw)
                exists = path.is_file() and path.stat().st_size > 0
            except Exception:
                exists = False
            add(f"{qid}_supplementary_{index}_exists", exists, path=raw)
            add(
                f"{qid}_supplementary_{index}_described",
                not is_placeholder(item.get("description")) and not is_placeholder(item.get("reason")),
                path=raw,
            )

    external_data = manifest["external_data"] if isinstance(manifest["external_data"], list) else []
    data_ids = [item.get("data_id") for item in external_data if isinstance(item, dict)]
    add("external_data_ids_unique", len(data_ids) == len(set(data_ids)) and all(data_ids), values=data_ids)
    add("external_data_reviewed", not is_placeholder(manifest["external_data_note"]), note=manifest["external_data_note"])
    for data in external_data:
        data_id = data.get("data_id", "unknown")
        required = {
            "data_id", "name", "description", "source", "accessed_at", "collection_method",
            "license_or_terms", "used_by", "files", "collection_scripts", "provenance_file",
        }
        add(f"{data_id}_fields_present", required <= set(data), missing=sorted(required - set(data)))
        if not required <= set(data):
            continue
        add(f"{data_id}_used_by_known_questions", set(data["used_by"]) <= set(qids), used_by=data["used_by"])
        metadata_ok = all(not is_placeholder(data[field]) for field in (
            "name", "description", "source", "accessed_at", "collection_method", "license_or_terms"
        ))
        add(f"{data_id}_provenance_metadata_complete", metadata_ok)
        paths = list(data["files"]) + list(data["collection_scripts"])
        paths.append({"path": data["provenance_file"], "description": "provenance"})
        for index, item in enumerate(paths):
            raw = item.get("path", "")
            try:
                path = project_path(project_root, raw)
                rel = path.relative_to(project_root)
                official_raw = rel.parts[:1] == ("题目",) or rel.parts[:2] == ("数据", "原始")
                safe = not official_raw and not FORBIDDEN_PARTS.intersection(path.parts)
                exists = path.is_file() and path.stat().st_size > 0
            except Exception:
                safe = False
                exists = False
            add(f"{data_id}_file_{index}_not_official_raw", safe, path=raw)
            add(f"{data_id}_file_{index}_exists", exists, path=raw)

    officials = manifest["official_outputs"] if isinstance(manifest["official_outputs"], list) else []
    if stage == "final":
        for index, item in enumerate(officials):
            raw = item.get("path", "")
            try:
                path = project_path(project_root, raw)
                exists = path.is_file() and path.stat().st_size > 0
                verification = project_path(project_root, item.get("verification_path", ""))
                verification_exists = verification.is_file() and verification.stat().st_size > 0
            except Exception:
                exists = False
                verification_exists = False
            add(f"official_{index}_exists", exists, path=raw)
            add(f"official_{index}_verified", item.get("status") == "pass", actual=item.get("status"))
            add(f"official_{index}_verification_record_exists", verification_exists, path=item.get("verification_path"))

    try:
        validate_manifest(manifest)
        add('schema_valid', True)
    except Exception as exc:
        add('schema_valid', False, error=str(exc))
    errors = structure_errors(output_root, manifest)
    add('public_directory_contract', not errors, errors=errors)
    paper_path = project_root / '论文/论文输入.json'
    if paper_path.is_file():
        paper = load_json(paper_path)
        problem_ids = [c['chapter_id'] for c in paper['chapters'] if c['role'] == 'problem']
        add('paper_question_order_matches', problem_ids == qids, paper=problem_ids, supporting=qids)
    build_path = internal_root(project_root) / BUILD_MANIFEST_NAME
    hash_path = internal_root(project_root) / HASH_NAME
    readme_path = output_root / README_NAME
    add('build_manifest_exists', build_path.is_file())
    add('hash_manifest_exists', hash_path.is_file())
    add('readme_exists', readme_path.is_file())
    if build_path.is_file():
        build = load_json(build_path)
        add('package_rebuilt_after_manifest_change', build.get('source_manifest_sha256') == sha256(manifest_path))
        built_questions = set(build.get('completed_questions', []))
        expected_questions = {q['question_id'] for q in target_questions}
        add('target_questions_packaged', expected_questions <= built_questions)
        if stage == 'final': add('all_questions_packaged', set(qids) == built_questions)
        entries = build.get('entries', [])
        expected_paths = {e['package_path'] for e in entries}
        actual_paths = {p.relative_to(output_root).as_posix() for p in output_root.rglob('*') if p.is_file()}
        add('file_inventory_complete', expected_paths == actual_paths,
            missing=sorted(expected_paths-actual_paths),extra=sorted(actual_paths-expected_paths))
        add('unique_destination_paths', len(entries)==len(expected_paths))
        for i,e in enumerate(entries):
            try:
                source = project_path(project_root,e['source_path'])
                packed = project_path(output_root,e['package_path'])
                ok = source.is_file() and packed.is_file() and sha256(source)==e['sha256']==sha256(packed)
            except Exception: ok=False
            add(f'entry_{i}_source_and_package_hash',ok,path=e['package_path'])
        for i,e in enumerate(build.get('internal_records',[])):
            try:
                source=project_path(project_root,e['source_path']); record=project_path(project_root,e['record_path'])
                ok=source.is_file() and record.is_file() and sha256(source)==e['sha256']==sha256(record)
            except Exception: ok=False
            add(f'internal_record_{i}_source_and_snapshot',ok)
        recorded_sources = {e['source_path'] for e in build.get('internal_records', [])}
        required_records = {q['run_verification']['record_path'] for q in target_questions}
        from reproduce_supporting_materials import receipt_path
        required_records.update(receipt_path(project_root, q['question_id']).relative_to(project_root).as_posix()
                                for q in target_questions)
        if stage == 'final': required_records.update(o['verification_path'] for o in officials)
        add('required_internal_records_complete', required_records <= recorded_sources,
            missing=sorted(required_records-recorded_sources))
        official_entries = {e['source_path']:e for e in entries if e['category']=='official_output'}
        for i,o in enumerate(officials):
            e=official_entries.get(o['path'])
            add(f'official_{i}_packaged_at_declared_destination',
                e is not None and e['package_path']==f"{SUPPORT_DIR_NAME}/{o['package_path']}")
        listed={(e.get('question_id'),e['source_path'],e['package_path']) for e in entries if e['category']=='source_code'}
        for i,q in enumerate(questions,1):
            if q not in target_questions: continue
            for src in q['source_files']:
                expected=f"{SUPPORT_DIR_NAME}/{question_name(i)}/源码/{src['package_path']}"
                add(f"{q['question_id']}_source_in_package_{src['package_path']}",
                    (q['question_id'],src['path'],expected) in listed)
            doc=output_root/SUPPORT_DIR_NAME/question_name(i)/'代码环境说明.md'
            content=doc.read_text(encoding='utf-8-sig') if doc.is_file() else ''
            add(f"{q['question_id']}_environment_document", all(x in content for x in ['环境','安装','输入','运行','输出','依赖'])
                and q['package_command'] in content and '待填写' not in content)
            add(f"{q['question_id']}_declared_dependencies",set(q.get('depends_on',[]))<=set(qids[:i-1]))
        try:
            summary=attachment_summary(manifest,output_root)
            readme=readme_path.read_text(encoding='utf-8-sig')
            add('summary_matches_actual_folders',summary==build.get('attachment_summary'))
            add('readme_covers_summary',all(r['path'] in readme and r['description'] in readme for r in summary))
            add('readme_run_instructions',all(x in readme for x in ['复现','数据','结果']))
        except Exception as exc: add('summary_matches_actual_folders',False,error=str(exc))
    if hash_path.is_file():
        records={}; malformed=[]
        for line in hash_path.read_text(encoding='utf-8-sig').splitlines():
            if '  ' not in line: malformed.append(line);continue
            digest,relative=line.split('  ',1)
            if relative in records: malformed.append(line)
            records[relative]=digest
        files={p.relative_to(output_root).as_posix():p for p in output_root.rglob('*') if p.is_file()}
        add('hash_manifest_well_formed',not malformed)
        add('hash_manifest_file_set_complete',set(records)==set(files))
        add('hash_manifest_values_match',all(records.get(k)==sha256(v) for k,v in files.items()))

    registry = project_root / '求解/候选图清单.json'
    if registry.is_file():
        from candidate_figures import audit_registry, package_selection_errors
        add('candidate_runtime_explicit', runtime in ('codex', 'claude'))
        if runtime in ('codex', 'claude'):
            coverage = audit_registry(project_root, registry, runtime, stage, question_id,
                                      paper_plan=project_root / '求解/视觉计划.json' if stage == 'final' else None)
            add('candidate_coverage_complete', coverage['status'] == 'PASS', failures=coverage['failures'])
            errors = package_selection_errors(project_root, registry, manifest, runtime)
            add('candidate_supplement_selection', not errors, errors=errors)

    from audit_diagram_workflow import audit as audit_diagrams
    diagrams = audit_diagrams(project_root / '求解/视觉计划.json',
        'question' if stage == 'question' else 'render', project_root, runtime,
        question_id=question_id, supporting_manifest=manifest_path)
    add('question_comprehensive_diagram_gate', diagrams['status'] == 'PASS', failures=diagrams['failures'])
    # The quota ledger is not evidence that ordinary scientific figures passed
    # their actual reference/source/render review. Check the selected question's
    # canonical assets too; other questions may remain planned until their turn.
    if diagrams['status'] == 'PASS':
        from visual_routes import audit_routes
        visual_path = project_root / '求解/视觉计划.json'
        visual = load_json(visual_path)
        owned = {r['figure_id'] for r in diagrams['figure_accounting']['figures']
                 if stage == 'final' or r.get('assurance_stage') == 'question'}
        ordinary = [f['figure_id'] for p in visual['problems'] for f in p.get('figures', [])]
        ordinary += [f['figure_id'] for f in visual.get('global_figures', [])]
        selected_figures = [fid for fid in ordinary if fid in owned]
        if selected_figures:
            figure_qa = audit_routes(visual_path, 'render', project_root, runtime=runtime,
                                     figure_ids=selected_figures)
            add('counted_scientific_figures_actual_asset_qa', figure_qa['status'] == 'PASS',
                failures=figure_qa['failures'])

    return {
        "status": "PASS" if not failures else "FAIL",
        "stage": stage,
        "question_id": question_id,
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "figure_accounting": diagrams.get('figure_accounting'),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--stage", choices=("question", "final"), required=True)
    parser.add_argument("--question-id")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("提交附件"))
    parser.add_argument("--report", type=Path)
    parser.add_argument('--runtime', choices=('codex', 'claude'))
    args = parser.parse_args()

    if args.stage == "question" and not args.question_id:
        raise SystemExit("--question-id is required for --stage question")
    if args.stage == "final" and args.question_id:
        raise SystemExit("--question-id is only valid for --stage question")

    project_root = args.project_root.resolve()
    manifest_path = project_path(project_root, str(args.manifest))
    output_root = project_path(project_root, str(args.output))
    report = audit(manifest_path, project_root, output_root, args.stage, args.question_id, args.runtime)
    if args.report:
        report_path = project_path(project_root, str(args.report))
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
