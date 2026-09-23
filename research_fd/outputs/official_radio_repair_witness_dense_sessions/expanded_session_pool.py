def session_pool(p,demands,sites,step=60.,max_sessions=18000):
    if not demands: return [],{'requirements':0,'unreachable':[],'sites':len(sites)}
    cfg=p.data['relay'];depot=p.nodes[p.depot];base=[depot.x,depot.y,depot.z]
    cover=np.zeros((len(sites),len(demands)),bool);cache={}
    for s,xyz in enumerate(sites):
        for i,d in enumerate(demands):
            key=(s,tuple(d['xyz']))
            if key not in cache: cache[key]=margin(p,xyz,d['xyz'],p.data['radio']['access_budget_db'])>=0
            cover[s,i]=cache[key]
    unreachable=np.flatnonzero(~cover.any(axis=0)).tolist()
    times=np.array([d['time'] for d in demands]);slots=np.floor(times/step+1e-9).astype(int)
    sessions=[]
    for site,xyz in enumerate(sites):
        ids=np.flatnonzero(cover[site]);valid_slots=np.unique(slots[ids])
        physical=relay_flight_components(p,xyz)
        outbound=physical['outbound_s'];inbound=physical['inbound_s']
        prepare=float(cfg.get('prepare',0.))
        for lo in valid_slots:
            lead=math.ceil((prepare+outbound+cfg['setup'])/step)
            departure=(lo-lead)*step
            if departure<0: continue
            ready=lo*step
            # Include short windows, powers of two and the longest energy-feasible one.
            maxhover=(cfg['energy_kwh']*(1-cfg['reserve'])-physical['flight_energy_kwh'])*3600/physical['hover_total_kw']
            takeoff=departure+prepare;arrival=takeoff+outbound
            maxend=math.floor((arrival+maxhover)/step)
            ends=sorted(set(int(s)+1 for s in valid_slots if lo<=s<maxend))
            for hi in ends:
                if hi<=lo or hi>maxend: continue
                ids2=ids[(slots[ids]>=lo)&(slots[ids]<hi)]
                if len(ids2)==0: continue
                stop=hi*step;returned=stop+inbound
                hover_duration=stop-arrival
                energy=physical['flight_energy_kwh']+physical['hover_total_kw']*hover_duration/3600
                soc=max(0.,1-energy/cfg['energy_kwh']);a=cfg['charge_knee'];k=cfg['charge_slow']
                charge=cfg['full_charge']*(max(a-soc,0)+k*(1-max(a,soc)))/(a+k*(1-a))
                if cfg.get('charge_table') is not None:
                    table=np.asarray(cfg['charge_table'],float);charge=float(table[-1,1]-np.interp(soc,table[:,0],table[:,1]))
                sessions.append(Session(site,list(xyz),departure,ready,stop,returned,math.ceil((returned+cfg['turnaround'])/step)*step,math.ceil((returned+charge)/step)*step,energy,ids2.tolist(),
                    preparation_s=prepare,
                    departure_semantics='resource_start_before_preparation' if prepare else 'airborne_departure',
                    takeoff=takeoff,arrival=arrival,
                    flight_energy_kwh=physical['flight_energy_kwh'],
                    cruise_energy_kwh=physical['cruise_energy_kwh'],climb_energy_kwh=physical['climb_energy_kwh'],
                    hover_energy_kwh=(cfg['hover_only_kw'] if physical['official'] else cfg['hover_kw'])*hover_duration/3600,
                    communication_energy_kwh=cfg['communication_kw']*hover_duration/3600 if physical['official'] else 0.))
    # Cap is only computational. A truncated pool may miss a feasible solution.
    truncated=len(sessions)>max_sessions
    if truncated:
        sessions=sorted(sessions,key=lambda s:(-len(s.covers)/(1+(s.aircraft_end-s.departure)/step),s.energy))[:max_sessions]
    return sessions,{'requirements':len(demands),'unreachable':unreachable,'sites':len(sites),'sessions':len(sessions),'pool_truncated':truncated}
