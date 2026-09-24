# ORION structure track method

This directory is additive. It imports the current ORION implementation and never edits the public solver, campaign, official graphs, config, or official evaluator.

## Scope

The track studies only structural decisions: large connected blocks, critical dependencies, load balance, and effective core count. It deliberately does not replace the memory/FIFO tracks or build a global budget controller.

## Candidate families

1. **Non-uniform phase partition**
   - Compute DAG depth and width by depth.
   - Cut at width turning points rather than forcing a fixed number of equal bins.
   - Split induced intervals by weak component, which preserves a forward quotient order.
   - Map groups with the existing rank/EFT-style mapper and optionally pack groups that share phase/core.

2. **Linear-chain contraction + rank/EFT mapping**
   - Contract only degree-one producer/consumer chains.
   - This keeps strongly serial local structure together while exposing parallel chains.
   - The official evaluator, not the proxy, decides whether extra communication is worth the parallelism.

3. **Effective-core sweep**
   - Build legal plans using every active core count from 2 to n-1 and append empty schedules to reach target n.
   - This follows the official plan format: the outer list has n core schedules, but an individual schedule may be empty.
   - It is a generic family; case IDs never appear in the algorithm.

4. **Critical-affinity local moves**
   - Around a validated incumbent, rank cross-core group dependencies using compute-path slack plus tensor-byte context.
   - Propose producer-to-consumer, consumer-to-producer, and pair-joint migrations.
   - Rebuild per-core group lists in a legal global topological order.
   - The score is only candidate ordering; all accepted numbers come from the unchanged official evaluator.

## Important evidence-driven rules

- A single weakly connected component is not treated as proof of seriality. Case 016 is one component but its formal q2/n5 plan puts all 17,995 compute ops on one core; new legal partitions reduce q2 from 7,715,523 to about 2.1M cycles.
- More target cores are not assumed to be better. Case 044 proves that a validated three-active-core plan, padded to five schedules and re-evaluated as n=5, keeps 45,343 cycles versus the formal five-active-core 67,069.
- A lower bound is not a target. Case 048 has a 75,960 compute-path lower bound; structural changes improve the plan, but the remaining gap is not claimed to be fully removable.
- Near-bound cases are controls. Case 059 q2/n5 is about 1.02x its lower bound and the structure track does not improve it in the cold paired gate.

## Selection

The plugin only proposes candidates. The runner uses the unchanged official evaluator and legality audit for every selected plan. Failure, timeout, and no-improvement outcomes are retained.
