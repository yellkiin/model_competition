"""不调用模型服务、不访问网络的完整工具链演练。"""
from __future__ import annotations

import csv
import shutil
import sys
import subprocess
from pathlib import Path

import numpy as np

from .core import initialize
from .publication import render, compile_tex
from .workflow import log_ai


def run_demo(root: str, compile_pdf: bool = False):
    ws = initialize(root)
    ws.path("problem.md").write_text("合成数据演练：用相同训练数据比较一次与二次回归；不用于竞赛评分。\n", encoding="utf-8")
    contract = ws.read("contract.json")
    contract.update(problem_id="DEMO", tasks=["比较拟合误差及结构消融"],
                    validation={"split_strategy": "independent train/validation/test",
                                "metric": "RMSE", "seeds": [42, 43, 44, 45, 46]})
    ws.write("contract.json", contract)
    # 方案先于数据和结果保存；实际赛题也必须先冻结选择规则。
    ws.write("notes/experiment_plan.json", {
        "status": "prespecified_demo", "baseline": "degree_1", "candidate": "degree_2",
        "hypothesis": "二次项能表示本演练预设的曲率；不宣称原创算法",
        "ablation": "删除二次项", "select_by": "validation RMSE",
        "forbidden": "根据 test 指标修改生成器或选择阶数", "seeds": [42, 43, 44, 45, 46]})
    with ws.path("inputs/synthetic.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["seed", "split", "x", "y"])
        for seed in (42, 43, 44, 45, 46):
            rng = np.random.default_rng(seed)
            for split, n in (("train", 160), ("validation", 40), ("test", 80)):
                x = rng.uniform(-2, 2, n)
                y = 1 + 2 * x + 0.6 * x**2 + rng.normal(0, 0.3, n)
                writer.writerows((seed, split, float(a), float(b)) for a, b in zip(x, y))
    ws.seal()
    source = Path(__file__).with_name("experiment.py")
    shutil.copyfile(source, ws.path("code/experiment.py"))
    subprocess.run([sys.executable, "code/experiment.py", "inputs/synthetic.csv",
                    "results/metrics.json"], cwd=ws.root, check=True, timeout=30)
    ws.record("results/metrics.json", ws.inputs() + ["code/experiment.py", "notes/experiment_plan.json"], "experiment")
    ws.write("claims.json", [{"id": "demo_comparison", "status": "supported",
                             "text": "完成预设模型、种子与划分的合成回归比较，不推断真实赛题表现。",
                             "source_ids": [], "evidence": ["results/metrics.json"]}])
    render(ws)
    log_ai(ws, "AI-assisted workbench implementation", "deterministic-demo-0.1",
           "执行预先写好的合成数据演练，不是模型 API 推理", ["paper/draft.tex"])
    if compile_pdf:
        compile_tex(ws, "paper/draft.tex", trusted=True)
    return ws
