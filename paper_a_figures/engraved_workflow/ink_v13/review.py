#!/usr/bin/env python3
"""Make a palette contact sheet and a 160 mm-wide A4 paper layout proof."""
from pathlib import Path
import argparse
import pymupdf
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
THEMES=('qinglu','qianjiang','yanlan','mono')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/simsun.ttc'))
    a=p.parse_args()
    docs=HERE/'docs'; docs.mkdir(exist_ok=True)
    thumbs=[]
    for theme in THEMES:
        doc=pymupdf.open(HERE/'exports'/f'workflow_{theme}_v13.pdf')
        page=doc[0]; pix=page.get_pixmap(matrix=pymupdf.Matrix(1050/page.rect.width,1050/page.rect.width),alpha=False)
        im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        tile=Image.new('RGB',(1100,im.height+68),'white')
        ImageDraw.Draw(tile).text((25,15),theme,fill='black',font_size=24)
        tile.paste(im,(25,50)); thumbs.append(tile)
    sheet=Image.new('RGB',(2200,thumbs[0].height*2),'white')
    for i,tile in enumerate(thumbs): sheet.paste(tile,((i%2)*1100,(i//2)*tile.height))
    sheet.save(docs/'four_palettes_review.png')
    if not a.font.exists():
        raise FileNotFoundError('Pass --font with a CJK font for the A4 text proof')
    mm=72/25.4
    proof=pymupdf.open(); page=proof.new_page(width=210*mm,height=297*mm)
    fig=pymupdf.open(HERE/'exports'/'workflow_qinglu_v13.pdf')
    x,y,width=25*mm,25*mm,160*mm
    height=width*fig[0].rect.height/fig[0].rect.width
    page.show_pdf_page(pymupdf.Rect(x,y,x+width,y+height),fig,0)
    page.insert_font(fontname='song',fontfile=str(a.font))
    caption='图1.1　联合决策、候选生成与统一执行评价'
    page.insert_textbox(pymupdf.Rect(x,y+height+10,x+width,y+height+42),caption,fontname='song',fontsize=10.5,align=1)
    text=(docs/'PAPER_TEXT_PR69.md').read_text(encoding='utf-8').split('## 可直接放入论文的一段正文',1)[1].split('## 插入说明',1)[0].strip().replace('如图所示','如图1.1所示',1)
    font=pymupdf.Font(fontfile=str(a.font)); remaining=text; lines=[]
    # Do not put Chinese closing punctuation at the beginning of a proof line.
    while remaining:
        available=width-(21 if not lines else 0); end=1
        while end <= len(remaining) and font.text_length(remaining[:end],fontsize=10.5) <= available:
            end+=1
        end=max(1,end-1)
        if end < len(remaining) and remaining[end-1].isascii() and remaining[end-1].isalnum() and remaining[end].isascii() and remaining[end].isalnum():
            token_start=end
            while token_start>0 and remaining[token_start-1].isascii() and remaining[token_start-1].isalnum(): token_start-=1
            if token_start: end=token_start
        if end < len(remaining) and remaining[end] in '，。；：、）】！？': end=max(1,end-1)
        lines.append(remaining[:end]); remaining=remaining[end:]
    baseline=y+height+60
    for i,line in enumerate(lines):
        page.insert_text((x+(21 if i==0 else 0),baseline+i*16),line,fontname='song',fontsize=10.5)
    if baseline+len(lines)*16 > 272*mm: raise ValueError('A4 proof paragraph does not fit')
    proof.subset_fonts()
    proof.save(docs/'workflow_qinglu_v13_A4.pdf',garbage=4,deflate=True)
    proof[0].get_pixmap(matrix=pymupdf.Matrix(1.6,1.6),alpha=False).save(docs/'workflow_qinglu_v13_A4_preview.png')
    print('Four palettes and A4 160 mm placement proof written')

if __name__=='__main__': main()
