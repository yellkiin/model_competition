"""Import real archived plans/responses into a relocatable seed catalogue.

Scan only supplied result roots, not the repository. Numerical reports without
plans remain targets, not incumbents. Historical clocks are never local costs.
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from .io import read, write, score, key, csv_read, utc, resolve

def job_incumbent(folder):
    state = read(folder/'progress.json')
    meta = state.get('incumbent') or state.get('selected')
    if not meta or not meta.get('result_file'):
        return None
    def located(name):
        p = resolve(folder, name)
        if p.is_file(): return p
        # Original Windows absolute prefixes need no rewrite of evidence bytes.
        tail = str(name).replace('\\', '/').split('/incumbents/')
        if len(tail) == 2: p = folder/'incumbents'/tail[1]
        else: p = folder/str(name).replace('\\', '/').split('/')[-1]
        return p
    pp, rp = located(meta['plan_file']), located(meta['result_file'])
    response = read(rp)
    if response.get('status') != 'ok' or not response.get('audit', {}).get('ok'):
        return None
    plan = read(pp); raw = response['official_result']
    q, n = int(state['q']), int(state['n'])
    if len(plan['core_schedules']) != n or raw['num_cores'] != n:
        raise ValueError(f'Archived core mismatch: {folder}')
    sm = read(folder/'summary.json') if (folder/'summary.json').is_file() else {}
    cost = sm.get('end_to_end_solve_seconds')
    if cost is None and state.get('seed_solve_seconds') is not None and state.get('elapsed_seconds') is not None:
        cost=float(state['seed_solve_seconds'])+float(state['elapsed_seconds'])
    if cost is None:
        cost = sm.get('total_solve_seconds')
    request = read(folder/'request.json') if (folder/'request.json').is_file() else {}
    if cost is None and not request.get('seed_job') and not meta.get('from_seed'):
        cost = sm.get('total_job_seconds', sm.get('process_seconds'))
    return dict(case=f'case_{int(str(state["case"]).removeprefix("case_")):03d}', q=q, n=n, plan=plan, response=response,
                plan_source=str(pp), result_source=str(rp),
                seed_solve_seconds=cost, origin=str(folder),
                same_plan_no_l2=None)

def build(roots, destination, cases=None, publication=None, extra_indices=()):
    out = Path(destination).resolve(); out.mkdir(parents=True, exist_ok=False)
    selected, pairs, errors, pending = {}, {}, [], []
    for root in map(Path, roots):
        for p in sorted(root.rglob('progress.json')):
            # Supplied roots must be FINAL or explicitly selected newer experiments.
            if any(x in p.parts for x in ('pilot', 'matched_legacy', 'sensitivity')): continue
            try:
                r = job_incumbent(p.parent)
                if not r or (cases and r['case'] not in cases): continue
                k = r['case'], r['q'], r['n']
                if r['q'] == 2:
                    pairs[(r['case'], r['n'], key(r['plan']))] = r
                if k not in selected or score(r['response']) < score(selected[k]['response']):
                    selected[k] = r
            except (ValueError, KeyError, OSError) as e:
                errors.append(dict(path=str(p), error=str(e)))
    # Explicit exported entries must carry actual plans and original responses.
    for index in extra_indices:
        idx=Path(index);obj=read(idx);entries=obj.get('entries',[]) if isinstance(obj,dict) else obj
        for entry in entries:
            if cases and entry['case'] not in cases:continue
            try:
                pp=resolve(idx.parent,entry['plan_file'])
                if not pp.exists():
                    from .io import ROOT
                    pp=ROOT/entry['plan_file']
                rp=resolve(idx.parent,entry['result_file']) if entry.get('result_file') else None
                if pp.exists() and (rp is None or not rp.exists()):
                    value=entry.get('recorded_makespan',entry.get('makespan'))
                    if value:
                        dest=out/'pending'/f'{len(pending):03d}_plan.json';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(pp,dest)
                        pending.append(dict(case=entry['case'],q=int(entry['q']),n=int(entry['n']),makespan=float(value),
                            plan_file=str(dest.relative_to(out)),seed_solve_seconds=entry.get('seed_solve_seconds'),origin=str(idx)))
                    continue
                plan,response=read(pp),read(rp)
                if response.get('status')!='ok' or not response.get('audit',{}).get('ok'):continue
                r=dict(entry,plan=plan,response=response,plan_source=str(pp),result_source=str(rp),
                       origin=entry.get('origin',str(idx)),seed_solve_seconds=entry.get('seed_solve_seconds'))
                k=r['case'],int(r['q']),int(r['n'])
                if k not in selected or score(response)<score(selected[k]['response']):selected[k]=r
                if r.get('pair_file'):
                    pair=read(resolve(idx.parent,r['pair_file']))
                    if pair.get('status')=='ok' and pair.get('audit',{}).get('ok'):
                        pairs[(r['case'],r['n'],key(plan))]=dict(response=pair)
            except (ValueError,OSError,KeyError) as exc:errors.append(dict(path=str(idx),error=str(exc)))
    rows = []
    for (case, q, n), r in sorted(selected.items()):
        folder = out/f'{case}_q{q}_n{n}'
        folder.mkdir()
        # Copy exact original response/plan bytes; no invented official wrapper.
        plan_file = folder/'plan.json'; response_file = folder/'response.json.gz'
        shutil.copyfile(r['plan_source'], plan_file)
        if Path(r['result_source']).suffix == '.gz':
            shutil.copyfile(r['result_source'], response_file)
        else: write(response_file, r['response'])
        pair_file = None
        pr = pairs.get((case, n, key(r['plan']))) if q == 3 else None
        if pr:
            pair_file = folder/'no_l2.json.gz'; write(pair_file, pr['response'])
        rows.append(dict(case=case, q=q, n=n, makespan=score(r['response'])[0],
            added_copy_bytes=score(r['response'])[1], plan_file=str(plan_file.relative_to(out)),
            result_file=str(response_file.relative_to(out)),
            pair_file=str(pair_file.relative_to(out)) if pair_file else None,
            seed_solve_seconds=r['seed_solve_seconds'], origin=r['origin']))
    target_rows = csv_read(publication) if publication else []
    write(out/'catalog.json', dict(schema=1, created_utc=utc(), entries=rows,
        targets=target_rows,pending=pending, errors=errors, source_roots=list(map(str, roots))))
    return out/'catalog.json'

def load_catalog(path):
    p = Path(path).resolve(); obj = read(p)
    for r in obj['entries']+obj.get('pending',[]):
        for field in ('plan_file','result_file','pair_file'):
            if r.get(field): r[field] = str(resolve(p.parent,r[field]).resolve())
    return obj

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--roots', nargs='+', required=True)
    p.add_argument('--out', required=True); p.add_argument('--publication')
    p.add_argument('--cases', nargs='+')
    a = p.parse_args()
    cases = {f'case_{int(c.removeprefix("case_")):03d}' for c in a.cases} if a.cases else None
    print(build(a.roots,a.out,cases,a.publication))

if __name__ == '__main__': main()
