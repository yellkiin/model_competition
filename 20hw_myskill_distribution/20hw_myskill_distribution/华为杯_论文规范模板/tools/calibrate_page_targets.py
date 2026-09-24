#!/usr/bin/env python3
"""Calibrate role-based chapter page windows from exemplar PDFs."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from pathlib import Path as _WorkflowPath
    _workflow_sys.path.insert(0, str(_WorkflowPath(__file__).resolve().parents[2] / "华为杯_求解规范/tools"))
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse
import json
from pathlib import Path


def inclusive(start, end):
    return max(0, end - start + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    by_role = {}
    observations = []
    for sample in baseline.get("samples", []):
        for section in sample.get("sections", []):
            if section.get("role") not in {"problem", "preliminary", "evaluation"}:
                continue
            pages = inclusive(section["start"], section["end"])
            role = section["role"]
            by_role.setdefault(role, []).append(pages)
            observations.append({"sample": sample["id"], "name": section["name"], "role": role, "pages": pages})
    targets = {}
    for role, values in sorted(by_role.items()):
        values.sort()
        lo = min(values)
        hi = max(values)
        # A role window is intentionally broad: it detects an outlier rather
        # than forcing every problem to imitate one exemplar.
        if role == "problem":
            min_pages = max(1, min(lo, 3))
            max_pages = max(hi, 14)
        elif role == "preliminary":
            min_pages, max_pages = 1, max(8, hi)
        else:
            # Historical observations never impose an evaluation maximum.
            targets[role] = {"min_pages": 1, "observed": values}
            continue
        targets[role] = {"min_pages": min_pages, "max_pages": max_pages, "observed": values}
    result = {
        "version": 2,
        "required_body_pages": int(baseline.get("required_body_pages", 35)),
        "page_system": baseline.get("page_number_system", "printed"),
        "body_definition": baseline.get("body_definition"),
        "chapter_hard_limits": {"关键性符号说明": 2},
        "chapter_start": "chapter_1_and_4_onward_new_page_chapters_2_3_continue",
        "first_three_chapters": {"min_pages": 3, "max_pages": 6, "severity": "warning", "counting": "unique_physical_content_pages_from_pdf_anchors"},
        "restatement_prose": {"minimum_equivalent_pages": 1.0, "severity": "error", "measurement": "paragraph_destinations_distinct_baselines_v1"},
        "evaluation_prose": {"minimum_equivalent_pages": 1.0, "severity": "error", "measurement": "paragraph_destinations_distinct_baselines_v1"},
        "abstract_targets": {"max_pages": 2, "keyword_label_count": 1,
                             "min_first_page_keyword_y_ratio": 0.8,
                             "policy": "摘要篇幅来自真实内容；不得以字号、间距或空白凑页。"},
        "role_targets": targets,
        "observations": observations,
        "policy": "Body minimum 35 pages and chapter_hard_limits remain hard gates. Restatement and evaluation each require at least one equivalent page of net prose in the final PDF, with no maximum. First-three-chapter 3\u20136 pages and other role windows are review warnings. Never alter official font, margins, or spacing, or repeat content to pass.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
