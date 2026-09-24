"""Precheck the official candidate final audit with cached immutable scans."""
from functools import lru_cache
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
import audit_academic_figure_assets as academic_audit
import chart_policy
import workspace_resources
from candidate_figures import audit_registry

academic_audit.build_index = lru_cache(maxsize=None)(academic_audit.build_index)
academic_audit.sync_report = lru_cache(maxsize=None)(academic_audit.sync_report)
chart_policy.audit_preflight = lru_cache(maxsize=None)(chart_policy.audit_preflight)
workspace_resources.dependencies = lru_cache(maxsize=None)(workspace_resources.dependencies)

if __name__ == "__main__":
    report = audit_registry(ROOT, ROOT / "求解/候选图清单.json", "codex", stage="final",
                            paper_plan="求解/视觉计划.json")
    target = ROOT / "求解/验收输出/候选.final.precheck.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"], report["failures"])
