"""Compile false source or printed years against current, real source evidence."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'华为杯_求解规范/tools'))
from collect_academic_paper_review import compile_evidence, verify_evidence
from audit_citations import audit_source, audit_pdf
from reference_evidence import sha
from run_citation_smoke import build, install_reviewed_sources


def run(root, sources, reviews, xelatex, variant='false_year'):
    main, _ = build(root,sources,'valid')
    install_reviewed_sources(root,reviews)
    clean = audit_source(root/'论文输入.json')
    if clean['status'] != 'PASS': raise ValueError(clean['failures'])
    if variant == 'false_year':
        path=root/'reference.bib'
        text=path.read_text(encoding='utf-8')
        if 'year    = {2011}' not in text: raise ValueError('Missing expected publisher fixture year')
        path.write_text(text.replace('year    = {2011}','year    = {2099}',1),encoding='utf-8')
        # Refresh the inventory hash while retaining the genuine publisher capture.
        evidence_path=root/'文献证据.json'
        evidence=json.loads(evidence_path.read_text(encoding='utf-8'))
        evidence['bibliography_files'][0]['sha256']=sha(path)
        evidence_path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    elif variant == 'bad_style':
        # Only mutate the isolated fixture's style. The bibliography itself and
        # reviewed publisher evidence remain correct; compile hashes are current.
        path=root/'gmcm.bst'
        text=path.read_text(encoding='utf-8')
        marker='FUNCTION {format.year}'
        start=text.index(marker)
        end=text.index('FUNCTION ',start+len(marker))
        block=text[start:end]
        if block.count('{ year extract.before.dash }') != 1: raise ValueError('Unexpected year style implementation')
        path.write_text(text[:start]+block.replace('{ year extract.before.dash }','{ "2099" }')+text[end:],encoding='utf-8')
    else:
        raise ValueError(variant)
    review=compile_evidence(root,main,root/'review.json','codex',[],xelatex)
    compile_errors=verify_evidence(root,review,main,'codex',[],require_visual=False)
    source=audit_source(root/'论文输入.json')
    physical=audit_pdf(main.with_suffix('.pdf'),main,root/'论文输入.json')
    expected_source = 'PASS' if variant == 'bad_style' else 'FAIL'
    expected_error = '实际PDF字段不符：year' if variant == 'bad_style' else '元数据不符：year'
    report={'variant':variant,'expected_behavior_pass':not compile_errors and source['status']==expected_source and physical['status']=='FAIL' and
            any(expected_error in e for e in physical['failures']),
            'compile_evidence_failures':compile_errors,'source':source,'pdf':physical,
            'scope':'Deliberately false source or printed year in an isolated negative paper; source receipts and compile hashes remain current.'}
    (root/'source-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    import pymupdf as fitz
    with fitz.open(main.with_suffix('.pdf')) as doc:
        for i,p in enumerate(doc):
            if p.get_text().startswith('6 参考文献'):
                p.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(root/f'{variant}-page-{i+1:03d}.png')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--source-reviews',type=Path,required=True)
    p.add_argument('--xelatex',required=True)
    p.add_argument('--variant',choices=['false_year','bad_style'],default='false_year')
    a=p.parse_args()
    result=run(a.output.resolve(),a.sources.resolve(),a.source_reviews.resolve(),a.xelatex,a.variant)
    print(json.dumps({'expected_behavior_pass':result['expected_behavior_pass'],
                      'compile_evidence_failures':result['compile_evidence_failures'],
                      'source_failures':result['source']['failures'],'pdf_failures':result['pdf']['failures']},ensure_ascii=False))
    raise SystemExit(not result['expected_behavior_pass'])
