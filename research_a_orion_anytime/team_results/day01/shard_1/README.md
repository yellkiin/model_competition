# ORION day01 分片 1 结果

仅含偶数 002–100，共 50 图。final：700 条主记录、250 条同方案缓存对照有效，原 700 项独立核验通过。完整统计、低分图分析、预算轨迹及启动器状态不一致见 final/REPORT.md。

refinement_complete 保留 19:02 阶段快照，缓存 pending、最终核验未完成；final 保留真实最终索引及验证。两个版本不混用。

## 获取完整结果包

原 ZIP 超过 GitHub 普通 Git 单文件限制，按交接规范分为 48 MiB 的原始字节分卷。没有删除记录、重新压缩或改变 ZIP 内容。每个目录的 ARCHIVE_PARTS.json 列出全部文件、次序、偏移和字节数；分卷必须全部下载，不能只取第一卷。

在本 shard_1 目录执行：

```powershell
python .\join_archive.py .\refinement_complete\ARCHIVE_PARTS.json
python .\join_archive.py .\final\ARCHIVE_PARTS.json
```

脚本按次序拼接，检查文件存在和长度；不计算哈希、不运行测试、不覆盖已有 ZIP。完整包名恢复为 team_day01_shard1_refinement_complete.zip 和 team_day01_shard1_final.zip，内部仍是标准 TRANSFER.json + run/。

随后在原 ORION 包根使用现有 transfer unpack，指定新的空输出目录。协调机合并应使用 final 的真实 final_index.json；不能把阶段 phase_index 用作最终索引。需要另一台奇数分片才能得到全队 100 图、1400 主记录、500 同方案对照。

报告、LOCAL_DELIVERY 和 ZIP 内状态是本地冻结时的历史记录，其 uploaded=false 不作事后篡改。远端发布确认另记在本目录 latest.json / PUBLICATION.json；这些文件仅在远端上传核实后添加。没有官方输入或其他题数据，没有重启计算、修改实验源码或预算。
