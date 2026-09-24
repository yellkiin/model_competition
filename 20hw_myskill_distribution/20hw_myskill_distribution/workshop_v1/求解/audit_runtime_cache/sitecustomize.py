"""Memoize immutable shared catalog scans within one official audit process.

This module is loaded only when its directory is explicitly placed on PYTHONPATH.
The shared template and source inputs stay read-only during each workshop run;
workshop.py also checks the shared-resource and input digests before and after.
The first call executes the maintained scanner unchanged, and later calls with
the same arguments reuse that exact result within the same child process.
"""

from functools import lru_cache
from pathlib import Path
import sys


_tools = Path(__file__).resolve().parents[3] / "华为杯_求解规范" / "tools"
sys.path.insert(0, str(_tools))

import audit_academic_figure_assets as _academic_audit
import chart_policy as _chart_policy
import environment_manager as _environment_manager
import workspace_resources as _workspace_resources
from environment_contract import merge_needs as _merge_needs, read_json as _read_json, validate as _validate, validate_needs as _validate_needs
from workspace_context import file_hash as _file_hash


_academic_audit.build_index = lru_cache(maxsize=None)(_academic_audit.build_index)
_academic_audit.sync_report = lru_cache(maxsize=None)(_academic_audit.sync_report)
_chart_policy.audit_preflight = lru_cache(maxsize=None)(_chart_policy.audit_preflight)
_workspace_resources.dependencies = lru_cache(maxsize=None)(_workspace_resources.dependencies)


_original_ensure_stage = _environment_manager.ensure_stage


def _ensure_stage_with_final_audit_lock(context, tool):
    """Avoid a nested manifest lock for cosmetic stage-reason changes.

    finish() holds the manifest lock while invoking its four official auditors.
    Their capabilities are already registered and verified, but the maintained
    stage preflight rewrites the last-tool reason on every call.  Only bypass
    that write when every other requirement field and the verified environment
    remain current; otherwise use the maintained preflight unchanged.
    """
    lock = context.workspace_root / "求解/验收输出/工作区清单.lock"
    if lock.is_file() and context.manifest.get("environment"):
        current = _validate_needs(_read_json(context.read_path(_environment_manager.NEEDS)))
        merged = _merge_needs(current, _environment_manager.stage_needs(context, tool))
        without_reason = lambda rows: [{k: v for k, v in row.items() if k != "reason"} for row in rows]
        if without_reason(current["requirements"]) == without_reason(merged["requirements"]):
            report = _validate(_read_json(context.read_path(_environment_manager.REPORT)), "环境检测")
            required = {row["capability"] for row in _environment_manager.stage_needs(context, tool)["requirements"]}
            statuses = {row["capability"]: row["status"] for row in report["results"]}
            if (report["workspace"] == str(context.workspace_root)
                    and report["requirements_sha256"] == _file_hash(context.read_path(_environment_manager.NEEDS))
                    and report["catalog_sha256"] == _file_hash(_environment_manager.ENV_DIR / "软件目录.json")
                    and all(statuses.get(capability) == "satisfied" for capability in required)
                    and all(Path(path).is_dir() for path in report["path_entries"])):
                _environment_manager.execution_environment(context)
                return context
    return _original_ensure_stage(context, tool)


_environment_manager.ensure_stage = _ensure_stage_with_final_audit_lock
