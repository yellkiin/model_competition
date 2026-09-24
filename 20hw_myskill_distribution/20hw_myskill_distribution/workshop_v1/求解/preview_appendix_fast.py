"""Prepare a provisional appendix using the unchanged audit with cached scans."""
from functools import lru_cache
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
sys.path.insert(0, str(ROOT.parent / "华为杯_论文规范模板/tools"))
import audit_academic_figure_assets as academic_audit
import chart_policy
import workspace_resources
from build_appendix import build_appendix

academic_audit.build_index = lru_cache(maxsize=None)(academic_audit.build_index)
academic_audit.sync_report = lru_cache(maxsize=None)(academic_audit.sync_report)
chart_policy.audit_preflight = lru_cache(maxsize=None)(chart_policy.audit_preflight)
workspace_resources.dependencies = lru_cache(maxsize=None)(workspace_resources.dependencies)

if __name__ == "__main__":
    result = build_appendix(
        project_root=ROOT,
        paper_manifest_path=Path("论文/论文输入.json"),
        supporting_manifest_path=Path("求解/支撑材料清单.json"),
        submission_dir=Path("提交附件"),
        output_tex=Path("论文/章节内容/99_附录.generated.tex"),
        output_manifest=Path("求解/附录清单.json"),
        runtime="codex",
    )
    print(result["problem_count"], result["appendix_part_count"], len(result["attachments"]))
