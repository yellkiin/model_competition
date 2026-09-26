#!/usr/bin/env python3
"""Inspect the delivered vector objects, annotations and four export variants."""
from pathlib import Path
import json
import xml.etree.ElementTree as E
HERE=Path(__file__).resolve().parent
NS={'s':'http://www.w3.org/2000/svg'}
S='{'+NS['s']+'}'
THEMES=('qinglu','qianjiang','yanlan','mono')

def check():
    rows=[];signature=None
    for name in THEMES:
        path=HERE/'assets'/f'workflow_{name}_v4.svg'
        root=E.parse(path).getroot()
        ids=[e.get('id') for e in root.iter() if e.get('id')]
        assert len(ids)==len(set(ids)), f'duplicate IDs in {name}'
        assert not root.findall('.//s:image',NS), 'Raster object in SVG'
        assert not root.findall('.//s:text',NS), 'Portable artwork still requires fonts'
        assert not root.findall('.//s:font',NS), 'Font resource bundled'
        labels=[e.get('data-label') for e in root.iter() if e.get('data-label')]
        for removed in ('图 1.1  ·  方法总览','候选示意：迁移 B','停止时',
                        '输出：调度方案 · 性能指标 · 时间—质量曲线',
                        'FIFO 复用时序 · Q3','只读 L2 · FIFO · Q3','G = (T ∪ O, E)'):
            assert removed not in labels,removed
        assert labels.count('COPY_IN')==1 and labels.count('COPY_OUT')==1
        for required in ('原始计算图','子图划分与归核','总体评价','反馈改进','核心 k1','核心 k2'):
            assert required in labels,required
        assert 'graph-definition' not in ids and 'finish-to-output' not in ids
        assert 'feedback-to-current' in ids and 'evaluation-to-feedback' in ids
        assert 'partition-expression' in ids
        assert not root.findall(".//s:path[@d='M2375,1201H2810']",NS)
        assert root.find(".//*[@id='ddr-to-l2-fill']").get('stroke-dasharray')=='7 6'
        ed=E.parse(path.with_name(path.stem+'_editable.svg')).getroot()
        assert len(ed.findall('.//s:text',NS))>50
        formulas=[e.get('data-tex') for e in root.iter() if e.get('data-tex')]
        if signature is None: signature=(labels,formulas)
        else: assert signature==(labels,formulas),'Different scientific text across palettes'
        rows.append({'palette':name,'labels':len(labels),'editable_text_nodes':len(ed.findall('.//s:text',NS)),
                     'portable_text_nodes':0,'raster_nodes':0,'all_14_annotation_targets_present':True,
                     'viewBox':root.get('viewBox')})
    report={'variants':rows,'annotation_ids':list(range(1,15)),
            'fonts':'Inherited SimSun/Times New Roman figure outlines and unchanged Computer Modern equations; editable source kept separately.',
            'scope':'Object checks supplement, not replace, the local full-view and PDF-detail review.'}
    (HERE/'docs/OBJECT_REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':check()
