# LOCAL_AGENT_PROMPT

Continue Problem A ORION structure track on a complete yellkiin/model_competition checkout. Do not modify shared research_a_orion_anytime/solver.py, campaign.py, official graphs, config, or evaluator.

## Environment

Windows priority:
- Python: D:\\python\\python.exe
- Python 3.12.x
- CPU-only
- workers: auto; process workers are not contest NPU core count.

Do not run hash/fingerprint tests, smoke tests, pytest/unittest, or a full-repository audit. Check only paths needed to launch the real experiment. Keep the official evaluator and legality audit unchanged.

## Next small batch

Run 016,024,044,048,064,059; Q1-Q3; 2 and 5 NPU cores; same-machine old/new; one continuous 120-second arm:

PowerShell command:

& 'D:\\python\\python.exe' -m research_a_orion_track_structure.run --cases 016,024,044,048,064,059 --questions 1,2,3 --cores 2,5 --seconds 120 --wall-seconds 5400 --max-evaluations 32 --workers auto --out research_a_orion_track_structure/results/local_120s

If case 016 Q1 still has no first feasible solution by 120 s, optimize first-feasible structural construction/evaluation latency before increasing the budget again.

## 044 warm effective-core check

Take the formal plan plans/q2/n3/case_044_multicore_res.json from research_a_orion_anytime/team_results/day01/combined_final/selected_plans.zip and register it as a warm seed whose target_n is 5. The runner must pad empty schedules and call the official evaluator at target n=5. Never copy 45,343 directly into an n5 table.

## Expansion gate

Expand to three-machine sharding only if:
- 016/024/048 gains remain stable;
- 059 does not regress materially;
- the 044 warm target-n replay remains legal and reproducible;
- failures/timeouts remain in the outputs.

For three machines, use one shared ordered case list plus --shards 3 and --shard-index 0/1/2. Do not run the full 100 graphs independently on all three machines.
