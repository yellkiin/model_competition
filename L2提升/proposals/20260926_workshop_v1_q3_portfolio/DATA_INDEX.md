# 数据位置与复现来源索引

本发布包基于早期 workshop_v1，发布的是已完成实验的审阅材料。完整候选运行目录未上传；下列 SHA-256 用于在原档案恢复后核对来源，不表示这些完整时间线可从当前提案下载。

## 已有仓库依赖

原工作区位置：[workshop_v1](../../../20hw_myskill_distribution/20hw_myskill_distribution/workshop_v1/)。上传前已检查官方 code/data、题面、逐例分析和四份旧求解依赖的目录条目。发布源码按 README 复制回原层级运行。旧全量候选档案完整性没有在远程逐一验证。

## 本次直接提供

- 500 个最终计划位于 [tar.xz 归档](./问题三_优化计划_500组.tar.xz)，SHA-256 为 `d4027ed958612fedd664d0815705bcd4bf4a679e756eca9eefd059c8ed3b3a18`。
- 原方案、新方案以及同方案无 L2 的数值在 [逐例对照](./all_questions_comparison.csv)。
- 计划来源和完整结果哈希见 [最终审计](./final_audit.json)、[计划清单](./plan_archive_manifest.json) 与 [代表例机制数据](./representative_mechanisms.json)。

## 报告引用的本地历史文件

以下路径相对原 workshop_v1 根目录，保留作档案定位；完整 JSON 时间线体积较大，未重复提交。报告中的分析结果已在机制数据和逐例表中提供。

| 原文件相对位置 | 字节数 | SHA-256 |
|---|---:|---|
| `数据/原始/A题官方附件/code/multicore_cut_evaluate_problem_3.py` | 32112 | `eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0` |
| `数据/原始/A题官方附件/data/config.txt` | 341 | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` |
| `求解/q3_l2_optimization_20260926/evaluations/case_003/n5/bands32_scale_04b7d7ea0d/q2.json.gz` | 309070 | `eaeae9e83a271bfd2899b0f054d29187db7784e33090786e17e59f2b74928f8f` |
| `求解/q3_l2_optimization_20260926/evaluations/case_003/n5/bands32_scale_04b7d7ea0d/q3.json.gz` | 364611 | `1aa841680ea653c637d502ba7bd6250fd667a8566629f4dbd5dcc2a9906bfe07` |
| `求解/q3_l2_optimization_20260926/evaluations/case_044/n5/bands8_pipebytes_w75_8f5e6c2e95/q2.json.gz` | 29977 | `c3854e938d8b5c997963821d0857f98d72869f861791ed26d01ee500e780aa39` |
| `求解/q3_l2_optimization_20260926/evaluations/case_044/n5/bands8_pipebytes_w75_8f5e6c2e95/q3.json.gz` | 38472 | `f56b4b5d32eed6c9530944bcaaf583aa6b0badb390e202132e70d67e3fdf8471` |
| `求解/q3_l2_optimization_20260926/evaluations/case_056/n5/bands64_scale_52a77323f9/q2.json.gz` | 249745 | `7962d5ad9d391db19419a5afe0335bbfdfb73ccfa9b1a50afcf3933bbfcfa70b` |
| `求解/q3_l2_optimization_20260926/evaluations/case_056/n5/bands64_scale_52a77323f9/q3.json.gz` | 322459 | `d441cd60826f4eec77d9724d5a2f9dd0d240627949887fe0bf6803b6572bd17e` |
| `求解/q3_l2_optimization_20260926/evaluations/case_083/n5/bands64_scale_ef4d013070/q2.json.gz` | 69396 | `b663da35ceb78e9eb87200c381bd58e51c6bf31986616257d2a87770c45aa724` |
| `求解/q3_l2_optimization_20260926/evaluations/case_083/n5/bands64_scale_ef4d013070/q3.json.gz` | 76194 | `cea45e954d456f90947c2c03f59740afc60a0d5b1fe0192390ac4249c4a0b3ad` |
| `求解/run_official_experiments.py` | 9844 | `93204bcd97f3e7ffc45409db483151be69eb88e4c961115b7c75d00a19eaecb3` |
| `求解/正式实验/候选评估/case_002/n5/bands8/q2.json.gz` | 38350 | `783b09236150df26a7af5a1b15148fbc22316f82d7bf503fb1b6d1c3a7fabff2` |
| `求解/正式实验/候选评估/case_002/n5/bands8/q3.json.gz` | 58383 | `3ab09e1a5124a157842677f8660780ca438a202606077d2fc092d567228f1d30` |
| `求解/正式实验/候选评估/case_003/n5/bands8/q3.json.gz` | 219349 | `a38dc80568a85e59b9c5e1ece663a53e1fb6166cff3670972d6d9439144d26b1` |
| `求解/正式实验/候选评估/case_044/n5/components/q3.json.gz` | 26701 | `86c441ce73232d1c6ae6a1d27e10430abf5c391237cdcbddf14d03e4c9304c69` |
| `求解/正式实验/候选评估/case_056/n5/bands8/q2.json.gz` | 118179 | `9a022f340d5024678f252b357ec5d27dcd5f5f6d8d6a562182c2bcb9038f2666` |
| `求解/正式实验/候选评估/case_056/n5/bands8/q3.json.gz` | 140433 | `7bfbc62b12c024fa3dbbbcd6505b1fc6ed5ee6c3c6b63492cafb0163eba0c7d4` |
| `求解/正式实验/候选评估/case_083/n5/components/q2.json.gz` | 50564 | `0d083bbd6d57626f938311e6fbd9c1b85e4334b91b22ea62104206c8aa15ba6c` |
| `求解/正式实验/候选评估/case_083/n5/components/q3.json.gz` | 61966 | `e4778d8afde84811a2da593853935e4005034b64db0d936f153c65985b085604` |
| `求解/正式实验/逐例分析.csv` | 110125 | `ab7e31c5aee6ccaa9f3effb2288388e1fbe89763085512466a63481ef71e9c59` |
| `论文/章节内容/06_问题三.tex` | 19762 | `6e64ee4cf04bcc83b342fd3adf1f5c6fe05105367f2372242ad581559eaeccab` |
| `论文/论文.pdf` | 1643328 | `488f77be7cf2a8299396446877782c40d41280ede7247d3562b73f7322543dfc` |
| `题目/通用神经网络处理器下的多核调度问题.docx` | 297415 | `d03f1d9a39f1fcae23467cc9fd384cbc61e4f13fc71f3567bdf44e1f3bab0b46` |
