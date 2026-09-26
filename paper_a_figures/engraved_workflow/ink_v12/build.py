#!/usr/bin/env python3
"""V12: preserve every V11 drawing object; tighten viewport and publish A4 sizes.

Requires Inkscape, PyMuPDF and Pillow. No font files or font installation are
needed: the portable source already contains the published native outlines.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SVG = 'http://www.w3.org/2000/svg'
NS = {'s': SVG}
ET.register_namespace('', SVG)
ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
THEMES = ('qinglu', 'qianjiang', 'yanlan', 'mono')
HASHES = {
 'qinglu': ('981eca4996d1c2fa9b787c8f6018f1917126c9d4','77e490e5a7594ac73c21092d9962cb4900094f1e'),
 'qianjiang': ('9cf289f3ef2435fba48c4564261b77d9bcdc5c6f','a45f47bd2ba0d229927e5171361cbf2048f72e4d'),
 'yanlan': ('0d6ce9d45255fc5241b296dd8450611294218f85','afd2ab13488196aa8c1f242b2c0c6ee54b40692a'),
 'mono': ('7d672f8c8d29b370e9642daceb31966ff9bc722b','b86d6c0cc94d1ae3adacb5d48da61fd957d6e03a'),
}
VIEW = (38, 240, 3454, 1536)
WIDTH_MM = 247
HEIGHT_MM = WIDTH_MM * VIEW[3] / VIEW[2]
PT_MM = 72 / 25.4
PNG_WIDTH = 7200
PREVIEW_WIDTH = 2400
LAYERS = ('joint-decision-v6', 'neighborhoods-v6', 'execution-v6',
          'main-process-v6', 'feedback-output-v6')


def run(command: list[str]) -> str:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if proc.returncode:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout


def blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def change(root: ET.Element) -> ET.Element:
    if root.get('data-version') != 'ink_v11':
        raise ValueError('Expected published V11 source')
    root.set('width', f'{WIDTH_MM}mm')
    root.set('height', f'{HEIGHT_MM:.12f}mm')
    root.set('viewBox', ' '.join(map(str, VIEW)))
    root.set('preserveAspectRatio', 'xMidYMid meet')
    root.set('data-version', 'ink_v12')
    root.set('data-input-version', 'ink_v11')
    root.set('data-v12-changes', 'tight-viewport-uniform-scale-A4-portrait-and-landscape-no-object-edit')
    root.find('s:title', NS).text = '图1.1 第十二版：A4等比例放大、联合决策与统一执行评价'
    root.find('s:desc', NS).text = (
        '第十一版原生字形和全部绘图对象保持不变，仅收紧外部留白并按A4设置物理尺寸。'
        '纵向正文版心160毫米；横向整页版心247毫米，较V11在160毫米处插入放大约56.43%。'
        '未单独拉伸、移位或重排文字、图形、框架和箭头。候选操作并非串行阶段；'
        '当前最优指已评价可行候选中的最好结果。'
    )
    return root


def verify_svg(old: ET.Element, new: ET.Element) -> dict:
    # Restore only explicitly permitted root attributes and accessibility text.
    restored = copy.deepcopy(new)
    restored.attrib.clear()
    restored.attrib.update(old.attrib)
    for tag in ('title', 'desc'):
        restored.find('s:' + tag, NS).text = old.find('s:' + tag, NS).text
    if ET.tostring(restored) != ET.tostring(old):
        raise AssertionError('A V11 drawing object changed')
    ids = [node.get('id') for node in new.iter() if node.get('id')]
    if len(ids) != len(set(ids)):
        raise AssertionError('Duplicate SVG IDs')
    editable = len(new.findall('.//s:text', NS))
    if editable not in (0, 107):
        raise AssertionError('Unexpected editable text count')
    return {'all_v11_drawing_objects_identical': True,
            'text_objects': editable, 'unique_ids': len(ids)}


def export(svg: Path, exe: str) -> None:
    for suffix, width in [('.pdf', None), ('.png', PNG_WIDTH), ('_preview.png', PREVIEW_WIDTH)]:
        cmd = [exe, str(svg), '--export-area-page', '--export-background=white',
               '--export-background-opacity=1', f'--export-filename={HERE / "exports" / (svg.stem + suffix)}']
        if width:
            cmd.append(f'--export-width={width}')
        run(cmd)


def page_proof(source: Path, target: Path, page_mm: tuple[float,float], draw_mm: float) -> None:
    import fitz
    src = fitz.open(source)
    out = fitz.open()
    pw, ph = (x * PT_MM for x in page_mm)
    page = out.new_page(width=pw, height=ph)
    w = draw_mm * PT_MM
    h = w * src[0].rect.height / src[0].rect.width
    box = fitz.Rect((pw-w)/2, (ph-h)/2, (pw+w)/2, (ph+h)/2)
    if min(box.x0, box.y0, pw-box.x1, ph-box.y1) < 25*PT_MM - 0.001:
        raise AssertionError('A4 proof crosses the 25 mm margins')
    page.show_pdf_page(box, src, 0, keep_proportion=True)
    out.set_metadata({'title':target.stem, 'subject':'A4 placement proof; not the compiled manuscript'})
    out.save(target, garbage=4, deflate=True)
    out.close(); src.close()


def verify_export(svg: Path, exe: str) -> dict:
    import fitz
    from PIL import Image
    data = run([exe, str(svg), '--query-all'])
    boxes = {}
    for line in data.splitlines():
        parts = line.split(',')
        if parts[0] in LAYERS:
            boxes[parts[0]] = list(map(float, parts[1:]))
    page_w = WIDTH_MM * 96 / 25.4
    page_h = HEIGHT_MM * 96 / 25.4
    for ident, (x,y,w,h) in boxes.items():
        if min(x,y) < -0.01 or x+w > page_w+0.01 or y+h > page_h+0.01:
            raise AssertionError('Visible layer clipped: ' + ident)
    if set(boxes) != set(LAYERS):
        raise AssertionError('Missing diagram layer')
    pdf = HERE/'exports'/(svg.stem+'.pdf')
    with fitz.open(pdf) as doc:
        p=doc[0]
        assert len(doc)==1 and not p.get_images() and not p.get_fonts()
        assert abs(p.rect.width/PT_MM-WIDTH_MM)<0.01
        assert abs(p.rect.height/PT_MM-HEIGHT_MM)<0.01
        p.get_pixmap(matrix=fitz.Matrix(3,3),alpha=False).save(HERE/'docs'/(svg.stem+'_pdf_review.png'))
    sizes={}
    for suffix,want in [('.png',PNG_WIDTH),('_preview.png',PREVIEW_WIDTH)]:
        with Image.open(HERE/'exports'/(svg.stem+suffix)) as img:
            assert img.width==want
            assert abs(img.height-want*VIEW[3]/VIEW[2])<1
            sizes[suffix]=list(img.size)
    assert gzip.decompress(svg.with_suffix('.svgz').read_bytes())==svg.read_bytes()
    return {'layer_bounds_px':boxes, 'visible_layers_inside_viewport':True,
            'pdf_pages':1,'pdf_image_resources':0,'pdf_font_resources':0,
            'pdf_size_mm':[WIDTH_MM,HEIGHT_MM], 'png_sizes':sizes}


def reviews(source: Path) -> None:
    import fitz
    from PIL import Image, ImageDraw
    ims=[]
    for name in THEMES:
        p=Image.open(HERE/'docs'/f'workflow_{name}_v12_pdf_review.png').convert('RGB')
        p.thumbnail((1400,650))
        cell=Image.new('RGB',(1440,700),'white')
        ImageDraw.Draw(cell).text((20,12),name,fill='black',font_size=22)
        cell.paste(p,(20,48));ims.append(cell)
    grid=Image.new('RGB',(2880,1400),'white')
    for i,im in enumerate(ims): grid.paste(im,((i%2)*1440,(i//2)*700))
    grid.save(HERE/'docs'/'four_palettes_review.png')
    # Same landscape sheet dimensions, so scale comparison is physical, not a zoom trick.
    comparison=fitz.open()
    paths=[source/'exports/workflow_qinglu_v11.pdf',HERE/'exports/workflow_qinglu_v12.pdf']
    for i,(path,w) in enumerate(zip(paths,(160,247))):
        with fitz.open(path) as src:
            page=comparison.new_page(width=297*PT_MM,height=210*PT_MM)
            page.insert_text((25*PT_MM,20*PT_MM),
                             'V11 at 160 mm' if i==0 else 'V12 at 247 mm (+56.43% linear scale)', fontsize=12)
            dw=w*PT_MM;dh=dw*src[0].rect.height/src[0].rect.width
            x=(page.rect.width-dw)/2;y=(page.rect.height-dh)/2
            page.show_pdf_page(fitz.Rect(x,y,x+dw,y+dh),src,0)
    comparison.save(HERE/'docs'/'A4_size_comparison_qinglu.pdf',garbage=4,deflate=True)
    canv=Image.new('RGB',(2376,840),'white')
    for i,page in enumerate(comparison):
        pix=page.get_pixmap(matrix=fitz.Matrix(4/PT_MM,4/PT_MM),alpha=False)
        im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        canv.paste(im,(i*1188,0))
    canv.save(HERE/'docs'/'A4_size_comparison_qinglu.png')
    comparison.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=HERE.parent/'ink_v11')
    args=parser.parse_args()
    exe=shutil.which('inkscape')
    if not exe: parser.error('Inkscape is required')
    for d in ('assets','exports','docs'): (HERE/d).mkdir(exist_ok=True)
    results={'source_version':'ink_v11', 'viewBox':list(VIEW),
             'portrait_width_mm':160,'landscape_width_mm':247,
             'relative_to_v11_at_160mm':247/160*3500/VIEW[2],
             'portrait_relative_to_v11_at_same_width':3500/VIEW[2],
             'palettes':{}}
    digests={}
    for name in THEMES:
        results['palettes'][name]={}
        for i,tail in enumerate(('', '_editable')):
            src=args.source/'assets'/f'workflow_{name}_v11{tail}.svg'
            if blob(src)!=HASHES[name][i]: raise ValueError('V11 source changed: '+str(src))
            old=ET.parse(src).getroot(); new=change(copy.deepcopy(old))
            target=HERE/'assets'/f'workflow_{name}_v12{tail}.svg'
            results['palettes'][name][tail or 'portable']=verify_svg(old,new)
            ET.ElementTree(new).write(target,encoding='utf-8',xml_declaration=True)
            digests[target.name]=hashlib.sha256(target.read_bytes()).hexdigest()
            if i==0:
                target.with_suffix('.svgz').write_bytes(gzip.compress(target.read_bytes(),mtime=0))
                export(target,exe)
                results['palettes'][name]['export']=verify_export(target,exe)
                pdf=HERE/'exports'/(target.stem+'.pdf')
                for kind,sz,w in [('portrait',(210,297),160),('landscape',(297,210),247)]:
                    page_proof(pdf,HERE/'exports'/(target.stem+f'_A4_{kind}.pdf'),sz,w)
        print(name+': preserved all source objects; vector and A4 exports verified',flush=True)
    reviews(args.source)
    write_json(HERE/'docs'/'VERIFICATION.json',results)
    write_json(HERE/'docs'/'REVIEWED_SVG_SHA256.json',digests)

if __name__=='__main__': main()
