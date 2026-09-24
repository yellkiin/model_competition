# ORION Anytime 的本地代理边界

本目录自包含，不依赖 research_a_orion_frontier 是否合并。先读 LOCAL_AGENT_PROMPT.md。只用 `watchdog -> campaign -> supervisor -> solver -> 原评估函数` 新入口运行本轮。`run.py/check_results.py` 是继承的 v1 对照接口与回归支持，不用于新版正式批次。

唯一目标变量：原图的子图分组、分核、核内子图序；最终输出只有两个官方字段。不得修改原数据、config、Step1/2/3、官方评估与验证函数，不得把代理分数记成正式周期。

运行失败、时间不足、质量/容量门槛失败都须保留；不得删除坏图、篡改门槛或只报成功子集为100图。完整结果包留在runs，不自动提交数据与生成结果。本目录已通过独立PR提交；本地agent不要重复创建PR、force push或自动merge，也不得覆盖其他AI目录。

这次开发机器是 Linux/CPython3.13.5。Windows按仓库的D:\python\python.exe / 64-bit CPython3.12.x；不兼容机器由本地agent单独配置解释器，不升级正在运行的环境。测试与正在跑的实验不得改源代码混用同一个输出根。

禁止额外测试：本轮不做冒烟测试、哈希/文件指纹测试、pytest、unittest、全仓审计或环境benchmark。只执行启动必要检查和真实官方算例；官方评估器内部合法性检查照常保留。
