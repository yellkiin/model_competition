---
name: mathmodel-figure-templates
description: Reproduce explicitly requested built-in MathModel scientific visualization examples in an isolated DEMO, using the bundled Python scripts. Huawei Cup production statistical figures continue to use academic-figure-skill and real results.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# MathModel Figure Templates

本 skill 用于明确要求的内置图形复刻演练。模板使用模拟数据，不作为华为杯正式科学结果或 academic 审核的替代品。先读取 `references/figure-catalog.md` 选择模板，按需读取 `references/plot-recipes.md`。这些引用相对本 SKILL.md，不相对 shell cwd。

## 共享工作区调用

按模板 `华为杯_求解规范/工作区工作流.md` 设置 `$python`、`$templateRoot`、`$workspaceRoot` 和 `$runtime`。Codex 读取 .agents，Claude 读取 .claude。确认当前工作区 purpose=demo，再执行复刻；列出模板不要求 DEMO。

```powershell
$skillSide = if ($runtime -eq 'codex') { '.agents' } else { '.claude' }
$skillRelative = "$skillSide/skills/sci-box-main/sci-box-main/skills/scibox-figure"
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/render_template.py" -- --list
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/run_shared_skill.py -- --script "$skillRelative/scripts/render_template.py" -- paired-raincloud --project 求解/模板演练/绘图复刻
```

共享入口解析实际 skill 路径、限制输出并保留运行前后核验。不要 cd 到共享 skill 后运行；不要硬编码其他机器的安装路径。默认演练输出同样位于 `求解/模板演练/绘图复刻/`。旧独立非共享项目可显式使用该安装下 `scripts/render_template.py` 的绝对路径和 `--project`，不用于新 workshop。

## 输出与适配

- 渲染器只复制选中源码到工作区 `scripts/`，图件输出到 `outputs/`，不复制整套 skill。
- 保留 PNG/PDF/SVG、可运行源码和模拟性质说明；实际打开输出检查，不自动授予科学或视觉通过。
- 自定义时修改工作区复制的源码，保留来源及确定性种子；不修改共享原件。
- `MPLCONFIGDIR` 使用共享执行器设置的工作区缓存，不写回 skill。
- 内置模板 id 以 `--list` 和目录索引的当前输出为准。
