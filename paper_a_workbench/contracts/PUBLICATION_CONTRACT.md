# 路径独立的论文资料接口 v1

算法运行器、论文工作台、GitHub发布三者通过一份明确选定的 `PAPER_EXPORT.json` 联系，不相互接管流程。此文件可放在未来任意最终结果目录。当前 examples 为 planned 格式样例；不是已完成实验。

## 发布方提供

- publication_id / publication_state：唯一批次及 planned、partial、final；final须来自实际发布判断。
- algorithm_revision、official_revision、result_revision：各自实际 Git 提交；方法、官方文件、结果不必同提交。
- method_paths：保持包结构和全部导入依赖的目录/文件，不只是 solver.py；config为原配置仓库路径。
- result_paths：同一方法/协议下的完整选中结果、论文数据及原始归档清单。不是挑选数值最好的若干行。
- protocol：实际 budget_scope、seconds、计时组成、冷/暖启动、历史成本口径及机器信息来源。两个根目录下字段相同不等于协议相同。
- runs：恢复后本地不重叠作业根；可用绝对路径或相对本地 spec 的路径。layout 描述 summary/plan/response/progress及inline/external配对位置。目录改名只更改映射。
- expected_cases：正式默认100张；小样本必须显式给实际清单。记录缺失不能通过缩小 expected_cases 伪装成百图。
- assets（可选）：明确的 GitHub Release tag及names，或artifact id及filename。先检查实际对象与存储状态，不把PR文字中提到的包当成已经取得的包。

`config_local` 是接收端解析到的实际配置原件，不用旧机器路径。`recorded_version` 可校验原 summary/request 的版本标签；固定源码提交另写 algorithm_revision。版本标签是关联线索，科学对应仍由理论/证据角色核对。

`adopt-export` 验证固定提交与实际路径后生成新 SOURCE_PROFILE；`sync` 只读Git对象按源复制到新快照。`assets` 使用本机现有 gh 授权读取指定文件；`unpack --parts` 严格按参数给定顺序恢复分卷，保留原记录JSON。不同分卷格式先读它们自身清单；本工具只支持组成标准ZIP的连续字节分卷。

## 接收端规范化输出

`intake` 是原记录读取和一致性检查，不执行算法或官方模拟器。它输出：

|文件|内容|
|---|---|
|main.csv|逐图q/n、真实makespan、原始单核、额外COPY/Spill、命中、时间、选中方案和响应路径|
|pairs.csv|同一完整Q3方案的有/无L2周期、两侧额外搬运、缓存比、字节命中及响应引用|
|anytime.csv|每30秒已有最好解与阶段、实际时钟、停止后持有状态；不填补未知早期值|
|improvement_events.csv|原progress逐次改善事件；时间与来源原样保留|
|means.csv|先逐图比值后算术平均和中位数；计数与预期分母保留|
|appendix_q1/2/3.csv|逐问附录；Q1/Q2一核明确为原基准约定|
|ACTUAL_PROTOCOLS.json|每个原request/summary中实际版本、时间帽、模式、机器执行记录|
|RAW_INDEX.json|来源summary到本次复制的原始方案/响应的对应关系|
|INTAKE_STATUS.json|缺项、冲突、样本、配对状态和formal_ready|

Q1/Q2一核不伪造为两百次新实验。标准正式键为100×14主记录，500个同方案配对。各分片重复键直接报冲突，不选择其中更小的值。缺失官方响应、审查失败、方案不同、配置变化、非默认敏感性、混合版本都要先解决。没有完整原始数据的CSV可用于内部了解，但不通过本接口进入正式实验段。

正式结果之外的参数研究、机制剖析和定向消融分别运行独立 intake 或来源适配，单独记录cohort/协议/代码。主数据集不被它们覆盖。

## 论文依赖接口

工作区 `求解/论文证据/主张依赖.json` 每条记录：
`id, statement, section, source_id, locator, formula_or_metric, selection, unit, denominator, method_revision, publication_id, dependent_figures, review_state`。
术语表记录：`term, symbol, definition, origin, first_definition, uses, aliases`。正文只用论文术语与符号，接口字段留在工作记录。

更新时比较文件内容对应的Git对象ID和数据键；变动沿依赖传播到公式、伪代码、图表、段落、摘要。无关章节不为“更新”而改写。SOURCE_LOCK固定一次阅读的来源，SESSION绑定唯一工作区。自动读取工具不授予主张或稿件“完成”状态。
