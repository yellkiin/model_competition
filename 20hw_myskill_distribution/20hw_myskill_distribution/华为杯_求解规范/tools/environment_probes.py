"""Small real functionality probes, never scientific/visual approval."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
from environment_platform import run, executables, process_env, user_root

DRAWIO_XML = '<mxfile><diagram name="Page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="环境测试 / test" style="rounded=0;whiteSpace=wrap;html=1;" vertex="1" parent="1"><mxGeometry x="20" y="20" width="180" height="70" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'


def package_probe(python, packages, folder, env):
    specs=[(p['requirement'],p['module']) for p in packages]
    code="""import json,importlib,importlib.metadata as m
from packaging.requirements import Requirement
rows=[]
for spec,module in json.loads(__import__('sys').argv[1]):
    r=Requirement(spec); v=m.version(r.name)
    assert r.specifier.contains(v,prereleases=False),(spec,v)
    importlib.import_module(module)
    rows.append([r.name,v])
print(json.dumps(rows))
"""
    r=run([python,'-I','-c',code,json.dumps(specs)],cwd=folder,env=env)
    return r


def python_function(capability, python, folder, env):
    code={
        'pdf': "import pymupdf as f; from PIL import Image; d=f.open();p=d.new_page();p.insert_text((30,30),'PDF probe');d.save('probe.pdf');d.close();d=f.open('probe.pdf');assert 'PDF probe' in d[0].get_text();d[0].get_pixmap().save('probe.png');im=Image.open('probe.png');assert im.width>0;print(f.VersionBind)",
        'tables': "import pandas as p;from pathlib import Path;d=p.DataFrame({'中文列':[1,2]});d.to_excel('probe.xlsx',index=False);r=p.read_excel('probe.xlsx');assert r.equals(d);print(p.__version__)",
        'science': "import numpy as n;import scipy.linalg as l;import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as p;assert n.allclose(l.solve([[2.,0],[0,2.]],[2.,4.]),[1,2]);p.plot([0,1],[0,1]);p.savefig('science.png');print(matplotlib.__version__)"
    }.get(capability)
    return run([python,'-I','-c',code],cwd=folder,env=env) if code else None


def tex_candidates():
    extra=[]
    for root in [Path(os.environ.get('APPDATA',''))/'TinyTeX',user_root()/'software/TinyTeX',Path(os.environ.get('LOCALAPPDATA',''))/'Programs/MiKTeX']:
        extra.extend([root/'bin/windows/xelatex.exe',root/'miktex/bin/x64/xelatex.exe'])
    for base in [Path('C:/texlive'),Path(os.environ.get('ProgramFiles','C:/Program Files'))/'MiKTeX']:
        if base.is_dir(): extra.extend(base.glob('*/bin/windows/xelatex.exe'));extra.append(base/'miktex/bin/x64/xelatex.exe')
    return executables('xelatex',extra)


def draw_candidates():
    extra=[os.environ.get('DRAWIO_CLI')]
    for base in [Path(os.environ.get('LOCALAPPDATA',''))/'Programs/draw.io',Path(os.environ.get('ProgramFiles',''))/'draw.io',user_root()/'software/drawio']:
        extra.append(base/'draw.io.exe')
    return list(dict.fromkeys(executables('drawio',extra)+executables('draw.io')))


def tex_probe(exe, folder, python, template, fonts_only=False):
    folder.mkdir(parents=True,exist_ok=True)
    # minted.sty and latexminted must come from a compatible provider release.
    # Keep workspace Scripts available for Pygments and providers without a
    # bundled launcher, but prefer the selected TeX bin directory.
    env=process_env([exe.parent,Path(python).parent])
    header=r'''\documentclass[UTF8]{ctexart}
\usepackage{fontspec}
\IfFontExistsTF{STXinwei}{}{\errmessage{Missing required font STXinwei}}
\IfFontExistsTF{SimSun}{}{\errmessage{Missing required font SimSun}}
\IfFontExistsTF{SimHei}{}{\errmessage{Missing required font SimHei}}
\IfFontExistsTF{KaiTi}{}{\errmessage{Missing required font KaiTi}}
\IfFontExistsTF{Times New Roman}{}{\errmessage{Missing required font Times New Roman}}
'''
    if fonts_only:
        body=header+'\\begin{document}字体检测\\end{document}'
    else:
        shutil.copyfile(template/'华为杯_论文规范模板/gmcm-title.sty',folder/'gmcm-title.sty')
        body=header+r'''\usepackage{gmcm-title,tikz,minted,natbib}
\begin{document}
\GMCMContestTitle{二十三}
中文环境验证，English text. \citep{probe}
\begin{tikzpicture}\draw[->] (0,0)--(2,0) node[right]{测试};\end{tikzpicture}
\inputminted{python}{sample.py}
\bibliographystyle{plainnat}\bibliography{probe}
\end{document}
'''
        (folder/'sample.py').write_text('# 中文注释\nprint("environment")\n',encoding='utf8')
        (folder/'probe.bib').write_text('@book{probe,author={Environment Test},title={Local smoke test},year={2026}}',encoding='utf8')
    (folder/'probe.tex').write_text(body,encoding='utf8')
    cmd=[exe,'-shell-escape','-interaction=nonstopmode','-halt-on-error','probe.tex']
    tests=[run([exe,'--version'],env=env)]
    if not fonts_only:
        kp=exe.with_name('kpsewhich.exe')
        if not kp.is_file(): return tests+[{'name':'kpsewhich','returncode':1,'output':'缺少宏包查找器'}]
        tests.append(run([kp,'minted.sty'],env=env))
    tests.append(run(cmd,cwd=folder,env=env,timeout=240))
    if tests[-1]['returncode'] or fonts_only: return tests
    bib=exe.with_name('bibtex.exe')
    if not bib.is_file(): return tests+[{'name':'bibtex','returncode':1,'output':'缺少 BibTeX'}]
    tests.append(run([bib,'probe'],cwd=folder,env=env));tests.append(run(cmd,cwd=folder,env=env,timeout=240));tests.append(run(cmd,cwd=folder,env=env,timeout=240))
    tests.append(run([python,'-I','-c',"import pymupdf as f;d=f.open('probe.pdf');assert len(d)>0;d[0].get_pixmap().save('tex-preview.png');print(len(d))"],cwd=folder,env=env))
    return tests


def draw_probe(exe, folder, python):
    folder.mkdir(parents=True,exist_ok=True)
    source=folder/'probe.drawio';source.write_text(DRAWIO_XML,encoding='utf8')
    tests=[]
    env=process_env([Path(python).parent,exe.parent],{'DRAWIO_CLI':str(exe)})
    for suffix in ('png','pdf'):
        target=folder/('probe.'+suffix)
        tests.append(run([exe,'--export','--format',suffix,'--output',target,source],cwd=folder,env=env,timeout=120))
    tests.append(run([python,'-I','-c',"from PIL import Image;import pymupdf as f;im=Image.open('probe.png');assert im.width>0;d=f.open('probe.pdf');assert len(d)==1;print('PNG/PDF decoded')"],cwd=folder,env=env))
    return tests
