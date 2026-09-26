"""Parse existing Q3/no-L2 response contents sequentially; no evaluator imports.

No inputs are changed. This checks saved evidence, not a new legality simulation.
Names and relative provenance are retained; no file fingerprints are computed.
"""
from __future__ import annotations
import argparse
import collections
import gzip
import json
import statistics
import time
from pathlib import Path

RUN_RELS = (
    'host0/records/run',
    'host1/records/research_a_orion_trident/runs/round01/shard_1',
    'host2/records/research_a_orion_trident/runs/round01/shard_2',
)
RECOVERY_REL = ('host1/records/research_a_orion_trident/runs/save_recovery_20260925/'
                'shard_1/attempt_001/jobs/case_049_q3_n1')
SELECTION_REL = ('host1/records/research_a_orion_trident/runs/save_recovery_20260925/'
                 'shard_1/SELECTED_RECOVERIES.json')


def read(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        return json.load(stream)


def verify_response(path, summary, question):
    result = {'present': path.is_file(), 'parsed': False, 'issues': []}
    if not result['present']:
        result['issues'].append('missing_response')
        return result
    try:
        wrapper = read(path)
        result['parsed'] = True
        official = wrapper.get('official_result', {})
        audit = wrapper.get('audit', {})
        result.update(status=wrapper.get('status'), audit_ok=audit.get('ok'),
                      audit_errors=audit.get('errors'), non_official=wrapper.get('non_official'),
                      makespan=official.get('makespan'), scene=official.get('scene'),
                      problem=official.get('problem'), num_cores=official.get('num_cores'))
        issues = result['issues']
        if wrapper.get('status') != 'ok': issues.append('wrapper_status_not_ok')
        if audit.get('ok') is not True or audit.get('errors') != []: issues.append('saved_audit_not_ok')
        if wrapper.get('non_official') is True: issues.append('non_official_response')
        if official.get('scene') != 'B': issues.append('scene_not_B')
        if official.get('num_cores') != summary['n']: issues.append('core_count_mismatch')
        expected = summary.get('makespan' if question == 3 else 'no_l2_makespan')
        if official.get('makespan') != expected: issues.append('summary_makespan_mismatch')
        if not isinstance(official.get('makespan'), (int, float)) or official['makespan'] <= 0:
            issues.append('missing_positive_makespan')
        config = {'bandwidth_bytes_per_cycle': 60, 'cross_core_copy_delay_cycles': 500}
        if question == 3:
            if official.get('problem') != 3 or official.get('cache_mode') != 'read_only':
                issues.append('q3_semantics_mismatch')
            config.update(cache_capacity_bytes=1048576, cache_bandwidth_bytes_per_cycle=250)
            if 'cache_stats' not in official or 'cache_events' not in official:
                issues.append('q3_cache_evidence_missing')
            stats = official.get('cache_stats', {})
            hb, mb = stats.get('hit_bytes'), stats.get('miss_bytes')
            if isinstance(hb, (int, float)) and isinstance(mb, (int, float)):
                rate = hb / (hb + mb) if hb + mb else 0
                result.update(cache_hit_bytes=hb, cache_miss_bytes=mb, cache_hit_rate=rate)
                if abs(stats.get('hit_rate', -1) - rate) > 1e-12: issues.append('cache_rate_inconsistent')
                if summary.get('cache_hit_rate') is not None and abs(summary['cache_hit_rate']-rate)>1e-12:
                    issues.append('summary_cache_rate_mismatch')
        else:
            if official.get('problem') not in (None, 2): issues.append('q2_problem_mismatch')
            if any(k in official for k in ('cache_mode', 'cache_events', 'cache_stats')):
                issues.append('no_l2_contains_cache_fields')
        result['config'] = {key: official.get(key) for key in config}
        for key, value in config.items():
            if key not in official: issues.append('config_field_missing:' + key)
            elif official[key] != value: issues.append('config_mismatch:' + key)
        result['saved_timeline_max'] = max((op['end'] for core in official.get('per_core_timeline', [])
                                           for op in core.get('ops', [])), default=None)
        if result['saved_timeline_max'] != official.get('makespan'):
            issues.append('timeline_makespan_mismatch')
        result['content_verified'] = not issues
    except Exception as exc:
        result['issues'].append('parse_or_schema_error:' + type(exc).__name__ + ':' + str(exc))
    return result


def verify_job(root, relative, provenance):
    job = root / relative
    row = dict(relative_job=relative, provenance=provenance, issues=[])
    try:
        summary = read(job / 'summary.json')
        row.update(case=summary['case'], n=summary['n'], summary_status=summary.get('status'),
                   summary_pair_status=summary.get('pair_status'), version=summary.get('version'))
        if summary.get('q') != 3: row['issues'].append('summary_q_not_3')
        if summary.get('status') != 'ok': row['issues'].append('summary_status_not_ok')
        if summary.get('pair_status') != 'ok': row['issues'].append('summary_pair_not_ok')
        if summary.get('cache_overrides') not in (None, {}): row['issues'].append('cache_overrides_present')
        plans = [job/'plan.json', job/'same_plan_no_l2_plan.json']
        row['plans_present'] = [p.is_file() for p in plans]
        row['same_plan_json_equal'] = all(row['plans_present']) and read(plans[0]) == read(plans[1])
        if not row['same_plan_json_equal']: row['issues'].append('missing_or_unequal_pair_plan')
        row['q3'] = verify_response(job/'result.json.gz', summary, 3)
        row['no_l2'] = verify_response(job/'same_plan_no_l2_result.json.gz', summary, 2)
        row['pair_content_verified'] = (not row['issues'] and row['q3'].get('content_verified',False)
                                         and row['no_l2'].get('content_verified',False))
        if row['pair_content_verified']:
            row['cache_ratio'] = row['no_l2']['makespan']/row['q3']['makespan']
    except Exception as exc:
        row['issues'].append('job_read_error:' + type(exc).__name__ + ':' + str(exc))
        row['pair_content_verified'] = False
    return row


def totals(rows):
    return dict(jobs=len(rows), pairs_content_verified=sum(r['pair_content_verified'] for r in rows),
                parsed_responses=sum(r.get(k,{}).get('parsed',False) for r in rows for k in ('q3','no_l2')),
                q3_content_verified=sum(r.get('q3',{}).get('content_verified',False) for r in rows),
                no_l2_content_verified=sum(r.get('no_l2',{}).get('content_verified',False) for r in rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-raw',type=Path,default=Path(r'<LOCAL_RAW_ROOT>'))
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).parent)
    parser.add_argument('--seconds',type=float,default=240)
    args=parser.parse_args(); started=time.monotonic(); rows=[]
    jobs=[(str(path.parent.relative_to(args.local_raw)).replace('\\','/'),f'original_shard_{i}')
          for i,rel in enumerate(RUN_RELS) for path in sorted((args.local_raw/rel/'jobs').glob('*_q3_n*/summary.json'))]
    jobs.append((RECOVERY_REL,'authorized_recovery_case_049_n1'))
    selection=read(args.local_raw/SELECTION_REL)
    authorization=[r for r in selection.get('recoveries',[]) if r.get('key')=='case_049_q3_n1']
    authorized=(len(authorization)==1 and authorization[0].get('pair_status')=='ok'
                and authorization[0].get('recovery_job')=='attempt_001/jobs/case_049_q3_n1')
    for relative,provenance in jobs:
        if time.monotonic()-started>=args.seconds:break
        rows.append(verify_job(args.local_raw,relative,provenance))
        if len(rows)%50==0:print(json.dumps(dict(processed=len(rows),planned=len(jobs)),ensure_ascii=False),flush=True)
    original=[r for r in rows if r['provenance'].startswith('original_')]
    recovery=[r for r in rows if r['provenance'].startswith('authorized_')]
    selected=[r for r in original if (r.get('case'),r.get('n'))!=('case_049',1)] + (recovery if authorized else [])
    report=dict(scope='existing saved official response content checks; no evaluator, no new solve, no hashes',
                complete=len(rows)==len(jobs),elapsed_seconds=time.monotonic()-started,
                planned_jobs=len(jobs),processed_jobs=len(rows),original=totals(original),selected=totals(selected),
                recovery_authorized=authorized,recovery_selection_relative=SELECTION_REL,
                selection_rule=selection.get('selection_rule'),recovery_selection_record=authorization,
                limitations='Saved audit receipts are checked, not independently re-proved. No graph/config/evaluator is changed. Recovery never backfills original trajectories.',
                rows=rows)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'RAW_RESPONSE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# Q3/L2 已保存原始响应内容核查','',
           '只解析既有 JSON/gzip 官方响应、summary 和 plan。没有调用评估器，没有重算合法性，没有修改输入或补造文件。',
           '每项检查已保存 wrapper status/audit、Q3/Q2 语义、周期与 summary/时间线终点一致、配置字段、命中字节率，以及同方案 JSON 对象一致性。',
           '',f"处理状态：{'完整' if report['complete'] else '达到读取窗口，部分完成'}；{len(rows)}/{len(jobs)} 项；耗时 {report['elapsed_seconds']:.3f} 秒。",'',
           '| 口径 | 主键 | 解析响应 | 内容核对通过的配对 |','|---|---:|---:|---:|']
    for name,subset in [('原始三片',original),('纳入已授权 049/n1 接续',selected)]:
        t=totals(subset);lines.append(f"| {name} | {t['jobs']} | {t['parsed_responses']} | {t['pairs_content_verified']} |")
    lines+=['',f'049/n1 接续授权选择记录已读且匹配：{authorized}。',f'相对来源：`{SELECTION_REL}`。',
            f'接续数据：`{RECOVERY_REL}`。','原始记录独立保留；最终选择按已明确授权的故障续跑替换唯一键，不按各版本逐例最优混拼。',
            '该接续的早期轨迹不得回填至原轮；JSON 保留完整选择回执与每项相对来源。','',
            '## 未通过或缺失项目','']
    for row in rows:
        if not row['pair_content_verified']:
            issues=row['issues']+['Q3:'+x for x in row.get('q3',{}).get('issues',[])]+['no-L2:'+x for x in row.get('no_l2',{}).get('issues',[])]
            lines.append(f"- `{row['relative_job']}`：{'；'.join(issues)}")
    lines+=['','## 最终有来源的有效配对统计','',
            '| 核数 | 有效配对 | AM(no-L2/Q3) | 中位数 | 变快/相等/变慢 |','|---|---:|---:|---:|---|']
    for n in range(1,6):
        ratios=[r['cache_ratio'] for r in selected if r.get('n')==n and r['pair_content_verified']]
        if ratios:lines.append(f'| {n} | {len(ratios)} | {statistics.mean(ratios):.9f} | {statistics.median(ratios):.9f} | {sum(x>1 for x in ratios)}/{sum(x==1 for x in ratios)}/{sum(x<1 for x in ratios)} |')
    lines+=['','注意：这是保存证据的内容一致性核查，不等于重新运行官方合法性检查，也不验证本机各副本逐字相同；未使用哈希或文件指纹。','']
    (args.output_dir/'RAW_RESPONSE_AUDIT.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps({k:report[k] for k in ['complete','elapsed_seconds','processed_jobs','original','selected','recovery_authorized']},ensure_ascii=False))


if __name__=='__main__':main()
