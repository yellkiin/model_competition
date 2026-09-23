# 2026 华为杯：赛程快照与发布操作

核对日期：2026-09-23。赛事为第二十三届中国研究生数学建模竞赛，不是本科全国大学生数学建模竞赛。所有下表时间均为**北京时间 UTC+08:00**；今天是开赛日，而不是尚有数月准备期。

来源：[研创网官方赛事页](https://cpipc.acge.org.cn/cw/hp/4)、[华中师范大学数学学院 2026-07-09 通知](https://maths.ccnu.edu.cn/info/1075/37573.htm)。后者正文明确列出竞赛、MD5 与 PDF 上传时间。学校自己的报名截止日期不推广为全国规则。

|环节|北京时间|机器时间/注意事项|
|---|---|---|
|比赛|2026-09-23 08:00 至 09-27 12:00|结束 `2026-09-27T12:00:00+08:00`|
|论文 MD5 提交|09-26 12:00 至 09-27 12:00|先定稿再生成校验码；不得与 PDF 上传截止混淆|
|PDF 上传|09-27 14:00 至 09-28 24:00|结束等于 `2026-09-29T00:00:00+08:00`|

[北京印刷学院研究生院 2026-09-17 通知](https://gs.bigc.edu.cn/yjspy/jwxx/c3d4acea32064c70b3cca72407335b2f.htm)的搜索索引还列出附件上传为 09-29 08:00 至 09-30 24:00，结束相当于 `2026-10-01T00:00:00+08:00`。本次该页面完整访问失败，附件阶段在操作前须由队长再次对照官方操作手册；它不延长论文定稿时限。工具不把这个待二次核对窗口写成自动上传计划。

## 规则读取边界

本次核实的是公开通知，不是已经读完官方 2026 论文标准文档及 AI 使用细则。没有成功取得这些附件全文，因此 `rules.json` 默认不确认任何检查项。2025 细则、校内模拟赛规定、GMCMthesis 的 2024 版本都不能替代 2026 官方文件。AI 使用是否允许、范围和披露方式必须据当年原文判断；框架具备能力不等于竞赛允许使用所有能力。

华中师范大学通知同时要求引用文献和程序标明来源，并说明比赛期间不得与队外人员讨论赛题内容。系统不邀请队外人类解题，不使用他队结果，不抹去 AI 使用记录。队员自行核对适用细则和每项实际使用。

## 真实工作区操作

先将队长从官方平台取得的模板与 AI 细则存入 `inputs/official_template.*`、`inputs/official_ai_policy.*`，保留原始文件名和哈希；完成 contract.json、problem.md、数据后 seal。读到的官方条款和页码写 notes/rules_review.md。下面是结构示例，不得机械改成 true：

```json
{
  "year": 2026,
  "verified_by": "",
  "policy_file": "inputs/official_ai_policy.pdf",
  "template_file": "inputs/official_template.docx",
  "checks": {
    "official_template": false,
    "anonymization": false,
    "ai_policy": false,
    "citations": false,
    "rendered_pdf": false,
    "all_questions_answered": false,
    "scientific_review": false
  }
}
```

当年允许的 AI 使用按 log-ai 记工具/模型版本/用途/输出；队员逐项核对后填 `human_review: reviewed`。修改过输出需要重新登记和复核，不能保留旧哈希的签署。生成模型、审稿和局限文件并 record；每项主张连到已读来源或实际实验。

完成受信 TeX 编译，逐页打开 PDF 检查匿名、公式、表格、中文字体、溢出、引文和官方版式。编译成功本身不满足 `rendered_pdf`。最终使用：

```bash
python -m huaweicup_agent audit WORK
python -m huaweicup_agent snapshot WORK
# 人类队员核对当前证据与 PDF，按 examples/approvals.json 填签署。
python -m huaweicup_agent audit WORK --final --pdf build/main.pdf
python -m huaweicup_agent freeze WORK --pdf build/main.pdf --filename YOUR_REAL_ID.pdf
```

approvals.snapshot 使用 snapshot 命令输出，pdf_sha256 使用当前目标 PDF 的 SHA256。队员填写身份和决定；agent 不代填。任何输入/证据/输出变化都会使当前签署过期。该签署只是本地流程约定，不提供身份认证，也不能防御具有写权限的人蓄意伪造。

freeze 输出 `release/文件.pdf` 和相邻 manifest，包含精确字节 MD5/SHA256、证据快照与 `uploaded: false`。必须使用赛事指定校验工具再次核对 MD5 并由队长操作官方系统；我们的 MD5 是字节一致性辅助，不代替官方上传回执。已冻结文件不覆盖，MD5 已提交的 PDF 不再修改。论文源文件、附录和程序按当年要求另行整理，不能把 release 中任何存在的文件视为官方平台已收到。
