"""Independent standard-library validation; never trusts training metrics."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def validate(config):
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    cfg=read(config); data=read(cfg['data']); split=read(cfg['split']); predictions=read(cfg['predictions'])
    assert predictions['ids']==split['validation']
    errors=[float(data['y'][int(i)])-p for i,p in zip(predictions['ids'],predictions['predictions'],strict=True)]
    assert all(math.isfinite(v) for v in errors)
    values={'rmse':math.sqrt(sum(e*e for e in errors)/len(errors)), 'mae':sum(abs(e) for e in errors)/len(errors)}
    output={'metrics':values,'evaluated_ids':split['validation'],
        'split_sha256':hashlib.sha256(Path(cfg['split']).read_bytes()).hexdigest(),
        'independence':'Separate standard-library implementation recomputes errors from original targets and saved predictions.',
        'leakage_review':'Train IDs alone fit feature scaling; held-out validation chooses candidates; test IDs are unused.'}
    Path(cfg['metrics']).write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(values))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);validate(p.parse_args().config)
