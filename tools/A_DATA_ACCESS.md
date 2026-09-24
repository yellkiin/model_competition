# A 题真实输入：GitHub 与网页 Agent 读取说明

2026-09-24 修复分支：`codex/a-data-plain-json-20260924`。

## 问题与修复

原 `.gitattributes` 将 `题目/A题/**/data/*.json` 全部交给 Git LFS。Git 中的 100 个文件实际均为三行指针，本地安装 LFS 并取得对象后才会得到完整图。只读取 Git blob 的网页连接器会拿到指针，不能直接用于 JSON 解析或求解。059、083 在某台机器能够读取，不代表它们在原 Git 提交中不是 LFS 指针。

本修复将以下目录的 `case_001.json` 至 `case_100.json` 改为普通 Git JSON：

`题目/A题/通用神经网络处理器下的多核调度问题  附件/data/`

“问题”和“附件”之间为两个空格。原路径、文件名和真实图字节不变；100 张图共 252,791,457 字节，最大单图 14,404,567 字节。没有重新序列化、压缩改写或修改图、配置、官方评估器。其他题的 LFS 规则不变，也没有重写旧 Git 历史。

原提交及尚未包含修复的分支仍然是指针。PR 合并前，请明确读取修复分支；不要默认读取 main 或旧实验分支。

## 网页 GitHub 连接器

指定仓库 `yellkiin/model_competition`、引用 `codex/a-data-plain-json-20260924`，然后按原目录读取 JSON。读取到的内容应该是包含 `tensors`、`ops`、`edges` 的对象，不再以 `version https://git-lfs.github.com/spec/v1` 开头。

普通 Git 文件也可能超过连接器的单次内容长度限制。若工具只返回部分内容，应在可执行环境通过 Git 获取完整文件，不要把截断文本保存为输入，也不要自行编造或缩小图。读取权限与运行 Python 的能力是两项独立条件。

## 已有开发环境只取得真实输入

在自己的仓库根目录执行下列命令；保留当前研发分支。此命令只恢复官方 `data/` 工作目录，不修改分支、索引、算法或结果目录；若这个目录存在你自行修改的内容，应先保存在目录外。

```text
git fetch --filter=blob:none --no-tags origin codex/a-data-plain-json-20260924
git restore --source=FETCH_HEAD --worktree -- "题目/A题/通用神经网络处理器下的多核调度问题  附件/data"
```

原官方附件的 `code/`、`docs/` 和 `data/config.txt` 仍按原入口使用。此数据修复不要求更新算法，不要求重跑已完成实验。

## 给三个研发 Agent 的补充提示词

> A 题原 data/ 的全部 100 张图曾由 Git LFS 保存，网页读取到三行指针不是实际图。请从 yellkiin/model_competition 的 codex/a-data-plain-json-20260924 分支，按原路径读取 case_001.json 至 case_100.json；这批现已保存为普通 Git 文件。不要只读取 main 或旧结果分支。若有终端，可用上面的 fetch + restore 只取得 data/，保留你自己的研发分支与代码。确认取得完整 JSON 后继续原定差图对照；不要运行哈希、指纹、checksum、smoke、pytest、unittest、全仓审计或额外 benchmark，不改官方图、config 或评估器。

## AI 辅助与验证记录

本次由 AI 协助定位 Git 属性与文件内容之间的差异，并在独立修复副本中进行存储迁移。已读取 100 个原指针声明的文件大小，并确认本机原始输入全部可解析为图 JSON；复制后直接逐字节比较内容，不计算哈希或指纹。提交前另确认 Git 暂存内容为完整 JSON，且与本机原始文件字节一致。远端发布后通过同一 GitHub 连接器复核实际返回内容。

本次没有求解、重跑实验或修改实验工作区，没有修改官方算法/合法性检查，也不自动合并 PR 或上传赛事平台。
