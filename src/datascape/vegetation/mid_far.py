"""Derived mid/far grammar on saved F2 evidence, separate from accepted catalogs.

The 1-mm float32 terrain and float16 retention archives are reduced-precision
evidence, not a reconstructed exact source mesh. Every new root explicitly
reports this limitation. All original records and source identities are read-only.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, substring

from datascape.strokes.vector import sample, resample, phase, read_vectors
from datascape.integration.visibility import clip_source, digest
from datascape.vegetation.tree_final_scale import make_tree, bundles, vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class Evidence:
    depth: np.ndarray
    xyz: np.ndarray
    ndvi: np.ndarray
    observations: np.ndarray
    occupied: np.ndarray
    retention: np.ndarray
    global_retention: np.ndarray
    protected_clearance: np.ndarray
    provenance: dict

    def point(self, xy):
        p = np.asarray(xy, float).reshape(1, 2)
        return dict(xy_mm=p[0].tolist(), source_forward_m=float(sample(self.depth, p)[0]),
                    source_xyz_utm_m=[float(sample(self.xyz[:, :, j], p)[0]) for j in range(3)],
                    ndvi=float(sample(self.ndvi, p)[0]),
                    effective_observations=float(sample(self.observations, p)[0]),
                    retained_ground=float(sample(self.retention, p)[0]),
                    depth_provider='saved-F2-1mm-raster-float32', crs='EPSG:32652',
                    contact_precision='Raster interpolation only; no exact triangle or observed trunk claim')


def load_evidence(root, config, checkpoint):
    root = Path(root)
    files = {k: root / v for k, v in config['field_paths'].items()}
    base = np.load(files['base']); keep = np.load(files['retention']); glob = np.load(files['global'])
    occupied = base['occupied'].copy()
    recorded = json.loads((checkpoint / 'artifacts/record.json').read_text())['field_sha256']
    if hashlib.sha256(occupied.tobytes()).hexdigest() != recorded['occupied']:
        raise ValueError('Saved F2 ownership domain differs from checkpoint')
    retention = keep['terrain_retention_C'].astype(float)
    global_r = glob['global_retention'].astype(float)
    # Add no new mist field. This conservative guard protects existing zero
    # cells and the original two-mm bottom reserve, including footprint/cap.
    protected = (retention <= 0) | (global_r <= 0) | ~occupied
    protected[898:] = True
    clearance = distance_transform_edt(~protected) - distance_transform_edt(protected)
    provenance = dict(files={str(p.relative_to(root)): sha_file(p) for p in files.values()},
        grid_mm=1, depth_dtype=str(base['depth_m'].dtype), xyz_dtype=str(base['xyz'].dtype),
        retention_dtype=str(keep['terrain_retention_C'].dtype),
        occupancy_exact_checkpoint_hash=True, full_float64_field_hash_equality=False,
        precision_note='Same inherited F2 archives; quantized depth/retention are not the exact v04 float64 arrays',
        missing=['Original MASTER/VEG TIFFs', 'exact mapped F2 triangles and owners', 'full-precision v04 field cache'])
    return Evidence(base['depth_m'].astype(float), base['xyz'].astype(float),
                    base['current_ndvi'].astype(float), base['current_observations'].astype(float),
                    occupied, retention, global_r, clearance, provenance)


def local_flow_index(baseline):
    """Measured A tangent; B tangent is retained separately for diagnostics."""
    result = {}
    for layer in ['A', 'B']:
        positions = []; directions = []; ids = []
        for r in baseline:
            if r['layer'] != layer:
                continue
            p = resample(r['xy_mm'], 2.)
            if len(p) < 2:
                continue
            v = np.diff(p, axis=0); length = np.linalg.norm(v, axis=1)
            good = length > 1e-8
            v = v[good] / length[good, None]
            v[v[:, 0] < 0] *= -1
            positions.extend(((p[:-1]+p[1:])/2)[good]); directions.extend(v)
            ids.extend([r['id']] * int(good.sum()))
        result[layer] = (cKDTree(positions), np.asarray(directions), ids)
    return result


def flow_at(index, xy):
    result = {}
    for layer, (tree, directions, ids) in index.items():
        distance, j = tree.query(xy)
        result[layer] = dict(distance_mm=float(distance), tangent=directions[j].tolist(), source_id=ids[j])
    return result


def make_scaffold(crop, evidence, sites, flow, config):
    """One latent root set shared by representations; no screen-height bands.

    Unequal Gaussian supports are authored around existing measured contacts,
    rotated by actual A flow and bounded by source-depth, evidence and reserves.
    These weights are pictorial interpretation, not inferred vegetation truth.
    """
    group_sites = [s for s in sites if s['kind'] == 'tree' and s['group'] == crop['group']]
    x0, y0, x1, y1 = crop['bounds_mm']
    yy, xx = np.mgrid[y0:y1, x0:x1]; points = np.c_[xx.ravel()+.5, yy.ravel()+.5]
    density = np.zeros(len(points)); parents = []
    for i, (j, weight, radii) in enumerate(zip(crop['parent_site_indices'], crop['parent_weights'], crop['parent_radii_mm'])):
        site = group_sites[j]; center = np.asarray(site['site']['xy_mm'])
        fi = flow_at(flow, center); tangent = np.asarray(fi['A']['tangent']); normal = np.array([-tangent[1], tangent[0]])
        delta = points-center
        value = weight*np.exp(-.5*((delta@tangent/radii[0])**2+(delta@normal/radii[1])**2))
        parents.append(dict(id=f'{crop["id"]}/mass-{i}', exact_checkpoint_site_id=site['object_id'],
                            xy_mm=center.tolist(), source_forward_m=site['site']['source_forward_m'],
                            weight=weight, radii_mm=radii, A_flow=fi['A'], B_flow=fi['B']))
        density += value
    gap = np.asarray(group_sites[crop['gap_site_index']]['site']['xy_mm'])
    d = points-gap; gr = crop['gap_radius_mm']
    density *= 1-crop['gap_strength']*np.exp(-.5*((d[:,0]/gr[0])**2+(d[:,1]/gr[1])**2))
    occ = evidence.occupied[y0:y1, x0:x1].ravel()
    depth = evidence.depth[y0:y1, x0:x1].ravel()
    ndvi = evidence.ndvi[y0:y1, x0:x1].ravel()
    obs = evidence.observations[y0:y1, x0:x1].ravel()
    q0, q1 = crop['source_q_range_m']
    # NDVI supports likelihood only; the low floor retains plausible open
    # vegetation, without inferring species or converting it into observed trees.
    likelihood = .25+.75*np.clip((np.nan_to_num(ndvi)-.08)/.42, 0, 1)
    eligible = occ & np.isfinite(depth) & (depth>=q0) & (depth<=q1) & (obs>=3)
    eligible &= evidence.global_retention[y0:y1, x0:x1].ravel()>0
    # Do not exclude local mist yet: visibility is compared using one raw set.
    eligible &= density > .10
    weights = density*likelihood*eligible
    if weights.sum() == 0:
        raise ValueError('No supported terrain in crop')
    rng = np.random.default_rng(config['seed']+ord(crop['id']))
    ids = rng.choice(len(points), size=min(18000, len(points)), replace=False,
                     p=(weights+1e-20)/(weights+1e-20).sum())
    roots = []; spacing = crop['root_spacing_mm']
    for j in ids:
        if not eligible[j]:
            continue
        xy = points[j]
        if any(np.linalg.norm(xy-np.array(old['xy_mm']))<spacing for old in roots):
            continue
        owner = int(np.argmin([np.linalg.norm((xy-np.array(p['xy_mm']))/np.array(p['radii_mm'])) for p in parents]))
        site = evidence.point(xy); f = flow_at(flow, xy)
        h0, h1 = crop['native_height_range_mm']
        # A declared pictorial depth schedule, not world-height projection.
        h = h1-(h1-h0)*np.clip((site['source_forward_m']-q0)/(q1-q0),0,1)
        h *= .92+.16*phase(f'{crop["id"]}/root-{len(roots)}', config['seed'])
        h = max(22., h)
        form = ['B', 'B', 'U', 'P', 'B'][len(roots)%5]
        roots.append(dict(id=f'mfv01/{crop["id"]}/root-{len(roots):03d}', xy_mm=xy.tolist(),
                          parent_mass_id=parents[owner]['id'], family=form, native_height_mm=float(h),
                          density=float(density[j]), site=site, flow=f))
        if len(roots)>=crop['root_count']:
            break
    return dict(roots=roots, parents=parents, density=density.reshape(xx.shape),
                eligible=eligible.reshape(xx.shape), likelihood=likelihood.reshape(xx.shape),
                original_group_site_ids=[s['object_id'] for s in group_sites])


def native_sources(scaffold, config):
    """Call immutable Tree v10 at native dimensions; preserve original IDs."""
    sources = []; templates = []; trees = []
    for root in scaffold['roots']:
        ident = root['id']; form = root['family']; h = root['native_height_mm']
        seed = int(phase(ident, config['seed'])*2**32)
        tree = make_tree(form, root=root['xy_mm'], height=h, identity=ident, seed=seed,
                         profile='v09' if form=='U' else 'refined',
                         growth_controls=GrowthControls(stem_ratio=.85, vigor=1.))
        records = vector_records(tree.marks, [tree])
        sources.extend(records); trees.append(tree)
        info = tree.canopy_diagnostics
        for key, marks in bundles(tree.marks).items():
            matching = [r for r in records if r.get('component_key') in {m.key for m in marks}]
            points = np.concatenate([m.xy for m in marks]); anchor = points.mean(axis=0)
            templates.append(dict(id=ident+'/'+key, root=root, anchor=anchor, marks=marks,
                                  source_records=matching, catalog_hash=digest(records)))
    return sources, templates, trees


def make_record(ident, points, root, template, mode, part, config):
    return dict(id=ident, xy_mm=np.asarray(points,float).tolist(), layer='derived-vegetation',
        width_mm=.28 if part=='principal-structure' else .26, opacity=1., preview_opacity=.82,
        source_stroke_id=ident, source_arc_mm=[0.,float(LineString(points).length)],
        owner_id=root['id'], group_id=root['parent_mass_id'], unit_id=template['id'],
        source_family='derived-mid-far', representation=mode, grammar_part=part,
        catalog_form=root['family'], native_height_mm=root['native_height_mm'],
        catalog_source_ids=[r['id'] for r in template['source_records']],
        catalog_source_hash=template['catalog_hash'], source_forward_m=root['site']['source_forward_m'],
        root_xy_mm=root['xy_mm'], terrain_A_source_id=root['flow']['A']['source_id'],
        terrain_B_source_id=root['flow']['B']['source_id'],
        depth_provider=root['site']['depth_provider'],
        source_site=root['site'], origin_kind='new-derived-vegetation', assumed_footprint_mm=config['footprint_mm'],
        physical_plotting_validated=False, geographic_status='data-supported terrain; procedural growth; authored pictorial placement')


def derive(scaffold, source_records, templates, crop, mode, config):
    """One crown representation system; modes select hierarchy and compression.

    Crown mode retains source foliage and a few principal structures. Field
    mode compresses pad layout, then rebuilds each inherited ray at a useful
    physical length. Neither scales a completed Tree specimen below H22.
    """
    if mode not in ('crowns', 'field'):
        raise ValueError('Unknown representation')
    accepted = []; rejected = []; occupied_units = []
    by_root = {r['id']:r for r in scaffold['roots']}
    # Dominant high-density centers win clearance; light fringes are subordinate.
    order = sorted(templates, key=lambda t:(-t['root']['density'], t['id']))
    for template in order:
        root = template['root']; anchor = template['anchor']; xyroot=np.asarray(root['xy_mm'])
        u = phase(template['id']+'/hierarchy', config['seed'])
        if mode=='crowns' and u > .82:
            rejected.append(dict(unit_id=template['id'], reason='crown-open-unit')); continue
        # Preserve branch-led layout and asymmetry; compress pad *positions*
        # in far mode while retaining meaningful minimum ray lengths.
        compression = .38 if crop['mode']=='far' else .82 if mode=='field' else 1.
        pivot = xyroot+(anchor-xyroot)*compression
        angle = math.atan2(*root['flow']['A']['tangent'][::-1])
        angle = float(np.clip(angle*.35,-.25,.25))
        rot = np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
        unit = []
        marks = template['marks']
        max_touches = 1 if crop['mode']=='far' and mode=='crowns' else 2
        for i,m in enumerate(marks[:max_touches]):
            p = np.asarray(m.xy); length = LineString(p).length
            if mode=='crowns' and crop['mode']!='far':
                out = xyroot+(p-xyroot)@rot.T
            else:
                direction = (p-p[0])@rot.T
                # Retain inherited curvature and unit fan angles; physical
                # lengths vary coherently per unit, not independent noise.
                span = 1.0 if crop['mode']=='far' else 1.7
                # Small v10 source rays often all equal the execution floor.
                # Rebuild a correlated unit length hierarchy above that floor
                # instead of inheriting a page of identical 2.8-mm dashes.
                target = config['minimum_length_mm']+span*(.18+.72*u+.10*i/max(len(marks),1))
                start = pivot+(p[0]-anchor)@rot.T*.60
                out = start+direction*target/max(length,1e-9)
            if LineString(out).length < config['minimum_length_mm']-1e-8:
                continue
            unit.append(make_record(f'{template["id"]}/{mode}/ray-{i}',out,root,template,mode,'directional-foliage',config))
        if not unit:
            continue
        shape = unary_union([LineString(r['xy_mm']) for r in unit])
        minimum = config['footprint_mm']+config['free_gap_mm']+config['sampling_guard_mm']
        distance = min([shape.distance(other) for other in occupied_units], default=1e6)
        if distance < minimum:
            rejected.append(dict(unit_id=template['id'],reason='cross-unit-footprint-gap',nearest_mm=distance));continue
        occupied_units.append(shape);accepted.extend(unit)
    if crop['mode']=='middle':
        for root in scaffold['roots']:
            # Partial trunk suppression is shared between overlapping crowns;
            # only selected native principal structures survive.
            probability=.24 if mode=='crowns' else .34
            if phase(root['id']+'/trunk',config['seed'])>probability:
                continue
            rr=[r for r in source_records if r.get('source_root_id')==root['id'] and
                r['grammar_part'] in (('trunk-contour','branch-contour') if mode=='crowns' else ('branch-contour',))]
            if not rr:continue
            template = next(t for t in templates if t['root']['id']==root['id'])
            for r in rr[:2 if mode=='crowns' else 1]:
                if LineString(r['xy_mm']).length>=config['minimum_length_mm']:
                    rec=make_record(r['id']+'/derived-principal',r['xy_mm'],root,template,mode,'principal-structure',config)
                    rec['catalog_source_ids']=[r['id']];accepted.append(rec)
    return accepted, rejected


def root_visibility(evidence, record, xy):
    """Same locked source-depth match semantics, on explicit quantized evidence."""
    q=record['source_forward_m'];background=sample(evidence.depth,xy)
    occ=sample(evidence.occupied.astype(float),xy,order=0)>.5
    global_r=sample(evidence.global_retention,xy)
    local=sample(evidence.retention,xy)/np.maximum(global_r,1e-12)
    delta=np.nan_to_num(background-q,nan=1e6)
    match=np.exp(-.5*(delta/220.)**2)*occ
    visible=(~occ)|(delta>=-25.)
    ret=global_r*(1-match*(1-np.clip(local,0,1)))
    return ret,visible


def visible_records(records,evidence,config,treatment='improved'):
    """Separate safe geometry clipping from deterministic whole-unit dissolution.

    Raw geometry is identical in inherited/improved comparisons. Fully omitted
    cells always stay empty. Improved occurrence and unequal endpoint retreat
    affect real paths, never display alpha.
    """
    result=[];ledger=[]
    for record in records:
        raw=deepcopy(record);line=LineString(raw['xy_mm']);length=line.length
        raw.setdefault('source_arc_mm',[0.,length])
        dense=resample(raw['xy_mm'],.25);ret,_=root_visibility(evidence,raw,dense)
        strength=float(np.clip((np.mean(ret)-.08)/.62,0,1))
        quantile=phase(raw['unit_id']+'/mist-occurrence',config['seed'])
        probability=.10+.90*strength**.8
        shortened=0.
        if treatment=='improved' and quantile>probability:
            ledger.append(dict(source_id=raw['id'],source_length_mm=length,kept_intervals_mm=[],
                               removed_mm=length,reason='whole-unit-mist-omission',mean_retention=float(np.mean(ret)),
                               strength=strength,selection_probability=probability));continue
        # Retreat selected weak fragments, rather than every stroke equally.
        if treatment=='improved' and strength<.82 and phase(raw['id']+'/retreat',config['seed'])<.65:
            retreat=(1-strength)*.55
            a=length*retreat*phase(raw['id']+'/left',config['seed'])
            b=length*(1-retreat*phase(raw['id']+'/right',config['seed']))
            if b-a<config['minimum_length_mm']:
                ledger.append(dict(source_id=raw['id'],source_length_mm=length,kept_intervals_mm=[],removed_mm=length,
                                   reason='retreat-below-physical-floor',mean_retention=float(np.mean(ret))));continue
            raw['xy_mm']=np.asarray(substring(line,a,b).coords).tolist();shortened=length-(b-a)
            raw['parent_interval_mm']=[a,b]
        def gate(xy,arc,r):
            retention,visible=root_visibility(evidence,r,xy)
            margin=config['footprint_mm']/2+1.4
            safe=sample(evidence.protected_clearance,xy,order=0)-margin
            # This is the inherited v03 object-mist threshold, without changing
            # local/global field semantics or synthesizing screen-height bands.
            ph=phase(r['id']+'/object-mist',config['seed'])
            threshold=.06+.40*(.5+.5*np.sin(arc/19+ph*2*np.pi))
            g=np.minimum(safe,retention-threshold)
            g=np.minimum(g,np.where(visible,1.,-1.))
            return g,['saved-F2-global-and-local-reserves','source-depth-visibility','inherited-mist-threshold']
        raw['source_arc_mm']=[0.,LineString(raw['xy_mm']).length]
        parts,decision=clip_source(raw,gate,minimum_mm=config['minimum_length_mm'],step_mm=.2)
        for r in parts:
            r['derived_parent_id']=record['id'];r['mist_treatment']=treatment
            r['mean_retention']=float(np.mean(ret));r['source_stroke_id']=record['id']
            # Arc intervals remain relative to the original pre-retreat source.
            offset=raw.get('parent_interval_mm',[0,0])[0]
            r['source_arc_mm']=[v+offset for v in r['source_arc_mm']]
            r['source_forward_profile_m']=[record['source_forward_m']]*len(r['xy_mm'])
        decision.update(source_length_mm=length,endpoint_retreat_mm=shortened,
                        mean_retention=float(np.mean(ret)),reason='safe-clipping-and-geometry-dissolution',
                        kept_intervals_mm=[r['source_arc_mm'] for r in parts],
                        removed_mm=length-sum(LineString(r['xy_mm']).length for r in parts))
        ledger.append(decision);result.extend(parts)
    return result,ledger


def color_support(ink,evidence,config,palette_weights):
    """Same foliage carriers, existing palette slots, and depth/visibility logic.

    No terrain A/C vectors are moved. Color is a separately gated directional
    support with a bounded normal offset, not a flat canopy fill or new palette.
    """
    slots=list(palette_weights);cdf=np.cumsum(list(palette_weights.values()),dtype=float);cdf/=cdf[-1]
    result=[];ledger=[]
    for parent in ink:
        if parent['grammar_part']!='directional-foliage':continue
        if phase(parent['unit_id']+'/color',config['seed'])>.76:continue
        r=deepcopy(parent);p=np.asarray(r['xy_mm'],float);t=p[-1]-p[0];t/=max(np.linalg.norm(t),1e-9)
        normal=np.array([-t[1],t[0]])
        r['xy_mm']=(p+normal*.22).tolist()
        r.update(id=parent['id']+'/color',source_stroke_id=parent['id']+'/color',layer='vegetation-color',
                 palette_slot=slots[min(len(slots)-1,int(np.searchsorted(cdf,phase(parent['unit_id']+'/slot',config['seed']))) )],
                 ink_parent_id=parent['id'],material_channel='derived-vegetation-color',
                 width_mm=.65,preview_opacity=.28,color_kind='vegetation',
                 geometry_basis='Same inherited directional foliage; normal offset 0.22 mm',
                 calibrated_dilution=False)
        r['source_arc_mm']=[0.,LineString(r['xy_mm']).length]
        # Geometry already passed occurrence once; do not square its mist
        # probability. Recheck only the displaced footprint/visibility.
        def gate(xy,arc,record):
            ret,vis=root_visibility(evidence,record,xy)
            safe=sample(evidence.protected_clearance,xy,order=0)-(config['footprint_mm']/2+1.4)
            return np.minimum.reduce([safe,ret-.08,np.where(vis,1.,-1.)]),['same-vegetation-mist-and-depth','offset-footprint']
        parts,decision=clip_source(r,gate,minimum_mm=config['minimum_length_mm'],step_mm=.2)
        for s in parts:
            s['source_forward_profile_m']=[r['source_forward_m']]*len(s['xy_mm'])
            s['width_profile_mm']=[.65]*len(s['xy_mm'])
            s['opacity_profile']=[.28]*len(s['xy_mm'])
            s['physical_plotting_validated']=False
        result.extend(parts);ledger.append(decision)
    return result,ledger


def bounds_filter(records,bounds):
    x0,y0,x1,y1=bounds
    return [r for r in records if LineString(r['xy_mm']).intersects(Polygon([(x0,y0),(x1,y0),(x1,y1),(x0,y1)]))]


def metrics(records,crop,scaffold,evidence,raw=None):
    rows=bounds_filter(records,crop['bounds_mm']);lengths=[LineString(r['xy_mm']).length for r in rows]
    # Length density is computed from clipped paths, not full paths merely
    # touching the crop. Dense/open domains are common to all candidates.
    x0,y0,x1,y1=crop['bounds_mm'];region=Polygon([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
    dense=scaffold['density']>=.70;open_mask=(scaffold['density']>=.10)&(scaffold['density']<.35)
    eligible=scaffold['eligible'];values={'dense':0.,'open':0.};mist_bins=[0,.08,.2,.35,.6,1.01]
    mist_length=np.zeros(5);d_length=0.
    allpoints=[]
    for r in rows:
        line=LineString(r['xy_mm']);d_length+=line.intersection(region).length
        p=resample(r['xy_mm'],.20);seg=np.diff(p,axis=0);mid=(p[:-1]+p[1:])/2;l=np.linalg.norm(seg,axis=1)
        xx=(mid[:,0]-x0).astype(int);yy=(mid[:,1]-y0).astype(int)
        valid=(xx>=0)&(xx<x1-x0)&(yy>=0)&(yy<y1-y0)
        xx=xx[valid];yy=yy[valid];l=l[valid];mid=mid[valid]
        values['dense']+=float(l[(dense&eligible)[yy,xx]].sum());values['open']+=float(l[(open_mask&eligible)[yy,xx]].sum())
        ret=sample(evidence.retention,mid)
        for j,(a,b) in enumerate(zip(mist_bins[:-1],mist_bins[1:])):mist_length[j]+=l[(ret>=a)&(ret<b)].sum()
        allpoints.extend(p)
    areas={k:int(((dense if k=='dense' else open_mask)&eligible).sum()) for k in values}
    densities={k:values[k]/max(areas[k],1) for k in values}
    arr=np.asarray(allpoints)
    extent=(arr.max(axis=0)-arr.min(axis=0)).tolist() if len(arr) else [0,0]
    result=dict(paths=len(rows),visible_groups=len(set(r.get('group_id',r.get('owner_id')) for r in rows)),
        constituent_roots=len(set(r.get('owner_id') for r in rows)),units=len(set(r.get('unit_id',r['id']) for r in rows)),
        path_length_mm=d_length,eligible_area_mm2=int(eligible.sum()),
        length_density_mm_per_mm2=d_length/max(int(eligible.sum()),1),
        centerline_extent_mm=extent,stroke_length_mm=dict(min=min(lengths,default=None),median=float(np.median(lengths)) if lengths else None,max=max(lengths,default=None)),
        common_dense_open_area_mm2=areas,common_dense_open_length_density=densities,
        dense_open_contrast=densities['dense']/densities['open'] if densities['open']>0 else None,
        terrain_retention_bin_edges=mist_bins,terrain_retention_bin_length_mm=mist_length.tolist(),
        physical_plotting_validated=False)
    if raw is not None:
        kept=sum(LineString(r['xy_mm']).length for r in records);total=sum(LineString(r['xy_mm']).length for r in raw)
        result.update(raw_paths=len(raw),raw_length_mm=total,removed_length_mm=total-kept,removed_length_fraction=1-kept/max(total,1e-9))
    return result
