"""Real compilation and stale-input rejection; not a ten-reference paper test."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)


import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_论文规范模板/tools'))

from bibliography_inputs import input_paths
from collect_academic_paper_review import compile_evidence, verify_evidence
from run_layout_smoke import create_fixture


def exercise_mutations(root: Path, main: Path, review: dict, specs: list) -> list[dict]:
    rows = []

    def check(name, candidate):
        failures = verify_evidence(root, candidate, main, 'codex', specs, require_visual=False)
        rows.append({'case': name, 'rejected': bool(failures), 'failures': failures})

    for path in sorted(input_paths(root, review['bibliography_inputs'])):
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n% changed after compilation\n')
            check('changed_' + path.name, review)
        finally:
            path.write_bytes(original)
    candidate = copy.deepcopy(review)
    candidate['bibliography_inputs'] = []
    check('deleted_input_inventory', candidate)
    candidate = copy.deepcopy(review)
    for row in candidate['bibliography_inputs']:
        row['sha256'] = '0' * 64
    check('forged_input_hashes', candidate)
    candidate = copy.deepcopy(review)
    candidate['source_closure'] = {p: h for p, h in candidate['source_closure'].items()
                                   if Path(p).suffix not in {'.bib', '.bst'}}
    check('omitted_bibtex_sources_from_closure', candidate)
    candidate = copy.deepcopy(review)
    candidate['schema_version'] = '2.1'
    candidate.pop('bibliography_inputs')
    check('old_2_1_record', candidate)
    # A plain version-string edit does not create missing actual-open evidence.
    candidate['schema_version'] = '2.2'
    check('old_record_version_only_edit', candidate)
    clean = verify_evidence(root, review, main, 'codex', specs, require_visual=False)
    rows.append({'case': 'restored_original_inputs', 'accepted': not clean, 'failures': clean})
    return rows


def run(output: Path, xelatex: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    shared = output / 'shared-bibliography'
    shared.mkdir()
    for variant in ('nested_aux_external_database', 'manual_bibliography'):
        root = output / variant
        main = create_fixture(root, 1)
        ref = root / 'c6.tex'
        if variant == 'nested_aux_external_database':
            (shared/'reference.bib').write_bytes((root/'reference.bib').read_bytes())
            (root/'reference.bib').unlink()
            (root/'extra.bib').write_text('% Empty second input tests multiple database reads.\n', encoding='utf-8')
            ref.write_text(ref.read_text(encoding='utf-8').replace(
                r'\bibliography{reference}', r'\bibliography{../shared-bibliography/reference,extra}'), encoding='utf-8')
            main.write_text(main.read_text(encoding='utf-8').replace(
                r'\input{c6.tex}', r'\include{c6}'), encoding='utf-8')
        else:
            ref.write_text(r'\begin{thebibliography}{1}' '\n'
                           r'\bibitem{knuth} Donald E. Knuth. The Art of Computer Programming, '
                           r'Volume 1: Fundamental Algorithms. 3rd ed. Addison-Wesley, 1997.' '\n'
                           r'\end{thebibliography}' '\n', encoding='utf-8')
        review = compile_evidence(root, main, root/'review.json', 'codex', [], xelatex)
        failures = verify_evidence(root, review, main, 'codex', [], require_visual=False)
        row = {'variant': variant, 'failures': failures,
               'bibliography_inputs': review['bibliography_inputs'],
               'compile_passes': len(review['compile_runs']),
               'generated_outputs': list(review['generated_outputs'])}
        if variant == 'nested_aux_external_database':
            row['mutations'] = exercise_mutations(root, main, review, [])
            child = root/'c6.aux'
            original = child.read_bytes()
            try:
                child.write_bytes(original + b'\n% changed nested AUX\n')
                errors = verify_evidence(root, review, main, 'codex', [], require_visual=False)
                row['mutations'].append({'case': 'changed_nested_aux', 'rejected': bool(errors), 'failures': errors})
            finally:
                child.write_bytes(original)
            row['passed'] = (not failures and row['compile_passes'] == 3 and
                any(r['scope']=='external' and r['kind']=='database' for r in review['bibliography_inputs']) and
                len(review['bibliography_inputs']) == 3 and 'c6.aux' in review['generated_outputs'] and
                all(r.get('rejected', r.get('accepted', False)) for r in row['mutations']))
        else:
            row['passed'] = not failures and not review['bibliography_inputs'] and row['compile_passes'] == 2
        cases.append(row)
    result = {'status': 'PASS' if all(r['passed'] for r in cases) else 'FAIL', 'cases': cases,
              'scope': 'Actual bibliography file closure, nested AUX, manual bibliography compatibility and stale evidence only. '
                       'One real book used as a formatting probe; neither ten references nor scientific acceptance is claimed.'}
    (output/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xelatex', required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.xelatex)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(result['status'] != 'PASS')
