from pathlib import Path
import base64,zlib,json,subprocess,os,shutil,sys,zipfile,importlib.util,re
ROOT=Path.cwd()
WS=Path('20hw_myskill_distribution/20hw_myskill_distribution/workshop_v2')
TEMP=Path(os.environ['RUNNER_TEMP'])/'paper-ink-native'
ART=ROOT/'paper-ink-output';ART.mkdir(exist_ok=True)
BRANCH='figures/paper-wide-ink-style-20260927'

def run(args,cwd=ROOT,log=None):
    if log:
        with (ART/log).open('w',encoding='utf8') as f:
            result=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:
            print((ART/log).read_text(encoding='utf8',errors='replace')[-15000:])
            raise RuntimeError('Build command failed: '+str(args))
    else:subprocess.run(args,cwd=cwd,check=True)

def apply():
    chunks=sorted((ROOT/'.github/paper-ink-transfer').glob('block*.txt'))
    if len(chunks)!=14:raise ValueError('Incomplete local source payload')
    payload=json.loads(zlib.decompress(base64.b64decode(''.join(p.read_text().strip() for p in chunks))))
    for rel,edits in payload['patches'].items():
        path=ROOT/rel;lines=path.read_text(encoding='utf-8-sig').splitlines(keepends=True)
        for e in reversed(edits):
            if lines[e['start']:e['end']]!=e['old']:raise ValueError('Paper base changed at '+rel)
            lines[e['start']:e['end']]=e['new']
        path.write_text(''.join(lines),encoding='utf8',newline='\n')
    for rel,text in payload['files'].items():
        path=ROOT/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf8',newline='\n')
    donor='5e06e77e85ef3eebb94f45c5ab57a1a829e95b25'
    run(['git','fetch','--depth=1','origin',donor])
    out=ROOT/WS/'论文/图片';out.mkdir(exist_ok=True)
    for directory,name in [('exports','workflow_qinglu_v5.pdf'),('exports','workflow_qinglu_v5.png'),('assets','workflow_qinglu_v5.svg'),('assets','workflow_qinglu_v5_editable.svg')]:
        data=subprocess.check_output(['git','show',donor+':paper_a_figures/engraved_workflow/ink_v5/'+directory+'/'+name])
        (out/name).write_bytes(data)
    (ART/'APPLIED_FILES.json').write_text(json.dumps(list(payload['files'])+list(payload['patches']),ensure_ascii=False,indent=2),encoding='utf8')
    print('Applied local edits and copied unchanged completed V5')

def compile_publish():
    run([sys.executable,str(ROOT/WS/'求解/线刻图件/build.py'),'--theme','qinglu'],'figures' if False else ROOT,'figure-build.txt')
    old='bb9ef99b041a2715c97fcadbd018dce2fbd7239d'
    run(['git','fetch','--depth=1','origin',old])
    TEMP.mkdir(parents=True,exist_ok=True)
    helper=TEMP/'native_fonts.py'
    helper.write_bytes(subprocess.check_output(['git','show',old+':.github/paper-review/native_fonts.py']))
    spec=importlib.util.spec_from_file_location('private_native_fonts',helper);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    buildws=TEMP/'ws'
    shutil.copytree(ROOT/WS,buildws,dirs_exist_ok=True)
    paper=buildws/'论文';fonts=TEMP/'private_fonts'
    mod.recover(ROOT/WS/'论文/论文.pdf',fonts)
    shutil.copy2(ROOT/'各种建模agent/MathModelAgent/backend/fonts/simhei.ttf',fonts/'SimHei.ttf')
    fontpath=fonts.as_posix()+'/'
    style=paper/'gmcm-title.sty';s=style.read_text(encoding='utf8')
    s=s.replace(r'\IfFontExistsTF{STXinwei}',r'\IfFileExists{'+fontpath+'STXinwei.ttf}')
    s=s.replace(r'\setCJKfamilyfont{hwxw}[AutoFakeBold=2]{STXinwei}',r'\setCJKfamilyfont{hwxw}[AutoFakeBold=2,Path='+fontpath+r']{STXinwei.ttf}')
    style.write_text(s,encoding='utf8')
    tex=paper/'论文.tex';s=tex.read_text(encoding='utf8')
    s=s.replace('\\documentclass[bwprint]','\\documentclass[bwprint,fontset=fandol]')
    bootstrap='\n'.join([r'\setmainfont{Times New Roman}',r'\setsansfont{Arial}',r'\setmonofont[Scale=MatchLowercase]{Courier New}',r'\setCJKmainfont[AutoFakeBold=2.15]{SimSun}',r'\setCJKfamilyfont{zhsong}[AutoFakeBold=2.15]{SimSun}',r'\setCJKsansfont[AutoFakeBold=2.15,Path='+fontpath+r']{SimHei.ttf}',r'\setCJKfamilyfont{zhhei}[AutoFakeBold=2.15,Path='+fontpath+r']{SimHei.ttf}',r'\setCJKfamilyfont{zhli}[Path='+fontpath+r']{LiSu.ttf}',r'\setCJKfamilyfont{gmcmabstract}[AutoFakeBold=2.15,Path='+fontpath+r']{LiSu.ttf}',r'\renewcommand{\lishu}{\CJKfamily{zhli}}',''])
    tex.write_text(s.replace('\\begin{document}',bootstrap+'\\begin{document}'),encoding='utf8')
    cmd=['xelatex','-shell-escape','-interaction=nonstopmode','-halt-on-error','-jobname=paper','论文.tex']
    try:
        run(cmd,paper,'xelatex-1.txt');run(['bibtex','paper'],paper,'bibtex.txt');run(cmd,paper,'xelatex-2.txt');run(cmd,paper,'xelatex-3.txt')
    finally:
        for ext in ['aux','bbl','blg','log','out','toc']:
            f=paper/('paper.'+ext)
            if f.exists():shutil.copy2(f,ART/f.name)
    import fitz
    doc=fitz.open(paper/'paper.pdf');pages=len(doc);doc.close()
    log=(paper/'paper.log').read_text(encoding='utf8',errors='replace')
    bad=[x for x in log.splitlines() if 'undefined' in x.lower() or 'Missing character:' in x or 'multiply defined' in x]
    if bad:raise ValueError('Unresolved typesetting issues: '+str(bad))
    shutil.copy2(paper/'paper.pdf',ROOT/WS/'论文/论文.pdf');shutil.copy2(paper/'paper.pdf',ART/'论文.pdf')
    note=ROOT/WS/'论文/批注文件夹/图件统一修改报告.md'
    t=note.read_text(encoding='utf8').replace('本地已完成整篇预排和19幅新图的局部审图；最终编译环境、页数和引用检查将随成稿记录补入本报告。',f'本地完成整篇预排及19幅重绘图的整图/局部检查，随后使用Windows原生SimSun、Times New Roman及数学Computer Modern进行图件导出与三遍XeLaTeX、一遍BibTeX编译。成稿{pages}页，无未定义引用、重复标签或缺字提示。封面特殊字形仅在临时目录复用现稿已有字形，不发布字体；没有改动模板字体配置。实际发布PDF还将下载检查受影响页面。')
    note.write_text(t,encoding='utf8',newline='\n')
    receipt={'pages':pages,'figures_total':20,'redrawn':19,'master':'PR68 Qinglu V5 unchanged','palette':'qinglu','experiments_run':0,'typesetting':'Windows native SimSun/Times New Roman; Computer Modern math','passes':['xelatex','bibtex','xelatex','xelatex'],'unresolved_issues':bad}
    rec=ROOT/WS/'求解/线刻图件/BUILD_RECEIPT.json';rec.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    run(['git','config','user.name','github-actions[bot]']);run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'])
    paths=json.loads((ART/'APPLIED_FILES.json').read_text(encoding='utf8'))+[str(WS/'论文/论文.pdf'),str(rec.relative_to(ROOT))]
    for q in ['一','二','三']:
        paths += [str(p.relative_to(ROOT)) for p in (ROOT/WS/'求解'/('问题'+q)/'图片').glob('*') if p.suffix in ('.pdf','.svg','.png')]
    paths += [str(p.relative_to(ROOT)) for p in (ROOT/WS/'求解/线刻图件/plot_data').rglob('*') if p.is_file()]
    paths += [str(WS/'论文/图片'/n) for n in ['workflow_qinglu_v5.pdf','workflow_qinglu_v5.png','workflow_qinglu_v5.svg','workflow_qinglu_v5_editable.svg']]
    paths=sorted(set(paths))
    run(['git','add','-f','--']+paths)
    temps=['.github/paper-ink-transfer','.github/workflows/paper_ink_intake_once.yml','.github/workflows/paper_ink_numeric_once.yml','.github/workflows/paper_ink_appendix_once.yml','.github/workflows/paper_ink_publish_once.yml']
    run(['git','rm','-r','--ignore-unmatch','--']+temps)
    run(['git','commit','-m','fig(A): unify all manuscript illustrations with V5 ink style, explanatory plots and compiled paper'])
    run(['git','push','origin','HEAD:'+BRANCH])
    with zipfile.ZipFile(ART/'complete_paper_ink_changes.zip','w',zipfile.ZIP_DEFLATED) as z:
        for rel in paths:z.write(ROOT/rel,rel.replace('\\','/'))
    (ART/'DELIVERY_COMMIT.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD']).decode(),encoding='utf8')
    shutil.rmtree(fonts)

if sys.argv[1]=='apply':apply()
else:compile_publish()
