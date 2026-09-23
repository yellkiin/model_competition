#!/usr/bin/env python3
"""C题：事件解析 + 合成验证 + RPCA 基线。

正式数据用法：
python experiments/c_pipeline.py VisualCogA_Task-1.mat --out c_out

无数据时可运行：
python experiments/c_pipeline.py --synthetic
"""

import argparse, json
from pathlib import Path
import numpy as np

def contiguous_onsets(x):
    nz=np.asarray(x)!=0
    return np.flatnonzero(nz & np.r_[True,~nz[:-1]])

def build_trial_table(viscue,tgtact,fs):
    cue_on=contiguous_onsets(viscue)
    resp_on=contiguous_onsets(tgtact)
    rows=[]
    for i,c in enumerate(cue_on):
        nxt=cue_on[i+1] if i+1<len(cue_on) else len(viscue)
        rs=resp_on[(resp_on>c)&(resp_on<nxt)]
        r=int(rs[0]) if len(rs) else None
        rows.append({
            "cue_sample":int(c),
            "cue":float(viscue[c]),
            "response_sample":r,
            "response":None if r is None else float(tgtact[r]),
            "rt_s":None if r is None else float((r-c)/fs),
            "timeout":r is None,
            "repeat_response":len(rs)>1,
        })
    return rows

def svt(M,tau):
    U,s,Vt=np.linalg.svd(M,full_matrices=False)
    s=np.maximum(s-tau,0)
    return (U*s)@Vt

def rpca_pcp(X,lam=None,mu=None,iters=500,tol=1e-6):
    m,n=X.shape
    lam=lam or 1/np.sqrt(max(m,n))
    norm2=np.linalg.norm(X,2)
    norminf=np.linalg.norm(X.ravel(),np.inf)/lam
    Y=X/max(norm2,norminf)
    mu=mu or 1.25/(norm2+1e-12)
    L=np.zeros_like(X); S=np.zeros_like(X)
    normX=np.linalg.norm(X,"fro")+1e-12
    for it in range(iters):
        L=svt(X-S+Y/mu,1/mu)
        T=X-L+Y/mu
        S=np.sign(T)*np.maximum(np.abs(T)-lam/mu,0)
        Z=X-L-S
        Y += mu*Z
        err=np.linalg.norm(Z,"fro")/normX
        if err<tol: break
        mu*=1.03
    return L,S,{"iterations":it+1,"residual":float(err)}

def epoch(data,onsets,fs,tmin=-0.2,tmax=0.8):
    a=int(round(tmin*fs)); b=int(round(tmax*fs))
    out=[]
    keep=[]
    for idx,o in enumerate(onsets):
        lo=o+a; hi=o+b
        if lo>=0 and hi<=data.shape[-1]:
            out.append(data[...,lo:hi])
            keep.append(idx)
    return np.asarray(out),keep

def synthetic(seed=7):
    rng=np.random.default_rng(seed)
    fs=256
    t=np.arange(-0.2,0.8,1/fs)
    clean=(1.2*np.exp(-0.5*((t-0.18)/0.045)**2)
           -0.8*np.exp(-0.5*((t-0.31)/0.06)**2)
           +0.9*np.exp(-0.5*((t-0.46)/0.08)**2))
    X=[]; C=[]
    for _ in range(80):
        amp=1+rng.normal(0,0.12); jitter=rng.normal(0,0.008)
        ct=(1.2*np.exp(-0.5*((t-(0.18+jitter))/0.045)**2)
           -0.8*np.exp(-0.5*((t-(0.31+jitter))/0.06)**2)
           +0.9*np.exp(-0.5*((t-(0.46+jitter))/0.08)**2))*amp
        x=ct+rng.normal(0,0.5,t.size)+rng.normal(0,0.25)*np.sin(2*np.pi*1.2*t)
        if rng.random()<0.28:
            c=int(rng.integers(30,t.size-30))
            x+=rng.uniform(3,7)*np.exp(-0.5*((np.arange(t.size)-c)/5)**2)
        X.append(x); C.append(ct)
    X=np.asarray(X); C=np.asarray(C)
    L,S,info=rpca_pcp(X)
    return {
        "raw_mse":float(np.mean((X-C)**2)),
        "rpca_mse":float(np.mean((L-C)**2)),
        "clean_peak":int(np.argmax(C.mean(0))),
        "raw_peak":int(np.argmax(X.mean(0))),
        "rpca_peak":int(np.argmax(L.mean(0))),
        "relative_mse_reduction":float(
            (np.mean((X-C)**2)-np.mean((L-C)**2))/np.mean((X-C)**2)),
        **info
    }

def load_mat(path):
    from scipy.io import loadmat
    m=loadmat(path,squeeze_me=True,struct_as_record=False)
    fs=float(np.asarray(m["SampleRate"]).squeeze())
    labels=[str(x).strip() for x in np.asarray(m["DataLabel"]).reshape(-1)]
    data=np.asarray(m["data"],dtype=float)
    return fs,labels,data

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mat",nargs="?",type=Path)
    ap.add_argument("--out",type=Path,default=Path("c_out"))
    ap.add_argument("--synthetic",action="store_true")
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)

    if args.synthetic or args.mat is None:
        res=synthetic()
        (args.out/"synthetic_validation.json").write_text(
            json.dumps(res,indent=2),encoding="utf-8")
        print(json.dumps(res,ensure_ascii=False,indent=2))
        return

    fs,labels,data=load_mat(args.mat)
    lower=[x.lower() for x in labels]
    def find(name):
        for i,x in enumerate(lower):
            if name.lower() in x:return i
        raise KeyError(name)
    i_vis=find("VisCue"); i_tgt=find("TgtAct")
    trials=build_trial_table(data[i_vis],data[i_tgt],fs)
    (args.out/"trial_table.json").write_text(
        json.dumps(trials,ensure_ascii=False,indent=2),encoding="utf-8")

    cue_on=np.array([x["cue_sample"] for x in trials],dtype=int)
    eeg=data[:3]
    ep,keep=epoch(eeg,cue_on,fs)
    # shape: trial, channel, time
    summary={"file":str(args.mat),"fs":fs,"labels":labels,
             "n_trials":len(trials),"n_epoched":len(keep),
             "timeouts":sum(x["timeout"] for x in trials),
             "repeat_responses":sum(x["repeat_response"] for x in trials)}
    if len(ep):
        # RPCA independently per channel across trial x time matrix
        den=np.empty_like(ep)
        sparse=np.empty_like(ep)
        infos=[]
        for ch in range(ep.shape[1]):
            L,S,info=rpca_pcp(ep[:,ch,:])
            den[:,ch,:]=L; sparse[:,ch,:]=S; infos.append(info)
        np.savez_compressed(args.out/"epochs_rpca.npz",
                            raw=ep,denoised=den,sparse=sparse,fs=fs)
        summary["rpca"]=infos
        summary["sparse_energy_ratio"]=float(
            np.sum(sparse**2)/(np.sum(ep**2)+1e-12))
    (args.out/"summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
