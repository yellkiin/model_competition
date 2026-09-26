PR title:
refactor(figures): redesign engraved workflow and add reusable ink-engraving style agent

PR body:
## Summary
- redesign the editable workflow figure in `paper_a_figures/engraved_workflow/ink_v2`
- introduce low-saturation ink-wash color themes while preserving the engraved black-and-white structure
- rebuild module connectors into a clear main process lane plus outer feedback lane
- move the right-bottom objective block back into clean whitespace and keep the `C_q` formula unobstructed
- add a reusable figure-style agent in `paper_a_figures/ink_engraving_agent` for future workflow and data figures
- export editable SVG, PDF and PNG assets for four coordinated themes

## Included assets
- editable workflow SVGs: `workflow_qinglu/qianjiang/yanlan/mono.svg(.svgz)`
- rendered exports: PDF, PNG, preview PNG
- palette sheet and style playbook
- matplotlib styling adapter (`style.py`) and examples
- source alignment, references and local review notes

## Notes
- this PR only updates the workflow figure system and reusable styling tools
- it does not change experiment data, solver code or other paper figures
- all assets remain editable; text stays as vector text in SVG/PDF
