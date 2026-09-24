"""Persistent calls to unmodified official functions; isolated and killable."""
from __future__ import annotations
import contextlib
import gzip
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import traceback


def dump(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for attempt in range(6):
        try:tmp.replace(path);return
        except PermissionError:
            if sys.platform!='win32' or attempt==5:raise
            time.sleep(.05*(attempt+1))


def compressed(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf-8',compresslevel=1) as f:
        json.dump(value,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    tmp.replace(path)


def settings(config):
    sections={};active=''
    for line in Path(config).read_text(encoding='utf-8-sig').splitlines():
        line=line.split('#',1)[0].strip()
        if not line:continue
        if line.startswith('['):active=line[1:-1];sections[active]={}
        else:
            k,v=line.split();sections[active][k]=int(v)
    return dict(capacity=sections['capacity'],bandwidth=sections['bandwidth']['bandwidth'],
        **sections['multicore_scene_a'],**sections['multicore_scene_b'],**sections['problem_3'])


def child(code,graph,config):
    sys.path.insert(0,str(Path(code).resolve()))
    from contest_io import _read_json
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b,read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3,read_cache_config
    from singlecore_evaluate import evaluate_singlecore
    raw=_read_json(graph)
    base=read_evaluation_config(config);a=read_scene_a_config(config);b=read_scene_b_config(config);c=read_cache_config(config)
    funcs={0:evaluate_singlecore,1:evaluate_scene_a,2:evaluate_scene_b,3:evaluate_problem_3}
    for line in sys.stdin:
        st=time.perf_counter()
        try:
            req=json.loads(line);q=req['q'];kwargs=dict(base)
            if q in (0,1):kwargs.update(cross_core_wait=a['task_cross_core_wait_cycles'],same_core_wait=a['task_same_core_wait_cycles'])
            else:kwargs['cross_core_copy_delay']=b['cross_core_copy_delay_cycles']
            if q==3:kwargs.update(c)
            plan=None if q==0 else _read_json(req['plan'])
            # Evaluator diagnostics cannot corrupt the parent/child protocol.
            with contextlib.redirect_stdout(sys.stderr):
                result=funcs[q](raw,**kwargs) if q==0 else funcs[q](raw,plan,**kwargs)
            elapsed=time.perf_counter()-st
            if not math.isfinite(result['makespan']) or result['makespan']<0:raise ValueError('invalid official makespan')
            compressed(req['raw'],result)
            move=result.get('data_movement_bytes',{});cache=result.get('cache_stats',{})
            hit=cache.get('hit_bytes',0);miss=cache.get('miss_bytes',0)
            reply=dict(status='ok',makespan=result['makespan'],official_seconds=elapsed,
                added_copy_bytes=move.get('added_copy_bytes'),partition_added_copy_bytes=move.get('partition_added_copy_bytes'),
                spill_added_copy_bytes=move.get('spill_added_copy_bytes'),scheduled_copy_bytes=move.get('scheduled_copy_bytes'),
                cache_hit_bytes=hit,cache_byte_hit_rate=hit/(hit+miss) if hit+miss else None,
                core_end={str(x['core_id']):max((op['end'] for op in x.get('ops',[])),default=0)
                          for x in result.get('per_core_timeline',[])})
        except Exception as e:
            reply=dict(status='error',error=str(e),traceback=traceback.format_exc(),official_seconds=time.perf_counter()-st)
        print(json.dumps(reply,ensure_ascii=False,allow_nan=False),flush=True)


class Session:
    def __init__(self,code,graph,config,directory):
        self.args=[str(code),str(graph),str(config)];self.directory=Path(directory);self.proc=None;self.log=None

    def start(self):
        self.events=queue.Queue()
        self.log=(self.directory/'official_stderr.log').open('a',encoding='utf-8')
        env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
        self.proc=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',__name__.rsplit('.',1)[0]+'.session',*self.args],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',env=env)
        proc=self.proc;events=self.events
        def reader():
            try:
                for line in proc.stdout:events.put(line)
            finally:events.put(None)
        self.thread=threading.Thread(target=reader,daemon=True);self.thread.start()

    def evaluate(self,q,plan_path,raw_path,timeout):
        st=time.monotonic()
        try:
            if self.proc is None:self.start()
            self.proc.stdin.write(json.dumps(dict(q=q,plan=str(plan_path),raw=str(raw_path)))+'\n');self.proc.stdin.flush()
            line=self.events.get(timeout=max(.01,timeout-(time.monotonic()-st)))
            if line is None:raise RuntimeError('official process exited; see official_stderr.log')
            result=json.loads(line)
        except queue.Empty:
            result=dict(status='timeout',error='per-evaluation wall limit');self.close()
        except (OSError,ValueError,RuntimeError) as e:
            result=dict(status='error',error=str(e));self.close()
        result['call_wall_seconds']=time.monotonic()-st
        return result

    def close(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:self.proc.wait(timeout=1.)
                except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=2.)
            if self.proc.stdin:self.proc.stdin.close()
            self.thread.join(timeout=1.)
            if self.proc.stdout:self.proc.stdout.close()
            self.proc=None
        if self.log:self.log.close();self.log=None


if __name__=='__main__':child(*sys.argv[1:])
