#!/usr/bin/env python3
"""Check source preservation, operations, palettes, IDs and vector-only exports."""
from copy import deepcopy
import gzip, hashlib, json, re, struct, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from build import HERE,NS,TAG,THEMES,SOURCE_HASHES,find,git_hash


def canonical(node,strip_transform=False):
    node=deepcopy(node)
    if strip_transform:node.attrib.pop('transform',None)
    for e in node.iter():
        e.attrib.pop('data-palette',None)
        for k,v in list(e.attrib.items()):
            v=re.sub(r'#[0-9a-fA-F]{6}','#COLOR',v)
            v=re.sub(r'v6-tip-[0-9a-fA-F]{6}','v6-tip-COLOR',v)
            e.set(k,v.replace('-v5','-v6').replace('v5-','v6-'))
        if e.tag==TAG('style') and e.text:e.text=re.sub(r'#[0-9a-fA-F]{6}','#COLOR',e.text)
    return ET.tostring(node)


def pngsize(p):
    b=p.read_bytes();assert b[:8]==b'\x89PNG\r\n\x1a\n';return struct.unpack('>II',b[16:24])


def main():
    sigs={};rows=[]
    for name in THEMES:
        pair=[]
        for i,tail in enumerate(('', '_editable')):
            oldpath=HERE.parent/'ink_v5/assets'/f'workflow_{name}_v5{tail}.svg'
            assert git_hash(oldpath)==SOURCE_HASHES[name][i], 'Published v5 changed'
            old=ET.parse(oldpath).getroot()
            p=HERE/'assets'/f'workflow_{name}_v6{tail}.svg';r=ET.parse(p).getroot();pair.append(r)
            assert r.get('viewBox')=='0 235 3500 1550'
            ids=[n.get('id') for n in r.iter() if n.get('id')]
            assert len(ids)==len(set(ids)), 'Duplicate SVG IDs'
            assert not r.findall('.//s:image',NS) and not r.findall('.//s:font',NS)
            for node in r.iter():
                for v in node.attrib.values():
                    for target in re.findall(r'url\(#([^\)]+)\)',v):assert target in ids, 'Broken SVG reference: '+target
            for letter in 'abcdef':find(r,'source-'+letter)
            assert find(r,'b-before-state').get('data-k1')=='AD'
            assert find(r,'b-before-state').get('data-k2')=='BC'
            assert find(r,'b-after-state').get('data-k1')=='ABD'
            assert find(r,'b-after-state').get('data-k2')=='C'
            assert find(r,'c-before-state').get('data-k1')=='ACD'
            assert find(r,'c-before-state').get('data-k2')=='B'
            assert find(r,'c-after-state').get('data-k1')=='ABD'
            assert find(r,'c-after-state').get('data-k2')=='C'
            assert find(r,'source-d').get('data-partition')=='B1={o2};B2={o4};B1->B2'
            assert find(r,'b-before-state-B-k2-to-k1').get('d')=='M1741,663V648'
            assert find(r,'split-preserved-dependency') is not None
            for x in ('section-01-to-02','section-02-to-03','pool-to-complete-candidate',
                      'current-to-candidate','candidate-to-evaluation','evaluation-to-feedback','feedback-to-current'):find(r,x)
            for x in ('bipartite-example','partition-expression'):
                assert canonical(find(old,x))==canonical(find(r,x)), 'Original graph or partition formula changed'
            assert canonical(find(old,'execution-v5'),True)==canonical(find(r,'execution-v6'),True), '03 artwork changed beyond whole-panel translation'
            for kind in ['out','in']:
                assert canonical(find(old,'copy-'+kind+'-label'))==canonical(find(r,'copy-'+kind+'-label'))
                assert canonical(find(old,'copy-'+kind+'-tensor-v5'))==canonical(find(r,'copy-'+kind+'-tensor-v6'))
            labels=[n.get('data-label') for n in r.iter() if n.get('data-label')]
            if i==0:
                assert not r.findall('.//s:text',NS), 'Portable SVG depends on installed fonts'
                assert labels.count('COPY_IN')==labels.count('COPY_OUT')==1
                assert '子图切分与归核' in labels and '当前最优方案' in labels
                assert not any(re.search(r'问题[一二三]|Q[123]',t) for t in labels), 'Question coverage belongs only in prose'
                assert gzip.decompress(p.with_suffix('.svgz').read_bytes())==p.read_bytes()
            sig=hashlib.sha256(canonical(r)).hexdigest()
            if i not in sigs:sigs[i]=sig
            assert sigs[i]==sig, 'Non-color differences among themes'
        base=HERE/'exports'/f'workflow_{name}_v6'
        assert pngsize(base.with_suffix('.png'))==(6000,2657)
        assert pngsize(base.with_name(base.name+'_preview.png'))==(2100,930)
        pdf=base.with_suffix('.pdf')
        def cmd(*a):return subprocess.check_output(a,text=True,timeout=60)
        assert re.search(r'^Pages:\s+1$',cmd('pdfinfo',str(pdf)),re.M)
        assert len(cmd('pdffonts',str(pdf)).strip().splitlines())==2
        assert len(cmd('pdfimages','-list',str(pdf)).strip().splitlines())==2
        rows.append({'palette':name,'svg_pair_source_verified':True,'portable_text_nodes':0,
                     'editable_text_nodes':len(pair[1].findall('.//s:text',NS)),
                     'six_operation_checks':'PASS','inherited_01_graph_and_03_artwork':'PASS',
                     'pdf_pages':1,'pdf_fonts':0,'pdf_images':0,'png':[6000,2657],'preview':[2100,930]})
    report={'version':'ink_v6','variants':rows,'geometry_sha256':sigs,
            'scope':'Only ink_v6; no solver experiments, numerical results or existing paper files changed.',
            'best_semantics':'Best feasible among evaluated candidates; no global optimality certificate.',
            'coverage_in_prose':{'Q1':'abcd','Q2':'abcde','Q3':'abcdef'}}
    (HERE/'docs').mkdir(exist_ok=True)
    (HERE/'docs/OBJECT_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
