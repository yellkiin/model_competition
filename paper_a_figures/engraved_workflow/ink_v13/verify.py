#!/usr/bin/env python3
"""Validate the v13 deliverables without changing them.

Run ``python verify.py`` after build.py. PDF inspection needs PyMuPDF or pypdf;
all SVG, SVGZ and PNG checks use the Python standard library. This structural
check complements, rather than replaces, inspection of the rendered figure.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET


THEMES = ("mono", "qianjiang", "qinglu", "yanlan")
PANEL_POSITIONS = {
    "source-a": (1, 1), "source-b": (1, 2),
    "source-c": (2, 1), "source-d": (2, 2),
    "source-e": (3, 1), "source-f": (3, 2),
}
SVG_NS = "http://www.w3.org/2000/svg"
URL_REF = re.compile(r"url\(\s*['\"]?#([^)'\"\s]+)['\"]?\s*\)")
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_COLOR = re.compile(r"rgba?\([^)]*\)")


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def inspect_svg(path: Path, portable: bool) -> tuple[ET.Element, dict]:
    root = ET.parse(path).getroot()
    require(root.tag == f"{{{SVG_NS}}}svg", f"{path.name}: not an SVG document")
    ids: dict[str, ET.Element] = {}
    for element in root.iter():
        identifier = element.get("id")
        if identifier:
            require(identifier not in ids, f"{path.name}: duplicate ID {identifier}")
            ids[identifier] = element

    references: set[str] = set()
    for element in root.iter():
        for key, value in element.attrib.items():
            references.update(URL_REF.findall(value))
            if local_name(key) == "href" and value.startswith("#"):
                references.add(value[1:])
            if local_name(key) in ("aria-labelledby", "aria-describedby"):
                references.update(value.split())
        if local_name(element.tag) == "style":
            references.update(URL_REF.findall(element.text or ""))
    missing = references - ids.keys()
    require(not missing, f"{path.name}: unresolved references {sorted(missing)}")

    text_count = sum(local_name(e.tag) == "text" for e in root.iter())
    require(text_count == 0 if portable else text_count > 0,
            f"{path.name}: {'portable must have zero text nodes' if portable else 'editable must retain text'}; found {text_count}")
    require(not any(local_name(e.tag) == "image" for e in root.iter()),
            f"{path.name}: embedded raster image found")
    panels = {}
    for identifier, expected in PANEL_POSITIONS.items():
        require(identifier in ids, f"{path.name}: missing panel {identifier}")
        panel = ids[identifier]
        actual = (panel.get("data-row"), panel.get("data-column"))
        require(actual == tuple(map(str, expected)),
                f"{path.name}: {identifier} should be row/column {expected}, found {actual}")
        panels[identifier] = {"row": expected[0], "column": expected[1]}
    return root, {
        "file": path.name, "elements": sum(1 for _ in root.iter()),
        "ids": len(ids), "references": len(references), "text_nodes": text_count,
        "viewBox": root.get("viewBox"), "panels": panels,
    }


def geometry_digest(root: ET.Element) -> str:
    """Keep layout, paths, text and typography; normalize palette-only differences.

    ID/reference normalization includes color-derived marker names. Title, desc
    and metadata may name a palette, so they are excluded from geometry checks.
    """
    id_map = {e.get("id"): f"id-{i}" for i, e in enumerate(root.iter()) if e.get("id")}

    def normalize(value: str) -> str:
        value = URL_REF.sub(lambda m: f"url(#{id_map.get(m.group(1), m.group(1))})", value)
        value = HEX_COLOR.sub("#COLOR", value)
        return RGB_COLOR.sub("COLOR", value)

    def canonical(element: ET.Element):
        if local_name(element.tag) in ("title", "desc", "metadata"):
            return None
        attributes = []
        for key, value in sorted(element.attrib.items()):
            name = local_name(key)
            if name in ("data-palette", "data-theme", "aria-labelledby", "aria-describedby"):
                continue
            if name == "id":
                value = id_map[value]
            elif name == "href" and value.startswith("#"):
                value = "#" + id_map.get(value[1:], value[1:])
            elif name in ("fill", "stroke", "stop-color", "flood-color", "color"):
                if value not in ("none", "inherit", "currentColor", "transparent") and not value.startswith("url("):
                    value = "COLOR"
                else:
                    value = normalize(value)
            else:
                value = normalize(value)
            attributes.append((key, value))
        text = element.text or ""
        if local_name(element.tag) == "style":
            text = normalize(text)
        elif not text.strip():
            text = ""
        children = [result for child in element if (result := canonical(child)) is not None]
        return element.tag, attributes, text, children

    raw = json.dumps(canonical(root), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def inspect_pdf(path: Path) -> dict:
    try:
        import pymupdf as fitz
    except ImportError:
        fitz = None
    if fitz is not None:
        with fitz.open(path) as document:
            require(len(document) == 1, f"{path.name}: expected one page, found {len(document)}")
            page = document[0]
            image_count = len(page.get_image_info())
            # Also inspect unused image resources, not only painted images.
            resource_images = len(page.get_images(full=True))
            require(image_count == 0 and resource_images == 0,
                    f"{path.name}: PDF contains raster images")
            return {"file": path.name, "pages": 1, "images": 0,
                    "width_pt": round(page.rect.width, 3), "height_pt": round(page.rect.height, 3)}

    try:
        from pypdf import PdfReader
        from pypdf.generic import ContentStream, IndirectObject
    except ImportError as error:
        raise RuntimeError("PDF verification needs PyMuPDF or pypdf installed") from error
    document = PdfReader(path)
    require(len(document.pages) == 1, f"{path.name}: expected one page, found {len(document.pages)}")
    page = document.pages[0]
    visited: set[int] = set()

    # Pattern resources can hide images from PageObject.images/get_images().
    # Inspect every object, including compressed-object-stream entries.
    object_keys = {(number, generation) for generation, entries in document.xref.items()
                   for number in entries if number}
    object_keys.update((number, 0) for number in document.xref_objStm)
    for number, generation in object_keys:
        obj = document.get_object(IndirectObject(number, generation, document))
        if hasattr(obj, "get"):
            require(obj.get("/Subtype") != "/Image",
                    f"{path.name}: raster image object {number} found")

    def no_images(container, resources=None):
        resources = container.get("/Resources", resources)
        if resources is not None:
            resources = resources.get_object()
            for resource_type in ("/XObject", "/Pattern"):
                if resource_type not in resources:
                    continue
                for obj in resources[resource_type].get_object().values():
                    obj = obj.get_object()
                    if id(obj) in visited:
                        continue
                    visited.add(id(obj))
                    require(obj.get("/Subtype") != "/Image", f"{path.name}: raster image resource found")
                    if obj.get("/Subtype") == "/Form" or obj.get("/PatternType") == 1:
                        no_images(obj, resources)
        contents = container.get_contents() if hasattr(container, "get_contents") else container
        if contents is not None:
            stream = contents if isinstance(contents, ContentStream) else ContentStream(contents, document)
            require(not any(operator == b"INLINE IMAGE" for _, operator in stream.operations),
                    f"{path.name}: inline raster image found")

    no_images(page)
    return {"file": path.name, "pages": 1, "images": 0,
            "width_pt": round(float(page.mediabox.width), 3),
            "height_pt": round(float(page.mediabox.height), 3)}


def inspect_png(path: Path) -> dict:
    with path.open("rb") as file:
        header = file.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR",
            f"{path.name}: invalid PNG header")
    width, height = struct.unpack(">II", header[16:24])
    require(width > 0 and height > 0, f"{path.name}: invalid dimensions")
    return {"file": path.name, "width_px": width, "height_px": height}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--json", type=Path, help="optional report destination")
    args = parser.parse_args()
    root = args.root.resolve()
    report: dict = {"version": "ink_v13", "layout": "3 rows x 2 columns", "themes": {}, "errors": []}
    fingerprints: dict[str, dict[str, str]] = {"editable": {}, "portable": {}, "detail": {}}

    def find_one(filename: str) -> Path:
        matches = sorted(root.rglob(filename))
        require(len(matches) == 1, f"Expected exactly one {filename}; found {len(matches)}")
        return matches[0]

    for theme in THEMES:
        info: dict = {}
        report["themes"][theme] = info
        stem = f"workflow_{theme}_v13"
        for kind, suffix in (("editable", "_editable.svg"), ("portable", ".svg"), ("detail", "_detail.svg")):
            try:
                path = find_one(stem + suffix)
                svg, svg_info = inspect_svg(path, portable=kind != "editable")
                digest = geometry_digest(svg)
                svg_info["normalized_geometry_sha256"] = digest
                fingerprints[kind][theme] = digest
                info[kind] = svg_info
            except Exception as error:
                report["errors"].append(f"{theme}/{kind}: {error}")
        for extension, inspector in ((".pdf", inspect_pdf), (".png", inspect_png),
                                     ("_detail.pdf", inspect_pdf), ("_detail.png", inspect_png)):
            try:
                info[extension.lstrip("._").replace(".", "_")] = inspector(find_one(stem + extension))
            except Exception as error:
                report["errors"].append(f"{theme}/{extension[1:]}: {error}")
        try:
            compressed = find_one(stem + ".svgz")
            uncompressed = find_one(stem + ".svg")
            require(gzip.decompress(compressed.read_bytes()) == uncompressed.read_bytes(),
                    f"{compressed.name}: decompressed content differs from portable SVG")
            info["svgz"] = {"file": compressed.name, "matches_portable_svg": True}
        except Exception as error:
            report["errors"].append(f"{theme}/svgz: {error}")

    for kind, themes in fingerprints.items():
        if len(themes) == len(THEMES):
            require_same = len(set(themes.values())) == 1
            if not require_same:
                report["errors"].append(f"{kind}: normalized geometry differs between palettes: {themes}")
    # Report additional PNGs such as contact sheets without requiring a theme name.
    primary_pngs = {f"workflow_{theme}_v13{suffix}.png" for theme in THEMES for suffix in ("", "_detail")}
    report["additional_pngs"] = []
    for path in sorted(root.rglob("*.png")):
        if path.name not in primary_pngs:
            try:
                report["additional_pngs"].append(inspect_png(path))
            except Exception as error:
                report["errors"].append(f"{path.name}: {error}")
    report["passed"] = not report["errors"]
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
