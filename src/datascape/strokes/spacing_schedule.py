"""Candidate A-row phase controls for the focused v3 spacing study."""
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.ndimage import binary_erosion, distance_transform_edt
from datascape.projection.composition import smoothstep
from datascape.strokes.generators import continuity_mask, contours, valid_runs
from datascape.strokes.vector import sample, resample
from datascape.strokes.mass_density import rhythm_weights, supported_blur


def phase_ablation(fixed, mass, baseline_profile, config, *, endpoint='local',
                   boundary_feather_mm=18, smoothing_mm=3,
                   maximum_displacement=8, minimum_derivative_ratio=.25):
    """Replay v2 with one explicitly variable constraint at a time."""
    b=fixed['base'];q=b['depth_m'];phi0=baseline_profile['phase_field']
    labels=mass['labels'];t=mass['t'];c=config['rhythm']
    rho=rhythm_weights(t,config)+c['D_support_gain']*mass['D_support']*(1-t)
    global_rho=float(np.mean(rho[labels>0]))
    correction=np.zeros_like(q);records=[]
    for item in mass['masses']:
        mid=item['label'];mask=labels==mid;delta=np.zeros_like(q);runs=0
        for x in range(q.shape[1]):
            ids=np.flatnonzero(mask[:,x]);parts=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
            for ys in parts:
                if len(ys)<c['minimum_column_run_mm']:continue
                qq=q[ys,x];order=np.argsort(qq,kind='stable');qs=qq[order]
                base=phi0[ys,x][order];rr=rho[ys,x][order]
                keep=np.r_[True,np.diff(qs)>1e-6];qs=qs[keep];base=base[keep];rr=rr[keep]
                if len(qs)<4 or qs[-1]-qs[0]<c['minimum_depth_span_m']:continue
                integral=np.r_[0,np.cumsum(np.diff(qs)*.5*(rr[:-1]+rr[1:]))]
                if integral[-1]<=0:continue
                if endpoint=='local':
                    new=base[0]+integral/integral[-1]*(base[-1]-base[0])
                elif endpoint=='global':
                    slope=(base[-1]-base[0])/(qs[-1]-qs[0])
                    new=base[0]+integral*slope/max(global_rho,1e-9)
                else:raise ValueError(endpoint)
                delta[ys,x]=np.interp(qq,qs,new-base);runs+=1
        if smoothing_mm>0:
            d=supported_blur(delta,mask,smoothing_mm)
        else:d=delta
        if boundary_feather_mm>0:
            dist=distance_transform_edt(mask)
            feather=smoothstep(np.maximum(dist-1,0)/boundary_feather_mm)
        else:
            dist=distance_transform_edt(mask);feather=np.ones_like(q)
        d*=feather
        d*=smoothstep((q-config['masses']['minimum_depth_m'])/c['scope_transition_m'])
        cap_fraction=float(np.mean(np.abs(d[mask])>maximum_displacement))
        d=np.clip(d,-maximum_displacement,maximum_displacement)
        correction[mask]=d[mask]
        records.append({'label':mid,'integrated_columns':runs,
            'mean_requested_weight':float(np.mean(rho[mask])),
            'endpoint_mode':endpoint,'boundary_zone_fraction':float(np.mean(dist[mask]<=18)),
            'cap_fraction':cap_fraction,'maximum_phase_displacement':float(np.max(np.abs(d[mask])))})
    qgy,qgx=np.gradient(q);pgy,pgx=np.gradient(phi0);base_d=pgx*qgx+pgy*qgy
    safe=binary_erosion(continuity_mask(b),iterations=2)&(labels>0)&(base_d>1e-8)
    gains=[]
    for rec in records:
        m=labels==rec['label'];dy,dx=np.gradient(np.where(m,correction,0))
        ratio=(dx*qgx+dy*qgy)/np.maximum(base_d,1e-8)
        worst=float(np.min(ratio[m&safe])) if np.any(m&safe) else 0
        gain=min(1.,(1-minimum_derivative_ratio)/max(-worst,1e-9))
        correction[m]*=gain;rec.update({'worst_unlimited_correction_ratio':worst,'topology_gain':gain})
        gains.append(gain)
    phase=phi0+correction;dy,dx=np.gradient(phase);actual=dx*qgx+dy*qgy
    ratio=np.ones_like(q);ratio[safe]=actual[safe]/base_d[safe]
    return {'phase':phase,'baseline_phase':phi0,'correction':correction,
            'directional_phase_ratio':ratio,'requested_density':rho,'safe':safe,
            'phase_derivative_nonpositive_pixels':int(np.sum(safe&(ratio<=0))),
            'integration':records}


def explicit_screen_spacing_phase(fixed, mass, baseline_profile, config,
                                  selected_labels=None, positions=None,
                                  multipliers=None, boundary_feather_mm=6):
    """Construct rows from a screen-space spacing schedule, not source-q budgets.

    The existing baseline phase supplies each form's projected reference pitch.
    A single form-wide normalization preserves its aggregate phase budget while
    allowing individual columns and terrain bands to gain or lose rows.
    """
    b=fixed['base'];phi0=baseline_profile['phase_field'];labels=mass['labels'];t=mass['t']
    if positions is None:positions=[0,.10,.28,.43,.60,.72,.88,1.0]
    if multipliers is None:multipliers=[1.45,1.45,.62,.62,1.45,1.45,.72,.48]
    positions=np.array(positions,float);multipliers=np.array(multipliers,float)
    if np.any(multipliers<=0):raise ValueError('Positive spacing multipliers are required')
    active=set(int(x) for x in (selected_labels if selected_labels is not None else np.unique(labels[labels>0])))
    correction=np.zeros_like(phi0);records=[]
    for mid in sorted(active):
        mask=labels==mid
        if not mask.any():continue
        runs=[];baseline_budget=0.;scheduled_budget=0.
        for x in range(mask.shape[1]):
            ids=np.flatnonzero(mask[:,x]);parts=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
            for ys in parts:
                if len(ys)<18:continue
                baseline=phi0[ys,x];dphi=np.diff(baseline)
                qd=np.diff(b['depth_m'][ys,x])
                # A projected run must retain a consistent forward orientation.
                good=np.abs(qd)>1e-6
                if good.mean()<.95 or (np.sign(qd[good]).mean()**2)<.9:continue
                sign=1 if np.median(dphi)>=0 else -1
                oriented=sign*dphi
                if np.mean(oriented>=-1e-7)<.95:continue
                oriented=np.maximum(oriented,0)
                tm=.5*(t[ys[:-1],x]+t[ys[1:],x])
                mult=np.interp(np.clip(tm,0,1),positions,multipliers)
                baseline_budget+=float(oriented.sum())
                scheduled_budget+=float(np.sum(oriented*mult))
                runs.append((x,ys,sign,oriented,mult))
        if not runs or scheduled_budget<=0:continue
        gain=baseline_budget/scheduled_budget
        delta=np.zeros_like(phi0);edges=0
        for x,ys,sign,oriented,mult in runs:
            inc=gain*oriented*mult
            new=np.r_[phi0[ys[0],x],phi0[ys[0],x]+sign*np.cumsum(inc)]
            delta[ys,x]=new-phi0[ys,x];edges+=len(ys)
        if boundary_feather_mm>0:
            dist=distance_transform_edt(mask)
            feather=smoothstep(np.maximum(dist-1,0)/boundary_feather_mm)
            delta*=feather
        # Low-pass only the correction field to prevent column-to-column seams.
        delta=supported_blur(delta,mask,1.0)
        correction[mask]=delta[mask]
        records.append({'label':mid,'runs':len(runs),'screen_phase_gain':gain,
            'screen_grid_edges':edges,'baseline_phase_budget':baseline_budget,
            'scheduled_phase_budget':scheduled_budget})
    q=b['depth_m'];qgy,qgx=np.gradient(q);pgy,pgx=np.gradient(phi0);base_d=pgx*qgx+pgy*qgy
    safe=binary_erosion(continuity_mask(b),iterations=2)&(labels>0)&(base_d>1e-8)
    unlimited=phi0+correction;uy,ux=np.gradient(unlimited);u_ratio=np.ones_like(q)
    u_ratio[safe]=(ux*qgx+uy*qgy)[safe]/base_d[safe]
    unlimited_folds=int(np.sum(safe&(u_ratio<=0)))
    for rec in records:
        mask=labels==rec['label'];dy,dx=np.gradient(np.where(mask,correction,0))
        local=(dx*qgx+dy*qgy)/np.maximum(base_d,1e-8)
        worst=float(np.min(local[mask&safe])) if (mask&safe).any() else 0
        gain=min(1.,.95/max(-worst,1e-9))
        correction[mask]*=gain;rec['topology_gain']=gain
    phase=phi0+correction
    dy,dx=np.gradient(phase);actual=dx*qgx+dy*qgy
    ratio=np.ones_like(q);ratio[safe]=actual[safe]/base_d[safe]
    return {'phase':phase,'baseline_phase':phi0,'correction':correction,
        'directional_phase_ratio':ratio,'safe':safe,
        'phase_derivative_nonpositive_pixels':int(np.sum(safe&(ratio<=0))),
        'unlimited_phase_derivative_nonpositive_pixels':unlimited_folds,
        'integration':records,'schedule_positions':positions.tolist(),
        'schedule_multipliers':multipliers.tolist()}


def explicit_source_spacing_phase(fixed, mass, baseline_profile, config,
                                  positions=None, multipliers=None,
                                  boundary_feather_mm=12, smoothing_mm=2,
                                  minimum_derivative_ratio=.05):
    """Apply an explicit crest-to-foot schedule to the existing projected pitch.

    Unlike v2, this weights the baseline phase derivative itself and normalizes
    once per terrain form. Adjacent paths therefore inherit the fixed F2 screen
    projection's local millimeter spacing, while columns may breathe differently.
    """
    b=fixed['base'];phi0=baseline_profile['phase_field'];q=b['depth_m']
    labels=mass['labels'];t=mass['t']
    if positions is None:positions=[0,.10,.28,.43,.60,.72,.88,1.0]
    if multipliers is None:multipliers=[1.45,1.45,.62,.62,1.45,1.45,.72,.48]
    positions=np.array(positions,float);multipliers=np.array(multipliers,float)
    if np.any(multipliers<=0):raise ValueError('Positive spacing multipliers are required')
    correction=np.zeros_like(phi0);records=[];runs_by_label={}
    for item in mass['masses']:
        mid=item['label'];mask=labels==mid;runs=[];budget=0.;weighted=0.
        for x in range(q.shape[1]):
            ids=np.flatnonzero(mask[:,x]);parts=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
            for ys in parts:
                if len(ys)<18:continue
                qq=q[ys,x];order=np.argsort(qq,kind='stable');qs=qq[order]
                base=phi0[ys,x][order];tt=t[ys,x][order]
                keep=np.r_[True,np.diff(qs)>1e-6];qs=qs[keep];base=base[keep];tt=tt[keep]
                if len(qs)<4 or qs[-1]-qs[0]<100:continue
                dphi=np.diff(base);sign=1 if np.median(dphi)>=0 else -1
                oriented=np.maximum(sign*dphi,0)
                if np.mean(sign*dphi>=-1e-7)<.95:continue
                tm=.5*(tt[:-1]+tt[1:]);mult=np.interp(np.clip(tm,0,1),positions,multipliers)
                budget+=float(oriented.sum());weighted+=float(np.sum(oriented*mult))
                runs.append((x,ys,order,base,sign,oriented,mult))
        if weighted<=0:continue
        gain=budget/weighted;delta=np.zeros_like(phi0)
        for x,ys,order,base,sign,oriented,mult in runs:
            phase_sorted=np.r_[base[0],base[0]+sign*np.cumsum(gain*oriented*mult)]
            delta[ys[order],x]=phase_sorted-base
        dist=distance_transform_edt(mask)
        if boundary_feather_mm>0:
            delta*=smoothstep(np.maximum(dist-1,0)/boundary_feather_mm)
        if smoothing_mm>0:delta=supported_blur(delta,mask,smoothing_mm)
        correction[mask]=delta[mask]
        records.append({'label':mid,'runs':len(runs),'form_global_gain':gain,
            'baseline_phase_budget':budget,'scheduled_phase_budget':weighted})
        runs_by_label[mid]=mask
    qgy,qgx=np.gradient(q);pgy,pgx=np.gradient(phi0);base_d=pgx*qgx+pgy*qgy
    safe=binary_erosion(continuity_mask(b),iterations=2)&(labels>0)&(base_d>1e-8)
    raw_phase=phi0+correction;uy,ux=np.gradient(raw_phase);u_ratio=np.ones_like(q)
    u_ratio[safe]=(ux*qgx+uy*qgy)[safe]/base_d[safe]
    unlimited_folds=int(np.sum(safe&(u_ratio<=0)))
    for rec in records:
        mask=runs_by_label[rec['label']];dy,dx=np.gradient(np.where(mask,correction,0))
        local=(dx*qgx+dy*qgy)/np.maximum(base_d,1e-8)
        worst=float(np.min(local[mask&safe])) if (mask&safe).any() else 0
        gain=min(1.,(1-minimum_derivative_ratio)/max(-worst,1e-9))
        correction[mask]*=gain;rec.update({'worst_correction_ratio':worst,'topology_gain':gain})
    phase=phi0+correction;dy,dx=np.gradient(phase);actual=dx*qgx+dy*qgy
    ratio=np.ones_like(q);ratio[safe]=actual[safe]/base_d[safe]
    return {'phase':phase,'baseline_phase':phi0,'correction':correction,
        'directional_phase_ratio':ratio,'safe':safe,
        'phase_derivative_nonpositive_pixels':int(np.sum(safe&(ratio<=0))),
        'unlimited_phase_derivative_nonpositive_pixels':unlimited_folds,
        'integration':records,'schedule_positions':positions.tolist(),
        'schedule_multipliers':multipliers.tolist()}


def trace_phase(phase, fixed, spacing_mm=3.0):
    """Trace the scalar field as continuous, source-validated A centerlines."""
    b=fixed['base'];paths=[];fallbacks=0
    levels=np.arange(.5,float(phase[b['occupied']].max()),1)
    for level,p in contours(phase,b['occupied'],levels):
        for run in valid_runs(p,b):
            coarse=resample(run,spacing_mm)
            if len(coarse)>=4:
                at=np.r_[0,np.cumsum(np.linalg.norm(np.diff(coarse,axis=0),axis=1))]
                curve=CubicSpline(at,coarse,axis=0,bc_type='natural')(np.linspace(0,at[-1],max(2,int(at[-1]/.5)+1)))
                checked=valid_runs(curve,b)
                if checked and all(np.max(np.abs(sample(phase,rr)-level))<.35 for rr in checked):
                    paths.extend(checked)
                else:paths.append(run);fallbacks+=1
            else:paths.append(run)
    strokes=[{'id':f'A-v3-{i:06d}','xy_mm':p.tolist(),'width_mm':.32,
        'layer':'A','preview_opacity':.82,'expression':{'intensity':.6,'pressure_calibrated':False}}
        for i,p in enumerate(paths)]
    length=sum(float(np.linalg.norm(np.diff(s['xy_mm'],axis=0),axis=1).sum()) for s in strokes)
    return strokes,{'raw_paths':len(strokes),'raw_length_mm':length,'spline_fallbacks':fallbacks}
