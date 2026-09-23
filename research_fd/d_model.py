"""D physical model and normalized input. Units: metres, seconds, kg, m^3, kWh.
Every synthetic parameter is in the generated instance, never hidden in a solver.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from itertools import permutations
from pathlib import Path
import json
import math
import numpy as np

@dataclass
class Node:
    id: str
    x: float
    y: float
    z: float
    work_height: float = 30.0

@dataclass
class Box:
    id: str
    node: str
    mass: float
    volume: float
    due: float
    hard_due: float | None = None
    weight: float = 1.0
    release: float = 0.0

@dataclass
class Fleet:
    id: str
    count: int
    batteries: int
    payload: float
    volume: float
    empty_mass: float
    usable_kwh: float
    range_empty_km: float
    range_full_km: float
    speed: float
    climb_speed: float
    descend_speed: float
    efficiency: float
    reserve: float
    prepare: float
    turnaround: float
    full_charge: float
    charge_knee: float
    charge_slow: float
    service: float
    service_per_box: float = 0.0
    hover_kw: float = 0.0
    charge_table: list[list[float]] | None = None

    def charge(self, consumed: float) -> float:
        soc = max(0., 1-consumed/self.usable_kwh)
        if self.charge_table is not None:
            table=np.asarray(self.charge_table,float)
            return float(table[-1,1]-np.interp(soc,table[:,0],table[:,1]))
        a, k = self.charge_knee, self.charge_slow
        return self.full_charge*(max(a-soc, 0)+k*(1-max(a, soc)))/(a+k*(1-a))

    def energy(self, distance: float, climb: float, load: float) -> float:
        reach = self.range_empty_km-(self.range_empty_km-self.range_full_km)*(load/self.payload)**1.5
        return self.usable_kwh*distance/(1000*reach)+(self.empty_mass+load)*9.80665*climb/(self.efficiency*3.6e6)

class Terrain:
    def __init__(self, spec: dict):
        self.spec = spec
        self.ds = None
        if spec['kind'] == 'raster':
            import rasterio
            from pyproj import Transformer
            self.ds = rasterio.open(spec['path'])
            if self.ds.crs is None:
                raise ValueError('DEM has no CRS')
            self.grid = self.ds.read(1, masked=True)
            self.inv = ~self.ds.transform
            self.to_native = Transformer.from_crs(spec['local_crs'], self.ds.crs, always_xy=True)
        elif spec['kind'] not in ('gaussian', 'flat'):
            raise ValueError('terrain kind must be raster, gaussian, or flat')

    def height(self, xy) -> np.ndarray:
        xy = np.atleast_2d(np.asarray(xy, float))
        if self.ds is not None:
            x, y = self.to_native.transform(xy[:, 0], xy[:, 1])
            c = np.floor(self.inv.a*np.asarray(x)+self.inv.b*np.asarray(y)+self.inv.c).astype(int)
            r = np.floor(self.inv.d*np.asarray(x)+self.inv.e*np.asarray(y)+self.inv.f).astype(int)
            if np.any(r < 0) or np.any(c < 0) or np.any(r >= self.ds.height) or np.any(c >= self.ds.width):
                raise ValueError('trajectory outside DEM: inspect local_crs and coordinates')
            z = self.grid[r, c]
            if np.any(np.ma.getmaskarray(z)):
                raise ValueError('DEM NoData encountered')
            return np.asarray(z, float)
        z = np.full(len(xy), float(self.spec.get('base', 0.)))
        for h in self.spec.get('hills', []):
            z += h['height']*np.exp(-.5*((xy[:,0]-h['x'])/h['sx'])**2-.5*((xy[:,1]-h['y'])/h['sy'])**2)
        return z

    def peak(self, a, b, step=15.):
        distance = np.linalg.norm(np.asarray(a)-b)
        p = np.linspace(a, b, max(2, int(np.ceil(distance/step))+1))
        if self.ds is None: return float(self.height(p).max())
        from .d_geometry import cells
        x,y=self.to_native.transform(p[:,0],p[:,1]);pixel=np.array([self.inv*(u,v) for u,v in zip(x,y)])
        touched=set()
        for u,v in zip(pixel[:-1],pixel[1:]): touched.update(cells(u,v,self.grid.shape))
        values=[self.grid[r,c] for r,c in touched]
        if any(np.ma.is_masked(v) or not np.isfinite(v) for v in values): raise ValueError('DEM NoData on arc')
        return float(max(values))

    def blocked(self, a, b, step=30.):
        # Omit exact endpoint equality, but retain points immediately above ground.
        n = max(3, int(np.ceil(np.linalg.norm(np.asarray(a[:2])-b[:2])/step))+1)
        t = np.linspace(0, 1, n)[1:-1]
        xy = (1-t[:,None])*np.asarray(a[:2])+t[:,None]*np.asarray(b[:2])
        ray = (1-t)*a[2]+t*b[2]
        return bool(np.any(self.height(xy) >= ray))

@dataclass
class Route:
    id: int
    kind: str
    boxes: tuple[int, ...]
    stops: tuple[str, ...]
    delivery: dict[int, float]
    duration: float
    aircraft_hold: float
    battery_hold: float
    energy: float
    release: float
    latest: float
    segments: list[dict]

class Problem:
    def __init__(self, data: dict):
        self.data = data
        self.nodes = {n['id']: Node(**n) for n in data['nodes']}
        self.boxes = [Box(**b) for b in data['boxes']]
        self.fleet = {f['id']: Fleet(**f) for f in data['fleet']}
        self.depot = data.get('depot', 'O01')
        self.terrain = Terrain(data['terrain'])
        self.arc_step = float(data.get('arc_step_m', 15))
        self.clearance = float(data.get('clearance_m', 50))
        self.arcs = {}
        if self.depot not in self.nodes or self.arc_step <= 0:
            raise ValueError('missing depot or invalid arc step')
        if len(self.nodes) != len(data['nodes']) or len(self.fleet) != len(data['fleet']):
            raise ValueError('duplicate node/fleet IDs')
        if len({b.id for b in self.boxes}) != len(self.boxes):
            raise ValueError('duplicate box IDs')
        for b in self.boxes:
            if b.node not in self.nodes or b.node == self.depot or min(b.mass,b.volume,b.weight) <= 0:
                raise ValueError(f'invalid box {b.id}')
            if not np.isfinite([b.mass,b.volume,b.due,b.weight,b.release]).all() or b.release < 0:
                raise ValueError('nonfinite or negative release')
            if b.hard_due is not None and (not np.isfinite(b.hard_due) or b.hard_due < b.release):
                raise ValueError('invalid hard deadline')
        for f in self.fleet.values():
            if min(f.count,f.batteries,f.payload,f.volume,f.empty_mass,f.usable_kwh,f.speed,f.climb_speed,f.descend_speed,f.full_charge) <= 0:
                raise ValueError(f'invalid fleet {f.id}')
            if not 0 <= f.reserve < 1 or not 0 < f.efficiency <= 1 or not 0 < f.charge_knee < 1 or f.charge_slow < 1:
                raise ValueError('invalid energy/charging parameter')
            if not 0 < f.range_full_km <= f.range_empty_km or min(f.prepare,f.turnaround,f.service,f.service_per_box,f.hover_kw) < 0:
                raise ValueError('invalid range or operation time')
        for f in self.fleet.values():
            if f.charge_table is not None:
                tab=np.asarray(f.charge_table,float)
                if tab.ndim!=2 or tab.shape[1]!=2 or len(tab)<2 or not np.isfinite(tab).all() or tab[0,0]!=0 or tab[-1,0]!=1 or np.any(np.diff(tab[:,0])<=0) or np.any(np.diff(tab[:,1])<0):
                    raise ValueError('charge_table requires increasing SOC 0..1 and nondecreasing elapsed full-charge seconds')
        self._route_cache = {}

    def arc(self, a: str, b: str):
        key = (a,b)
        if key not in self.arcs:
            u,v = self.nodes[a], self.nodes[b]
            distance = math.hypot(u.x-v.x, u.y-v.y)
            cruise = max(self.terrain.peak([u.x,u.y],[v.x,v.y],self.arc_step),u.z,v.z)+self.clearance
            if max(u.z+u.work_height,v.z+v.work_height) > cruise:
                raise ValueError('work altitude exceeds defined cruise altitude')
            self.arcs[key] = (distance,cruise,cruise-u.z-u.work_height,cruise-v.z-v.work_height)
        return self.arcs[key]

    def route(self, items, kind, order=None) -> Route | None:
        items = tuple(sorted(set(int(i) for i in items)))
        if not items: return None
        key = (items,kind,tuple(order) if order else None)
        if key in self._route_cache: return self._route_cache[key]
        f = self.fleet[kind]
        load = sum(self.boxes[i].mass for i in items)
        if load > f.payload+1e-9 or sum(self.boxes[i].volume for i in items) > f.volume+1e-9:
            self._route_cache[key] = None
            return None
        stops = sorted({self.boxes[i].node for i in items})
        if order is not None and (len(order) != len(stops) or set(order) != set(stops)):
            raise ValueError('visit order must contain exactly the delivered nodes')
        if len(stops) > 4 and order is None:
            # Explicit bounded neighborhood, not a factorial search at large size.
            stops = sorted(stops, key=lambda n: math.atan2(self.nodes[n].y,self.nodes[n].x))
        orders = [tuple(order)] if order else (list(permutations(stops)) if len(stops)<=4 else [tuple(stops)])
        best = None
        for seq in orders:
            t, energy, q = f.prepare, 0., load
            delivery, segs = {}, []
            def add(dt,a,b,phase):
                nonlocal t
                if dt > 1e-9:
                    segs.append(dict(t0=t,t1=t+dt,a=a,b=b,phase=phase))
                    t += dt
            a = self.depot
            for b in (*seq,self.depot):
                u,v = self.nodes[a],self.nodes[b]
                dist,z,up,down = self.arc(a,b)
                energy += f.energy(dist,up,q)
                add(up/f.climb_speed,[u.x,u.y,u.z+u.work_height],[u.x,u.y,z],'climb')
                add(dist/f.speed,[u.x,u.y,z],[v.x,v.y,z],'cruise')
                add(down/f.descend_speed,[v.x,v.y,z],[v.x,v.y,v.z+v.work_height],'descend')
                if b != self.depot:
                    delivered = [i for i in items if self.boxes[i].node == b]
                    hold = f.service+len(delivered)*f.service_per_box
                    add(hold,[v.x,v.y,v.z+v.work_height],[v.x,v.y,v.z+v.work_height],'service')
                    energy += f.hover_kw*hold/3600
                    for i in delivered: delivery[i] = t
                    q = max(0.,q-sum(self.boxes[i].mass for i in delivered))
                a = b
            if energy > f.usable_kwh*(1-f.reserve)+1e-9: continue
            release = max(self.boxes[i].release for i in items)
            latest = min((self.boxes[i].hard_due-delivery[i] for i in items if self.boxes[i].hard_due is not None),default=math.inf)
            if latest < release-1e-8: continue
            candidate = Route(-1,kind,items,seq,delivery,t,t+f.turnaround,t+f.charge(energy),energy,release,latest,segs)
            # Feasible-at-release first; timing-aware ordering uses available slack.
            rank = (t, -latest)
            if best is None or rank < (best.duration,-best.latest): best = candidate
        self._route_cache[key] = best
        return best

    @classmethod
    def load(cls,path):
        path = Path(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['terrain']['kind']=='raster' and not Path(data['terrain']['path']).is_absolute():
            data['terrain']['path'] = str((path.parent/data['terrain']['path']).resolve())
        return cls(data)


def synthetic(seed=0,n_nodes=15,n_boxes=80,tightness=1.) -> dict:
    rng=np.random.default_rng(seed)
    terrain={'kind':'gaussian','base':100.,'hills':[{'x':2500.,'y':0.,'sx':600.,'sy':2800.,'height':280.},{'x':-1800.,'y':2300.,'sx':950.,'sy':750.,'height':180.}]}
    ground=Terrain(terrain)
    xy=np.vstack([[0.,0.],rng.uniform(-4500,4500,(n_nodes,2))])
    zs=ground.height(xy)
    nodes=[dict(id='O01' if i==0 else f'S{i:03}',x=float(x),y=float(y),z=float(zs[i]),work_height=0. if i==0 else 30.) for i,(x,y) in enumerate(xy)]
    fleet=[]
    for ident,count,bats,pay,vol,empty,energy,re,rf,sp,ct in [('A',4,6,25,.060,28,2.2,40,22,17,1800),('B',2,4,30,.073,35,2.8,48,25,20,2400),('C',2,4,80,.250,85,6.8,65,32,24,3000)]:
        fleet.append(dict(id=ident,count=count,batteries=bats,payload=pay,volume=vol,empty_mass=empty,usable_kwh=energy,range_empty_km=re,range_full_km=rf,speed=sp,climb_speed=4.,descend_speed=3.,efficiency=.72,reserve=.15,prepare=90.,turnaround=90.,full_charge=ct,charge_knee=.8,charge_slow=2.,service=35.,service_per_box=3.,hover_kw=0.))
    boxes=[]
    for i in range(n_boxes):
        node=1+i%n_nodes
        due=float(rng.uniform(1600,3500)*tightness)
        hard=due if i < max(1,n_boxes//5) else None
        boxes.append(dict(id=f'B{i+1:03}',node=f'S{node:03}',mass=float(rng.choice([6,8,10,12,14])),volume=float(rng.choice([.014,.020,.028,.036])),due=due,hard_due=hard,weight=3. if hard else 1.,release=0.))
    return dict(schema_version=1,metadata={'source':'SYNTHETIC BENCHMARK; not the competition attachment','seed':seed,'note':'15/80 and fleet counts/capacities resemble prior report; geometry, energy, times and boxes are artificial.'},depot='O01',nodes=nodes,boxes=boxes,fleet=fleet,terrain=terrain,clearance_m=50.,arc_step_m=20.,radio={'frequency_mhz':2400.,'obstruction_db':10.,'direct_budget_db':110.,'access_budget_db':116.,'backhaul_budget_db':121.,'ground_antenna_m':12.,'ray_step_m':50.},relay={'count':2,'packs':6,'energy_kwh':3.2,'reserve':.15,'speed':20.,'climb_speed':4.,'descend_speed':3.,'travel_kw':1.8,'hover_kw':1.0,'setup':60.,'turnaround':90.,'full_charge':2400.,'charge_knee':.8,'charge_slow':2.,'heights_m':[120.,220.,300.]})
