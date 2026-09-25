"""Conditional 3-choose-2, then 3-choose-1; charged to the same graph cap.

Diagnostic arms start from the SAME archived initial solution. They are stored
separately and do not silently replace the primary SMF table. No matrix runs
for an isolated bad proposal when the overall selected solution improved.
"""
from __future__ import annotations
import time
from pathlib import Path
from .io import read,write,score

def conditional(parent):
    from .engine import Runner
    suspicious=[]
    for st in parent.states.values():
        if st.q==0:continue
        if not st.best:reason='missing_incumbent'
        elif st.initial and score(st.best['response'])[0]>st.initial['makespan']:reason='selected_regression'
        elif st.target and st.best and score(st.best['response'])[0]>st.target*1.005:reason='published_target_gap'
        elif st.initial and st.calls>=6 and st.best_raw and st.best_raw>1.005*st.initial['makespan']:
            reason='all_new_candidates_below_reference'
        else:continue
        suspicious.append((st,reason))
    # Use the first actual primary solution, not different constructor outputs.
    from .report import events
    first={}
    for row in events(parent.out):
        if row['event']=='incumbent':first.setdefault((row['q'],row['n']),row)
    entries=[]
    for (q,n),row in first.items():
        item=dict(row,case=parent.graph)
        for field in ('plan_file','result_file','pair_file'):
            if item.get(field):item[field]=str(parent.out/item[field])
        entries.append(item)
    catalog=parent.out/'diagnostics/initial_catalog.json'
    write(catalog,dict(entries=entries,targets=[]))
    receipts=[]
    for st,reason in suspicious[:2]:
        if parent.left()<3:break
        records=[]
        for tier,modes in [(2,['SM','SF','MF']),(1,['S','M','F'])]:
            if tier==1 and records:
                values=[r['makespan'] for r in records if r.get('makespan')]
                # A pair revealing a clear improvement is sufficient to guide follow-up.
                if values and min(values)<(st.target or (st.initial or {}).get('makespan',min(values)))*.995:break
            for i,mode in enumerate(modes):
                left=parent.left()
                if left<1:break
                cap=min(15.,left/max(1,(len(modes)-i)*(2 if tier==2 else 1)))
                if cap<.5:break
                out=parent.out/'diagnostics'/f'q{st.q}_n{st.n}'/mode
                req={**parent.req,'out':str(out),'mode':mode,'keys':[(st.q,st.n)],
                     'seconds':cap,'launch_epoch':time.time(),'catalog':str(catalog),'diagnostics':False,'cache_study':False,'max_evaluations':8}
                write(out/'request.json',req)
                parent.event('diagnostic_start',q=st.q,n=st.n,mode=mode,reason=reason,cap=cap)
                start=time.monotonic()
                child=Runner(req,shared=(parent.session,parent.cfg,parent.gc))
                try:
                    child.run();best=child.states[st.q,st.n].best
                    value=score(best['response'])[0] if best else None
                    row=dict(q=st.q,n=st.n,mode=mode,reason=reason,tier=tier,makespan=value,
                        seconds=time.monotonic()-start,official_calls=child.calls,
                        start_graph_seconds=parent.elapsed()-(time.monotonic()-start),
                        initial_makespan=first.get((st.q,st.n),{}).get('makespan'))
                except Exception as exc:
                    row=dict(q=st.q,n=st.n,mode=mode,tier=tier,error=str(exc),seconds=time.monotonic()-start)
                records.append(row);receipts.append(row);parent.event('diagnostic_end',**row)
    write(parent.out/'diagnostics.json',dict(arms=receipts,selection='primary SMF unchanged',
        cost_scope='included in original graph cap',policy='pairs first; singles if unresolved'))
