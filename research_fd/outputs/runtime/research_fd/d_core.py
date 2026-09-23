"""Independent D kernels. Conservative grid geometry; no invented routing solution."""
from __future__ import annotations
from dataclasses import dataclass
import heapq
import math
import numpy as np


def grid_supercover(start, end, shape):
    """Closed raster cells touched by a segment: (row,col)->[t_enter,t_exit].
    Coordinates are pixel-boundary coordinates (column,row), not pixel centers.
    Corner-only contacts and both sides of a grid boundary are retained.
    """
    a, b = np.asarray(start, float), np.asarray(end, float)
    h, w = shape
    if a.shape != (2,) or b.shape != (2,) or not np.isfinite(a+b).all() or min(h, w) <= 0:
        raise ValueError("invalid segment/grid")
    if np.any(np.minimum(a, b) < 0) or np.any(np.maximum(a, b) > [w, h]):
        raise ValueError("segment is outside the DEM; refusing extrapolation")
    delta = b-a
    ts = {0., 1.}
    for k in range(2):
        if delta[k] != 0:
            for edge in range(math.ceil(min(a[k], b[k])), math.floor(max(a[k], b[k]))+1):
                t = (edge-a[k])/delta[k]
                if 0 < t < 1:
                    ts.add(float(t))
    ts = sorted(ts)
    cells = {}
    def touch(t, lo, hi):
        xy = a+t*delta
        choices = []
        for v, size in zip(xy, [w, h]):
            nearest = round(v)
            ids = [nearest-1, nearest] if abs(v-nearest) < 1e-10 else [math.floor(v)]
            choices.append([i for i in ids if 0 <= i < size])
        for col in choices[0]:
            for row in choices[1]:
                old = cells.get((row, col), (lo, hi))
                cells[(row, col)] = (min(old[0], lo), max(old[1], hi))
    for t in ts:
        touch(t, t, t)
    for lo, hi in zip(ts[:-1], ts[1:]):
        touch((lo+hi)/2, lo, hi)
    return cells


def terrain_max(dem, start, end):
    z = np.asarray(dem, float)
    values = np.array([z[r, c] for r, c in grid_supercover(start, end, z.shape)])
    if not np.isfinite(values).all():
        raise ValueError("NoData on segment; no safety conclusion is possible")
    return float(values.max())


def terrain_blocked(dem, start, end, z_start, z_end):
    z = np.asarray(dem, float)
    if not np.isfinite([z_start, z_end]).all():
        raise ValueError("invalid endpoint altitude")
    blocked = False
    for (r, c), (lo, hi) in grid_supercover(start, end, z.shape).items():
        if not np.isfinite(z[r, c]):
            raise ValueError("NoData on ray")
        low_ray = min(z_start+(z_end-z_start)*lo, z_start+(z_end-z_start)*hi)
        blocked |= z[r, c] >= low_ray
    return bool(blocked)


def fspl(distance_m, frequency_mhz=2400.):
    if min(distance_m, frequency_mhz) <= 0 or not np.isfinite([distance_m, frequency_mhz]).all():
        raise ValueError("distance and frequency must be positive")
    return 32.45+20*math.log10(frequency_mhz)+20*math.log10(distance_m/1000)


def link_certificate(a0, a1, b0, b1, allowed_loss_db, obstruction_db=10., frequency_mhz=2400.):
    """Sufficient whole-interval certificate under the specified pathloss model.
    Both endpoints move affinely on the SAME interval. allowed_loss_db is the
    weaker directional path budget AFTER system loss, sensitivity and margin.
    False means uncertified, not necessarily disconnected. Distance floor: 1 m.
    """
    points = [np.asarray(x, float) for x in (a0, a1, b0, b1)]
    if any(x.shape != (3,) for x in points) or not np.isfinite(points).all():
        raise ValueError("four finite 3D endpoints required")
    if not np.isfinite([allowed_loss_db, obstruction_db]).all() or obstruction_db < 0:
        raise ValueError("invalid path budget/obstruction")
    a0, a1, b0, b1 = points
    dmax = max(float(np.linalg.norm(a0-b0)), float(np.linalg.norm(a1-b1)), 1.)
    margin = allowed_loss_db-fspl(dmax, frequency_mhz)-obstruction_db
    return {"certified": margin >= 0, "worst_margin_db": float(margin), "distance_bound_m": dmax}


@dataclass(frozen=True)
class Aircraft:
    payload: float
    empty_mass: float
    usable_kwh: float
    empty_range_km: float
    full_range_km: float
    climb_efficiency: float
    reserve: float

    def __post_init__(self):
        vals = [self.payload, self.empty_mass, self.usable_kwh, self.empty_range_km,
                self.full_range_km, self.climb_efficiency]
        if not np.isfinite(vals+[self.reserve]).all() or min(vals) <= 0 or not 0 <= self.reserve < 1:
            raise ValueError("invalid aircraft parameters")
        if self.empty_range_km < self.full_range_km or self.climb_efficiency > 1:
            raise ValueError("invalid range or efficiency")

    def leg_energy(self, distance_km, climb_m, payload):
        if not np.isfinite([distance_km, climb_m, payload]).all() or min(distance_km, climb_m, payload) < 0 or payload > self.payload:
            raise ValueError("invalid leg/load")
        reach = self.empty_range_km-(self.empty_range_km-self.full_range_km)*(payload/self.payload)**1.5
        return self.usable_kwh*distance_km/reach + (self.empty_mass+payload)*9.80665*climb_m/(self.climb_efficiency*3.6e6)

    def roundtrip_limit(self, distance_km, outward_climb_m, return_climb_m):
        def energy(q):
            return self.leg_energy(distance_km, outward_climb_m, q)+self.leg_energy(distance_km, return_climb_m, 0.)
        cap = self.usable_kwh*(1-self.reserve)
        if energy(0) > cap:
            return None
        lo, hi = 0., self.payload
        for _ in range(70):
            mid = (lo+hi)/2
            if energy(mid) <= cap:
                lo = mid
            else:
                hi = mid
        return lo


def charge_seconds(soc, full_time, knee, slow_factor):
    """Two constant-rate phases normalized to full_time from SOC=0.
    knee/slow_factor MUST be checked against original problem; no default values.
    """
    if not np.isfinite([soc, full_time, knee, slow_factor]).all() or not 0 <= soc <= 1 or full_time <= 0 or not 0 < knee < 1 or slow_factor < 1:
        raise ValueError("invalid charging curve")
    remaining = max(knee-soc, 0)+slow_factor*(1-max(knee, soc))
    return full_time*remaining/(knee+slow_factor*(1-knee))


def color_intervals(intervals):
    """Optimal coloring of positive-duration half-open intervals [start,end).
    Common depot, identical compatible resources, no repositioning/setup extras.
    Returns minimum count and assignment in input order.
    """
    intervals = list(intervals)
    if any(not np.isfinite([s, e]).all() or s < 0 or e <= s for s, e in intervals):
        raise ValueError("positive-duration, nonnegative finite intervals required")
    busy, free, assignment, count = [], [], [None]*len(intervals), 0
    for i in sorted(range(len(intervals)), key=lambda i: (intervals[i][0], intervals[i][1], i)):
        s, e = intervals[i]
        while busy and busy[0][0] <= s:
            _, resource = heapq.heappop(busy)
            heapq.heappush(free, resource)
        if free:
            resource = heapq.heappop(free)
        else:
            resource, count = count, count+1
        assignment[i] = resource
        heapq.heappush(busy, (e, resource))
    return count, assignment


def frozen_components(nodes, hyperedges):
    nodes = list(nodes)
    if len(set(nodes)) != len(nodes):
        raise ValueError("duplicate nodes")
    parent = {n: n for n in nodes}
    def root(n):
        if n not in parent:
            raise ValueError("unknown node in hyperedge")
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for edge in hyperedges:
        edge = list(edge)
        if edge:
            first = root(edge[0])
            for n in edge[1:]:
                parent[root(n)] = first
    out = {}
    for n in nodes:
        out.setdefault(root(n), []).append(n)
    return list(out.values())


def validate_resources(tasks, capacities):
    """Check fixed normalized aircraft/battery occupancies, not complete Q2/Q3.
    Each task: id,type,aircraft,battery,start,aircraft_end,battery_ready.
    capacities: type -> {aircraft: count,battery: count}. Includes initial packs.
    """
    if len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError("duplicate task ids")
    for cap in capacities.values():
        for label in ('aircraft', 'battery'):
            if not isinstance(cap[label], int) or isinstance(cap[label], bool) or cap[label] < 0:
                raise ValueError('resource capacities must be nonnegative integers')
    errors, required = [], {}
    for kind in sorted({t['type'] for t in tasks}):
        if kind not in capacities:
            raise ValueError("missing type capacity")
        group = [t for t in tasks if t['type'] == kind]
        required[kind] = {}
        for label, end in [('aircraft', 'aircraft_end'), ('battery', 'battery_ready')]:
            intervals = [(t['start'], t[end]) for t in group]
            need, _ = color_intervals(intervals)
            required[kind][label] = need
            if need > capacities[kind][label]:
                errors.append(f'{kind}: insufficient {label}: need {need}')
            if len({t[label] for t in group}) > capacities[kind][label]:
                errors.append(f'{kind}: too many named {label} resources')
            for resource in {t[label] for t in group}:
                count, _ = color_intervals([(t['start'], t[end]) for t in group if t[label] == resource])
                if count > 1:
                    errors.append(f'{kind}: overlapping {label} {resource}')
    return {'valid_occupancy': not errors, 'errors': errors, 'required': required,
            'scope': 'fixed intervals only; not a full energy/deadline/communication verifier'}
