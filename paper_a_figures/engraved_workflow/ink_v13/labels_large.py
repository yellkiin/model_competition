"""Enlarge the six operation-panel labels without scaling their diagrams.

Call ``enlarge_pool_labels(root, editable_reference, find)`` immediately after
build.scale_labels and before layout translations. Works with both editable and
outlined SVGs by matching the original editable text IDs. Column-level headings
and the selection card are excluded so all three columns keep matching headers.
"""
from __future__ import annotations

import re

SVG = "http://www.w3.org/2000/svg"


def _append(node, transform):
    node.set("transform", (node.get("transform", "") + " " + transform).strip())


def enlarge_pool_labels(root, editable_reference, find, *, text_factor=1.12,
                        small_math_total=1.20, fifo_subtitle_factor=1.10):
    """Grow text only, retaining all primitive sizes, hatching and line widths.

    The existing build pass has already enlarged b/c/split outlined mathematics
    by 1.12. Other small operation/tensor/timeline symbols are still at their
    source size; bring these two cases to the same 1.20 total enlargement.
    """
    reference_text = {
        node.get("id"): node
        for node in editable_reference.iter()
        if node.tag == "{" + SVG + "}text" and node.get("id")
    }
    for letter in "abcdef":
        panel = find(root, "source-" + letter)
        if panel.get("data-v13-panel-labels-enlarged") == "true":
            continue

        def walk(node):
            identifier = node.get("id", "")
            reference = reference_text.get(identifier)
            if reference is not None:
                factor = fifo_subtitle_factor if identifier == "text-085" else text_factor
                x, y = float(reference.get("x", 0)), float(reference.get("y", 0))
                _append(node, f"translate({x:g},{y:g}) scale({factor:.12g}) translate({-x:g},{-y:g})")
                if node.get("data-v13-effective-font-size"):
                    size = float(node.get("data-v13-effective-font-size")) * factor
                    node.set("data-v13-effective-font-size", f"{size:.2f}")
                node.set("data-v13-panel-label-factor", f"{factor:.12g}")
                # A/B/C/D sit in 38-unit-high front faces. A small downward
                # baseline adjustment retains clearance under the hatched top.
                if re.match(r"[bc]-(before|after)-state-label-", identifier):
                    _append(node, "translate(0,1.25)")
                return
            if node.get("data-tex"):
                if identifier.startswith("badge-"):
                    factor = 1.10  # Keep lettering safely inside native circles.
                elif identifier.startswith(("b-", "c-", "split-")):
                    factor = small_math_total / 1.12
                else:
                    factor = small_math_total
                _append(node, f"scale({factor:.12g})")
                node.set("data-v13-panel-label-factor", f"{factor:.12g}")
                return  # A math formula is one label; do not enlarge its paths twice.
            for child in node:
                walk(child)

        walk(panel)
        panel.set("data-v13-panel-labels-enlarged", "true")
        panel.set("data-v13-panel-text-factor", f"{text_factor:.12g}")
        panel.set("data-v13-small-math-total", f"{small_math_total:.12g}")
