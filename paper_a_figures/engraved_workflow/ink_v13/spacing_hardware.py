"""Enlarge and compact V11 hardware components without distorting the artwork.

Call ``space_hardware(root, find, shift)`` after the V13 hardware outer
translation/uniform enlargement and label adjustments.  Only direct-child wrappers
are translated and uniformly enlarged; connectors and pipeline-rule ``d``
attributes are redrawn.
The two MTE2 bars move right by 12 native units for enlarged label clearance.
Cuboid faces,
glyphs, hatching, existing transforms, stroke styles and markers are retained.
The original painter order is preserved by wrapping contiguous runs.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
OFFSETS = {
    "core-tasks": 0,
    "pipelines": 50,
    "private-memory": 125,
    "copy-annotations": 215,
    "ddr": 270,
    "l2": 333,
    "fill-annotations": 333,
    "hit-annotation": 215,
}
LEFT_CORE_SHIFT = -20
RIGHT_CORE_SHIFT = -38
HIT_LABEL_SHIFT = -58
DDR_SHIFT = -29

CONNECTORS = {
    # Four private-memory arrows retain equal start/end clearances.
    "pipe-private-0": "M2178,877.24 V941.55",
    "pipe-private-1": "M2341,877.24 V941.55",
    "pipe-private-2": "M2575,877.24 V941.55",
    "pipe-private-3": "M2738,877.24 V941.55",
    # Endpoints follow the enlarged private-memory and DDR faces.
    # Control-point offsets interpolate those endpoint displacements, leaving
    # the native horizontal routing and arrowhead style intact.
    # Bow the middle of each COPY path away from its enlarged label while
    # retaining the same endpoints, stroke, markers and transfer direction.
    "left-copy-out": "M2165.9,1044.95 C2036,1129.35 2073,1236.75 2183.6,1300.15",
    "left-copy-in": "M2298,1300.15 C2419,1215.783333 2455,1127.416667 2342.1,1046.05",
    "right-copy-out": "M2581.6,1044.95 C2459,1132.35 2483,1227.75 2632.4,1300.15",
    "right-copy-in": "M2779.8,1300.15 C2859,1226.783333 2856,1124.416667 2762.2,1046.05",
    # Join the shifted DDR bottom to the shifted L2 left edge.  The two cubic
    # pieces retain a common vertical tangent; the bend moves to x=2325 to
    # clear the enlarged fill annotations when the horizontal gap is compact.
    "ddr-to-l2-fill": "M2343.1,1445.35 C2282,1450.35 2325,1515.36 2325,1572.36 C2325,1607.36 2340,1611.36 2387.32,1611.36",
    # Preserve the right-side routing while following enlarged L2/pipeline faces.
    "l2-hit-read": "M2798.36,1620.32 C2886,1443.706667 2904,1009.093333 2871.84,773.48",
}

_EXPLICIT_STAGES = {
    "copy-out-tensor-v6": "copy-annotations",
    "copy-in-tensor-v6": "copy-annotations",
    "copy-out-label": "copy-annotations",
    "copy-in-label": "copy-annotations",
    "right-copy-annotations-v8": "copy-annotations",
    "text-124": "ddr",
    "text-125": "l2",
    "text-127": "fill-annotations",
    "text-128": "fill-annotations",
    "l2-hit-label-v11": "hit-annotation",
}


def _stage(node):
    """Classify the fixed V11 direct children, equally for outlined/editable SVG."""
    ident = node.get("id", "")
    if ident in CONNECTORS:
        return None
    if ident in _EXPLICIT_STAGES:
        return _EXPLICIT_STAGES[ident]
    kind = node.tag.rsplit("}", 1)[-1]
    if kind in ("title", "desc"):
        return None
    # V11 already groups each original row by one of these translations.
    # Search rather than compare the entire transform because V13 adds label
    # adjustments while preserving the inherited transform expression.
    transform = node.get("transform", "")
    for original_y, name in ((50, "core-tasks"), (40, "pipelines"), (30, "private-memory")):
        if re.search(r"translate\(\s*0(?:\.0+)?\s*[, ]\s*" + str(original_y) + r"(?:\.0+)?\s*\)", transform):
            return name
    # These six cuboid faces are anonymous in V11.  Classify by their original
    # geometry; do not assign ids to them or rewrite any face/path coordinates.
    if kind == "path":
        start = node.get("d", "").split("l", 1)[0]
        if start in ("M2180,1080", "M2817,1080"):
            return "ddr"
        if start in ("M2460,1252", "M2790,1252"):
            return "l2"
    if kind == "rect":
        xy = (float(node.get("x", 0)), float(node.get("y", 0)))
        if xy == (2180, 1080):
            return "ddr"
        if xy == (2460, 1252):
            return "l2"
    raise ValueError("Unexpected V11 hardware child: " + (ident or ET.tostring(node, encoding="unicode")[:180]))


def _horizontal_shift(node, stage):
    """Close the between-core gap by translating the intact right-hand set."""
    if stage == "ddr":
        return DDR_SHIFT
    if stage == "hit-annotation":
        return HIT_LABEL_SHIFT
    if stage == "l2" or node.get("id") == "right-copy-annotations-v8":
        return RIGHT_CORE_SHIFT
    if stage == "copy-annotations":
        return LEFT_CORE_SHIFT
    if stage not in ("core-tasks", "pipelines", "private-memory"):
        return 0
    ident = node.get("id", "")
    if ident.startswith("text-") and ident[5:].isdigit():
        return RIGHT_CORE_SHIFT if 113 <= int(ident[5:]) <= 121 else LEFT_CORE_SHIFT
    if node.get("x") is not None:
        return RIGHT_CORE_SHIFT if float(node.get("x")) >= 2500 else LEFT_CORE_SHIFT
    match = re.match(r"M\s*([\d.]+)", node.get("d", ""))
    if match:
        return RIGHT_CORE_SHIFT if float(match.group(1)) >= 2500 else LEFT_CORE_SHIFT
    raise ValueError("Unclassified left/right hardware child: " + ident)


def _component_scale(node, stage, dx):
    """Return dx, uniform scale and the native anchor of each intact component."""
    if stage in ("core-tasks", "pipelines"):
        cx = 2708 if dx == RIGHT_CORE_SHIFT else 2293
        return dx, (1.10 if stage == "core-tasks" else 1.16), cx, (449 if stage == "core-tasks" else 676.5)
    if stage == "ddr":
        return dx, 1.10, 2514, 1105.5
    if stage == "l2":
        return dx, 1.12, 2637, 1331  # Keep the established bottom edge fixed.
    if stage == "private-memory":
        centers = {"text-111": 2206, "text-112": 2353, "text-120": 2621, "text-121": 2768}
        cx = centers.get(node.get("id"))
        if cx is None:
            first = node.get("x")
            if first is None:
                match = re.match(r"M\s*([\d.]+)", node.get("d", ""))
                first = match.group(1) if match else None
            x = float(first) if first is not None else -1
            cx = {2138: 2206, 2261: 2206, 2285: 2353, 2408: 2353,
                  2553: 2621, 2676: 2621, 2700: 2768, 2823: 2768}.get(x)
        if cx is None:
            raise ValueError("Unclassified private-memory face: " + str(node.attrib))
        # Increase the distance between L1 and UB centers enough to retain a
        # clear gap after each complete cuboid (including its label) grows.
        dx += -8 if cx in (2206, 2621) else 8
        return dx, 1.10, cx, 865.5
    return dx, 1.0, 0, 0


def _pipeline_label_clearance(children, shift):
    """Leave equal clearances for the enlarged MTE2/3 labels on both cores."""
    bars = []
    rules = []
    for node in children:
        kind = node.tag.rsplit("}", 1)[-1]
        if kind == "rect" and node.get("class") == "hatch" and node.get("y") == "659":
            x = float(node.get("x", 0))
            if x in (2211.8, 2626.8):
                bars.append((node, "left" if x < 2500 else "right"))
        if kind == "path" and node.get("class") in ("faint", "hair"):
            match = re.fullmatch(r"M(2207|2622),(\d+)H(2405|2407|2820|2822)", node.get("d", ""))
            if match:
                x, y, end = map(int, match.groups())
                side = "left" if x < 2500 else "right"
                rules.append((node, side, x, y, end))
    if len(bars) != 2 or len(rules) != 16:
        raise ValueError("Unexpected V11 pipeline bars/rules for equal label clearance")
    for node, side in bars:
        node.set("id", "hardware-mte2-bar-" + side + "-v13")
        shift(node, 12, 0)
    for node, side, x, y, end in rules:
        node.set("id", "hardware-pipeline-rule-" + side + "-" + str(y) + "-v13")
        node.set("d", f"M{x + 12},{y}H{end}")


def space_hardware(root, find, shift):
    """Translate 03's component rows and reconnect the existing native paths.

    ``find`` is the build helper ``find(root, id)``; ``shift`` is its
    ``shift(element, dx, dy)`` helper.  The passed hardware outer transform is
    untouched.  With a 1.12 uniform outer scale and a global y translation of
    approximately -3, the content runs from y=500 to the L2 base near y=1861.
    With global x translation -180.3, the enlarged pipeline pair spans roughly
    x=2154..3022, with the hit annotation retained inside the 3110 right edge.
    Pipeline frames grow 1.16; core/task sets, individual L1/UB cuboids and
    DDR grow 1.10; L2 grows 1.12 about its bottom edge.  All growth is uniform,
    with styles and original artwork retained.  The private-memory arrows are
    shortened from 114 to 64.31 native units and reconnect to the enlarged faces.
    Repeated calls on the same root are a no-op.
    """
    hardware = find(root, "hardware-cutaway-v6")
    if hardware.get("data-v13-component-spacing") == "uniform-components-compact":
        return
    children = list(hardware)
    stages = [_stage(node) for node in children]  # Validate before mutation.
    deltas = [_horizontal_shift(node, stage) if stage else 0 for node, stage in zip(children, stages)]
    components = [_component_scale(node, stage, dx) if stage else (0, 1, 0, 0)
                  for node, stage, dx in zip(children, stages, deltas)]
    connectors = {ident: find(hardware, ident) for ident in CONNECTORS}
    _pipeline_label_clearance(children, shift)
    for child in children:
        hardware.remove(child)
    counts = {}
    last_stage = None
    wrapper = None
    for node, stage, component in zip(children, stages, components):
        if stage is None:
            hardware.append(node)
            last_stage = None
            wrapper = None
            continue
        dx, scale, cx, cy = component
        key = (stage, dx, scale, cx, cy)
        if key != last_stage:
            counts[stage] = counts.get(stage, 0) + 1
            wrapper = ET.SubElement(hardware, "{" + SVG + "}g", {
                "id": "hardware-" + stage + "-v13-" + str(counts[stage]),
                "data-v13-spacing-role": stage,
                "data-v13-translate-x": str(dx),
                "data-v13-translate-y": str(OFFSETS[stage]),
                "data-v13-uniform-component-scale": str(scale),
            })
            if scale != 1:
                wrapper.set("transform", f"translate({cx:g},{cy:g}) scale({scale:g}) translate({-cx:g},{-cy:g})")
            shift(wrapper, dx, OFFSETS[stage])
        wrapper.append(node)
        last_stage = key
    for ident, d in CONNECTORS.items():
        connectors[ident].set("d", d)
    hardware.set("data-v13-component-spacing", "uniform-components-compact")
    hardware.set("data-v13-component-offsets", ";".join(name + ":" + str(value) for name, value in OFFSETS.items()))
    hardware.set("data-v13-horizontal-compaction", "left:-20;right:-38;ddr:-29;hit-label:-58")
