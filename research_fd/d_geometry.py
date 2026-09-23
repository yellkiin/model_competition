"""Raster cell traversal for native-CRS polylines; retain corner contacts."""
import math
import numpy as np

def cells(a,b,shape):
    a=np.asarray(a,float);b=np.asarray(b,float);h,w=shape;delta=b-a
    if np.any(np.minimum(a,b)<0) or np.any(np.maximum(a,b)>[w,h]): raise ValueError('segment outside DEM')
    events={0.,1.}
    for k in (0,1):
        if delta[k]!=0:
            for boundary in range(math.ceil(min(a[k],b[k])),math.floor(max(a[k],b[k]))+1):
                t=(boundary-a[k])/delta[k]
                if 0<t<1: events.add(float(t))
    events=sorted(events);out={}
    def add(t,lo,hi):
        choices=[]
        for v,size in zip(a+t*delta,(w,h)):
            near=round(v);ii=[near-1,near] if abs(v-near)<1e-10 else [math.floor(v)]
            choices.append([i for i in ii if 0<=i<size])
        for c in choices[0]:
            for r in choices[1]:
                prev=out.get((r,c),(lo,hi));out[(r,c)]=(min(lo,prev[0]),max(hi,prev[1]))
    for t in events:add(t,t,t)
    for lo,hi in zip(events[:-1],events[1:]):add((lo+hi)/2,lo,hi)
    return out
