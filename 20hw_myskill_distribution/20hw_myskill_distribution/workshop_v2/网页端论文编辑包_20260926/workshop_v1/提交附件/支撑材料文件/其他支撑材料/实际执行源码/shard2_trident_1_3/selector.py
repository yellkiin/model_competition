"""Work-aware warmup and bounded cost-normalized exploration, not fixed 60s sleep."""
from __future__ import annotations
from math import log,sqrt
from statistics import median


def choose(sources, attempts, generated, elapsed, cap, remaining):
    rows=[r for r in attempts if r.get('source') in sources and r.get('status')!='running']
    grouped={s:[r for r in rows if r['source']==s] for s in sources}
    counts={s:len(v) for s,v in grouped.items()}
    sm_calls=sum(r.get('source') in ('s','m') for r in attempts if r.get('status')=='ok')
    # Let structural/working-set repairs settle, but bounded by actual calls AND
    # elapsed time. No time is spent idling and tiny graphs can reach F immediately.
    warm=('f' in sources and sm_calls<4 and elapsed<min(20.,cap*.18)
          and any(s in sources for s in ('s','m')))
    choices=[s for s in sources if not(warm and s=='f')]
    new=[s for s in choices if counts[s]<2 and generated.get(s,0)<12]
    if new:return min(new,key=lambda s:(counts[s],generated.get(s,0),choices.index(s))), 'source_warmup'
    costs={s:max(.005,median([r.get('generation_seconds',0)+r.get('eval_and_audit_seconds',r.get('eval_seconds',.1)) for r in grouped[s][-8:]] or [.1])) for s in choices}
    feasible=[s for s in choices if costs[s]*1.2+.05<=remaining]
    if feasible:choices=feasible
    elif rows:return None,'estimated_time_admission'
    last={s:max((r['index'] for r in grouped[s]),default=0) for s in choices}
    now=max((r['index'] for r in rows),default=0)
    oldest=min(choices,key=lambda s:(last[s],generated.get(s,0)))
    if now-last[oldest]>=8:return oldest,'bounded_starvation'
    def value(s):
        recent=grouped[s][-8:]
        gain=sum(r.get('gain_fraction',0) for r in recent)/max(1,len(recent))
        failed=sum(r.get('status')!='ok' for r in recent)/max(1,len(recent))
        bonus=.012*sqrt(log(2+len(rows))/(1+counts[s]))
        return (gain+bonus)/(costs[s]*(1+failed))
    return max(choices,key=lambda s:(value(s),-last[s])), 'recent_gain_per_cost'
