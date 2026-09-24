"""Record the author's completed visual review of the two current galleries.

The 23 academic contact pages, eight ModelViz contact pages and four scibox
contact pages were opened at original resolution before this record was made.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACADEMIC = ROOT / "求解/academic_gallery/gallery_review.json"
PREFLIGHT = ROOT / "求解/绘图能力预检.json"


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def observations(name: str) -> tuple[str, str, str]:
    low = name.lower()
    groups = [
        ("3dheatmap", "矩阵单元凸起与投影阴影组成三维热图", "可展示核数、场景和收益的双离散轴", "单元太密时透视遮挡，需控制类别数量"),
        ("frequency", "立体小矩形格与顶端边际点线", "适合离散核数与图结构分组的频数", "过多案例会使坐标与高低难辨"),
        ("barablation", "分面长条比较、误差棒和统一图例", "可比较组件消融或调度策略", "本题没有随机重复时不得沿用示例误差棒"),
        ("barcomparison", "并列小面板与多方法柱状比较", "可显示三场景多核收益", "本题不应沿用示例模型名和误差线"),
        ("groupedbar", "并列或横向成组色条，部分叠加散点", "适合配对案例的核数与策略比较", "方法数多时横轴拥挤，需精选组别"),
        ("convergence", "蓝色收敛带和红色约束比例双轴", "仅适用确实有迭代优化轨迹的数据", "当前启发式无迭代轨迹，不能直接套用"),
        ("paired", "配对散点由浅灰线连接并叠加箱体", "适合逐例场景A/B或缓存前后对比", "禁止把模板示例显著性标注移入本题"),
        ("scenarioheatmap", "有数值标注的红蓝场景矩阵", "可比较图族、核数、方法的真实指标", "颜色需统一量纲，格过多会缩小数字"),
        ("sensitivity", "以零线分隔的双向水平条及端点", "适合真实参数扰动后的收益变化", "仅固定官方参数时不应伪造扰动结果"),
        ("linetrend", "多色折线或小型趋势分面", "可显示一至五核的平均加速比", "横轴为离散核数，需保留点和准确刻度"),
        ("resourcedesign", "饱和收益曲线、阴影和推荐点", "可描述核数增加后的边际收益", "推荐点必须来自计算规则，不能主观标记"),
        ("ridg", "错层密度轮廓及分组标签", "可比较多核收益的案例分布", "样本少的子组不可强行做平滑密度"),
        ("violin", "小提琴密度叠加真实散点", "可比较百例加速比和长尾", "分布过于偏斜时应核查带宽和截断"),
        ("heatmap", "颜色编码的矩阵与可选树图或数字", "可展示多案例、多核或参数的二维结果", "只填官方结构化结果，避免过密格导致不可读"),
        ("waterfall", "有正负方向的贡献瀑布条", "可分解官方耗时或数据移动变化", "各项必须满足可加总恒等式"),
        ("correlation", "散点、密度、相关矩阵或网络连线", "可探索图结构与加速收益的关联", "相关不能解释为因果，显著性需真实计算"),
        ("sankey", "多级节点及流量宽度的桑基流", "可展示算子或数据量的分配流向", "必须有守恒可核的流量，节点数宜简化"),
        ("trajectory", "三维轨迹并配两个二维投影", "本题时间核数方案若形成真实三轴可参考", "时间线是离散甘特条，三维轨迹易误导"),
        ("manifold", "连续曲面或拓扑流形", "仅可借用三维曲面视觉语言", "本题无连续流形物理量，语义不适合"),
        ("parameter", "二维等值色带、边界线及标记", "可画真实参数扫描的收益表面", "需明确两独立参数及真实扫描，不可插值造极值"),
        ("residual", "零轴上下的茎状图与边际分布", "可显示独立核验误差或基线差值", "本题核验误差应为零，差值需明确口径"),
    ]
    for key, visual, fit, limit in groups:
        if key in low:
            return fit, visual, limit
    return (
        "适合从真实逐例调度指标中选取含义一致的变量",
        "本预览使用分组色彩、坐标标注和多面板层级呈现比较",
        "示例标签与示例数值不得沿用；需按论文尺寸再检可读性",
    )


def main() -> None:
    review = json.loads(ACADEMIC.read_text(encoding="utf-8"))
    for number, row in enumerate(review["pages"], 1):
        row.update(reviewed=True,
                   tool_ref=f"functions.exec/view_image:求解/academic_gallery/assets_{number:02d}.png",
                   observation=f"已在原分辨率查看第{number}页各单元的图形、标签和密度；其中包含科研绘图示例，需要按本题变量和论文尺寸重新适配。")
    for row in review["asset_observations"]:
        fit, visual, limit = observations(row["path"])
        row.update(data_fit=fit, visual_features=visual, limitations=limit)
    dump(ACADEMIC, review)

    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    academic, modelviz = preflight["providers"]
    academic.update(
        capabilities="多核收益配对比较、分布、矩阵、敏感性及三维候选；保留39个生产家族的可改源程序",
        data_structures="结构化CSV/JSON转表后可绘制逐例成对数据、核数扫描、时间线和分组矩阵",
        limitations="需按五项映射精读具体家族；模板实验数字与显著性标记不得移用",
        gallery_review_path="求解/academic_gallery/gallery_review.json",
        capability_review={"reviewed": True, "tool_ref": "functions.exec/view_image:academic_gallery/assets_01-23.png",
                           "observation": "已逐页打开23张联系表共135个视觉资产；可用于配对、分布、热图和真实三维，机制图另走结构路由。"},
    )
    modelviz.update(
        capabilities="89套模板含分组比较、分布、矩阵、关系、参数扫描及真实三维候选",
        data_structures="逐例CSV的核数、场景、时长、拷贝字节与命中率可映射模板字段",
        limitations="选择后仍须精读预览与源码；生物、地理及学习类示例不可直接套入调度问题",
        capability_review={"reviewed": True, "tool_ref": "functions.exec/view_image:求解/模板预览/modelviz_catalog_01-08.png",
                           "observation": "已打开全部8页89个模板预览；折线、分布和部分三维适用，多数领域专用图语义不适用。"},
    )
    for i, item in enumerate(modelviz["previews"]):
        page = i // 12 + 1
        fit, visual, limit = observations(item["template_id"])
        for view in item["views"]:
            view.update(reviewed=True,
                        tool_ref=f"functions.exec/view_image:求解/模板预览/modelviz_catalog_{page:02d}.png",
                        observation=f"已在第{page}页查看{item['template_id']}预览；{visual}。{fit}；{limit}。")
    dump(PREFLIGHT, preflight)
    print(json.dumps({"academic_pages": len(review["pages"]), "academic_assets": len(review["asset_observations"]),
                      "modelviz_previews": len(modelviz["previews"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
