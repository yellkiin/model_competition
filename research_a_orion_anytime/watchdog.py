"""Whole-campaign watchdog, including parsing, verification and child solvers.

Invoke instead of campaign for the 12-hour stop policy. This stops owned process
children, not unrelated experiments. OS termination latency is separately reported.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .worker import atomic_json


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--out',required=True);p.add_argument('--hours',type=float,default=11.5)
    a,_=p.parse_known_args(argv)
    if not 0<a.hours<=12:raise ValueError('hours must be positive and at most 12')
    root=Path(a.out).resolve();root.mkdir(parents=True,exist_ok=True)
    started=time.time();manifest=root/'campaign.json'
    deadline=started+a.hours*3600
    if manifest.exists():deadline=min(deadline,json.loads(manifest.read_text(encoding='utf8'))['deadline_epoch'])
    remaining=deadline-time.time()
    if remaining<=0:raise TimeoutError('Campaign deadline already expired; no automatic reset')
    kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
    child=subprocess.Popen([sys.executable,'-m','research_a_orion_anytime.campaign',*argv],**kwargs)
    expired=False
    try:child.wait(timeout=remaining)
    except (subprocess.TimeoutExpired,KeyboardInterrupt):
        expired=time.time()>=deadline
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=20)
        else:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        child.wait()
    atomic_json(root/'watchdog_status.json',dict(expired=expired,started_epoch=started,deadline_epoch=deadline,
                finished_epoch=time.time(),exit_code=child.returncode,
                note='Deadline stops computation; it does not guarantee all mandatory results have finished'))
    return 124 if expired else child.returncode

if __name__=='__main__':raise SystemExit(main())
