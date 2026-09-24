"""Measure visible overview ink in the actual paper, excluding caption/white margin.

This is a geometric check, never a judgement of substantive content or readability.
"""
from pathlib import Path

MM = 25.4 / 72
MIN_HEIGHT_MM = 148.5


def measure_body(page, bbox, text_width_mm, source_pdf=None):
    import pymupdf as fitz
    import numpy as np
    box = fitz.Rect(bbox)
    pix = page.get_pixmap(clip=box, dpi=216, colorspace=fitz.csRGB, alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    ys, xs = np.where(np.min(rgb, axis=2) < 240)
    failures = []
    if not len(xs):
        return {'status': 'FAIL', 'failures': ['empty_graphic']}
    # Use rendered pixmap origin: rounding a clip does not preserve its exact edge.
    ink = [(pix.x + xs.min()) / 3, (pix.y + ys.min()) / 3,
           (pix.x + xs.max() + 1) / 3, (pix.y + ys.max() + 1) / 3]
    width, height = (ink[2]-ink[0])*MM, (ink[3]-ink[1])*MM
    if height < MIN_HEIGHT_MM - .2:
        failures.append('overview_body_below_half_A4_height')
    if width < .9 * text_width_mm - .2:
        failures.append('overview_body_not_near_full_text_width')
    if box.width * MM > text_width_mm + .5:
        failures.append('overview_exceeds_text_width')
    ratio_error = None
    if source_pdf:
        with fitz.open(Path(source_pdf)) as source:
            if len(source) != 1:
                failures.append('overview_source_must_be_one_page')
            ratio_error = abs((box.width/box.height)/(source[0].rect.width/source[0].rect.height)-1)
            if ratio_error > .005:
                failures.append('overview_nonuniform_scaling_or_crop')
    return {'status': 'FAIL' if failures else 'PASS', 'failures': failures,
            'ink_bbox_bp': ink, 'body_width_mm': width, 'body_height_mm': height,
            'A4_height_fraction': height / 297, 'A4_area_fraction': width*height/(210*297),
            'text_area_fraction_25mm_margins': width*height/(160*247),
            'source_aspect_relative_error': ratio_error, 'threshold': 240, 'measurement_dpi': 216,
            'assurance': 'Actual PDF ink bbox; dashed borders count as ink. Content density, padding abuse and legibility require actual visual review.'}


def audit_bodies(root, diagrams, review):
    import pymupdf as fitz
    figures = {f['figure_id']: f for f in review['figures']}
    rows = []
    with fitz.open(root / review['pdf_path']) as pdf:
        for d in diagrams:
            if d.get('kind') != 'comprehensive' or d.get('placement') != 'body':
                continue
            occurrences = figures.get(d['diagram_id'], {}).get('occurrences', [])
            if len(occurrences) != 1:
                rows.append({'diagram_id': d['diagram_id'], 'status': 'FAIL', 'failures': ['one_overview_occurrence_required']})
                continue
            o = occurrences[0]
            rows.append({'diagram_id': d['diagram_id'], 'page': o['page_number'],
                         **measure_body(pdf[o['page_number']-1], o['pdf_bbox'], o['text_width_mm'], root/d['outputs']['vector'])})
    return rows
