#!/usr/bin/env python3
"""Run one reviewed working script and record real execution; never grant visual approval."""
from __future__ import annotations

# Shared execution is explicit; direct legacy/maintenance CLIs must declare mode.
if __name__ == "__main__":
    import sys as _workflow_sys
    _workflow_sys.dont_write_bytecode = True
    from workspace_cli import require_cli_mode
    require_cli_mode(__file__)

import argparse,json,os,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from build_academic_figure_asset_index import safe,sha,write_json
from prepare_academic_figure_review import plan_figures,sidecar_path
from audit_visual_plan import audit

def execute(root,plan_path,figure_id,runtime,arguments,interpreter=None,allow_demo=False,timeout=600):
    root=Path(root).resolve();plan_path=safe(root,str(plan_path))
    from candidate_figures import audit_figure
    gate=audit_figure(root,plan_path,figure_id,'plan',runtime,allow_demo)
    if gate['status']!='PASS':raise ValueError('Plan gate failed: '+json.dumps(gate['failures'],ensure_ascii=False))
    plan=json.loads(plan_path.read_text(encoding='utf-8-sig'))
    refs=json.loads(sidecar_path(plan_path).read_text(encoding='utf-8-sig'))
    figure=next(f for f in plan_figures(plan) if f['figure_id']==figure_id)
    record=next(f for f in refs['figures'] if f['figure_id']==figure_id)
    script=safe(root,figure['script']);suffix=script.suffix.lower()
    executable=interpreter or (sys.executable if suffix=='.py' else shutil.which('Rscript') if suffix=='.r' else None)
    if not executable:raise ValueError('No verified Python/R interpreter for '+str(script))
    if not Path(executable).is_file():raise ValueError('Interpreter must be an existing absolute executable: '+executable)
    inputs={figure['script']}|{p['result_file'] for p in figure['panels']}
    outputs={figure['outputs']['vector'],figure['outputs']['preview'],figure['statistics_report']}
    if inputs&outputs:raise ValueError('Input/output path collision')
    before={p:sha(safe(root,p)) for p in inputs}
    from workspace_resources import dependencies
    resource_dependencies = dependencies(root,runtime,'academic')
    command=[str(Path(executable).resolve()),str(script),*arguments]
    run_path=safe(root,record['run_record_path']);run_path.parent.mkdir(parents=True,exist_ok=True)
    log_path=run_path.with_suffix('.log')
    if run_path in [safe(root,p) for p in inputs|outputs] or log_path in [safe(root,p) for p in inputs|outputs]:raise ValueError('Run record/log path collision')
    env=os.environ.copy();env.update(PYTHONUTF8='1',MPLBACKEND='Agg',PYTHONDONTWRITEBYTECODE='1')
    started=datetime.now(timezone.utc).isoformat();started_ns=time.time_ns()
    try:
        result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        code=result.returncode;log=result.stdout+'\n'+result.stderr
    except subprocess.TimeoutExpired as exc:
        code=124;log='TIMEOUT: '+str(exc)
    finished=datetime.now(timezone.utc).isoformat()
    log_path.write_text('COMMAND '+json.dumps(command,ensure_ascii=False)+'\nSTART '+started+'\n'+log+'\nRETURN_CODE '+str(code)+'\n',encoding='utf-8')
    files={p:sha(safe(root,p)) for p in inputs|outputs if safe(root,p).is_file()}
    mtimes={p:safe(root,p).stat().st_mtime_ns for p in outputs if safe(root,p).is_file()}
    failures=[]
    if code!=0:failures.append('Working script failed with return code '+str(code))
    if any(files.get(p)!=v for p,v in before.items()):failures.append('Inputs or working script changed during plotting')
    if set(mtimes)!=outputs or any(t<started_ns for t in mtimes.values()):failures.append('Missing output or output not written by this run')
    run={'schema_version':'2.0','runtime':runtime,'figure_id':figure_id,'command':command,'cwd':str(root),
         'resource_dependencies':resource_dependencies,
         'started_at':started,'finished_at':finished,'started_at_ns':started_ns,'returncode':code,
         'log_path':log_path.relative_to(root).as_posix(),'log_sha256':sha(log_path),'files':files,
         'input_sha256_before':before,'output_mtime_ns':mtimes,'status':'FAIL' if failures else 'EXECUTED_REVIEW_REQUIRED',
         'failures':failures,'assurance':'Real subprocess execution and current files recorded; no scientific or visual approval granted.'}
    write_json(run_path,run)
    return run

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',type=Path,default=Path('.'));p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--runtime',choices=['codex','claude'],required=True);p.add_argument('--figure-id',required=True)
    p.add_argument('--interpreter');p.add_argument('--allow-demo',action='store_true');p.add_argument('--timeout',type=int,default=600)
    p.add_argument('arguments',nargs=argparse.REMAINDER)
    a=p.parse_args();arguments=a.arguments[1:] if a.arguments[:1]==['--'] else a.arguments
    try:
        result=execute(a.project_root,a.plan,a.figure_id,a.runtime,arguments,a.interpreter,a.allow_demo,a.timeout)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 1 if result['failures'] else 0
    except Exception as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)},ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
