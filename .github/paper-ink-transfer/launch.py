from pathlib import Path
import sys
p=Path(__file__).with_name('publish.py')
s=p.read_text(encoding='utf8')
s=s.replace("['git','rm','-r','--ignore-unmatch'", "['git','rm','--sparse','-r','--ignore-unmatch'")
s=s.replace("paths=sorted(set(paths))", "paths += [str(WS/'求解/线刻图件/RESULT_FIGURES.json')]\n    paths=sorted(set(paths))\n    with zipfile.ZipFile(ART/'review_assets.zip','w',zipfile.ZIP_DEFLATED) as z:\n        for rel in paths:z.write(ROOT/rel,rel.replace('\\\\','/'))")
exec(compile(s,str(p),'exec'),globals())
