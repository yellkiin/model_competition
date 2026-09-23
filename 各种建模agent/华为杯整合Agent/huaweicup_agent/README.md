# 华为杯整合建模 Agent / Evidence-first Workbench

将调研、机制驱动的创新、代码实验、科学绘图、LaTeX 写作和双重审核整合到同一证据链。本组件位于 `各种建模agent/华为杯整合Agent/`，不改变本仓库原有题面、数据、上游快照和调研。

**实现方式：宿主 agent 负责真正的推理、网页阅读和编辑；Python CLI 负责运行演练、管理证据、绘图、编译与冻结。它不是不接模型也能自主解决任意赛题的服务。**

## 立即运行

以下模块命令先在仓库根执行 `cd "各种建模agent/华为杯整合Agent"`；也可在根目录使用 `python tools/huaweicup.py` 代替 `python -m huaweicup_agent`。使用独立 Python 3.11+ 环境：

```bash
python -m venv .venv-huaweicup
source .venv-huaweicup/bin/activate
python -m pip install -r huaweicup_agent/requirements.txt
python -m unittest discover -s huaweicup_agent/tests -v
python -m huaweicup_agent demo /tmp/huaweicup-demo --compile
python -m huaweicup_agent audit /tmp/huaweicup-demo
python -m huaweicup_agent freeze /tmp/huaweicup-demo --filename DEMO.pdf --rehearsal
```

`--compile` 需要系统安装 XeLaTeX、ctex/Fandol 字体和常用宏包；没有 TeX 时省略该参数，仍可运行实验、生成 PDF/PNG 图和 TeX。不要把字体文件提交到仓库。工作区已存在且非空时拒绝覆盖，换一个路径重新演练。

输出包括：原始 CSV、实验方案、可独立运行的实验脚本、20 行模型/种子/划分结果、PDF/PNG 图、TeX 数表和正文、PDF、输入/产物哈希、发布清单。五个种子分别比较两个候选的验证和测试误差；正文和结果明确标记为 synthetic 演练。它不是历年获奖论文复现，也没有调用 LLM API。

## 在真实赛题上调用整合 agent

将以下指令交给能读取本仓库的宿主：

> 读取 huaweicup_agent/AGENTS.md。使用工作区 /path/to/work，按总控、调研、建模创新、实验、绘图、写作、独立审稿、对抗复核推进。先读完整题面、冻结固定条件和输入，核验当年规则。先交付每问基线和实验计划，再运行获准的代码。所有主张必须映射来源/实验，不代填队员最终签署。

独立 Skill 入口位于上一级 `SKILL.md`，根 `AGENTS.md` 提供路由。`assets ROLE --check` 检查本仓库参考指南，`papers` 查询已匹配论文；指南不会自动执行。角色不是八个强制付费服务，可在一个宿主中按角色执行；独立审稿应另开上下文。

```bash
python -m huaweicup_agent init /path/to/work --mode competition
# 队员放入 problem.md、inputs/ 数据及当年官方模板/AI 规则，完成 contract.json。
python -m huaweicup_agent seal /path/to/work
python -m huaweicup_agent prompt /path/to/work orchestrator
python -m huaweicup_agent prompt /path/to/work researcher
python -m huaweicup_agent search "robust optimization uncertainty set" --output /tmp/candidates.json
# 搜索结果是 metadata，需读取原文并制作来源卡，再逐条 source-add。
python -m huaweicup_agent source-add /path/to/work /path/to/verified-source.json
python -m huaweicup_agent prompt /path/to/work modeler
```

其余角色为 coder、visualizer、writer、reviewer、redteam。prompt 只生成交接任务，宿主必须继续真正执行，不能报成“角色已完成”。检索需要联网；当前容器仅验证了 HTTP 协议替身，不宣称实网调用通过。历年参赛论文不一定有 DOI，不能只查 Crossref。

## 结果、画图与 LaTeX

```bash
# 由队员审查代码，宿主在受控环境实际运行后登记：
python -m huaweicup_agent record /path/to/work results/metrics.json \
  --depends problem.md contract.json inputs/data.csv code/solve.py notes/experiment_plan.json
python -m huaweicup_agent plot /path/to/work notes/plot.json
# writer 写真实论文，列出其直接依赖：
python -m huaweicup_agent record /path/to/work paper/main.tex \
  --depends results/metrics.json figures/result.pdf paper/references.bib
python -m huaweicup_agent compile /path/to/work --tex paper/main.tex --trusted-tex
python -m huaweicup_agent log-ai /path/to/work --tool YOUR_TOOL --model YOUR_MODEL_VERSION \
  --purpose "LaTeX 初稿辅助，待队员核对" --outputs paper/main.tex
```

真实 CSV 绘图规格示例，保存为工作区 `notes/plot.json`：

```json
{"data":"inputs/data.csv","kind":"scatter","name":"result","x":"time","y":"error","xlabel":"Time (s)","ylabel":"Error (m)"}
```

支持 line/scatter/bar，数据必须已封存或已登记；输出科学矢量 PDF 和 PNG。折线横轴必须严格递增，缺失/非有限数据拒绝绘制。内置图件使用系统默认配色；正式论文需人工打开图件核对。其他图型和指标可由宿主编写专用脚本并用 record 登记，不虚称已经实现通用优化/深度学习求解器。

内置 `render` **仅用于合成演练**，以免自动套用演练叙事到真实赛题。`compile` 支持受信 TeX，运行 XeLaTeX 三轮；发现传统 bibdata 时调用 BibTeX；使用 recorder 跟踪实际本地输入。当前环境缺少 BibTeX，相关正向测试跳过；不声称 Biber 自动兼容。自定义宏/外部字体/宏包需要队员核验。

## 发布不是自动参赛提交

`audit` 检查已经实现的结构/哈希/数值条件。`audit --final` 额外要求：当年官方文件已封存、规则清单已人工确认、逐问模型/审稿/局限报告、已复核 AI 记录、绑定当前证据和 PDF 的队员签署。签署格式见 examples/approvals.json，步骤见 docs/contest_2026.md。

```bash
python -m huaweicup_agent audit /path/to/work --final --pdf build/main.pdf
python -m huaweicup_agent freeze /path/to/work --pdf build/main.pdf --filename A26000010001.pdf
```

文件名仅为格式示例，须替换为题号和队伍真实编号，按当年规则确认。freeze 拒绝覆盖已冻结 PDF，输出 MD5/SHA256 和 `uploaded: false`。校验码绑定复制后的准确字节；队长在官方平台人工完成各阶段提交。**工具不会提交论文，也不会伪造队员签署或检查完成记录。**

## 能力和验证范围

|能力|已实现|需要宿主/人工或额外验证|
|---|---|---|
|调研|Crossref 元数据接口、来源状态/定位检查、历年入口目录|网页/PDF 实读、引用事实核验；实网接口待运行环境验证|
|创造|八角色协议、基线与三候选要求、反例/消融/淘汰流程|宿主真正推导与求解；不能保证新颖性或获奖|
|实验|可复现合成实验、输入和产物依赖哈希、RMSE 重算|题目专用求解器、沙箱与训练预算、样本 ID 一致性|
|绘图|真实 CSV 三类图、同源误差图、PDF/PNG 输出|特殊图型、科学图注与视觉检查|
|写作|TeX/BibTeX 导出、中文 XeLaTeX 编译、recorder 追踪|真实正文、2026 官方版式、BibTeX 后端实测|
|审计|过期/引用/数值/人工确认/发布字节校验|科学正确性、身份认证、实际平台提交|

调研范围与没有读取成功的全文见 [research.md](docs/research.md)，历年参考导航见 [catalog.json](references/catalog.json)。这些状态刻意保留，不能用“已找到文件”替代“已读过论文”。
