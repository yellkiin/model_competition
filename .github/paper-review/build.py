from pathlib import Path
import os, re, shutil, subprocess, zipfile, json
from native_fonts import recover

ROOT=Path.cwd()
WS=Path('20hw_myskill_distribution/20hw_myskill_distribution/workshop_v2')
BASE='2236080cd82e031c8768d7ac9fe46d7b47eea95e'
BRANCH='fix/paper-a-annotations-20260927'
ART=ROOT/'paper-review-output'; ART.mkdir(exist_ok=True)

def run(args,cwd=ROOT,log=None):
    if log:
        with open(ART/log,'w',encoding='utf-8') as f:
            p=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        if p.returncode:
            print((ART/log).read_text(encoding='utf-8',errors='replace')[-12000:])
            raise RuntimeError('Command failed: '+str(args))
    else: subprocess.run(args,cwd=cwd,check=True)

run(['git','fetch','--depth=1','origin',BASE])
ops={}
for src in sorted((ROOT/'.github/paper-review').glob('changes*.txt')):
    s=src.read_text(encoding='utf-8'); matches=list(re.finditer(r'^@@ (.*?) (\d+) (\d+) @@\n',s,re.M))
    if not matches: raise RuntimeError('Empty patch '+str(src))
    for i,m in enumerate(matches):
        name,a,b=m.groups(); end=matches[i+1].start() if i+1<len(matches) else len(s)
        ops.setdefault(name,[]).append((int(a),int(b),s[m.end():end]))
changed=[]
for name,edits in ops.items():
    rel=WS/'论文'/name
    original=subprocess.check_output(['git','show',BASE+':'+rel.as_posix()]).decode('utf-8-sig')
    lines=[v+'\n' for v in original.splitlines()]
    for a,b,text in sorted(edits,reverse=True):
        if not 0<=a<=b<=len(lines): raise RuntimeError('Invalid revision range '+name)
        lines[a:b]=text.splitlines(keepends=True)
    (ROOT/rel).write_text(''.join(lines),encoding='utf-8',newline='\n'); changed.append(rel)
fig=WS/'论文/图片/workflow_mono_v3.pdf'; (ROOT/fig).parent.mkdir(exist_ok=True)
shutil.copy2(ROOT/'paper_a_figures/engraved_workflow/ink_v3/exports/workflow_mono_v3.pdf',ROOT/fig)
changed.append(fig)

# A disposable compile copy handles hosted-runner font availability. No font files are published.
temp=Path(os.environ['RUNNER_TEMP'])/'paper-native-review'
if temp.exists(): shutil.rmtree(temp)
buildws=temp/'ws'; shutil.copytree(ROOT/WS,buildws)
paper=buildws/'论文'; fonts=temp/'private_fonts'
recover(ROOT/WS/'论文/论文.pdf',fonts)
shutil.copy2(ROOT/'各种建模agent/MathModelAgent/backend/fonts/simhei.ttf',fonts/'SimHei.ttf')
fontpath=fonts.as_posix()+'/'
style=paper/'gmcm-title.sty'
st=style.read_text(encoding='utf-8')
st=st.replace(r'\IfFontExistsTF{STXinwei}',r'\IfFileExists{'+fontpath+'STXinwei.ttf}')
st=st.replace(r'\setCJKfamilyfont{hwxw}[AutoFakeBold=2]{STXinwei}',r'\setCJKfamilyfont{hwxw}[AutoFakeBold=2,Path='+fontpath+r']{STXinwei.ttf}')
style.write_text(st,encoding='utf-8')
tex=paper/'论文.tex'; source=tex.read_text(encoding='utf-8')
source=source.replace('\\documentclass[bwprint]','\\documentclass[bwprint,fontset=fandol]')
bootstrap='\n'.join([
 r'\setmainfont{Times New Roman}',r'\setsansfont{Arial}',r'\setmonofont[Scale=MatchLowercase]{Courier New}',
 r'\setCJKmainfont[AutoFakeBold=2.15]{SimSun}',
 r'\setCJKfamilyfont{zhsong}[AutoFakeBold=2.15]{SimSun}',
 r'\setCJKsansfont[AutoFakeBold=2.15,Path='+fontpath+r']{SimHei.ttf}',
 r'\setCJKfamilyfont{zhhei}[AutoFakeBold=2.15,Path='+fontpath+r']{SimHei.ttf}',
 r'\setCJKfamilyfont{zhli}[Path='+fontpath+r']{LiSu.ttf}',
 r'\setCJKfamilyfont{gmcmabstract}[AutoFakeBold=2.15,Path='+fontpath+r']{LiSu.ttf}',
 r'\renewcommand{\lishu}{\CJKfamily{zhli}}',''])
source=source.replace('\\begin{document}',bootstrap+'\\begin{document}')
tex.write_text(source,encoding='utf-8')
for ext in ['aux','bbl','blg','log','out','toc','pdf']:
    f=paper/('paper.'+ext)
    if f.exists(): f.unlink()
cmd=['xelatex','-shell-escape','-interaction=nonstopmode','-halt-on-error','-jobname=paper','论文.tex']
try:
    run(cmd,paper,'xelatex-1.txt')
    run(['bibtex','paper'],paper,'bibtex.txt')
    run(cmd,paper,'xelatex-2.txt')
    run(cmd,paper,'xelatex-3.txt')
finally:
    for ext in ['aux','bbl','blg','log','out','toc']:
        f=paper/('paper.'+ext)
        if f.exists(): shutil.copy2(f,ART/f.name)
shutil.copy2(paper/'paper.pdf',ROOT/WS/'论文/论文.pdf'); changed.append(WS/'论文/论文.pdf')
(ART/'compile-environment.txt').write_text('Windows native SimSun / Times New Roman / Arial / Courier New / Consolas. Existing repository SimHei. Unchanged masthead and labels use only glyphs already embedded in the current 78-page manuscript (STXinwei, LiSu), reconstructed solely in a disposable directory. No fonts or temporary font substitutions are committed. Three XeLaTeX passes and BibTeX; no experiments, smoke tests or hash tests.\n',encoding='utf-8')
with zipfile.ZipFile(ART/'revised-manuscript.zip','w',zipfile.ZIP_DEFLATED) as z:
    for rel in changed:
        z.write(ROOT/rel,rel.as_posix())
    for rel in [WS/'论文/摘要.tex',WS/'论文/参考文献.bib']:
        z.write(ROOT/rel,rel.as_posix())
shutil.copy2(paper/'paper.pdf',ART/'论文.pdf')
shutil.rmtree(fonts)
run(['git','config','user.name','github-actions[bot]'])
run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'])
run(['git','add','--']+[p.as_posix() for p in changed])
if subprocess.run(['git','diff','--cached','--quiet']).returncode:
    run(['git','commit','-m','revise(A): implement annotated theory, notation, workflow and compiled manuscript'])
    run(['git','push','origin','HEAD:'+BRANCH])
(ART/'MANUSCRIPT_COMMIT.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD']).decode(),encoding='utf-8')
