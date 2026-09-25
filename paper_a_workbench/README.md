# A题论文工作台：项目内生产、统一理论、本地原始实验

在当前Codex项目内建立干净的 `ORION_Paper_Agent/`。原20hw提供workshop、绘图、LaTeX、支撑材料和PDF检查；本包提供证据整理、理论、写作、学术编辑、增量修订和独立审阅六个专题角色。

**理论框架已原生接入。** `SOURCE_PROFILE`包含PR #44的`paper_a_theory`，sync固定实际提交，prepare-theory核对七个必需文件，转换合并术语表，package-inputs装入理论输入，bind交给工作区六个角色。无需再在总控提示词后追加理论包提示词。

**实验原件在本地。** 默认只读 `C:\Users\LEGION\Desktop\数据`。GitHub获取代码、题面、文献和报告；桌面目录的完整ZIP、连续ZIP分卷或已解包目录提供summary、方案、原响应、进度与图数据。报告上传完成不替代原件到位。

## 入口

- `START_HERE.md`：零上下文取代码及部署。
- `FINAL_LOCAL_PROMPT.md`：给本地Codex的一份完整启动指令。
- `BOOTSTRAP_LOCAL.ps1`：参数默认从当前项目解析，无固定安装盘符。
- `LOCAL_CODEX_PROMPT.md`：安装后的`ORION_论文总控提示词.md`。
- `UPDATE_CODEX_PROMPT.md`：同一会话的增量更新。

```powershell
$project=(Get-Location).Path
& .\paper_a_workbench\BOOTSTRAP_LOCAL.ps1 -ProjectRoot $project -DataRoot 'C:\Users\LEGION\Desktop\数据'
```

脚本已有授权Git/gh与Python即可取资料；原模板可位于当前项目自身或同名子目录。未找到完整模板时，从用户授权仓库恢复共享资源。脚本不会执行优化实验，不会把旧论文或完成记录复制为新成果。

## 项目内布局

```text
<当前项目>/
  .orion_paper_cache/repository/           Git资料缓存
  .orion_paper_cache/template-<commit>/   按需恢复的共享模板
  ORION_Paper_Agent/
    AGENTS.md + .agents/skills/           生产工作流及六个专题skills
    paper_a_workbench/
    ORION_论文总控提示词.md
    ORION_论文更新提示词.md
    .orion_paper/SESSION.json             项目、Agent、缓存、数据与工作区实际路径
    数据/ORION_论文资料/snapshots/         冻结的源码、理论、文献、报告
    数据/ORION_论文资料/local_catalogues/  桌面数据目录与归档清单
    数据/ORION_论文资料/local_records/     选中归档的解包副本
    <原workshop工具创建的本次工作区>/
      求解/论文理论/bindings/             已接入的理论与合并术语
      求解/论文证据/                      规范化数据与依赖
      论文/论文.tex + 章节内容/
      提交附件/
```

所有安装与写作路径相对项目；外部数据路径是用户指定的唯一默认绝对路径。没有预设旧工作区、继承旧PASS或删除用户目录的步骤。

## 理论与版本

共同路线为“联合决策—统一执行—多邻域迭代改进”。原题与未修改的官方语义定义任务，实际运行代码决定采用的机制，#44提供理论起点和引用线索。PR38是理论包的核读锚点，不是未来结果的强制目录。实际来源通过PAPER_EXPORT绑定；路径迁移与科学行为变化分别处理。

使用`THEORY_BINDING.json`、`GLOSSARY.json`及宿主实际完成的`THEORY_ALIGNMENT.md`、`TERM_SYMBOL_LEDGER.json`、`METHOD_TO_CODE.csv`和`RESULT_BINDING.json`。公式、数字、引用和成立条件在编辑前后保护。正文采用题面规范名“总体任务执行时间（Makespan）”。

## 原数据接口

`scan-local → materialize-local（已解包目录直接读）→ local-spec → intake`。

主实验选择一个明确轮次和互不重叠分片；诊断、参数研究、历史对照分开。Q3核对完整相同方案；基准与时间口径保留原记录。缺件只影响相应数据/结论，理论准备和其他已有部分继续。

工具不自动上传数据、不启动百图、不合并PR或提交赛事。已完成的资料接入检查及范围在`VALIDATION.md`与`review/`。
