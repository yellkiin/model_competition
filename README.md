# 数学建模竞赛资料与赛题调研

本仓库整理 A–F 六题的题面、基础调研、可核验文献及论文写作方向。调研日期为 2026-09-23；报告用于选题与后续自主建模，未将计划中的模型或实验写成已经完成的结果。

## 阅读入口

- [六题调研总览与选题建议](调研/README.md)
- [A 题 多核调度](调研/A题_基础调研与写作方向.md)
- [B 题 燃料电池冷启动](调研/B题_基础调研与写作方向.md)
- [C 题 脑电计算模型](调研/C题_基础调研与写作方向.md)
- [D 题 无人机运输与通信](调研/D题_基础调研与写作方向.md)
- [E 题 多模态情感预测](调研/E题_基础调研与写作方向.md)
- [F 题 大模型资源配置](调研/F题_基础调研与写作方向.md)
- [文献总索引](调研/文献总索引.md)与 [BibTeX 文献库](调研/references.bib)

## 数据管理

题面与已解压附件位于 `题目/`，纳入 Git 或 Git LFS 版本管理；原 ZIP/XZ 在解压并核验后删除。A 题测试图及较大的二进制、语料文件使用 Git LFS。系统元数据和 Office 锁文件继续忽略。

E 题的 `unaligned_50.pkl` 超过 2 GiB，使用三个未压缩字节分片存放于 `data-parts/E_unaligned_50/`，由 Git LFS 管理；完整原件由脚本按原路径重建。分片与原件的字节数和 SHA-256 记录在 [分片清单](data-parts/manifest.json)。

安装 Git LFS 后，在另一台机器上获取完整数据：

```sh
git lfs install
git -c core.longpaths=true clone https://github.com/yellkiin/model_competition.git
cd model_competition
git config --local core.longpaths true
git lfs pull
python tools/restore_data_parts.py
```

`core.longpaths` 用于支持 Windows 下 F 题附件的长路径。已有克隆可先设置该选项、执行 `git pull`，再执行最后两条命令。恢复脚本检查分片和原件的 SHA-256，已有且一致的原件会跳过重建；内容不一致时中止，不覆盖文件。使用 `python tools/restore_data_parts.py --verify-only` 可仅校验分片及已有原件。GitHub 的 ZIP 源码下载不能替代上述完整数据获取流程。

详见 [数据清单说明](调研/数据清单说明.md)、[逐文件 SHA-256 清单](调研/数据文件清单.json)和 [解压核验记录](调研/数据整理记录.json)。题目数据约 6.06 GB，分片另外占用约 2.90 GB；Git LFS 本地缓存还会占用磁盘空间。

`tools/prepare_problem_data.py` 提供安全解压和核验流程；`tools/build_data_inventory.py` 生成数据清单并区分普通 Git、Git LFS、分片重建及本地忽略文件。调研资料以 Markdown 和 JSON 保存，便于多人协作、检索与修订。

原有 `各种建模agent/` 资料保持原样。本次调研不代表其中工具已经安装、运行或通过验证。
