# Academic asset reference protocol v2 (Huawei Cup)

共享运行的命令变量 `$templateRoot`、`$workspaceRoot`、`$runtime`、`$python` 按模板 `华为杯_求解规范/工作区工作流.md` 的“命令变量”设置。工具从共享模板读取，子进程 cwd 为工作区；本题路径相对工作区，skill 内部引用相对本 SKILL.md。

Shared-workspace path contract: `.agents/...` or `.claude/...` reference identifiers remain relative to template_root; scientific paths, index/contact outputs and review derivatives remain relative to workspace_root. Use the dedicated read-only resource resolver for references. Existing commands below show legacy child-tool arguments; invoke shared runs through the template's `workshop.py run --workspace-root ... --tool ... -- ...` entry. Do not prepend arbitrary ../ to records, copy complete skills, or relax scientific output boundaries. Shared asset changes invalidate dependent reference evidence.

## Candidate scope extension

The separate `候选图清单.schema.json` registry supports visual plan v1.1 with v1.0 compatibility and the v2 academic asset protocol. `candidate_figures.py figure` and the runner audit one complete figure with the same applicable plan/render route checks; other unfinished candidates and body quotas are outside that scope. Body plans are derived selections and still pass full existing counts and paper checks. No automatic transfer of QA to changed assets or of render approval to paper approval. Reserve figures must be fully reviewed at planned paper dimensions. The full-gallery rule applies equally to academic candidates; skill asset/source files stay read-only.

## Scope and priority

Panel classification follows drawing specification sections 1.3–1.4. Visual plan v1.1 adds routes while retaining v1.0 compatibility; this academic v2 asset contract remains unchanged. Prepare/audit only the academic panels in mixed figures, retain whole-figure execution/output checks, and independently audit modelviz panels through `.modelviz.json` and native/domain/structure panels through `.media.json`. Pure native/domain figures need no academic sidecar or gallery. Figure data, maps and rendering still require real provenance and visual review.

Ordinary scientific figures compare this skill and modelviz-skill as equal sources under drawing specification section 1.2. This v2 sidecar is exclusively for academic-source panels, never fabricated for modelviz panels. Codex uses `.agents/skills/academic-figure-skill`; Claude uses `.claude/skills/academic-figure-skill`. All project CLIs require `--runtime codex|claude`. Never silently read the other mirror. Diagram backends follow the project structure-diagram workflow; ordinary flowcharts remain scibox-diagram/draw.io first, while algorithm, physics and comprehensive diagrams use their dedicated skill routes.

Priority: scientific correctness and real data semantics → Chinese readability and actual paper format → selected asset design → generic defaults. The atlas and production outputs provide design evidence, never contest data. Do not impose a minimum effect, correlation, variance, AUC or separation.

## 1. Whole-gallery overview, once per project and asset version

Run the index builder below. It recursively inventories all asset files; visual inventory includes every image frame, PDF page and SVG, with per-file errors, source/output hints and placeholders. Render the numbered contact sheets and actually open every page. Each cell maps to the full relative source path, page/frame, preview, bounding box and hashes in `contact_manifest.json`. Contact sheets support overview; open originals or detailed crops when density prevents understanding. A damaged/unviewable file is an explicit incomplete item, never silently omitted.

After actual viewing, fill `gallery_review.json`: one receipt for every contact page, and concrete data fit, visual features and limitations for each image asset. The initializer leaves observations empty. A script cannot attest that an image was viewed. Reuse only when runtime, inventory and preview hashes match; reindex changes and review changed assets. A fresh context must reopen this figure's selected original references even if the global overview is reusable.

## 2. Data-first search and candidate detail

Before choosing type/layout, establish the question, fields, units, dimensions, grouping/pairing, sample count, distribution and available uncertainty. At plan time label assumptions `planned`; before rendering inspect saved results and mark `verified` with a hashed data profile. Missing statistics are not permission to copy template numbers.

`prepare_academic_figure_review.py` searches the complete family catalog, including zero-hit families, and records deterministic keyword/structure hints. These are NOT a semantic or visual classifier. Read the overview observations and compare scientifically plausible alternatives; normally 2–3, or explain why only one is suitable. Do not assume the plan's current family is the only possible candidate. Rewrite the query and plan family/layout when review warrants it.

For each candidate family open ALL example outputs and read ALL related scripts/dependencies. Open candidate atlas originals. The selected atlas and selected production example require detailed image/PDF/SVG viewing, not only a small contact cell. PDF/SVG multi-page candidates require complete page review. Record actual tools/paths and specific observations; do not invent tool call IDs or reuse generic prose for different assets. If the harness exposes no stable tool ID, record the actual tool name, exact file and identifiable session context, with the assurance boundary below.

## 3. Five-way mapping and executable style contract

For every Figure/Panel record question → actual result schema → exact atlas image → exact production source → native_run/visual_adapt/cross_type_inherit. Also record production example, source function/line section, each candidate's fit/conflict/selection reason, and the inherited/changed visual parameters.

The sidecar `style_contract` covers layout, hierarchy, facets, palette, line_width, marker_size, alpha, axes, ticks, grid, legend, colorbar, annotations, spacing, statistics and typography. Each row states reference_value, final_value, basis (`source`, `image_estimate`, `not_applicable`), source_path, source_locator and reason. Use actual values where available; explicitly distinguish visual estimates. For N/A state the scientific reason. A generic “Nature style” entry is insufficient.

Copy the selected production source into the work directory and adapt its data loader, fields, units and necessary display parameters. Retain reference proportions, semantic palette, marks, axes, legends and annotation logic when meaningful. Do not blindly inject global rcParams/theme before selection. Use common defaults only for gaps. Significant brackets, fitted curves, uncertainty and density layers require real valid data/statistics. Keep true null/constant/overlapping data; omit invalid KDE rather than add noise. No source/example image becomes a contest result.

Set `paper_geometry` from the actual TeX format: source_tex/hash, measured or explicitly derived text_width_mm, width_fraction and basis. target_width_mm = text_width_mm × width_fraction. Current A4 with 25 mm left/right margins has 160 mm text width; 0.8 textwidth is 128 mm, not 183 mm. Verify actual output and in-paper readability rather than blindly forcing either value. Scientific geometry and Chinese legibility may justify changing reference proportions; record why.

## 4. Execution and independent visual dimensions

Run the plan gate before formal rendering. Use a working copy, saved input and real execution logs (command, timestamps, returncode, log/hash and input/script/output hashes). Output vector PDF/SVG and 300 dpi PNG. Quantitative axes, labels and lines remain vector; real raster data layers may be rasterized. Avoid bbox=tight silently changing declared physical dimensions; measure exports.

Open final PNG, rendered PDF and grayscale. Generate a QA-only reference/actual contact with the exact selected atlas + production example + final image, preserve its input hashes, and ACTUALLY open it. Record whether each visual difference is a necessary adaptation or a defect. Fix/re-render/review unresolved defects. Separately report `scientific_validity`, `reference_fidelity`, `print_readability`; each needs substantive observations. Static PASS is not an aesthetic PASS.

The render gate requires current data profiles, outputs, actual run, comparison inputs and three review dimensions. The paper gate additionally requires actual TeX inclusion and measured size/page review. Keep each figure near its scientific evidence; review whole-paper semantic colors and visual rhythm without manufacturing extra panels.

## Commands and migration

Run from project root using the actual project Python, not an unverified Windows alias. Replace `codex` with `claude` for that runtime. The exact CLIs are available via `--help`.

```powershell
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/build_academic_figure_asset_index.py -- --runtime $runtime --check-sync --contact-dir 求解/验收输出/academic_assets --report 求解/验收输出/academic_assets.index.audit.json
# Actually view every generated page, then fill academic_assets/gallery_review.json.

& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/prepare_academic_figure_review.py -- --runtime $runtime --plan 求解/视觉计划.json --gallery-review 求解/验收输出/academic_assets/gallery_review.json
# Complete candidate search/comparisons, detail receipts, mapping, geometry and styles.
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_visual_plan.py -- --runtime $runtime --plan 求解/视觉计划.json --stage plan --project-root . --report 求解/视觉计划.plan.audit.json
# Execute plotting, collect real profiles/run evidence, open references and results, fill QA.
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_visual_plan.py -- --runtime $runtime --plan 求解/视觉计划.json --stage render --project-root . --report 求解/视觉计划.render.audit.json
# After audit_tex passes, compile and collect actual inclusions (includes the required XeLaTeX passes and BibTeX when needed).
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/collect_academic_paper_review.py -- --runtime $runtime --plan 求解/视觉计划.json --main-tex 论文/论文.tex --output 论文/验收输出/图形入文.review.json --project-root .
# Actually open the generated paper pages; fill occurrences and portfolio_review.
& $python -B "$templateRoot/华为杯_求解规范/tools/workshop.py" run --workspace-root $workspaceRoot --runtime $runtime --tool 华为杯_求解规范/tools/audit_visual_plan.py -- --runtime $runtime --plan 求解/视觉计划.json --stage paper --main-tex 论文/论文.tex --project-root . --report 论文/验收输出/视觉计划.paper.audit.json
```

`视觉计划.schema.json` v1.1 retains v1.0 compatibility; absent routing fields mean academic. The separately versioned `academic_figure_references.schema.json` and `<plan>.assets.json` remain v2. Old v1 reviews cannot pass v2 by changing a version string: retain the old sidecar as history, regenerate a draft from the current index, then actually perform missing overview, candidate, style and comparison review. Initializers must never transfer old PASS into new unperformed requirements. DEMO fixtures remain in `求解/验收输出/academic_figure_integration/`; `--allow-demo` never permits paper-stage production acceptance.

## Assurance boundary

### Execution and paper collectors

`run_academic_figure.py --runtime codex --plan <plan> --figure-id <ID> --interpreter <absolute-python-or-Rscript> -- <script arguments>` runs the full plan gate, then the actual working script. It records input hashes before running, log, return code and output modification times. `prepare_academic_figure_qa.py --runtime codex --plan <plan> --figure-id <ID>` produces current vector/grayscale/reference-comparison previews and an unreviewed QA record. Neither tool grants visual approval; existing QA requires explicit `--replace-review` after retaining its history.

`collect_academic_paper_review.py` requires the render gate first. It uses a wrapper around the unchanged main TeX, runs XeLaTeX with `-shell-escape -recorder` (two passes, or an initial pass followed by BibTeX and two further passes), and records graphicx's resolved path, box width/height/depth, actual shipout page and named PDF destination. Version 2.2 paper evidence derives `pdf_bbox` from that destination and the measured box. The paper gate rederives coordinates and checks overview/roadmap graphics and captions against actual subsection boundaries, including the physical preceding reference. It hashes the local TeX source closure, final PDF, `.fls` and `.afprobe`, generates actual PDF page renders, and links the new review path into the sidecar. The record follows `academic_paper_review.schema.json`; all occurrence/portfolio reviews start blank. The paper gate re-derives measured values and compares preview pixels against the current PDF. Same filenames in different directories do not match.

BibTeX inputs are collected separately because XeLaTeX's `.fls` normally omits them. The collector enables `KPATHSEA_DEBUG=4`, reads successful file opens and cross-checks the `.blg` database/style list. It hashes every actually read `.bib`/`.bst` in `bibliography_inputs`, adds project inputs to `source_closure`, and tracks nested `.aux` files in `generated_outputs`. External bibliography/style inputs retain their absolute paths and hashes; package project-owned dependencies for reproducibility. Missing or unsupported open traces fail with a recompile instruction; a file-search result is not read evidence. Reverification reads current inputs again, so editing a bibliography or style invalidates the old review. This is file provenance, not proof that references are real, relevant, correctly cited or sufficient in number.

Use `includegraphics` width/height/angle for planned figures. Public outer `resizebox`, `scalebox` and `rotatebox` wrappers are explicitly rejected because the inner box measurement would not represent the final transformed width. Resolve such a failure in the working paper source rather than accepting an incorrect measurement. Custom low-level TeX transformations still need manual review. Do not edit official classes or title formatting to accommodate the probe.

Retain an existing paper review and select a new output path on rerender. After BibTeX or any source/figure edit, run the collector and actual page review again. Old manually declared paper-width records, version 2.0 records without physical coordinates, and version 2.1 records without BibTeX input evidence do not satisfy the current schema. Recompile and actually review rather than backfilling fields or changing a version string. DEMO collection is isolated with `--allow-demo`; it never makes the production paper gate accept DEMO data.

File hashes, declarations and even tool-reference strings can be edited. Audits check coverage/current files and recorded provenance; they do not prove cognition, aesthetic quality or authentic harness execution. Actual viewing tool calls and meaningful judgment are mandatory. No real contest yet: build/review the gallery and exercise explicitly labeled isolated DEMO data; do not invent a contest plan. Test Claude path/configuration separately from actually running Claude Code, and label the distinction.
