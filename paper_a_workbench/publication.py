"""Explicit publication selection, portable acquisition and safe ZIP restoration."""
from __future__ import annotations
import json, re, subprocess, zipfile
from pathlib import Path
from urllib.parse import quote
from common import read, write, within, fresh


def validate(p):
    for k in ('publication_id','publication_state','algorithm_revision','official_revision',
              'result_revision','method_paths','result_paths','config','protocol'):
        if k not in p: raise ValueError('Publication field required: '+k)
    if p['publication_state'] not in ('planned','partial','final'):raise ValueError('Invalid publication_state')
    for k in ('algorithm_revision','official_revision','result_revision'):
        if not re.fullmatch(r'[0-9a-f]{40,64}',p[k]):raise ValueError('Pin '+k+' to an actual commit')
    for k in ('method_paths','result_paths'):
        if not isinstance(p[k],list) or not p[k]:raise ValueError(k+' must name actual repository paths')
        for path in p[k]:within(Path.cwd(),path)
    within(Path.cwd(),p['config'])
    if p['protocol'].get('budget_scope') not in ('graph_question_core','graph_all_questions_cores'):
        raise ValueError('Specify actual budget_scope, independently of directory name')
    return p


def adopt(profile_path, export_path, out):
    profile=read(profile_path); p=validate(read(export_path))
    profile['active_publication']=p
    kept=[g for g in profile['sources'] if g['id'] not in ('method','results')]
    for g in kept:
        if g['id']=='problem':g['ref']=p['official_revision']
    kept += [dict(id='method',ref=p['algorithm_revision'],paths=p['method_paths'],required=True,
                  text_only=True,exclude_parts=['runs','raw','team_results','results','evidence']),
             dict(id='results',ref=p['result_revision'],paths=p['result_paths'],required=True)]
    profile['sources']=kept
    write(out,profile)
    return {'profile':str(Path(out).resolve()),'publication_id':p['publication_id'],
            'state':p['publication_state'],'next':'sync with this profile; assemble raw runs; use intake on this one publication'}


def assets(spec_path,destination):
    """Download only explicitly selected artifacts/assets via the user's existing gh auth."""
    spec=read(spec_path);repo=spec.get('repository','yellkiin/model_competition')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Invalid repository')
    out=fresh(destination);receipts=[]
    def api(path,target=None):
        command=['gh','api',path]
        if target is None:
            r=subprocess.run(command,capture_output=True,check=True)
            return json.loads(r.stdout)
        with target.open('wb') as stream:
            r=subprocess.run(command+['-H','Accept: application/octet-stream'],stdout=stream,stderr=subprocess.PIPE)
        if r.returncode:
            target.unlink(missing_ok=True)
            raise RuntimeError(r.stderr.decode('utf-8','replace'))
    for item in spec.get('assets',[]):
        try:
            if item['kind']=='release':
                meta=api(f'repos/{repo}/releases/tags/'+quote(item['tag'],safe=''))
                choices={a['name']:a for a in meta['assets']}
                for name in item['names']:
                    a=choices[name];dest=within(out,name)
                    if dest.exists():raise FileExistsError(dest)
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    api(f'repos/{repo}/releases/assets/{int(a["id"])}',dest)
                    if dest.stat().st_size!=a['size']:raise ValueError('Downloaded asset size mismatch: '+name)
                    receipts.append(dict(kind='release',tag=item['tag'],name=name,id=a['id'],size=a['size'],status='downloaded'))
            elif item['kind']=='artifact':
                aid=int(item['id']);meta=api(f'repos/{repo}/actions/artifacts/{aid}')
                if meta['expired']:raise ValueError('Artifact expired; select its persistent release archive')
                dest=within(out,item.get('filename',meta['name']+'.zip'))
                if dest.exists():raise FileExistsError(dest)
                dest.parent.mkdir(parents=True,exist_ok=True)
                api(f'repos/{repo}/actions/artifacts/{aid}/zip',dest)
                if not zipfile.is_zipfile(dest):raise ValueError('Downloaded artifact is not a ZIP')
                receipts.append(dict(kind='artifact',id=aid,name=meta['name'],status='downloaded',size=dest.stat().st_size))
            else:raise ValueError('Supported asset kinds: release, artifact')
        except (OSError,ValueError,KeyError,RuntimeError,subprocess.CalledProcessError) as exc:
            receipts.append(dict(request=item,status='fetch_error',error=str(exc)))
        write(out/'ASSET_RECEIPTS.json',receipts)
    return {'destination':str(out),'receipts':receipts}


def unpack(parts,destination):
    """Concatenate an explicitly ordered part list; extract without rewriting source records."""
    out=fresh(destination);archive=out/'joined.zip'
    try:
        with archive.open('wb') as dst:
            for path in parts:
                with Path(path).open('rb') as src:
                    while chunk:=src.read(1024*1024):dst.write(chunk)
        files=[]
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if member.is_dir():continue
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Archive contains a symbolic link')
                target=within(out/'records',member.filename);target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(member) as src,target.open('wb') as dst:
                    while chunk:=src.read(1024*1024):dst.write(chunk)
                files.append(dict(path=member.filename,bytes=target.stat().st_size))
        write(out/'UNPACK_RECEIPT.json',{'parts':[str(Path(p).resolve()) for p in parts],'files':files,
              'record_policy':'Original JSON contents and paths unchanged. Intake resolves relative layout instead.'})
    finally:
        archive.unlink(missing_ok=True)
    return {'records':str(out/'records'),'files':len(files)}
