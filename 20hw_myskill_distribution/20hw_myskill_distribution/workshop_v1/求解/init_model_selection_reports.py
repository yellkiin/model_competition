"""Create C-class model-selection gate records for the three optimization tasks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main() -> None:
    evidence = {
        path: sha(path)
        for path in ("求解/题面约束清单.md", "求解/数据审计.json")
    }
    factors = {
        "task_type": "给定 DAG、核心数与资源约束的确定性组合优化，无待预测标签。",
        "modality": "100 个 JSON 计算图，含 Op、Tensor 和依赖边。",
        "sample_size": "100 个不同规模图是优化实例，并非独立监督训练样本。",
        "feature_dimension": "节点和边数量随图而变，非固定维度监督特征表。",
        "labels": "没有官方最优切图标签；模拟器输出仅是候选方案的目标函数值。",
        "quality": "100 图通过 ID、字段、非负值和无环审计；官方配置固定。",
        "nonlinearity": "Makespan 对切图、Pipe、缓存和共享带宽存在非线性耦合。",
        "structure": "计算图为 DAG，可直接利用拓扑、连通块和依赖层结构。",
        "architecture": "若训练 GNN 需可靠优质方案标签且推理可满足时间预算，现有输入不具备。",
        "advantage": "当前直接调用确定性官方仿真器可比较候选，学习型代理无已证优势。",
        "resources": "工作区可运行官方评估代码；无需 GPU 训练或额外依赖。",
        "time_budget": "100 图、1～5 核、三场景的官方全量评估优先，占用主要计算预算。",
    }
    for index, name in enumerate(("一", "二", "三"), 1):
        report = {
            "schema_version": "1.0",
            "question_id": f"q{index}",
            "purpose": "production",
            "status": "draft",
            "applicable": False,
            "eligibility": {
                "class": "C",
                "reason": "本问是有显式约束和官方仿真目标的计算图组合优化；100 个图不提供最优方案标签，直接评价候选方案可复核，学习模型没有可验证的训练目标。",
                "factors": factors,
            },
            "evidence": evidence,
            "budget": {
                "device": "CPU；未启用深度学习训练",
                "vram_mb": 4096,
                "seconds": 3600,
                "max_trials": 1,
                "strategy": "C 类不执行学习试验，采用官方模拟器评估确定性启发式方案。",
                "exception_reason": "",
            },
            "metrics": [],
            "candidates": [],
            "comparison_conditions": "两种确定性图划分启发式的比较另按官方固定配置逐例完成；本报告只登记学习模型适用性门控。",
            "main_model": None,
            "improved_model": None,
            "selection_reason": "直接仿真评价候选方案，按 Makespan 和新增搬运量选择。",
            "tradeoffs": "依赖段切分增加并行性，也可能增加边界搬运与同步等待。",
            "ml_omission_reason": "缺少独立的最优方案标签与合适的验证划分。",
        }
        output = ROOT / f"求解/问题{name}/结果/model_selection_report.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
