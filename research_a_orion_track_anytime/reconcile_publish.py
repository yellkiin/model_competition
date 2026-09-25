"""Publish THIS run's records, not reconstruct historical missing experiments."""
import csv,gzip,json,os,shutil,urllib.request,urllib.error,zipfile
from pathlib import Path
from collections import Counter,defaultdict
REPO='yellkiin/model_competition'
OUT=Path('research_a_orion_track_anytime/results/reconcile_20260925_1012')
PEER='27f7aa073bd7f91a1b1b9842eb2c9eb48117bf37'
TAG='anytime-reconcile-20260925-1012'

def api(endpoint,method='GET',data=None):
    url='https://api.github.com/repos/'+REPO+endpoint
    headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'}
    payload=json.dumps(data).encode() if data is not None else None
    if payload is not None:headers['Content-Type']='application/json'
    with urllib.request.urlopen(urllib.request.Request(url,data=payload,headers=headers,method=method),timeout=60) as r:return json.load(r)

def csvwrite(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row));path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    roots=sorted(Path('/tmp/reconcile_download').glob('reconcile-case-*'))
    rows=[];prefixes=[];bundles=[];sources=[];checks=[]
    for root in roots:
        case=root.name.rsplit('-',1)[-1]
        for af in sorted(root.glob('*/all_jobs.json')):
            phase=af.parent.name;records=json.loads(af.read_text())
            for r in records:
                slim={k:v for k,v in r.items() if not isinstance(v,(list,dict))}
                slim.update(batch=phase,source_artifact=root.name)
                rows.append(slim)
                jobname=Path(r.get('job','')).name
                selected=af.parent/'jobs'/jobname/'selected'
                if selected.is_dir():
                    plan=json.loads((selected/'plan.json').read_text())
                    with gzip.open(selected/'response.json.gz','rt') as f:resp=json.load(f)
                    raw=resp['official_result']
                    ok=resp['status']=='ok' and resp['audit']['ok'] and raw['makespan']==r.get('makespan') and len(plan['core_schedules'])==r['n']
                    check=dict(case=r['case'],q=r['q'],n=r['n'],method=r['method'],mode=r['mode'],batch=phase,selected_response_valid=ok)
                    if r['q']==3:
                        pairdir=af.parent/'pairs'/f'{r["case"]}_q3_n{r["n"]}_{r["mode"].replace("_start","")}_{r["method"]}'/'selected'
                        if pairdir.exists():
                            pair=json.loads((pairdir/'plan.json').read_text())
                            with gzip.open(pairdir/'response.json.gz','rt') as f:pr=json.load(f)
                            check['pair_exact_and_valid']=pair==plan and pr['status']=='ok' and pr['audit']['ok'] and pr['official_result']['makespan']==r.get('no_l2_makespan')
                        else:check['pair_exact_and_valid']=False
                    checks.append(check)
                    dest=OUT/'selected'/case/phase/r['method'];dest.mkdir(parents=True,exist_ok=True)
                    shutil.copy(selected/'plan.json',dest/'plan.json')
                    (dest/'SOURCE.json').write_text(json.dumps(dict(artifact=root.name,member=str(selected.relative_to(root)),makespan=raw['makespan'],q=r['q'],n=r['n']),indent=2))
            tf=af.parent/'trajectory.csv'
            if tf.exists():
                for r in csv.DictReader(tf.open(encoding='utf-8-sig')):prefixes.append(dict(r,batch=phase,source_artifact=root.name))
        z=Path('/tmp')/(root.name+'_raw.zip')
        with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for f in sorted(root.rglob('*')):
                if f.is_file():archive.write(f,str(f.relative_to(root)))
        bundles.append(z)
        cf=root/'EXECUTION_COMMIT.txt'
        sources.append(dict(case=case,execution_commit=cf.read_text().strip() if cf.exists() else None,raw_bundle=z.name))
    csvwrite(OUT/'per_case.csv',rows);csvwrite(OUT/'trajectory.csv',prefixes);csvwrite(OUT/'official_checks.csv',checks)
    grouped=defaultdict(dict)
    for r in rows:grouped[r['case'],r['q'],r['n'],r['mode'],r['batch']][r['method']]=r
    comparison=[]
    for (c,q,n,mode,batch),methods in sorted(grouped.items()):
        old=methods.get('old',{});peer=methods.get('peer_v4',{});new=methods.get('repair_v6',{})
        o,p,x=old.get('makespan'),peer.get('makespan'),new.get('makespan')
        comparison.append(dict(case=c,q=q,n=n,mode=mode,batch=batch,old=o,peer_v4=p,repair_v6=x,
          repair_vs_peer='missing' if p is None or x is None else 'win' if x<p else 'loss' if x>p else 'tie',
          improvement_vs_peer_pct=None if p is None or x is None else (1-x/p)*100,
          old_seconds=old.get('solve_seconds'),peer_seconds=peer.get('solve_seconds'),repair_seconds=new.get('solve_seconds'),
          peer_evaluations=peer.get('evaluations_completed_within_budget'),repair_evaluations=new.get('evaluations_completed_within_budget'),
          peer_stop=peer.get('stopped'),repair_stop=new.get('stopped')))
    csvwrite(OUT/'comparison.csv',comparison)
    summary=dict(expected_search_arms=36,actual_search_arms=len(rows),status_counts=dict(Counter(r.get('status') for r in rows)),
      peer_comparison=dict(Counter(r['repair_vs_peer'] for r in comparison)),
      selected_response_checks=len(checks),selected_response_valid=sum(bool(r['selected_response_valid']) for r in checks),
      q3_pairs_requested=sum(r['q']==3 for r in rows),q3_pairs_exact_valid=sum(bool(r.get('pair_exact_and_valid')) for r in checks),
      prior_v4_v5_originals_recovered=False,new_code_policy='reconcile-v6',peer_commit=PEER,
      workflow_run_id=int(os.environ['GITHUB_RUN_ID']),per_case_execution=sources,full_100_rerun=False)
    (OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    # Preserve compact version metadata for actual authorship boundaries.
    comparison_meta=api('/compare/16abeb6c5bcc98acb322665fdb8dc7fbd377bcb2...'+PEER)
    lineage=[dict(sha=c['sha'],author=c['commit']['author']['name'],date=c['commit']['author']['date'],message=c['commit']['message']) for c in comparison_meta['commits']]
    (OUT/'PEER_COMMITS.json').write_text(json.dumps(lineage,ensure_ascii=False,indent=2),encoding='utf8')
    release=None
    for r in api('/releases?per_page=100'):
        if r['tag_name']==TAG:release=r;break
    if release is None:release=api('/releases','POST',dict(tag_name=TAG,target_commitish=os.environ['BRANCH'],name='Anytime reconciliation: complete fresh evidence',body='Fresh reconciliation experiments; original missing v4/v5 data are NOT reconstructed. Peer PR34 is unchanged. See PR36 and SUMMARY.json.',draft=True,prerelease=True))
    assets=[]
    for path in bundles:
        existing=next((a for a in release.get('assets',[]) if a['name']==path.name),None)
        if existing:
            if existing['size']!=path.stat().st_size:raise RuntimeError('Refusing to overwrite an existing evidence asset')
            asset=existing
        else:
            req=urllib.request.Request('https://uploads.github.com/repos/'+REPO+f'/releases/{release["id"]}/assets?name='+path.name,data=path.read_bytes(),headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Content-Type':'application/zip'},method='POST')
            with urllib.request.urlopen(req,timeout=180) as response:asset=json.load(response)
        assets.append(dict(name=asset['name'],asset_id=asset['id'],size_bytes=asset['size'],state=asset['state']))
    release=api('/releases/'+str(release['id']),'PATCH',dict(draft=False,prerelease=True))
    inventory={a['name']:a for a in api('/releases/'+str(release['id'])+'/assets?per_page=100')}
    for a in assets:a['url']=inventory[a['name']]['browser_download_url']
    evidence=dict(summary=summary,release_url=release['html_url'],assets=assets,
       peer_original_branch_untouched=True,original_missing_local_claims_not_reused=True)
    (OUT/'EVIDENCE_INDEX.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
