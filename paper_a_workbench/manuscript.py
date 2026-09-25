"""Mechanical academic-edit checks. Semantic proof/citation review stays explicit."""
from __future__ import annotations
import re
from collections import Counter
from pathlib import Path
from common import read

DEFENSIVE=('不声称','不冒充','不能据此','仅供参考','无法保证','不应据此')
HISTORY=('上一版','旧pilot','旧 pilot','PR #','草稿R2','草稿 R2','workshop_v')
IMPLEMENTATION=('node_to_subgraph','core_schedules','candidate_lower','stop_gap','plan_hash','publish_results.ps1')
PROTECTED=('下界','上界','算术平均','几何平均','中位数','同一方案','字节命中率','至少','至多','全部用例')


def strip_comments(text):
    return re.sub(r'(?<!\\)%[^\n]*','',text)


def visible(text):
    text=strip_comments(text)
    text=re.sub(r'\\begin\{(lstlisting|verbatim|minted)\}.*?\\end\{\1\}','',text,flags=re.S)
    text=re.sub(r'\\(?:cite\w*|ref|eqref|label)\*?(?:\[[^]]*\])*\{[^}]*\}','',text)
    return text


def locks(text):
    clean=strip_comments(text)
    math=re.findall(r'\$\$.*?\$\$|(?<!\\)\$[^$]*\$|\\\[.*?\\\]|\\\(.*?\\\)',clean,re.S)
    math += re.findall(r'\\begin\{(?:equation\*?|align\*?|gather\*?)\}.*?\\end\{(?:equation\*?|align\*?|gather\*?)\}',clean,re.S)
    citations=re.findall(r'\\(?:cite\w*|ref|eqref|label)\*?(?:\[[^]]*\])*\{[^}]*\}',clean)
    numbers=re.findall(r'(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?(?:\\?%)?',clean)
    return {'math':Counter(re.sub(r'\s+','',s) for s in math),'citations':Counter(citations),
            'numbers':Counter(n.replace('\\%','%') for n in numbers),
            'qualifiers':Counter({x:clean.count(x) for x in PROTECTED if x in clean})}


def compare(before,after):
    a,b=locks(before),locks(after);changed={}
    for k in a:
        if a[k]!=b[k]:changed[k]={'removed':dict(a[k]-b[k]),'added':dict(b[k]-a[k])}
    return {'protected_elements_equal':not changed,'changed':changed,
            'next':'Review logical relations and units in context; equality checks preserve tokens, not the entire meaning.'}


def lint(files, glossary_path):
    glossary=read(glossary_path);findings=[];joined='';offsets=[]
    for file in files:
        p=Path(file);text=visible(p.read_text(encoding='utf-8-sig'))
        offsets.append((len(joined),str(p)));joined+=text+'\n'
        for i,line in enumerate(text.splitlines(),1):
            for category,terms in [('defensive',DEFENSIVE),('development_history',HISTORY),('implementation_identifier',IMPLEMENTATION)]:
                for term in terms:
                    if term in line:findings.append({'file':str(p),'line':i,'kind':category,'text':term})
            if '显著' in line:findings.append({'file':str(p),'line':i,'kind':'evidence_review','text':'显著：核对是否为量化描述或有检验依据，不自动替换成更强结论'})
    for entry in glossary['terms']:
        canonical=entry['term']
        for alias in entry.get('avoid_aliases',[]):
            if alias in joined:findings.append({'kind':'terminology','text':alias,'canonical':canonical})
        if canonical in joined and entry.get('definition_pattern'):
            first=joined.index(canonical);match=re.search(entry['definition_pattern'],joined)
            if not match or match.start()>first:
                findings.append({'kind':'definition_order','text':canonical,'instruction':'在首次使用处定义，并核对后文实际复用'})
    return {'findings':findings,'mechanical_clear':not findings,
            'scope':'Only the explicitly ordered manuscript body files; appendices/logs are not silently treated as prose.'}
