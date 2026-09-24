"""Generate literal, auditable figure fragments from a diagram sidecar.

Put each input after the first-section description and reference. The final
FloatBarrier keeps deferred floats before the next subsection without shrinking.
"""
from pathlib import Path
import argparse
import json
import os


def generate(root, sidecar, main_tex, output_dir):
    from workspace_context import bounded
    root = Path(root).resolve()
    data = json.loads(bounded(root, str(sidecar)).read_text(encoding='utf-8-sig'))
    main = bounded(root, str(main_tex))
    out = bounded(root, str(output_dir)); out.mkdir(parents=True, exist_ok=True)
    ids = [q['overview_id'] for q in data['questions']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate overview mapping')
    records = []
    for q in data['questions']:
        candidates = [d for d in data['diagrams'] if d['diagram_id'] == q['overview_id'] and
                      d.get('problem_id') == q['problem_id'] and d.get('kind') == 'comprehensive' and d.get('placement') == 'body']
        if len(candidates) != 1:
            raise ValueError('Exactly one primary overview required: ' + q['problem_id'])
        d = candidates[0]
        label, caption = d['paper']['label'], d['paper']['caption']
        if any(c in label+caption for c in '{}\\\n'):
            raise ValueError('Use a plain short caption and label')
        vector = bounded(root, d['outputs']['vector'])
        path = os.path.relpath(vector, main.parent).replace('\\', '/')
        width = float(d['target_width_mm'])
        if width <= 0:
            raise ValueError('Positive width required')
        fragment = out / (q['problem_id'] + '-overview.tex')
        fragment.write_text('% Generated figure only; description and reference belong before this input.\n'
                            '\\begin{figure}[!htbp]\n\\centering\n'
                            + f'\\includegraphics[width={width:g}mm]{{{path}}}\n'
                            + f'\\caption{{{caption}}}\\label{{{label}}}\n'
                            + '\\end{figure}\n\\FloatBarrier\n', encoding='utf8')
        records.append(str(fragment.relative_to(root)))
    return records


if __name__ == '__main__':
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sidecar', required=True); p.add_argument('--main-tex', required=True)
    p.add_argument('--output-dir', required=True)
    a = p.parse_args()
    print(json.dumps(generate(Path.cwd(), a.sidecar, a.main_tex, a.output_dir), ensure_ascii=False))
