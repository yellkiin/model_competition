from pathlib import Path
import fitz, json, re, csv
from PIL import Image,ImageDraw

R=Path(__file__).resolve().parent
W=R.parents[1];P=W/'论文'
pdf=P/'论文_PR52复审版_20260926.pdf'
d=fitz.open(pdf);names=d.resolve_names()
out=R/'页面复核';out.mkdir(exist_ok=True)
pages=[]
for i,p in enumerate(d):
    target=out/f'p{i+1:03}.png'
    p.get_pixmap(matrix=fitz.Matrix(100/72,100/72),alpha=False).save(target)
    pages.append({'page':i+1,'path':str(target),'text':p.get_text()})
for start in range(0,len(d),6):
    sheet=Image.new('RGB',(1260,1236),'#eeeeee');draw=ImageDraw.Draw(sheet)
    for k in range(min(6,len(d)-start)):
        im=Image.open(pages[start+k]['path']);im.thumbnail((410,590))
        x=(k%3)*420;y=(k//3)*618
        sheet.paste(im,(x+5,y+20));draw.text((x+8,y+4),str(start+k+1),fill='black')
    sheet.save(out/f'contact_{start+1:03}_{min(start+6,len(d)):03}.png')
(out/'PAGE_INDEX.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
aux=(P/'论文.aux').read_text(encoding='utf-8')
labels=re.findall(r'\\newlabel\{([^}]+)\}\{\{([^}]+)\}\{(\d+)\}.*?\}\{([^{}]+)\}\{\}\}',aux)
allkeys=[x[0] for x in labels]
badlabels=[x[0] for x in labels if x[3] not in names or names[x[3]].get('page')!=int(x[2])-1]
links=[l for p in d for l in p.get_links() if l['kind'] in (fitz.LINK_GOTO,fitz.LINK_NAMED)]
badlinks=[l.get('nameddest') for l in links if not 0<=l.get('page',-1)<len(d)]
sources=[P/'论文.tex',P/'摘要.tex',*(P/'章节内容').rglob('*.tex'),*(P/'综合图片段').glob('*.tex')]
text='\n'.join(p.read_text(encoding='utf-8-sig') for p in sources)
refs=set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}',text))
cite={x.strip() for g in re.findall(r'\\cite(?:\[[^]]*\])?\{([^}]+)\}',text) for x in g.split(',')}
bib=set(re.findall(r'\\bibcite\{([^}]+)\}',aux))
log=(P/'compile.log').read_text(encoding='utf-8',errors='replace')
refpage=next(p['page'] for p in pages if re.search(r'8\s+参考文献',p['text']) and '[1]' in p['text'])
apppage=next(p['page'] for p in pages if p['page']>refpage and re.search(r'9\s+附录',p['text']))
result=dict(pdf=str(pdf),pages=len(d),body_pages=[4,refpage-1],references_page=refpage,appendix_pages=[apppage,len(d)],
    labels=len(labels),internal_links=len(links),missing_references=sorted(refs-set(allkeys)),
    missing_citations=sorted(cite-bib),duplicate_labels=sorted({x for x in allkeys if allkeys.count(x)>1}),
    label_target_mismatches=badlabels,invalid_link_pages=badlinks,missing_glyph='Missing character:' in log,
    overfull=log.count('Overfull'),underfull=log.count('Underfull'),visual_review='pending')
(R/'编译与引用.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
old={r['label']:r for r in csv.DictReader((W/'求解/审校_20260926/编号与引用映射.csv').open(encoding='utf-8-sig'))}
with (R/'编号与页码.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['label','number','page','previous_number','previous_page'])
    for label,number,page,anchor in labels:
        w.writerow([label,number,page,old.get(label,{}).get('new_number',''),old.get(label,{}).get('new_page','')])
print(json.dumps(result,ensure_ascii=False))
