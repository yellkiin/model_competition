"""Restore a shard publication for collection without rewriting experiment data."""
import argparse,shutil,tempfile,zipfile
from pathlib import Path
from .io import read


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('publication');p.add_argument('--out',required=True)
    a=p.parse_args(argv);source=Path(a.publication).resolve();out=Path(a.out).resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Restore into a new/empty directory')
    out.mkdir(parents=True,exist_ok=True);info=read(source/'PUBLICATION.json')
    parts=info.get('archive_parts') or [{'path':info['archive']}]
    with tempfile.TemporaryFile() as combined:
        for part in parts:
            path=(source/part['path']).resolve()
            if source not in path.parents:raise ValueError('Archive path outside publication')
            if part.get('bytes') is not None and path.stat().st_size!=part['bytes']:raise ValueError(f'Truncated part: {path.name}')
            with path.open('rb') as f:shutil.copyfileobj(f,combined,4*2**20)
        combined.seek(0)
        with zipfile.ZipFile(combined) as z:
            for item in z.infolist():
                target=(out/item.filename).resolve()
                if target!=out and out not in target.parents:raise ValueError('Archive member outside destination')
            z.extractall(out)
    print(out/'run')
if __name__=='__main__':main()
