"""按阶段路由仓库内参考资料。只读取元数据，不执行上游代码或冒称已经读过。"""
from __future__ import annotations

import csv
from pathlib import Path
from .core import digest

HWB = "各种建模agent/hwb-math-modeling-skills"
MMA = "各种建模agent/MathModelAgent"
WRITING = "各种建模agent/awesome-ai-research-writing/README.md"
LIBRARY = HWB + "/数模资料/优秀论文索引/近期论文原文"
GUIDES = {
    "orchestrator": [HWB + "/skills/总控类/hwb-modeling-workflow/SKILL.md", "调研/README.md", MMA + "/backend/app/core/flows.py"],
    "researcher": [HWB + "/数模资料/优秀论文索引/README.md", "调研/文献总索引.md"],
    "modeler": [HWB + "/skills/生成类/hwb-modeling-ideas/SKILL.md", HWB + "/skills/论文自查类/hwb-model-dictionary/SKILL.md"],
    "coder": [MMA + "/backend/app/core/agents/coder_agent.py", HWB + "/skills/论文自查类/hwb-model-solution-checker/SKILL.md"],
    "visualizer": [WRITING, HWB + "/skills/论文自查类/hwb-paper-format-checker/SKILL.md"],
    "writer": [WRITING, HWB + "/skills/论文自查类/hwb-abstract-checker/SKILL.md", HWB + "/skills/论文自查类/hwb-reference-appendix-checker/SKILL.md"],
    "reviewer": [HWB + "/skills/论文自查类/hwb-review-paper/SKILL.md", HWB + "/skills/论文自查类/hwb-model-solution-checker/SKILL.md"],
    "redteam": [HWB + "/skills/论文自查类/hwb-model-assumption-checker/SKILL.md", HWB + "/skills/论文自查类/hwb-reference-appendix-checker/SKILL.md"],
}


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "tools/huaweicup.py").is_file() and (parent / "各种建模agent").is_dir():
            return parent
    raise ValueError("未找到 model_competition 仓库根；请从仓库内调用入口")


def guide_records(role: str, root: Path | None = None) -> list[dict]:
    if role not in GUIDES:
        raise ValueError("未知角色")
    root = (root or repository_root()).resolve()
    records = []
    for relative in GUIDES[role]:
        path = root / relative
        path.resolve().relative_to(root)
        found = path.is_file()
        records.append({"path": relative, "exists": found,
                        "sha256": digest(path) if found else None,
                        "reading_status": "host_must_read", "execute": False})
    return records


def paper_records(year: int | None = None, problem: str | None = None,
                  root: Path | None = None) -> list[dict]:
    """按原始索引查询；下载、阅读、奖项与数学正确性不相互推断。"""
    root = (root or repository_root()).resolve()
    path = root / LIBRARY / "index_match.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = []
    for row in rows:
        if year is not None and int(row["年份"]) != year:
            continue
        if problem is not None and row["题号"] != problem:
            continue
        result.append({"year": int(row["年份"]), "problem": row["题号"],
                       "id": row["论文/队伍编号"], "status": row["下载状态"],
                       "archive": LIBRARY + "/" + row["压缩包"] if row["压缩包"] else None,
                       "member": row["压缩包内路径"], "sha256": row["SHA256"],
                       "award_status": row["奖项核验"], "note": row["说明"]})
    return result
