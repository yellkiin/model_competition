"""One-use reviewed source transfer. Removed from final branch after expansion."""
from pathlib import Path
import base64,json,zlib,shutil
root=Path.cwd(); temp=root/'.orion_unified_delivery'
spec=json.loads(zlib.decompress(base64.b64decode(''.join(p.read_text(encoding='ascii') for p in sorted(temp.glob('part_*.txt'))))))
built={}
for item in spec['files']:
    target=root/item['path']
    if not target.is_relative_to(root/'research_a_orion_unified'):
        raise ValueError('Unexpected output path')
    if 'text' in item:
        data=item['text'].encode('utf8')
    elif 'base64' in item:
        data=base64.b64decode(item['base64'])
    else:
        data=(root/item['source']).read_bytes()
        if item.get('namespace'):
            text=data.decode('utf8').replace('research_a_orion_trident','research_a_orion_unified').replace('research_a_orion_fusion','research_a_orion_unified')
            lines=text.splitlines(keepends=True)
            if len(lines)!=item['line_count']:
                raise ValueError('Source revision changed: '+item['source'])
            for start,end,replacement in reversed(item['edits']):
                lines[start:end]=replacement
            data=''.join(lines).encode('utf8')
    built[target]=data
for item in spec['archives']:
    source=root/item['source']; target=root/item['target']
    if target.exists(): raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
    source.write_text('# 历史实验入口\n\n此计划已归档：`'+item['target']+'`。\n\n新实验统一使用仓库根目录 `ORION_START_HERE.md` 和 `research_a_orion_unified/PLAN.md`。旧代码及已有结果路径保留，供原实验恢复、核对和复现；不要同时按两套旧计划重跑百图。\n',encoding='utf8')
for target,data in built.items():
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
(root/'history/orion_plans/README.md').write_text('''# ORION 历史计划\n\n- `fusion_smf23/`：PR #40 已合并的旧实验说明和主机提示词。\n- `trident_v13/`：PR #38 已合并的旧实验说明和主机提示词。\n\n归档保留原文，不把旧成绩改成新算法成绩。旧 Python 代码与 team_results 没有搬动或删除，仍可按原提交恢复；已有运行请在其原工作区继续，不在运行中切换版本。\n\n当前唯一新实验入口：`research_a_orion_unified/`。比较报告位于该目录 `COMPARISON_REPORT.md`；本次没有把全部旧程序删掉、重命名或合并原始结果。\n''',encoding='utf8')
(root/'ORION_START_HERE.md').write_text('''# 问题 A：当前实验入口\n\n当前使用 **ORION Unified**：先阅读 `research_a_orion_unified/COMPARISON_REPORT.md` 和 `PLAN.md`，三台分别使用 `HOST_0.md`、`HOST_1.md`、`HOST_2.md`。\n\n默认运行：`powershell -NoProfile -ExecutionPolicy Bypass -File .\\research_a_orion_unified\\run_windows.ps1 -ShardIndex 0`，其他主机只改分片编号。\n\nFusion 与 Trident 的旧计划已移入 `history/orion_plans/`。旧代码和结果留在原路径供复现，不作为另一套同时启动的正式计划。不要重新跑三份完整百图。\n\n原题和附件在 `题目/A题/`；文献在 `调研/A题_文献库/`。只更改我方调度方案，不更改原图、配置或官方评估器。\n''',encoding='utf8')
agent=root/'AGENTS.md'
text=agent.read_text(encoding='utf8')
text=text.replace('读`research_a/LOCAL_PROMPT.md`和`research_a/README.md`并实际启动实验','先读`ORION_START_HERE.md`和`research_a_orion_unified/PLAN.md`，再按对应`HOST_0/1/2.md`实际启动实验')
agent.write_text(text,encoding='utf8')
readme=root/'README.md'
text=readme.read_text(encoding='utf8')
readme.write_text('> 问题 A 当前入口：[`ORION_START_HERE.md`](ORION_START_HERE.md)。旧 Fusion / Trident 计划在 `history/orion_plans/`。\n\n'+text,encoding='utf8')
print('Installed',len(built),'readable files; archived',len(spec['archives']),'old plan documents')
shutil.rmtree(temp)
(root/'.github/workflows/orion_unified_delivery.yml').unlink()
