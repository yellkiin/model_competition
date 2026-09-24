"""Normalize extended Windows output-root prefixes using the existing rewrite rule."""
import shutil
from pathlib import Path
from build_snapshot import BASE,SOURCE,read,put,utc
from research_a_orion_anytime.transfer import rewrite

snap=SOURCE.parent/'snapshots/final/auto'
dest=BASE/'phase_publication_20260924/artifacts/shard_0/final'
changed=[]
for f in snap.rglob('*.json'):
    rel=f.relative_to(snap)
    if rel.parts[0] in ['publication','execution_provenance']:continue
    if f.name.endswith('_plan.json') or f.name=='current_plan.json':continue
    old=read(f);new=rewrite(old,'\\\\?\\'+str(SOURCE),snap.as_posix())
    if new!=old:put(f,new);changed.append(str(rel))
idx=read(snap/'final_index.json')
for e in idx['chosen']+idx['pairs']:
    p=Path(e['summary'])
    if not p.is_relative_to(snap) or not p.exists():raise ValueError('Unrelocated index')
    s=read(p)
    for key in ['job','plan','result']:
        v=Path(s[key])
        if not v.is_relative_to(snap) or not v.exists():raise ValueError('Unrelocated selected artifact: '+str(v))
note=dict(corrected_at_utc=utc(),scope='Unpublished final snapshot only; no active results or algorithm edits',
    old_prefix='\\\\?\\'+str(SOURCE),new_prefix=str(snap),changed_json_files=changed,
    selected_main_references=700,selected_pair_references=250,all_selected_artifacts_inside_snapshot=True)
put(dest/'OUTPUT_PATH_RELOCATION.json',note);put(snap/'publication/OUTPUT_PATH_RELOCATION.json',note)
for p in [dest/'REPORT.md',snap/'publication/REPORT.md']:
    with p.open('a',encoding='utf8') as f:f.write('\n最终打包前另修正两条缓存索引及其元数据使用的Windows扩展路径前缀（\\\\?\\）。修正仅限未发布快照的完整输出根前缀，使用原transfer.rewrite；全部700主/250配对及方案、结果引用均确认位于冻结根内，原活动结果和成绩未改。见OUTPUT_PATH_RELOCATION.json。\n')
old_dir=BASE/'phase_publication_20260924/unpublished_final_archive_attempt_1'
old_dir.mkdir(exist_ok=False)
for p in list(dest.glob('team_day01_shard0_final.zip*'))+[dest/'TRANSFER_PARTS.json']:
    if p.exists():
        if not p.resolve().is_relative_to(dest.resolve()):raise ValueError('Outside final staging')
        shutil.move(str(p),str(old_dir/p.name))
# The failed receive attempt is retained. Start the corrected receive at a fresh root later.
print('RELOCATED',len(changed))
