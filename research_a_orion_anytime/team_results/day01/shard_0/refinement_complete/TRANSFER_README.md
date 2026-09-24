# 结果包重组与读取

本目录的 5 个 .part 文件是一个标准 transfer ZIP 的连续字节分卷，不是互相独立的ZIP。必须下载全部分卷以及 TRANSFER_PARTS.json、reassemble_transfer.py 到同一目录。完整ZIP大小 448,345,608 字节；目录内共 14,140 项。所有失败证据均保留。

在该目录执行 `D:\python\python.exe reassemble_transfer.py`，生成 `team_day01_shard0_refinement_complete.zip`；脚本拒绝覆盖已有输出。它按清单检查分卷字节数并顺序拼接，不启动任何求解。

回到原ORION运行包根，用已有模块解压到新空输出根：

```powershell
& 'D:\python\python.exe' -m research_a_orion_anytime.transfer unpack --zip '<本目录绝对路径>\team_day01_shard0_refinement_complete.zip' --root '<新的空接收根>'
```

阶段版使用 phase_index.json，缓存pending，不能冒充final；最终版保留 final_index.json 与原700项verification。正式合并两片需要各自最终包，使用原官方输入执行原campaign collect。包中不含官方图/config/evaluator，不要在接收根继续formal求解。

execution_provenance 是历史执行证据，其旧来源路径不用于继续运行。活动输出根内的可用主结果引用已按原transfer.rewrite重定位；接收机unpack再次重定位。不要为了快迭代修改或混入本轮成绩。
