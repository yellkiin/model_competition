from pathlib import Path
import fitz, io, re
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

def recover(pdf, out):
    doc=fitz.open(pdf); seen={}
    for page in doc:
        for item in page.get_fonts(full=True): seen[item[0]]=item
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    for family in ['STXinwei','LiSu']:
        chars={}; meta=None
        for x,info in seen.items():
            if info[1]!='ttf' or info[3].split('+')[-1]!=family: continue
            ft=TTFont(io.BytesIO(doc.extract_font(x)[3])); gs=ft.getGlyphSet()
            if meta is None: meta=ft
            cmap=ft.getBestCmap() or {} if 'cmap' in ft else {}
            if not cmap:
                key=doc.xref_get_key(x,'ToUnicode')[1]
                text=doc.xref_stream(int(key.split()[0])).decode('ascii'); pairs=[]
                for block in re.findall(r'beginbfchar(.*?)endbfchar',text,re.S):
                    pairs+=re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>',block)
                for block in re.findall(r'beginbfrange(.*?)endbfrange',text,re.S):
                    for a,b,c in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>',block):
                        pairs += [(f'{i:04X}',f'{int(c,16)+i-int(a,16):04X}') for i in range(int(a,16),int(b,16)+1)]
                dx=int(re.search(r'\d+',doc.xref_get_key(x,'DescendantFonts')[1]).group())
                kind,value=doc.xref_get_key(dx,'CIDToGIDMap')
                mapping=doc.xref_stream(int(value.split()[0])) if kind=='xref' else None
                for a,b in pairs:
                    u=bytes.fromhex(b).decode('utf-16-be')
                    if len(u)!=1: continue
                    cid=int(a,16); gid=int.from_bytes(mapping[2*cid:2*cid+2],'big') if mapping else cid
                    if gid<len(ft.getGlyphOrder()): cmap[ord(u)]=ft.getGlyphName(gid)
            for u,g in cmap.items():
                if u in chars: continue
                pen=DecomposingRecordingPen(gs); gs[g].draw(pen)
                tt=TTGlyphPen(None); pen.replay(tt); chars[u]=(tt.glyph(),ft['hmtx'][g])
        if not chars: raise RuntimeError('Missing embedded masthead glyphs: '+family)
        units=meta['head'].unitsPerEm
        chars.setdefault(32,(TTGlyphPen(None).glyph(),(units//2,0)))
        fb=FontBuilder(units,isTTF=True); cmap={u:'u%06X'%u for u in chars}
        fb.setupGlyphOrder(['.notdef']+list(cmap.values()))
        fb.setupGlyf({'.notdef':TTGlyphPen(None).glyph(),**{cmap[u]:g[0] for u,g in chars.items()}})
        fb.setupHorizontalMetrics({'.notdef':(units,0),**{cmap[u]:g[1] for u,g in chars.items()}})
        fb.setupHorizontalHeader(ascent=meta['hhea'].ascent,descent=meta['hhea'].descent,lineGap=meta['hhea'].lineGap)
        fb.setupCharacterMap(cmap)
        fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':family+'-TemporaryEmbeddedGlyphs','fullName':family,'psName':family})
        os2=meta['OS/2']
        fb.setupOS2(sTypoAscender=os2.sTypoAscender,sTypoDescender=os2.sTypoDescender,sTypoLineGap=os2.sTypoLineGap,usWinAscent=os2.usWinAscent,usWinDescent=os2.usWinDescent)
        fb.setupPost(); fb.save(out/(family+'.ttf'))
        print(f'{family}: {len(chars)} existing masthead/label glyphs; private temporary use only')
