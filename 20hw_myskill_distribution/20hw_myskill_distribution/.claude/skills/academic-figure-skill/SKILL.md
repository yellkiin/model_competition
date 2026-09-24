---
name: academic-figure-skill
description: Create, adapt, review and export scientific result figures for manuscripts and Huawei Cup modeling papers using the bundled atlas and production sources. Use for model comparison, prediction/error, distributions, matrices, sensitivity, robustness and multipanel evidence. Excludes dashboards, decorative graphics, flowcharts and data cleaning alone.
---

# Academic Figure Skill

共享运行的命令变量 `$templateRoot`、`$workspaceRoot`、`$runtime`、`$python` 按模板 `华为杯_求解规范/工作区工作流.md` 的“命令变量”设置。工具从共享模板读取，子进程 cwd 为工作区；本题路径相对工作区，skill 内部引用相对本 SKILL.md。


In shared Huawei Cup runs, the template's `华为杯_求解规范/工作区工作流.md` defines the two roots. Read this skill and its relative references/assets from template_root using the selected runtime; write the index, overview, adapted script, figures, QA and caches under workspace_root. Run maintained tools through `workshop.py run`. Never copy this whole skill into a workshop or resolve its internal links against shell cwd. Preserve the full atlas and five-way mapping gates below.

## Panel routing boundary

Read the project drawing specification sections 1.3–1.4 before applying the atlas requirement. Ordinary statistical panels compare academic and modelviz equally under drawing specification section 1.2, regardless of attachment extension. Native images/frames/reconstructed imagery and domain spatial/signal rendering use the separate media evidence gate; they do not trigger gallery browsing or fabricate academic mappings. Mixed figures keep full academic checks for statistical panels and independent media/structure checks for the others. Geographic content also follows section 15. The full-gallery rules below apply only to academic panels; missing legacy routing fields retain academic compatibility; new plans explicitly declare source_skill.

## Continuous candidate discovery

For Huawei Cup, run the seven-dimension discovery check after each meaningful data, feature, training, optimization or validation stage and after method/result changes. Read the project drawing specification section 14 and `华为杯_求解规范/候选图工作流.md` for lifecycle and tools. All reserve figures require the same atlas/source mapping, real execution and plan/render visual QA as body figures. Only actual paper inclusion is deferred. `references/modeling-figures.md` routes problem types; do not restrict discovery to available family names or body figure quotas.

Create scientific figures by studying the actual designs in `assets/figure-atlas/` and `assets/figures/`, matching them to the data, and adapting the closest production source. The intended quality is visible design inheritance and scientific suitability, not a checklist of generic journal styling.

## Mandatory entry

Read `references/asset-reference-protocol.md` and the project's drawing specification first. That protocol defines the v2 full-gallery/candidate/style/execution/paper interface. Do not draw after reading only this SKILL.md.

For Huawei Cup, Codex reads `.agents/skills/academic-figure-skill`; Claude Code reads `.claude/skills/academic-figure-skill`. This is one of two equal ordinary-result providers alongside modelviz-skill; use its asset gate only for panels actually selecting academic. Project tools require an explicit runtime. Full automatic paper mode uses the contest question and Evidence Matrix to make routine scientific and design choices without per-figure confirmation. Ask only for a real missing input, unresolved unit ambiguity or unavailable necessary runtime/permission.

## Workflow

1. Understand the scientific question and inspect data/expected result schema before selecting a chart or layout. Establish units, groups/pairs, distributions, sample count and available statistics. Plan assumptions remain `planned` until saved results are validated.
2. Build the complete asset index and actually view every page of the readable full-gallery overview at the start of a paper. Handle PDF/SVG/multi-page files and document unviewable assets. Reuse the overview only for the same asset version. An index or metadata read is not viewing.
3. Search the whole catalog, compare plausible families using data suitability and actual appearance, then open candidates in detail and read all candidate-family production code/outputs. `references/directory-map.md` and `modeling-figures.md` are search aids, not automatic selection instructions.
4. Record per-Panel five-way mapping, selected example/source function, candidate decisions and concrete style contract. Choose symmetric/asymmetric/other layout from evidence and the reference; there is no default hero layout. Preserve style where it communicates meaning. Correctness → Chinese/paper readability → reference design → generic defaults.
5. Detect required Python/R and dependencies; copy the selected source to the work directory. Adapt data and necessary display parameters; record any faithful language port. Never silently lower quality because a runtime is missing. Use `native_run` for compatible real-data execution, `visual_adapt` for faithful adaptation, `cross_type_inherit` only for a documented semantic mismatch.
6. After selection, consult typography, palette, layout and export references to fill gaps. Do not overwrite an asset with a fixed global palette/spine/grid/legend policy. Set physical width from the actual TeX text width and intended fraction. Use `scripts/chinese_fonts.py` to resolve real Chinese glyph coverage; draw and inspect the smoke test.
7. Validate saved inputs, genuinely run the working script, capture logs and input/output hashes. No template p-values, fake replicates or improved-looking data. Real null effects, constant arrays and overlapping groups are valid. Output vector PDF/SVG plus 300 dpi PNG; do not flatten quantitative panels into PNG composites.
8. Follow `references/checklist.md`: actual reference/result comparison, final PNG/PDF and grayscale review at paper size. Report scientific validity, reference fidelity and print readability separately. Revise source and re-render defects. Static checks never establish beauty. Run plan/render/paper gates and register only current accepted outputs.

## Design decisions

- One figure answers one scientific question; panels add necessary evidence. Do not add redundant panels to imitate density.
- Inherit the reference's meaningful palette, geometry, marks, whitespace, axes, labels and annotation structure. A palette name or “Nature style” comment is not inheritance.
- Shared scientific semantics use stable colors/units; distinct questions can use different justified figure families and layouts. Avoid identical four-panel grids throughout a paper.
- Chinese labels and final print scale often require larger type or adjusted spacing. Record these adaptations instead of copying literal screen sizes.
- Scientific constraints take precedence over an attractive template. Never copy biological labels, results, effect sizes or unsupported uncertainty into contest figures.

## References and tools

Always read the asset protocol, `figure-contract.md` and `checklist.md`. Read `chinese-figures.md` plus `scripts/chinese_fonts.py` for Chinese rendering. After selecting assets, consult `typography.md`, `color-palettes.md`, `export-specs.md`, and `journal-specs.md` as conditional defaults. For multiple panels use `multipanel-layout.md`; for R use `r-rendering.md`; for relevant failure cases use `revision-cases.md` and `common-pitfalls.md`.

Project orchestration: `build_academic_figure_asset_index.py` → `prepare_academic_figure_review.py` → actual review → `audit_visual_plan.py --stage plan` → real execution and rendered review → `--stage render` → actual TeX/PDF review → `--stage paper`. Command details and migration rules are in the asset protocol. Initializers never fill observations or PASS.

Skill static tools `qa_validator.py` and `check_figure.py` flag technical issues; they do not supersede the project sidecar, source/reference review or rendered QA. Use `--journal huawei` for the project instead of imposing journal column sizes. `scripts/generate_adapters.py` produces portable pointers to these same rules; do not copy a competing fixed style from old adapters.

## Delivery

Deliver working source, vector master, PNG, statistics/provenance and actual visual review. Define sample/replicate, center/interval, tests when applicable, model splits/seeds/metrics and input fields. N/A is allowed with a scientific reason, never invented numbers. Record unresolved missing runtime or failed review as incomplete.

Mechanism/geometry uses the project Schematic Plan with TikZ/XeLaTeX. Flowcharts use Flowchart Plan and scibox-diagram/draw.io when available, TikZ fallback otherwise; this skill does not replace structural truth gates.
