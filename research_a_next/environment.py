"""Report Windows compatibility without installing/changing system environments."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import struct
import sys
from .official import write


def describe(allow_compatible=False):
    bits=struct.calcsize('P')*8
    memory=None
    if os.name=='nt':
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                      ('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),
                      ('page',ctypes.c_ulonglong),('page_available',ctypes.c_ulonglong),
                      ('virtual',ctypes.c_ulonglong),('virtual_available',ctypes.c_ulonglong),
                      ('extended_available',ctypes.c_ulonglong)]
        info=MEMORYSTATUSEX();info.length=ctypes.sizeof(info)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
            memory=dict(total_gib=round(info.total/2**30,2),available_gib=round(info.available/2**30,2))
    exact=sys.version_info[:3]==(3,12,5) and bits==64 and platform.python_implementation()=='CPython'
    compatible=(3,10)<=sys.version_info[:2]<(3,15) and bits==64 and platform.python_implementation()=='CPython'
    usable=exact or (allow_compatible and compatible)
    return dict(executable=sys.executable,python=platform.python_version(),implementation=platform.python_implementation(),
                bits=bits,platform=platform.platform(),logical_cpus=os.cpu_count(),memory=memory,
                preferred_python='CPython 3.12.5 x64',matches_preferred=exact,compatible_range=compatible,
                status='ready' if usable else 'local_agent_action_needed',cuda_required=False,third_party_packages=[],
                suggested_workers=1 if memory and memory['available_gib']<6 else 2,
                note='Other Python versions need explicit --allow-compatible and must be recorded; speed comparisons across CPUs concern evaluator cycles, not host wall time.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-compatible',action='store_true')
    a=p.parse_args();result=describe(a.allow_compatible);write(a.out,result);print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['status']!='ready':raise SystemExit(3)

if __name__=='__main__':main()
