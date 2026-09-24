"""Synthetic regression DEMO; portable training source, no template imports."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import pickle
import time
import numpy as np


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def dump(p, x):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def train(cfg):
    import torch
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import RandomForestRegressor
    torch.set_num_threads(1)
    torch.manual_seed(cfg['seed'])
    np.random.seed(cfg['seed'])
    data = load(cfg['data'])
    split = load(cfg['split'])
    x, y = np.array(data['x'], dtype=np.float32), np.array(data['y'], dtype=np.float32)
    train_ids, val_ids = [int(i) for i in split['train']], [int(i) for i in split['validation']]
    mu, sd = x[train_ids].mean(0), x[train_ids].std(0)
    z = (x - mu) / np.maximum(sd, 1e-6)
    t0 = time.perf_counter()
    history, epochs, best_epoch = [], 1, 1
    if cfg['kind'] == 'ridge':
        model = Ridge(alpha=1).fit(z[train_ids], y[train_ids])
        predictions = model.predict(z[val_ids])
        parameters = z.shape[1] + 1
    elif cfg['kind'] == 'rf':
        model = RandomForestRegressor(n_estimators=50,max_depth=6,min_samples_leaf=3,random_state=cfg['seed'],n_jobs=1).fit(z[train_ids],y[train_ids])
        predictions = model.predict(z[val_ids])
        parameters = sum(t.tree_.node_count for t in model.estimators_)
    else:
        model = torch.nn.Sequential(torch.nn.Linear(x.shape[1],16),torch.nn.ReLU(),
                                    torch.nn.Linear(16,8),torch.nn.ReLU(),torch.nn.Linear(8,1))
        opt = torch.optim.Adam(model.parameters(),lr=.01)
        xx=torch.tensor(z); yy=torch.tensor(y[:,None])
        best, bad, state = float('inf'), 0, None
        for epoch in range(1,81):
            model.train()
            order=np.random.permutation(train_ids)
            for start in range(0,len(order),32):
                batch=order[start:start+32]
                opt.zero_grad()
                loss=torch.nn.functional.mse_loss(model(xx[batch]),yy[batch])
                loss.backward(); opt.step()
            model.eval()
            with torch.no_grad():
                error=float(torch.nn.functional.mse_loss(model(xx[val_ids]),yy[val_ids]))
            history.append({'epoch':epoch,'validation_mse':error})
            if error < best-1e-6:
                best,bad,state,best_epoch=error,0,copy.deepcopy(model.state_dict()),epoch
            else:
                bad+=1
            if bad>=10:
                break
        epochs=epoch
        model.load_state_dict(state)
        with torch.no_grad():
            predictions=model(xx[val_ids]).numpy().ravel()
        parameters=sum(p.numel() for p in model.parameters())
    checkpoint=Path(cfg['checkpoint']); checkpoint.parent.mkdir(parents=True,exist_ok=True)
    with checkpoint.open('wb') as f:
        pickle.dump({'model':model,'mean':mu,'std':sd},f)
    dump(cfg['predictions'],{'ids':split['validation'],'predictions':[float(v) for v in predictions]})
    dump(cfg['training_record'],dict(seed=cfg['seed'],parameters=parameters,batch_size=32,input_shape=[len(train_ids),x.shape[1]],
        best_epoch=best_epoch,epochs=epochs,early_stopping={'patience':10,'triggered':epochs<80},
        device='cpu',peak_memory_mb=0,elapsed_seconds=time.perf_counter()-t0,history=history,
        preprocessing='mean/std fitted only to train IDs',torch_version=torch.__version__))
    print(json.dumps({'kind':cfg['kind'],'epochs':epochs,'best_epoch':best_epoch,'parameters':parameters}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
    train(load(a.config))
