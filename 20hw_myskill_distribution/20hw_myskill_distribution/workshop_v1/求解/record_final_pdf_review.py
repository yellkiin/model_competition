"""Record observations made from the final 61-page PDF and its exact renders."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "论文/论文.pdf"
PAPER = ROOT / "论文/验收输出/图形入文.v4.review.json"
FIRST = ROOT / "论文/验收输出/前三章.v4.review.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


PAGE_NOTES = {
    5: "问题背景给出二部依赖图、私有存储及场景差别；1.2在页下开始，标题后仍有完整任务文字，未孤立。",
    6: "1.2连续交代三问的输入、方案、指标与复现要求；路线图引句在正文末，页下留白来自下一页的整幅路线图，无缺段或裁切。",
    7: "图1.1在独立页居中；四带依次是共用图与评估口径、场景A、场景B、共享L2，箭头和图题可辨。",
    8: "路线图后的衔接段位于本页页首，使第一章内容页连续；模型假设随即说明其工作假设性质。符号章同页接排，表3.1题名、表头及首行同页，列宽无溢出。",
    9: "符号表续页沿用表3.1编号与四列表头；容量、带宽和指标单位完整，末尾表注在底线外且未孤立。",
    10: "第四章在新页有问题文字与问题一综合图；顶部DAG、中部方法、底部两张实测缩图和图题均在版心内。",
    38: "评价章优点和缺点各有四条具体依据，官方100例成绩、成对反事实和方法边界分开表述；标题、编号与行间无碰撞。",
    39: "推广与改进为两个自然段，分别写迁移前提与后续实验；本页下方留白由参考文献另起页形成，正文无截断。",
}

SYMBOL_NOTES = {
    8: "首段表题居中、顶线与表头分隔线、底线清楚，类别与单一符号逐行对应，无竖线及缩放挤压。",
    9: "续表重复表头并保留同一表号；最终注在底线下。局部裁图左缘紧贴注字，整页PDF可确认完整的‘注：’及内容。",
}

EVALUATION_NOTES = {
    "advantages_evidence": ("第7.1节四点分别落实官方Makespan、同方案反事实、500份所选方案复核与结构异质性；三问五核均值写明样本范围。", ["论文/论文.pdf:38", "论文/章节内容/07_模型评价与展望.tex:7.1"]),
    "limitations_causes_impacts": ("第7.2节四点说明有限候选的最优性边界、粗负载与资源争用、六例参数网格外推范围以及题定模拟语义依赖，均写出可能影响。", ["论文/论文.pdf:38", "论文/章节内容/07_模型评价与展望.tex:7.2"]),
    "transfer_conditions": ("第7.3节首段列明迁移需重建合法性、存储层级、Pipe并发、固定开销及评估接口，且明确数值加速结论不能直接迁移。", ["论文/论文.pdf:39", "论文/章节内容/07_模型评价与展望.tex:7.3首段"]),
    "improvement_paths": ("第7.3节次段提出自适应切分、局部合并/迁核/重排与跨容量带宽重优化，并要求固定案例和评估预算下成对核验。", ["论文/论文.pdf:39", "论文/章节内容/07_模型评价与展望.tex:7.3次段"]),
    "verified_vs_proposed": ("第7.1—7.2节的100例正式成绩、500份逐问复核与六例非官方网格均标出性质；第7.3节用‘后续可’和‘宜’表达尚未运行的改进。", ["论文/论文.pdf:38", "论文/论文.pdf:39"]),
    "substance_without_padding": ("第38页逐条解释真实证据与机制，第39页给出可执行迁移条件和改进实验；净正文测量约1.15页，未用扩大间距或重复句填页。", ["论文/论文.pdf:38", "论文/论文.pdf:39"]),
}

FIGURE_NOTES = {
    "q1-F01": "第12页六边形图呈现非COPY操作规模与最大连通块占比，轴与色标可见，图题在图下。",
    "q1-F02": "第13页上图的1—5核均值折线与案例分位阴影均在坐标区内，标值与图题清楚。",
    "q1-F03": "第13页下图以四组小提琴和散点呈现结构分层，基准线、分组样本量和图题可辨。",
    "q1-F04": "第14页上图展示五核加速与新增DDR搬运的散点，坐标和颜色条完整。",
    "q1-F05": "第14页下图的二维分箱胜率矩阵显示样本数与百分比，色标和图题未裁切。",
    "q1-F06": "第15页散点给出候选评估时间与相对质量，族名图例在版心内。",
    "q2-F01": "第21页下图逐核展示同方案场景A/B时长比分布，基准线、核数及图题可见。",
    "q2-F02": "第22页上图保留场景B重选收益的少量严格改善点与大量接近1的实例，刻度和图题可辨。",
    "q2-F03": "第22页下图用双色面积分开边界COPY与Spill，四个核数和MiB单位完整。",
    "q2-F04": "第23页上图以容量峰值比例、点色和纵轴收益构成资源散点，色标未越界。",
    "q2-F05": "第23页下图的速度—搬运成对坐标、零参考线与点均完整。",
    "q2-F06": "第21页上图的1—5核平均加速比折线在正文宽度内，标值和图题清楚。",
    "q3-F01": "第30页下图有L2与无L2的经验累积分布逐核叠加，图例、刻度和图题可读。",
    "q3-F02": "第31页六边形图与离散点显示命中字节率—同方案收益关系，色标完整且图题未截断。",
    "q3-F03": "第35页两幅非官方容量—带宽响应面并列，案例044/083标识及三维轴可见。",
    "q3-F04": "第36页六例固定带宽容量响应折线及图例在版心内，图题注明命中率。",
    "q3-F05": "第32页堆叠条展示各核数命中和未命中查询字节，百分比标签与图例清楚。",
    "q3-F06": "第30页上图为同方案无L2与有L2的逐核平均加速比两条线，图例和图题完整。",
    "GLOBAL-ROADMAP": "第7页总体路线图四带居中，场景与任务次序、箭头、图题均清晰，无截断。",
    "q1-OVERVIEW": "第10页问题一综合图的DAG、切图方法、两张真实结果缩图与正文图号对应，图题位置正常。",
    "q2-OVERVIEW": "第19页问题二综合图的同核Task合并、跨核COPY及结果缩图按三带排列，图题与正文分开。",
    "q3-OVERVIEW": "第28页问题三综合图分开L2命中/未命中读路径，官方与非官方结果缩图在底带，图题完整。",
}


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    paper = json.loads(PAPER.read_text(encoding="utf-8"))
    first = json.loads(FIRST.read_text(encoding="utf-8"))
    assert sha(PDF) == paper["pdf_sha256"] == first["pdf_sha256"]
    assert paper["pdf_pages"] == 61
    assert {x["physical_page"] for x in first["pages"]} == set(PAGE_NOTES)
    assert {x["physical_page"] for x in first["symbol_crops"]} == set(SYMBOL_NOTES)
    assert {x["figure_id"] for x in paper["figures"]} == set(FIGURE_NOTES)
    assert set(first["evaluation_content_review"]) == set(EVALUATION_NOTES)
    sys.path.insert(0, str((ROOT / "../华为杯_论文规范模板/tools").resolve()))
    from audit_pdf_layout import audit_layout
    layout = audit_layout(PDF, ROOT / "论文/论文.tex", ROOT / "论文/论文输入.json")
    assert layout["status"] == "PASS"
    first["local_symbol_definitions"] = layout["first_chapters_source"]
    for row in first["pages"]:
        n = row["physical_page"]
        row.update(reviewed=True, tool_ref=f"functions.view_image:论文/验收输出/前三章.v4.review_pages/page_{n:03d}.png", observation=PAGE_NOTES[n], issues=[])
    for row in first["symbol_crops"]:
        n = row["physical_page"]
        row.update(reviewed=True, tool_ref=f"functions.view_image:论文/验收输出/前三章.v4.review_pages/symbol_{n:03d}.png", observation=SYMBOL_NOTES[n], issues=[])
    for key, (observation, locations) in EVALUATION_NOTES.items():
        first["evaluation_content_review"][key] = {"status": "verified", "observation": observation, "evidence_locations": locations}
    first.update(status="PASS", recheck="complete", reviewed_at=now)
    for figure in paper["figures"]:
        note = FIGURE_NOTES[figure["figure_id"]]
        for row in figure["occurrences"]:
            page = row["page_number"]
            start = (page - 1) // 8 * 8 + 1
            end = min(start + 7, 61)
            row.update(reviewed=True, tool_ref=f"functions.view_image:论文/验收输出/final-visual-v4/contact-{start:02d}-{end:02d}.png; {row['page_render_path']}", observation=note)
    paper["portfolio_review"] = {
        "reviewed": True,
        "tool_ref": "functions.view_image:论文/验收输出/final-visual-v4/contact-01-08.png 至 contact-57-61.png（8张；全61页）",
        "observation": "逐页查看最终61页：摘要2页、动态目录2页、正文35页、参考文献1页和代码附录21页；22个图件均落在对应问题正文，三问综合图在首节，科学图轴题与图题可见，附录代码可分页，无空白页、明显遮挡或跨版心截断。第27页和第39页因章节自然结束留白，内容未重复凑页。",
    }
    paper.update(status="PASS", reviewed_at=now)
    save(FIRST, first)
    save(PAPER, paper)
    print("Recorded actual final PDF review:", len(first["pages"]), "pages,", len(first["symbol_crops"]), "symbol crops,", len(paper["figures"]), "figures")


if __name__ == "__main__":
    main()
