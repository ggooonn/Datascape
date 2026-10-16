"""Redistribute transverse rows within visible terrain masses on fixed F2."""
from copy import deepcopy
import numpy as np
from scipy.ndimage import (label,maximum_filter,minimum_filter,gaussian_filter,
    binary_erosion,distance_transform_edt)
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.interpolate import PchipInterpolator,CubicSpline
from datascape.projection.composition import smoothstep
from datascape.strokes.generators import continuity_mask,contours,valid_runs
from datascape.strokes.vector import sample,resample
from datascape.strokes.density_rhythm import density_profile,foreground_a,transfer


def supported_blur(value,mask,sigma):
    return gaussian_filter(np.where(mask,value,0),sigma)/np.maximum(gaussian_filter(mask.astype(float),sigma),1e-8)


def mass_coordinates(fixed,parent,config):
    """Geodesic catchments of measured relief, separated at source jumps.

    Labels are analysis units, not geographic mountain names. Absolute height
    only locates summits; density uses each label's normalized relief.
    """
    b=fixed['base'];o=continuity_mask(b);z=fixed['_grammar_xyz'][:,:,2];q=b['depth_m'];c=config['masses']
    domain=o&(q>c['minimum_depth_m']);components,n=label(domain)
    seeds=[];next_seed=1;d_candidates=[]
    for s in parent:
        if s['layer']!='D':continue
        p=resample(s['xy_mm'],1);zz=sample(z,p);ii=np.argsort(-zz)
        for i in ii:
            x,y=np.floor(p[i]).astype(int)
            if 0<=y<900 and 0<=x<600 and domain[y,x]:d_candidates.append((x,y));break
    for component in range(1,n+1):
        mask=components==component
        if mask.sum()<c['minimum_component_pixels']:continue
        zz=supported_blur(z,mask,c['summit_smoothing_mm']);local=maximum_filter(np.where(mask,zz,-1e6),size=c['summit_window_mm'])
        broad=supported_blur(z,mask,c['prominence_scale_mm']);eligible=mask&(zz>=local-1e-6)&((zz-broad)>c['minimum_prominence_m'])
        yy,xx=np.where(eligible);order=np.argsort(-zz[yy,xx],kind='stable')
        y0,x0=np.unravel_index(np.argmax(np.where(mask,zz,-1e6)),z.shape)
        chosen=[np.array([x0,y0])]
        for x,y in d_candidates:
            pt=np.array([x,y])
            if mask[y,x] and min(np.linalg.norm(pt-p) for p in chosen)>=c['D_seed_spacing_mm']:chosen.append(pt)
        for i in order:
            pt=np.array([xx[i],yy[i]])
            if chosen and min(np.linalg.norm(pt-p) for p in chosen)<c['summit_spacing_mm']:continue
            chosen.append(pt)
        if not chosen:
            y,x=np.unravel_index(np.argmax(np.where(mask,zz,-1e6)),z.shape);chosen=[np.array([x,y])]
        for x,y in chosen:
            seeds.append({'label':next_seed,'seed_pixel_xy':[int(x),int(y)],'seed_source_xyz_m':fixed['_grammar_xyz'][y,x].tolist()});next_seed+=1
    # Multi-source geodesic assignment cannot cross a source jump or missing
    # surface. Valley costs favor separate neighboring mountain catchments.
    h,w=o.shape;index=np.arange(h*w).reshape(h,w);rows=[];cols=[];costs=[]
    xyz=fixed['_grammar_xyz'];valley=fixed['features']['valley_medium']
    for dy,dx in [(0,1),(1,0),(1,1),(1,-1)]:
        ya=slice(0,h-dy);yb=slice(dy,h)
        xa=slice(max(0,-dx),min(w,w-dx));xb=slice(max(0,dx),min(w,w+dx))
        aa=(ya,xa);bb=(yb,xb);valid=domain[aa]&domain[bb]
        step=np.linalg.norm(xyz[aa][:,:,:2]-xyz[bb][:,:,:2],axis=2)
        valid&=(step<110)
        rows.extend(index[aa][valid]);cols.extend(index[bb][valid]);costs.extend(np.maximum(step[valid],.1)*(1+3*(valley[aa][valid]+valley[bb][valid])/2))
    graph=coo_matrix((costs,(rows,cols)),shape=(h*w,h*w)).tocsr()
    seed_nodes=np.array([index[s['seed_pixel_xy'][1],s['seed_pixel_xy'][0]] for s in seeds])
    _,_,owners=dijkstra(graph,directed=False,indices=seed_nodes,min_only=True,return_predecessors=True)
    lookup={node:s['label'] for node,s in zip(seed_nodes,seeds)}
    labels=np.array([lookup.get(v,0) for v in owners],np.int32).reshape(h,w);labels[~domain]=0
    t=np.zeros_like(z);records=[];accepted=np.zeros_like(labels)
    for seed in seeds:
        m=(labels==seed['label'])&domain
        if m.sum()<c['minimum_mass_pixels']:continue
        low,top=np.percentile(z[m],[c['foot_percentile'],c['crest_percentile']]);span=top-low
        if span<c['minimum_relief_m']:continue
        tt=np.clip((top-z)/span,0,1);t[m]=tt[m];accepted[m]=seed['label']
        cy,cx=np.unravel_index(np.argmax(np.where(m,z,-1e6)),z.shape)
        y,x=np.where(m);records.append({**seed,'crest_pixel_xy':[int(cx),int(cy)],'crest_source_xyz_m':fixed['_grammar_xyz'][cy,cx].tolist(),
            'pixels':int(m.sum()),'bounds_mm':[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)],
            'relative_foot_elevation_m':float(low),'relative_crest_elevation_m':float(top),'relief_m':float(span)})
    # Frozen D contributes a read-only proximity signal, never a new D path.
    d=np.zeros(o.shape,bool)
    for s in parent:
        if s['layer']=='D':
            p=np.floor(resample(s['xy_mm'],.5)).astype(int);d[np.clip(p[:,1],0,899),np.clip(p[:,0],0,599)]=True
    proximity=np.exp(-.5*(distance_transform_edt(~d)/config['rhythm']['D_support_sigma_mm'])**2) if d.any() else np.zeros_like(z)
    return {'labels':accepted,'t':t,'D_support':proximity,'masses':records}


def rhythm_weights(t,config):
    c=config['rhythm'];return PchipInterpolator(c['positions'],c['relative_density'])(np.clip(t,0,1))


def phase_redistribution(fixed,mass,baseline_profile,config):
    """Conserve phase counts at each mass/run boundary; no global density gain.

    Cumulative integration redistributes rows inside each source-continuous
    column run. A shared field is authored before panel splitting.
    """
    b=fixed['base'];q=b['depth_m'];phi0=baseline_profile['phase_field'];labels=mass['labels'];t=mass['t'];c=config['rhythm']
    rho=rhythm_weights(t,config)+c['D_support_gain']*mass['D_support']*(1-t)
    correction=np.zeros_like(q);records=[]
    for item in mass['masses']:
        mid=item['label'];mask=labels==mid;delta=np.zeros_like(q);runs=0
        for x in range(q.shape[1]):
            ids=np.flatnonzero(mask[:,x]);parts=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
            for ys in parts:
                if len(ys)<c['minimum_column_run_mm']:continue
                qq=q[ys,x];order=np.argsort(qq,kind='stable');qs=qq[order];base=phi0[ys,x][order];rr=rho[ys,x][order]
                keep=np.r_[True,np.diff(qs)>1e-6];qs=qs[keep];base=base[keep];rr=rr[keep]
                if len(qs)<4 or qs[-1]-qs[0]<c['minimum_depth_span_m']:continue
                # Integrate in source meters: the v1 global depth-frequency
                # profile supplies endpoint budgets, not the local rhythm.
                increments=np.diff(qs)*.5*(rr[:-1]+rr[1:]);integral=np.r_[0,np.cumsum(increments)]
                if integral[-1]<=0:continue
                phase=base[0]+integral/integral[-1]*(base[-1]-base[0])
                delta[ys,x]=np.interp(qq,qs,phase-base);runs+=1
        # Return continuously to original row phase at every analysis boundary.
        dist=distance_transform_edt(mask);feather=smoothstep(np.maximum(dist-1,0)/c['boundary_feather_mm'])
        delta=supported_blur(delta,mask,c['phase_smoothing_mm'])*feather
        delta*=smoothstep((q-config['masses']['minimum_depth_m'])/c['scope_transition_m'])
        delta=np.clip(delta,-c['maximum_phase_displacement'],c['maximum_phase_displacement'])
        correction[mask]=delta[mask]
        records.append({'label':mid,'integrated_columns':runs,'max_phase_displacement':float(np.max(np.abs(delta[mask])))})
    # A phase field is a path placement coordinate, not a terrain deformation.
    gy,gx=np.gradient(q);py,px=np.gradient(phi0);base_derivative=px*gx+py*gy
    safe=binary_erosion(continuity_mask(b),iterations=2)&(labels>0)&(base_derivative>1e-8)
    # Bound the phase derivative along original transverse normals. This
    # prevents folded/closed stroke-coordinate pockets, not terrain changes.
    for item in records:
        mask=labels==item['label'];dy,dx=np.gradient(np.where(mask,correction,0));ratio=(dx*gx+dy*gy)/np.maximum(base_derivative,1e-8)
        worst=float(np.min(ratio[mask&safe])) if (mask&safe).any() else 0.
        gain=min(1.,(1-c['minimum_phase_derivative_ratio'])/max(-worst,1e-9))
        correction[mask]*=gain;item['topology_gain']=gain
    phase=phi0+correction;dy,dx=np.gradient(phase)
    base_derivative=px*gx+py*gy;actual=dx*gx+dy*gy
    ratio=np.ones_like(q);ratio[safe]=actual[safe]/base_derivative[safe]
    return {'phase':phase,'baseline_phase':phi0,'requested_density':rho,'correction':correction,'directional_phase_ratio':ratio,
        'integration':records,'phase_derivative_nonpositive_pixels':int(np.sum(safe&(ratio<=0)))}


def generate_a(fixed,fields,parent,config,parent_mist):
    b=fixed['base'];phase=fields['phase'];paths=[];level_ids=[];fallbacks=0
    levels=np.arange(.5,float(phase[b['occupied']].max()),1)
    for level,p in contours(phase,b['occupied'],levels):
        for run in valid_runs(p,b):
            coarse=resample(run,config['spline_knot_mm'])
            if len(coarse)>=4:
                at=np.r_[0,np.cumsum(np.linalg.norm(np.diff(coarse,axis=0),axis=1))]
                curve=CubicSpline(at,coarse,axis=0,bc_type='natural')(np.linspace(0,at[-1],max(2,int(at[-1]/.5)+1)))
                # Keep interpolation on its actual phase surface.
                checked=valid_runs(curve,b)
                if checked and all(np.max(np.abs(sample(phase,rr)-level))<config['maximum_spline_phase_error'] for rr in checked):
                    paths.extend(checked);level_ids.extend([level]*len(checked))
                else:paths.append(run);level_ids.append(level);fallbacks+=1
            else:paths.append(run);level_ids.append(level)
    raw=[{'id':f'A-mass-{i:06d}','xy_mm':p.tolist(),'width_mm':.32,'layer':'A','preview_opacity':.82,
        'expression':{'intensity':.6,'pressure_calibrated':False}} for i,p in enumerate(paths)]
    raw=foreground_a(raw,fixed,.72)
    strokes=transfer(raw,fixed,parent_mist)
    # Preserve the previously selected foreground A exactly. This is a scope
    # boundary, not an elevation or screen-height driver of mountain density.
    cutoff=config['masses']['minimum_depth_m']
    near=[deepcopy(s) for s in parent if s['layer']=='A' and np.mean(sample(b['depth_m'],resample(s['xy_mm'],1)))<cutoff]
    strokes=[s for s in strokes if np.mean(sample(b['depth_m'],resample(s['xy_mm'],1)))>=cutoff]
    for s in strokes:s['id']='v2-'+s['id']
    return near+strokes,raw,{'raw_paths':len(raw),'unchanged_foreground_paths':len(near),'new_mountain_paths':len(strokes),'native_contour_fallbacks':fallbacks}
