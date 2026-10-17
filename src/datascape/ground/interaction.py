"""Limited shared-contract consumer for simple synthetic source polylines.

All decisions use original source arcs and a union of visible masks. Unknown
rank does not imply a number. This is not geographic reciprocal scene masking.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import numpy as np
from shapely.geometry import LineString, GeometryCollection, Point
from shapely.ops import unary_union, substring
from datascape.vegetation.tree_occlusion_proof import line_parts


@dataclass(frozen=True)
class Region:
    identity: str
    owner_id: str
    geometry: object
    depth: float | None
    role: str = 'opaque-body'
    boundary_basis: str = 'body-boundary'
    already_buffered_receiver_mm: float = 0.
    boundary_ink_width_mm: float = .6


@dataclass(frozen=True)
class Corridor:
    identity: str
    geometry: object
    evidence: str = 'artist-designed synthetic opening; no water/path claim'
    uncertainty: str = 'pictorial intent only; no geographic correspondence'
    allowed_edge_ids: tuple = ()


def union_or_empty(parts):
    return unary_union(parts) if parts else GeometryCollection()


def visible_regions(regions):
    """Opaque bodies only; visible rear support excludes nearer solid bodies.

    This planar constant-rank fixture resolver cannot model varying crown depth.
    Unresolved depth bodies do not participate in visibility certification.
    """
    out=[]
    for r in sorted(regions,key=lambda x:x.identity):
        front=[s.geometry for s in regions if r.depth is not None and s.depth is not None
               and s.depth<r.depth and s.owner_id!=r.owner_id and s.role=='opaque-body']
        g=r.geometry.difference(union_or_empty(front))
        out.append(Region(r.identity,r.owner_id,g,r.depth,r.role,r.boundary_basis,
                          r.already_buffered_receiver_mm,r.boundary_ink_width_mm))
    return out


def _fragment(record, line, part, start, end, reason):
    rec=deepcopy(record)
    xy=np.asarray(part.coords)
    # The source's direction, original ID and original arc coordinates survive.
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(record['xy_mm'],axis=0),axis=1))]
    q=np.array([line.project(Point(p)) for p in xy])
    if q[0]>q[-1]: xy=xy[::-1];q=q[::-1]
    for key in ('width_profile_mm','opacity_profile'):
        if key in rec:
            if len(rec[key])!=len(arc): raise ValueError('misaligned source profile')
            rec[key]=np.interp(q,arc,record[key]).tolist()
    expr=rec.get('expression',{})
    if 'intensity_samples' in expr:
        if len(expr['intensity_samples'])!=len(arc): raise ValueError('misaligned intensity')
        expr['intensity_samples']=np.interp(q,arc,record['expression']['intensity_samples']).tolist()
    source=record.get('source_stroke_id',record['id'])
    parent_range=record.get('source_arc_mm',[0.,line.length])
    # Catalog consumer is one-pass only. Reject recursive clipping instead of
    # silently converting clipped local lengths into original source lengths.
    if abs(parent_range[0])>1e-7 or abs(parent_range[1]-line.length)>1e-5:
        raise ValueError('clip original source paths once')
    signature=hashlib.sha256(f'{source}/{start:.8f}/{end:.8f}'.encode()).hexdigest()[:12]
    rec.update(id=f'{source}/kept-{signature}',source_stroke_id=source,
               source_arc_mm=[start,end],xy_mm=xy.tolist(),decision_revision='local-contract-0.1',
               omission_reasons=reason)
    return rec


def plan(records, regions=(), corridor=None, replacements=None, minimum_mm=2.8,
         edge_mm=.15, protected=None):
    """Return actual vector fragments and interval audit; never raster erasing.

    replacements maps source IDs to original arc intervals; protection is audit
    intent and never an exemption from nearer opaque bodies. Corridors are
    independent pictorial reserves. Input lines must be simple, one-pass paths.
    """
    if minimum_mm<0 or edge_mm<0: raise ValueError('nonnegative assumptions required')
    replacements=replacements or {}; protected=protected or {}
    lookup={r['id']:r for r in records}
    if len(lookup)!=len(records): raise ValueError('duplicate source IDs')
    if set(replacements)-lookup.keys() or set(protected)-lookup.keys():
        raise ValueError('unresolved source references')
    visible=visible_regions(regions)
    result=[]; audit=[];unknown=[]; conflicts=[]; equal_depth=[]
    for rec in sorted(records,key=lambda x:x['id']):
        line=LineString(rec['xy_mm'])
        if not line.is_simple or line.is_ring: raise ValueError('simple open source path required')
        width=rec.get('assumed_footprint_mm',rec['width_mm']);depth=rec.get('forward_depth')
        if not np.isfinite(width) or width<=0: raise ValueError('positive receiving footprint required')
        if depth is not None and not np.isfinite(depth): raise ValueError('finite known depth rank required')
        cuts=[]; reasons=[]
        for r in visible:
            if r.owner_id==rec['owner_id'] or r.geometry.is_empty: continue
            if depth is None or r.depth is None:
                if line.intersects(r.geometry): unknown.append([rec['id'],r.identity])
                continue
            if depth==r.depth:
                if r.role=='opaque-body' and line.intersects(r.geometry):
                    equal_depth.append(dict(source_id=rec['id'],region_id=r.identity,decision='equal rank contact/visibility unresolved; retained'))
                continue
            if depth<r.depth: continue
            # body boundaries include no ink radius. A legacy tree mask already
            # includes the receiving terrain half-width and edge allowance.
            margin=width/2+edge_mm-r.already_buffered_receiver_mm
            if r.boundary_basis == 'body-boundary': margin += r.boundary_ink_width_mm/2
            if margin < -1e-8: raise ValueError('legacy buffer exceeds requested receiving clearance')
            g=r.geometry.buffer(max(0.,margin),quad_segs=12)
            if line.intersects(g): cuts.append(g);reasons.append(r.identity)
        if corridor and rec['id'] not in corridor.allowed_edge_ids:
            g=corridor.geometry.buffer(width/2,quad_segs=12)
            if line.intersects(g):cuts.append(g);reasons.append(corridor.identity)
        for a,b in replacements.get(rec['id'],[]):
            if not 0<=a<b<=line.length+1e-7: raise ValueError('invalid original arc interval')
            cuts.append(substring(line,a,b));reasons.append('surface-replacement')
        cut=union_or_empty(cuts)
        raw=line.difference(cut)
        kept=[]; short=[]
        # Rounding is part of final feasibility; recheck after 0.001 mm output.
        for g in line_parts(raw):
            rounded=LineString(np.round(g.coords,3))
            if rounded.length<minimum_mm:
                short.append((line.project(g.interpolate(0)),line.project(g.interpolate(1,normalized=True)),g.length));continue
            # Retain exact intersection endpoints when rounding would enter a
            # hard exclusion. No reconnection or bridging across gaps.
            if not cut.is_empty and rounded.intersection(cut).length>1e-8: rounded=g
            a=line.project(g.interpolate(0)); b=line.project(g.interpolate(1,normalized=True))
            if a>b:a,b=b,a
            result.append(_fragment(rec,line,rounded,a,b,sorted(reasons)))
            kept.append([a,b])
        removed=line.intersection(cut)
        excluded=[]
        for g in line_parts(removed):
            a=line.project(g.interpolate(0)); b=line.project(g.interpolate(1,normalized=True))
            excluded.append(sorted([a,b]))
        for a,b in protected.get(rec['id'],[]):
            if not 0<=a<b<=line.length+1e-7: raise ValueError('invalid contact protection')
            segment=substring(line,a,b)
            lost=segment.intersection(cut).length
            if lost>1e-7: conflicts.append(dict(source_id=rec['id'],interval_mm=[a,b],
                excluded_mm=lost,decision='depth/reserve wins; protection is not a waiver'))
        kept_length=sum(b-a for a,b in kept)
        audit.append(dict(source_id=rec['id'],source_length_mm=line.length,
                          kept_intervals_mm=sorted(kept),excluded_intervals_mm=sorted(excluded),
                          removed_mm=line.length-kept_length,
                          excluded_mm=removed.length,short_dropped_mm=sum(x[2] for x in short),
                          short_intervals_mm=short,reasons=sorted(reasons)))
    return result,dict(sources=audit,unknown_depth_pairs=unknown,contact_conflicts=conflicts,
        equal_depth_conflicts=equal_depth,
        source_length_mm=sum(x['source_length_mm'] for x in audit),
        removed_mm=sum(x['removed_mm'] for x in audit),
        excluded_mm=sum(x['excluded_mm'] for x in audit),
        short_dropped_mm=sum(x['short_dropped_mm'] for x in audit),
        minimum_final_path_mm=min((LineString(r['xy_mm']).length for r in result),default=None),
        fragments=len(result),assumptions=dict(minimum_mm=minimum_mm,edge_mm=edge_mm,
        measured=False,depth_provider='synthetic-local-rank-v1',geographic_depth_m=None))


def replacement_intervals(records,support):
    result={}
    for r in records:
        line=LineString(r['xy_mm']); intervals=[]
        for part in line_parts(line.intersection(support)):
            a=line.project(part.interpolate(0));b=line.project(part.interpolate(1,normalized=True))
            if abs(a-b)>1e-8: intervals.append(sorted([a,b]))
        if intervals: result[r['id']]=sorted(intervals)
    return result


def duplicate_coverage(a,b):
    """Actual assumed-footprint intersection, not a source-path count proxy."""
    def coverage(records):
        return union_or_empty([LineString(r['xy_mm']).buffer(r.get('assumed_footprint_mm',r['width_mm'])/2,quad_segs=8) for r in records])
    aa,bb=coverage(a),coverage(b)
    return dict(terrain_footprint_mm2=aa.area,added_footprint_mm2=bb.area,
                duplicate_mm2=aa.intersection(bb).area,
                duplicate_fraction_of_added=aa.intersection(bb).area/max(bb.area,1e-9))
