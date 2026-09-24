# Figure QA: reference, science and final paper size

Reserve figures require every plan/render check below, including actual reference comparison, final vector-page/PNG/grayscale viewing and all three independent review dimensions. Before question completion audit seven-dimension stage records and promised figures; before delivery recheck code, results and claims for omissions. Only body-selected figures require actual in-paper evidence; reserve figures never count toward body quotas.

Read asset-reference-protocol.md for the v2 evidence schema. Checks here complement that gate; static code checks cannot establish visual quality. Do not inject a fixed palette, remove meaningful borders or impose a default layout to satisfy a linter.

## Before execution

- Complete full-gallery coverage and per-panel candidate detail. Verify source hashes and the actual function/section being adapted.
- Confirm saved fields, units, sample count, pairing, grouping, uncertainty and transformations. Planned schemas must be revalidated before rendering.
- Review the 16-row style contract against the chosen atlas and production example. Values from code and estimates from images must be distinguished.
- Derive width from actual TeX text width and intended fraction. Preserve reference proportions where compatible with Chinese text. No universal 89/183 mm requirement.
- Use chinese_fonts.py for actual glyph coverage, then draw and inspect Chinese text. No mandatory Arial replacement.

## Technical checks after actual execution

- Save real command, timestamps, return code, nonempty log and current input/source/output hashes. A pre-existing image is not execution evidence.
- Recompute relevant statistics from saved data. Define center, interval and independent replicate. No invented significance brackets, uncertainty, KDE, fitted surfaces or copied template values.
- Check vector primitives, fonts and physical PDF/SVG dimensions, and PNG at 300 dpi. Quantitative text/lines remain vector; genuine image layers may remain raster.
- Check axes include the data and do not mislead. Bars start at zero unless an explicitly justified alternative encoding is used. Null effects and constant arrays are valid; never add noise to make density estimable.
- Source linting is advisory where output cannot be inferred. check_figure.py and qa_validator.py default to the Huawei project profile. Their PASS never replaces the project gate or viewing.

## Actual image review (required)

Open selected original references again after context recovery. Open the final PNG, rendered vector PDF, grayscale and QA-only reference/current comparison. For dense layouts enlarge or crop until labels and encodings can be inspected. The comparison includes both selected atlas and production example and records their current hashes.

Report three separate dimensions with concrete observations:

1. **scientific_validity**: Does the figure answer its stated question using actual fields, units and justified statistics? Are intervals, distributions, thresholds and scales honestly defined?
2. **reference_fidelity**: Which source layout proportions, semantic colors, marks, spacing, legends and annotation conventions remain recognizable? Explain each necessary deviation. A common palette name is insufficient evidence.
3. **print_readability**: At actual TeX scale, inspect all Chinese text, units, ticks, panels, legends and colorbars for overlap/cropping, density, line weight and grayscale distinguishability.

Keep scientifically meaningful grids, complete frames, internal legends or marginal distributions when the reference and data warrant them. Fix visible defects, rerun the working source and regenerate evidence. Do not merely change QA status. Record failure or incomplete review honestly.

## Paper admission

Confirm the actual included vector path, current hash, TeX source closure, compiled PDF and displayed width. Open the actual paper page. Check the set of figures for stable semantic colors and varied, scientifically justified structures; do not force all questions into four equal panels.

READY requires all three dimensions and the plan/render/paper gate to pass with current artifacts. Missing runtime, unviewed output or a unresolved visual issue remains INCOMPLETE. After three root-cause repair failures report the exact blocker and existing artifacts; do not waive quality gates.

Editable receipts and hashes validate recorded provenance and coverage, not cognition or aesthetic quality. Actual viewing tool calls and the specific observations remain essential.
