#!/usr/bin/env python3
"""Structural/export checks for the revised figure; visual review is separate."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image

HERE=Path(__file__).resolve().parent
NS={'s':'http://www.w3.org/2000/svg'}


def validate(root_dir: Path=HERE) -> dict:
    checks=[]
    label_sets=[]
    for name in ['mono','qinglu']:
        svg=root_dir/'assets'/f'workflow_{name}_v3.svg'
        root=ET.parse(svg).getroot()
        ids=[e.get('id') for e in root.iter() if e.get('id')]
        assert len(ids)==len(set(ids)), 'Duplicate SVG IDs'
        assert root.get('data-text-outlined')=='true', 'Text has not been outlined'
        assert not root.findall('.//s:text',NS), 'Portable SVG still depends on installed fonts'
        assert not root.findall('.//s:image',NS), 'Embedded bitmap'
        assert len([e for e in root.iter() if e.get('data-source')])==5
        labels=[e.get('data-label') for e in root.iter() if e.get('data-label')]
        assert not any('固定同一方案' in t for t in labels)
        assert any('迁移 B' in t for t in labels)
        label_sets.append(labels)
        for x,y in [('430','1084'),('1677','741'),('2572','453')]:
            rect=root.find(f'.//s:rect[@x="{x}"][@y="{y}"]',NS)
            assert rect is not None and rect.get('class')=='paper', 'B remains highlighted'
        for ident,tex in [('partition-expression',r'\mathcal{P}=\{A,B,C,D\}'),
                          ('graph-definition',r'G=(T\cup O,E)'),('text-104','k_1'),('text-113','k_2'),
                          ('makespan-v3',r'C_q(y)=\max_j f_j')]:
            node=root.find(f'.//*[@id="{ident}"]')
            assert node is not None and node.get('data-tex')==tex, ident
            assert node.get('data-math-fonts')=='Computer Modern'
        assert ',380.000000)' in root.find('.//*[@id="graph-definition"]').get('transform')
        for ident in ['text-104','text-113']:
            assert ',424.000000)' in root.find(f'.//*[@id="{ident}"]').get('transform')
        for ident,label in [('text-122','COPY_OUT'),('text-123','COPY_IN')]:
            node=root.find(f'.//*[@id="{ident}"]')
            assert node.get('data-label')==label and node.get('data-anchor')=='middle'
        assert gzip.decompress(svg.with_suffix('.svgz').read_bytes())==svg.read_bytes()
        editable=svg.with_name(svg.stem+'_editable.svg')
        edit=ET.parse(editable).getroot()
        assert edit.findall('.//s:text',NS), 'Editable source missing'
        assert Image.open(root_dir/'exports'/f'{svg.stem}.png').size==(6000,3650)
        assert Image.open(root_dir/'exports'/f'{svg.stem}_preview.png').size==(1800,1095)
        pdf=root_dir/'exports'/f'{svg.stem}.pdf'
        assert pdf.read_bytes().startswith(b'%PDF-')
        fonts=subprocess.check_output(['pdffonts',str(pdf)],text=True).splitlines()
        assert len([line for line in fonts[2:] if line.strip()])==0, 'PDF still carries fonts'
        checks.append({'palette':name,'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),
                       'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                       'semantic_label_count':len(labels),'global_links':5,'font_independent':True,
                       'png_pixels':[6000,3650],'uniform_b_blocks':True,'bottom_q3_note_removed':True,
                       'math_font':'Computer Modern','editable_source_kept':True})
    assert label_sets[0]==label_sets[1], 'Palettes have different content'
    for p in root_dir.rglob('*'):
        assert p.suffix.lower() not in {'.ttf','.otf','.ttc','.woff','.woff2','.pfb'}, 'Font file in deliverable'
        if p.suffix in {'.py','.md','.svg','.yml'}:
            assert not re.search(r'(?m)^(?:<{7}|={7}|>{7})(?: |$)',p.read_text(encoding='utf-8')), 'Conflict marker'
    receipt={'checks':checks,'new_solver_experiments':0,
             'scope':'Figure typography, vector layout and deterministic exports only',
             'visual_review':'Exported SVG and PDF previews require separate visual inspection'}
    (root_dir/'docs').mkdir(exist_ok=True)
    (root_dir/'docs'/'EXPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt

if __name__=='__main__':
    validate()
