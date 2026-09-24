"""Receive two final transfer archives into new, disjoint roots."""
import json
import sys
from pathlib import Path
from build_snapshot import BASE,REPO,read,put,utc
from research_a_orion_anytime.transfer import main as transfer

root=BASE/'team_collection_20260924'
if root.exists():raise ValueError('Collection root must be new')
root.mkdir()
remote=BASE/'pr19_resolution/research_a_orion_anytime/team_results/day01/shard_1/final'
meta=read(remote/'ARCHIVE_PARTS.json')
archive1=root/meta['archive_name']
if archive1.parent!=root:raise ValueError('Archive output path')
for p in meta['parts']:
    f=remote/p['name']
    if f.parent!=remote or not f.exists() or f.stat().st_size!=p['bytes']:raise ValueError('Missing / wrong-size part')
with archive1.open('xb') as out:
    for p in meta['parts']:
        with (remote/p['name']).open('rb') as src:
            while True:
                b=src.read(1024**2)
                if not b:break
                out.write(b)
if archive1.stat().st_size!=meta['archive_bytes']:raise ValueError('Archive byte count')
archive0=BASE/'phase_publication_20260924/artifacts/shard_0/final/team_day01_shard0_final.zip'
for n,a in enumerate([archive0,archive1]):
    transfer(['unpack','--root',str(root/f'shard_{n}/auto'),'--zip',str(a)])
    print('UNPACKED',n,flush=True)
    idx=read(root/f'shard_{n}/auto/final_index.json')
    wanted={(f'case_{i:03d}',q,c) for i in range(n+1,101,2) for q,c in [(0,1),(3,1)]+[(q,c) for q in [1,2,3] for c in [2,3,4,5]]}
    actual=[tuple(x['key']) for x in idx['chosen']]
    if len(actual)!=700 or set(actual)!=wanted:raise ValueError('Main keys not a complete disjoint shard')
    pairs=[tuple(x['key']) for x in idx['pairs']]
    if len(pairs)!=250 or set(pairs)!={k for k in wanted if k[1]==3}:raise ValueError('Pair keys')
    for entry in idx['chosen']+idx['pairs']:
        p=Path(entry['summary'])
        if not p.is_relative_to(root/f'shard_{n}/auto') or not p.exists():raise ValueError('Unrelocated result path')
        if read(p)['status']!='ok':raise ValueError('Selected result not valid')
put(root/'RECEIPT.json',dict(received_at_utc=utc(),shard_1_remote_commit='8c4f60ee33fdc3cbf92b894517f75b9670ec08df',
    archives=[str(archive0),str(archive1)],main_keys=[700,700],pair_keys=[250,250],disjoint=True,independent_collection_pending=True))
print('READY_FOR_ORIGINAL_COLLECT',flush=True)
