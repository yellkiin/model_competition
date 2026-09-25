"""Publish existing result bytes only. No solvers, score changes, or full-repo audit.

Large archives are private-repository Release assets; small snapshots stay in Git.
The temporary receiver supplies a ZIP with an explicit ten-file allowlist.
"""
from __future__ import annotations
import base64
import csv
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REPO = 'yellkiin/model_competition'
BRANCH = 'orion/archive-structure-results-20260925-0455'
TAG = 'orion-structure-results-20260925-0455'
ROOT = Path('research_a_orion_track_structure/results/publication_20260925_0455')
WORK = Path('/tmp/orion_archive_publish')
EXPECTED = {
 'ORION_structure_recheck_20260925_raw_local.zip':72928491,
 'ORION_structure_recheck_20260925_raw_ci.zip':178963385,
 'ORION_structure_recheck_20260925_code_reports.zip':1448778,
 'ORION_structure_recheck_per_case_20260925.csv':522407,
 'ORION_structure_recheck_trajectory_20260925.csv':434696,
 'ORION_structure_recheck_REPORT_20260925.md':14573,
 'orion_structure_cold30_36046726567.zip':28255987,
 'orion_structure_real_small_36048331790.zip':24170191,
 'ORION_safe_refine_recovered_results_20260925.zip':75151,
 'ORION_safe_refine_results_20260925.md':5585,
}
TOKEN = os.environ['GH_TOKEN']
API = 'https://api.github.com/repos/'+REPO
HEADERS = {'Authorization':'Bearer '+TOKEN,'Accept':'application/vnd.github+json',
           'X-GitHub-Api-Version':'2022-11-28','User-Agent':'orion-existing-results-archive'}

def api(endpoint, method='GET', data=None, missing_ok=False):
    url=API+'/'+endpoint
    headers=dict(HEADERS)
    payload=None
    if data is not None:
        payload=json.dumps(data,ensure_ascii=False).encode('utf8');headers['Content-Type']='application/json'
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,data=payload,headers=headers,method=method)
            with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
        except urllib.error.HTTPError as exc:
            if exc.code==404 and missing_ok:return None
            if exc.code in (429,500,502,503,504) and attempt<3:
                time.sleep(3*(attempt+1));continue
            raise RuntimeError(f'GitHub {method} {endpoint}: status {exc.code}') from None
    raise RuntimeError('GitHub request retries exhausted')

def git(*args):
    return subprocess.check_output(['git',*args],text=True).strip()

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def csv_write(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def upload_asset(release, path):
    name=path.name
    existing=api(f"releases/{release['id']}/assets?per_page=100")
    same=next((a for a in existing if a['name']==name),None)
    if same:
        if same['size']!=path.stat().st_size:
            raise RuntimeError('Refuse overwriting differently sized asset '+name)
        return same
    url=release['upload_url'].split('{',1)[0]+'?'+urllib.parse.urlencode({'name':name})
    headers=dict(HEADERS)
    headers.update({'Content-Type':'application/zip' if path.suffix=='.zip' else 'application/octet-stream',
                    'Content-Length':str(path.stat().st_size)})
    with path.open('rb') as body:
        req=urllib.request.Request(url,data=body,headers=headers,method='POST')
        try:
            with urllib.request.urlopen(req,timeout=300) as r:asset=json.load(r)
        except urllib.error.HTTPError as exc:
            raise RuntimeError('Release asset upload failed '+name+': '+str(exc.code)) from None
    if asset.get('state')!='uploaded' or asset['size']!=path.stat().st_size:
        raise RuntimeError('Release asset not completely uploaded: '+name)
    print('UPLOADED',name,asset['size'],flush=True)
    return asset

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def download_artifact(artifact, path):
    # Never forward the repository token to the signed storage redirect.
    req=urllib.request.Request(API+f"/actions/artifacts/{artifact['id']}/zip",headers=HEADERS)
    opener=urllib.request.build_opener(NoRedirect())
    try:
        response=opener.open(req,timeout=90)
    except urllib.error.HTTPError as exc:
        if exc.code not in (301,302,303,307,308):
            raise RuntimeError('Artifact download request failed: '+str(exc.code)) from None
        location=exc.headers.get('Location')
        if not location or not location.startswith('https://'):raise RuntimeError('Invalid artifact redirect')
        response=urllib.request.urlopen(location,timeout=180)
    with response, path.open('wb') as out:shutil.copyfileobj(response,out,8*1024*1024)
    if path.stat().st_size!=artifact['size_in_bytes']:raise RuntimeError('Artifact archive length mismatch')
    return path

def safe_extract(archive,destination):
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            p=PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe archive path')
            if item.is_dir():continue
            target=destination.joinpath(*p.parts);target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)

def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise RuntimeError('Unexpected repository')
    metadata=api('')
    if not metadata.get('private'):raise RuntimeError('Refusing to publish private experiment archives to a public repository')
    WORK.mkdir(exist_ok=True)
    git('fetch','origin',BRANCH)
    git('merge','--ff-only','FETCH_HEAD')
    inventory=None
    with zipfile.ZipFile('/tmp/orion_incoming_results.zip') as incoming:
        if set(incoming.namelist())!=set(EXPECTED)|{'LOCAL_INVENTORY.json'}:
            raise RuntimeError('Incoming ZIP does not match requested allowlist')
        for name,size in EXPECTED.items():
            if incoming.getinfo(name).file_size!=size:raise RuntimeError('Incoming length mismatch '+name)
            with incoming.open(name) as src,(WORK/name).open('wb') as dst:shutil.copyfileobj(src,dst,8*1024*1024)
        inventory=json.loads(incoming.read('LOCAL_INVENTORY.json'))
    write_json(ROOT/'LOCAL_INVENTORY.json',inventory)
    receipt=json.loads(Path('/tmp/orion_ingest_receipt.json').read_text())
    write_json(ROOT/'TRANSFER_RECEIPT.json',receipt)
    # Freeze full small attachments without applying their source code to main.
    safe_extract(WORK/'ORION_structure_recheck_20260925_code_reports.zip',ROOT/'pr30_code_reports_snapshot')
    safe_extract(WORK/'ORION_safe_refine_recovered_results_20260925.zip',ROOT/'pr31_recovered_summary')
    for name in EXPECTED:
        if not name.endswith('.zip'):
            (ROOT/'aggregate_attachments').mkdir(exist_ok=True)
            shutil.copyfile(WORK/name,ROOT/'aggregate_attachments'/name)
    source31='9550ac947af13f14c775d0ef003ac4101188dd47'
    frozen=[]
    for relative in ('review/REPORT.md','review/per_case.csv','review/means.csv','EVIDENCE_INDEX.json'):
        path='research_a_orion_track_structure/results/safe_refine_20260925/'+relative
        result=api('contents/'+path+'?ref='+source31)
        target=ROOT/'pr31_repository_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(base64.b64decode(result['content']))
        frozen.append({'source_commit':source31,'source_path':path,'snapshot_path':str(target)})
    releases=api('releases?per_page=100')
    release=next((r for r in releases if r['tag_name']==TAG),None)
    if release is None:
        release=api('releases','POST',{'tag_name':TAG,'target_commitish':BRANCH,
          'name':'ORION structure: archived experiment files (2026-09-25)',
          'body':'Existing experiment evidence only. No algorithm runs or score changes. Two PR31 raw/code-plan archives are unavailable and are listed in the manifest. This is not a full new benchmark release.',
          'draft':True,'prerelease':True,'make_latest':'false'})
    if not release.get('draft'):raise RuntimeError('Refusing to alter an already published release')
    published=[]
    for name,size in EXPECTED.items():
        asset=upload_asset(release,WORK/name)
        published.append({'name':name,'size_bytes':size,'asset_id':asset['id'],
           'url':asset['browser_download_url'],'source':'existing_conversation_attachment',
           'evidence_level':'recovered_summary_only' if name.startswith('ORION_safe_refine') else 'original_saved_evidence',
           'state':asset['state']})
    extra=[];remote_errors=[]
    for run_id in (36046094858,36046578817,36047055409):
        listing=api(f'actions/runs/{run_id}/artifacts?per_page=100',missing_ok=True)
        if not listing:
            remote_errors.append({'run_id':run_id,'status':'source_run_not_accessible'});continue
        for artifact in listing.get('artifacts',[]):
            if artifact.get('expired'):
                remote_errors.append({'run_id':run_id,'artifact_id':artifact['id'],'status':'expired'});continue
            name=f"prior_run_{run_id}_artifact_{artifact['id']}.zip"
            try:
                download_artifact(artifact,WORK/name)
                asset=upload_asset(release,WORK/name)
                extra.append({'name':name,'size_bytes':asset['size'],'asset_id':asset['id'],
                    'url':asset['browser_download_url'],'source_run_id':run_id,
                    'source_artifact_id':artifact['id'],'source_artifact_name':artifact['name'],
                    'state':asset['state'],'evidence_level':'original_github_artifact_copy'})
            except Exception as exc:
                remote_errors.append({'run_id':run_id,'artifact_id':artifact['id'],'status':'archive_copy_failed','error':str(exc)})
    members=[]
    for path in sorted(WORK.glob('*.zip')):
        with zipfile.ZipFile(path) as z:
            for item in z.infolist():
                members.append({'archive':path.name,'member':item.filename,'size_bytes':item.file_size,
                    'compressed_bytes':item.compress_size})
    csv_write(ROOT/'ARCHIVE_MEMBERS.csv',members)
    manifest={'schema_version':1,'published_at_utc':datetime.now(timezone.utc).isoformat(),
      'repository':REPO,'branch':BRANCH,'source_main_at_start':'a67329c768be3bf750f7bd61f487d4ec22f5fe24',
      'release_tag':TAG,'release_id':release['id'],
      'release_url':'https://github.com/'+REPO+'/releases/tag/'+TAG,
      'purpose':'Archive previous results only. No experiment rerun. No automatic merge.',
      'available_local_files_uploaded':len(published),'uploaded_local_bytes':sum(x['size_bytes'] for x in published),
      'all_available_local_files_uploaded':len(published)==len(EXPECTED),
      'all_prior_experiment_evidence_complete':False,
      'assets':published+extra,'missing':inventory['missing'],'remote_archive_errors':remote_errors,
      'frozen_repository_snapshots':frozen,'transfer':receipt,
      'private_keys_or_repository_tokens_in_archive':False,
      'original_official_inputs_and_literature_not_reuploaded':True}
    write_json(ROOT/'PUBLISHED_MANIFEST.json',manifest)
    table=['|文件|字节数|已上传附件|','|---|---:|---|']
    for asset in published+extra:
        table.append(f"|{asset['name']}|{asset['size_bytes']}|[下载]({asset['url']})|")
    text='''# ORION 结构线已完成实验归档

本次按用户要求上传前面已保存的实验文件，**没有重新跑算法、没有更新正式100图成绩，也没有合并任何PR**。

## 下载与范围

大型ZIP已上传到本私有仓库的Release附件；小型CSV、报告、源码快照及图表保存在本目录。Release不是新算法的正式验收发布，也不是100图新成绩。

'''
    text+='[打开全部归档附件]('+manifest['release_url']+')\n\n'+'\n'.join(table)+'\n'
    text+='''
## 小型文件

- `pr30_code_reports_snapshot/`：此前代码/报告包的219个原始成员，包含完整聚合表和17张图；代码仅作为快照，不应用到公共实现。
- `aggregate_attachments/`：此前单独交付的完整逐次CSV、连续轨迹及报告。
- `pr31_repository_snapshot/`：PR31指定提交中的报告、21行逐图表、均值和原证据索引。
- `pr31_recovered_summary/`：上次中断后恢复的5个文件，只是恢复表和说明，不冒充完整原始包。
- `ARCHIVE_MEMBERS.csv`：已上传ZIP的成员与字节数索引。
- `PUBLISHED_MANIFEST.json`：真实Release附件ID、URL、大小、来源与缺失清单。

## 仍然缺失，不能声称已上传

1. `ORION_safe_refine_20260925_code_plans_report.zip`
2. `ORION_safe_refine_20260925_raw.zip`

PR31曾称这两包已作为会话附件交付，但当前运行环境与Library没有找回。此次不能补造其21个升级方案、98条种子池、42张轨迹图或完整官方响应。PR31分支中的历史文字在冻结快照里原样保留；其“已交付”表述不构成本次上传证明，以本目录缺失清单为准。

不能从汇总的32,870等分数反推出对应原始方案。续优化时只使用确实存在且能重新官方评估的plan，不拿本次缺失的文件路径当可用种子。

## 非侵入性

所有小型新增内容仅在本结果归档目录；未修改原图/config/官方评估器、公共solver/campaign、其他研究线或旧结果。临时接收工作流已从最终分支删除。归档传输run不是实验run。
'''
    if remote_errors:text+='\n额外早期artifact复制缺项：\n```json\n'+json.dumps(remote_errors,ensure_ascii=False,indent=2)+'\n```\n'
    (ROOT/'README.md').write_text(text,encoding='utf8')
    # Remove only our temporary transport files, never pre-existing experiment files.
    for transient in ('UPLOAD_SESSION.json','UPLOAD_COMPLETE.json','TRANSFER_RECEIVED.json'):
        (ROOT/transient).unlink(missing_ok=True)
    shutil.rmtree('.github/actions/orion-results-ingest')
    Path('.github/workflows/orion_results_archive.yml').unlink()
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','-A','--',str(ROOT),'.github/actions/orion-results-ingest','.github/workflows/orion_results_archive.yml')
    git('commit','-m','results(structure): archive available full evidence and explicitly record missing safe-refine packages')
    git('push','origin','HEAD:'+BRANCH)
    release=api(f"releases/{release['id']}",'PATCH',{'draft':False,'prerelease':True,'make_latest':'false',
       'body':'Previously completed ORION structure experiments, archived without rerunning. '+str(len(published)+len(extra))+' result assets. All ten available conversation files uploaded. Missing: the two PR31 safe-refine full code/plans and raw ZIPs. See '+str(ROOT)+'/PUBLISHED_MANIFEST.json and README in branch '+BRANCH+'. No automatic merge; not a new full-100 benchmark.'})
    print('PUBLISHED',release['html_url'],'commit',git('rev-parse','HEAD'),flush=True)
    print(json.dumps({'local_files':len(published),'prior_artifact_copies':len(extra),
       'local_bytes':manifest['uploaded_local_bytes'],'missing_files':len(manifest['missing']),
       'remote_archive_errors':len(remote_errors)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
