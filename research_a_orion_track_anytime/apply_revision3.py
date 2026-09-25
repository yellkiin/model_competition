"""One-time materialization of v3; source files, not this helper, run experiments."""
from pathlib import Path
D=Path(__file__).parent

def main():
    p=D/'adapter.py';s=p.read_text()
    if 'def _prioritized_stages(' not in s:
        s=s.replace("revised = request.get('revision') == 'v2'", "revised = request.get('revision') in ('v2','v3')")
        old="('stage', iter(stage_candidates(g, n, cfg, q)))"
        if old not in s:raise ValueError('Expected frozen v2 stage source')
        s=s.replace(old,"('stage', iter(_prioritized_stages(g,n,cfg,q,deadline) if request.get('revision')=='v3' else stage_candidates(g,n,cfg,q)))")
        helper='''
def _prioritized_stages(g,n,cfg,q,deadline):
    """Bounded lookahead of existing stage candidates, no new partition logic.

    Charge generation of the eight fixed-grid members before the first yield;
    evaluate the lowest existing proxy first. Leave expensive stage DP lazy.
    """
    from research_a_orion_anytime.strategies import stage_candidates
    stream=iter(stage_candidates(g,n,cfg,q));batch=[]
    for _ in range(8):
        if time.monotonic()+.05>=deadline:break
        try:batch.append(next(stream))
        except StopIteration:break
    yield from sorted(batch,key=lambda c:(c['proxy']['score'],c['name']))
    yield from stream

'''
        s=s.replace('\ndef _family(value):',helper+'\ndef _family(value):');p.write_text(s)
    p=D/'runner.py';s=p.read_text().replace("choices=['v1.1','v2']","choices=['v1.1','v2','v3']");p.write_text(s)
if __name__=='__main__':main()
