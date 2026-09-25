"""Freshly validate the exact day01 selected plan for requested real configurations."""
import argparse,csv,time
from pathlib import Path
from .storage import read,write
from .reconcile_runner import run_job
ROOT=Path(__file__).resolve().parents[1]
OFF=ROOT/"题目/A题/通用神经网络处理器下的多核调度问题  附件"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cases",required=True);p.add_argument("--questions",default="3")
    p.add_argument("--cores",default="5");p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify-seconds",type=float,default=90)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    cases={"case_"+f"{int(c):03d}" for c in a.cases.split(",")}
    qs=set(map(int,a.questions.split(",")));ns=set(map(int,a.cores.split(",")))
    day=ROOT/"research_a_orion_anytime/team_results/day01/combined_final"
    rows=list(csv.DictReader((day/"per_case.csv").open(encoding="utf-8-sig")))
    records=[];errors=[]
    for row in rows:
        case=row["case"];q=int(row["q"]);n=int(row["n"])
        if case not in cases or q not in qs or n not in ns:continue
        matches=[]
        for pg in (ROOT/"raw_day01").glob(f"**/{case}_q{q}_n{n}/progress.json"):
            state=read(pg);meta=state.get("incumbent")
            if not meta or meta["makespan"]!=int(row["makespan"]):continue
            plan=pg.parent/meta["plan_file"];response=pg.parent/meta["result_file"]
            if plan.is_file() and response.is_file():matches.append((pg,plan,response))
        if not matches:
            errors.append(dict(case=case,q=q,n=n,error="No final matching raw plan"));continue
        matches.sort(key=lambda t:("refinement" not in str(t[0]),str(t[0])))
        pg,plan,response=matches[0];job=out/"seeds"/f"{case}_q{q}_n{n}"
        req=dict(case=case,q=q,n=n,method="fixed",job=str(job),fixed_plan=str(plan),
            seconds=a.verify_seconds,official=str(OFF),graph=str(OFF/"data"/f"{case}.json"),
            config=str(OFF/"data/config.txt"),identity={"purpose":"new_fixed_replay"})
        got=run_job(req,a.verify_seconds,int(row["baseline"]),0.)
        if got.get("status")!="ok" or got.get("makespan")!=int(row["makespan"]):
            errors.append(dict(case=case,q=q,n=n,error="New replay mismatch or timeout",observed=got.get("makespan")))
        else:
            records.append(dict(case=case,q=q,n=n,seed_job=str(job),
                baseline=int(row["baseline"]),recorded_makespan=int(row["makespan"]),
                original_plan=str(plan),original_response=str(response),original_progress=str(pg),
                seed_solve_seconds=float(row["solve_seconds"]) if row.get("solve_seconds") else None,
                seed_cost_complete=False,validation_seconds=got["solve_seconds"],
                replay_plan=got["plan_file"],replay_response=got["result_file"]))
        write(out/"seed_manifest.json",records);write(out/"errors.json",errors)
    write(out/"seed_manifest.json",records);write(out/"errors.json",errors)
    if errors or len(records)!=len(cases)*len(qs)*len(ns):
        raise SystemExit("Incomplete seed validation; consult errors.json")
if __name__=="__main__":main()
