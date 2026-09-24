"""Make a fresh package-shaped rehearsal directory inside this workshop."""
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'求解/支撑预演/20260923_1730/支撑材料文件'
if DEST.exists():raise RuntimeError('预演目录已存在，保留旧证据并改用新名称')
for sub in ('其他数据','其他支撑材料'):(DEST/sub).mkdir(parents=True)
shutil.copy2(ROOT/'求解/提交源/官方输入.zip',DEST/'其他数据/官方输入.zip')
shutil.copy2(ROOT/'求解/提交源/正式候选评估.zip',DEST/'其他支撑材料/正式候选评估.zip')
shared=('collect_official_results.py','verify_official_results.py','summarize_validations.py')
for label in ('一','二','三'):
    src=DEST/f'问题{label}/源码'
    (src/'求解').mkdir(parents=True)
    shutil.copy2(ROOT/f'求解/问题{label}/问题{label}.py',src/f'问题{label}.py')
    shutil.copy2(ROOT/'求解/support_reproduce.py',src/'support_reproduce.py')
    for name in shared:shutil.copy2(ROOT/'求解'/name,src/'求解'/name)
print(DEST)
