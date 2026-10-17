"""Support-relative 2.5D vector visibility, deliberately short of 3D certification.

All clipping is performed once on original source arc intervals. Raster fields
supply bounded spatial decisions, never white paint or alpha erasure. Source
forward distance is distinct from F2 mapped triangle ownership.
"""
from copy import deepcopy
import hashlib
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter
from rasterio.features import rasterize
from affine import Affine
from shapely.geometry import LineString, Point
from shapely.ops import substring
from datascape.strokes.vector import sample

SHAPE = (900, 600)


def digest(value):
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def burn(geometry):
    if geometry.is_empty:
        return np.zeros(SHAPE, bool)
    return rasterize([(geometry, 1)], out_shape=SHAPE, transform=Affine.identity(),
                     all_touched=True, dtype='uint8').astype(bool)


def contact(fixed, xy):
    """Interpolate on the owning final F2 triangle at the exact contact point."""
    x, y = map(float, xy)
    t = fixed['terrain']; iy, ix = int(y), int(x)
    if not (0 <= ix < 600 and 0 <= iy < 900):
        raise ValueError('Contact outside continuous painting')
    face_id = int(t['owners'][iy, ix])
    if face_id < 0:
        raise ValueError('Contact has no visible terrain owner')
    face = t['faces'][face_id]; p = t['pixel'][face]
    weights12 = np.linalg.solve((p[1:] - p[0]).T, np.array([x, y]) - p[0])
    weights = np.r_[1-weights12.sum(), weights12]
    # The owning raster cell may cross a triangle edge. Search adjacent owners
    # for the true point, rather than extrapolating a cell's triangle.
    if weights.min() < -1e-7:
        owners = t['owners'][max(0,iy-2):iy+3,max(0,ix-2):ix+3]
        found = False
        for fid in sorted(set(owners.ravel()) - {-1}):
            candidate = t['faces'][fid]; cp = t['pixel'][candidate]
            try: uv = np.linalg.solve((cp[1:]-cp[0]).T, np.array([x,y])-cp[0])
            except np.linalg.LinAlgError: continue
            ww = np.r_[1-uv.sum(),uv]
            if ww.min() >= -1e-7:
                face_id, face, p, weights = int(fid), candidate, cp, ww
                found = True; break
        if not found:
            raise ValueError('No containing mapped source triangle at contact')
    xyz = weights @ t['xyz'][face]
    b = fixed['base']
    eye=np.asarray(fixed['scene']['primary_eye_xy_m'],float)
    coef=np.asarray(fixed['scene']['look_target_xy_m'],float)-eye
    coef/=np.linalg.norm(coef)
    q=float((xyz[:2]-eye)@coef)
    # Lateral q derivative is measured from this triangle, not invented from mm.
    bary_dx = np.linalg.solve((p[1:]-p[0]).T,np.array([1.,0.]))
    xyz_dx = np.r_[-bary_dx.sum(),bary_dx] @ t['xyz'][face]
    return dict(xy_mm=[x,y], mapped_face_id=face_id,
                original_mesh_face_id=int(t['source_ids'][face_id]),
                barycentric=weights.tolist(), source_xyz_utm_m=xyz.tolist(),
                source_forward_m=q, lateral_q_per_mm=float(xyz_dx[:2]@coef),
                crs='EPSG:32652', slope_deg=float(b['slope_deg'][iy,ix]),
                ndvi=float(b['current_ndvi'][iy,ix]),
                effective_observations=float(b['current_observations'][iy,ix]),
                retained_ground=float(fixed['retention'][iy,ix]),
                evidence='mapped source triangle; objects are authored, not observed')


def depth_field(site, lateral_bound_m=35.):
    """Upright 2.5D sheet; lateral ground derivative bounded in source meters.

    The height direction has no fabricated world-size conversion. This cannot
    establish the depth of a leaning branch, a rock overhang or an unseen surface.
    """
    xx = np.arange(600)[None,:]+.5
    q = site['source_forward_m'] + np.clip((xx-site['xy_mm'][0]) *
         site['lateral_q_per_mm'], -lateral_bound_m, lateral_bound_m)
    return np.broadcast_to(q,SHAPE).copy()


def adapt(record, origin_kind, owner_id, family):
    r = deepcopy(record)
    for key in ('source_stroke_id','source_arc_mm','source_family'):
        if key in r:
            r['upstream_'+key] = r[key]
    r.update(origin_kind=origin_kind, owner_id=owner_id, source_family=family,
             source_stroke_id=record['id'],
             source_arc_mm=[0.,LineString(record['xy_mm']).length],
             material_channel='color-support' if family=='C' else 'structural-ink',
             physical_plotting_validated=False)
    return r


def clip_source(record, gate=None, force_reason=None, minimum_mm=2.8, step_mm=.35):
    """Intersect decision zeroes in original arc space; interpolate all profiles."""
    line = LineString(record['xy_mm']); length = line.length
    if force_reason:
        return [], dict(source_id=record['id'],source_length_mm=length,
                        kept_intervals_mm=[],removed_mm=length,
                        short_dropped_mm=0.,reasons=[force_reason])
    if record.get('origin_kind')=='new-catalog' and length<minimum_mm:
        return [],dict(source_id=record['id'],source_length_mm=length,
            kept_intervals_mm=[],removed_mm=length,short_dropped_mm=length,
            reasons=['post-catalog-minimum-path'])
    arcs = np.linspace(0,length,max(2,int(np.ceil(length/step_mm))+1))
    xy = np.asarray([line.interpolate(a).coords[0] for a in arcs])
    values,reasons = gate(xy,arcs,record) if gate else (np.ones(len(xy)),[])
    if np.all(values>0):
        return [deepcopy(record)],dict(source_id=record['id'],source_length_mm=length,
                kept_intervals_mm=[[0.,length]],removed_mm=0.,short_dropped_mm=0.,reasons=[])
    intervals=[]; start=0. if values[0]>0 else None
    for a,b,ga,gb in zip(arcs[:-1],arcs[1:],values[:-1],values[1:]):
        if ga>0>=gb:
            end=a+(b-a)*ga/(ga-gb)
            intervals.append((start,end)); start=None
        elif ga<=0<gb:
            start=a+(b-a)*(-ga)/(gb-ga)
    if start is not None: intervals.append((start,length))
    out=[]; kept=[];short=0.
    source_arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(record['xy_mm'],axis=0),axis=1))]
    for a,b in intervals:
        if b-a<minimum_mm:
            short+=b-a; continue
        part=substring(line,a,b); points=np.asarray(part.coords)
        # Exact substring endpoints and original vertices. No rounded endpoint
        # may re-enter an exclusion, and no chord can bridge an omitted interval.
        at=np.r_[a, a+np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        rec=deepcopy(record)
        for key in ('width_profile_mm','opacity_profile'):
            if key in rec:
                if len(rec[key])!=len(source_arc):raise ValueError('profile misalignment')
                rec[key]=np.interp(at,source_arc,record[key]).tolist()
        if 'intensity_samples' in rec.get('expression',{}):
            if len(record['expression']['intensity_samples'])!=len(source_arc):raise ValueError('intensity misalignment')
            rec['expression']['intensity_samples']=np.interp(at,source_arc,record['expression']['intensity_samples']).tolist()
        token=hashlib.sha256(f'{record["id"]}/{a:.9f}/{b:.9f}'.encode()).hexdigest()[:14]
        rec.update(id=record['id']+'/visible-'+token,xy_mm=points.tolist(),
                   source_stroke_id=record['id'],source_arc_mm=[float(a),float(b)],
                   omission_reasons=sorted(set(reasons)))
        out.append(rec);kept.append([float(a),float(b)])
    return out,dict(source_id=record['id'],source_length_mm=length,
        kept_intervals_mm=kept,removed_mm=length-sum(b-a for a,b in kept),
        short_dropped_mm=short,reasons=sorted(set(reasons)))


def visibility_field(fixed, q, tolerance_m=25.):
    b=fixed['base']; delta=b['depth_m']-q
    visible=(~b['occupied']) | (delta>=-tolerance_m)
    # Existing depth-matched local omission remains unchanged. It becomes real
    # interval omission for new geometry; it is not renderer transparency.
    cfg=fixed['vegetation_config'];local=fixed['retention']/np.maximum(fixed['refined']['global_retention'],1e-12)
    match=np.exp(-.5*(delta/cfg['omission_match_sigma_m'])**2)*b['occupied']
    retain=fixed['refined']['global_retention']*(1-match*(1-np.clip(local,0,1)))
    retain*=visible
    retain[898:]=0
    return retain,visible


def regions_from_tree(tree, visible, width_mm=.8):
    """Visible ink occupancy builds cores; empty lobes cannot create a mask."""
    from datascape.vegetation.tree_occlusion_proof import masks,MaskAssumptions
    m=masks(tree,MaskAssumptions(vegetation_width_mm=width_mm))
    # The v10 mask already contains .30 receiver radius + .15 edge tolerance.
    body=burn(m['body'].buffer(-.45)) & visible
    ink=np.zeros(SHAPE,bool)
    for mark in tree.marks:
        if mark.part=='foliage-field':
            ink |= burn(LineString(mark.xy).buffer(width_mm/2))
    ink &= visible
    sigma=float(np.clip(tree.height*.025,1.3,3.2))
    density=gaussian_filter(ink.astype(float),sigma=sigma)
    density*=visible
    # Absolute local ink-area occupancy at a declared one-mm raster / Gaussian
    # kernel; no pad hull, wash halo or per-tree peak normalization.
    core=np.clip((density-.075)/.13,0,1)
    transition=np.clip((density-.018)/.095,0,1)
    soft=np.maximum(.88*core,.55*transition)*visible
    sparse=ink & (density<.075)
    return dict(body=body,soft=soft,core=density>=.075,sparse=sparse,
                v10=burn(m['selective'])&visible,full=burn(m['full'])&visible,
                occupancy=density,sigma_mm=sigma,
                core_area_mm2=int((density>=.075).sum()),
                retained_foliage_footprint_mm2=int(ink.sum()))


def signed_clearance(mask):
    if not mask.any():return np.full(SHAPE,1e6)
    return distance_transform_edt(~mask)-distance_transform_edt(mask)


def behind_object(own,other,own_q,other_q):
    farther=own_q>other_q+25.
    if own.get('group') and own.get('group')==other.get('group'):
        # Explicit, bounded same-contact choice: tree in front of rock, and
        # opaque objects in front of Soil. This is ordinal contact intent,
        # never a fabricated metric offset or a global draw-order rule.
        rank={'tree':0,'rock':1,'soil':2}
        tied=np.abs(own_q-other_q)<=25.
        if rank.get(own['kind'],9)>rank.get(other['kind'],9):
            farther |= tied
        if own['kind']==other['kind']=='rock' and own.get('parent_mass_id')==other.get('parent_mass_id'):
            farther |= tied & (own.get('catalog_local_rank',0)>other.get('catalog_local_rank',0))
    return farther


def object_gate(fixed, obj, occluders, footprint_extra_mm=0.):
    retain=obj['retention']; q=obj['q']; hard=signed_clearance(~obj['visible'])
    global_safe=signed_clearance(fixed['refined']['global_retention']<=0)
    def gate(xy,arc,r):
        width=r.get('assumed_footprint_mm',r['width_mm'])+footprint_extra_mm
        receiver=width/2+.15+1.0 # explicit raster/decision sampling guard
        values=np.minimum(sample(hard,xy)-receiver,sample(global_safe,xy)-receiver)
        values=np.minimum(values,898-width/2-xy[:,1])
        values=np.minimum(values,np.minimum(xy[:,0]-width/2,600-width/2-xy[:,0]))
        # Stable source-keyed, long-wave omissions; no per-pixel random noise.
        ph=int(hashlib.sha256((r['id']+'/object-mist').encode()).hexdigest()[:8],16)/16**8
        threshold=.06+.40*(.5+.5*np.sin(arc/19+ph*2*np.pi))
        values=np.minimum(values,sample(retain,xy)-threshold)
        reasons=['locked-global-reserve','nearer-terrain','depth-matched-mist']
        own_q=sample(q,xy)
        for other in occluders:
            if other['id']==obj['id']:continue
            behind=behind_object(obj,other,own_q,sample(other['q'],xy))
            if not behind.any():continue
            body=sample(other['body_distance'],xy)-receiver
            values=np.minimum(values,np.where(behind,body,1e6))
            density=sample(other['regions']['soft'],xy)
            ph2=int(hashlib.sha256((r['id']+'/'+other['id']).encode()).hexdigest()[:8],16)/16**8
            softgate=.12+.78*ph2-density
            values=np.minimum(values,np.where(behind,softgate,1e6))
            reasons.append('visible-nearer-object:'+other['id'])
        return values,reasons
    return gate


def terrain_gate(fixed, objects, replacements=(), footprint_extra_mm=0.):
    def gate(xy,arc,r):
        own_q=sample(fixed['base']['depth_m'],xy)
        if r['source_family']=='V' and 'source_object_depth_m' in r:
            own_q=np.full(len(xy),r['source_object_depth_m'])
        width=max(r.get('width_profile_mm',[r['width_mm']]))+footprint_extra_mm
        receiver=width/2+.15+1.0
        values=np.ones(len(xy))*1e6; reasons=[]
        for obj in objects:
            behind=own_q>sample(obj['q'],xy)+25.
            # Depth-uncertain contact is preserved unless it crosses an exact
            # body footprint; no root-collar exemption through a solid trunk.
            equal=np.abs(own_q-sample(obj['q'],xy))<=25.
            body=sample(obj['body_distance'],xy)-receiver
            values=np.minimum(values,np.where(behind|equal,body,1e6))
            density=sample(obj['regions']['soft'],xy)
            ph=int(hashlib.sha256((r['id']+'/'+obj['id']).encode()).hexdigest()[:8],16)/16**8
            threshold=.12+.78*ph+.08*np.sin(arc/17+ph*5)
            values=np.minimum(values,np.where(behind,threshold-density,1e6))
            if np.any((behind|equal)&(body<0)) or np.any(behind&(threshold<density)):
                reasons.append('object:'+obj['id'])
        if r['source_family'] in ('A','C'):
            line=LineString(r['xy_mm'])
            for obj,region in replacements:
                # Soil owns its explicit host-ground intervals only. A farther
                # patch must not replace a nearer terrain or object surface.
                behind=own_q>=sample(obj['q'],xy)-25.
                inside=np.array([region.contains(Point(p)) for p in xy])
                values=np.minimum(values,np.where(inside&behind,-1.,1e6))
                if np.any(inside&behind):reasons.append('soil-surface-replacement:'+obj['id'])
        return values,reasons
    return gate
