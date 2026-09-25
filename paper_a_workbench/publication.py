"""Bind one experiment publication; default delivery is local raw + Git reports."""
from __future__ import annotations
import json,re,subprocess,zipfile
from pathlib import Path
from urllib.parse import quote
from common import read,write,within,fresh


def validate(p):
    local=p.get('result_delivery','local')=='local'
    for k in ('publication_id','publication_state','algorithm_revision','official_revision','method_paths','config','protocol'):
        if k not in p:raise ValueError('Publication field required: '+k)
    if p['publication_state'] not in ('planned','partial','final'):raise ValueError('Invalid publication_state')
    for k in ('algorithm_revision','official_revision'):
        if p[k] is None and p['publication_state']!='final':continue
        if not re.fullmatch(r'[0-9a-f]{40,64}',str(p[k])):raise ValueError('Pin '+k+' to the actual commit')
    if p.get('result_revision') is not None:
        if not re.fullmatch(r'[0-9a-f]{40,64}',str(p['result_revision'])):raise ValueError('Pin result_revision to the report commit')
    elif not local:raise ValueError('Remote results require a result_revision')
    if not isinstance(p['method_paths'],list) or not p['method_paths']:raise ValueError('Declare method_paths')
    for path in p['method_paths']+p.get('result_paths',[]):within(Path.cwd(),path)
    within(Path.cwd(),p['config'])
    if p['protocol'].get('budget_scope') not in ('graph_question_core','graph_all_questions_cores'):
        raise ValueError('Declare the actual budget_scope')
    return p


def adopt(profile_path,export_path,out):
    profile=read(profile_path);p=validate(read(export_path));profile['active_publication']=p
    replaced={'results'} | ({'method'} if p['algorithm_revision'] else set())
    kept=[g for g in profile['sources'] if g['id'] not in replaced]
    for g in kept:
        if g['id']=='problem' and p['official_revision']:g['ref']=p['official_revision']
    if p['algorithm_revision']:
        kept.append(dict(id='method',ref=p['algorithm_revision'],paths=p['method_paths'],required=True,
                         text_only=True,exclude_parts=['runs','raw','team_results','results','evidence']))
    paths=p.get('result_paths',[])
    if paths and p.get('result_revision'):
        kept.append(dict(id='results',ref=p['result_revision'],paths=paths,required=False,
                         reports_only=True,text_only=True,role='Reports only; raw evidence comes from local selected runs.'))
    profile['sources']=kept
    # Theory and local-data delivery are independent of choosing/changing a publication.
    profile.setdefault('result_delivery','local')
    write(out,profile)
    return dict(profile=str(Path(out).resolve()),publication_id=p['publication_id'],state=p['publication_state'],
                next='sync code/reports/theory; select local raw runs; create local-spec and intake')


def assets(spec_path,destination):
    """Explicit optional asset reads; raw ZIP download requires a separate opt-in."""
    spec=read(spec_path);repo=spec.get('repository','yellkiin/model_competition')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid repository')
    if not spec.get('allow_raw_download',False):
        for item in spec.get('assets',[]):
            if item['kind']=='artifact' or any(Path(n).suffix.lower() not in {'.md','.json','.csv','.txt','.bib'} for n in item.get('names',[])):
                raise ValueError('Raw data is local by default; select the desktop archive instead')
    out=fresh(destination);receipts=[]
    def api(path,target=None):
        command=['gh','api',path]
        if target is None:return json.loads(subprocess.run(command,capture_output=True,check=True).stdout)
        with target.open('wb') as stream:
            r=subprocess.run(command+['-H','Accept: application/octet-stream'],stdout=stream,stderr=subprocess.PIPE)
        if r.returncode:
            target.unlink(missing_ok=True);raise RuntimeError(r.stderr.decode('utf-8','replace'))
    for item in spec.get('assets',[]):
        try:
            if item['kind']=='release':
                meta=api(f'repos/{repo}/releases/tags/'+quote(item['tag'],safe=''));choices={a['name']:a for a in meta['assets']}
                for name in item['names']:
                    a=choices[name];dest=within(out,name)
                    if dest.exists():raise FileExistsError(dest)
                    dest.parent.mkdir(parents=True,exist_ok=True);api(f'repos/{repo}/releases/assets/{int(a["id"])}',dest)
                    if dest.stat().st_size!=a['size']:raise ValueError('Downloaded asset size mismatch: '+name)
                    receipts.append(dict(kind='release',tag=item['tag'],name=name,id=a['id'],size=a['size'],status='downloaded'))
            elif item['kind']=='artifact':
                aid=int(item['id']);meta=api(f'repos/{repo}/actions/artifacts/{aid}')
                if meta['expired']:raise ValueError('Artifact expired')
                dest=within(out,item.get('filename',meta['name']+'.zip'))
                if dest.exists():raise FileExistsError(dest)
                dest.parent.mkdir(parents=True,exist_ok=True);api(f'repos/{repo}/actions/artifacts/{aid}/zip',dest)
                if not zipfile.is_zipfile(dest):raise ValueError('Downloaded artifact is not a ZIP')
                receipts.append(dict(kind='artifact',id=aid,name=meta['name'],status='downloaded',size=dest.stat().st_size))
            else:raise ValueError('Supported asset kinds: release, artifact')
        except (OSError,ValueError,KeyError,RuntimeError,subprocess.CalledProcessError) as exc:
            receipts.append(dict(request=item,status='fetch_error',error=str(exc)))
        write(out/'ASSET_RECEIPTS.json',receipts)
    return dict(destination=str(out),receipts=receipts)


def unpack(parts,destination):
    from local_data import unpack_paths
    return unpack_paths(parts,destination)
