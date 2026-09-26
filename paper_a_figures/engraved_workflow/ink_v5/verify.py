#!/usr/bin/env python3
"""Object, four-palette, unchanged-source and exported-PDF checks for ink_v5."""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
from build import (HERE, NS, TAG, THEMES, SOURCE_HASHES, CENTER_X, COPY_CENTERS,
                   COPY_BASELINE, CUBE_CENTER_Y, CUBE_SCALE, MIGRATION_X,
                   CANDIDATE_LABEL, SELECTION_LABEL, find, git_hash)


def canonical(node):
    """Ignore palette pigments, not vector geometry, scientific text or IDs."""
    node = deepcopy(node)
    for e in node.iter():
        e.attrib.pop('data-palette', None)
        for k,v in list(e.attrib.items()):
            e.set(k, re.sub(r'#[0-9a-fA-F]{6}', '#COLOR', v).replace('-v4','-v5').replace('v4-','v5-'))
        if e.tag == TAG('style') and e.text:
            e.text = re.sub(r'#[0-9a-fA-F]{6}', '#COLOR', e.text)
    return ET.tostring(node)


def png_size(path):
    raw=path.read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n', path
    return struct.unpack('>II', raw[16:24])


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=90).stdout


def render_details():
    pdf=HERE/'exports/workflow_qinglu_v5.pdf'
    width=4800
    regions={'01_centered_connectors':(90,870,940,1110),
             '02_copy_pairs':(2090,887,2850,1056),
             '03_candidate_selection':(1510,587,1970,923)}
    for name,(x0,y0,x1,y1) in regions.items():
        scale=width/3000
        args=['pdftoppm','-singlefile','-png','-scale-to-x',str(width),'-scale-to-y','-1',
              '-x',str(round(x0*scale)),'-y',str(round((y0-235)*scale)),
              '-W',str(round((x1-x0)*scale)),'-H',str(round((y1-y0)*scale)),
              str(pdf),str(HERE/'docs'/name)]
        command(*args)


def check(renders=False):
    signatures={}; rows=[]
    for name in THEMES:
        for tail,expected in zip(('', '_editable'),SOURCE_HASHES[name]):
            source=HERE.parent/'ink_v4/assets'/f'workflow_{name}_v4{tail}.svg'
            assert git_hash(source)==expected, 'v4 was changed'
        path=HERE/'assets'/f'workflow_{name}_v5.svg'
        root=ET.parse(path).getroot()
        ed=ET.parse(path.with_name(path.stem+'_editable.svg')).getroot()
        for node,kind in ((root,'portable'),(ed,'editable')):
            ids=[e.get('id') for e in node.iter() if e.get('id')]
            assert len(ids)==len(set(ids)), 'Duplicate IDs'
            assert not node.findall('.//s:image',NS), 'Raster image in SVG'
            assert not node.findall('.//s:font',NS), 'Embedded font resource'
            assert node.get('data-version')=='ink_v5'
            assert node.get('viewBox')=='0 235 3000 1430'
            assert find(node,'graph-to-partition').get('d')==f'M{CENTER_X},911 V933'
            assert find(node,'partition-to-cores').get('d')==f'M{CENTER_X},1033 V1066'
            card=find(node,'partition-map-card')
            assert float(card.get('x'))+float(card.get('width'))/2==CENTER_X
            for direction in ('out','in'):
                label=find(node,f'copy-{direction}-label')
                cube=find(node,f'copy-{direction}-tensor-v5')
                nums=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',cube.get('transform'))))
                tx,ty,scale=nums
                assert scale==CUBE_SCALE
                assert abs(tx+scale-COPY_CENTERS[direction])<1e-7
                assert abs(ty-3.5*scale-CUBE_CENTER_Y)<1e-7
                assert label.get('transform').startswith(f'translate({COPY_CENTERS[direction]},{COPY_BASELINE})')
                assert cube.get('data-transfer-path')==label.get('data-transfer-path')==f'left-copy-{direction}'
            migration=find(node,'b-migration-v5')
            assert migration.get('d')==f'M{MIGRATION_X},691 V719'
            assert migration.get('style')=='stroke-linecap:butt;stroke-linejoin:miter'
            head=find(node,'migration-arrowhead-v5')
            assert head.get('refX')=='1'
            assert head.find('s:path',NS).get('d')=='M1,1 L9,5 L1,9 Z'
            pieces=node.findall(".//*[@data-part='migration-target-B']")
            assert len(pieces)==4 and all(e.get('transform').startswith('translate(33,0)') for e in pieces)
            assert find(node,'source-structure').get('data-solution-status')=='illustrative-candidates-not-proven-optimal'
            assert find(node,'candidate-migration-label') is not None
            assert find(node,'evaluated-selection-label') is not None
            for ident in ('feedback-to-current','evaluation-to-feedback','current-to-candidate',
                          'candidate-to-evaluation','partition-expression'):
                assert find(node,ident) is not None
            sig=hashlib.sha256(canonical(node)).hexdigest()
            if kind not in signatures: signatures[kind]=sig
            assert signatures[kind]==sig, f'Non-color differences across {kind} palettes'
        assert not root.findall('.//s:text',NS), 'Portable SVG still depends on font files'
        labels=[e.get('data-label') for e in root.iter() if e.get('data-label')]
        assert labels.count('COPY_IN')==1 and labels.count('COPY_OUT')==1
        assert CANDIDATE_LABEL in labels and SELECTION_LABEL in labels
        assert len(ed.findall('.//s:text',NS))==84
        old=ET.parse(HERE.parent/'ink_v4/assets'/f'workflow_{name}_v4.svg').getroot()
        old_math=[canonical(n) for n in old.iter() if n.get('data-tex')]
        new_math=[canonical(n) for n in root.iter() if n.get('data-tex')]
        assert old_math==new_math, 'Inherited mathematics changed'
        assert gzip.decompress(path.with_suffix('.svgz').read_bytes())==path.read_bytes()
        base=HERE/'exports'/path.stem
        assert png_size(base.with_suffix('.png'))==(6000,2860)
        assert png_size(base.with_name(base.name+'_preview.png'))==(1800,858)
        pdf=base.with_suffix('.pdf')
        info=command('pdfinfo',str(pdf))
        assert re.search(r'^Pages:\s+1$', info,re.M), 'PDF is not single-page'
        fonts=command('pdffonts',str(pdf)).strip().splitlines()
        images=command('pdfimages','-list',str(pdf)).strip().splitlines()
        assert len(fonts)==2 and len(images)==2, 'PDF contains font resources or raster artwork'
        rows.append({'palette':name,'labels':len(labels),'editable_text_nodes':84,
                     'portable_text_nodes':0,'unchanged_math_groups':len(new_math),
                     'pdf_pages':1,'pdf_fonts':0,'pdf_images':0,
                     'png':[6000,2860],'preview':[1800,858],
                     'source_svg_hashes_verified':True,'all_four_requested_items_checked':True})
    docs=HERE/'docs';docs.mkdir(exist_ok=True)
    if renders: render_details()
    report={'version':'ink_v5','variants':rows,'color_independent_geometry_sha256':signatures,
            'optimality_status':'Candidate illustration; no global-optimality assertion or new experiment.',
            'checks':'SVG object checks and PDF resource inspection; visual review recorded separately.'}
    (docs/'OBJECT_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--renders',action='store_true')
    args=ap.parse_args()
    check(args.renders)
