# 2026-09-24 structure-track real-data report

## What was actually run

Evidence was taken from the latest day01 combined tables, both final raw transfer archives, and fresh official re-evaluation. Fresh runs used the unchanged official evaluator and legality audit.

The first direct gate re-evaluated formal plans and structural candidates on real cases. A second isolated gate re-evaluated the formal case 044 Q2/n3 plan after appending two empty core schedules and treating it as n=5. A third run compared old ORION against the structure track on the same GitHub-hosted machine with the same 30-second per-arm budget, two workers, cases 016/024/044/048/059, Q1-Q3, and n=2/5.

## Main findings

### 016: not inherently serial; the formal plan simply uses one core

Fresh replay of formal Q2/n5: makespan 7,715,523; effective cores 1; compute ops [17,995,0,0,0,0]; PIPE_V work [7,714,975,0,0,0,0]; added COPY 0.

This directly falsifies the inference that one weakly connected component means no parallelism. Direct structural candidates reached 2,088,400 (Q2) and 2,086,586 (Q3). In the equal-budget cold gate, old Q2/n5 stayed at 7,715,523 while new reached 2,118,785; Q3/n5 was 7,715,523 vs 2,117,845. Both Q1/n2 and Q1/n5 timed out before the first official feasible evaluation at 30 s, so no Q1 cold-start win is claimed.

### 024: all five cores are active, but formal load is badly skewed

Fresh formal Q2/n5 replay: makespan 2,225,709; compute ops [1752,195,180,3661,171]; PIPE_V work [746352,87361,80012,1562197,78873].

The direct chain/rank candidate reached 695,284 cycles with 499,564 added-copy bytes. The equal-budget cold gate confirmed the effect: old 2,252,144 vs new 695,284 for Q2/n5, and old 2,250,914 vs new 693,470 for Q3/n5.

### 044: over-partitioning is real; fewer active cores are a valid target-n solution

Formal Q2 n3 is 45,343 cycles with 1,057,984 added-copy bytes. Formal Q2 n5 is 67,069 cycles with 2,839,040 added-copy bytes.

The exact formal n3 plan was padded with two empty core schedules and re-evaluated through the official Q2 evaluator as n=5: 45,343 cycles, effective cores 3, compute ops [527,465,372,0,0], audit_ok true. Relative to formal n5 this is a 32.394% makespan reduction.

The cold-start structure solver did not rediscover this strong plan in 30 s: both old and new ended at 69,095 for Q2/n5. The evidence therefore supports effective-core reuse/warm seeding, not a claim that the current cold constructor solves 044 by itself.

### 048: partly path-limited, but the partition still matters

The compute-path lower bound is 75,960. Formal Q2/n5 uses all five cores and scores 116,272 in the formal table. A chain/rank candidate reached 99,729 in the direct gate. The equal-budget cold gate gave old 117,600 vs new 99,581 for Q2/n5 and old 117,513 vs new 99,127 for Q3/n5.

So 048 is neither bad partition only nor unimprovable because of the critical path. Structural improvement is real, while the path bound explains why fivefold scaling is not a sensible target.

### 059 and 001: controls prevent overfitting

Case 059 Q2/n5 has a 147,558.4 lower bound and a formal 150,455 result. In the cold gate old and new both ended at 150,524. The new structural families do not improve it.

Case 001 has perfectly balanced replayed Q2/n5 pipe work across all five cores and the non-uniform packed candidate exactly reproduces the 47,502 formal score.

### 064: simple reconstruction is not automatically better

The direct structural candidates were worse than the formal selected solution, so the formal solution is retained. This is a useful negative result: later day01 refinement can beat a clean from-scratch structural reconstruction.

## Equal-budget cold gate

Selected 30-second examples:

| Case | Q | n | old | new | change |
|---|---:|---:|---:|---:|---:|
| 016 | 2 | 5 | 7,715,523 | 2,118,785 | -72.539% |
| 016 | 3 | 5 | 7,715,523 | 2,117,845 | -72.551% |
| 024 | 2 | 5 | 2,252,144 | 695,284 | -69.128% |
| 024 | 3 | 5 | 2,250,914 | 693,470 | -69.192% |
| 048 | 2 | 5 | 117,600 | 99,581 | -15.322% |
| 048 | 3 | 5 | 117,513 | 99,127 | -15.646% |
| 059 | 2 | 5 | 150,524 | 150,524 | 0% |
| 044 | 2 | 5 | 69,095 | 69,095 | 0% |

See per_case.csv for every arm. The 30/60/120/300 rows in trajectory.csv come from the same continuous run. Because this gate stopped each arm at 30 s, later rows are explicitly marked stopped_carry_forward; they are not backfilled with a later final value.

## Raw-history check

Both final transfer archives were reconstructed unchanged. For the selected cases the archive contains per-job plan, compressed official result, request, progress, and summary records. Raw records confirm, among other things, that case 059 reaches very small certified gaps early and that case 048 retains a 75,960 compute-path bound while mapping improves.

Fresh official replay is used for the numerical claims above, so this report does not depend on an old report's interpretation.

## Code changes

- effective-core candidate sweep covers every active count 2..n-1;
- critical cross-core group dependencies are ranked by path slack plus tensor-byte context;
- local generation includes producer-to-consumer, consumer-to-producer, and pair-joint migration;
- method remains case-ID agnostic;
- public ORION solver/campaign, graphs, config, and official evaluator are unchanged.

The 30-second paired gate validates the complete current plugin path. Not every winning solution is attributed specifically to the new critical-move family because earlier structural families may win first.

## Limits and next step

1. Q1 on 016 still has a first-feasible latency problem; neither arm produced a valid plan within 30 s.
2. 044 needs formal/warm effective-core seeding in routine experiments; cold construction did not recover 45,343.
3. Longer 60/120/300-second continuous runs should precede expansion to 100 graphs.
4. No lower bound is claimed to be reachable.
5. This is a representative gate, not a replacement 100-graph formal publication.
