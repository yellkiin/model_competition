"""Observed-cost source allocation with staged warmup and persistent statistics.

This is a heuristic for non-stationary search, not an IID bandit regret theorem.
All estimates include completed local evaluations; no historical-machine timing.
"""
from collections import defaultdict,deque
from statistics import median
from math import log,sqrt

class Selector:
    def __init__(self):
        self.scanned=0;self.count=defaultdict(int);self.last=defaultdict(int)
        self.recent=defaultdict(lambda:deque(maxlen=8));self.sm_ok=0

    def choose(self,sources,attempts,generated,elapsed,cap,remaining,last_gain):
        for i in range(self.scanned,len(attempts)):
            row=attempts[i]
            if row.get('status')=='running':break
            source=row.get('source');self.count[source]+=1;self.last[source]=row['index']
            self.recent[source].append(row);self.scanned=i+1
            self.sm_ok+=int(source in ('s','m') and row.get('status')=='ok')
        # Do useful S/M work first, not a fixed wall-time barrier for fast cases.
        prelude=min(60.,cap*.30)
        improving=(elapsed-last_gain<3. and self.sm_ok<24 and elapsed<min(80.,cap*.60))
        warm='f' in sources and any(s in sources for s in ('s','m')) and ((elapsed<prelude and self.sm_ok<6) or improving)
        choices=[s for s in sources if not(warm and s=='f')]
        if not choices:choices=list(sources)
        untouched=[s for s in choices if self.count[s]<2 and generated.get(s,0)<12]
        if untouched:return min(untouched,key=lambda s:(self.count[s],generated.get(s,0),choices.index(s))),'source_warmup'
        costs={s:max(.01,median([r.get('generation_seconds',0)+r.get('eval_and_audit_seconds',r.get('eval_seconds',.1)) for r in self.recent[s]] or [.1])) for s in choices}
        admitted=[s for s in choices if 1.2*costs[s]+.1<remaining]
        if admitted:choices=admitted
        elif self.scanned:return None,'estimated_time_admission'
        now=max((self.last[s] for s in choices),default=0)
        oldest=min(choices,key=lambda s:(self.last[s],self.count[s]))
        if now-self.last[oldest]>=8:return oldest,'bounded_starvation'
        def value(s):
            rs=self.recent[s];reward=sum(r.get('gain_fraction',0.) for r in rs)/max(1,len(rs))
            failures=sum(r.get('status')!='ok' for r in rs)/max(1,len(rs))
            bonus=.012*sqrt(log(2+self.scanned)/(1+self.count[s]))
            return (reward+bonus)/(costs[s]*(1+failures))
        return max(choices,key=lambda s:(value(s),-self.last[s])), 'staged_cost_allocation' if warm else 'joint_gain_per_cost'
