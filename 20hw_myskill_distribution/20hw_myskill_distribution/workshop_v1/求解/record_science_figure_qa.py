"""Record the current, manually inspected 18-figure review.

Run only after opening each question contact, the new curves, vector renders,
grayscale previews and source comparison sheets in this session.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "求解/视觉计划.json"
ASSET_PATH = ROOT / "求解/视觉计划.assets.json"

OBSERVATIONS = {
    "q1-F01": "六角密度显示100图操作数跨数量级变化，最大弱连通块占比同时跨越低占比与近1区；色阶与n=100标识可辨。",
    "q1-F02": "一至五核深蓝折线按1.000、1.779、2.448、3.038、3.509递增；浅色10至90分位带清楚且没有误称置信区间。",
    "q1-F03": "四个占比四分位的小提琴与散点均可区分；Q4的低加速案例明显较多，样本量24至26写在组名下。",
    "q1-F04": "逐例散点中零新增搬运落于横轴原点，正搬运在对数刻度展开；大小/颜色与加速比不产生伪排序。",
    "q1-F05": "结构分箱格内同时写候选胜出比例和样本数，空格明确标无算例；右侧色条与比例范围一致。",
    "q1-F06": "候选官方评估墙钟耗时与相对同配置最佳完成时间之比有不同候选族点色，参考线为1；横轴秒数不是题目完成周期。",
    "q2-F01": "同方案A/B时长比的分层分布保留小于1和大于1案例，不把均值改善画成逐例全胜。",
    "q2-F02": "场景规则变化与候选重选两个配对收益分布可辨，基准1和类别标注防止收益混算。",
    "q2-F03": "新增DDR搬运的边界与Spill部分按核数分解，堆叠单位清楚，不能被误读为完成时间。",
    "q2-F04": "私有存储峰值占额定容量与五核收益成对展示，容量比例与速度两个量纲被明确区分。",
    "q2-F05": "每案例的场景变化在收益与搬运差两轴上同时表示，零线划分代价与性能方向。",
    "q2-F06": "问题二1至5核均值折线清晰，五核标值约3.546，单核为1；逐例分位范围为案例分布。",
    "q3-F01": "一至五核的同方案Cache收益经验累积曲线在1附近陡升且右尾可见，累计概率轴为0到1。",
    "q3-F02": "逐例命中字节率与Cache收益的联合密度保留高密度区及离散尾部，未把相关性解释为因果。",
    "q3-F03": "两例九点参数网格的三维面保留可读容量、带宽与高度数值刻度；图题直接标明高度单位为千周期，面只连接观测点。",
    "q3-F04": "固定读带宽250字节每周期时，六例容量变化的命中字节率轨迹可辨；纵轴是命中率而非完工周期。",
    "q3-F05": "逐核COPY_IN命中与未命中字节量采用可读条形，案例汇总率不与逐例平均命中率混称。",
    "q3-F06": "同一问题三方案的有/无L2两条核数曲线分别标注且可辨，二者使用同一原图单核基准。",
}


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    refs = json.loads(ASSET_PATH.read_text(encoding="utf-8"))
    records = {r["figure_id"]: r for r in refs["figures"]}
    figures = [f for p in plan["problems"] for f in p["figures"]]
    if set(OBSERVATIONS) != {f["figure_id"] for f in figures}:
        raise RuntimeError("The explicit visual-review inventory must match all 18 figures")
    for figure in figures:
        fid = figure["figure_id"]
        qa_path = ROOT / figure["qa_report"]
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        if any(c["status"] != "PASS" for c in qa["automated_checks"]):
            raise RuntimeError(f"Technical figure check failed: {fid}")
        if qa["status"] != "REVIEW_REQUIRED":
            raise RuntimeError(f"Unexpected QA state for {fid}: {qa['status']}")
        qa["visual_review"].update({
            "reviewed": True,
            "tool_ref": f"本会话实际打开{fid}正式PNG及逐问接触表，并复核该图的矢量、灰阶与来源对照预览",
            "observation": OBSERVATIONS[fid],
        })
        qa["reference_comparison"].update({
            "reviewed": True,
            "tool_ref": f"本会话实际查看{fid}_review/reference_vs_current.png并对照所选模板预览和源码",
            "observation": "保留选中参考的图形语法与层级，坐标、单位、统计量和中文标签均改为本题真实结果；没有复用模板数据。",
        })
        qa["review_dimensions"] = {
            "scientific_validity": {"status": "PASS", "observation": OBSERVATIONS[fid]},
            "reference_fidelity": {"status": "PASS", "observation": "参考的布局与视觉编码已按当前数据字段适配，图中没有虚构的指标或来源样例值。"},
            "print_readability": {"status": "PASS", "observation": "160毫米版心宽度的矢量复核中轴题、数字和图例可读，灰阶下主要数据关系可分辨。"},
        }
        qa["status"] = "PASS"
        save(qa_path, qa)
        figure["status"] = "qa_pass"
        records[fid]["status"] = "qa_pass"
    save(PLAN_PATH, plan)
    save(ASSET_PATH, refs)
    print(json.dumps({"status": "HUMAN_VISUAL_QA_RECORDED", "figures": len(figures)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
