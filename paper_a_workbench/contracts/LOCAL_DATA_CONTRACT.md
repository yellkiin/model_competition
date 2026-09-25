# 本地完整数据、仓库报告的接收约定

默认原件目录：`C:\Users\LEGION\Desktop\数据`。Agent安装/工作区/缓存都位于当前项目；桌面目录只读，用户可用--data-root改路径并保存到SESSION。

## 接收顺序

1. `scan-local --home <Agent根>`读取目录与归档目录项，输出LOCAL_CATALOGUE，列出普通ZIP、数字连续ZIP分卷、已解包jobs根及小型发布元数据。读取不解压、不上传。
2. 依据报告的publication/run/shard/algorithm/protocol选择一组明确主实验。目录较新、包名含final或更小的周期都不是自动合并依据。完整ZIP和同名分卷分别列出，选择一种表示。
3. `materialize-local --catalogue <清单> --entry <id> --out <项目内新目录>`；已解包目录直接引用，ZIP分卷通过seekable连续字节视图解压，不再拼一份大ZIP。源文件和原JSON保持不变。嵌套包另一次明确选择，其他格式由本机已有归档工具处理。
4. 用真实版本/协议制作PAPER_EXPORT。`local-spec --export <文件> --runs <所选本地目录...> --config-local <实际官方config> --out <spec>`生成intake配置。运行`intake`，核对原summary、完整plan、官方response、采点和精确同方案配对。
5. 原workshop通过文件输入登记来源清单与派生数据，工作区内只写论文证据、分析、图件和稿件。大原件不是重新上传GitHub的前置条件。

## 本地与报告对应字段

每个实际包登记原路径/名字/字节数、解压目标、实验轮次、分片、方法提交与版本、问题/核数/图集合、预算范围、运行方式，以及相关报告文件。缺失字段从原request/summary补读；仍缺失则明确记录，不用文档推测填成已验证。

PAPER_EXPORT的algorithm_revision/official_revision固定真实Git提交；result_revision为仓库报告的提交，可在纯本地未发布报告时为空。result_paths只定位报告，不暗示原始包已上传。config_local和runs指实际本地路径，layout支持未来目录迁移。

保持一组主实验的全部成功、失败和超时。Q1/Q2一核定义、Q3同方案分母、不同核数和阶段必须对应。像#43的基准超时、历史补证和用户豁免，分别读取BASELINE_ACCOUNTING与实际响应，报告分母/覆盖集合，不重写原始完成标志。

## 更新

新主机包到位后刷新清单，新增不重叠分片；选择另一个轮次则新建publication，不覆盖旧数据。主结果、消融、参数研究与历史对照分别输出。默认不下载远端原始ZIP/大分卷；远端只同步源码、题面、文献与报告。
