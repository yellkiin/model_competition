#!/usr/bin/env python3
"""Render the exported PDFs independently; create review crops/contact sheet."""
from pathlib import Path
import fitz
from PIL import Image, ImageDraw
from build import HERE, THEMES

def main():
    images=[]
    for name in THEMES:
        doc=fitz.open(HERE/'exports'/f'workflow_{name}_v6.pdf');pg=doc[0]
        p=pg.get_pixmap(matrix=fitz.Matrix(2100/pg.rect.width,2100/pg.rect.width),alpha=False)
        im=Image.frombytes('RGB',[p.width,p.height],p.samples);im.thumbnail((1400,620))
        sheet=Image.new('RGB',(1400,655),'white');sheet.paste(im,(0,35))
        ImageDraw.Draw(sheet).text((15,8),name,fill='black');images.append(sheet)
        if name=='qinglu':
            s=pg.rect.width/3500
            for key,(x0,y0,x1,y1) in {'migration_exchange':(1510,490,2445,934),'split':(1040,960,1460,1350)}.items():
                clip=fitz.Rect(x0*s,(y0-235)*s,x1*s,(y1-235)*s)
                pg.get_pixmap(matrix=fitz.Matrix(2.2,2.2),clip=clip,alpha=False).save(HERE/'docs'/f'{key}.png')
    canvas=Image.new('RGB',(2800,1310),'white')
    for i,im in enumerate(images):canvas.paste(im,((i%2)*1400,(i//2)*655))
    canvas.save(HERE/'docs/four_palettes_review.png')

if __name__=='__main__':main()
