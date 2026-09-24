"""Render selected reference previews for actual human/agent visual inspection."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,fitz

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT.parent
OUT=ROOT/'求解/模板对照'
OUT.mkdir(exist_ok=True)
INDEX=json.loads((ROOT/'求解/academic_figure_asset_index.json').read_text(encoding='utf8'))
IDS={'DensityHeatmap','ParameterSweep','Violin','MarginalDensity','ScenarioHeatmap','PairedBoxScatter',
     'GroupedViolin','BarComposition','ConvergenceBand','3DHeatmap','LineTrend'}
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
entries=[]
for f in INDEX['families']:
    if f['figure_type'] not in IDS:continue
    for rp in f['atlas_references']+[o['path'] for o in f['outputs']]:
        src=TEMPLATE/rp
        if src.suffix.lower()=='.pdf':
            pix=fitz.open(src)[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
            img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        else:
            img=Image.open(src).convert('RGB')
        entries.append((f['figure_type'],rp,img))
for start in range(0,len(entries),12):
    batch=entries[start:start+12]
    sheet=Image.new('RGB',(1800,1530),'#f8fafc')
    draw=ImageDraw.Draw(sheet)
    for j,(fam,path,img) in enumerate(batch):
        col,row=j%3,j//3;x,y=col*600,row*382
        img.thumbnail((560,325),Image.Resampling.LANCZOS)
        sheet.paste(img,(x+(600-img.width)//2,y+42+(325-img.height)//2))
        draw.text((x+10,y+8),f'{fam} | {Path(path).name}',font=FONT,fill='#26374f')
    output=OUT/f'selected_{start//12+1:02d}.png'
    sheet.save(output)
    print(output,len(batch))
