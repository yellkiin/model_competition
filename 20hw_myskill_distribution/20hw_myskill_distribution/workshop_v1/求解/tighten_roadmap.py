"""Adapt the chosen four-band draw.io template to the A4 paper width.

The chosen scibox template, topology, colors, headings and symbols are kept.
Only inter-band whitespace, canvas size and text size are adjusted after
inspecting its first render at the intended paper width.
"""

from pathlib import Path
from xml.etree import ElementTree as ET


HERE = Path(__file__).resolve().parent
source = HERE / "总体路线图.drawio"
target = HERE / "总体路线图_紧凑.drawio"
tree = ET.parse(source)
root = tree.getroot()
model = root.find("./diagram/mxGraphModel")
assert model is not None
model.set("pageWidth", "1100")
model.set("pageHeight", "1450")


def shift(y: str) -> str:
    value = float(y)
    offset = 105 if value >= 1210 else 70 if value >= 855 else 35 if value >= 500 else 0
    result = value - offset
    return str(int(result)) if result.is_integer() else str(result)


for cell in model.findall("./root/mxCell"):
    name = cell.get("id", "")
    geometry = cell.find("mxGeometry")
    if geometry is None:
        continue
    if name == "canvas_background":
        geometry.set("width", "1100")
        geometry.set("height", "1450")
        continue
    if name == "outer":
        points = geometry.find("Array")
        assert points is not None
        for point in points.findall("mxPoint"):
            if point.get("y") == "1675":
                point.set("y", "1420")
        continue
    if "y" in geometry.attrib:
        geometry.set("y", shift(geometry.get("y", "0")))
    for point in geometry.findall(".//mxPoint"):
        if point.get("y") is not None:
            point.set("y", shift(point.get("y", "0")))
    style = cell.get("style", "")
    if cell.get("value"):
        if name == "title":
            style = style.replace("fontSize=20;", "fontSize=24;")
        else:
            style = style.replace("fontSize=18;", "fontSize=22;")
        cell.set("style", style)

tree.write(target, encoding="utf-8", xml_declaration=True)
print(target)
