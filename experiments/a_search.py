#!/usr/bin/env python3
"""A题：基于官方评估器的候选生成与搜索骨架。

用法示例：
python experiments/a_search.py graph.json --problem 2 --cores 4 --budget 300

该脚本假设从仓库根目录运行，并会自动定位官方附件 code/。
正式图未随 Git 提交，因此本文件只提供可直接在本地数据上运行的实现。
"""

import argparse, hashlib, json, math, random, subprocess, sys, tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A_DIR = ROOT / "题目" / "A题" / "通用神经网络处理器下的多核调度问题  附件"
CODE_DIR = A_DIR / "code"
DATA_DIR = A_DIR / "data"
sys.path.insert(0, str(CODE_DIR))

from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes,
    _random_topological_order, validate_multicore_plan
)

EXCLUDED = {"COPY_IN", "COPY_OUT"}

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def eligible_ops(graph):
    return [op["id"] for op in graph["ops"] if op.get("op") not in EXCLUDED]

def deterministic_topo(graph):
    preds, succs = _build_op_adjacency(graph)
    ids = sorted(eligible_ops(graph))
    cp, cs = _contract_excluded_copy_nodes(ids, succs)
    return _random_topological_order(ids, cp, cs, random.Random(0))

def topo_blocks(graph, block_size):
    topo = deterministic_topo(graph)
    mapping = {}
    for i, op in enumerate(topo):
        mapping[op] = i // block_size
    return mapping

def op_cycles(graph):
    return {op["id"]: op.get("cycles", 0) for op in graph["ops"]}

def build_tensor_edges(graph):
    ops = {op["id"] for op in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    prod, cons = defaultdict(set), defaultdict(set)
    direct = []
    for e in graph["edges"]:
        a,b=e["source"],e["target"]
        if a in ops and b not in ops: prod[b].add(a)
        elif a not in ops and b in ops: cons[a].add(b)
        elif a in ops and b in ops: direct.append((a,b,0))
    out=[]
    for tid, ps in prod.items():
        size=tensors.get(tid,{}).get("size",0)
        for p in ps:
            for c in cons.get(tid,()):
                if p!=c and p in ops and c in ops:
                    out.append((p,c,size,tid))
    return out

def assign_blocks(graph, mapping, cores, eps=0.15, seed=0):
    """Greedy epsilon-constraint assignment.

    首先保证单核估计负载尽量不超过 (1+eps)*ideal；
    在满足条件的 core 中优先放到能减少 tensor cut bytes 的位置。
    """
    rng=random.Random(seed)
    cyc=op_cycles(graph)
    edges=build_tensor_edges(graph)
    blocks=sorted(set(mapping.values()))
    nodes={b:[] for b in blocks}
    for op,b in mapping.items(): nodes[b].append(op)
    weight={b:sum(cyc.get(o,0) for o in nodes[b]) for b in blocks}
    ideal=sum(weight.values())/cores
    limit=(1+eps)*ideal
    core_load=[0]*cores
    block_core={}
    adjacency=defaultdict(list)
    for u,v,size,tid in edges:
        bu,bv=mapping.get(u),mapping.get(v)
        if bu!=bv:
            adjacency[bu].append((bv,size))
            adjacency[bv].append((bu,size))

    order=sorted(blocks,key=lambda b:-weight[b])
    for b in order:
        feasible=[c for c in range(cores) if core_load[c]+weight[b] <= limit]
        if not feasible:
            feasible=list(range(cores))
        scored=[]
        for c in feasible:
            saved=sum(sz for nb,sz in adjacency[b] if block_core.get(nb)==c)
            overload=max(0,core_load[c]+weight[b]-limit)
            scored.append((-saved, overload, core_load[c], rng.random(), c))
        c=min(scored)[-1]
        block_core[b]=c
        core_load[c]+=weight[b]

    schedules=[[] for _ in range(cores)]
    for b in sorted(blocks):
        schedules[block_core[b]].append(b)
    plan={"node_to_subgraph":{str(k):v for k,v in mapping.items()},
          "core_schedules":schedules}
    validate_multicore_plan(graph,plan)
    return plan

def canonical(plan):
    raw=json.dumps(plan,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()

def evaluator_script(problem):
    return CODE_DIR / f"multicore_cut_evaluate_problem_{problem}.py"

def evaluate(graph_path, plan, problem, config):
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"plan.json"
        p.write_text(json.dumps(plan,ensure_ascii=False),encoding="utf-8")
        cmd=[sys.executable,str(evaluator_script(problem)),
             str(graph_path),str(p),"--config",str(config)]
        cp=subprocess.run(cmd,capture_output=True,text=True)
        if cp.returncode!=0:
            return {"ok":False,"stderr":cp.stderr[-4000:]}
        # 评估器会打印/写结果；为了兼容官方脚本版本，从 stdout 中抓最后一个 JSON。
        candidates=[]
        for line in cp.stdout.splitlines():
            line=line.strip()
            if line.startswith("{") and line.endswith("}"):
                try: candidates.append(json.loads(line))
                except Exception: pass
        result=candidates[-1] if candidates else {"stdout":cp.stdout}
        result["ok"]=True
        return result

def extract_makespan(result):
    if not result.get("ok"): return math.inf
    for key in ("makespan","total_time","execution_time"):
        if key in result and isinstance(result[key],(int,float)): return result[key]
    text=json.dumps(result)
    import re
    m=re.search(r'"makespan"\s*:\s*([0-9.]+)',text)
    return float(m.group(1)) if m else math.inf

def mutate(plan, rng):
    q=json.loads(json.dumps(plan))
    nonempty=[i for i,x in enumerate(q["core_schedules"]) if x]
    if not nonempty: return q
    src=rng.choice(nonempty)
    idx=rng.randrange(len(q["core_schedules"][src]))
    b=q["core_schedules"][src].pop(idx)
    dst=rng.randrange(len(q["core_schedules"]))
    pos=rng.randrange(len(q["core_schedules"][dst])+1)
    q["core_schedules"][dst].insert(pos,b)
    return q

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("graph",type=Path)
    ap.add_argument("--problem",type=int,choices=(1,2,3),default=2)
    ap.add_argument("--cores",type=int,default=4)
    ap.add_argument("--block-size",type=int,default=32)
    ap.add_argument("--eps",type=float,default=0.15)
    ap.add_argument("--budget",type=int,default=200)
    ap.add_argument("--seed",type=int,default=0)
    ap.add_argument("--config",type=Path,default=DATA_DIR/"config.txt")
    ap.add_argument("--out",type=Path,default=Path("a_search_best.json"))
    args=ap.parse_args()

    graph=load_json(args.graph)
    mapping=topo_blocks(graph,args.block_size)
    best=assign_blocks(graph,mapping,args.cores,args.eps,args.seed)
    cache={}
    r=evaluate(args.graph,best,args.problem,args.config)
    best_score=extract_makespan(r)
    cache[canonical(best)]=best_score
    log=[{"iter":0,"makespan":best_score,"result":r}]

    rng=random.Random(args.seed)
    current=best
    for it in range(1,args.budget+1):
        cand=mutate(current,rng)
        try: validate_multicore_plan(graph,cand)
        except Exception: continue
        h=canonical(cand)
        if h in cache: score=cache[h]
        else:
            rr=evaluate(args.graph,cand,args.problem,args.config)
            score=extract_makespan(rr); cache[h]=score
        if score < best_score:
            best,best_score,current=cand,score,cand
            log.append({"iter":it,"makespan":score})
        elif rng.random()<0.05:
            current=cand

    args.out.write_text(json.dumps({
        "best_makespan":best_score,
        "best_plan":best,
        "evaluated":len(cache),
        "improvements":log,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"best_makespan":best_score,
                      "evaluated":len(cache),
                      "out":str(args.out)},ensure_ascii=False))

if __name__=="__main__":
    main()
