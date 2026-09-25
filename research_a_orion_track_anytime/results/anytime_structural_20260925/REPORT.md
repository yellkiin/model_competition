# Anytime structural/FIFO small-sample validation — 2026-09-25

All new scores below are from the unchanged official evaluator on the original graph/config. Day01 values are accepted as the baseline per the user request; they were not re-run. Final selection is incumbent-safe: a failed or slower proposal never replaces the verified seed.

|case|day01 Q3 n5|new Q3 n5|change|same-plan Q2 no-L2|cache-only change|
|---|---:|---:|---:|---:|---:|
|024|2,227,340|2,216,206|-0.500%|2,218,866|-0.120%|
|044|46,827|44,768|-4.397%|81,944|-45.368%|
|083|181,091|180,934|-0.087%|215,505|-16.042%|
|084|391,700|285,686|-27.065%|285,686|-0.000%|
|086|48,028|47,682|-0.720%|54,336|-12.246%|

Across these five improved Q3 cases plus controls 001 and 059, the arithmetic mean of `day01/new` is **1.06146** and the geometric mean is **1.05483**. This is a small-sample continuation aggregate, not a 100-graph benchmark.

## New structural rule

`private_island_micro_wave_e2_s2` activates without case IDs when the graph has at least 8 weak compute components, >=75% of ops in components of <=32 ops, external inputs are overwhelmingly component-private, and the incumbent is still >8% above the global lower bound. It keeps each independent component closed, balances whole components by pipe work, and opens only a capacity-sized micro-wave before advancing to the next stage.

On case 084 this rule detected 1077 independent micro-components and reduced Q2/Q3 n5 from 391,700 to 285,686 in the selected candidate. The exact selected Q3 plan has Q2=Q3=285,686 and zero Q3 hits, so this gain is structural scheduling rather than cache credit.

## Budget rule evidence

Case 059 Q3 n5 stopped at the verified 150,524 seed with zero additional official evaluations because `(U-L)/U` is about 1.97%, under the v4 near-bound budget threshold.

## Literature connection

The private-island rule uses A02/A39-style acyclic/component structure only as a proposal representation, A16-style live-memory/spill reasoning to size the open wave, and A42-style bounded local refinement. None of those paper objectives replaces the official makespan. The third-question FIFO logic remains based on the official issue-time lookup / completion-time fill semantics; LRU-oriented cache papers are not used as a scoring model.

## Scope

This is a warm-start continuation study, not a 100-graph cold-start replacement claim. The algorithm does not branch on case ID; the case list appears only in this experiment report. Q3 no-L2 controls above re-evaluate the exact selected Q3 plan under Q2 semantics. Raw selected plans and complete official responses are preserved in the conversation delivery archive instead of being re-encoded as opaque repository payloads.
