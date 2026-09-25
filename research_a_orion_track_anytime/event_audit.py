"""Interpret actual official events; no replacement cache simulator."""
from collections import OrderedDict
from .trace import operations

def inspect(raw):
    ops=operations(raw);resident=OrderedDict();used=0;hits=misses=inserts=hit_refills=evictions=0
    for i,e in enumerate(raw['cache_events']):
        op=ops[e['core_id'],e['op_id']];tid=e['tensor_id'];size=e['size_bytes']
        if e['event'] in ('hit','miss'):
            if e['time']!=op['start']:raise ValueError('lookup not at issue')
            if (e['event']=='hit')!=(tid in resident):raise ValueError('lookup residency mismatch')
            if e['event']=='hit':hits+=1
            else:misses+=1
        elif e['event']=='insert':
            if e['time']!=op['end']:raise ValueError('fill not at completion')
            if tid in resident:raise ValueError('resident key refreshed by insert')
            displaced=[]
            while resident and used+size>raw['cache_capacity_bytes']:
                key,val=resident.popitem(last=False);used-=val;displaced.append(key)
            if displaced!=e.get('evicted_tensor_ids',[]):raise ValueError('not FIFO oldest-first eviction')
            if size>raw['cache_capacity_bytes']:raise ValueError('oversized insert')
            resident[tid]=size;used+=size;inserts+=1;evictions+=len(displaced);hit_refills+=bool(op.get('cache_hit'))
    return dict(events=len(raw['cache_events']),lookup_at_issue=True,fill_at_completion=True,fifo_oldest_eviction=True,hit_does_not_refresh=True,hits=hits,misses=misses,inserts=inserts,evictions=evictions,completion_of_previously_hit_read_refills=hit_refills,final_resident_bytes=used)
