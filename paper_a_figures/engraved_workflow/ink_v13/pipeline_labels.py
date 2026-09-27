"""Replace only the eight 03 pipeline names with native SimSun Chinese labels.

Call ``replace_pipeline_labels(root)`` before ``scale_labels`` for both the
source SVG and its editable reference.  The source positions, 22-unit font size
and baselines remain unchanged.  Existing V13 label/component enlargement then
applies equally to editable text and portable outlines.  Only eight glyph
outlines are bundled; no font file is required to build the portable SVG.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
LABELS = {
    "text-107": ("矩阵", 2137, 580),
    "text-108": ("向量", 2137, 627),
    "text-109": ("读入", 2137, 674),
    "text-110": ("写出", 2137, 721),
    "text-116": ("矩阵", 2552, 580),
    "text-117": ("向量", 2552, 627),
    "text-118": ("读入", 2552, 674),
    "text-119": ("写出", 2552, 721),
}
FONT_SIZE = 22


@lru_cache(maxsize=1)
def _glyph_data():
    return json.loads(Path(__file__).with_name("pipeline_glyphs.json").read_text(encoding="utf-8"))


def replace_pipeline_labels(root):
    """Use 矩阵/向量/读入/写出 at exactly the eight original pipeline IDs."""
    nodes = []
    for ident, (label, x, y) in LABELS.items():
        node = root.find(".//*[@id='" + ident + "']")
        if node is None:
            raise ValueError("Missing pipeline label: " + ident)
        if node.tag.rsplit("}", 1)[-1] not in ("text", "g"):
            raise ValueError("Unexpected pipeline-label element: " + ident)
        nodes.append((node, label, x, y))
    data = _glyph_data()
    unit_scale = FONT_SIZE / data["units_per_em"]
    for node, label, x, y in nodes:
        if node.get("data-v13-pipeline-language") == "zh-CN":
            continue
        node.set("data-label", label)
        node.set("data-fonts", "SimSun")
        node.set("data-font-size", str(FONT_SIZE))
        node.set("data-v13-pipeline-language", "zh-CN")
        for child in list(node):
            node.remove(child)
        if node.tag == "{" + SVG + "}text":
            node.text = label
            node.set("font-size", str(FONT_SIZE))
            # Inline font-family overrides V11's generic .math family rule.
            existing = node.get("style", "").rstrip("; ")
            node.set("style", (existing + ";" if existing else "") + "font-family:'SimSun',serif;font-weight:400;font-style:normal")
        else:
            node.text = None
            node.set("data-anchor", "start")
            node.set("data-width", f"{sum(data['glyphs'][c]['advance'] for c in label) * unit_scale:.6f}")
            node.set("stroke", "none")
            outlines = ET.SubElement(node, "{" + SVG + "}g", {
                "transform": f"translate({x:g},{y:g}) scale({unit_scale:g},{-unit_scale:g})",
                "stroke": "none",
            })
            cursor = 0
            for char in label:
                glyph = data["glyphs"][char]
                attributes = {"d": glyph["path"]}
                if cursor:
                    attributes["transform"] = f"translate({cursor:g},0)"
                ET.SubElement(outlines, "{" + SVG + "}path", attributes)
                cursor += glyph["advance"]
