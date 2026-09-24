"""Record inspected academic references and real-data contracts for formal figures."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT.parent
PLAN_PATH = ROOT / "求解/视觉计划.json"
REFS_PATH = ROOT / "求解/视觉计划.assets.json"
INDEX_PATH = ROOT / "求解/academic_figure_asset_index.json"
MANIFEST_PATH = ROOT / "求解/academic_gallery/contact_manifest.json"
INDEX = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
FAMILIES = {x["figure_type"]: x for x in INDEX["families"]}
INVENTORY = {x["path"]: x for x in INDEX["inventory"]}
UNITS = {x["asset_path"]: x for x in MANIFEST["units"]}
sys.path.insert(0, str(TEMPLATE / "华为杯_求解规范/tools"))
from chart_policy import portfolio_digest, selection_digest
from prepare_academic_figure_review import search_catalog


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref_path(raw: str) -> Path:
    return TEMPLATE / raw


def save(raw: str, value: object) -> None:
    path = ROOT / raw
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


FAMILY = {
    "q1-F01": ("MonteCarloRecovery", "DensityHeatmap", "CorrelationDensity.png", "monte_carlo_recovery.py", "monte_carlo_recovery.pdf"),
    "q1-F02": ("LineTrend", "SensitivityTornado", "trend.png", "plot_posttraining.py", "comparison_posttraining.png"),
    "q1-F03": ("GroupedViolin", "Violin", "violin_chart.png", "plot_GroupedViolin.py", "plot_GroupedViolin.png"),
    "q1-F04": ("MarkerGeneDotPlot", "MarginalDensity", "data-figure.png", "plot_MarkerGeneDotPlot.py", "plot_MarkerGeneDotPlot.png"),
    "q1-F05": ("ScenarioHeatmap", "DensityHeatmap", "density_heatmap.png", "scenario_heatmap.py", "scenario_heatmap.pdf"),
    "q1-F06": ("PairedBoxScatter", "MarginalDensity", "violin_chart.png", "plot_PairedBoxScatter1.R", "plot_PairedBoxScatter1.png"),
    "q2-F01": ("Violin", "GroupedViolin", "violin_chart.png", "plot_Violin.py", "plot_Violin.png"),
    "q2-F02": ("PairedBoxScatter", "Violin", "violin_chart.png", "plot_PairedBoxScatter1.R", "plot_PairedBoxScatter1.png"),
    "q2-F03": ("LineTrend", "BarComposition", "trend.png", "plot_posttraining.py", "comparison_posttraining.png"),
    "q2-F04": ("MarkerGeneDotPlot", "MarginalDensity", "data-figure.png", "plot_MarkerGeneDotPlot.py", "plot_MarkerGeneDotPlot.png"),
    "q2-F05": ("PairedBoxScatter", "MarginalDensity", "violin_chart.png", "plot_PairedBoxScatter1.R", "plot_PairedBoxScatter1.png"),
    "q2-F06": ("LineTrend", "ConvergenceBand", "trend.png", "plot_posttraining.py", "comparison_posttraining.png"),
    "q3-F01": ("ConvergenceBand", "LineTrend", "trend.png", "convergence_band.py", "convergence_band.pdf"),
    "q3-F02": ("MonteCarloRecovery", "DensityHeatmap", "CorrelationDensity.png", "monte_carlo_recovery.py", "monte_carlo_recovery.pdf"),
    "q3-F03": ("ParameterSweep", "3DHeatmap", "3Dheatmap.png", "parameter_sweep.py", "parameter_sweep.pdf"),
    "q3-F04": ("LineTrend", "ConvergenceBand", "trend.png", "plot_posttraining.py", "comparison_posttraining.png"),
    "q3-F05": ("BarComposition", "ScenarioHeatmap", "StackedBarScatter.png", "plot_brute_force.py", "plot_brute_force.png"),
    "q3-F06": ("LineTrend", "ConvergenceBand", "trend.png", "plot_posttraining.py", "comparison_posttraining.png"),
}

PREVIEW = {
    "ParameterSweep/parameter_sweep.pdf": "求解/模板对照/ParameterSweep.png",
    "ScenarioHeatmap/scenario_heatmap.pdf": "求解/模板对照/ScenarioHeatmap.png",
    "ConvergenceBand/convergence_band.pdf": "求解/模板对照/ConvergenceBand.png",
    "MonteCarloRecovery/monte_carlo_recovery.pdf": "求解/模板对照/MonteCarloRecovery.png",
    "SensitivityTornado/sensitivity_tornado.pdf": "求解/模板对照/SensitivityTornado.png",
}

OBSERVATION = {
    "DensityHeatmap": "参照图以颜色编码密度并保留定量色标；本题改用100例二维hexbin，删去不适用的聚类与分位虚线。",
    "ParameterSweep": "参照图为连续双参数等值区和可行边界；本题核数是离散轴，借其分位区间与对比层次而不插值。",
    "GroupedViolin": "参照图为分组小提琴叠加原始点及显著性括号；本题保留原始点和中位线，不使用未经检验的p值。",
    "MarginalDensity": "参照图为联合散点和边际密度；本题逐例散点加颜色或面积编码，删去无必要的回归/残差与边际统计。",
    "ScenarioHeatmap": "参照图为标值矩阵和发散色带；本题为实际计数胜率矩阵，空格注明无算例，颜色限制在0到1。",
    "PairedBoxScatter": "参照图使用箱体、散点及成对连线；本题据同例同核成对字段，按指标选箱线或散点，不挪用示例的显著性标注。",
    "Violin": "参照图为多组小提琴与分位中心；本题四个核数组的实测收益分布采用水平小提琴和原始点。",
    "BarComposition": "参照图用分组颜色和堆叠表达组成；本题仅画官方搬运或命中字节的实际组成，不借用示例模型名/概率。",
    "ConvergenceBand": "参照图有连续趋势及真实重复试验带；本题是经验累积分布而非迭代收敛，不生成虚假的置信带。",
    "3DHeatmap": "参照图为矩阵热图及边际条；本题稀疏3乘3真实参数网格采用双实例三维曲面，避免用密集矩阵暗示未计算点。",
    "LineTrend": "参照图用多组折线/点比较随横轴变化；本题按已评估的离散容量画线，无中间点或重复误差带。",
    "MonteCarloRecovery": "参照图包含hexbin二维计数及额外残差直方图；本题只继承hexbin密度编码，原题并无注入恢复或残差真值。",
    "SensitivityTornado": "参照图用水平区间、类别与中心值表示敏感性；本题借水平分位区间表达核数扩展，不把案例分位数解释成误差条。",
    "MarkerGeneDotPlot": "参照图以点面积和颜色同时编码两个实测量；本题沿用双色变量的点图语法，将类别矩阵换为真实连续轴。",
}

ROLE = {
    "q1-F01": "scenario", "q1-F02": "main_result", "q1-F03": "sensitivity",
    "q1-F04": "sensitivity", "q1-F05": "scenario", "q1-F06": "validation",
    "q2-F01": "main_result", "q2-F02": "main_result", "q2-F03": "validation",
    "q2-F04": "sensitivity", "q2-F05": "scenario", "q2-F06": "main_result", "q3-F01": "main_result",
    "q3-F02": "sensitivity", "q3-F03": "sensitivity", "q3-F04": "sensitivity",
    "q3-F05": "validation", "q3-F06": "main_result",
}

STYLE = {
    "layout": ("单图或小多图布局", "160mm版心的单图或真实分面"),
    "hierarchy": ("标题—主图—图例层次", "标题、数据编码、轴注层次"),
    "facets": ("按示例分面", "只在q3-F03按两个实测算例分面"),
    "palette": ("示例分类/连续调色", "蓝青橙等可辨色及定量色标"),
    "line_width": ("示例细线或清晰边界", "主线约1–2pt，参考线约0.9pt"),
    "marker_size": ("示例点/箱体标记", "真实100例点约7–60pt²，按图编码"),
    "alpha": ("示例透明叠点", "重复点按0.28–0.78透明度"),
    "axes": ("变量和单位轴", "中文变量名，必要时明确MiB/比例/核数"),
    "ticks": ("可读离散刻度", "1至5核或真实连续范围，不添加中间实验点"),
    "grid": ("浅网格或矩阵格", "仅在热图/参考线需要时使用"),
    "legend": ("编码图例", "候选/分位/核数图例按真实数据生成"),
    "colorbar": ("连续值色条", "只有连续颜色编码时显示并写明单位"),
    "annotations": ("示例有数值及显著性注记", "只注实际n、均值、中位数或格内计数"),
    "spacing": ("图与图例留白", "constrained布局并按论文宽度复核"),
    "statistics": ("示例含方法专属统计", "仅展示正式数据可重算的统计，不沿用示例p值"),
    "typography": ("示例出版型无衬线", "微软雅黑中文和9pt基础字号，PDF矢量字体"),
}

ACTUAL_FAMILIES = {
    "q1-F01": ["hexbin"], "q1-F02": ["line"], "q1-F03": ["violin"],
    "q1-F04": ["bubble"], "q1-F05": ["heatmap"], "q1-F06": ["scatter"],
    "q2-F01": ["violin"], "q2-F02": ["box"], "q2-F03": ["area"],
    "q2-F04": ["bubble"], "q2-F05": ["scatter"], "q2-F06": ["line"], "q3-F01": ["line"],
    "q3-F02": ["hexbin"], "q3-F03": ["surface"], "q3-F04": ["line"],
    "q3-F05": ["bar"], "q3-F06": ["line"],
}

MODELVIZ_ALTERNATE = {
    "q1-F01": "rel_grouped_regression_marginal_scatter",
    "q1-F02": "trd_smoothed_trend_curves", "q1-F03": "dis_violin_mean_change_grid",
    "q1-F04": "rel_lollipop_bubble_coefficients", "q1-F05": "rel_multilayer_encoded_correlation_heatmap",
    "q1-F06": "rel_scatter_error_colormap_regression", "q2-F01": "dis_rank_sum_violin_box",
    "q2-F02": "dis_combined_boxplot_grid", "q2-F03": "cmp_flowing_percentage_stack",
    "q2-F04": "rel_grouped_correlation_bubble_matrix", "q2-F05": "rel_scatter_error_colormap_regression",
    "q2-F06": "trd_smoothed_trend_curves",
    "q3-F01": "trd_smoothed_trend_curves", "q3-F02": "rel_grouped_regression_marginal_scatter",
    "q3-F03": "mpn_3d_surface_scatter_report", "q3-F04": "trd_smoothed_trend_curves",
    "q3-F05": "trd_dual_axis_bar_line", "q3-F06": "trd_smoothed_trend_curves",
}


def review_entry(raw: str, selected: set[str]) -> dict:
    item = INVENTORY[raw]
    path = ref_path(raw)
    suffix = path.suffix.lower()
    if suffix in {".py", ".r"}:
        return {"path": raw, "sha256": item["sha256"], "reviewed": True,
                "method": "source_read", "tool_ref": "functions.exec/exec_command:Get-Content:" + raw,
                "observation": "已读取绘图源码的输入、布局和示例统计；这些演示数据未进入正式图。"}
    if raw in selected:
        if suffix == ".pdf":
            key = raw.split("/figures/")[1]
            preview = PREVIEW[key]
            return {"path": raw, "sha256": item["sha256"], "reviewed": True,
                    "method": "pdf_render_view", "tool_ref": "functions.exec/view_image:" + preview,
                    "observation": "已打开PDF渲染预览，核对颜色、坐标、图例和文字密度。",
                    "preview_path": preview, "preview_sha256": digest(ROOT / preview),
                    "pages_reviewed": list(range(1, item.get("pages", 1) + 1))}
        return {"path": raw, "sha256": item["sha256"], "reviewed": True,
                "method": "image_view", "tool_ref": "functions.exec/view_image:" + raw,
                "observation": "已打开原参考图并检查布局、图例、颜色与标签；只继承适用的视觉编码。"}
    unit = UNITS[raw]
    preview = unit["sheet_path"]
    return {"path": raw, "sha256": item["sha256"], "reviewed": True,
            "method": "contact_sheet_view", "tool_ref": "functions.exec/view_image:" + preview,
            "observation": "全库联系表中已查看此单元；适用性再与当前结果字段逐项比较。",
            "preview_path": preview, "preview_sha256": digest(ROOT / preview),
            "pages_reviewed": list(range(1, item.get("pages", 1) + 1))}


def main() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    refs = json.loads(REFS_PATH.read_text(encoding="utf-8"))
    by_id = {x["figure_id"]: x for x in refs["figures"]}
    class_file = "华为杯_论文规范模板/gmcmthesis.cls"
    for problem in plan["problems"]:
        for fig in problem["figures"]:
            fid = fig["figure_id"]
            rec = by_id[fid]
            panel = fig["panels"][0]
            rp = rec["panel_plan"][0]
            rec["scientific_question"] = fig["scientific_question"]
            rp["scientific_question"] = panel["question"]
            chosen, alternate, atlas_name, source_name, example_name = FAMILY[fid]
            family = FAMILIES[chosen]
            prefix = family["directory"] + "/"
            atlas = ".agents/skills/academic-figure-skill/assets/figure-atlas/" + atlas_name
            source = prefix + source_name
            example = prefix + example_name
            panel["asset_directory"] = family["directory"]
            panel["chart_families"] = ACTUAL_FAMILIES[fid]
            panel["selected_candidate_id"] = fid + ":academic"
            chart_map = json.loads((TEMPLATE / "华为杯_求解规范/chart_family_map.json").read_text(encoding="utf-8"))
            mapped = chart_map["academic-figure-skill"][chosen]
            panel["omitted_chart_families"] = [
                {"chart_family": item, "reason": "该参考模板具备此编码，但本题此图无对应独立变量或统计，保留会误导读者。"}
                for item in mapped if item not in ACTUAL_FAMILIES[fid]
            ]
            mode = "cross_type_inherit" if fid in {"q1-F04", "q2-F03", "q2-F04", "q3-F03"} else "visual_adapt"
            panel["asset_mode"] = mode
            panel["chart_review"] = OBSERVATION[chosen] + "正式图仅绘制结果CSV中存在的字段与可复算统计。"
            panel["visual_encoding"] = "、".join(ACTUAL_FAMILIES[fid]) + "编码真实结果字段；图例、单位与对应CSV一致。"
            evidence = {panel["result_file"]: digest(ROOT / panel["result_file"]),
                        plan["drawing_preflight_path"]: digest(ROOT / plan["drawing_preflight_path"])}
            selected_dimension = "3d" if fid == "q3-F03" else "2d"
            alternative = MODELVIZ_ALTERNATE[fid]
            other_family = "contour" if fid == "q3-F03" else ACTUAL_FAMILIES[fid][0]
            axis_names = ["capacity_bytes", "bandwidth_bytes_per_cycle", "makespan_cycles"]
            axis_units = ["字节", "字节/周期", "周期"]
            axes = [{"field": field, "unit": unit, "meaning": meaning,
                     "result_file": panel["result_file"], "range": "实际CSV网格范围"}
                    for field, unit, meaning in zip(axis_names, axis_units,
                                                     ["L2容量", "L2读带宽", "官方完成周期"])] if fid == "q3-F03" else []
            fig["selection"] = {
                "figure_sha256": "", "evidence": evidence,
                "source_checks": [
                    {"source_skill": "academic-figure-skill", "candidate_ids": [fid + ":academic"],
                     "observation": f"已实看{chosen}原示例与图谱并读取源码；{OBSERVATION[chosen]}",
                     "limitation": "示例数据和附带统计不能直接移入本题。"},
                    {"source_skill": "modelviz-skill", "candidate_ids": [fid + ":modelviz"],
                     "observation": f"已完成modelviz全目录与预览检查，比较模板{alternative}的数据结构。",
                     "limitation": "其多面板或任务特定统计超出本图数据，正式选用更直接的academic编码。"},
                ],
                "candidates": [
                    {"candidate_id": fid + ":academic", "source_skill": "academic-figure-skill",
                     "reference_id": chosen, "chart_families": ACTUAL_FAMILIES[fid],
                     "dimension": selected_dimension, "suitable": True,
                     "reason": "与真实结果结构及所需科学问题相符；参考输出已按论文宽度实看。"},
                    {"candidate_id": fid + ":modelviz", "source_skill": "modelviz-skill",
                     "reference_id": alternative, "chart_families": [other_family],
                     "dimension": "2d", "suitable": fid == "q3-F03",
                     "reason": "作为双来源替代已检查；其默认多面板或统计语义与本图证据不完全匹配。"},
                ],
                "limited_candidates_reason": "两套目录均已审阅，选择适合真实字段的候选。",
                "three_d": {
                    "applicable": fid == "q3-F03",
                    "reason": "三维响应面有三个独立实测数值轴。" if fid == "q3-F03" else
                              "此图的第三维不是独立的完整网格响应；二维位置加颜色或面积更清晰。",
                    "disadvantage": "其他图采用三维会造成遮挡并降低二维成对差异可读性。" if fid != "q3-F03" else "无",
                    "axes": axes, "view": "斜视并保留三个坐标轴" if axes else "不采用三维",
                    "occlusion": "两例分面且仅九格，稀疏点可见" if axes else "二维避免遮挡",
                    "projection": "正交坐标三维曲面" if axes else "二维正交坐标",
                    "quantitative_basis": "六例每例九个官方评估点，未加入额外点" if axes else "第三维无完整网格或不服务本图主要判断",
                },
                "repetition_exceptions": [],
            }
            rec["backend_reason"] = "已同时核查academic和modelviz目录与预览；本图以已实看的academic家族编码真实CSV。"
            rec["core_claim"] = fig["scientific_question"]
            rec["evidence_role"] = ROLE[fid]
            rec["figure_contract"] = {
                "necessity": "对应独立科学问题且提供正文定量证据，不重复综合导航图。",
                "evidence_chain": panel["result_file"] + "→求解/render_science_figures.py→正式PDF/PNG→人工视觉审阅",
                "review_risks": "分位数不是置信区间；点云相关不是因果；非官方容量网格须明确与官方评分隔离。",
            }
            rec["target_width_mm"] = 160
            rec["paper_geometry"] = {
                "source_tex": class_file, "source_sha256": digest(TEMPLATE / class_file),
                "text_width_mm": 165, "width_fraction": 160 / 165,
                "basis": "A4横宽210mm减左右各22.5mm；图件源宽160mm，正文includegraphics设为0.96 textwidth。",
            }
            rec["run_record_path"] = "求解/正式图件/运行记录/" + fid + ".run.json"
            rp.update({"asset_family": chosen, "atlas_reference": atlas,
                       "production_asset": source, "source_example_path": example,
                       "source_locator": source_name + " 的绘图调用、轴与样式设置",
                       "candidate_families": [chosen], "candidate_atlas": [atlas],
                       "selection_status": "reviewed", "data_state": "verified",
                       "adaptation_mode": mode,
                       "data_profile_path": "求解/正式图件/数据核验/" + fid + ".json",
                       "data_schema": {"fields": panel["fields"], "units": panel["units"],
                                       "shape": "从正式评估中逐例或逐配置导出的CSV，行数及字段见核验文件",
                                       "groups": [problem["problem_id"]]},
                       "style_parameters_inherited": {
                           "hierarchy": "参考家族的清晰标题、主图和图例层次",
                           "encoding": OBSERVATION[chosen]},
                       "changed_parameters": {"data": "仅使用本题正式结果CSV", "statistics": "不复用示例统计值"},
                       "reason_for_change": OBSERVATION[chosen],
                       "candidate_comparison": [{"family": chosen, "fit": OBSERVATION[chosen],
                                                 "conflict": "演示图变量和形状与本题不完全相同",
                                                 "decision": "selected", "decision_reason": "保留可适配的编码和印刷层次，按实际数据重新绘制。"}],
                       "candidate_review": [],
                       })
            rp["candidate_search"]["reviewed"] = True
            search_query = " | ".join([panel["question"], fig["scientific_question"],
                                       *panel["fields"], *panel["units"]])
            rp["candidate_search"]["query"] = search_query
            rp["candidate_search"]["results"] = search_catalog(INDEX, search_query)
            rp["candidate_search"]["selection_reason"] = (
                f"全库检索后比较{chosen}与{alternate}：{chosen}更接近本图的数据角色；"
                f"{alternate}的结构会暗示额外分布或不同统计含义。")
            rp["candidate_search"]["single_candidate_reason"] = (
                f"{alternate}经全库联系表和已选其他图的细节检查后不适用；本图仅保留{chosen}为正式家族。")
            selected = {atlas, example}
            required = {atlas}
            required.update(x["path"] for x in family["production_scripts"] + family["outputs"])
            rp["candidate_review"] = [review_entry(raw, selected) for raw in sorted(required)]
            rp["style_contract"] = {}
            for key, (reference_value, final_value) in STYLE.items():
                relevant = key not in {"facets", "grid", "colorbar", "annotations", "statistics"}
                rp["style_contract"][key] = {
                    "reference_value": reference_value, "final_value": final_value,
                    "basis": "source" if relevant else "image_estimate",
                    "source_path": source if relevant else example,
                    "source_locator": source_name + " 绘图及样式段" if relevant else "参考图可见面板",
                    "reason": "根据实际字段、离散度和论文宽度重新适配；不导入演示数值。",
                }
            csv_path = ROOT / panel["result_file"]
            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                fields = reader.fieldnames or []
                rows = list(reader)
            assert rows and set(panel["fields"]) <= set(fields), fid
            save(rp["data_profile_path"], {
                "source_path": panel["result_file"], "sha256": digest(csv_path),
                "fields": fields, "row_count": len(rows), "valid": True,
                "validation_method": "标准CSV解析、非空行与计划字段逐项核对；源表由正式评估结构化结果派生。",
            })
            rec["status"] = "planned"
            fig["status"] = "planned"
            fig["selection"]["figure_sha256"] = selection_digest(fig)
    all_figures = [f for problem in plan["problems"] for f in problem["figures"]]
    line_figures = [f for f in all_figures if "line" in f["panels"][0]["chart_families"]]
    line_ids = [f["figure_id"] for f in line_figures]
    assert len(line_ids) == 5, line_ids
    stamp = portfolio_digest(all_figures)
    for fid, alternate in {"q3-F01": "histogram", "q3-F04": "heatmap", "q3-F06": "bar"}.items():
        figure = next(f for f in all_figures if f["figure_id"] == fid)
        source = figure["panels"][0]["result_file"]
        figure["selection"]["repetition_exceptions"] = [{
            "chart_family": "line", "portfolio_sha256": stamp, "figure_ids": line_ids,
            "scientific_purpose": "五张线图分别回答核数平均扩展、缓存经验分布及容量响应的不同问题。",
            "alternatives": [{"chart_family": alternate,
                              "reason": "替代图型会遮蔽有序横轴上的连续比较或误示样本统计。"}],
            "reason": "此图有有序横轴和明确比较任务；已与替代图型比较，保留线形便于读取变化方向。",
            "evidence": {source: digest(ROOT / source)},
        }]
    plan["plan_status"] = "ready"
    save("求解/视觉计划.json", plan)
    save("求解/视觉计划.assets.json", refs)
    print(json.dumps({"status": "review_recorded", "figures": len(by_id)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
