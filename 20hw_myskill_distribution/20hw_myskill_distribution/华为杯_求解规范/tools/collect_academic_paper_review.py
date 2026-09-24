#!/usr/bin/env python3
"""Compile the unchanged TeX source with an inclusion probe; prepare UNREVIEWED paper evidence."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from build_academic_figure_asset_index import safe, sha, write_json
from bibliography_inputs import (bibliography_inputs, bibliography_requested,
                                 generated_outputs, input_paths)

# Instrument graphicx in a wrapper, without editing the paper or official class.
# Width is the actual includegraphics box, not an assumed template constant.
PROBE = r'''\makeatletter
\newwrite\AFstream
\newcount\AFid
\newcount\AFpage
\newcount\AFtransform
\newsavebox\AFbox
\AddToHook{shipout/before}{\global\advance\AFpage by1}
\AddToHook{begindocument/end}{%
  \immediate\openout\AFstream=\jobname.afprobe
  \let\AFsetfile\Gin@setfile
  \def\Gin@setfile#1#2#3{\xdef\AFfile{#3}\AFsetfile{#1}{#2}{#3}}%
  \let\AFgraphics\includegraphics
  \let\AFresize\resizebox
  \let\AFscale\scalebox
  \let\AFrotate\rotatebox
  \RenewDocumentCommand\resizebox{s m m +m}{\begingroup\advance\AFtransform by1\IfBooleanTF{#1}{\AFresize*{#2}{#3}{#4}}{\AFresize{#2}{#3}{#4}}\endgroup}%
  \RenewDocumentCommand\scalebox{m o +m}{\begingroup\advance\AFtransform by1\IfNoValueTF{#2}{\AFscale{#1}{#3}}{\AFscale{#1}[#2]{#3}}\endgroup}%
  \RenewDocumentCommand\rotatebox{O{} m +m}{\begingroup\advance\AFtransform by1\AFrotate[#1]{#2}{#3}\endgroup}%
  \RenewDocumentCommand\includegraphics{s O{} m}{%
    \ifnum\AFtransform>0\PackageError{academic-paper-probe}{Outer graphics transformation is not measurable here}{Use includegraphics width/height/angle directly for the planned figure.}\fi
    \global\advance\AFid by1
    \gdef\AFfile{}%
    \sbox\AFbox{\IfBooleanTF{#1}{\AFgraphics*[#2]{#3}}{\AFgraphics[#2]{#3}}}%
    \immediate\write\AFstream{FIG|\number\AFid|\AFfile|\the\wd\AFbox|\the\ht\AFbox|\the\textwidth|\the\dp\AFbox}%
    \edef\AFdeferred{\noexpand\write\AFstream{PAGE|\number\AFid|\noexpand\number\noexpand\AFpage}}%
    \AFdeferred\leavevmode\hypertarget{gmcm.graphic.\number\AFid}{\usebox\AFbox}%
  }%
}
\makeatother
'''

def read_probe(path, cwd):
    rows = {}; pages = {}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        parts = line.split('|')
        if parts[0] == 'FIG' and len(parts) == 7:
            raw = parts[2].strip().strip('"')
            source = Path(raw)
            source = (cwd / source).resolve() if not source.is_absolute() else source.resolve()
            def mm(s):
                if not s.endswith('pt'): raise ValueError('Unexpected TeX dimension: '+s)
                return float(s[:-2]) / 72.27 * 25.4
            rows[int(parts[1])] = {'path': source, 'display_width_mm': mm(parts[3]),
                'display_height_mm': mm(parts[4]), 'text_width_mm': mm(parts[5]),
                'display_depth_mm': mm(parts[6])}
        elif parts[0] == 'FIG':
            raise ValueError('Outdated or invalid inclusion probe; recompile for physical coordinates')
        elif parts[0] == 'PAGE' and len(parts) == 3:
            pages.setdefault(int(parts[1]), []).append(int(parts[2]))
    for key, row in rows.items():
        if len(pages.get(key, [])) != 1: raise ValueError('Unshipped or reused graphic box: '+str(key))
        row['page_number'] = pages[key][0]
    return rows

def locate_graphics(doc, rows):
    """Recover actual shipout baselines from PDF destinations, not editable JSON."""
    import pymupdf as fitz
    names = doc.resolve_names()
    for key, row in rows.items():
        anchor = names.get('gmcm.graphic.'+str(key), {})
        page = anchor.get('page')
        if page != row['page_number']-1 or anchor.get('to') is None:
            raise ValueError('Missing or inconsistent graphic destination: '+str(key))
        point = fitz.Point(anchor['to']) * doc[page].transformation_matrix
        scale = 72 / 25.4
        box = [point.x, point.y-row['display_height_mm']*scale,
               point.x+row['display_width_mm']*scale, point.y+row['display_depth_mm']*scale]
        if not doc[page].rect.contains(fitz.Rect(box)):
            raise ValueError('Graphic extends outside physical PDF page: '+str(key))
        row['pdf_bbox'] = box
    return rows

def read_fls(path, cwd):
    inputs = set()
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('INPUT '):
            item = Path(line[6:].strip().strip('"'))
            item = (cwd/item).resolve() if not item.is_absolute() else item.resolve()
            if item.is_file(): inputs.add(item)
    return inputs

def compile_evidence(root, main_tex, output, runtime, figure_specs, xelatex=None):
    """Low-level collector also used for isolated tests; grants no gate or visual approval."""
    import pymupdf as fitz
    root = Path(root).resolve(); main = safe(root, str(main_tex)); out = safe(root, str(output))
    if runtime not in {'codex', 'claude'}: raise ValueError('Explicit runtime required')
    from workspace_resources import dependencies
    resource_dependencies = dependencies(root,runtime,'paper')
    if out.exists(): raise ValueError('Review exists; retain it and choose a new evidence path')
    work = out.parent / (out.stem+'_files'); work.mkdir(parents=True, exist_ok=True)
    exe = xelatex or shutil.which('xelatex')
    if not exe: raise ValueError('XeLaTeX not found')
    rel = lambda p: p.resolve().relative_to(root).as_posix()
    wrapper = work/'probe_wrapper.tex'
    wrapper.write_text(PROBE+'\n\\input{'+main.name+'}\n', encoding='utf-8')
    before_main = sha(main)
    before_vectors = {s['vector_path']: sha(safe(root,s['vector_path'])) for s in figure_specs}
    # The final paper always contains the generated minted appendix.  Full
    # shell escape is explicit so latexminted/Pygments works consistently on
    # TeX Live and MiKTeX instead of depending on local restricted-shell lists.
    command = [str(exe), '-shell-escape', '-interaction=nonstopmode', '-halt-on-error', '-file-line-error',
               '-recorder', '-jobname='+main.stem, '-output-directory=.', wrapper.as_posix()]
    # cwd already is main.parent. A relative output directory avoids passing a
    # Chinese Windows path through TeX's narrow environment to latexminted.
    started = time.time_ns(); runs = []; bibliography_run = None; bib_inputs = []
    env = dict(os.environ)
    env['PATH'] = str(Path(exe).resolve().parent) + os.pathsep + env.get('PATH', '')
    def run_command(cmd, name, run_env=None):
        result = subprocess.run(cmd, cwd=main.parent, env=run_env or env, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=300)
        log = work/(name+'.log'); log.write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
        row = {'command': cmd, 'cwd':str(main.parent), 'returncode':result.returncode,
               'log_path':rel(log), 'log_sha256':sha(log)}
        if result.returncode: raise ValueError('Compilation failed; inspect '+str(log))
        return row
    runs.append(run_command(command, 'compile_1'))
    if bibliography_requested(main):
        bibtex = Path(exe).resolve().with_name('bibtex.exe' if os.name == 'nt' else 'bibtex')
        if not bibtex.is_file(): raise ValueError('BibTeX not found beside XeLaTeX')
        bibliography_run = run_command([str(bibtex), main.stem], 'bibliography',
                                       dict(env, KPATHSEA_DEBUG='4'))
        bib_inputs = bibliography_inputs(root, main, safe(root, bibliography_run['log_path']))
        runs.append(run_command(command, 'compile_2'))
    def pagination_state():
        return {suffix: sha(main.with_suffix(suffix)) for suffix in ('.aux', '.toc', '.out') if main.with_suffix(suffix).is_file()}
    previous_state = pagination_state()
    runs.append(run_command(command, 'compile_final'))
    current_state = pagination_state()
    while current_state != previous_state and len(runs) < 6:
        previous_state = current_state
        runs.append(run_command(command, 'compile_stable_' + str(len(runs) + 1)))
        current_state = pagination_state()
    if current_state != previous_state:
        raise ValueError('交叉引用/目录分页六遍后仍不稳定；检查日志并修订，不能采集通过证据')
    pdf = main.with_suffix('.pdf'); fls = main.with_suffix('.fls'); probe = main.with_suffix('.afprobe')
    if any(not p.is_file() or p.stat().st_mtime_ns < started for p in (pdf, fls, probe)):
        raise ValueError('Missing or stale compilation outputs')
    if sha(main)!=before_main or any(sha(safe(root,p))!=h for p,h in before_vectors.items()):
        raise ValueError('Main source or planned vector changed during compilation')
    inputs = read_fls(fls, main.parent); inclusions = read_probe(probe, main.parent)
    bib_paths = input_paths(root, bib_inputs)
    if bibliography_run and bib_inputs != bibliography_inputs(root, main, safe(root, bibliography_run['log_path'])):
        raise ValueError('Bibliography inputs changed during compilation')
    if any(p.stat().st_mtime_ns > started for p in bib_paths):
        raise ValueError('Bibliography inputs changed during compilation')
    # Snapshot the exact local source closure reported by the engine. External TeX
    # distribution dependencies are recorded separately, not mistaken for project source.
    source_ext = {'.tex','.sty','.cls','.bib','.bst','.cfg','.def','.clo'}
    sources = {rel(p):sha(p) for p in inputs | bib_paths if p.is_relative_to(root) and p.suffix.lower() in source_ext}
    if rel(main) not in sources: raise ValueError('Main source absent from recorder')
    if any(safe(root,p).stat().st_mtime_ns > started for p in sources):
        raise ValueError('Source closure changed during compilation')
    figures=[]
    with fitz.open(pdf) as doc:
        locate_graphics(doc, inclusions)
        for spec in figure_specs:
            vector=safe(root,spec['vector_path'])
            matches=[(k,r) for k,r in inclusions.items() if r['path']==vector]
            if vector not in inputs or not matches: raise ValueError('Planned vector not actually included: '+str(vector))
            occurrences=[]
            for key,row in matches:
                page_no=row['page_number']
                if not 1<=page_no<=len(doc): raise ValueError('Invalid shipout page: '+str(page_no))
                preview=work/f'page_{page_no:03d}.png'
                doc[page_no-1].get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).save(preview)
                occurrences.append({k:v for k,v in row.items() if k!='path'} | {
                    'probe_id':key,'page_render_path':rel(preview),'page_render_sha256':sha(preview),
                    'reviewed':False,'tool_ref':'','observation':''})
            figures.append({'figure_id':spec['figure_id'],'vector_path':spec['vector_path'],
                'vector_sha256':sha(vector),'occurrences':occurrences})
        page_count=len(doc)
    record={'schema_version':'2.2','runtime':runtime,'status':'REVIEW_REQUIRED',
        'resource_dependencies':resource_dependencies,
        'main_tex':rel(main),'main_tex_sha256':sha(main),'pdf_path':rel(pdf),'pdf_sha256':sha(pdf),
        'pdf_pages':page_count,'source_closure':sources,'started_at_ns':started,'compile_runs':runs,
        'bibliography_run':bibliography_run, 'bibliography_inputs':bib_inputs,
        'generated_outputs':generated_outputs(root, main),
        'fls_path':rel(fls),'fls_sha256':sha(fls),'probe_path':rel(probe),'probe_sha256':sha(probe),
        'figures':figures,'portfolio_review':{'reviewed':False,'tool_ref':'','observation':''},
        'pagination_stability': {'previous':previous_state,'current':current_state},
        'assurance':'Real XeLaTeX includegraphics box and shipout measurements. Public outer resize/scale/rotate wrappers fail explicitly; use includegraphics width/height/angle. Editable records do not prove viewing.'}
    manifest_path = main.parent / '论文输入.json'
    if manifest_path.is_file():
        import sys
        paper_tools = Path(__file__).resolve().parents[2] / '华为杯_论文规范模板/tools'
        if str(paper_tools) not in sys.path: sys.path.insert(0, str(paper_tools))
        from audit_pdf_layout import audit_layout
        from first_chapters_pdf import prepare_review
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        review_path = (main.parent / manifest['first_chapters_review_path']).resolve()
        review_path.relative_to(main.parent)
        prepare_review(pdf, audit_layout(pdf, main, manifest_path), review_path)
        record['first_chapters_review_path'] = rel(review_path)
    write_json(out,record)
    return record

def verify_evidence(root, review, main_tex, runtime, figure_specs, require_visual=True):
    """Re-derive inclusion, dimensions and recorder closure instead of trusting typed JSON."""
    root=Path(root).resolve(); main=safe(root,str(main_tex)); failures=[]
    def check(code,ok):
        if not ok: failures.append(code)
    try:
        from audit_academic_figure_assets import schema_errors
        schema=json.loads((Path(__file__).resolve().parent.parent/'academic_paper_review.schema.json').read_text(encoding='utf-8-sig'))
        errors=schema_errors(review,schema)
        if errors: return ['paper_schema: '+x for x in errors]
        from workspace_resources import evidence_current
        check('paper_resource_dependencies_current',evidence_current(root,runtime,'paper',review))
        check('paper_runtime',review['runtime']==runtime)
        check('paper_main',safe(root,review['main_tex'])==main and review['main_tex_sha256']==sha(main))
        for key in ('pdf','fls','probe'):
            p=safe(root,review[key+'_path'])
            check('paper_'+key+'_current',p.is_file() and sha(p)==review[key+'_sha256'])
        inputs=read_fls(safe(root,review['fls_path']),main.parent)
        bib = review['bibliography_run']
        requested = bibliography_requested(main)
        check('paper_bibliography_run_matches_aux', bool(bib) == requested)
        actual_bib_inputs = []
        if bib:
            check('paper_bibliography_compile', requested and 3 <= len(review['compile_runs']) <= 6 and
                  bib['returncode']==0 and sha(safe(root,bib['log_path']))==bib['log_sha256'])
            actual_bib_inputs = bibliography_inputs(root, main, safe(root,bib['log_path']))
        check('paper_bibliography_inputs_current', review['bibliography_inputs'] == actual_bib_inputs)
        bib_paths = input_paths(root, actual_bib_inputs)
        source_ext={'.tex','.sty','.cls','.bib','.bst','.cfg','.def','.clo'}
        expected={p.relative_to(root).as_posix():sha(p) for p in inputs | bib_paths if p.is_relative_to(root) and p.suffix.lower() in source_ext}
        check('paper_source_closure',review['source_closure']==expected and main in inputs)
        generated=generated_outputs(root, main)
        check('paper_generated_outputs_current',review['generated_outputs']==generated and
              main.with_suffix('.aux').relative_to(root).as_posix() in generated)
        check('paper_double_compile',2 <= len(review['compile_runs']) <= 6 and all(
            x['returncode']==0 and sha(safe(root,x['log_path']))==x['log_sha256'] for x in review['compile_runs']))
        stability = review.get('pagination_stability', {})
        current = {suffix:sha(main.with_suffix(suffix)) for suffix in ('.aux','.toc','.out') if main.with_suffix(suffix).is_file()}
        check('paper_pagination_stable', bool(current) and stability.get('previous') == current == stability.get('current'))
        rows=read_probe(safe(root,review['probe_path']),main.parent)
        import pymupdf as fitz
        from PIL import Image
        with fitz.open(safe(root,review['pdf_path'])) as pdf:
            locate_graphics(pdf, rows)
            check('paper_pdf_page_count',len(pdf)==review['pdf_pages'])
            expected_pages={}
            for f in review['figures']:
                for x in f['occurrences']:
                    page=x['page_number']
                    if page not in expected_pages:
                        pix=pdf[page-1].get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False)
                        expected_pages[page]=(pix.width,pix.height,pix.samples)
                    with Image.open(safe(root,x['page_render_path'])) as im:
                        width,height,pixels=expected_pages[page]
                        check(f['figure_id']+':paper_preview_is_actual_pdf',im.size==(width,height) and im.convert('RGB').tobytes()==pixels)
        by_id={f['figure_id']:f for f in review['figures']}
        check('paper_figure_ids',len(by_id)==len(review['figures']) and set(by_id)=={s['figure_id'] for s in figure_specs})
        for spec in figure_specs:
            fid=spec['figure_id']; item=by_id[fid]; vector=safe(root,spec['vector_path'])
            check(fid+':paper_exact_vector',item['vector_path']==spec['vector_path'] and vector in inputs and item['vector_sha256']==sha(vector))
            matches={k:r for k,r in rows.items() if r['path']==vector}
            occ=item['occurrences'];check(fid+':paper_occurrences',bool(matches) and len(occ)==len(matches) and {x['probe_id'] for x in occ}==set(matches))
            for x in occ:
                raw=matches[x['probe_id']]
                check(fid+':paper_measurement',all(x[k]==raw[k] for k in ['display_width_mm','display_height_mm','display_depth_mm','text_width_mm','page_number','pdf_bbox']) and abs(raw['display_width_mm']-spec['target_width_mm'])<0.5)
                check(fid+':paper_preview',sha(safe(root,x['page_render_path']))==x['page_render_sha256'])
                if require_visual: check(fid+':paper_view',x.get('reviewed') is True and bool(x.get('tool_ref','').strip()) and bool(x.get('observation','').strip()))
        if require_visual:
            p=review['portfolio_review'];check('paper_portfolio_view',p.get('reviewed') is True and bool(p.get('tool_ref','').strip()) and bool(p.get('observation','').strip()))
    except (KeyError,ValueError,TypeError,OSError,IndexError) as exc: failures.append('paper_evidence_invalid: '+str(exc))
    return failures

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,default=Path('.'));p.add_argument('--main-tex',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--runtime',choices=['codex','claude'],required=True);p.add_argument('--xelatex')
    p.add_argument('--allow-demo',action='store_true',help='Collect isolated demo pages; never admits demo to production paper gate')
    a=p.parse_args();root=a.project_root.resolve()
    from audit_visual_plan import audit
    from prepare_academic_figure_review import sidecar_path
    try:
        plan=safe(root,str(a.plan));gate=audit(plan,'render',root,None,allow_demo=a.allow_demo,runtime=a.runtime)
        if gate['status']!='PASS':raise ValueError('Render gate failed: '+json.dumps(gate['failures'],ensure_ascii=False))
        refs=json.loads(sidecar_path(plan).read_text(encoding='utf-8-sig')) if sidecar_path(plan).is_file() else {'figures':[]}
        from visual_routes import paper_specs, media_sidecar
        specs=paper_specs(plan)
        from modelviz_bridge import sidecar as modelviz_sidecar
        from audit_diagram_workflow import sidecar, load
        result=compile_evidence(root,a.main_tex,a.output,a.runtime,specs,a.xelatex)
        refs['paper_review_path']=safe(root,str(a.output)).relative_to(root).as_posix()
        if sidecar_path(plan).is_file():write_json(sidecar_path(plan),refs)
        if media_sidecar(plan).is_file():
            media=load(media_sidecar(plan));media['paper_review_path']=refs['paper_review_path']
            write_json(media_sidecar(plan),media)
        if modelviz_sidecar(plan).is_file():
            modelviz=load(modelviz_sidecar(plan));modelviz['paper_review_path']=refs['paper_review_path']
            write_json(modelviz_sidecar(plan),modelviz)
        diagrams=load(sidecar(plan));diagrams['paper_review_path']=refs['paper_review_path']
        write_json(sidecar(plan),diagrams)
        print(json.dumps({'status':result['status'],'figures':len(result['figures']),'output':str(a.output)},ensure_ascii=False))
    except Exception as exc:print(json.dumps({'status':'FAIL','error':str(exc)},ensure_ascii=False));return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
