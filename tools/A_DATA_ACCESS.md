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

远端复核发现第二层限制：当前连接器对 `case_051.json` 返回完整文件中的正常 JSON 文本，但大于 1 MiB 的 `case_016.json`、`case_014.json` 返回空正文。这是文件内容接口的大小限制，不是修复分支仍保存 LFS 指针。不要把空正文或截断文本保存为输入。

若网页环境不能直接用 Git 下载，可以读取本分支的 `tools/a_input_payloads/MANIFEST.json`，按指定图对应的 `parts` 顺序取得普通文本分片，保存为相同相对路径，再读取 `tools/restore_a_inputs.py` 和 `tools/a_input_payloads/config.txt`。所有分片采用 gzip + base64，仅压缩传输，不重写 JSON；每个文本分片小于 1 MiB。将完整工具返回正文保存为文件，不要把 base64 手工抄写、截断或交给模型改写。支持工具编排的环境可直接把工具返回的 content 写入文件，不必在聊天中打印大段内容。

取得清单、配置和所需分片后，在具有 Python 执行能力的环境运行：

```text
python tools/restore_a_inputs.py --payload-dir tools/a_input_payloads --output-dir inputs_A/data --cases 16 24 51
```

Windows 本机用 `D:\python\python.exe` 代替 `python`；网页执行环境使用已有 Python。不传 `--cases` 时还原全部 100 张图，需先取得全部分片。输出目录可以直接指定为原官方附件的 `data/`；已有真实文件若内容相同会跳过，若不同则拒绝覆盖。仅当需要把已有 LFS 指针替换成真实数据时加 `--replace-lfs-pointers`。脚本不联网、不安装依赖、不运行求解器，也不计算哈希或指纹；原官方配置随输入原样还原。

读取权限与运行 Python 的能力是两项独立条件；没有代码执行能力的聊天只能读资料，不能声称已跑实验。

## 已有开发环境只取得真实输入

在自己的仓库根目录执行下列命令；保留当前研发分支。此命令只恢复官方 `data/` 工作目录，不修改分支、索引、算法或结果目录；若这个目录存在你自行修改的内容，应先保存在目录外。

```text
git fetch --filter=blob:none --no-tags origin codex/a-data-plain-json-20260924
git restore --source=FETCH_HEAD --worktree -- "题目/A题/通用神经网络处理器下的多核调度问题  附件/data"
```

原官方附件的 `code/`、`docs/` 和 `data/config.txt` 仍按原入口使用。此数据修复不要求更新算法，不要求重跑已完成实验。

## 给三个研发 Agent 的补充提示词

> A 题输入读取问题已在 yellkiin/model_competition 的 codex/a-data-plain-json-20260924 分支修复。先读 tools/A_DATA_ACCESS.md。原路径 100 张图现为普通 Git 文件；小文件可直接读取，超过 1 MiB 的文件若返回空正文，请改取 tools/a_input_payloads/MANIFEST.json 中对应图的完整文本分片，配合 tools/restore_a_inputs.py 无损还原到独立输入目录；配置用同目录 config.txt。可以用 Git 的环境优先通过 fetch + restore 直接取得原 data/，保留自己的研发分支与代码。不要只读取 main 或旧结果分支。确认取得完整 JSON 后继续原定差图对照；不要运行哈希、指纹、checksum、smoke、pytest、unittest、全仓审计或额外 benchmark，不改官方图、config 或评估器。

## AI 辅助与验证记录

本次由 AI 协助定位 Git 属性与文件内容之间的差异，并在独立修复副本中进行存储迁移。已读取 100 个原指针声明的文件大小，并确认本机原始输入全部可解析为图 JSON；复制后直接逐字节比较内容，不计算哈希或指纹。提交前另确认 Git 暂存内容为完整 JSON，且与本机原始文件字节一致。远端发布后通过同一 GitHub 连接器复核实际返回内容。

本次没有求解、重跑实验或修改实验工作区，没有修改官方算法/合法性检查，也不自动合并 PR 或上传赛事平台。
