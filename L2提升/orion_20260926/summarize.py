"""Summarize saved local Q3 refinements. No solves or evaluator calls.

Run: python -m L2提升.orion_20260926.summarize --run-root PATH
Writes summary.json, summary.csv, attempts.csv and SUMMARY.md inside PATH.
Use --print-only to inspect the JSON summary without writing files.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import statistics
from pathlib import Path


def load(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        return json.load(stream)


def equal_files(left, right):
    return left.is_file() and right.is_file() and load(left) == load(right)


def response_check(path, expected):
    response = load(path)
    return bool(expected is not None and response and response.get('status') == 'ok'
                and response.get('official_result', {}).get('makespan') == expected
                and response.get('audit', {}).get('ok') is True
                and not response.get('audit', {}).get('errors'))


def ratio(a, b):
    return a / b if a is not None and b else None


def delta(a, b):
    return a - b if a is not None and b is not None else None


def stop_reason(state, execution, request):
    explicit = state.get('search_stop_reason') or state.get('stop_reason')
    if explicit:
        return explicit, 'recorded'
    reason = execution.get('reason')
    if reason in ('job_wall_limit', 'experiment_deadline', 'worker_error', 'not_started_deadline'):
        return reason, 'recorded execution reason'
    if state.get('status') == 'failed':
        return state.get('reason', 'failed'), 'recorded'
    attempts = state.get('attempts', [])
    search_limit = request.get('seconds', 120) - max(15, request.get('seconds', 120) * .2)
    candidates = [a for a in attempts if a.get('family') not in ('seed', 'pair')]
    before_final = [a for a in attempts if a.get('name') != 'final_same_plan_no_l2']
    if len(before_final) >= request.get('calls', 64) - 1:
        return 'call_cap', 'inferred from recorded calls; one final-pair slot reserved'
    if any(a.get('completed_seconds', a.get('started_seconds', 0)) >= search_limit for a in candidates):
        return 'search_time_limit', 'inferred from recorded attempt completion times'
    final_pair = next((a for a in attempts if a.get('name') == 'final_same_plan_no_l2'), {})
    if final_pair.get('started_seconds', 0) >= search_limit:
        return 'search_time_limit', 'inferred from final-pair start at/after search deadline; includes generation time'
    if state.get('status') in ('complete', 'partial') and state.get('elapsed_seconds', 0) < search_limit:
        return 'source_exhausted_or_no_further_improving_epoch', 'inferred; round1 did not record exact generator exhaustion'
    return 'unknown', 'not recorded; no extra profiling performed'


def summarize(root):
    protocol = load(root / 'PROTOCOL.json', {})
    exit_record = load(root / 'RUN_EXIT.json', {})
    rows, attempts_out = [], []
    family = collections.defaultdict(collections.Counter)
    errors = []
    for job in sorted((root / 'jobs').iterdir()):
        if not job.is_dir():
            continue
        request = load(job / 'request.json', {})
        state = load(job / 'result.json') or load(job / 'progress.json', {})
        execution = load(job / 'execution.json', {})
        attempts = state.get('attempts', [])
        base, base2 = state.get('baseline') or {}, state.get('baseline_no_l2') or {}
        best, pair = state.get('best') or {}, state.get('pair') or {}
        raw = state.get('raw_candidate_best') or {}
        seed_attempt = next((a for a in attempts if a.get('family') == 'seed' and a.get('q') == 3), {})
        base_pair_attempt = next((a for a in attempts if a.get('name') == 'baseline_same_plan_no_l2'), {})
        seed_plan = root / 'seeds' / request.get('case', state.get('case', '')) / 'plan.json'
        seed_plan_equal = bool(seed_attempt.get('plan_file') and equal_files(seed_plan, job / seed_attempt['plan_file']))
        seed_verified = bool(seed_plan_equal and seed_attempt.get('status') == 'ok'
                             and seed_attempt.get('makespan') == request.get('prior_makespan') == base.get('makespan')
                             and response_check(job / seed_attempt['result_file'], base.get('makespan')))
        baseline_pair_equal = bool(base_pair_attempt.get('plan_file')
                                   and equal_files(seed_plan, job / base_pair_attempt['plan_file']))
        baseline_pair_verified = bool(seed_verified and baseline_pair_equal
                                      and base_pair_attempt.get('status') == 'ok'
                                      and response_check(job / base_pair_attempt['result_file'], base2.get('makespan')))
        pair_equal = equal_files(job / 'best_plan.json', job / 'same_plan_no_l2_plan.json')
        best_verified = response_check(job / 'best_response.json.gz', best.get('makespan'))
        pair_verified = bool(pair_equal and best_verified and state.get('pair_status') == 'ok'
                             and response_check(job / 'same_plan_no_l2_response.json.gz', pair.get('makespan')))
        seed_q3 = base.get('makespan') if seed_verified else None
        seed_q2 = base2.get('makespan') if baseline_pair_verified else None
        best_q3 = best.get('makespan') if best_verified else None
        best_q2 = pair.get('makespan') if pair_verified else None
        seed_gain = delta(seed_q2, seed_q3)
        final_gain = delta(best_q2, best_q3)
        stop, stop_evidence = stop_reason(state, execution, request)
        status = state.get('status', 'not_started' if execution.get('reason') == 'not_started_deadline' else 'missing')
        if execution.get('reason') in ('job_wall_limit', 'experiment_deadline') and status == 'running':
            status = 'interrupted_with_incumbent' if best_verified else 'interrupted_no_legal_result'
        row = dict(
            case=request.get('case', state.get('case')), arm=request.get('arm', state.get('arm')),
            version=request.get('version', state.get('version')), status=status,
            execution_reason=execution.get('reason'), seed_Q3=seed_q3, seed_Q2=seed_q2,
            best_Q3=best_q3, best_Q2=best_q2,
            improvement_percent=100 * (1 - best_q3 / seed_q3) if seed_q3 and best_q3 is not None else None,
            seed_same_plan_cache_ratio=ratio(seed_q2, seed_q3), best_same_plan_cache_ratio=ratio(best_q2, best_q3),
            seed_cache_saved_cycles=seed_gain, final_cache_saved_cycles=final_gain,
            no_l2_plan_delta_cycles=delta(seed_q2, best_q2), cache_saved_delta_cycles=delta(final_gain, seed_gain),
            seed_cache_hit=base.get('cache_hit_rate'), best_cache_hit=best.get('cache_hit_rate'),
            seed_spill_bytes=base.get('spill_added_copy_bytes'), best_spill_bytes=best.get('spill_added_copy_bytes'),
            seed_added_copy_bytes=base.get('added_copy_bytes'), best_added_copy_bytes=best.get('added_copy_bytes'),
            official_calls=len(attempts), recorded_official_calls=state.get('official_calls'),
            official_seconds=sum(a.get('eval_seconds', 0) or 0 for a in attempts),
            eval_and_save_seconds=sum(a.get('eval_and_save_seconds', 0) or 0 for a in attempts),
            generation_seconds=sum(a.get('generation_seconds', 0) or 0 for a in attempts),
            wall_seconds=execution.get('wall_seconds', state.get('elapsed_seconds')),
            worker_elapsed_seconds=state.get('elapsed_seconds'),
            raw_candidate_Q3=raw.get('makespan'), raw_candidate_added_copy_bytes=raw.get('added_copy_bytes'),
            raw_candidate_family=raw.get('family'), best_family=best.get('family'), best_name=best.get('name'),
            seed_replay_verified=seed_verified, seed_plan_equal=seed_plan_equal,
            baseline_pair_verified=baseline_pair_verified, final_pair_verified=pair_verified,
            final_pair_plan_equal=pair_equal, pair_status=state.get('pair_status'),
            search_stop=stop, search_stop_evidence=stop_evidence,
            search_limit_seconds=request.get('seconds', 120) - max(15, request.get('seconds', 120) * .2),
            call_limit=request.get('calls'), job_limit_seconds=request.get('seconds'),
            source=f'jobs/{job.name}/result.json' if (job / 'result.json').exists() else f'jobs/{job.name}/progress.json',
        )
        row['candidate_calls'] = sum(a.get('family') not in ('seed', 'pair') for a in attempts)
        row['accepted_candidates'] = sum(bool(a.get('accepted')) for a in attempts if a.get('family') not in ('seed', 'pair'))
        row['late_legal_candidates'] = sum(a.get('status') == 'ok' and a.get('within_search_budget') is False for a in attempts)
        rows.append(row)
        previous = seed_q3
        for attempt in attempts:
            candidate = attempt.get('family') not in ('seed', 'pair')
            name = (row['arm'], attempt.get('family', 'unknown'))
            counter = family[name]
            counter['calls'] += 1
            outcome = attempt.get('status', 'unknown')
            if outcome == 'ok': counter['valid'] += 1
            elif 'timeout' in outcome or 'time_limit' in outcome: counter['timeout'] += 1
            elif outcome == 'running': counter['unfinished'] += 1
            else: counter['invalid_or_error'] += 1
            if attempt.get('accepted'): counter['accepted'] += 1
            if candidate and attempt.get('accepted') and previous is not None and attempt.get('makespan', previous) < previous:
                counter['strict_cycle_improvements'] += 1
            if candidate and attempt.get('accepted'): previous = attempt.get('makespan', previous)
            counter['official_seconds'] += attempt.get('eval_seconds', 0) or 0
            counter['generation_seconds'] += attempt.get('generation_seconds', 0) or 0
            flat = {k: v for k, v in attempt.items() if k != 'pipe_busy'}
            flat.update(case=row['case'], arm=row['arm'], version=row['version'], job_status=status)
            attempts_out.append(flat)
        errors.extend(dict(case=row['case'], arm=row['arm'], error=e) for e in state.get('errors', []))
        worker_error = load(job / 'worker_error.json')
        if worker_error: errors.append(dict(case=row['case'], arm=row['arm'], worker_error=worker_error))
    samples = []
    if (root / 'resources.jsonl').exists():
        for line in (root / 'resources.jsonl').read_text(encoding='utf-8').splitlines():
            if line.strip(): samples.append(json.loads(line))
    active_samples = [s for s in samples if s.get('active', 0) > 0]
    cpus = [s['cpu_fraction'] for s in active_samples if s.get('cpu_fraction') is not None]
    resources = dict(samples=len(samples), active_samples=len(active_samples),
                     active_max=max([s.get('active', 0) for s in samples] or [0]),
                     active_mean=statistics.mean([s.get('active', 0) for s in active_samples]) if active_samples else None,
                     target_max=max([s.get('target_workers', 0) for s in samples] or [0]),
                     cpu_active_mean=statistics.mean(cpus) if cpus else None, cpu_peak=max(cpus) if cpus else None,
                     available_ram_min_gib=min([s['available_bytes'] / 2**30 for s in samples if 'available_bytes' in s] or [0]))
    by_arm = {}
    for arm in sorted({r['arm'] for r in rows}):
        rr = [r for r in rows if r['arm'] == arm]
        values = [r['improvement_percent'] for r in rr if r['improvement_percent'] is not None]
        by_arm[arm] = dict(jobs=len(rr), status_counts=dict(collections.Counter(r['status'] for r in rr)),
                           seed_verified=sum(r['seed_replay_verified'] for r in rr),
                           pairs_verified=sum(r['final_pair_verified'] for r in rr),
                           improved=sum(r['improvement_percent'] > 0 for r in rr if r['improvement_percent'] is not None),
                           tied=sum(r['improvement_percent'] == 0 for r in rr if r['improvement_percent'] is not None),
                           worse=sum(r['improvement_percent'] < 0 for r in rr if r['improvement_percent'] is not None),
                           mean_improvement_percent=statistics.mean(values) if values else None,
                           official_calls=sum(r['official_calls'] for r in rr), official_seconds=sum(r['official_seconds'] for r in rr),
                           stop_counts=dict(collections.Counter(r['search_stop'] for r in rr)))
    keys = [(r['case'], r['arm']) for r in rows]
    return dict(schema=1, scope='fixed-case local Q3 refiners, not full SMFB or a 100-graph run',
                protocol=protocol, run_exit=exit_record, resources=resources, by_arm=by_arm,
                duplicate_case_arm_keys=[list(k) for k, count in collections.Counter(keys).items() if count > 1],
                rows=rows, families=[dict(arm=k[0], family=k[1], **v) for k, v in sorted(family.items())], errors=errors), attempts_out


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)


def fmt(value, digits=3):
    return '缺失' if value is None else (f'{value:.{digits}f}' if isinstance(value, float) else str(value))


def markdown(summary):
    protocol = summary['protocol']
    lines = ['# Q3/L2 小批次本轮结果', '',
             '本报告由保存的真实官方响应、请求、attempts 和资源日志生成；没有调用求解器或评估器。', '',
             f"固定案例：{', '.join(str(x) for x in protocol.get('cases', []))}；Q3/五核，最多 {protocol.get('workers')} workers。"
             f"每作业 {protocol.get('seconds')} 秒、最多 {protocol.get('calls')} 次官方调用，起点和最终同方案 Q2 回放均计入。",
             f"本轮总墙钟 {fmt(summary['run_exit'].get('wall_seconds'))} 秒。", '',
             '各臂都是在同一份既有强方案上做局部 Q3 改进，并非完整 SMFB 搜索。'
             '本次六图是机制诊断样本，没有运行 100 图；结果不证明全局最优，也不代表总体均值。', '',
             '| 臂 | 作业 | 起点新回放验证 | 最终同plan配对 | 改善/持平/变差 | 官方调用 | 官方秒数之和 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for arm, data in summary['by_arm'].items():
        lines.append(f"| {arm} | {data['jobs']} | {data['seed_verified']} | {data['pairs_verified']} | "
                     f"{data['improved']}/{data['tied']}/{data['worse']} | {data['official_calls']} | {data['official_seconds']:.3f} |")
    lines += ['', '官方秒数是各次评价自身 `eval_seconds` 求和；并行作业的和不等于整轮墙钟。'
              '单作业墙钟取 `execution.wall_seconds`，包含读取、构造、评价、保存和配对。', '',
              '| 图 | 臂 | 状态 | 起点 Q3/Q2 | 最终 Q3/Q2 | Q3下降% | 最终同plan L2比 | hit | Spill | addedCOPY | calls | 墙钟秒 | raw候选Q3 |',
              '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in summary['rows']:
        lines.append(f"| {r['case']} | {r['arm']} | {r['status']} | {fmt(r['seed_Q3'])}/{fmt(r['seed_Q2'])} | "
                     f"{fmt(r['best_Q3'])}/{fmt(r['best_Q2'])} | {fmt(r['improvement_percent'])} | {fmt(r['best_same_plan_cache_ratio'],6)} | "
                     f"{fmt(r['best_cache_hit'],6)} | {fmt(r['best_spill_bytes'])} | {fmt(r['best_added_copy_bytes'])} | "
                     f"{r['official_calls']} | {fmt(r['wall_seconds'])} | {fmt(r['raw_candidate_Q3'])} |")
    lines += ['', 'hit 是官方命中字节率（0..1）。raw 候选列排除种子，只包含搜索时限内真实评价的合法候选；'
              '未优于 incumbent 的候选仍报告。缺合法新候选时留空，不把保留种子冒充新方法改善。', '',
              '## 同方案核对与描述性差分', '',
              '起点须通过本次 Q3 重新评价，周期等于 prior_makespan，且 attempt plan 与保存种子 JSON 对象相同。'
              '起点 Q2 同样检查方案对象与原响应；最终检查 best_plan 与 same_plan_no_l2_plan 对象相等、'
              '两份官方响应 status/audit 和 makespan 一致。核查不使用哈希。核对不通过的配对数值不用于收益计算。', '',
              '| 图 | 臂 | 起点缓存节省周期 | 最终缓存节省周期 | 无L2方案变化周期 | 缓存节省差周期 |',
              '|---|---|---:|---:|---:|---:|']
    for r in summary['rows']:
        lines.append(f"| {r['case']} | {r['arm']} | {fmt(r['seed_cache_saved_cycles'])} | {fmt(r['final_cache_saved_cycles'])} | "
                     f"{fmt(r['no_l2_plan_delta_cycles'])} | {fmt(r['cache_saved_delta_cycles'])} |")
    lines += ['', '起点缓存节省=seedQ2−seedQ3；最终缓存节省=bestQ2−bestQ3；无L2方案变化=seedQ2−bestQ2。'
              '恒等式 seedQ3−bestQ3 = (seedQ2−bestQ2) + [(bestQ2−bestQ3)−(seedQ2−seedQ3)] 仅是描述性代数分解。'
              '两部分不是独立因果效应：改变方案会同时改变依赖、带宽竞争与缓存访问时序。', '',
              '## 候选来源与退出原因', '',
              '| 臂 | 来源 | 调用 | 合法 | 非法/错误 | 显式超时 | 未结束 | 接受 | 严格周期改善 |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for f in summary['families']:
        lines.append(f"| {f['arm']} | {f['family']} | {f.get('calls',0)} | {f.get('valid',0)} | {f.get('invalid_or_error',0)} | "
                     f"{f.get('timeout',0)} | {f.get('unfinished',0)} | {f.get('accepted',0)} | {f.get('strict_cycle_improvements',0)} |")
    lines += ['', 'seed/pair 单列，接受种子不计为新候选改善；未结束调用不能当成已成功评价。', '',
              '| 图 | 臂 | 搜索退出判定 | 依据 | 搜索上限秒 | 单项/调用上限 |', '|---|---|---|---|---:|---|']
    for r in summary['rows']:
        lines.append(f"| {r['case']} | {r['arm']} | {r['search_stop']} | {r['search_stop_evidence']} | "
                     f"{r['search_limit_seconds']} | {r['job_limit_seconds']}s / {r['call_limit']} |")
    lines += ['', '原 runner 若未写精确停止原因，本表明确标注推断：调用达到 calls−1 表示预留最终配对槽后的搜索调用上限；'
              '候选完成时刻跨过搜索截止表示时间上限；提前结束且没有触及时限/调用上限表示来源耗尽或无进一步改进的 epoch。'
              '不把这种提前停止写成用满 96 秒或 64 次评价。', '', '## 资源与局限', '',
              '资源来自 resources.jsonl 的现场采点，不是另跑性能基准：', '',
              f"- {json.dumps(summary['resources'],ensure_ascii=False)}",
              f"- 状态分布：{json.dumps({k:v['status_counts'] for k,v in summary['by_arm'].items()},ensure_ascii=False)}",
              f"- 重复 case/arm 键：{summary['duplicate_case_arm_keys']}；运行错误条数：{len(summary['errors'])}。", '',
              'cpu_active_mean/cpu_peak 使用 active>0 且 CPU 非空的样本；active_mean 同样只取运行时采点，'
              'RAM 是全机可用内存。保存原始 attempts/response/日志，不对未完成结果补造分数。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--print-only', action='store_true')
    args = parser.parse_args()
    summary, attempts = summarize(args.run_root)
    if args.print_only:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    (args.run_root / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(args.run_root / 'summary.csv', summary['rows'])
    write_csv(args.run_root / 'attempts.csv', attempts)
    (args.run_root / 'SUMMARY.md').write_text(markdown(summary), encoding='utf-8')
    print(json.dumps(dict(run_root=str(args.run_root), by_arm=summary['by_arm'], resources=summary['resources']), ensure_ascii=False))


if __name__ == '__main__':
    main()
