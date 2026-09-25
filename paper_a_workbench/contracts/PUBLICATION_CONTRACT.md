# 论文发布接口：方法/官方语义固定，原数据本地读取

PAPER_EXPORT声明一个明确实验集合，和算法目录名称无关。原始执行包、报告、理论和论文是不同层次；所有结果须能定位到真正原记录。

## 必需字段

`publication_id`、`publication_state`（planned/partial/final）、`algorithm_revision`、`official_revision`、`method_paths`、`config`、`protocol`。

正式final的algorithm_revision和official_revision均为实际40/64位Git提交；准备/部分资料可保留null并等待原记录对齐，不填造提交。未知版本时adopt保留准备阶段来源，理论绑定保持待对齐。method_paths保留完整模块及依赖；config为官方配置在相应提交的路径。protocol明确budget_scope（graph_question_core或graph_all_questions_cores）、seconds、主机/worker/冷或续优化/种子成本口径，不由文件夹名推定。

`result_delivery`默认local。`result_revision`记录Git报告提交，`result_paths`列报告路径；纯本地未发布报告时可为null和空列表。对原文件、源代码和实际指标的验证不因报告上传状态而省略。

`runs`和`config_local`由local-spec填写为本机实际路径；`layout`按原始存储布局配置。默认格式是jobs/*/summary.json、同目录plan.json/result.json.gz/progress.json及精确同方案配对，未来改变目录只调整映射，不重写原JSON路径。

## 理论与来源

adopt-export完整保留`theory_pr38_v1`以及文献源，只替换所选method/results；不把理论源当作实验发布。理论提交由SOURCE_LOCK固定，算法锚点不同先做实际语义对齐。#44已合并，默认从main读取；需要采用后续开发版时指定明确ref，再按更新协议固定新版。

`expected_cases`声明本数据集真实图集合。正式100图标准覆盖为1400主配置与500同方案配对；缺失或特殊基准处理写入原始记账与论文范围。主数据和参数/诊断分别建接口文件，不逐行挑最优混成主结果。

## 文件与计时

读取实际summary、完整plan、官方response、progress。Q3无L2侧必须是同一个完整plan在Q2语义的响应。先逐图求加速比再算术平均。每30秒点只用当时已验证并可用的解；历史种子成本未知时保持未知，追加时间仍独立提供。

结果数据从桌面原件读取。GitHub只同步源码、原题、文献、理论与报告；默认assets拒绝隐式原始ZIP下载。未来用户明确改变传输策略时才另外启用。
