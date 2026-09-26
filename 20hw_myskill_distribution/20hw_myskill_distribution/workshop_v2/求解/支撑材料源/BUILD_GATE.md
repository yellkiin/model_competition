# 原构建器接入状态

本次提交附件已从实际选定的 1400 个主配置及 500 个同方案配对整理。`求解/支撑材料清单.json` 遵循共享 schema v2，但保持 `draft`，不宣称逐问科学验收或独立目录复现通过。

共享 `build_supporting_materials.py` 对 `draft` 问题只复制代码环境说明，跳过逐问源码与中间表；改为 `complete` 时，则要求逐问 `model_selection` 报告通过门禁、真实 `run_verification` 和 `reproduction` 证据。目前工作区尚无逐问模型选择报告及独立提交副本复现记录，因此不能用共享构建器完整产出本次要求的逐问目录而不虚构 PASS。现有提交附件由 `prepare_package.py` 只按真实清单复制，内部保留 `PUBLIC_SELECTION_PROVENANCE.json` 精确来源；未改动共享工具或正文。

后续接入原构建器时，需要根 Agent 建立真实逐问模型选择报告、运行验证、独立复现记录，并将清单逐问与总状态按实际审核结果改为 `complete`。同时明确如何把整理式响应重算作为复现入口，而不要求重复完整百图优化搜索；原 schema 的 `reproduction` 必须有 solve 与 validate 两步及既有参考输出。不能将本文件视作验证记录。
