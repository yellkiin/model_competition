# 容器入口与交付边界

此处交付的是已经在 Windows 实测的算法代码、冻结依赖和最小数据。**本次发布没有另行声称完成 Linux 实测**；网页端 AI 应在其真实容器中运行并记录兼容问题与结果，不能把本文命令当成已执行回执。

已有父实现来自 `217444aba097259feb09cac8544279533f670986`，必要依赖放在 `_frozen/`。入口 `experiment.py` 用 `runpy` 加载它们，子进程也从 `_frozen/` 运行；不依赖最新 main 的另一份 F 实现。发布只增加了入口包装及 Linux `start_new_session`，以便已有时限控制仅终止自己的 worker 进程组；未修改算法、原题或官方评价。

使用已有 Python 3.10+，CPU/标准库，无需安装 PyTorch/CUDA/Conda。以下命令从本 PR 的仓库根执行。

## 取得官方 A 输入

已有题目附件时，直接把包含 `code/`、`data/` 的实际路径传给 `--official`。题目路径是 `题目/A题/通用神经网络处理器下的多核调度问题  附件/`（“问题”与“附件”间两个空格）。不要复制修改版评估器。

如果容器尚无附件，可只恢复本轮六图及完整原官方代码：

```bash
python -X utf8 -m L2提升.orion_20260926.prepare_official --repo-root . --out /tmp/orion_l2_official --cases 001 026 030 033 080 083 --fetch
```

该工具从已有实验所用原始输入提交 `b513a98f86183a8c1b41d67a547f06fa9d578e2a` 按原字节取文件，不修改配置、不恢复其他题、不下载100图种子包。网络/仓库访问受限或对象仍为 LFS 指针时明确报错并保留 `.part`，不能用自造图或替代代码补齐。

## 实际小批次复现

```bash
python -X utf8 -u -m L2提升.orion_20260926.experiment \
  --official /tmp/orion_l2_official \
  --seed-root L2提升/orion_20260926/seeds \
  --out /tmp/orion_l2_v1_replay \
  --cases 001 026 030 033 080 083 \
  --arms existing_F L2_window_v1 --seconds 120 --calls 64 \
  --workers 2 --wall-seconds 1200
python -X utf8 -m L2提升.orion_20260926.summarize --run-root /tmp/orion_l2_v1_replay
```

原始六图强起点在 `seeds/jobs/`；本次最好完整固定版本 v1 的六个方案在 `incumbents_v1/jobs/`。两者均有真实方案文件，summary 是精简来源回执，未携带多 GB 历史响应。选择任一种起点做新方法比较时，所有比较臂必须一致且明确记录；入口总会重新官方回放，不能只信历史分数。

各作业仍包含种子 Q3/Q2 回放和最终同 plan Q2 配对。目录必须全新；12个作业是六图×两臂，不是完整 SMFB 或100图。先按参考配置复现还是设计新的小批次，交给研究者根据当前问题选择；新方法可以有自己的 runner，不要求沿用本候选生成器。

`reports/` 保存原 Windows 的真实结果，不能用新容器结果覆盖。新版本放 `../proposals/<unique_slug>/`，原始运行输出放容器临时目录或已授权的数据目录，提交小表和报告即可。

## 证据文件

- `reports/FINAL_REPORT.md`：可独立阅读的总结；最佳固定策略是 v1，而非最后执行的 v3。
- `reports/version_comparison.csv`：30项原实测，保留重复F对照；每批 `attempts.csv`、`anytime.jsonl`、`resources.jsonl` 保存小型成本与轨迹。
- `reports/existing_q3_pair_audit.csv`：已有500主键与049接续的逐项保存证据核对，缺项保留。
- `reports/RAW_RESPONSE_AUDIT.md` 与 `EVIDENCE_AUDIT.md`：原始498配对、选择接续后499配对的区别。
- `DELIVERY_MANIFEST.json`：冻结来源和发布时所作的兼容调整。原测量完整候选/官方响应仍在用户本机，不假装已经上传。

报告中的 `<LOCAL_...>`、`<OFFICIAL_DIR>`、`<PYTHON312>` 是脱敏的原始位置标记，不是可直接访问的路径。复现使用上面的参数化命令。
