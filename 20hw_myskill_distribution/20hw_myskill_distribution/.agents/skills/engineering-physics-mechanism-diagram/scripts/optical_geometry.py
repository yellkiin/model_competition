"""Planar Snell geometry from explicit inputs; emits analytical DEMO values, not measurements."""
import argparse,json,math
from pathlib import Path

def solve(n1,n2,theta_deg):
    if n1<=0 or n2<=0 or not 0<=theta_deg<90:raise ValueError('Positive indices and 0 <= incidence < 90 required')
    a=math.radians(theta_deg);ratio=n1/n2*math.sin(a)
    result={'n1':n1,'n2':n2,'incidence_deg':theta_deg,'reflection_deg':theta_deg,
            'incident_direction':[math.sin(a),-math.cos(a)],'reflected_direction':[math.sin(a),math.cos(a)],
            'total_internal_reflection':ratio>1}
    if ratio<=1:
        b=math.asin(ratio)
        result.update(refraction_deg=math.degrees(b),refracted_direction=[math.sin(b),-math.cos(b)],
                      snell_residual=n1*math.sin(a)-n2*math.sin(b))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--n1',type=float,required=True);p.add_argument('--n2',type=float,required=True)
    p.add_argument('--incidence-deg',type=float,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=solve(a.n1,a.n2,a.incidence_deg);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
