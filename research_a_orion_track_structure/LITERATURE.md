# Literature basis for the structure track

The starting point is the repository's reviewed A-problem library and its method-order document, not a title-only keyword list.

- **A49 (2019), scalable clustering-based task scheduler**: motivates clustering/mapping as a joint communication-vs-parallelism problem. We transfer the clustering/mapping idea, but not its machine model or objective.
- **A39, multilevel acyclic hypergraph partitioning**: supports treating one tensor with a producer and multiple consumers as a shared communication object and preserving acyclicity through coarsening/refinement. Hyperedge connectivity is only a proxy here; official COPY timing is always re-evaluated.
- **A02, acyclic DAG partitioning**: supports acyclic coarsening, initial partitioning, and refinement. Edge cut/node weight are not substituted for official makespan.
- **A01 / HEFT**: provides rank/EFT-style list scheduling intuition for mapping exposed groups to heterogeneous resource timelines. The contest has multiple pipes/shared DDR, so the implementation uses it only as a candidate heuristic.
- **A08 / IOS**: supports non-uniform/topological-window grouping rather than treating every layer uniformly.
- **A42, local migration/refinement framework**: motivates small local reassignment windows around a validated incumbent. The implementation uses group/core migration and always sends the resulting plan through official legality and timing.
- **A33, decomposition-based constraint optimization**: supports decomposing structural construction from exact expensive scoring. We keep construction/proxy and official evaluation separate.

Files consulted before implementation:
- `调研/A题_文献库/README.md`
- `调研/A题_文献库/方法对照与阅读顺序.md`
- `调研/A题_文献.json`

This round does not claim to reproduce any paper algorithm verbatim.
