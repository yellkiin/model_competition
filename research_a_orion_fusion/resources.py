"""CPU/RAM-driven admission. Keep a 25% system headroom target, no load generator.

Standard library on Windows/Linux; no psutil/CUDA dependency. The memory budget
is based on whole-machine use (including other programs), not 75% of free RAM.
"""
from __future__ import annotations
import ctypes, math, os, signal, subprocess, time
from pathlib import Path


def cpus():
    count = os.cpu_count() or 1
    if hasattr(os,'sched_getaffinity'):
        count = min(count,len(os.sched_getaffinity(0)))
    try:
        quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota!='max':count=min(count,max(1,math.ceil(int(quota)/int(period))))
    except (OSError,ValueError):pass
    return count


def memory():
    if os.name=='nt':
        class Status(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
                ('total','avail','page_total','page_avail','virt_total','virt_avail','extended')]
        x=Status();x.length=ctypes.sizeof(x)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(x)):raise OSError('GlobalMemoryStatusEx')
        return x.total,x.avail
    fields={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2}
    total,avail=fields['MemTotal'],fields.get('MemAvailable',fields['MemFree'])
    try:
        lim=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        used=int(Path('/sys/fs/cgroup/memory.current').read_text())
        if lim!='max':total=min(total,int(lim));avail=min(avail,max(0,int(lim)-used))
    except (OSError,ValueError):pass
    return total,avail


def rss(pid):
    if os.name=='nt':
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        h=kernel.OpenProcess(0x0400|0x0010,False,pid)
        if not h:return 0
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in
                ('peak','working','poolpeak','pool','nonpeak','non','page','pagepeak')]
        c=Counters();c.cb=ctypes.sizeof(c)
        try:
            fn=ctypes.WinDLL('psapi').GetProcessMemoryInfo
            fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
            return c.working if fn(h,ctypes.byref(c),c.cb) else 0
        finally:kernel.CloseHandle(h)
    try:return int(next(x for x in Path(f'/proc/{pid}/status').read_text().splitlines() if x.startswith('VmRSS:')).split()[1])*1024
    except (OSError,StopIteration,ValueError):return 0


class Meter:
    def __init__(self):self.previous=None
    def sample(self):
        total,available=memory();busy=None
        if os.name=='nt':
            a,b,c=ctypes.c_ulonglong(),ctypes.c_ulonglong(),ctypes.c_ulonglong()
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(a),ctypes.byref(b),ctypes.byref(c)):
                ticks=(b.value+c.value,a.value)
            else:ticks=None
        else:
            parts=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
            ticks=(sum(parts),parts[3]+parts[4])
        if ticks and self.previous:
            delta=ticks[0]-self.previous[0]
            if delta>0:busy=max(0.,min(1.,1-(ticks[1]-self.previous[1])/delta))
        self.previous=ticks
        return {'cpu_fraction':busy,'logical_cpus':cpus(),'total_bytes':total,'available_bytes':available,'used_bytes':total-available}


class Admission:
    def __init__(self,max_workers=0,reserve=.25):
        self.reserve=reserve
        self.maximum=max(1,math.floor(cpus()*(1-reserve)))
        if max_workers:self.maximum=min(self.maximum,max_workers)
        self.target=min(2,self.maximum);self.peak=256*2**20;self.cool=0;self.meter=Meter()

    def update(self,active):
        sample=self.meter.sample()
        for entry in active:
            entry['peak_rss']=max(entry.get('peak_rss',0),rss(entry['proc'].pid))
            self.peak=max(self.peak,entry['peak_rss'])
        per_job=max(256*2**20,int(self.peak*1.3))
        room=sample['available_bytes']-int(sample['total_bytes']*self.reserve)
        memory_target=max(0,len(active)+int(room//per_job))
        cap=min(self.maximum,memory_target)
        busy=sample['cpu_fraction']
        if room<0 or (busy is not None and busy>1-self.reserve+.05):
            self.target=max(0,min(cap,self.target-1));self.cool=0
        elif (busy is None or busy<1-self.reserve-.07) and cap>self.target:
            self.cool+=1
            if self.cool>=3:self.target+=1;self.cool=0
        else:self.cool=0
        self.target=min(self.target,cap)
        # Restart after other applications release resources, but do not force
        # one worker through the RAM headroom when the machine is genuinely full.
        if not active and self.target==0 and cap>0 and (busy is None or busy<.75):self.target=1
        sample.update(target_workers=self.target,max_workers=self.maximum,observed_peak_rss=self.peak,
                      per_job_reserved_bytes=per_job,reserve_fraction=self.reserve)
        return sample


def terminate(proc):
    if proc.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    else:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.kill()
