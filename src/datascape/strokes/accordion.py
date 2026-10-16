"""A-only phase schedules with spatially local monotonicity constraints."""
import numpy as np
from scipy import sparse
from scipy.ndimage import binary_erosion, distance_transform_edt
from datascape.projection.composition import smoothstep
from datascape.strokes.mass_density import rhythm_weights, supported_blur
from datascape.strokes.generators import continuity_mask


def interior_distance(mask):
    """Include the canvas border in the fixed zero-displacement collar."""
    return distance_transform_edt(np.pad(mask,1,constant_values=False))[1:-1,1:-1]


def integrated_target(fixed, reference, labels, density, *, feather_mm=18,
                      smoothing_mm=3, maximum_displacement=8):
    """Keep each continuous run's phase budget and change its internal spacing."""
    q=fixed['base']['depth_m']; delta=np.zeros_like(q); records=[]
    for mid in np.unique(labels[labels>0]):
        mask=labels==mid; local=np.zeros_like(q); runs=0
        for x in range(q.shape[1]):
            ids=np.flatnonzero(mask[:,x])
            for ys in np.split(ids,np.flatnonzero(np.diff(ids)>1)+1):
                if len(ys)<18:continue
                qq=q[ys,x]; order=np.argsort(qq,kind='stable'); qs=qq[order]
                base=reference[ys,x][order]; rho=density[ys,x][order]
                keep=np.r_[True,np.diff(qs)>1e-6]; qs=qs[keep];base=base[keep];rho=rho[keep]
                if len(qs)<4 or qs[-1]-qs[0]<70:continue
                integral=np.r_[0,np.cumsum(np.diff(qs)*.5*(rho[:-1]+rho[1:]))]
                if integral[-1]<=0:continue
                new=base[0]+integral/integral[-1]*(base[-1]-base[0])
                local[ys,x]=np.interp(qq,qs,new-base); runs+=1
        local=supported_blur(local,mask,smoothing_mm)
        local*=smoothstep(np.maximum(interior_distance(mask)-1,0)/feather_mm)
        delta[mask]=np.clip(local[mask],-maximum_displacement,maximum_displacement)
        records.append({'label':int(mid),'runs':runs})
    return reference+delta, records


def mountain_target(fixed, mass, reference_profile, config, release_strength=.65):
    """Existing crest/shoulder/descent anchors plus pre-omission A release."""
    rho=rhythm_weights(mass['t'],config)+config['rhythm']['D_support_gain']*mass['D_support']*(1-mass['t'])
    r=np.clip(fixed['retention'],0,1)
    release=1-release_strength*(1-smoothstep(r/.85))
    # A placement policy reads R; neither R nor its transfer is edited.
    requested=rho*release
    c=config['rhythm']
    target,records=integrated_target(fixed,reference_profile['phase_field'],mass['labels'],requested,
        feather_mm=c['boundary_feather_mm'],smoothing_mm=c['phase_smoothing_mm'],
        maximum_displacement=c['maximum_phase_displacement'])
    q=fixed['base']['depth_m'];sc=smoothstep((q-config['masses']['minimum_depth_m'])/config['rhythm']['scope_transition_m'])
    reference=reference_profile['phase_field'];target=reference+(target-reference)*sc
    return target, {'requested_density':requested,'release_multiplier':release,'integration':records}


def foreground_target(fixed, reference, cutoff=1600, settings=None):
    """Measured mounds/gentle retained ground versus low-flow A corridors."""
    c={'base_density':.80,'island_gain':1.40,'channel_gain':.65,
       'feature_smoothing_mm':5,'release_floor':.30,'release_full_retention':.80,
       'maximum_target_displacement':10,'target_feather_mm':15,'target_smoothing_mm':4}
    if settings:c.update(settings)
    f=fixed['features'];b=fixed['base'];o=continuity_mask(b);q=b['depth_m'];r=fixed['retention']
    gentle=1-smoothstep((np.nan_to_num(b['slope_deg'],nan=45)-4)/20)
    island=supported_blur((.68*f['mound']+.32*f['ridge'])*(.45+.55*gentle),o,c['feature_smoothing_mm'])
    channel=supported_blur(np.maximum(f['valley_small'],.65*f['valley_medium']),o,c['feature_smoothing_mm'])
    release=c['release_floor']+(1-c['release_floor'])*smoothstep(np.clip(r,0,1)/c['release_full_retention'])
    rho=np.clip(c['base_density']+c['island_gain']*island-c['channel_gain']*channel,.20,2.00)*release
    from scipy.ndimage import label
    labels,_=label(o&(q<cutoff))
    target,records=integrated_target(fixed,reference,labels,rho,feather_mm=c['target_feather_mm'],
        smoothing_mm=c['target_smoothing_mm'],maximum_displacement=c['maximum_target_displacement'])
    scope=1-smoothstep((q-(cutoff-250))/250)
    target=reference+(target-reference)*scope
    return target, {'island':island,'channel':channel,'requested_density':rho,'integration':records,'labels':labels,'parameters':c}


def local_monotone_projection(fixed, reference_phase, target_phase, baseline_phase,
                              domain, *, floor=.05, smoothness=4., maximum_change=10.,
                              boundary_mm=2, time_limit=180):
    """Project requested A phase locally; no whole-mass worst-pixel gain.

    A sparse convex quadratic program fits target displacement while smoothing
    neighboring displacements. Linear central-difference constraints keep the
    phase derivative along source-depth normals positive on the same checked
    surface used by v3. Fixed boundary pixels have zero displacement.
    """
    import osqp
    b=fixed['base'];q=b['depth_m'];h,w=q.shape
    qy,qx=np.gradient(q);py,px=np.gradient(baseline_phase)
    normalizer=px*qx+py*qy
    ry,rx=np.gradient(reference_phase);r_ratio=np.ones_like(q)
    safe=binary_erosion(continuity_mask(b),iterations=2)&(normalizer>1e-8)
    r_ratio[safe]=(rx*qx+ry*qy)[safe]/normalizer[safe]
    variable=domain&continuity_mask(b)&(interior_distance(domain)>boundary_mm)
    index=np.full(q.shape,-1,np.int32);index[variable]=np.arange(variable.sum());n=int(variable.sum())
    if not n:raise ValueError('No variable phase pixels')
    # Finite-difference stencil: constraints may include fixed zero neighbors.
    affected=np.zeros_like(safe)
    for dy,dx in [(0,1),(0,-1),(1,0),(-1,0)]:affected|=np.roll(variable,(dy,dx),(0,1))
    constrained=safe&affected
    yy,xx=np.where(constrained);nr=len(yy);rows=[];cols=[];values=[]
    den=normalizer[yy,xx]
    for dy,dx,factor in [(0,1,qx[yy,xx]/(2*den)),(0,-1,-qx[yy,xx]/(2*den)),(1,0,qy[yy,xx]/(2*den)),(-1,0,-qy[yy,xx]/(2*den))]:
        ids=index[yy+dy,xx+dx];good=ids>=0
        rows.extend(np.arange(nr)[good]);cols.extend(ids[good]);values.extend(factor[good])
    normal=sparse.coo_matrix((values,(rows,cols)),shape=(nr,n)).tocsc()
    lower=np.full(nr,floor-1e-7)-r_ratio[yy,xx]
    # Graph smoothness with a zero-displacement boundary collar.
    degree=np.zeros(n);gr=[];gc=[];gv=[]
    for dy,dx in [(0,1),(1,0)]:
        a=index[:h-dy,:w-dx];bb=index[dy:,dx:]
        both=(a>=0)&(bb>=0);ia=a[both];ib=bb[both]
        np.add.at(degree,ia,1);np.add.at(degree,ib,1)
        gr.extend(ia);gc.extend(ib);gv.extend(np.full(len(ia),-1.))
        gr.extend(ib);gc.extend(ia);gv.extend(np.full(len(ia),-1.))
        edge=(a>=0)&(bb<0);np.add.at(degree,a[edge],1)
        edge=(a<0)&(bb>=0);np.add.at(degree,bb[edge],1)
    lap=sparse.coo_matrix((gv,(gr,gc)),shape=(n,n)).tocsc()+sparse.diags(degree)
    P=sparse.eye(n,format='csc')+smoothness*lap
    target=(target_phase-reference_phase)[variable]
    A=sparse.vstack([normal,sparse.eye(n,format='csc')],format='csc')
    lo=np.r_[lower,np.full(n,-maximum_change)];hi=np.r_[np.full(nr,np.inf),np.full(n,maximum_change)]
    solver=osqp.OSQP();solver.setup(P=P,q=-target,A=A,l=lo,u=hi,
        eps_abs=1e-4,eps_rel=1e-4,max_iter=15000,verbose=False,polishing=True,time_limit=time_limit)
    solver.warm_start(x=np.zeros(n));res=solver.solve(raise_error=False)
    if res.x is None or res.info.status!='solved':
        raise RuntimeError('Phase QP did not converge: '+res.info.status)
    correction=np.zeros_like(q);correction[variable]=res.x
    phase=reference_phase+correction;gy,gx=np.gradient(phase);ratio=np.ones_like(q)
    ratio[safe]=(gx*qx+gy*qy)[safe]/normalizer[safe]
    remaining=int(np.sum(constrained&(ratio<=0)))
    if remaining:raise AssertionError(f'{remaining} nonpositive phase derivatives after local solve')
    return phase,{'solver_status':res.info.status,'iterations':int(res.info.iter),
        'variables':n,'normal_constraints':nr,'min_phase_ratio_checked':float(np.min(ratio[constrained])),
        'nonpositive_phase_derivative_pixels':remaining,
        'maximum_phase_change':float(np.max(abs(correction))),
        'target_rms_error':float(np.sqrt(np.mean((correction[variable]-target)**2))),
        'primal_residual':float(res.info.prim_res),'dual_residual':float(res.info.dual_res),
        'solve_time_seconds':float(res.info.solve_time),'correction':correction,
        'phase_ratio':ratio,'safe':constrained,'variable':variable}
