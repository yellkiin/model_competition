# A题论文工作台

把已经完成的方法和原始实验接入20hw正式写作流程，先准备统一模型、术语、证明与图件计划，待一份明确的正式实验发布后生成结果章和摘要。算法可以来自 #38、#40 或后续新目录，论文接口通过固定提交和路径配置衔接。

## 本次选型

原20hw保留为工作区/环境/绘图/LaTeX/支撑材料引擎；融合huaweicup_agent的证据与角色分工思路，新增6个专题skills。不会重新让建模Agent设计另一套算法，不运行演练稿生成器。详细对照见 `AGENT_COMPARISON.md`。

入口为 `LOCAL_CODEX_PROMPT.md`；增量更新为 `UPDATE_CODEX_PROMPT.md`。最高写作约定在 `policies/WRITING_CONSTITUTION.md`。安装到本地后，这两个入口分别变成新根 `ORION_论文总控提示词.md`、`ORION_论文更新提示词.md`。

## 本地目录

```text
E:\20hw_myskill_distribution\             原模板/数据/workshop_v1，保持原样
E:\orion_paper_repo\                       私有仓库的授权只读资料缓存
E:\ORION_Paper_Agent\                      新论文Agent根，从此打开Codex
  AGENTS.md                                原入口/版权 + 用户优先写作约定
  .agents\skills\                         原8种生产skills + 本题6种专题skills
  华为杯_求解规范\                         原工作流，只读共享
  华为杯_论文规范模板\                     原版式，只读共享
  paper_a_workbench\                       本次适配与接口
  ORION_论文总控提示词.md
  ORION_论文更新提示词.md
  .orion_paper\SESSION.json                本次明确工作区，初始为空
  题目\A题_<snapshot>.docx
  数据\ORION_论文资料\snapshots\<id>\
    problem\题目\A题\...
    literature\调研\...
    method\<最终算法目录>\...
    results\<所选发布目录>\...             正式结果到位后新增
    SOURCE_LOCK.json
  数据\ORION_论文资料_<snapshot>.zip         原workshop输入是文件，不是目录
  workshop_vN\                             由原start分配，不手工猜编号
    求解\论文证据\、论文理论\、论文修订\
    论文\论文.tex、章节内容\*.tex
    提交附件\、待选图库\
```

只复制本机授权共享模板到新根，旧workshop不迁移。输入原件、工作区副本、规范化表和稿件彼此区分。现有本地数据可逐字节复用为输入，仍需登记版本与来源；旧论文不作新数值来源。

## 安装与使用

```powershell
& .\paper_a_workbench\BOOTSTRAP_LOCAL.ps1 -Repo 'E:\orion_paper_repo' -Template 'E:\20hw_myskill_distribution' -Home 'E:\ORION_Paper_Agent' -Python 'D:\python\python.exe'
```

脚本优先已有Python；安装模板工具会新建独立根。已经安装过时不再运行install，按SESSION续接。首次获取通过授权Git/gh，文件大时分批读取并按需恢复LFS原件，不把显示截断片段当文件。原模板若不存在，template-source从冻结版本只恢复共享目录，排除旧workshop和数据。

从新根打开Codex，完整执行 `ORION_论文总控提示词.md`。原创版权首次实际启动原工作流时按原入口展示，匿名论文不嵌入版权说明。本次资料准备和接口检查不会创建正式workshop或安装LaTeX。

## 更新接口

发布者参照 `contracts/PAPER_EXPORT.example.json` 提供真实 `PAPER_EXPORT.json`。该接口区分算法、官方输入、结果各自提交，方法目录、结果目录和本地记录布局分别配置。代码路径变化只需更改这些配置，停止策略/数学行为变化则由理论角色判断并修订证明和方法。

1. `discover`：读取候选发布索引，记录而不擅自选最终版本。
2. `adopt-export`：把明确选中的发布映射到新的SOURCE_PROFILE。
3. `sync` / `assets` / `unpack`：只读获取与恢复，保存新快照。
4. `intake`：从原summary/方案/官方响应/配对/进度生成规范化数据；不重跑求解。
5. `changes` + 增量修订skill：定位数据、理论、图表与摘要依赖，按原add-input登记。
6. `lint` / `check-edit`：辅助术语和事实保持审阅，再走原图件/PDF/finish流程。

完整接口与字段见 `contracts/PUBLICATION_CONTRACT.md`。`formal_ready`只表示原记录数据完整性，不代替论文科学审阅或原finish。未知未来结果不填；当前主稿可先写理论。来源卡、版本比较、开发日志不进入正文。

## 实际检查与边界

现有011原记录完成14主+5配对的接入，目录改名等价，重复键和错误同方案配对均定位；两份编辑副本验证公式/引文保护。没有执行新算法实验，没有制作新正式终稿。检查脚本输出在 `review/`，详细含义见 `VALIDATION.md`。

不随本PR分发原模板、第三方skill素材或字体。原题和研究资料从用户已有授权仓库/本机取得。更新动作只在用户触发时运行；不设置后台监控，不自动上传赛事或合并PR。
