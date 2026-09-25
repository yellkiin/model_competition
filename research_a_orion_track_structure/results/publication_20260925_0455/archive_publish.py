"""Archive already completed experiments. Does not run or import any solver.

Exact small attachment bytes arrive as a compressed transport. Existing private
GitHub artifacts are copied server-side to Release assets. Local-only archives
that could not be transferred are explicitly NOT called uploaded.
"""
from __future__ import annotations
import base64,csv,io,json,os,shutil,subprocess,tarfile,time,urllib.error,urllib.parse,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath

REPO='yellkiin/model_competition'
BRANCH='orion/archive-structure-results-20260925-0455'
TAG='orion-structure-results-20260925-0455'
ROOT=Path('research_a_orion_track_structure/results/publication_20260925_0455')
WORK=Path('/tmp/orion_existing_archive');WORK.mkdir(exist_ok=True)
API='https://api.github.com/repos/'+REPO
HEADERS={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'orion-requested-evidence-archive'}
EXPECTED={
 'aggregate_attachments/ORION_structure_recheck_per_case_20260925.csv':522407,
 'aggregate_attachments/ORION_structure_recheck_trajectory_20260925.csv':434696,
 'aggregate_attachments/ORION_structure_recheck_REPORT_20260925.md':14573,
 'aggregate_attachments/ORION_safe_refine_results_20260925.md':5585,
 'pr31_recovered_summary/RECOVERY_REPORT.md':5585,
 'pr31_recovered_summary/arithmetic_check.json':6400,
 'pr31_recovered_summary/per_case.csv':3666,
 'pr31_recovered_summary/recomputed_means.csv':590,
}
RUNS=[36085958693,36046726567,36048331790,36046094858,36046578817,36047055409]
FROZEN={'pr30':'a0da7b746449243e3c57fc23d54dab68756270bd','pr31':'9550ac947af13f14c775d0ef003ac4101188dd47'}
MISSING=[
 {'name':'ORION_structure_recheck_20260925_raw_local.zip','size_bytes':72928491,'status':'available_locally_not_uploaded','reason':'Container DNS/network blocks binary transfer. Local v3/v4 original responses are not replaced by CI results.'},
 {'name':'ORION_structure_recheck_20260925_code_reports.zip','size_bytes':1448778,'status':'exact_attachment_not_uploaded','reason':'Available locally; full aggregate CSV/report bytes uploaded separately and Git-tracked snapshots archived, but original 17 PNGs and exact 219-member attachment are not claimed uploaded.'},
 {'name':'ORION_safe_refine_20260925_code_plans_report.zip','status':'not_recovered','reason':'Unavailable in current runtime and Library. Cannot reconstruct selected plans, seed pool or original plots from score tables.'},
 {'name':'ORION_safe_refine_20260925_raw.zip','status':'not_recovered','reason':'Unavailable; PR31 original candidate responses and full trajectories remain missing.'},
]

def api(endpoint,method='GET',data=None,missing_ok=False):
    headers=dict(HEADERS);body=None
    if data is not None:body=json.dumps(data,ensure_ascii=False).encode();headers['Content-Type']='application/json'
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(API+'/'+endpoint,data=body,headers=headers,method=method),timeout=90) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==404 and missing_ok:return None
            if e.code in (429,500,502,503,504) and attempt<3:time.sleep(3*(attempt+1));continue
            raise RuntimeError(f'GitHub {method} {endpoint}: HTTP {e.code}') from None
    raise RuntimeError('GitHub retries exhausted')

def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
def dump(path,x):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def csvout(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def download_artifact(a,path):
    req=urllib.request.Request(API+f"/actions/artifacts/{a['id']}/zip",headers=HEADERS)
    try:r=urllib.request.build_opener(NoRedirect()).open(req,timeout=90)
    except urllib.error.HTTPError as e:
        if e.code not in (301,302,303,307,308):raise RuntimeError(f'Artifact {a["id"]} HTTP {e.code}') from None
        u=e.headers.get('Location','')
        if not u.startswith('https://'):raise RuntimeError('Unexpected artifact redirect')
        # Storage request has no repository Authorization header.
        r=urllib.request.urlopen(u,timeout=180)
    with r,path.open('wb') as f:shutil.copyfileobj(r,f,8*1024*1024)
    if path.stat().st_size!=a['size_in_bytes']:raise RuntimeError('Artifact download length mismatch')

def upload(release,path):
    assets=api(f"releases/{release['id']}/assets?per_page=100")
    existing=next((x for x in assets if x['name']==path.name),None)
    if existing:
        if existing['size']!=path.stat().st_size or existing['state']!='uploaded':raise RuntimeError('Existing asset mismatch; refusing overwrite '+path.name)
        return existing
    u=release['upload_url'].split('{')[0]+'?'+urllib.parse.urlencode({'name':path.name})
    headers={**HEADERS,'Content-Type':'application/octet-stream','Content-Length':str(path.stat().st_size)}
    with path.open('rb') as f:
        req=urllib.request.Request(u,data=f,headers=headers,method='POST')
        with urllib.request.urlopen(req,timeout=300) as response:a=json.load(response)
    if a['size']!=path.stat().st_size or a['state']!='uploaded':raise RuntimeError('Incomplete asset '+path.name)
    print('UPLOADED',path.name,a['size'],flush=True);return a

def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO or not api('').get('private'):raise RuntimeError('Expected private repository only')
    git('fetch','origin',BRANCH);git('merge','--ff-only','FETCH_HEAD')
    data=b''.join((ROOT/'_transfer'/f'aggregates.part{i:03d}.bin').read_bytes() for i in range(5))
    if len(data)!=61196:raise RuntimeError('Compressed attachment transfer length mismatch')
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as t:
        members=t.getmembers()
        if {m.name for m in members}!=set(EXPECTED):raise RuntimeError('Attachment allowlist mismatch')
        for m in members:
            p=PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or not m.isfile() or m.size!=EXPECTED[m.name]:raise RuntimeError('Invalid attachment member')
            target=ROOT.joinpath(*p.parts);target.parent.mkdir(parents=True,exist_ok=True)
            with t.extractfile(m) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
    dump(ROOT/'SMALL_ATTACHMENT_TRANSFER.json',{'encoding':'five binary chunks of an XZ tar archive','files':[{'path':k,'size_bytes':v} for k,v in EXPECTED.items()],'new_experiments':0})
    print('RESTORED_EXACT_SMALL_FILES',len(EXPECTED),flush=True)
    snapshots=[]
    for rel in ('review/REPORT.md','review/per_case.csv','review/means.csv','EVIDENCE_INDEX.json'):
        p='research_a_orion_track_structure/results/safe_refine_20260925/'+rel
        obj=api('contents/'+p+'?ref='+FROZEN['pr31'])
        dest=ROOT/'pr31_repository_snapshot'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(base64.b64decode(obj['content']));snapshots.append({'source_commit':FROZEN['pr31'],'path':p,'snapshot':str(dest)})
    releases=api('releases?per_page=100');release=next((r for r in releases if r['tag_name']==TAG),None)
    if not release:
        release=api('releases','POST',{'tag_name':TAG,'target_commitish':BRANCH,'name':'ORION structure: preserved experiment evidence (2026-09-25)','body':'Archive of previous results only; not a new benchmark. Some local-only or missing archives remain pending.','draft':True,'prerelease':True,'make_latest':'false'})
    assets=[];errors=[];members=[]
    def preserve(path,source):
        a=upload(release,path)
        assets.append({'name':path.name,'asset_id':a['id'],'url':a['browser_download_url'],'size_bytes':a['size'],'state':a['state'],**source})
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for m in z.infolist():members.append({'archive':path.name,'member':m.filename,'size_bytes':m.file_size,'compressed_bytes':m.compress_size})
    for run_id in RUNS:
        listing=api(f'actions/runs/{run_id}/artifacts?per_page=100',missing_ok=True)
        if not listing or not listing.get('artifacts'):
            errors.append({'run_id':run_id,'status':'no_accessible_artifact'});continue
        dump(ROOT/'source_runs'/f'{run_id}_artifacts.json',listing)
        for a in listing['artifacts']:
            if a.get('expired'):
                errors.append({'run_id':run_id,'artifact_id':a['id'],'status':'expired'});continue
            if len(assets)>=90:raise RuntimeError('Unexpected asset count')
            path=WORK/f'run_{run_id}_artifact_{a["id"]}.zip'
            try:
                download_artifact(a,path)
                preserve(path,{'source':'existing_github_artifact','source_run_id':run_id,'source_artifact_id':a['id'],'source_artifact_name':a['name']})
            except Exception as e:errors.append({'run_id':run_id,'artifact_id':a['id'],'status':'copy_failed','error':str(e)})
    for label,commit in FROZEN.items():
        try:
            git('fetch','--no-tags','--depth=1','origin',commit)
            dest=WORK/f'{label.upper()}_git_snapshot_{commit[:12]}.zip'
            git('archive','--format=zip','--output='+str(dest),commit,'research_a_orion_track_structure')
            preserve(dest,{'source':'immutable_repository_snapshot','source_commit':commit,'not_original_conversation_code_zip':True})
        except Exception as e:errors.append({'snapshot':label,'commit':commit,'status':'copy_failed','error':str(e)})
    smallzip=WORK/'ORION_exact_aggregate_CSV_reports_20260925.zip'
    with zipfile.ZipFile(smallzip,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for rel in EXPECTED:z.write(ROOT/rel,rel)
    preserve(smallzip,{'source':'original_small_attachment_bytes','original_members':8,'not_original_full_raw_archive':True})
    for rel in EXPECTED:
        if rel.startswith('aggregate_attachments/'):
            preserve(ROOT/rel,{'source':'exact_original_conversation_attachment','evidence':'aggregate_table_or_report_only'})
    csvout(ROOT/'ARCHIVE_MEMBERS.csv',members)
    dump(ROOT/'PENDING_UPLOADS.json',MISSING)
    csvout(ROOT/'ASSETS.csv',assets)
    manifest={'schema_version':2,'created_at_utc':datetime.now(timezone.utc).isoformat(),'repository':REPO,'branch':BRANCH,'release_tag':TAG,'release_id':release['id'],'release_url':'https://github.com/'+REPO+'/releases/tag/'+TAG,'purpose':'Archival copy only. No algorithms run, no score changes, no merge.','publication_workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'new_experiments':0,'asset_count':len(assets),'asset_bytes':sum(a['size_bytes'] for a in assets),'assets':assets,'small_attachment_files_uploaded':8,'frozen_snapshots':snapshots,'pending_or_missing':MISSING,'remote_copy_errors':errors,'all_previous_results_uploaded':False,'raw_ci_original_wrapper_transmitted':False,'raw_ci_members_archived_separately':sum(a.get('source_run_id')==36085958693 for a in assets),'temporary_workflow_cleanup':'performed by connector after this run; not experiment code'}
    dump(ROOT/'PUBLISHED_MANIFEST.json',manifest)
    lines=['# ORION结构线：既有结果归档（部分交付）','','本次只归档前面已经完成的实验，**没有新跑算法、没有更新正式成绩、没有合并PR**。','','## 已真正上传','','[打开本私有仓库归档下载页]('+manifest['release_url']+')','','|附件|字节数|下载|','|---|---:|---|']
    for a in assets:lines.append('|'+a['name']+'|'+str(a['size_bytes'])+'|[下载]('+a['url']+')|')
    lines+=['','完整聚合CSV和报告也可在 `aggregate_attachments/` 直接查看，恢复摘要在 `pr31_recovered_summary/`。PR31原提交的四个文件冻结在 `pr31_repository_snapshot/`；不把其中历史“完整包已交付”文字当作本次上传证据。','',
      'PR30七图CI包按原GitHub artifact分别转存，保留原始成员；不是声称已传输会话中的178MB外层ZIP。PR30/31 Git源码快照不是会话代码ZIP，也不能代替本地未上传响应或原始图片。','',
      '## 仍未全部上传','',
      '- **本地存在但网络传输失败**：`ORION_structure_recheck_20260925_raw_local.zip`（72,928,491字节）。本地v3/v4原始响应不能用CI原始包代替。',
      '- **本地代码/报告ZIP未原样上传**：`ORION_structure_recheck_20260925_code_reports.zip`（1,448,778字节）。完整两份聚合CSV和报告已单独上传；Git中的代码结果已另做快照，但不能声称原17张PNG或全部219成员已上传。',
      '- **未找回**：`ORION_safe_refine_20260925_code_plans_report.zip` 与 `ORION_safe_refine_20260925_raw.zip`。不从分数补造21个最终方案、98条种子池、42张图和官方响应。','',
      '以上状态详见 `PENDING_UPLOADS.json`。最新轮摘要存在，不意味着最新原始计划可下载。继续研究只能使用确实存在并能重新原评估的plan。','',
      '## 可追溯清单','',
      '`PUBLISHED_MANIFEST.json`列出真实Release附件ID、URL和大小。`ARCHIVE_MEMBERS.csv`列出ZIP成员。`source_runs/`是源artifact信息。传输工作流ID只标识归档，不是实验ID。','',
      '仅新增本结果目录；未修改官方图/config/评估器、公共solver/campaign、其他研究线或旧结果。不自动合并。']
    if errors:lines+=['','## 未取得的远端项','```json',json.dumps(errors,ensure_ascii=False,indent=2),'```']
    (ROOT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    # Contents-only job commits results; the connector removes the temporary workflow later.
    for p in (ROOT/'_transfer').glob('*.bin'):p.unlink()
    (ROOT/'UPLOAD_SESSION.json').unlink(missing_ok=True)
    git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','-A','--',str(ROOT))
    git('commit','-m','results(structure): preserve cloud raw artifacts and exact local CSVs; state remaining gaps')
    git('push','origin','HEAD:'+BRANCH)
    release=api(f'releases/{release["id"]}','PATCH',{'draft':False,'prerelease':True,'make_latest':'false','body':f'Archive of already completed ORION structure experiments. {len(assets)} downloadable assets. Exact aggregate CSVs/reports and immutable Git snapshots included. IMPORTANT: local v3/v4 raw ZIP and original code-report ZIP are not transferred; two PR31 complete ZIPs were not recovered. This is a partial evidence archive, not a new benchmark or automatic merge. See {ROOT}/PUBLISHED_MANIFEST.json in branch {BRANCH}.'})
    print('PUBLISHED_RELEASE',release['html_url'],flush=True)
    print(json.dumps({'assets':len(assets),'bytes':manifest['asset_bytes'],'errors':errors,'pending':len(MISSING),'commit':git('rev-parse','HEAD')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
