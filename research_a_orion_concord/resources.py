"""Admission feedback for real jobs: target 75% CPU and 75% RAM, no busy waiting."""
from __future__ import annotations
import os
import time
from pathlib import Path
try:
    import psutil
except ImportError:
    psutil=None


def capacity():
    cpu=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1
    quota=Path('/sys/fs/cgroup/cpu.max')
    if quota.exists():
        q,period=quota.read_text().split()
        if q!='max':cpu=min(cpu,float(q)/float(period))
    total=psutil.virtual_memory().total if psutil else None
    if total is None and os.name=='nt':
        import ctypes
        class M(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
                ('total','available','page','page_available','virtual','virtual_available','extended')]
        m=M();m.length=ctypes.sizeof(m)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):total=m.total
    if total is None:
        try:total=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
        except (OSError,ValueError,AttributeError):total=4*1024**3
    limit=Path('/sys/fs/cgroup/memory.max')
    if limit.exists() and limit.read_text().strip()!='max':total=min(total,int(limit.read_text()))
    return cpu,total

class Budget:
    def __init__(self,reserve=.25,max_workers=None):
        self.cpu,self.ram=capacity();self.reserve=reserve
        self.cpu_slots=max(1,int(self.cpu*(1-reserve)))
        if max_workers:self.cpu_slots=min(self.cpu_slots,max_workers)
        self.peak=256*1024**2;self.old_time=time.monotonic();self.old_cpu=None
        self.policy=dict(effective_cpus=self.cpu,total_memory_bytes=self.ram,
                         reserve_fraction=reserve,cpu_slots=self.cpu_slots)
        if psutil:psutil.cpu_percent(None)
    def sample(self,active):
        rss=0;peak=0;own_cpu=0.;stamp=time.monotonic()
        for task in active:
            try:
                if psutil:
                    p=psutil.Process(task['process'].pid);v=p.memory_info().rss
                    ct=p.cpu_times();total_cpu=ct.user+ct.system
                    prev,old_stamp=task.get('cpu_sample',(0.,task['start']))
                    own_cpu+=max(0.,total_cpu-prev)/max(.001,stamp-old_stamp)
                    task['cpu_sample']=(total_cpu,stamp)
                    v+=sum(c.memory_info().rss for c in p.children(recursive=True))
                elif os.name=='nt':
                    import ctypes
                    class C(ctypes.Structure):
                        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(k,ctypes.c_size_t) for k in
                         ('peak','rss','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile')]
                    c=C();c.cb=ctypes.sizeof(c)
                    fn=ctypes.windll.psapi.GetProcessMemoryInfo
                    fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
                    fn(ctypes.c_void_p(int(task['process']._handle)),ctypes.byref(c),c.cb);v=c.rss
                else:
                    v=int(Path(f'/proc/{task["process"].pid}/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                rss+=v;peak=max(peak,v);task['peak_rss']=max(task.get('peak_rss',0),v)
            except (OSError,ValueError,ProcessLookupError):pass
            except Exception:pass
        self.peak=max(self.peak,peak)
        current=Path('/sys/fs/cgroup/memory.current')
        if current.exists():used=int(current.read_text())
        elif psutil:used=psutil.virtual_memory().total-psutil.virtual_memory().available
        elif os.name=='nt':
            import ctypes
            class M(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
                    ('total','available','page','page_available','virtual','virtual_available','extended')]
            m=M();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));used=m.total-m.available
        else:used=rss
        load=psutil.cpu_percent(None) if psutil else None
        now=time.monotonic();stat=Path('/sys/fs/cgroup/cpu.stat')
        if stat.exists():
            stats=dict(x.split() for x in stat.read_text().splitlines());value=int(stats['usage_usec'])/1e6
            if self.old_cpu is not None:load=100*(value-self.old_cpu)/max(.001,(now-self.old_time)*self.cpu)
            self.old_cpu=value
        self.old_time=now
        available=max(0,self.ram*(1-self.reserve)-used)
        by_memory=len(active)+int(available/max(256*1024**2,self.peak*1.35))
        slots=min(self.cpu_slots,by_memory)
        if load is not None:
            other_cpu=max(0.,self.cpu*load/100-own_cpu)
            slots=min(slots,max(0,int(self.cpu*(1-self.reserve)-other_cpu+.15)))
        slots=max(0,slots)
        return slots,dict(time=now,cpu_percent=load,memory_used_bytes=used,
            memory_target_bytes=int(self.ram*(1-self.reserve)),active=len(active),
            own_rss_bytes=rss,observed_job_peak_bytes=self.peak,admission_slots=slots,own_cpu_cores=own_cpu)
