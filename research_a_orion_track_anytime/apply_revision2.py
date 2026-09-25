"""Materialize the measured v2 revision from the frozen v1.1 source.

Not used at solver runtime. The resulting adapter/runner are committed as files.
"""
from pathlib import Path
D=Path(__file__).parent

def main():
    p=D/'adapter.py';s=p.read_text()
    if 'last_local_source = None' not in s:
        s=s.replace("adaptive = request['method'] in ('budget','combined')", "adaptive = request['method'] in ('budget','combined')\n    revised = request.get('revision') == 'v2'\n    last_local_source = None")
        s=s.replace('nonlocal expanded, last_fifo_source','nonlocal expanded, last_fifo_source, last_local_source, pool, queued')
        old="""        if fifo_enabled and best:
            source = plan_key(best['plan'])"""
        new="""        if revised and best:
            source = plan_key(best['plan'])
            if source != last_local_source:
                # Discard only stale incumbent-specific streams; global construction remains.
                retained = [(name, stream) for name, stream in streams if name not in ('fifo','upstream_local')]
                streams.clear(); streams.extend(retained)
                stale = [c for c in pool if c['family'].startswith('anytime/fifo')]
                pool[:] = [c for c in pool if not c['family'].startswith('anytime/fifo')]
                for c in stale:queued.discard(plan_key(c['plan']))
                state['stale_fifo_discarded'] = state.get('stale_fifo_discarded',0)+len(stale)
                def anchored(parent=best):
                    yield from neighbours(g,parent['plan'],cfg,q,parent['official_result'],limit=12)
                    yield from mutations(g,parent['plan'],cfg,q,parent['official_result'],1)
                    yield from joint_window(g,parent['plan'],cfg,q,parent['official_result'],1)
                streams.appendleft(('upstream_local',iter(anchored())))
                last_local_source=source
        if fifo_enabled and best:
            source = plan_key(best['plan'])"""
        if old not in s:raise ValueError('v1.1 source context missing')
        s=s.replace(old,new)
        s=s.replace("constructive_pending = any(name in ('frontier', 'stage', 'finer') for name, _ in streams)","constructive_pending = any(name in (('frontier','stage','finer','upstream_local') if revised else ('frontier','stage','finer')) for name,_ in streams)")
        s=s.replace("reason = stop_reason(history, best_time, lower, request.get('gap_tolerance', .02),", "gap = request.get('gap_tolerance', .02)\n        if revised:gap = gap/(1+gap) # exactly the original solver's U/L threshold\n        reason = stop_reason(history, best_time, lower, gap,")
        p.write_text(s)
    p=D/'runner.py';s=p.read_text()
    if "p.add_argument('--revision'" not in s:
        s=s.replace("p.add_argument('--gap-tolerance',type=float,default=.02)","p.add_argument('--revision',choices=['v1.1','v2'],default='v1.1');p.add_argument('--gap-tolerance',type=float,default=.02)")
        s=s.replace("policy='wu-v1.1'","policy='wu-'+a.revision");s=s.replace("strategy='anytime',gap_tolerance=a.gap_tolerance)","strategy='anytime',gap_tolerance=a.gap_tolerance,revision=a.revision)")
        p.write_text(s)
if __name__=='__main__':main()
