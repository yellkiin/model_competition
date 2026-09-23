"""失败关闭的发布检查。人工签署是流程约定，不是身份认证。"""
from __future__ import annotations

import re
import shutil

from .core import Workspace, digest, save, stamp, validate_sources
from .publication import metric_rows
from .research import eligible_sources

CHECKS = ("official_template", "anonymization", "ai_policy", "citations",
          "rendered_pdf", "all_questions_answered", "scientific_review")


def audit(ws: Workspace, final: bool = False, pdf: str = "build/draft.pdf") -> dict:
    errors, warnings = [], []
    try:
        errors += ws.input_errors() + ws.artifact_errors()
        errors += validate_sources(ws.read("sources.json"))
        if ws.path("results/metrics.json").exists():
            metric_rows(ws)
        sources = {s["id"] for s in eligible_sources(ws)}
        ledger = ws.read("artifacts.json")
        for claim in ws.read("claims.json"):
            if claim.get("status") != "supported":
                warnings.append(f"未支持的主张: {claim.get('id', '?')}")
                if final:
                    errors.append("正式主张存在未支持项")
                continue
            refs, evidence = claim.get("source_ids", []), claim.get("evidence", [])
            if not refs and not evidence:
                errors.append(f"主张没有证据: {claim.get('id', '?')}")
            if any(key not in sources for key in refs):
                errors.append("主张引用了未阅读/未复核来源")
            if any(name not in ledger for name in evidence):
                errors.append("主张引用未登记产物")
        if final:
            errors += final_errors(ws, pdf)
        else:
            warnings.append("普通 audit 通过仅代表已实现检查通过，不代表竞赛可提交")
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        errors.append(f"证据结构不完整或无法读取: {exc}")
    return {"ok": not errors, "scope": "final" if final else "workspace",
            "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def final_errors(ws: Workspace, pdf: str) -> list[str]:
    errors = []
    contract, rules = ws.read("contract.json"), ws.read("rules.json")
    if contract.get("mode") != "competition":
        errors.append("演练工作区不可作为正式参赛成果")
    if contract.get("problem_id") == "TBD" or not contract.get("tasks"):
        errors.append("题目契约未完成")
    if rules.get("year") != contract.get("year") or not rules.get("verified_by"):
        errors.append("当年赛事规则未经人工核对")
    for name in CHECKS:
        if rules.get("checks", {}).get(name) is not True:
            errors.append(f"缺少规则/人工检查: {name}")
    for name in ("policy_file", "template_file"):
        target = rules.get(name, "")
        if not target or target not in ws.read("input_manifest.json")["files"]:
            errors.append(f"当年官方文件未作为输入封存: {name}")
    ledger = ws.read("artifacts.json")
    for name in ("notes/model.md", "notes/review.md", "notes/limitations.md"):
        if name not in ledger or not ws.path(name).is_file() or not ws.path(name).stat().st_size:
            errors.append(f"缺少已登记的人工可读报告: {name}")
    usage = ws.read("ai_usage.json")
    if not usage or any(r.get("human_review") != "reviewed" for r in usage):
        errors.append("AI 使用披露记录为空或未复核")
    for record in usage:
        for name, sha in record.get("output_sha256", {}).items():
            if not ws.path(name).is_file() or digest(ws.path(name)) != sha:
                errors.append(f"AI 输出在复核记录之后变更: {name}")
    target = ws.path(pdf)
    if pdf not in ledger or ledger[pdf].get("kind") != "pdf":
        errors.append("PDF 未登记编译/来源")
    if not target.is_file() or target.read_bytes()[:5] != b"%PDF-":
        errors.append("PDF 缺失或文件头错误")
        return errors
    approvals = ws.read("approvals.json")
    if (approvals.get("decision") != "approved" or not approvals.get("approved_by")
            or approvals.get("snapshot") != ws.snapshot()
            or approvals.get("pdf_sha256") != digest(target)):
        errors.append("缺少绑定当前证据快照和 PDF 的队员签署")
    if ws.path("results/metrics.json").exists() and ws.read("results/metrics.json").get("synthetic"):
        errors.append("内置 synthetic 演练结果禁止正式发布")
    return errors


def freeze(ws: Workspace, pdf: str, filename: str, rehearsal: bool = False) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.pdf", filename):
        raise ValueError("发布名仅允许 ASCII 字母/数字/下划线/短横线.pdf")
    if rehearsal and ws.read("contract.json").get("mode") != "rehearsal":
        raise ValueError("竞赛工作区不能用 rehearsal 绕过正式检查")
    report = audit(ws, final=not rehearsal, pdf=pdf)
    if not report["ok"]:
        raise ValueError("; ".join(report["errors"]))
    source = ws.path(pdf)
    if source.read_bytes()[:5] != b"%PDF-" or pdf not in ws.read("artifacts.json"):
        raise ValueError("缺少有效且已登记的 PDF")
    expected = digest(source)
    folder = "release_demo" if rehearsal else "release"
    destination = ws.path(f"{folder}/{filename}")
    if destination.exists():
        raise ValueError("已冻结文件禁止覆盖；请另建版本")
    destination.parent.mkdir(exist_ok=True)
    shutil.copyfile(source, destination)
    if digest(destination) != expected or digest(source) != expected:
        destination.unlink()
        raise ValueError("复制期间源 PDF 变化；未完成冻结")
    value = {"created_at": stamp(), "rehearsal": rehearsal, "file": destination.name,
             "sha256": expected, "md5": digest(destination, "md5"),
             "evidence_snapshot": ws.snapshot(), "uploaded": False}
    save(destination.with_suffix(".manifest.json"), value)
    return value
