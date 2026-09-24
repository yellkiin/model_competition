"""Run the unchanged final material audit with cached immutable visual scans."""
from functools import lru_cache
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
import audit_academic_figure_assets as academic_audit
import chart_policy
import workspace_resources
from audit_supporting_materials import audit

academic_audit.build_index = lru_cache(maxsize=None)(academic_audit.build_index)
academic_audit.sync_report = lru_cache(maxsize=None)(academic_audit.sync_report)
chart_policy.audit_preflight = lru_cache(maxsize=None)(chart_policy.audit_preflight)
workspace_resources.dependencies = lru_cache(maxsize=None)(workspace_resources.dependencies)

if __name__ == "__main__":
    report = audit(ROOT / "求解/支撑材料清单.json", ROOT, ROOT / "提交附件",
                   "final", None, "codex")
    path = ROOT / "求解/验收输出/支撑材料/final.precheck.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [x for x in report.get("failures", [])]
    print(report["status"], [(x.get("code"), x.get("severity")) for x in failures])
