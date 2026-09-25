# Windows persistence correction, 2026-09-25

Base: PR38 `489ec93a4c74683679e6a87a0175e4b8a3e3bbe1`. Runtime label: `trident-1.3-win-save.1`.

The first shard-0 run stopped at the actual-case gate: Q3 case002/n2 raised WinError 5 while replacing progress.json. Only two workers were active; saved whole-system CPU samples were roughly 25–32%, so excessive concurrency is not established. The exact blocking reader is unknown.

Atomic JSON/gzip replacement now retries only Windows errors 5/32/33 for at most one second, with short capped backoff. The old destination is never deleted or rewritten in place. Persistent errors still propagate with the temporary file retained. Successful transient recoveries have a JSONL diagnostic. This time remains part of measured I/O and the original job deadline.

No solver strategy, official validation, graph, configuration, seed acceptance, resource reserve, or stopping criterion is changed. The campaign continuation option uses a new directory, copies the original batch clock, reuses completed jobs with explicit original-version provenance, and retries incomplete jobs only within the remaining per-configuration budget. Saved legal incumbents are retained through the existing validated-response mechanism. Prior cost and retry provenance are recorded; no trajectory is stitched into a single uninterrupted run.

The first complete Q1 case002/n2 is reused. Q3 case002/n2 retains 127007 and has 585.859 seconds remaining from its original 600-second cap. Shard 0 and the same prepared manifest remain fixed. The original failed run and publication are preserved. Validation is by these real official cases and the subsequent shard run; no smoke/unit/benchmark/fingerprint task is added.
