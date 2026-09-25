# ORION结构线：既有结果归档（部分交付）

本次只归档前面已经完成的实验，**没有新跑算法、没有更新正式成绩、没有合并PR**。

## 已真正上传

[打开本私有仓库归档下载页](https://github.com/yellkiin/model_competition/releases/tag/orion-structure-results-20260925-0455)

|附件|字节数|下载|
|---|---:|---|
|run_36085958693_artifact_10844700264.zip|15273926|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10844700264.zip)|
|run_36085958693_artifact_10844436271.zip|37707350|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10844436271.zip)|
|run_36085958693_artifact_10844341222.zip|28083442|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10844341222.zip)|
|run_36085958693_artifact_10844265253.zip|2983134|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10844265253.zip)|
|run_36085958693_artifact_10844170482.zip|11406584|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10844170482.zip)|
|run_36085958693_artifact_10843858504.zip|18213767|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10843858504.zip)|
|run_36085958693_artifact_10843813692.zip|65289391|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36085958693_artifact_10843813692.zip)|
|run_36046726567_artifact_10829028488.zip|28255987|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36046726567_artifact_10829028488.zip)|
|run_36048331790_artifact_10829414796.zip|24170191|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36048331790_artifact_10829414796.zip)|
|run_36046094858_artifact_10828791683.zip|14436|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36046094858_artifact_10828791683.zip)|
|PR30_git_snapshot_a0da7b746449.zip|226840|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/PR30_git_snapshot_a0da7b746449.zip)|
|PR31_git_snapshot_9550ac947af1.zip|65443|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/PR31_git_snapshot_9550ac947af1.zip)|
|ORION_exact_aggregate_CSV_reports_20260925.zip|88674|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/ORION_exact_aggregate_CSV_reports_20260925.zip)|
|ORION_structure_recheck_per_case_20260925.csv|522407|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/ORION_structure_recheck_per_case_20260925.csv)|
|ORION_structure_recheck_trajectory_20260925.csv|434696|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/ORION_structure_recheck_trajectory_20260925.csv)|
|ORION_structure_recheck_REPORT_20260925.md|14573|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/ORION_structure_recheck_REPORT_20260925.md)|
|ORION_safe_refine_results_20260925.md|5585|[下载](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/ORION_safe_refine_results_20260925.md)|

完整聚合CSV和报告也可在 `aggregate_attachments/` 直接查看，恢复摘要在 `pr31_recovered_summary/`。PR31原提交的四个文件冻结在 `pr31_repository_snapshot/`；不把其中历史“完整包已交付”文字当作本次上传证据。

PR30七图CI包按原GitHub artifact分别转存，保留原始成员；不是声称已传输会话中的178MB外层ZIP。PR30/31 Git源码快照不是会话代码ZIP，也不能代替本地未上传响应或原始图片。

## 仍未全部上传

- **本地存在但网络传输失败**：`ORION_structure_recheck_20260925_raw_local.zip`（72,928,491字节）。本地v3/v4原始响应不能用CI原始包代替。
- **本地代码/报告ZIP未原样上传**：`ORION_structure_recheck_20260925_code_reports.zip`（1,448,778字节）。完整两份聚合CSV和报告已单独上传；Git中的代码结果已另做快照，但不能声称原17张PNG或全部219成员已上传。
- **未找回**：`ORION_safe_refine_20260925_code_plans_report.zip` 与 `ORION_safe_refine_20260925_raw.zip`。不从分数补造21个最终方案、98条种子池、42张图和官方响应。

以上状态详见 `PENDING_UPLOADS.json`。最新轮摘要存在，不意味着最新原始计划可下载。继续研究只能使用确实存在并能重新原评估的plan。

## 可追溯清单

`PUBLISHED_MANIFEST.json`列出真实Release附件ID、URL和大小。`ARCHIVE_MEMBERS.csv`列出ZIP成员。`source_runs/`是源artifact信息。传输工作流ID只标识归档，不是实验ID。

仅新增本结果目录；未修改官方图/config/评估器、公共solver/campaign、其他研究线或旧结果。不自动合并。

## 未取得的远端项
```json
[
  {
    "run_id": 36046578817,
    "status": "no_accessible_artifact"
  },
  {
    "run_id": 36047055409,
    "status": "no_accessible_artifact"
  }
]
```

## 补存的历史日志

- [run_36046578817_historical_logs.zip](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36046578817_historical_logs.zip)：历史执行日志，不是原始plan/response包，不填补原包缺失。
- [run_36047055409_historical_logs.zip](https://github.com/yellkiin/model_competition/releases/download/orion-structure-results-20260925-0455/run_36047055409_historical_logs.zip)：历史执行日志，不是原始plan/response包，不填补原包缺失。
