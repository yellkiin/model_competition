# Shard 0: frozen trident-1.3, incomplete Windows execution

Branch: `integration/orion-trident-publish-20260925`.
Pre-run `git rev-parse HEAD`: `489ec93a4c74683679e6a87a0175e4b8a3e3bbe1`.
The frozen runtime and official evaluator were not edited or updated.
Python: existing CPython 3.12.8 x64, Windows 11, host Nuggets. The requested D-drive interpreter did not exist; the existing Program Files Python312 interpreter was selected with `-Python`.

Command: `& .\research_a_orion_trident\run_windows.ps1 -Python '<existing Python312 interpreter>' -ShardIndex 0 -FetchInputs -Seconds 600 -Hours 12`.
Exact local command and path are retained in the raw LAUNCH_RECEIPT.json.

## Actual outcome

The frozen launcher performed its two real official configurations and failed its gate. It did not admit the other 474 configurations. Campaign elapsed through process exit: 14.452 seconds. No extra round, budget reset, retries or source patch were applied.

| Configuration | Saved official Makespan | Reference | State |
|---|---:|---:|---|
| 002 Q1 / n2 | 130549 | 130549 | Complete; retained stronger reference |
| 002 Q3 / n2 | 127007 | 128272 | Partial worker error; legal improvement saved, no no-L2 pair |

The Q3 reduction is 0.9862% relative to its same-configuration reference. It is not a single-core speedup. No current Q0 denominator exists, so speedup and same-plan cache benefit remain missing.

476 main configurations: 1 complete, 1 partial with saved legal incumbent, 474 not started; 0 failures without incumbent. The partial job has an actual worker error. All 170 required Q3 no-L2 pairs are missing. The standard report's `successful_main=2` counts saved legal outputs, not two fully completed jobs; use SHARD_0_COVERAGE.json for completion status. No time limit was reached.

## Concrete failure

`solve.py:222 -> save -> persist -> io.py:22 -> tmp.replace(p)` raised `PermissionError: [WinError 5]` while replacing Q3 `progress.json.tmp` with `progress.json`. Exact traceback and error JSON remain in raw records. File sharing/locking is a plausible explanation, but the responsible process and cause were not observed. No other process was terminated. A failed temporary write is copied as `failed_uncommitted_progress_tmp.json` only to preserve error evidence; it was not promoted to saved progress or used to improve reported scores.

The frozen gate requires the Q3 same-plan pair. Bypassing that gate, editing persistence, or resetting this configuration's budget would change the requested execution. None was done. A future compatibility fix and a separately identified continuation require an explicit version/remaining-budget decision.

## Evidence and limits

The normal reporting function checked the two existing selected official timelines and exported paper_data, selected plans, candidate/source costs, COPY/Spill/cache, Pipe summaries and errors. It did not rerun the official evaluator or search. The actual run retained its normal official legality checks throughout.

Both jobs stopped before 30 seconds. Standard budget_prefixes contains event-derived zero-time values and later `stopped_hold` rows. Those later points describe holding the saved incumbent after termination, not new evaluations or observed continued search. No final values were filled into earlier time points. Unknown historical costs remain missing.

The standard report lists missing keys across the full 100-graph universe; this machine was assigned only the 34 frozen shard-0 cases. The shard-specific coverage file records exactly its 476 keys. Other shards were never started. No method-quality or mean-speedup conclusion can be drawn from this interrupted two-configuration run.
