"""Bind the draft abstract to current result-derived facts; audit remains separate."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'求解/正式实验/摘要事实.json'
facts=json.loads(source.read_text(encoding='utf-8'))
sha=hashlib.sha256(source.read_bytes()).hexdigest()
path='求解/正式实验/摘要事实.json'
questions=[]
for q in ('q1','q2','q3'):
    row=facts['questions'][q]
    statements=[]
    for kind,key in (('method','method'),('conclusion','conclusion'),('value','speedup'),('validation','validation')):
        item={'kind':kind,'text':row[key]['text'] if kind=='conclusion' else
              f"{row[key]['value']:.4f}{row[key]['unit']}" if kind=='value' else row[key],
              'source_path':path,'source_sha256':sha,'source_pointer':f'/questions/{q}/{key}'}
        if kind=='value': item['decimal_places']=4
        statements.append(item)
    if q=='q3':
        value=row['cache_gain']
        statements.append({'kind':'value','text':f"{value['value']:.4f}{value['unit']}",
                           'source_path':path,'source_sha256':sha,'source_pointer':'/questions/q3/cache_gain',
                           'decimal_places':4})
    questions.append({'chapter_id':q,'statements':statements})
out=ROOT/'论文/摘要证据.json'
out.write_text(json.dumps({'schema_version':'1.0','questions':questions},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(out)
