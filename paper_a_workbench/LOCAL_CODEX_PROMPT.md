# ORION 论文总控：以既有研究为输入，先建立统一论证，再接入正式实验

本提示词供零上下文的本地 Codex 使用。开始时完整读取本文件、根 AGENTS.md、本目录 policies/WRITING_CONSTITUTION.md；本次用户写作要求优先于其他模板和旧任务。任务是论文生产，不是另起一套求解方法或重跑全部实验。

## 1. 确认根目录，保留旧项目

默认原模板为 `E:\20hw_myskill_distribution`；新论文 Agent 根为 `E:\ORION_Paper_Agent`；Git 资料缓存为 `E:\orion_paper_repo`。变量可按真实机器调整。旧模板及 `workshop_v1` 原样保留。已有新的 Agent 根时读取 `.orion_paper/SESSION.json` 续接，不重复安装，不猜最大 workshop 编号。

新 Agent 由原 20hw 完整生产工作流加本题写作规则和六个专题 skill 组成。集成版 huaweicup_agent 作为来源管理、角色分工的参考，不使用其 synthetic demo/render，不把它的 `paper/main.tex` 路径代替当前 `论文/论文.tex`。

若尚未安装，先在仓库独立分支取得 `paper_a_workbench/BOOTSTRAP_LOCAL.ps1`，执行该脚本。它只复制授权的共享模板到新根，不复制旧 workshop、实验数值或旧 PASS。若原模板目录缺失，脚本从冻结仓库恢复共享资源。它不调用求解器，不自行开始论文工作区。首次实际启动原论文流程前，按保留的原 AGENTS 展示版权与使用声明；匿名论文里不放这段声明。

## 2. 资料接入与版本选择

先读取 `paper_a_workbench/SOURCE_PROFILE.json`。`active_publication=null` 表示尚在准备阶段，不把任何已有 day01、小样本、某个 PR 描述当作新正式成绩。

执行（Python 指向本机现有兼容解释器）：

```powershell
$home = 'E:\ORION_Paper_Agent'
$repo = 'E:\orion_paper_repo'
$python = 'D:\python\python.exe'
$entry = "$home\paper_a_workbench\workbench.py"
& $python $entry discover --repo $repo --ref main --fetch --out "$home\数据\ORION_论文资料\publication_candidates.json"
& $python $entry sync --repo $repo --profile "$home\paper_a_workbench\SOURCE_PROFILE.json" --home $home --fetch --lfs
```

每个可变 Git 引用在一次同步中只解析一次，落入新的快照。小批次取文件；Git LFS 原件由 Git LFS 获取。元数据阶段可用 `--metadata-only`，此时不把资料状态记成全文已齐。不要将 Connector 的显示片段拼成图数据。若 `git clone` 网络路径不通，使用授权 Connector 读取/下载对应文件或 artifact，再按来源清单落入同样目录；一次传输失败不抹掉已到位的资料。

资料范围：原题 DOCX、官方附件 code/data/docs/config；文献 README、方法对照与阅读顺序、逐篇 JSON 和相关原 PDF；已选择算法的完整导入依赖和理论说明；正式结果的 summary/progress/方案/官方响应、配对、时间曲线及图数据。实验方案、历史报告只作来源导航。

准备阶段核读已合并的 #38/#40 共通机制。**最终算法不是在两份结果里逐图选最小数，而是由一份明确的 `PAPER_EXPORT.json` 冻结。** 若目录改名，只改该文件的 method_paths、result_paths、版本和 layout，读写流程不改。发现新的已发布结果或 PR 时先记录候选；选择必须由实验 publication_state、配置、版本和原始记录支持，不能以更新时间或标题“best”代替选择依据。

选择后执行 `adopt-export` 生成新的本地 SOURCE_PROFILE，再 `sync`；实验尚未最终发布时继续准备理论，不中止全部工作。明确的多个版本科学冲突由变更角色形成简短决策记录；普通文件路径、分卷恢复和字段对应自主完成。

## 3. 文件位置与原工作流入口

新资料只进入 `$home\题目` / `$home\数据\ORION_论文资料\snapshots\<snapshot_id>`。参考论文、原图、代码、结果分别在带来源名的子目录下；SOURCE_LOCK 记录真实路径与固定提交。

读取 `.orion_paper/latest_snapshot.json` 中明确的 snapshot 后执行：

```powershell
& $python $entry package-inputs --home $home --snapshot '<刚刚同步记录的绝对路径>'
```

该命令输出真实 DOCX 文件与资料 ZIP，并生成 `.orion_paper/START_COMMAND.json` 中的参数数组。`workshop.py --input` 接收这两个**文件**，不是目录。完整读取 `华为杯_求解规范/工作区工作流.md`、`总控阶段_codex.md`、当前论文模板规范及实际 CLI 帮助后执行原 `workshop.py start`。按返回的 `workspace_root` 调用 `bind`。已有本次工作区时走 `add-input --reason` 登记新资料，不再 start；所有编号和清单由原工具产生。

本题包内 Python 工具在输入整理区运行，不塞进原 workshop.run 的工具白名单，不修改白名单。科学分析/绘图进入工作区后按原规范的真实入口和已登记解释器运行。题面、数据与模板只读；正式源码为 `workspace_root\论文\论文.tex`、`章节内容\*.tex`。每次会话从新 Agent 根启动，显式读取专题 SKILL.md，切换 shell 目录不代表重新加载规则。

## 4. 先完成可独立于新数值的论证

按证据整理→理论核对→正文组织→学术编辑→独立审阅推进。实际使用 `.agents/skills/orion-evidence-curator`、`orion-theory-review`、`orion-paper-writer`、`orion-academic-edit`、`orion-change-integrator`、`orion-paper-review`。每个角色有明确输入/输出，宿主真实执行；生成任务文件不等于完成。

准备阶段必须产出：逐问题目要求表、术语与符号注册表、来源卡、统一理论提纲、可核对的定义/命题/证明、方法—实现对应、正文理论初稿、图件计划和待数据清单。论文主线为同一个调度方案空间、同一个完成时间目标，在不同任务与存储语义下通过互补的合法邻域迭代改进。科学陈述使用题目和文献术语，不以工程目录名或 S/M/F/B 字母拼成理论名称。

`policies/THEORY_BLUEPRINT.md` 是论证草图，必须逐条与最终代码、原题、原评估器和文献核对后才转入正文。给出假设、变量域、量纲、推导、成立条件、复杂度和伪代码。证明仅针对被证明的数学对象；局部代理的精确最优性和全图官方完工时间是不同命题。讲清三问的共同结构和语义差异，不重新训练“神经网络模型”来满足泛化 Agent 的流程。

正文只写实际方法、理论、实验设计与客观结果。开发版本比较、缺件处理、上传日志、代码字段、接口错误放工作记录。先定义再使用；同一概念只用注册名称，术语来源给到题面/原论文/基础教材。摘要最后写，不在等待数据时写未来结论。文献先读 README、方法对照、JSON，再按原文所支持的主张引用，不整库导入引用凑数。

## 5. 正式结果到位后再完成实验部分

根据 contracts/PUBLICATION_CONTRACT.md，恢复本次选中的一组不重叠分片。必要的大包用 `assets`、`unpack`；保留原 JSON 与原路径，适配器用相对布局读文件而非全局替换原记录。

创建本地 intake spec，运行 `intake --spec <文件> --out <新的规范化目录>`。原适配器直接核对 summary、完整 plan、官方 response、配置及进度，不重新求解。Q3 配对必须完整 plan 相同。标准键为 100 图×14 主配置和500配对；Q1/Q2 一核曲线点来自基准约定；加速比先逐图计算再取算术平均。性能周期和生成方案的 CPU 秒数分开。同机/跨机、冷/续优化、历史成本和时间预算采用真实记录，不改写成统一冷预算。

`final-ready` 只表示数据接口检查状态；理论、图件、引用和 PDF 仍需实际审核。数据部分缺项时生成“工作记录/待办”，可以编译理论工作稿，但不输出正式完成记录或填补未知指标。不要为了论文无理由再跑100图；少量必要补证另建资料集，记录版本与预算后作为独立实验使用。

结果进入唯一规范化目录后，所有图表和文中数值引用此目录。每项数值记录依赖文件和选择条件；每30秒点只取当时已取得的最好解，早停后持有明确标记。容量/带宽研究与默认正式100图分开；同一方案无 L2/有 L2 才用于缓存效应。

## 6. 绘图、编辑和完成

继续用原 academic-figure/modelviz、scibox、机理/逐问综合图、摘要、支撑材料 skills。先做 Evidence Matrix 和图件计划，再依据数据制作图；流程图也只表达实际算法。题面所需核数曲线、配对、每例数据优先。35页及图数为模板要求，靠充分推导与非重复信息满足，不放大间距、捏造实验或塞无关图。按用户要求，正文不出现开发历程和防御式套话。

编辑前后用 `check-edit` 核对公式、数字、引文标签和限定词；正文按实际章节顺序用 `lint` 检查。脚本结果只是定位线索，再做语义审阅，尤其检查“相关→导致”“改善→显著”“局部→全局”的强度变化。不得为了去AI味替换标准术语、去掉成立条件或删除实际AI披露。

最终执行原工作流的论文、图件、支撑材料复现、动态附录和实际PDF逐页审查。修订后重新 finish 登记，不继承 workshop_v1 的状态。队员签署与赛事上传由队伍完成。本任务默认不向 GitHub 写论文或合并 PR；另获明确发布指令时再发布。

交付：明确 workspace_root、论文PDF/TeX、正式图件与可编辑源、规范化逐例数据、官方方案/附件、来源卡、复现和最终审查记录。实验未最终发布时先交理论工作稿和准确待办，继续使用本次工作区；正式数据到位后读取根 `ORION_论文更新提示词.md`。
