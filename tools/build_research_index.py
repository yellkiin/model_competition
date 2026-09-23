"""Validate per-problem reference records and build a Markdown/BibTeX index."""
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '调研'
REQUIRED = {'id','title','authors','year','venue','url','doi','type','relevance','verified_date','verification'}

def escape_bib(value):
    return str(value).replace('\\', r'\textbackslash{}').replace('{', r'\{').replace('}', r'\}').replace('&', r'\&').replace('%', r'\%').replace('_', r'\_').replace('#', r'\#')

def bib_authors(value):
    names=[n.strip() for n in value.split(';') if n.strip()]
    return ' and '.join('others' if n.lower() in {'et al.','et al','等'} else n for n in names)

def main():
    all_refs=[]
    for letter in 'ABCDEF':
        path=OUT/f'{letter}题_文献.json'
        refs=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(refs,list) or len(refs)<15:
            raise ValueError(f'Expected at least 15 references for {letter}')
        for ref in refs:
            if not REQUIRED.issubset(ref):
                raise ValueError((path,REQUIRED-set(ref)))
            if not re.fullmatch(letter+r'\d{2,3}',ref['id']):
                raise ValueError(('Reference ID',ref['id']))
            if not ref['url'].startswith('https://'):
                raise ValueError(('Stable HTTPS URL required',ref['id']))
            if not isinstance(ref['year'],int) or not 1900<=ref['year']<=2026:
                raise ValueError(('Year',ref['id'],ref['year']))
        all_refs.extend(refs)
    if len({r['id'] for r in all_refs})!=len(all_refs):
        raise ValueError('Duplicate reference IDs')
    keys=[(r['doi'].lower().removeprefix('https://doi.org/') if r['doi'] else r['url'].rstrip('/')) for r in all_refs]
    counts=Counter(r['id'][0] for r in all_refs)
    lines=['# 文献总索引','',f'核验日期：2026-09-23。共 {len(all_refs)} 个按题目编排的引用条目，按 DOI 或 URL 去重为 {len(set(keys))} 项；同一文献可服务不同题目。','',
           '核验层级记录在各题 JSON 的 `verification` 字段。查到论文页面或摘要只能确认书目信息和摘要层面的适用性，不代表已完成全文复核。论文与官方技术文档分开标注，工具文档不替代方法的论文依据。','',
           '| 题目 | 条目数 | 报告 |','|---|---:|---|']
    for letter in 'ABCDEF':
        lines.append(f'| {letter} | {counts[letter]} | [{letter}题基础调研与写作方向]({letter}题_基础调研与写作方向.md) |')
    bib=[]
    for letter in 'ABCDEF':
        lines += ['',f'## {letter}题','']
        for ref in [r for r in all_refs if r['id'].startswith(letter)]:
            lines += [f"### {ref['id']} {ref['title']}",'',f"{ref['authors']}（{ref['year']}）。{ref['venue']}。类型：{ref['type']}。",'',
                      f"用途：{ref['relevance']}",'',f"来源：[{ref['title']}]({ref['url']})；核验层级：{ref['verification']}。",'']
            if ref['doi']: lines += [f"DOI：`{ref['doi']}`",'']
            fields={'title':ref['title'],'author':bib_authors(ref['authors']),'year':ref['year'],'howpublished':ref['venue'],'note':f"{ref['type']}; verified {ref['verified_date']}; {ref['verification']}"}
            body=[f'@misc{{{ref["id"]},']
            body += [f'  {k} = {{{escape_bib(v)}}},' for k,v in fields.items()]
            body.append(f'  url = {{{ref["url"]}}},')
            if ref['doi']: body.append(f'  doi = {{{ref["doi"]}}},')
            body.append('}')
            bib.append('\n'.join(body))
    (OUT/'文献总索引.md').write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')
    (OUT/'references.bib').write_text('% Bibliographic starting points; verify full author lists and publication metadata before final submission.\n\n'+'\n\n'.join(bib)+'\n',encoding='utf-8')
    print(json.dumps({'references':len(all_refs),'unique_doi_or_url':len(set(keys)),'by_problem':dict(counts)},ensure_ascii=False))

if __name__=='__main__':
    main()
