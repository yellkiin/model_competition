"""Join ordered release parts; preserve the original standard transfer format."""
import json
from pathlib import Path
r=Path(__file__).resolve().parent
m=json.loads((r/'TRANSFER_PARTS.json').read_text(encoding='utf8'))
out=r/m['archive_name']
if out.parent!=r or out.exists():raise ValueError('Output must be a new file beside the parts')
for p in m['parts']:
 f=r/p['name']
 if f.parent!=r or f.stat().st_size!=p['bytes']:raise ValueError('Missing or wrong-size part: '+p['name'])
with out.open('xb') as dst:
 for p in m['parts']:
  with (r/p['name']).open('rb') as src:
   while True:
    b=src.read(1024*1024)
    if not b:break
    dst.write(b)
if out.stat().st_size!=m['archive_bytes']:raise ValueError('Reconstructed size differs')
print(out)
