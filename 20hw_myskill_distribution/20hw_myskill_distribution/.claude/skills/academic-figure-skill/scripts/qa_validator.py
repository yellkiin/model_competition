#!/usr/bin/env python3
"""Academic Figure Skill QA Validator — translates references/checklist.md into executable assertions.

Input:  a generated Python plot script (or inline code string)
Output: structured PASS/FAIL/WARN report with line-level issue locations.

Usage:
    python qa_validator.py <script.py>              # validate a file
    python qa_validator.py "<code string>"          # validate inline code
    python qa_validator.py my_fig.py --journal nature  # journal-specific checks

Checks: AP-0 through AP-7, CL-1 through CL-7 (≈20 automated checks).
Pass 2 (VI-1..VI-6) and Pass 3 (VV-1..VV-5) are LLM-executed per checklist.md.
No AI needed for automated checks — runs anywhere Python is installed.
"""

from __future__ import annotations
import argparse, ast, os, re, sys
from collections import Counter
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Finding:
    check_id: str
    pass_: bool
    category: str  # "PASS", "FAIL", "WARN"
    message: str
    line: int | None = None  # best-effort line number


# ═══════════════════════════════════════════════════════════
# Pass 0 — Anti-Pattern Scan (AP-0 through AP-7)
# ═══════════════════════════════════════════════════════════

def check_ap0_style_baseline(source: str) -> Finding:
    return Finding('AP-0', False, "WARN", 'Compare the selected asset and sidecar style_contract; no mandatory global rcParams or palette block.')


def check_ap1_default_palette(source: str) -> Finding:
    return Finding('AP-1', False, "WARN", 'Palette suitability is assessed from data semantics and selected reference, not palette names.')


def check_ap2_jet_rainbow(source: str) -> Finding:
    """Detect jet/rainbow/hsv used as colormap."""
    patterns = ["cmap='jet'", "cmap='rainbow'", "cmap='hsv'",
                "cmap=\"jet\"", "cmap=\"rainbow\"", "cmap=\"hsv\""]
    hits = [p for p in patterns if p in source]
    ok = len(hits) == 0
    return Finding("AP-2", ok,
        "PASS" if ok else "WARN",
        "No jet/rainbow colormap" if ok else f"Spectral scale requires documented semantic/accessibility review: {hits}")


def check_ap3_four_sided_borders(source: str) -> Finding:
    return Finding('AP-3', False, "WARN", 'Retain meaningful reference borders; inspect clipping and overlap in the rendered output.')


def check_ap4_legend_occlusion(source: str) -> Finding:
    return Finding('AP-4', False, "WARN", 'Inspect the actual legend against plotted data. Internal placement is allowed in empty space.')


def check_ap5_low_res_export(source: str) -> Finding:
    """Verify vector export + 300dpi raster."""
    has_pdf = ".pdf" in source or "'pdf'" in source or '"pdf"' in source
    has_svg = ".svg" in source or "'svg'" in source or '"svg"' in source
    has_eps = ".eps" in source or "'eps'" in source or '"eps"' in source
    ok = has_pdf or has_svg or has_eps
    return Finding("AP-5", ok,
        "PASS" if ok else "FAIL",
        "Vector export present" if ok else "No vector export (PDF/SVG/EPS) — only raster found")


def check_ap6_missing_points(source: str) -> Finding:
    """For bar/box plots with small n, verify individual points shown."""
    has_points = any(kw in source for kw in
        ["stripplot", "swarmplot", "geom_point", "geom_jitter",
         "scatter", "sns.stripplot", "position_jitter"])
    has_bar = any(kw in source for kw in ["bar", "boxplot", "barh", "geom_boxplot"])
    if not has_bar:
        return Finding("AP-6", True, "PASS", "N/A — not a bar/box plot")
    return Finding("AP-6", has_points,
        "PASS" if has_points else "WARN",
        "Individual data points shown" if has_points else "Bar/box without individual points — add stripplot or geom_jitter")


def check_ap7_default_font(source: str) -> Finding:
    return Finding('AP-7', False, "WARN", 'Verify actual Chinese glyph coverage using chinese_fonts.py and rendered output; Arial is not required.')


# ═══════════════════════════════════════════════════════════
# Pass 1 — Code-Level Compliance (CL-1 through CL-7)
# ═══════════════════════════════════════════════════════════

def _find_fontsizes(source: str) -> list[float]:
    """Font keywords only; capsize/markersize/scatter size are not font sizes."""
    matches = re.findall(r"\b(?:fontsize|font\.size|labelsize|titlesize)\b[\"']?\s*[=:]\s*(\d+(?:\.\d+)?)", source)
    matches += re.findall(r"element_text\([^)]*?\bsize\s*=\s*(\d+(?:\.\d+)?)", source)
    return [float(x) for x in matches]


def check_cl1_fontsize(source: str) -> Finding:
    sizes = _find_fontsizes(source)
    if not sizes:
        return Finding("CL-1", True, "PASS", "No fontsize declarations — relying on defaults (verify manually)")
    too_small = [s for s in sizes if s < 5]
    ok = len(too_small) == 0
    return Finding("CL-1", ok,
        "PASS" if ok else "FAIL",
        f"All font sizes >= 5pt (min: {min(sizes)}pt)" if ok else f"Fonts below 5pt: {too_small}")


def check_cl2_dimensions(source: str) -> Finding:
    """Check figure dimensions match 89mm or 183mm column width."""
    # Look for size declarations in mm or inches
    mm_patterns = re.findall(r'figsize\s*=\s*\(\s*(\d+(?:\.\d+)?)\s*(?:\*\s*mm_to_inch|/\s*25\.4)', source)
    inch_patterns = re.findall(r'figsize\s*=\s*\(\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\)', source)
    # compose.py style: fig_width_mm / MM_PER_INCH
    compose_patterns = re.findall(r'(?:fig_width_mm|fig_w_mm)\s*=\s*(\d+\.?\d*)', source)
    ratio_divs = re.findall(r'(\d+\.?\d*)\s*/\s*MM_PER_INCH', source)
    ratio_slash = re.findall(r'(\d+\.?\d*)\s*/\s*mm_to_inch', source)
    # R: ggsave(width = XX, height = YY, units = "mm")
    r_mm = re.findall(r'width\s*=\s*(\d+\.?\d*)\s*,\s*(?:height|units\s*=\s*["\']mm)', source)

    widths_found = ([float(w) for w in mm_patterns] + [float(w)*25.4 for w,_ in inch_patterns]
                    + [float(w) for w in compose_patterns] + [float(w) for w in ratio_divs]
                    + [float(w) for w in ratio_slash])
    if not widths_found:
        return Finding("CL-2", True, "WARN", "No explicit dimension declaration — verify actual output size")
    bad=[w for w in widths_found if not (abs(w-89)<=3 or abs(w-183)<=5)]
    return Finding("CL-2", not bad, "FAIL" if bad else "PASS",
                   f"Non-journal widths: {bad}" if bad else f"Declared widths match 89/183mm: {widths_found}")


def check_cl3_dpi(source: str) -> Finding:
    """Check DPI >= 300 in savefig/ggsave calls or rcParams dict."""
    dpi_values = [int(m.group(1)) for m in re.finditer(r'dpi\s*=\s*(\d+)', source)]
    res_values = [int(m.group(1)) for m in re.finditer(r'res\s*=\s*(\d+)', source)]
    # rcParams dict form: "savefig.dpi": 300 or 'savefig.dpi': 300
    dict_dpi = [int(m.group(1)) for m in re.finditer(r'''["']savefig\.dpi["']\s*:\s*(\d+)''', source)]
    all_vals = dpi_values + res_values + dict_dpi
    if not all_vals:
        return Finding("CL-3", False, "WARN", "No explicit DPI — matplotlib defaults to 100 (insufficient for print)")
    too_low = [v for v in all_vals if v < 300]
    ok = len(too_low) == 0
    return Finding("CL-3", ok,
        "PASS" if ok else "FAIL",
        f"All DPI values >= 300" if ok else f"DPI below 300: {too_low}")


def check_cl4_font_embedding(source: str) -> Finding:
    has_pdf_type = "pdf.fonttype" in source and ("42" in source.split("pdf.fonttype", 1)[1][:20])
    has_svg_type = "svg.fonttype" in source and ("none" in source.split("svg.fonttype", 1)[1][:20].lower())
    has_cairo = "cairo_pdf" in source or "cairo_png" in source
    ok = has_pdf_type or has_cairo
    return Finding("CL-4", ok,
        "PASS" if ok else "FAIL",
        "Font embedding configured" if ok else "No pdf.fonttype=42 or cairo_pdf — fonts may not embed")


def check_cl5_spine_linewidth(source: str) -> Finding:
    return Finding('CL-5', False, "WARN", 'Compare reference stroke widths at final paper scale; no universal spine thickness.')


def check_cl6_tick_direction(source: str) -> Finding:
    return Finding('CL-6', False, "WARN", 'Inherit meaningful tick direction; verify legibility and overlap at final size.')


def check_cl7_export_completeness(source: str) -> Finding:
    has_vector = ".pdf" in source or ".svg" in source or ".eps" in source
    has_raster = ".png" in source or ".tif" in source
    ok = has_vector and has_raster
    return Finding("CL-7", ok,
        "PASS" if ok else "FAIL",
        "Vector + raster both exported" if ok else "Missing export — need both PDF and PNG")


if __name__ == '__main__':
    import json
    from dataclasses import asdict
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target');parser.add_argument('--journal',default='huawei');parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    try:
        path=Path(args.target)
        source=path.read_text(encoding='utf-8-sig') if path.is_file() else args.target
        findings=[]
        for name,check in sorted(list(globals().items())):
            if callable(check) and (name.startswith('check_ap') or name.startswith('check_cl')):
                if name=='check_cl2_dimensions' and args.journal=='huawei':
                    result=Finding('CL-2',False,'WARN','Project asset gate checks measured PDF width against actual TeX geometry; 89/183 mm is not imposed.')
                else:
                    result=check(source)
                findings.extend(result if isinstance(result,list) else [result])
        rows=[asdict(x) for x in findings]
        report={'status':'FAIL' if any(not x.pass_ and x.category=='FAIL' for x in findings) else 'PASS',
                'checks':rows,'assurance':'Static code patterns only, not visual review or actual artifact inspection'}
    except Exception as exc:report={'status':'FAIL','error':str(exc)}
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(0 if report['status']=='PASS' else 1)
