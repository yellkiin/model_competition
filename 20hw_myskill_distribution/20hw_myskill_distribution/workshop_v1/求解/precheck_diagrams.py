"""Run the unchanged diagram audit with cached immutable shared-resource scans."""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))

import audit_academic_figure_assets as academic  # noqa: E402
import chart_policy  # noqa: E402
import workspace_resources  # noqa: E402
from audit_diagram_workflow import audit  # noqa: E402

academic.build_index = lru_cache(maxsize=None)(academic.build_index)
academic.sync_report = lru_cache(maxsize=None)(academic.sync_report)
chart_policy.audit_preflight = lru_cache(maxsize=None)(chart_policy.audit_preflight)
workspace_resources.dependencies = lru_cache(maxsize=None)(workspace_resources.dependencies)

result = audit(ROOT / "求解/视觉计划.json", "render", ROOT, "codex")
print(json.dumps({"status": result["status"], "failures": result["failures"][:40]}, ensure_ascii=False))
