"""Draw actual local development trajectories; keep independent runs separate."""
from pathlib import Path
import csv

def main():
 import matplotlib.pyplot as plt
 root=Path(__file__).parent/'evidence';out=root/'figures';out.mkdir(exist_ok=True)
 def read(name):
  with (root/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 events=read('all_improvement_events.csv');arms=read('all_measured_arms.csv')
 for case,q,n in [('case_024','2','2'),('case_044','1','4'),('case_083','3','4')]:
  def selected(r):return r['experiment']=='integration_new_configs_v1' and (r['case'],r['q'],r['n'])==(case,q,n)
  pts=sorted(filter(selected,events),key=lambda r:float(r['elapsed_seconds']));arm=next(filter(selected,arms))
  x=[float(r['elapsed_seconds']) for r in pts]+[float(arm['local_seconds'])];y=[int(r['makespan']) for r in pts];y.append(y[-1])
  fig,ax=plt.subplots(figsize=(8,4.6));ax.step(x,y,where='post',label='Best validated incumbent');ax.scatter(x[:-1],y[:-1],s=18)
  ax.set_xlabel('Additional run time (seconds)');ax.set_ylabel('Makespan (cycles; lower is better)');ax.set_title(f'{case} / Q{q} / {n} cores / Trident 1.0');ax.legend();fig.tight_layout()
  for ext in ('svg','png'):fig.savefig(out/f'{case}_q{q}_n{n}_actual_trajectory.{ext}',dpi=180)
  plt.close(fig)
 order=['sm','sf','mf','s','m','f'];vals={r['components']:int(r['new_makespan']) for r in arms if r['experiment']=='diagnostic_011_q3_n5'}
 fig,ax=plt.subplots(figsize=(8,4.6));ax.bar([s.upper()+'+B' for s in order],[vals[s] for s in order]);ax.set_ylabel('Selected makespan (cycles)');ax.set_title('case_011 / Q3 / 5 cores: targeted subset diagnosis');ax.set_xlabel('Research sources; common baseline source B is retained');fig.tight_layout()
 for ext in ('svg','png'):fig.savefig(out/f'case_011_subset_diagnosis.{ext}',dpi=180)
 plt.close(fig)
if __name__=='__main__':main()
