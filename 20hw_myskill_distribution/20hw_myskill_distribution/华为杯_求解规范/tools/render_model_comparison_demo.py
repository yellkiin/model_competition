"""Compile and render the real generated comparison in the production class.

This is a focused typesetting smoke, not a complete competition paper.
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,default=Path('.'));a=p.parse_args()
    from workspace_context import shared_context
    from model_selection import publish, paper_gate, read, write
    root=a.project_root.resolve();ctx=shared_context(root)
    if not ctx or ctx.manifest['purpose']!='demo':
        raise ValueError('Only registered DEMO')
    publish(root)
    errors=paper_gate(root,read(root/'论文/demo_model_manifest.json'))
    if errors: raise ValueError(str(errors))
    folder=root/'论文'
    template=ctx.template_root/'华为杯_论文规范模板'
    for name in ('gmcmthesis.cls','gmcm-title.sty','gmcm-layout.sty'):
        shutil.copy2(template/name,folder/name)
    main_tex=r'''\documentclass[bwprint]{gmcmthesis}
\geometry{top=25mm,bottom=25mm,left=25mm,right=25mm}
\usepackage{booktabs,longtable}
\pagestyle{plain}
\begin{document}
\songti\fontsize{12pt}{18pt}\selectfont
\input{章节内容/q1.tex}
\end{document}
'''
    (folder/'模型比较DEMO.tex').write_text(main_tex,encoding='utf-8')
    logs=[]
    for i in range(2):
        cmd=['xelatex','-interaction=nonstopmode','-halt-on-error','模型比较DEMO.tex']
        proc=subprocess.run(cmd,cwd=folder,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        log=folder/f'模型比较DEMO_{i+1}.log';log.write_text(proc.stdout+proc.stderr,encoding='utf-8')
        logs.append(dict(argv=cmd,returncode=proc.returncode,log=log.relative_to(root).as_posix()))
        if proc.returncode: raise RuntimeError('XeLaTeX failed: '+str(log))
    import fitz
    doc=fitz.open(folder/'模型比较DEMO.pdf')
    pages=[]
    for i,page in enumerate(doc):
        dest=folder/f'模型比较DEMO_page{i+1}.png'
        page.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(dest)
        pages.append(dest.relative_to(root).as_posix())
    text='\n'.join(page.get_text() for page in doc)
    if not all(s in text for s in ('Ridge','Random Forest','MLP','DEMO')):
        raise ValueError('PDF missing model labels or DEMO marking')
    warnings=(folder/'模型比较DEMO.log').read_text(encoding='utf-8',errors='replace')
    if any(s in warnings for s in ('Overfull \\hbox','Missing character','undefined references')):
        raise ValueError('Typesetting warning requires repair')
    write(root/'求解/验收输出/模型比较渲染.json',dict(status='RENDERED_REVIEW_REQUIRED',pages=pages,commands=logs,
        assurance='真实编译与文字检查；实际页面视觉复核另记，非完整论文验收'))
    print(json.dumps({'pages':pages},ensure_ascii=False))


if __name__=='__main__':
    sys.dont_write_bytecode=True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    main()
