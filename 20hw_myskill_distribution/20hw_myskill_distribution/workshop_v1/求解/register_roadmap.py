"""Register the actually rendered first-chapter route in the diagram plan."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT.parent
SIDECAR = ROOT / "求解/视觉计划.diagrams.json"
PLAN = ROOT / "求解/视觉计划.json"
PREFIX = ".agents/skills/sci-box-main/sci-box-main/skills/scibox-diagram/assets"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(raw: str, locator: str) -> dict:
    return {"path": raw, "sha256": sha(ROOT / raw), "locator": locator}


data = json.loads(SIDECAR.read_text(encoding="utf-8"))
assert not any(x["diagram_id"] == "GLOBAL-ROADMAP" for x in data["diagrams"])
refs = []
for name, observation, decision in [
    ("four-content-evidence-roadmap", "四层彩色横带各自包含左侧三项、中心要点、右侧三项；阶段之间单向连接，适合输入审计与三个递进场景。", "选用四层结构，把原示例政策建议替换为真实L2场景；缩短带间空白并提高字级。"),
    ("triple-band-research-validation", "三层证据带含中心分析与两侧模块，空白较大；本题审计加三场景共四层，压入三层会混淆场景。", "淘汰：需把两个独立场景挤入同一带，真实关系和论文尺寸均不如四层方案。"),
    ("four-stage-research-framework", "同为四层，但每层只有两列任务节点，难同时容纳候选构造、约束及评价三类信息。", "淘汰：四阶段数目适合，节点容量和证据对照不足。"),
]:
    raw = f"{PREFIX}/{name}/preview.png"
    refs.append({"path": raw, "sha256": sha(TEMPLATE / raw), "reviewed": True,
                 "observation": observation, "decision": decision})

panels = [
    ("input", "object", "题定二部计算图、100个算例、固定配置与方案合法性审计", "求解/题面约束清单.md", "共用问题定义；输入与评估边界", "左侧输入核查到右侧单核基准的研究起点，未使用示例数值。"),
    ("scene_a", "process", "独立Task的场景A：连通块、深度分段和独立块分批候选", "求解/求解计划.md", "共用计算与候选；逐问工作1", "场景A确为第一问，每子图一Task，右侧只写评价量。"),
    ("scene_b", "process", "同核复用的场景B：Task合并、跨核同步与容量核验", "求解/题面约束清单.md", "问题二：场景B", "场景B建立在切图方案上，但重新按合并Task规则评估。"),
    ("cache", "process", "共享只读L2：FIFO、容量和带宽响应及同方案比较", "求解/题面约束清单.md", "问题三：共享只读L2 Cache", "Cache仅供COPY_IN查询；改动配置的响应只作非官方分析。"),
]
diagram = {
    "diagram_id": "GLOBAL-ROADMAP", "problem_id": None, "kind": "flowchart", "placement": "body",
    "scientific_question": "题定三场景如何从共同图结构、合法方案及官方评估形成完整研究路线？",
    "backend": "drawio", "backend_reason": "选中scibox可编辑四内容模板，便于保持阶段色带、单向连接与论文矢量文字。",
    "source": "求解/总体路线图_紧凑.drawio",
    "dependencies": ["求解/总体路线图.drawio", "求解/总体路线图内容.json",
                     "求解/tighten_roadmap.py", "求解/preview_roadmap_page.py"],
    "outputs": {"vector": "求解/总体路线图_紧凑.pdf", "preview": "求解/总体路线图_紧凑.png"},
    "target_width_mm": 160,
    "sources": [source("求解/题面约束清单.md", "共用定义和问题一至三"),
                source("求解/求解计划.md", "共用计算与候选"),
                source("求解/数据审计.json", "cases数组包含100个官方图结构审计")],
    "references": refs,
    "panels": [
        {"panel_id": pid, "kind": kind, "content": content, "source_path": path,
         "source_locator": locator, "semantic_review": review}
        for pid, kind, content, path, locator, review in panels
    ],
    "connections": [
        {"from": a, "to": b, "type": "sequence", "meaning": meaning,
         "source_locator": locator}
        for a, b, meaning, locator in [
            ("input", "scene_a", "合法输入与固定单核基准先于场景A方案评价", "题面约束清单.md:问题一"),
            ("scene_a", "scene_b", "场景B沿用切图候选但按同核Task复用规则重评", "题面约束清单.md:问题二"),
            ("scene_b", "cache", "共享L2建立在场景B的Task与跨核同步结构上", "题面约束清单.md:问题三"),
        ]
    ],
    "flow_semantics": True,
    "paper": {"caption": "多核调度研究路线", "label": "fig:roadmap",
              "reference_context": "第一章1.2问题重述末段明确作为本文研究安排，并先引用后插图。"},
    "qa_path": "求解/总体路线图.qa.json", "status": "rendered",
    "template_selection_path": "求解/总体路线图模板选型.json",
}
data["diagrams"].append(diagram)
data["figure_accounting"].append({
    "figure_id": "GLOBAL-ROADMAP", "purpose": "global_roadmap", "problem_id": None,
    "per_question": False, "paper_total": True, "flow_total": True,
    "scientific_contribution": "以题定图结构和官方评估为基础，准确串联场景A、同核复用场景B与共享只读L2。",
})
SIDECAR.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
plan = json.loads(PLAN.read_text(encoding="utf-8"))
plan["flowcharts"] = [{"scope": "全篇", "needed": "yes", "reason": "三个问题有明确递进的任务组织和验证顺序。",
                       "plan_id": "GLOBAL-ROADMAP", "status": "rendered"}]
PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("GLOBAL-ROADMAP registered")
