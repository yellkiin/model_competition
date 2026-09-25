# Primary literature read for Anytime Wu

Repository reading order: `调研/A题_文献库/README.md`, `方法对照与阅读顺序.md`, and `调研/A题_文献.json`. The actual original DOCX and unchanged official Q3 source were read, rather than relying on earlier reports.

## A12 — Zheng et al., Ansor, OSDI 2020

Read PDF pp.9–10 (printed pp.870–871), sections 5.2 and 6, including the task-allocation formulation and the initial round-robin exploration before gradient-based allocation. Original: https://www.usenix.org/system/files/osdi20-zheng.pdf .

Transferred: distinguishing end-to-end value from isolated component improvement, family-first exploration, local measured evaluation costs, and historical improvement evidence. Our selector uses finite candidate queues, shrinkage calibration and an acquisition heuristic. It does NOT implement Ansor's learned boosting model or its gradient-descent task scheduler. Tensor tiling/fusion/code generation and a sum-of-subgraph latency objective are not substituted for the official multicore Makespan.

## A40 — A cache-aware DAG scheduling method on multicores: Exploiting node affinity and deferred executions, 2025

Read PDF pp.4–5 (printed pp.3–4), system/task model and cache reuse profile. Original: https://eprints.whiterose.ac.uk/id/eprint/225201/1/JSA24_Cache_aware_DAG.pdf .

Important mismatch: the paper assumes inclusive L1/L2, **LRU** and periodic DAG releases. The competition's read-only shared cache uses **FIFO**, issue-time lookup and completion-time fill. We only borrow the idea that reuse timing and resource competition must be considered jointly. No LRU distance model, dispatch to a busy core, artificial waiting, or sleep/delay command is introduced. Legal work-before-reader rearrangements change natural issue times within the existing official interface.

## A16 — Li, Gupta, Malik, COSMA, 2023

Read pp.3–4, section III's operator schedule and tensor create/preserve/spill/retrieve formulation. Original: https://arxiv.org/pdf/2311.18246 .

Transferred as an explanation constraint: memory events have lifetimes and must not be reduced to a hit-rate scalar. COSMA jointly controls scratchpad addresses and replacement. Those freedoms do not exist in our plan interface, so neither an ILP memory allocator nor a replacement-policy modification is claimed here.

## A17 — Ahn et al., Ordering Chaos / SERENITY, 2020

Read local original PDF pp.4–5, dynamic-programming scheduling and Algorithm 1. It allocates the new activation before releasing completed predecessors and remembers the best peak-memory partial schedule.

Transferred: respect topological dependencies and distinguish partial order from the selected execution. We do not reimplement its DP, use ready-set signatures as new optimality certificates, or optimize memory allocation in this track. Actual memory/Pipe dependencies remain the unchanged official evaluator's responsibility.

## A33 — Satish, Ravindran, Keutzer, decomposition-based constraint scheduling, 2007

Read local original pp.2–3, master/subproblem separation and cycle-derived constraints. The source learns SAT constraints and provides exact finite-model optimization.

Transferred only the separation of candidate proposal and validation. Our exact plan-equality duplicate removal and official candidate-bound pruning are NOT a Benders/SAT implementation, and a stagnant finite heuristic queue is NOT proof of optimality.

## Evidence boundaries

Fixed-observation criticality freezes the durations measured in one real official run. It includes original dependency, memory/Pipe-order and cross-copy arcs, but it is not a counterfactual simulation of the shared DDR queue. A zero-slack cached read does not by itself prove that making it miss would increase Makespan by its standalone latency. Exact cache gain is always the same Q3-selected plan evaluated again in Q2/no-L2.


## Structural continuation literature mapping (2026-09-25)

The new private-island micro-wave is not copied from a single paper. It combines only mechanisms that remain legal under the official evaluator:

- **A02 / A39:** acyclic grouping and component/hyperedge structure motivate keeping independent compute islands closed while changing legal grouping/mapping candidates.
- **A16 COSMA:** create/preserve/spill reasoning motivates bounding the number of simultaneously opened islands by live L1/UB bytes. We do not use COSMA's address placement, free reordering, or explicit swap decisions.
- **A42:** bounded local refinement and multiple candidate families motivate treating the structural wave as one proposal family inside the Anytime controller rather than as a replacement objective.
- FIFO cache behavior still comes exclusively from the official problem-3 event semantics. CADE/LRU-style reuse distance is not used as a cache model.

Measured evidence and same-plan Q2/Q3 controls are in `results/anytime_structural_20260925/`.
