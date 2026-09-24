"""Isolated maintenance regression for ordinary references plus AI disclosure."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    solver_tools = Path(__file__).resolve().parents[2] / "华为杯_求解规范/tools"
    sys.path.insert(0, str(solver_tools))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

from ai_disclosure import AI_DISCLOSURE, AI_KEY, AI_TEXT, AI_TEX_HOOK, disclosure_record, ensure_evidence_record
from audit_citations import audit_pdf, audit_source
from reference_evidence import reference_inventory_errors, sha
from test_paper_contract import make_fixture
from build_latex import build_main, copy_assets


def _source_record(root: Path, key: str, number: int) -> dict:
    title = f"English Reference {number}"
    quote = f"Evidence for reference {number}"
    capture = root / f"{key}.txt"
    capture.write_text(
        f"Author Example. {title}. 2001. English Journal. 1. 10--20. {quote}.",
        encoding="utf-8",
    )
    receipt = root / f"{key}-receipt.json"
    receipt.write_text(json.dumps({
        "requested_url": f"https://example.org/{key}",
        "final_url": f"https://example.org/{key}",
        "sha256": sha(capture),
        "status": 200,
        "retrieved_utc": "2026-09-22T00:00:00+00:00",
        "fixture": True,
    }), encoding="utf-8")
    source = {
        "url": f"https://example.org/{key}",
        "authority": "publisher",
        "authority_reason": "Controlled maintenance fixture; source fields are synthetic and are not scientific evidence.",
        "capture_path": capture.name,
        "capture_sha256": sha(capture),
        "receipt_path": receipt.name,
        "receipt_sha256": sha(receipt),
        "format": "field_quotes",
        "field_quotes": {
            "authors": [{"value": "Author Example", "quote": "Author Example"}],
            "title": [{"value": title, "quote": title}],
            "year": [{"value": "2001", "quote": "2001"}],
            "container": [{"value": "English Journal", "quote": "English Journal"}],
            "volume": [{"value": "1", "quote": "1"}],
            "pages": [{"value": "10--20", "quote": "10--20"}],
        },
        "review": {
            "reviewed": True,
            "tool_ref": "synthetic-maintenance-fixture",
            "observation": "Fixture fields are checked for parser and PDF binding behavior only; they are not a source approval.",
        },
    }
    body_excerpt = f"English evidence sentence {number}\\cite{{{key}}}."
    return {
        "key": key,
        "reference_type": "ordinary",
        "sources": [source],
        "manual_metadata": {
            "kind": "article",
            "title": title,
            "authors": ["Author Example"],
            "year": "2001",
            "container": "English Journal",
            "volume": "1",
            "pages": "10--20",
        },
        "usages": [{
            "chapter_id": "c4",
            "body_excerpt": body_excerpt,
            "source_excerpt": quote,
            "relevance": "The fixture binds an English source excerpt to its body citation for parser regression only.",
            "reviewed": True,
            "tool_ref": "synthetic-maintenance-fixture",
        }],
    }


def build_fixture(root: Path, count: int = 10, *, bibtex: bool = False, early: bool = False) -> tuple[Path, list[str]]:
    root.mkdir(parents=True, exist_ok=True)
    manifest = make_fixture(root, 1)
    keys = [f"ref{i:02d}" for i in range(1, count + 1)]
    body = "\\section{问题一求解与分析}\n\\subsection{问题的描述与分析}\n"
    body += "\n".join(f"English evidence sentence {i}\\cite{{{key}}}." for i, key in enumerate(keys, 1))
    body += "\n\\subsection{模型与验证}\nThe fixture contains English references only.\n"
    (root / "c4.tex").write_text(body, encoding="utf-8")
    bibitems = [
        f"\\bibitem{{{key}}} Author Example. English Reference {i}. English Journal, 1:10--20, 2001."
        for i, key in enumerate(keys, 1)
    ]
    (root / "c6.tex").write_text("\\begin{thebibliography}{10}\n" + "\n".join(bibitems) + "\n\\end{thebibliography}\n", encoding="utf-8")
    if bibtex:
        (root/'c6.tex').write_text(r'\bibliographystyle{gmcm}\bibliography{reference}', encoding='utf8')
        (root/'reference.bib').write_text('\n'.join(
            '@article{'+key+', author={Author Example}, title={English Reference '+str(i)+'}, '
            'year={2001}, journal={English Journal}, volume={1}, pages={10--20}}'
            for i,key in enumerate(keys,1)), encoding='utf8')
    early_excerpt = r'隔离夹具的AI标注排版测试（不声明真实使用）\cite{ai_tool_disclosure}。'
    if early:
        body = body.replace('\\subsection{问题的描述与分析}\n',
            '\\subsection{问题的描述与分析}\n'+early_excerpt+'\n',1)
        (root/'c4.tex').write_text(body,encoding='utf8')
    from test_first_chapters import fixture_evidence
    fixture_evidence(root, manifest)
    records = [_source_record(root, key, i) for i, key in enumerate(keys, 1)]
    if bibtex:
        for row in records:
            row.pop('manual_metadata')
    ai = disclosure_record()
    if early:
        log = root/'ai-log.txt'
        log.write_text('SYNTHETIC FIXTURE ONLY: AI辅助文本的实际使用位置',encoding='utf8')
        ai['usage_status'] = 'adopted'
        ai['usages'] = [{
            'chapter_id':'c4', 'body_excerpt':early_excerpt,
            'ai_output_excerpt':'AI辅助文本的实际使用位置', 'record_path':log.name,
            'record_sha256':sha(log), 'record_excerpt':log.read_text(encoding='utf8'),
            'purpose':'tool_disclosure', 'reviewed':True,
            'tool_ref':'synthetic-maintenance-fixture',
            'relevance':'Synthetic regression fixture only; no actual use or scientific approval is asserted.'}]
    book_source = root/('reference.bib' if bibtex else 'c6.tex')
    evidence = {
        "schema_version": "1.1",
        "bibliography_files": [{"path": book_source.name, "sha256": sha(book_source)}],
        "references": records + [ai],
    }
    (root / "文献证据.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["references_evidence_path"] = "文献证据.json"
    (root / "论文输入.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    ensure_evidence_record(root / "论文输入.json")
    text, _ = build_main(manifest, root, include_appendix=False)
    text = text.replace("\\end{document}", "\\clearpage\\section{附录}\n\\end{document}")
    main = root / "论文.tex"
    main.write_text(text, encoding="utf-8")
    template = Path(__file__).resolve().parents[1]
    copy_assets(template, root, include_appendix=False)
    return main, keys


def compile_fixture(main: Path, xelatex: str) -> list[dict]:
    env = dict(os.environ)
    env["PATH"] = str(Path(xelatex).parent) + os.pathsep + env.get("PATH", "")
    commands = [
        [xelatex, "-shell-escape", "-interaction=nonstopmode", "-halt-on-error", main.name],
        [xelatex, "-shell-escape", "-interaction=nonstopmode", "-halt-on-error", main.name],
    ]
    if (main.parent/'reference.bib').exists():
        commands.insert(1, [str(Path(xelatex).with_name('bibtex.exe')), main.stem])
        commands.append(commands[0])
    runs = []
    for command in commands:
        proc = subprocess.run(command, cwd=main.parent, env=env, capture_output=True)
        runs.append({"command": command, "exit_code": proc.returncode})
        (main.parent / f"compile-{len(runs)}.log").write_bytes(proc.stdout + proc.stderr)
        if proc.returncode:
            break
    return runs


def inventory_cases(keys: list[str]) -> dict:
    ordinary = [{"key": key, "reference_type": "ordinary"} for key in keys]
    ai = disclosure_record()
    cases = {
        "ten_ordinary_plus_ai": ordinary + [ai],
        "nine_ordinary_plus_ai": ordinary[:-1] + [ai],
        "missing_ai": ordinary,
        "duplicate_ai": ordinary + [ai, dict(ai)],
        "ai_not_last": [ai] + ordinary,
        "wrong_ai_date": ordinary + [dict(ai, ai_disclosure={**AI_DISCLOSURE, "date": "2026-09-22"})],
    }
    result = {}
    for name, rows in cases.items():
        failures = reference_inventory_errors(rows, keys)
        result[name] = {"passed_expected": not failures if name == "ten_ordinary_plus_ai" else bool(failures), "failures": failures}
    moved = reference_inventory_errors(ordinary + [{"key": "extra", "reference_type": "ordinary"}, ai], keys + ["extra"])
    result["ordinary_count_moves_ai_number"] = {"passed_expected": not moved, "failures": moved}
    early_ai = ordinary + [dict(ai)]
    result["ai_early_body_annotation_keeps_tail_rule"] = {
        "passed_expected": not reference_inventory_errors(early_ai, keys + [AI_KEY]),
        "failures": reference_inventory_errors(early_ai, keys + [AI_KEY]),
    }
    return result


def negative_pdf_cases(output: Path, xelatex: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    cases=[]
    for variant in ('missing_ai', 'duplicate_ai', 'wrong_model', 'wrong_date', 'extra_mark', 'ai_not_last', 'ordinary_order'):
        root=output/variant
        main,_=build_fixture(root,early=True)
        text=main.read_text(encoding='utf8')
        if variant=='missing_ai': text=text.replace(AI_TEX_HOOK,'')
        elif variant=='duplicate_ai': text=text.replace(AI_TEX_HOOK,AI_TEX_HOOK+'\n'+AI_TEX_HOOK)
        elif variant=='wrong_model': text=text.replace('DeepSeek-V4.1-Flash','DeepSeek-wrong')
        elif variant=='wrong_date': text=text.replace('2026-09-23','2026-09-22')
        elif variant=='extra_mark': text=text.replace(AI_TEXT,'[M] '+AI_TEXT)
        elif variant=='ai_not_last':
            text=text.replace(AI_TEX_HOOK,'')
            refs=root/'c6.tex'
            refs.write_text(refs.read_text(encoding='utf8').replace(r'\begin{thebibliography}{10}',
                r'\begin{thebibliography}{10}\bibitem{ai_tool_disclosure}'+AI_TEXT),encoding='utf8')
        elif variant=='ordinary_order':
            refs=root/'c6.tex'
            lines=refs.read_text(encoding='utf8').splitlines()
            lines[1],lines[2]=lines[2],lines[1]
            refs.write_text('\n'.join(lines),encoding='utf8')
        main.write_text(text,encoding='utf8')
        runs=compile_fixture(main,xelatex)
        if runs[-1]['exit_code']:
            raise ValueError('Negative must compile before testing the PDF gate: '+variant)
        physical=audit_pdf(main.with_suffix('.pdf'),main,root/'论文输入.json')
        # Verify the actual physical failures, not just stale source hashes.
        expected={'missing_ai':'ai_disclosure_has_generated', 'duplicate_ai':'bibcite',
                  'wrong_model':'正文格式', 'wrong_date':'正文格式', 'extra_mark':'正文格式',
                  'ai_not_last':'固定AI披露键','ordinary_order':'numbered_by_first_body_appearance'}[variant]
        passed=physical['status']=='FAIL' and any(expected in f for f in physical['failures'])
        cases.append({'variant':variant,'passed':passed,'runs':runs,'pdf':physical})
    result={'status':'PASS' if all(c['passed'] for c in cases) else 'FAIL', 'cases':cases,
            'scope':'Intentionally invalid synthetic PDFs; expected rejection is not paper acceptance.'}
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result


def run(output: Path, xelatex: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for mode,count,early in [('manual',10,False),('manual',14,True),('bibtex',10,True),('bibtex',14,True)]:
        root = output/f'{mode}-{count}'
        main,keys = build_fixture(root,count,bibtex=mode=='bibtex',early=early)
        # Regeneration is byte-for-byte stable and adds no second hook or record.
        manifest = json.loads((root/'论文输入.json').read_text(encoding='utf8'))
        before = (root/'文献证据.json').read_bytes()
        stable_record = not ensure_evidence_record(root/'论文输入.json') and before == (root/'文献证据.json').read_bytes()
        text,_ = build_main(manifest,root,include_appendix=False)
        stable_hook = text.count('ai_tool_disclosure') == 1
        runs = compile_fixture(main,xelatex)
        source = audit_source(root/'论文输入.json')
        physical = audit_pdf(main.with_suffix('.pdf'), main, root/'论文输入.json') if runs[-1]['exit_code']==0 else {'status':'FAIL','failures':['compile failed']}
        from audit_citations import auxiliary_numbers
        numbers = auxiliary_numbers(main)
        previews=[]
        if runs[-1]['exit_code']==0:
            import pymupdf as fitz
            with fitz.open(main.with_suffix('.pdf')) as doc:
                for i,page in enumerate(doc):
                    if 'English evidence sentence' in page.get_text() or 'DeepSeek' in page.get_text():
                        preview=root/f'page-{i+1}.png'
                        page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(preview)
                        previews.append(str(preview))
        row={'variant':root.name,'runs':runs,'source':source,'pdf':physical,
             'ai_number':numbers.get(AI_KEY),'expected_number':count+1,
             'repeat_generation_stable':stable_record and stable_hook,'previews':previews}
        row['passed']=source['status']==physical['status']=='PASS' and row['ai_number']==count+1 and row['repeat_generation_stable']
        cases.append(row)
    inventory=inventory_cases([f'ref{i:02d}' for i in range(1,11)])
    result={'status':'PASS' if all(c['passed'] for c in cases) and all(c['passed_expected'] for c in inventory.values()) else 'FAIL',
            'cases':cases,'inventory':inventory,
            'scope':'SYNTHETIC maintenance fixtures, not genuine source approvals, AI use records, or formal paper results.'}
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--xelatex',required=True)
    parser.add_argument('--negative-pdf',action='store_true')
    args=parser.parse_args()
    result=(negative_pdf_cases if args.negative_pdf else run)(args.output.resolve(),args.xelatex)
    print(json.dumps({'status':result['status'],'cases':[{k:c.get(k) for k in ('variant','passed','ai_number')} for c in result['cases']]}))
    raise SystemExit(result['status']!='PASS')
