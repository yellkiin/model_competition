"""Local attachment extraction and explicit column mapping; original files are read-only.
OOXML is read as ZIP/XML, without Excel/LibreOffice or cached external services.
"""
from __future__ import annotations
import argparse,json,math,posixpath,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from .d_model import Problem,Terrain
from .d_experiments import save

S={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

def workbook(path):
    """Return sheet -> rows. Formulas retain cached value and expression separately.
    Dates stay Excel serial numbers: local mapping must explicitly define time zero.
    """
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in si.findall('.//s:t',S)) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        links={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        out={}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',S):
            target=links[sheet.attrib[REL]];name=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows=[];formulas=[]
            for r in ET.fromstring(z.read(name)).findall('s:sheetData/s:row',S):
                rid=int(r.attrib['r'])
                while len(rows)<rid: rows.append([])
                for c in r:
                    ref=c.attrib.get('r','');letters=re.match('[A-Z]+',ref)
                    if not letters: continue
                    col=0
                    for ch in letters.group(): col=26*col+ord(ch)-64
                    while len(rows[rid-1])<col: rows[rid-1].append(None)
                    v=c.find('s:v',S);value=None if v is None else v.text;typ=c.attrib.get('t')
                    if typ=='s' and value is not None: value=shared[int(value)]
                    elif typ=='inlineStr': value=''.join(t.text or '' for t in c.findall('s:is//s:t',S))
                    elif typ=='b': value=value=='1'
                    elif typ not in ('str','e') and value is not None:
                        try: value=float(value)
                        except ValueError: pass
                    rows[rid-1][col-1]=value
                    f=c.find('s:f',S)
                    if f is not None: formulas.append({'cell':ref,'formula':f.text,'cached':value})
            out[sheet.attrib['name']]={'rows':rows,'formulas':formulas}
        return out


def extract(repo,out):
    root=Path(repo)/'题目/D题';out=Path(out);out.mkdir(parents=True,exist_ok=True)
    index=[]
    for file in sorted(root.rglob('*.xlsx')):
        sheets=workbook(file);name=file.stem+'.json';save(out/name,{'source':str(file.relative_to(repo)),'sheets':sheets})
        index.append({'file':str(file.relative_to(repo)),'extracted':name,'sheets':{k:len(v['rows']) for k,v in sheets.items()}})
    for file in sorted(root.glob('*.docx')):
        with zipfile.ZipFile(file) as z:
            xml=z.read('word/document.xml');tree=ET.fromstring(xml)
            ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text=[''.join(p.itertext()) for p in tree.findall('.//w:p',ns)]
            (out/(file.stem+'.txt')).write_text('\n'.join(text),encoding='utf-8')
            # Preserve equations/tables in original OOXML alongside searchable text.
            (out/(file.stem+'.xml')).write_bytes(xml)
    save(out/'index.json',index)
    return index


def mapped(rule,row):
    if isinstance(rule,str): return row[rule]
    if 'when' in rule:
        cond=rule['when'];v=row[cond['column']]
        return mapped(rule['then'] if v in cond['in'] else rule.get('else',{'const':None}),row)
    if 'min' in rule:
        values=[mapped(r,row) for r in rule['min']];values=[v for v in values if v is not None]
        return min(values) if values else None
    value=rule['const'] if 'const' in rule else row[rule['column']]
    if 'values' in rule: value=rule['values'][str(value)]
    if value is None or value=='': return rule.get('missing',None)
    if 'scale' in rule or 'offset' in rule: value=float(value)*rule.get('scale',1)+rule.get('offset',0)
    if rule.get('type')=='int': value=int(value)
    if rule.get('type')=='str': value=str(value)
    return value


def table_rows(repo,spec):
    rows=workbook(Path(repo)/spec['file'])[spec['sheet']]['rows'];head=rows[spec['header_row']-1]
    headers=[str(v).strip() if v is not None else f'__empty_{i}' for i,v in enumerate(head)]
    if len(set(headers))!=len(headers): raise ValueError('duplicate headers: select the correct header row')
    output=[]
    for values in rows[spec['header_row']:]:
        if not any(v is not None for v in values): continue
        row={k:values[i] if i<len(values) else None for i,k in enumerate(headers)}
        if spec.get('skip_if_empty') and row[spec['skip_if_empty']] is None: continue
        output.append({field:mapped(rule,row) for field,rule in spec['fields'].items()})
    return output


def normalize(repo,mapping,out):
    cfg=json.loads(Path(mapping).read_text(encoding='utf-8'));data=cfg['template']
    for key,spec in cfg['tables'].items(): data[key]=table_rows(repo,spec)
    if cfg.get('coordinates',{}).get('input')=='lonlat':
        from pyproj import CRS,Transformer
        origin=next(n for n in data['nodes'] if n['id']==data['depot'])
        crs=CRS.from_proj4(f"+proj=aeqd +lat_0={origin['lat']} +lon_0={origin['lon']} +datum=WGS84 +units=m +no_defs")
        transform=Transformer.from_crs(cfg['coordinates'].get('source_crs','EPSG:4326'),crs,always_xy=True)
        for n in data['nodes']: n['x'],n['y']=transform.transform(n.pop('lon'),n.pop('lat'))
        data['terrain']['local_crs']=crs.to_wkt()
    terrain=data['terrain']
    if terrain['kind']=='raster': terrain['path']=str((Path(repo)/terrain['path']).resolve())
    dem=Terrain(terrain)
    for node in data['nodes']:
        if node.get('z') is None: node['z']=float(dem.height([[node['x'],node['y']]])[0])
    for f in data['fleet']:
        for key in ('count','batteries'): f[key]=int(f[key])
    # Dataclass/schema and physical-unit checks occur before writing the normalized input.
    p=Problem(data);save(out,data)
    return {'nodes':len(p.nodes),'boxes':len(p.boxes),'total_mass_kg':sum(b.mass for b in p.boxes),'total_volume_m3':sum(b.volume for b in p.boxes),'output':str(out)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('inspect');a.add_argument('--repo',default='.');a.add_argument('--out',required=True)
    b=sub.add_parser('normalize');b.add_argument('--repo',default='.');b.add_argument('--mapping',required=True);b.add_argument('--out',required=True)
    args=parser.parse_args()
    result=extract(args.repo,args.out) if args.command=='inspect' else normalize(args.repo,args.mapping,args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
