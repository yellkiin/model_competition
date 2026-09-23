"""Read D OOXML attachments, skipping named lock/metadata files only.

Original attachments and research_fd source are never modified. Run at repo root.
"""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research_fd.d_data import workbook

OUT = ROOT / "research_fd/outputs/official_extract"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def ignore(path):
    return (path.name.startswith(("~$", "._")) or path.name in (".DS_Store", "Thumbs.db")
            or "__MACOSX" in path.parts)

def math_text(node):
    tag=node.tag.rsplit("}",1)[-1]
    def child(name):
        x=node.find("m:"+name, NS)
        return "" if x is None else math_text(x)
    if tag=="f": return "("+child("num")+")/("+child("den")+")"
    if tag=="sSup": return child("e")+"^("+child("sup")+")"
    if tag=="sSub": return child("e")+"_("+child("sub")+")"
    if tag=="sSubSup": return child("e")+"_("+child("sub")+")^("+child("sup")+")"
    if tag=="rad": return "root["+child("deg")+"]("+child("e")+")"
    if tag=="d":
        pr=node.find("m:dPr", NS)
        left="("; right=")"
        if pr is not None:
            v=pr.find("m:begChr",NS)
            if v is not None: left=v.attrib.get("{"+NS['m']+"}val",left)
            v=pr.find("m:endChr",NS)
            if v is not None: right=v.attrib.get("{"+NS['m']+"}val",right)
        return left+" | ".join(math_text(x) for x in node.findall("m:e",NS))+right
    if tag=="nary": return "SUM_["+child("sub")+"]^["+child("sup")+"]("+child("e")+")"
    if tag=="m": return " ; ".join(math_text(x) for x in node.findall("m:mr",NS))
    if tag.endswith("Pr"): return ""
    if tag=="t": return node.text or ""
    return "".join(math_text(c) for c in node)

def para_text(p):
    parts=[]
    for child in p:
        if child.tag.endswith("}oMath") or child.tag.endswith("}oMathPara"):
            parts.append(" [MATH "+math_text(child)+"] ")
        else:
            parts.extend(x.text or "" for x in child.iter() if x.tag in
                         ("{"+NS['w']+"}t", "{"+NS['w']+"}instrText"))
    return "".join(parts)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files=sorted((ROOT/"题目/D题").rglob("*"))
    index=[]; skipped=[]; names=set()
    for file in files:
        if not file.is_file(): continue
        if ignore(file):
            skipped.append(str(file.relative_to(ROOT))); continue
        if file.suffix.lower() not in (".docx", ".xlsx"): continue
        if file.stem in names: raise ValueError("duplicate output stem: "+file.stem)
        names.add(file.stem)
        # Invalid non-lock files raise BadZipFile; do not silently skip corruption.
        with zipfile.ZipFile(file) as z:
            bad=z.testzip()
            if bad: raise ValueError(f"CRC failure in {file}: {bad}")
            item={"file":str(file.relative_to(ROOT)), "sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                  "bytes":file.stat().st_size, "type":file.suffix[1:]}
            if file.suffix.lower()==".xlsx":
                sheets=workbook(file); name=file.stem+".json"
                write(OUT/name,{"source":item['file'],"sheets":sheets})
                item.update(extracted=name,sheets={k:len(v['rows']) for k,v in sheets.items()})
            else:
                xml=z.read("word/document.xml"); tree=ET.fromstring(xml)
                paragraphs=tree.findall(".//w:p",NS)
                ids={id(p): i+1 for i,p in enumerate(paragraphs)}
                records=[{"paragraph":i+1,"text":para_text(p)} for i,p in enumerate(paragraphs)]
                tables=[]
                for ti,table in enumerate(tree.findall(".//w:tbl",NS),1):
                    rows=[]
                    for ri,row in enumerate(table.findall("w:tr",NS),1):
                        cells=[]
                        for ci,cell in enumerate(row.findall("w:tc",NS),1):
                            ps=cell.findall(".//w:p",NS)
                            cells.append({"row":ri,"column":ci,"paragraphs":[ids[id(p)] for p in ps],
                                          "text":"\n".join(para_text(p) for p in ps)})
                        rows.append(cells)
                    tables.append({"table":ti,"rows":rows})
                equations=[]
                for i,p in enumerate(paragraphs,1):
                    for m in p.findall(".//m:oMath",NS):
                        equations.append({"paragraph":i,"text":math_text(m),"xml":ET.tostring(m,encoding="unicode")})
                (OUT/(file.stem+".xml")).write_bytes(xml)
                (OUT/(file.stem+".txt")).write_text("\n".join(f"P{p['paragraph']:04}: {p['text']}" for p in records)+"\n",encoding="utf-8")
                write(OUT/(file.stem+".json"),{"source":item['file'],"paragraphs":records,"tables":tables,"equations":equations})
                item.update(extracted=file.stem+".json",text=file.stem+".txt",xml=file.stem+".xml",
                            paragraphs=len(paragraphs),tables=len(tables),equations=len(equations))
            index.append(item)
            print(json.dumps(item,ensure_ascii=False),flush=True)
    write(OUT/"index.json",index)
    write(OUT/"skipped_metadata.json",{"reason":"named Office locks and OS metadata only","files":skipped})
    print(json.dumps({"status":"complete","attachments":len(index),"skipped_metadata":skipped},ensure_ascii=False))

if __name__=="__main__": main()
