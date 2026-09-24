"""Build the candidate gallery with memoized immutable shared-asset scans.

Each candidate still passes the unmodified figure audit, including its own
rendered files, QA record, plan contract, and source references.
"""
from functools import lru_cache
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))

import audit_academic_figure_assets as academic_audit
import chart_policy
import workspace_resources
from candidate_figures import build_gallery

academic_audit.build_index = lru_cache(maxsize=None)(academic_audit.build_index)
academic_audit.sync_report = lru_cache(maxsize=None)(academic_audit.sync_report)
chart_policy.audit_preflight = lru_cache(maxsize=None)(chart_policy.audit_preflight)
workspace_resources.dependencies = lru_cache(maxsize=None)(workspace_resources.dependencies)

if __name__ == "__main__":
    print(build_gallery(ROOT, ROOT / "求解/候选图清单.json", ROOT / "待选图库", "codex"))
