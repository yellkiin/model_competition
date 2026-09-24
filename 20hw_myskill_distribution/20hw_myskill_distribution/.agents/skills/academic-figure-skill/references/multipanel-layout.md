# Multi-Panel Layout & Anti-Redundancy

Principles for composing multiple panels into a single figure. Apply these before generating the adaptive layout in Step 4.

---

## 1. Anti-Redundancy: The Three-Tier Progression

Each panel must answer a **unique** question. Cover any panel with your hand — if the reader loses nothing, that panel is redundant.

| Tier | Question | Best Encoded As | Example |
|------|----------|-----------------|---------|
| **Overview** | "What is the overall pattern?" | Stacked bars, composition, total counts, overall distribution | Panel a: cell type composition across tissues |
| **Deviation** | "What makes each group unique?" | Z-score heatmap, diverging colormap, fold-change vs baseline | Panel b: Z-score deviation from pan-tissue mean |
| **Relationship** | "How do variables co-vary?" | Scatter/bubble, correlation, network edge weight | Panel c: immune infiltration vs tumor purity correlation |

Each tier encodes information **orthogonal** to the previous one. Overview shows absolute values. Deviation subtracts the overview to reveal group-specific signals. Relationship asks a co-variation question entirely.

### Redundancy Traps

| Trap | Example | The Fix |
|------|---------|---------|
| **Absolute + Absolute** | Panel a: stacked bar of %; Panel b: heatmap of the same % | Replace heatmap with Z-score deviation. Panel a = "what", panel b = "what's unusual" |
| **Subset of parent** | Panel a: all tumors ranked by size; Panel b: top-10 tumors (same ranking) | Replace panel b with tumor size vs immune infiltration scatter |
| **Two rankings** | Panel a: genes ranked by log2FC; Panel b: same genes by -log10(p) | Merge into one volcano plot, or turn one into pathway enrichment |
| **Different visual, same data** | Panel a: pie chart; Panel b: stacked bar of same composition | Choose one (stacked bar preferred for CNS). Use freed panel for relationship data |
| **Correlated axes** | Panel a: x vs y (r=0.9); Panel b: x vs z (r=0.85) | Show one scatter + correlation matrix heatmap for all pairwise |

### Redundancy Audit (run before finalizing layout)

For each pair of planned panels:
1. **Same data?** → Merge or replace one.
2. **Same question?** → Restructure to different questions.
3. **One derivable from the other?** → The derived panel is redundant.
4. **Removing one weakens the conclusion?** → If no, remove it.

A 3-panel figure with information-dense, non-redundant panels beats a 6-panel figure where 3 panels repeat information.

---

## 2. Hero Panel Principle

A 3–6 panel asymmetric figure needs one **hero panel**; equal-weight quantitative grids need not have one. The hero is — the panel with the strongest visual weight that anchors the reader's attention.

- **Size:** Derive area ratios from the selected reference and evidence hierarchy; 1.2–1.5 is only an example, not a requirement.
- **Position:** Top-left or center (the most visually prominent position)
- **Color:** Preserve semantic colors from the reference. Greater saturation is optional and must not change scientific meaning.
- **Content:** Carries the figure's core conclusion directly. If a reviewer looks at the hero panel for 3 seconds, they get the key message.

Supporting evidence may receive less area when justified, but shared quantitative semantics retain their colors and scales. Equal-weight comparisons may remain symmetric.

---

## 3. Narrative Ordering

Panels are read left-to-right, top-to-bottom. The panel order IS the story.

### Rules

1. **Order by scientific narrative.** A schematic-led figure can lead with the model only after the separate structural truth gate passes. Do not mechanically force data-first order.
2. **Discovery before validation.** Screening results go before follow-up validation.
3. **Less complex before more complex.** Simple bar chart at (a), dense heatmap at (d). Readers build visual literacy panel by panel.
4. **Shared-axis panels adjacent.** If panels (b) and (c) share y-axis range, place them side-by-side.
5. **Self-contained groups.** If panels (a-c) form a discovery group and (d-f) a validation group, visually group them (top row = discovery, bottom row = validation).

### Narrative Check

After laying out panels, ask: "If a reviewer reads only the panel labels (a, b, c...) and glances at each panel for 2 seconds, do they understand the main message?" If no, reorder.

---

## When to Load

Load this file when composing multi-panel figures (2+ panels). Apply anti-redundancy audit before generating the adaptive layout. Apply hero panel and narrative ordering during layout design.
