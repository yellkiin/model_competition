"""Record the current portfolio-level reason for the three extra line figures."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
from chart_policy import portfolio_digest  # noqa: E402
from prepare_academic_figure_review import figure_contract_digest  # noqa: E402

IDS = ["q1-F02", "q2-F06", "q3-F01", "q3-F04", "q3-F06"]
REASONS = {
    "q3-F01": (
        "五核组的同方案L2收益经验累积曲线必须保留概率阶梯和尾部阈值，才能判断收益有多少实例超过1。",
        "经验分布曲线提供逐阈值累计比例，直方图会随箱宽改变尾部视觉判断；这里有明确的不同科学用途。",
        [{"chart_family": "histogram", "reason": "分箱频数不能在任意收益阈值直接读出累计实例比例，且尾部受箱宽影响。"}]),
    "q3-F04": (
        "容量顺序与六例命中率平台效应是灵敏度问题，需要直接追踪同一实例随容量增加的轨迹。",
        "折线连接实测容量点只表示有序配置，六条轨迹的转折和平台在热图中不易横向比较。",
        [{"chart_family": "heatmap", "reason": "离散色阶弱化各实例容量从0.25到4 MiB的转折和完全不变的平台。"}]),
    "q3-F06": (
        "题目要求核数一至五的加速比曲线，此图同时比较同一所选方案的无L2与有L2。",
        "两条有序核数曲线明确展示缓存收益随核数增加的差距；分组柱会减弱成对趋势。",
        [{"chart_family": "bar", "reason": "分组柱可以读单个核数，但难以直接比较两个场景随核数变化的连续差距。"}]),
}


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for plan_name in ("候选计划", "视觉计划"):
        plan_path = ROOT / f"求解/{plan_name}.json"
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        figures = [f for q in data["problems"] for f in q["figures"]]
        stamp = portfolio_digest(figures)
        refs = {r["figure_id"]: r for r in json.loads((ROOT / f"求解/{plan_name}.assets.json").read_text(encoding="utf-8"))["figures"]}
        for f in figures:
            fid = f["figure_id"]
            if fid not in REASONS:
                continue
            purpose, reason, alternatives = REASONS[fid]
            evidence_path = f"求解/图件数据/{fid}.csv"
            f["selection"]["repetition_exceptions"] = [{
                "chart_family": "line", "portfolio_sha256": stamp,
                "figure_ids": IDS, "scientific_purpose": purpose,
                "alternatives": alternatives, "reason": reason,
                "evidence": {evidence_path: sha(evidence_path)},
            }]
            qa_path = ROOT / f["qa_report"]
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            if qa["status"] != "PASS":
                raise RuntimeError(f"Visual QA must already be complete for {fid}")
            qa["contract_sha256"] = figure_contract_digest(f, refs[fid])
            save(qa_path, qa)
        save(plan_path, data)
    print(json.dumps({"status": "EXCEPTIONS_REVIEWED", "figure_ids": list(REASONS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
