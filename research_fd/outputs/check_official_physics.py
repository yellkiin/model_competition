"""Small numerical checks for the outputs/runtime official physical adapter.

This is a unit fixture with flat geometry, not a formal attachment result.
"""
from pathlib import Path
import sys,json,copy,math,traceback
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research_fd/outputs/runtime'))
import numpy as np
from research_fd.d_model import Problem,Fleet,synthetic
from research_fd.d_radio import relay_flight_components,session_pool

PARAM=json.loads((ROOT/'research_fd/outputs/official_parameters.json').read_text(encoding='utf-8'))
RESULTS=[]
def near(x,y,tol=1e-9):
    if not math.isclose(x,y,rel_tol=1e-12,abs_tol=tol): raise AssertionError((x,y))

def charge():
    records=[]
    for spec in PARAM['fleet']:
        f=Fleet(**spec);T=f.full_charge;errors=[];dense_errors=[]
        dense=np.linspace(0,1,101)
        elapsed=np.where(dense<.9,T*.65*dense/.9,T*(.65+.35*(dense-.9)/.1))
        for s in np.linspace(0,1,1001):
            exact=T*(.65*(.9-s)/.9+.35) if s<.9 else T*.35*(1-s)/.1
            actual=f.charge((1-s)*f.usable_kwh)
            errors.append(abs(actual-exact))
            dense_errors.append(abs(actual-(T-np.interp(s,dense,elapsed))))
        assert max(errors)<1e-9 and max(dense_errors)<1e-9
        records.append({'kind':f.id,'maximum_formula_error_s':max(errors),'maximum_3_vs_101_knot_error_s':max(dense_errors)})
    return records

def fixture():
    d=synthetic(7,1,2)
    d['metadata']={'source':'PHYSICS UNIT FIXTURE, NOT OFFICIAL INSTANCE'}
    d['terrain']={'kind':'flat','base':0.}
    d['nodes']=[{'id':'O01','x':0.,'y':0.,'z':0.,'work_height':0.},
                {'id':'S001','x':1500.,'y':0.,'z':0.,'work_height':30.}]
    d['boxes']=[{'id':'B001','node':'S001','mass':1.,'volume':.001,'due':1e8},
                {'id':'B002','node':'S001','mass':1.,'volume':.001,'due':1e8}]
    d['fleet']=copy.deepcopy(PARAM['fleet']);d['relay']=copy.deepcopy(PARAM['relay']);d['radio']=copy.deepcopy(PARAM['radio'])
    return d

def loading():
    d=fixture();new=Problem(d).route([0,1],'A')
    old_data=copy.deepcopy(d)
    for f in old_data['fleet']:f['loading_per_box']=0.
    old=Problem(old_data).route([0,1],'A')
    assert new is not None and old is not None
    for name in ('duration','aircraft_hold','battery_hold'):
        near(getattr(new,name)-getattr(old,name),60.)
    for b in new.delivery:near(new.delivery[b]-old.delivery[b],60.)
    for a,b in zip(new.segments,old.segments):near(a['t0']-b['t0'],60.);near(a['t1']-b['t1'],60.)
    near(new.energy,old.energy)
    return {'boxes':2,'loading_per_box_s':30,'added_duration_s':new.duration-old.duration,
            'energy_unchanged_kwh':new.energy,'first_airborne_time_s':new.segments[0]['t0']}

def relay():
    p=Problem(fixture());xyz=[1500.,0.,100.];c=relay_flight_components(p,xyz)
    expected_cruise=1.15*200/3600
    expected_climb=23.5*9.80665*100/(.72*3.6e6)
    near(c['outbound_s'],125.);near(c['inbound_s'],100+100/3)
    near(c['cruise_energy_kwh'],expected_cruise);near(c['climb_energy_kwh'],expected_climb)
    near(c['flight_energy_kwh'],expected_cruise+expected_climb)
    pool,info=session_pool(p,[{'time':600.,'xyz':xyz,'owner':0,'route_id':0}], [xyz],60.)
    s=next(s for s in pool if s.stop==660.)
    near(s.departure,240.);near(s.takeoff,420.);near(s.arrival,545.);near(s.ready,600.)
    near(s.hover_energy_kwh,1.05*115/3600);near(s.communication_energy_kwh,.05*115/3600)
    near(s.energy,expected_cruise+expected_climb+1.1*115/3600)
    near(s.energy,s.flight_energy_kwh+s.hover_energy_kwh+s.communication_energy_kwh)
    near(s.returned,660+100+100/3)
    assert s.energy<=3.2*.8 and s.aircraft_end>=s.returned+300
    soc=1-s.energy/3.2;T=1800.
    charge=T*(.65*(.9-soc)/.9+.35) if soc<.9 else T*.35*(1-soc)/.1
    near(s.pack_end,math.ceil((s.returned+charge)/60)*60)
    return {'flight':c,'resource_start_s':s.departure,'takeoff_s':s.takeoff,'arrival_s':s.arrival,
            'ready_s':s.ready,'stop_s':s.stop,'returned_s':s.returned,'energy_kwh':s.energy,
            'aircraft_end_s':s.aircraft_end,'pack_end_s':s.pack_end,'energy_components_kwh':
            {'cruise':s.cruise_energy_kwh,'climb':s.climb_energy_kwh,'hover':s.hover_energy_kwh,'communication':s.communication_energy_kwh}}

def legacy():
    d=fixture();d['relay']=synthetic()['relay'];p=Problem(d);xyz=[1500.,0.,100.]
    c=relay_flight_components(p,xyz)
    expected=1.8*((100/4+1500/20)+(1500/20+100/3))/3600
    near(c['flight_energy_kwh'],expected)
    assert c['cruise_energy_kwh'] is None and not c['official']
    pool,_=session_pool(p,[{'time':600.,'xyz':xyz,'owner':0,'route_id':0}],[xyz],60.)
    for s in pool:
        near(s.departure,s.takeoff)
        near(s.energy,expected+(s.stop-s.departure-c['outbound_s'])/3600)
    return {'legacy_flight_energy_kwh':expected,'sessions_checked':len(pool),'prepared_seconds':0}

for name,test in [('charge_exact_3_knots',charge),('loading_30_seconds_per_box',loading),('relay_official_energy_and_timeline',relay),('legacy_synthetic_preserved',legacy)]:
    try: RESULTS.append({'test':name,'status':'passed','details':test()})
    except Exception as e: RESULTS.append({'test':name,'status':'failed','error':repr(e),'traceback':traceback.format_exc()})
out=ROOT/'research_fd/outputs/review/official_physics_checks.json'
out.write_text(json.dumps({'source':'unit fixture; no optimization executed','checks':RESULTS},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(RESULTS,ensure_ascii=False,indent=2))
raise SystemExit(any(r['status']!='passed' for r in RESULTS))
