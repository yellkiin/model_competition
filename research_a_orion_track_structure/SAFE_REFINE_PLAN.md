# Safe structure refinement — 2026-09-25

## Scope and frozen sources

Continue PR #30 findings without modifying that conflicted branch. This branch starts from main `996d7d11f10ac44ce65fcd361d5a057a5795c0f9`. The local official/public solver snapshot is the unchanged source exported at `e04b2bf5df946f48714c66ba84d61bd4b90ece00`; published structural helpers come from PR #29. No official graph, configuration, evaluator, shared solver/campaign, memory track, or anytime track is modified.

## What the guarantee means

Every job begins with an explicit existing target-question/target-core plan that is freshly re-evaluated. A complete official response and legality audit are required before replacing the incumbent. Failure, worse score, duplicate proposal, and timeout never erase this plan. This guarantees no regression relative to the supplied verified seed, not equality against an arbitrary cold solver given the same wall time.

Both old ORION continuation and the new structural continuation receive the same seed. The costed portfolio executes both and keeps the best validated plan. It charges both search costs and same-plan Q3/no-L2 replay costs. This is a warm portfolio, not a free per-case oracle or a new 100-case cold benchmark. Historical seed acquisition costs that cannot be fully traced remain unknown.

## Candidate mechanisms

- Re-evaluate smaller-core and cross-question saved plans in the target question after padding empty cores. Source scores are never copied into the target result.
- Preserve unaffected core orders and group IDs in single-group moves and pair swaps.
- Jointly migrate dependent groups, and refine a large block with acyclic prefix/suffix splits.
- Retain long communication-heavy chains, while trying communication-weighted rank/EFT mappings and fewer active cores.
- Cycle structural families without replacing the incumbent candidate; all proxy ranking is heuristic and all selected scores are official.

## Initial negative experiment

Real case 024 Q2 five-core naïve chain splitting was executed before the main protocol. Splitting into 2/1/3-operation chunks produced 1547896 / 4189611 / 1544634 cycles, far worse than the protected 695284-cycle plan. Large intermediate tensor traffic, not just load balance, matters. These failed trials and original responses are retained. The main policy does not force this fine splitting.

## Bounded experiments

1. Pilot: 044 and 064, questions 1/2/3, five cores, old/safe with the same validated seed, 120 seconds per arm and 64 evaluation cap, total 900 seconds.
2. Main small sample: 001/016/024/044/048/059/064, questions 1/2/3, five cores, 300 seconds per arm and 128 evaluation cap, total 1800 seconds. Parent observers enforce wall limits. Lower checkpoints are from the same trajectory; later points explicitly carry stopped incumbents.
3. Linux Python 3.13.5 CPU-only. Worker count is chosen from available CPU/memory at startup and held fixed for comparison blocks; it is not an NPU core count and not a claimed runtime autoscaler.

No tests, smoke runs, fingerprints, or whole-repository audit are added. Existing official legality checks stay enabled. No automatic merge or contest submission.

Completion status and exact measured outcomes are reported separately after inspecting the new raw outputs. Merely creating this plan file does not assert that the full protocol completed.
