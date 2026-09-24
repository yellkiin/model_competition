"""Isolated citation rendering using independently retrieved publisher metadata.

This builds a typography fixture, not a scientific contest paper. It does not
turn a successful compilation or ten source entries into final acceptance.
"""
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
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '华为杯_求解规范/tools'))

from audit_pdf_layout import audit_layout
from audit_citations import audit_pdf as audit_citation_pdf
from collect_academic_paper_review import compile_evidence, verify_evidence
from run_layout_smoke import create_fixture
from reference_evidence import sha
from ai_disclosure import AI_KEY, disclosure_record


REFERENCES = [
    ('guyon03a', '特征选择研究将预测效果、计算成本和对数据生成过程的理解列为选择变量的动机'),
    ('pedregosa11a', 'Scikit-learn提供统一接口的监督与无监督学习实现，可用作实验的软件工具'),
    ('bergstra12a', '随机搜索文献为超参数优化提供了与网格搜索比较的基线方法'),
    ('cawley10a', '模型选择准则本身可能过拟合，从而使性能估计产生选择偏差'),
    ('guyon10a', '模型选择综述比较了简约原则在贝叶斯、最小描述长度和正则化等理论中的作用'),
    ('cawley07a', '超参数的贝叶斯正则化把惩罚引入模型选择层，以控制该层的过拟合'),
    ('vandermaaten08a', 't-SNE将高维样本映射到低维空间，用于观察数据结构'),
    ('srivastava14a', 'Dropout在训练时随机移除网络单元及其连接，以减少共同适应'),
    ('duchi11a', '自适应次梯度方法根据先前迭代信息调整更新的几何尺度'),
    ('vincent10a', '堆叠去噪自编码器通过逐层学习恢复受扰动输入来构造表示'),
]


def build(root: Path, sources: Path, variant: str) -> tuple[Path, list[str]]:
    main = create_fixture(root, 1)
    entries = []
    keys = []
    sentences = []
    for stem, meaning in REFERENCES:
        raw = (sources/(stem+'.bib')).read_text(encoding='utf-8-sig')
        match = re.search(r'@article\s*\{\s*([^,\s]+)', raw)
        if not match:
            raise ValueError('Missing primary bibliography entry: '+stem)
        key = match[1]
        keys.append(key)
        entries.append(raw)
        sentences.append(meaning + '\\cite{'+key+'}。\n\n')
    (root/'reference.bib').write_text('\n'.join(entries), encoding='utf-8')
    text = '\n本节为文献排版演练，以下为相关方法的简要文献说明，不报告赛题实验结果。\n\n'
    text += ''.join(sentences if variant != 'nine_cited' else sentences[:-1])
    if variant != 'nine_cited':
        text += ('连续引用排版测试\\cite{'+','.join(keys[:3])+'}，逗号位于引文之后。\n\n'
                 '非连续多篇引用测试\\cite{'+keys[0]+','+keys[3]+','+keys[-1]+'}；分号邻接测试。\n\n'
                 '全范围引用测试\\cite{'+','.join(keys)+'}。\n')
    chapter = root/'c4.tex'
    content = chapter.read_text(encoding='utf-8').replace(
        r'文献引用字形测试\cite{knuth}。', text)
    chapter.write_text(content, encoding='utf-8')
    ref = root/'c6.tex'
    if variant == 'nine_cited':
        ref.write_text(r'\nocite{*}'+'\n'+ref.read_text(encoding='utf-8'), encoding='utf-8')
    elif variant == 'baseline_citations':
        main.write_text(main.read_text(encoding='utf-8').replace(r'\begin{document}',
            r'\setcitestyle{numbers,square}'+'\n'+r'\begin{document}'), encoding='utf-8')
    elif variant != 'valid':
        raise ValueError(variant)
    return main, keys


def install_reviewed_sources(root: Path, reviews_path: Path):
    """Reuse explicitly authored reviews only for this exact fixture prose.

    This is a DEMO helper, not an initializer for a real paper or an automatic
    source reviewer. Acquisition drafts remain unchanged and unreviewed.
    """
    from audit_citations import audit_citation_keys
    reviews = json.loads(reviews_path.read_text(encoding='utf-8-sig'))
    if not reviews['reviewed'] or not reviews['tool_ref'].strip():
        raise ValueError('缺少已实际进行的来源审阅')
    snapshots = reviews_path.parent
    acquired = {r['key']:r for r in json.loads((snapshots/'results.json').read_text(encoding='utf-8'))}
    citation = audit_citation_keys(root/'论文输入.json')
    raw_bib = (root/'reference.bib').read_text(encoding='utf-8')
    records = []
    for review in reviews['references']:
        stem = review['stem']
        matching = [k for k in citation['keys'] if k.endswith(':'+stem)]
        if not matching: continue
        key = matching[0]
        if key not in raw_bib: raise ValueError('实引键未在当前演练书目中')
        src = acquired[stem]['source_draft'].copy()
        target = root/'参考来源'/stem
        target.mkdir(parents=True,exist_ok=True)
        for field in ('capture_path','receipt_path'):
            original = snapshots/src[field]
            copied = target/original.name
            shutil.copyfile(original,copied)
            src[field] = copied.relative_to(root).as_posix()
        src['authority'] = 'publisher'
        src['authority_reason'] = 'JMLR期刊官方论文页面直接列出作者、题名、卷期页码和摘要，作为本篇文章的出版来源。'
        src['review'] = {'reviewed':True,'tool_ref':reviews['tool_ref'],'observation':review['observation']}
        meaning = dict(REFERENCES)[stem]
        excerpt = meaning+'\\cite{'+key+'}。'
        chapters = sorted({c['chapter_id'] for c in citation['calls'] if key in c['keys']})
        records.append({'key':key,'reference_type':'ordinary','sources':[src],'usages':[{'chapter_id':chapter,'body_excerpt':excerpt,
            'source_excerpt':review['source_excerpt'],'relevance':review['relevance'],
            'reviewed':True,'tool_ref':reviews['tool_ref']} for chapter in chapters]})
    records.append(disclosure_record(AI_KEY))
    evidence = {'schema_version':'1.1','bibliography_files':[{'path':'reference.bib','sha256':sha(root/'reference.bib')}],
                'references':records}
    (root/'文献证据.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    path = root/'论文输入.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest['references_evidence_path']='文献证据.json'
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


def run(output: Path, sources: Path, variant: str, xelatex: str, source_reviews: Path) -> dict:
    import pymupdf as fitz
    main, keys = build(output, sources, variant)
    install_reviewed_sources(output, source_reviews)
    review = compile_evidence(output, main, output/'review.json', 'codex', [], xelatex)
    failures = verify_evidence(output, review, main, 'codex', [], require_visual=False)
    layout = audit_layout(main.with_suffix('.pdf'), main, output/'论文输入.json')
    citation_gate = audit_citation_pdf(main.with_suffix('.pdf'), main, output/'论文输入.json')
    pages = []
    with fitz.open(main.with_suffix('.pdf')) as doc:
        for i, page in enumerate(doc):
            text = page.get_text()
            if '本节为文献排版演练' in text or '连续引用排版测试' in text or text.startswith('6 参考文献'):
                path = output/f'citation-page-{i+1:03d}.png'
                page.get_pixmap(matrix=fitz.Matrix(1.5,1.5), alpha=False).save(path)
                pages.append(str(path))
    result = {'variant': variant, 'evidence_failures': failures, 'layout': layout,
              'citation_gate': citation_gate,
              'expected_behavior_pass': not failures and (citation_gate['status']=='PASS') == (variant=='valid'),
              'reference_keys': keys, 'page_previews': pages,
              'scope': 'Actual citation typography probe only. Source metadata is external primary evidence; '
                       'ten-entry count alone does not certify actual body citation or full-paper acceptance.'}
    (output/'citation-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--sources', type=Path, required=True)
    ap.add_argument('--source-reviews', type=Path, required=True)
    ap.add_argument('--variant', choices=['valid', 'nine_cited', 'baseline_citations'], default='valid')
    ap.add_argument('--xelatex', required=True)
    args = ap.parse_args()
    result = run(args.output.resolve(), args.sources.resolve(), args.variant, args.xelatex, args.source_reviews.resolve())
    print(json.dumps({'evidence_failures': result['evidence_failures'],
                      'layout_failures': result['layout']['failures'],
                      'citation_failures': result['citation_gate']['failures'],
                      'expected_behavior_pass': result['expected_behavior_pass'],
                      'page_previews': result['page_previews']}, ensure_ascii=False))
    raise SystemExit(not result['expected_behavior_pass'])
