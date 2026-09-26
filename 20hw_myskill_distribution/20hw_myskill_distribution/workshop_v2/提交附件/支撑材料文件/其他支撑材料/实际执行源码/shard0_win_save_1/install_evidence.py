"""Place an already delivered raw ZIP into ordinary <=40MiB review parts."""
from __future__ import annotations
import argparse,json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('--out',default=str(Path(__file__).parent/'evidence/raw'));a=p.parse_args()
    src=Path(a.archive);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if list(out.glob('evidence.zip.part*')):raise FileExistsError('Review parts already installed')
    parts=[]
    with src.open('rb') as f:
        i=0
        while True:
            b=f.read(40*2**20)
            if not b:break
            i+=1;name=f'evidence.zip.part{i:03d}';(out/name).write_bytes(b);parts.append({'file':name,'bytes':len(b)})
    (out/'PARTS.json').write_text(json.dumps({'encoding':'concatenated ordinary ZIP bytes','parts':parts,'total_bytes':src.stat().st_size},indent=2))
    print('Installed',len(parts),'parts')
if __name__=='__main__':main()
