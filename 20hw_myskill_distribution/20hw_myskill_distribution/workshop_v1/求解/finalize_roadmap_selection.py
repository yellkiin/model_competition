"""Record the reviewed template gallery and the A-problem adaptation."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
record_path = HERE / "总体路线图模板选型.json"
record = json.loads(record_path.read_text(encoding="utf-8"))
assert record["status"] == "pending"
observations = [
    "五带上下串联，阶段和证据节点很多；缩到A4后信息密度偏高。",
    "三栏纵向组织，多次横向连接；更适合研究框架而非三场景的连续评估。",
    "三栏阶段纵排，每层内有分工节点；与四个内容阶段并非直接匹配。",
    "横向长画布与任务流水，论文A4竖版缩放会显著压小文字。",
    "三栏的行为干预研究链，分区含案例文字；当前硬件场景映射成本高。",
    "纵向耦合方法与实验框架，内部文字较密，适合单模型而非三种场景。",
    "立方体与交集图元突出模型关系，本题四阶段顺序不宜用交叠语义。",
    "五阶段自上而下包含数据、模型和部署，节点比本题三场景需求多。",
    "药物发现主题三平面和立体透视突出领域对象，不适合调度流程。",
    "双圆重叠结构表达交集，不能准确对应单向场景递进。",
    "双圆重叠变体仍以交集为主，缺少独立Task到Cache的顺序主线。",
    "双环分层平台包含左右循环与反馈，本题没有对应真实闭环。",
    "双研究筒状路线强调并列研究与输出，三问有真实前后条件变化。",
    "三带生态旅游整合采用较大的矩形内容块，压入三场景会遗漏输入审计。",
    "五带特征检测路线有多层箭头与局部判断，信息比当前总览所需复杂。",
    "三带实地研究链含资料、研究、成果，无法逐一对应输入和三场景。",
    "五章路线为重复分带小节点，增加一层并未改善本题A4的文字容量。",
    "四带方法路线图中间为复杂机制，适合方法章节而非问题重述总览。",
    "四层横带各有左三项、中心要点、右三项，并以单向箭头串联。",
    "四阶段带每层只有左右各两项，无法同时呈现候选、约束和评价。",
    "同心圆和分层环适合系统层次，不表达从场景A到L2的顺序。",
    "五带六边形研究链包含抽象交互单元，缩小后的新绘字较密。",
    "五阶段创新链有跨层长箭头，本题若套入会添加没有证据的创新环节。",
    "六阶段模型优化带数超过输入加三问的真实内容，容易制造额外步骤。",
    "港口可持续与质量房屋为领域综合分区，定量图和对象与本题不匹配。",
    "三栏证据卡片带小统计图，适合已有多图成果摘要，不适合首章题意。",
    "纵向研究设计闭环只有一条狭窄主轴，难容纳三场景并行约束。",
    "五带研究框架多层详细节点，论文首章总览文字会过小。",
    "五阶段研究方法路线可表达流程，较四带增加无题定阶段。",
    "五带棱镜式研究阶段更偏多方案对照，本题阶段数为输入加三问。",
    "三带实验路线组织清晰，但只能合并输入审计与一问。",
    "三带研究验证图有左右三项，第四个真实内容带缺位。",
]
assert len(record["gallery"]) == len(observations) == 32
for index, (item, observation) in enumerate(zip(record["gallery"], observations)):
    sheet = index // 8 + 1
    item.update({"reviewed": True, "observation": observation,
                 "tool_ref": f"functions.exec/view_image:求解/模板预览/scibox_catalog_0{sheet}.png"})
record["candidates"] = [
    {"template_id": "four-content-evidence-roadmap",
     "fit": "四个内容带与输入审计、场景A、场景B、共享L2逐一对应；左右三项足够放方法和评价。",
     "decision": "采用并保留四色标题带、虚线分区、中心要点和单向箭头；压缩无效空白并放大字体。"},
    {"template_id": "triple-band-research-validation",
     "fit": "三带有左输入、中心结果与右输出，真实问题却有输入及三种不同硬件场景。",
     "decision": "不采用，若把场景A/B合入同带，会模糊同核复用与独立Task的关键条件。"},
    {"template_id": "four-stage-research-framework",
     "fit": "四带数量匹配，但每带只有两组左右节点，无法同时呈现候选、约束和官方指标。",
     "decision": "不采用；节点容量不足，所选四内容证据链可在A4尺寸保留更清楚的对应关系。"},
]
record["adaptation"] = {
    "rationale": "以输入审计加题定三问构成真实四阶段，场景B依赖A的切图候选，L2建立在B的Task结构上。",
    "preserved_style": "沿用模板的海军蓝总题、紫绿橙红阶段标题、浅色中心块、左右证据卡片和纵向单箭头。",
    "changes": "替换全部示例术语；将四阶段映射到当前赛题；原版底部空白较大，压缩带间距与画布并把节点字体由18提至22以适配160毫米版心。",
    "semantic_mapping": [
        {"panel_id": "input", "template_slot": "第一条内容带：左三项—中心—右三项",
         "adaptation": "对应二部图与固定配置审计、合法输入、100算例和单核基准。"},
        {"panel_id": "scene_a", "template_slot": "第二条内容带：左三项—中心—右三项",
         "adaptation": "对应场景A三类切图候选、方案生成及Task等待、DDR搬运、Makespan。"},
        {"panel_id": "scene_b", "template_slot": "第三条内容带：左三项—中心—右三项",
         "adaptation": "对应场景B同核Task、跨核同步、缓存驻留与配对评价。"},
        {"panel_id": "cache", "template_slot": "第四条内容带：左三项—中心—右三项",
         "adaptation": "对应共享只读L2的FIFO、容量/带宽响应、同方案对照和候选切换。"},
    ],
}
record["status"] = "reviewed"
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("roadmap template selection reviewed")
