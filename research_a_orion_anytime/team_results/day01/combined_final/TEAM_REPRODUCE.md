# 从两片最终结果复核100图

本次已在新的接收根分别unpack，使用原campaign collect得到formal_complete=true、1400主记录、500同方案对照、1400独立主核验和空缺失列表。COLLECTION_STATUS.json记录执行时间和退出码0。collect_stdout/stderr为原命令日志。

先下载完整两片final目录中的分卷和清单。片0的6卷用该目录reassemble_transfer.py重组；片1的13卷用shard_1/join_archive.py读取final/ARCHIVE_PARTS.json重组。两边分卷大小不同，但重组后均是标准TRANSFER.json + run/ ZIP。不删分卷、不混用阶段ZIP。

```powershell
& 'D:\python\python.exe' '<shard_0\final>\reassemble_transfer.py'
& 'D:\python\python.exe' '<shard_1>\join_archive.py' '<shard_1\final>\ARCHIVE_PARTS.json'
```

回到与本次相同的ORION源码包根，给下面占位符填入本机路径；所有接收/汇总目录必须是新的空目录。官方图、配置、评估器使用你已有的官方输入，不从结果包里补造。

```powershell
& 'D:\python\python.exe' -m research_a_orion_anytime.transfer unpack --zip '<片0完整ZIP路径>' --root '<新根>\shard_0\auto'
& 'D:\python\python.exe' -m research_a_orion_anytime.transfer unpack --zip '<片1完整ZIP路径>' --root '<新根>\shard_1\auto'
& 'D:\python\python.exe' -m research_a_orion_anytime.campaign collect --official '<官方附件根>' --out '<新根>\merged' --indices '<新根>\shard_0\auto\final_index.json' '<新根>\shard_1\auto\final_index.json'
```

该命令读取与核验已有结果，不启动新的solver。它保留原合法性检查并要求完整100图；若键冲突或身份不一致应报错，不按成绩择优。不能对接收目录执行formal续跑。

per_case.csv保持原1400主键；Q1/Q2单核点按基线定义为1，不能另外补成独立求解记录。selected_plans.zip含1400份原collect导出的选中方案；失败证据保留在两片完整transfer中。均值先逐图T1/Tk再平均，P10按(N-1)*0.1线性插值，缓存因果比只使用同方案有/无L2。

执行条件必须一同引用：片0改进27/54秒、1→2→4 worker、Python3.12.5；片1改进30/60秒、2 worker、Python3.12.14；算法/官方配置版本一致，实际预算与混合并发限制在REPORT和两片来源记录中保留。

本次仅发布到用户授权的私有GitHub分支，未自动合并PR、未上传赛事平台，未启动下一算法版本。
