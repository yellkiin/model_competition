"""Record a current, manually inspected cross-question candidate review."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
from candidate_figures import inventory

SCOPES = [
    "求解/solve_components.py", "求解/solve_bands.py", "求解/solve_batches.py",
    "求解/run_official_experiments.py", "求解/verify_official_results.py",
    "求解/analyze_official_results.py", "求解/cache_sensitivity.py",
    "求解/analyze_cache_sensitivity.py", "求解/build_figure_data.py",
    "求解/render_science_figures.py", "求解/build_deep_evidence.py",
    "求解/build_crosscheck_tables.py", "求解/正式实验/总体摘要.json",
    "求解/正式实验/统计分析.json", "求解/正式实验/逐问核验摘要.json",
    "求解/正式实验/深度分析.json", "求解/正式实验/交叉核查.json",
    "论文/章节内容/04_问题一.tex", "论文/章节内容/05_问题二.tex",
    "论文/章节内容/06_问题三.tex", "论文/章节内容/07_模型评价与展望.tex",
]

path = ROOT / "求解/候选图清单.json"
registry = json.loads(path.read_text(encoding="utf-8"))
registry["final_review"] = {
    "observation": (
        "实际复查三问正式源码、100例结构化结果、独立核验、深度及交叉核查表与正文主张，"
        "并打开图库核对18张合格正文科学图。问题一的结构反例与规模分布、问题二的同方案A/B"
        "及候选搬运构成、问题三的固定方案Cache收益及非官方网格边界均在图表和正文中对应。"
        "七维复查未发现新的独立且已有真实数据支持、需要另图表达的科学问题；"
        "没有把早期未登记的数值阶段回填为候选事件。文件清单只证明当前版本一致，不替代科学审阅。"
    ),
    "question_ids": ["q1", "q2", "q3"],
    "scopes": SCOPES,
    "files": inventory(ROOT, SCOPES),
}
path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(registry["final_review"]["files"]))
