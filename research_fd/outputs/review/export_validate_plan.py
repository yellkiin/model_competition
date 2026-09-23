"""Export and cross-check an existing D plan; never modifies input or solver code.

Run with research_fd/.venv/Scripts/python.exe. All outputs are restricted to
research_fd/outputs. Resource/coverage/time checks are independent of metrics();
physical route reconstruction and radio propagation reuse the declared engine.
"""
from __future__ import annotations
import argparse
import csv
import importlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def recharge_seconds(consumed, energy, full_charge, knee, slow, table=None):
    """Independent arithmetic for the declared piecewise cumulative SOC curve."""
    soc = max(0., 1-consumed/energy)
    if table is None:
        return full_charge*(max(knee-soc, 0.)+slow*(1-max(knee, soc)))/(knee+slow*(1-knee))
    if soc <= table[0][0]:
        cumulative = table[0][1]
    elif soc >= table[-1][0]:
        cumulative = table[-1][1]
    else:
        for (x0, y0), (x1, y1) in zip(table, table[1:]):
            if x0 <= soc <= x1:
                cumulative = y0+(soc-x0)*(y1-y0)/(x1-x0)
                break
    return table[-1][1]-cumulative


def validate_export(input_path, plan_path, out, radio_step=10.0, skip_radio=False, runtime=None):
    sys.path.insert(0, str(ROOT))
    if runtime is not None:
        runtime = Path(runtime).resolve()
        if not (runtime/'research_fd/d_model.py').is_file():
            raise ValueError('--runtime must contain the adapted research_fd package')
        sys.path.insert(0, str(runtime))
    from research_fd.d_model import Problem
    from research_fd.d_experiments import load_plan
    from research_fd.d_radio import evaluate_radio, margin, ground
    active_model = Path(importlib.import_module('research_fd.d_model').__file__).resolve()
    if runtime is not None and not active_model.is_relative_to(runtime):
        raise RuntimeError('Another research_fd package was already imported; use a fresh process for --runtime')
    out = Path(out).resolve()
    out.relative_to((ROOT / 'research_fd/outputs').resolve())
    out.mkdir(parents=True, exist_ok=True)
    p = Problem.load(input_path)
    raw = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    jobs, sessions = load_plan(plan_path)
    issues = []
    notes = []
    tolerance = 1e-5
    metadata = p.data.get('metadata', {})

    def aircraft_label(kind, index):
        ids = metadata.get('transport_aircraft_ids', {}).get(kind, [])
        if isinstance(index, int) and 0 <= index < len(ids):
            return ids[index]
        return f'{kind}-U{index+1:02d}' if isinstance(index, int) else None

    def battery_label(kind, index):
        return f'{kind}-B{index+1:02d}' if isinstance(index, int) else None

    def issue(scope, code, **context):
        issues.append(dict(scope=scope, code=code, **context))

    def close(a, b, scope, field, **context):
        if not math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=tolerance):
            issue(scope, 'stored_value_differs_from_recomputed', field=field, stored=a, expected=b, **context)

    def check_id(value, count, scope, resource, **context):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < count:
            issue(scope, 'resource_id_outside_inventory', resource=resource, resource_id=value, inventory=count, **context)

    def overlaps(intervals, scope):
        # Check all pairs, including nested intervals; do not rely on adjacency.
        for key, spans in intervals.items():
            spans = sorted(spans)
            for i, (start, end, owner) in enumerate(spans):
                for start2, end2, owner2 in spans[i+1:]:
                    if start2 >= end-tolerance:
                        break
                    if min(end, end2)-max(start, start2) > tolerance:
                        issue(scope, 'resource_interval_overlap', resource=key, first=owner, second=owner2,
                              first_interval=[start, end], second_interval=[start2, end2])

    delivery_events = defaultdict(list)
    box_counts = Counter()
    transport_spans = defaultdict(list)
    relay_spans = defaultdict(list)
    trips, aircraft_rows, battery_rows, relay_rows, segment_rows = [], [], [], [], []
    if not jobs:
        issue('transport', 'empty_plan', expected_boxes=len(p.boxes))
    for index, job in enumerate(jobs):
        r = job.route
        context = {'job': index, 'route_id': r.id}
        if r.kind not in p.fleet:
            issue('transport', 'unknown_fleet', kind=r.kind, **context)
            continue
        f = p.fleet[r.kind]
        check_id(job.aircraft, f.count, 'transport', r.kind+'_aircraft', **context)
        check_id(job.battery, f.batteries, 'transport', r.kind+'_battery', **context)
        if not math.isfinite(job.start) or job.start < -tolerance:
            issue('transport', 'invalid_start', start=job.start, **context)
        if job.start < r.release-tolerance:
            issue('transport', 'route_release_violation', start=job.start, release=r.release, **context)
        if math.isfinite(r.latest) and job.start > r.latest+tolerance:
            issue('transport', 'route_latest_start_violation', start=job.start, latest=r.latest, **context)
        indexes = list(r.boxes)
        if any(not isinstance(i, int) or i < 0 or i >= len(p.boxes) for i in indexes):
            issue('transport', 'invalid_box_index', boxes=indexes, **context)
            continue
        box_counts.update(indexes)
        if set(indexes) != set(r.delivery) or len(set(indexes)) != len(indexes):
            issue('transport', 'route_boxes_delivery_mismatch', boxes=indexes, delivery=list(r.delivery), **context)
        mass = sum(p.boxes[i].mass for i in indexes)
        volume = sum(p.boxes[i].volume for i in indexes)
        if mass > f.payload+tolerance or volume > f.volume+tolerance:
            issue('transport', 'payload_or_volume_exceeded', mass_kg=mass, volume_m3=volume, **context)
        if not math.isfinite(r.energy) or r.energy < 0 or r.energy > f.usable_kwh*(1-f.reserve)+tolerance:
            issue('transport', 'return_energy_reserve_violated', energy_kwh=r.energy, usable_kwh=f.usable_kwh, reserve=f.reserve, **context)
        try:
            expected = p.route(indexes, r.kind, r.stops)
            if expected is None:
                issue('transport', 'route_not_physically_feasible_at_release', **context)
            else:
                for field in ('duration', 'aircraft_hold', 'battery_hold', 'energy', 'release'):
                    close(getattr(r, field), getattr(expected, field), 'transport', field, **context)
                if math.isfinite(r.latest) != math.isfinite(expected.latest):
                    issue('transport', 'latest_start_finiteness_mismatch', **context)
                elif math.isfinite(r.latest):
                    close(r.latest, expected.latest, 'transport', 'latest', **context)
                for i in set(r.delivery) & set(expected.delivery):
                    close(r.delivery[i], expected.delivery[i], 'transport', 'delivery_offset', box=p.boxes[i].id, **context)
                if len(r.segments) != len(expected.segments):
                    issue('transport', 'segment_count_mismatch', **context)
                else:
                    for segment_id, (saved, recalculated) in enumerate(zip(r.segments, expected.segments)):
                        if saved['phase'] != recalculated['phase']:
                            issue('transport', 'segment_phase_mismatch', segment=segment_id, **context)
                        for field in ('t0', 't1'):
                            close(saved[field], recalculated[field], 'transport', field, segment=segment_id, **context)
                        for field in ('a', 'b'):
                            for dim, (x, y) in enumerate(zip(saved[field], recalculated[field])):
                                close(x, y, 'transport', field+str(dim), segment=segment_id, **context)
        except Exception as exc:
            issue('transport', 'physical_reconstruction_error', exception=type(exc).__name__, message=str(exc), **context)
        returned = job.start+r.duration
        motion_start = job.start+(r.segments[0]['t0'] if r.segments else f.prepare+len(indexes)*getattr(f, 'loading_per_box', 0.))
        charge = recharge_seconds(r.energy, f.usable_kwh, f.full_charge, f.charge_knee, f.charge_slow, f.charge_table)
        close(f.charge(r.energy), charge, 'transport', 'charging_function', **context)
        soc = 1-r.energy/f.usable_kwh
        close(r.aircraft_hold, r.duration+f.turnaround, 'transport', 'aircraft_hold_formula', **context)
        close(r.battery_hold, r.duration+charge, 'transport', 'battery_hold_formula', **context)
        transport_spans[f'{r.kind}_aircraft_{job.aircraft}'].append((job.start, job.start+r.aircraft_hold, index))
        transport_spans[f'{r.kind}_battery_{job.battery}'].append((job.start, job.start+r.battery_hold, index))
        for i, offset in r.delivery.items():
            if i < 0 or i >= len(p.boxes):
                issue('transport', 'invalid_delivery_index', box_index=i, **context)
                continue
            b = p.boxes[i]
            delivered = job.start+offset
            delivery_events[i].append((index, r.id, r.kind, job.aircraft, job.battery, delivered))
            if job.start < b.release-tolerance:
                issue('transport', 'box_release_violation', box=b.id, **context)
            if b.hard_due is not None and delivered > b.hard_due+tolerance:
                issue('transport', 'hard_deadline_violation', box=b.id, delivered_s=delivered, hard_due_s=b.hard_due, **context)
        trips.append(dict(job=index, route_id=r.id, kind=r.kind, aircraft=job.aircraft, battery=job.battery,
                          aircraft_id=aircraft_label(r.kind, job.aircraft), battery_label=battery_label(r.kind, job.battery),
                          boxes=';'.join(p.boxes[i].id for i in indexes), stops=';'.join(r.stops), mass_kg=mass,
                          volume_m3=volume, start_s=job.start, first_motion_s=motion_start, returned_s=returned,
                          aircraft_available_s=job.start+r.aircraft_hold, battery_full_s=job.start+r.battery_hold,
                          energy_kwh=r.energy, return_soc=soc))
        aircraft_rows.append(dict(resource=f'{r.kind}_aircraft_{job.aircraft}', kind=r.kind, resource_id=job.aircraft,
                                  aircraft_id=aircraft_label(r.kind, job.aircraft),
                                  job=index, route_id=r.id, prepare_start_s=job.start, motion_start_s=motion_start,
                                  returned_s=returned, available_s=job.start+r.aircraft_hold))
        battery_rows.append(dict(resource=f'{r.kind}_battery_{job.battery}', kind=r.kind, resource_id=job.battery,
                                 battery_label=battery_label(r.kind, job.battery),
                                 job=index, route_id=r.id, occupied_start_s=job.start, departure_soc=1.0,
                                 returned_s=returned, return_soc=soc, consumed_kwh=r.energy,
                                 charging_start_s=returned, charge_duration_s=charge, full_available_s=job.start+r.battery_hold))
        for segment_id, seg in enumerate(r.segments):
            segment_rows.append(dict(job=index, route_id=r.id, segment=segment_id, phase=seg['phase'],
                                     start_s=job.start+seg['t0'], end_s=job.start+seg['t1'],
                                     from_xyz_m=json.dumps(seg['a']), to_xyz_m=json.dumps(seg['b'])))
    overlaps(transport_spans, 'transport')
    box_rows = []
    hard_count, hard_late, tardiness = 0, 0.0, 0.0
    for i, b in enumerate(p.boxes):
        events = delivery_events[i]
        if box_counts[i] != 1 or len(events) != 1:
            issue('transport', 'box_coverage_not_exactly_one', box=b.id, route_occurrences=box_counts[i], delivery_occurrences=len(events))
        for event in events or [None]:
            row = dict(box_id=b.id, box_index=i, node=b.node, mass_kg=b.mass, volume_m3=b.volume,
                       release_s=b.release, due_s=b.due, hard_due_s=b.hard_due, priority_weight=b.weight,
                       coverage=len(events), delivery_status='unserved' if event is None else ('delivered' if len(events)==1 else 'duplicated'))
            if event is not None:
                j, rid, kind, a, bat, arrival = event
                late = max(0., arrival-b.due)
                hard = 0. if b.hard_due is None else max(0., arrival-b.hard_due)
                hard_count += hard > tolerance
                hard_late += hard
                tardiness += b.weight*late
                row.update(job=j, route_id=rid, kind=kind, aircraft=a, battery=bat, delivered_s=arrival,
                           aircraft_id=aircraft_label(kind, a), battery_label=battery_label(kind, bat),
                           tardiness_s=late, weighted_tardiness_s=b.weight*late, hard_lateness_s=hard)
            box_rows.append(row)
    independently_recomputed_metrics = dict(trips=len(jobs), unserved=sum(len(delivery_events[i])==0 for i in range(len(p.boxes))),
        duplicated=sum(len(delivery_events[i])>1 for i in range(len(p.boxes))), hard_violations=hard_count,
        hard_lateness_s=hard_late, weighted_tardiness_s=tardiness,
        makespan_s=max((j.start+j.route.duration for j in jobs), default=0.), energy_kwh=sum(j.route.energy for j in jobs))
    for key, value in independently_recomputed_metrics.items():
        if key in raw.get('metrics', {}):
            close(raw['metrics'][key], value, 'transport', 'metrics.'+key)
    relay = p.data.get('relay', {})
    schedule_step = float(raw.get('detail', {}).get('schedule_step_s', 60.0))
    for index, s in enumerate(sessions):
        check_id(getattr(s, 'aircraft', None), relay['count'], 'relay', 'relay_aircraft', session=index)
        check_id(getattr(s, 'pack', None), relay['packs'], 'relay', 'relay_pack', session=index)
        if not (0 <= s.departure <= s.ready < s.stop <= s.returned <= min(s.aircraft_end, s.pack_end)+tolerance):
            issue('relay', 'invalid_session_time_order', session=index)
        depot = p.nodes[p.depot]
        horizontal = math.hypot(s.xyz[0]-depot.x, s.xyz[1]-depot.y)
        try:
            site_ground = float(p.terrain.height([s.xyz[:2]])[0])
            agl = s.xyz[2]-site_ground
            if not -tolerance <= agl <= 300+tolerance:
                issue('relay', 'height_outside_allowed_range', session=index, agl_m=agl)
            peak = max(p.terrain.peak(s.xyz[:2], [depot.x, depot.y], p.arc_step)+p.clearance, s.xyz[2], depot.z)
            outbound = (peak-depot.z)/relay['climb_speed']+horizontal/relay['speed']+(peak-s.xyz[2])/relay['descend_speed']
            inbound = (peak-s.xyz[2])/relay['climb_speed']+horizontal/relay['speed']+(peak-depot.z)/relay['descend_speed']
            preparation = float(relay.get('prepare', 0.))
            takeoff = s.departure+preparation
            arrival = takeoff+outbound
            if getattr(s, 'takeoff', None) is not None:
                close(s.takeoff, takeoff, 'relay', 'takeoff_s', session=index)
            if getattr(s, 'arrival', None) is not None:
                close(s.arrival, arrival, 'relay', 'arrival_s', session=index)
            if hasattr(s, 'preparation_s'):
                close(s.preparation_s, preparation, 'relay', 'preparation_s', session=index)
            if s.ready < arrival+relay['setup']-tolerance:
                issue('relay', 'service_before_arrival_and_setup', session=index)
            close(s.returned, s.stop+inbound, 'relay', 'returned_s', session=index)
            if relay.get('energy_model') == 'official_horizontal_climb':
                cruise_energy = relay['travel_kw']*2*horizontal/relay['speed']/3600
                climb_energy = relay['takeoff_mass_kg']*relay['gravity_m_s2']*((peak-depot.z)+(peak-s.xyz[2]))/(relay['climb_efficiency']*3.6e6)
                flight_energy = cruise_energy+climb_energy
                hover_energy = relay['hover_only_kw']*(s.stop-arrival)/3600
                communication_energy = relay['communication_kw']*(s.stop-arrival)/3600
                close(relay['hover_kw'], relay['hover_only_kw']+relay['communication_kw'], 'relay', 'hover_power_sum', session=index)
            else:
                cruise_energy, climb_energy = None, None
                flight_energy = relay['travel_kw']*(outbound+inbound)/3600
                hover_energy = relay['hover_kw']*(s.stop-arrival)/3600
                communication_energy = 0.
            expected_energy = flight_energy+hover_energy+communication_energy
            close(s.energy, expected_energy, 'relay', 'energy_kwh', session=index)
            for field, expected in (('flight_energy_kwh', flight_energy), ('cruise_energy_kwh', cruise_energy),
                                    ('climb_energy_kwh', climb_energy), ('hover_energy_kwh', hover_energy),
                                    ('communication_energy_kwh', communication_energy)):
                if expected is not None and getattr(s, field, None) is not None:
                    close(getattr(s, field), expected, 'relay', field, session=index)
            soc = 1-s.energy/relay['energy_kwh']
            if soc < relay['reserve']-tolerance:
                issue('relay', 'relay_energy_reserve_violation', session=index, soc=soc)
            charge = recharge_seconds(s.energy, relay['energy_kwh'], relay['full_charge'], relay['charge_knee'], relay['charge_slow'], relay.get('charge_table'))
            for stored, shortest, label in ((s.aircraft_end, s.returned+relay['turnaround'], 'aircraft_end'),
                                            (s.pack_end, s.returned+charge, 'pack_end')):
                if stored < shortest-tolerance or stored > shortest+schedule_step+tolerance:
                    issue('relay', 'invalid_postflight_hold', session=index, field=label, stored=stored, shortest=shortest)
            backhaul = margin(p, s.xyz, ground(p), p.data['radio']['backhaul_budget_db'])
            if backhaul < -tolerance:
                issue('relay', 'relay_backhaul_unavailable', session=index, margin_db=backhaul)
        except Exception as exc:
            issue('relay', 'relay_physical_reconstruction_error', session=index, exception=type(exc).__name__, message=str(exc))
            arrival, outbound, inbound, charge, soc, backhaul = [None]*6
            takeoff = s.departure
            flight_energy, cruise_energy, climb_energy, hover_energy, communication_energy = [None]*5
        relay_spans[f'relay_aircraft_{getattr(s,"aircraft",None)}'].append((s.departure, s.aircraft_end, index))
        relay_spans[f'relay_pack_{getattr(s,"pack",None)}'].append((s.departure, s.pack_end, index))
        relay_id = getattr(s, 'aircraft', None)
        relay_ids = metadata.get('relay_aircraft_ids', [])
        relay_label = relay_ids[relay_id] if isinstance(relay_id, int) and 0 <= relay_id < len(relay_ids) else (f'R{relay_id+1:02d}' if isinstance(relay_id, int) else None)
        relay_rows.append(dict(session=index, site=s.site, aircraft=getattr(s, 'aircraft', None), pack=getattr(s, 'pack', None),
                               aircraft_id=relay_label, pack_label=battery_label('R', getattr(s, 'pack', None)),
                               site_x_m=s.xyz[0], site_y_m=s.xyz[1], site_altitude_m=s.xyz[2], preparation_start_s=s.departure,
                               departure_s=takeoff,
                               arrived_s=arrival, ready_s=s.ready, service_stop_s=s.stop, returned_s=s.returned,
                               aircraft_available_s=s.aircraft_end, pack_full_s=s.pack_end, energy_kwh=s.energy,
                               flight_energy_kwh=flight_energy, cruise_energy_kwh=cruise_energy, climb_energy_kwh=climb_energy,
                               hover_energy_kwh=hover_energy, communication_energy_kwh=communication_energy,
                               return_soc=soc, charge_duration_s=charge, backhaul_margin_db=backhaul))
    overlaps(relay_spans, 'relay')
    fine = raw.get('detail', {}).get('fine_evaluation')
    if fine and fine.get('misses', 0):
        issue('radio', 'stored_fine_evaluation_has_disconnects', misses=fine['misses'])
    radio_check = None
    if not skip_radio and jobs and 'radio' in p.data:
        try:
            radio_check = evaluate_radio(p, jobs, sessions, dt=radio_step)
            if radio_check['misses']:
                issue('radio', 'recomputed_radio_disconnects', misses=radio_check['misses'], sample_step_s=radio_step)
            if fine and abs(float(fine.get('sample_step_s', -1))-radio_step)<tolerance:
                if fine['samples'] != radio_check['samples'] or fine['misses'] != radio_check['misses']:
                    issue('radio', 'stored_fine_evaluation_differs_from_recomputed')
                if fine.get('minimum_margin_db') is not None and radio_check.get('minimum_margin_db') is not None:
                    close(fine['minimum_margin_db'], radio_check['minimum_margin_db'], 'radio', 'minimum_margin_db')
        except Exception as exc:
            issue('radio', 'radio_reconstruction_error', exception=type(exc).__name__, message=str(exc))
    elif skip_radio:
        notes.append('Radio recomputation explicitly skipped; cannot certify joint feasibility.')
    transport_valid = not any(x['scope']=='transport' for x in issues)
    relay_valid = not any(x['scope']=='relay' for x in issues)
    radio_valid = radio_check is not None and not any(x['scope']=='radio' for x in issues)
    status = 'invalid' if issues else ('valid' if radio_valid else 'transport_valid_radio_not_checked')
    validation = dict(status=status,
        transport_valid=transport_valid, relay_valid=relay_valid, radio_valid=radio_valid,
        joint_valid=transport_valid and relay_valid and radio_valid,
        input=str(Path(input_path).resolve()), plan=str(Path(plan_path).resolve()), metadata=p.data.get('metadata', {}),
        runtime_model=str(active_model),
        exported_resource_labels='Aircraft IDs use input metadata when supplied; battery/relay-pack labels (A-B01, R-B01) are derived export labels, not attachment-provided serial numbers. Internal resource indices remain zero-based.',
        validation_scope='Independent coverage/inventory/all-pairs interval/deadline arithmetic; declared route and radio engines reused for physics.',
        charging_scope='Parallel charging; no unprovided finite charger inventory introduced.',
        stored_metrics=raw.get('metrics', {}), independently_recomputed_metrics=independently_recomputed_metrics,
        issues=issues, notes=notes, relay_sessions=len(sessions),
        radio_ray_step_m=p.data.get('radio', {}).get('ray_step_m'), radio_evaluation=radio_check,
        numerical_scope='Finite temporal and terrain-ray samples do not prove continuous-time communication.')
    write_csv(out/'per_box_delivery.csv', box_rows, ['box_id','box_index','node','mass_kg','volume_m3','release_s','due_s','hard_due_s','priority_weight','coverage','delivery_status','job','route_id','kind','aircraft','aircraft_id','battery','battery_label','delivered_s','tardiness_s','weighted_tardiness_s','hard_lateness_s'])
    write_csv(out/'transport_trips.csv', trips, ['job','route_id','kind','aircraft','aircraft_id','battery','battery_label','boxes','stops','mass_kg','volume_m3','start_s','first_motion_s','returned_s','aircraft_available_s','battery_full_s','energy_kwh','return_soc'])
    write_csv(out/'aircraft_timeline.csv', aircraft_rows, ['resource','kind','resource_id','aircraft_id','job','route_id','prepare_start_s','motion_start_s','returned_s','available_s'])
    write_csv(out/'battery_timeline.csv', battery_rows, ['resource','kind','resource_id','battery_label','job','route_id','occupied_start_s','departure_soc','returned_s','return_soc','consumed_kwh','charging_start_s','charge_duration_s','full_available_s'])
    write_csv(out/'transport_segments.csv', segment_rows, ['job','route_id','segment','phase','start_s','end_s','from_xyz_m','to_xyz_m'])
    write_csv(out/'relay_tasks.csv', relay_rows, ['session','site','aircraft','aircraft_id','pack','pack_label','site_x_m','site_y_m','site_altitude_m','preparation_start_s','departure_s','arrived_s','ready_s','service_stop_s','returned_s','aircraft_available_s','pack_full_s','energy_kwh','flight_energy_kwh','cruise_energy_kwh','climb_energy_kwh','hover_energy_kwh','communication_energy_kwh','return_soc','charge_duration_s','backhaul_margin_db'])
    dump(out/'validation.json', validation)
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--radio-step', type=float, default=10.)
    parser.add_argument('--skip-radio', action='store_true')
    parser.add_argument('--runtime', help='Directory containing the adapted research_fd package; original package is default')
    args = parser.parse_args()
    if args.radio_step <= 0:
        parser.error('--radio-step must be positive')
    result = validate_export(args.input, args.plan, args.out, args.radio_step, args.skip_radio, args.runtime)
    print(json.dumps({k: result[k] for k in ('status','transport_valid','relay_valid','radio_valid','independently_recomputed_metrics')}, ensure_ascii=False))
    print('Issues:', len(result['issues']))


if __name__ == '__main__':
    main()
