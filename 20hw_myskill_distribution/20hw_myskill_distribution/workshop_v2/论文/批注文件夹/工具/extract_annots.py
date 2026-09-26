# -*- coding: utf-8 -*-
"""Extract annotations (comments/highlights) from a PDF with the text they mark."""
import sys
import argparse
from pathlib import Path
import json
import pymupdf

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pdf")
parser.add_argument("output_json")
args = parser.parse_args()
PDF = args.pdf
Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)

MARKUP_TYPES = {pymupdf.PDF_ANNOT_HIGHLIGHT, pymupdf.PDF_ANNOT_UNDERLINE,
                pymupdf.PDF_ANNOT_STRIKE_OUT, pymupdf.PDF_ANNOT_SQUIGGLY}

results = []

doc = pymupdf.open(PDF)
for pno, page in enumerate(doc, start=1):
    for annot in page.annots() or []:
        a_type = annot.type  # (code, name)
        info = annot.info
        content = (info.get("content") or "").strip()
        author = (info.get("title") or "").strip()
        subject = (info.get("subject") or "").strip()
        cdate = info.get("creationDate") or info.get("modDate") or ""

        marked_text = ""
        # text-markup annotations: recover exact marked span(s) from quads
        if a_type[0] in MARKUP_TYPES and annot.vertices:
            quads = [pymupdf.Quad(annot.vertices[i:i + 4])
                     for i in range(0, len(annot.vertices), 4)]
            parts = []
            last_r = None
            for q in quads:
                r = q.rect
                if last_r is not None and abs(r.y0 - last_r.y0) < 1e-3:
                    # continuation on same line: avoid duplicating overlap
                    if r.x0 < last_r.x1:
                        r.x0 = last_r.x1
                t = page.get_textbox(r).strip()
                if t:
                    parts.append(t)
                last_r = q.rect
            marked_text = " ".join(parts)
        elif a_type[0] in MARKUP_TYPES:
            marked_text = page.get_textbox(annot.rect).strip()

        # try to locate a sentence around the marked rect for context
        context = ""
        if annot.rect and not annot.rect.is_empty:
            grow = pymupdf.Rect(annot.rect.x0 - 10, annot.rect.y0 - 12,
                                annot.rect.x1 + 10, annot.rect.y1 + 12)
            context = " ".join(page.get_textbox(grow).split())

        results.append({
            "page": pno,
            "type": a_type[1],
            "author": author,
            "date": cdate,
            "subject": subject,
            "comment": content,
            "marked_text": marked_text,
            "context": context,
        })

doc.close()

print(f"total annotations: {len(results)}")
for r in results:
    print("=" * 80)
    print(f"第{r['page']}页 | {r['type']} | 作者: {r['author']} | 时间: {r['date']}")
    if r["subject"]:
        print(f"主题: {r['subject']}")
    if r["marked_text"]:
        print(f"批注对象原文: {r['marked_text']}")
    if r["comment"]:
        print(f"批注内容: {r['comment']}")
    if r["context"] and not r["marked_text"]:
        print(f"所在区域文本: {r['context']}")

with open(args.output_json,
          "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("saved json")
