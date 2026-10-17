"""Bounded derivatives of the v02 grammar, not additional rock species."""
from copy import deepcopy
import hashlib
import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import substring,unary_union
from datascape.ground.grammar import path_record
from datascape.ground.surface_ground_v02 import localized_ground
from datascape.vegetation.tree_occlusion_proof import line_parts

MODES=('control','interruption','overlap','combined')
FOOTPRINT_MM=.6

def footprint(records):
    return unary_union([LineString(p['xy_mm']).buffer(p.get('assumed_footprint_mm',max(.6,p['width_mm']))/2) for p in records])

def rhythm(records,mode='combined',strength=1.,structural_gaps=()):
    """Keep original geometry lineage; only eligible long internal bands change.

    Omission is an authored shoulder opening, never re-labelled as a fault.
    Existing fracture-mouth and burial clipping remain inherited from v02.
    Visibility clipping is exclusively the downstream interaction planner.
    """
    if mode not in MODES or not 0<=strength<=1:raise ValueError('invalid rhythm controls')
    out=[];events=[];overlaps=[]
    for p in records:
        line=LineString(p['xy_mm']);n=int(hashlib.sha256(p['id'].encode()).hexdigest()[:8],16)
        eligible=p['grammar_part']=='bedding-band' and line.length>20
        pieces=[(0.,line.length)]
        if eligible and mode in ('interruption','combined') and n%4==1 and strength:
            # Release only ends already incident on an inherited fracture mouth.
            ends=[Point(line.coords[0]),Point(line.coords[-1])]
            incident=[any(g.distance(e)<.8 for g in structural_gaps) for e in ends]
            trim=(.8+.35*(n%3))*strength
            a=trim if incident[0] else 0.;b=line.length-trim if incident[1] else line.length
            if a or b<line.length:
                pieces=[(a,b)]
                events.append(dict(parent=p['id'],kept_arc_mm=[a,b],excluded_arc_mm=([[0.,a]] if a else [])+([[b,line.length]] if b<line.length else []),reason='inherited-fracture-mouth-release',structural_fracture=True))
        if eligible and mode in ('interruption','combined') and n%5 in (0,1):
            # A shared upper/right shoulder zone defines the opening, not regular dashes.
            mid=line.interpolate(.5,normalized=True)
            target=Point(46 if mid.x<70 else (81 if mid.x<112 else 130),mid.y)
            s=line.project(target);gap=(3.0+(n%3)*1.1)*strength
            if 5<s<line.length-5:
                lo,hi=pieces[0]
                pieces=[(lo,max(lo,s-gap/2)),(min(hi,s+gap/2),hi)]
                events.append(dict(parent=p['id'],excluded_arc_mm=[[s-gap/2,s+gap/2]],reason='pictorial-shoulder-omission',structural_fracture=False))
        for j,(a,b) in enumerate(pieces):
            if b-a<2.8:continue
            if a==0 and b==line.length:out.append(deepcopy(p));continue
            q=deepcopy(p);q.update(path_record(p['id']+f'/rhythm-{j}',substring(line,a,b).coords,p['owner_id'],p['grammar_part'],p['width_mm'],p['forward_depth'],p['layer']))
            q.update(rhythm_parent_id=p['id'],rhythm_parent_arc_mm=[a,b]);out.append(q)
        if eligible and mode in ('overlap','combined') and n%7==2 and strength:
            a=line.length*(.17+.06*(n%3));b=min(line.length-3,a+5.5+(n%4))
            if b-a<2.8:continue
            seg=substring(line,a,b);xy=np.array(seg.coords);t=np.linspace(0,1,len(xy))
            d=np.gradient(xy,axis=0);norm=np.linalg.norm(d,axis=1);normal=np.c_[-d[:,1],d[:,0]]/norm[:,None]
            xy+=normal*(.24+.78*t+.12*np.sin(np.pi*t))[:,None]*strength
            q=deepcopy(p);q.update(path_record(p['id']+'/offset',xy,p['owner_id'],'selected-offset',p['width_mm'],p['forward_depth'],p['layer']))
            q.update(rhythm_parent_id=p['id'],rhythm_parent_arc_mm=[a,b])
            occupied=footprint(out+records);candidate=footprint([q]);fraction=candidate.intersection(occupied).area/candidate.area
            # Reject rather than hide excessive footprint duplication.
            accepted=fraction<=.35
            overlaps.append(dict(parent=p['id'],added_coverage_fraction=fraction,accepted=accepted,limit=.35))
            if accepted:out.append(q)
    return out,dict(mode=mode,strength=strength,omissions=events,offsets=overlaps,
        inherited_gaps='v02 structural fracture / burial; unchanged',visibility='downstream planner only',footprint_mm=.6)

def context_ground(identity,host,patches,context='open',corridor=None):
    """One surface-patch grammar with context-dependent directional emphasis.

    v02 ownership and white regions remain, but uneven runs dissolve into
    supporting A flow and selected C-like oblique transitions. No perimeter ink.
    """
    if context not in ('rock','tree','open','mixed'):raise ValueError('unknown context')
    g=localized_ground(identity,host,patches,corridor=corridor)
    source=np.asarray(host['xy_mm']);paths=[]
    for p in g.surface.paths:
        q=deepcopy(p);xy=np.asarray(p['xy_mm']);j=int(p['patch_id'].rsplit('-',1)[1]);cx,cy,rx,ry=patches[j]
        z=(xy[:,1].mean()-cy)/ry
        # Sparse upper dissolution, concentrated contact shoulders; no random noise.
        run=int(p['id'].split('/run-')[1].split('/')[0])
        if run in (0,8) or (context=='open' and run==2):continue
        fraction=.62 if run in (1,6) else (.82 if run in (3,5) else 1.)
        line=LineString(xy);a=(1-fraction)*line.length*(.25 if run%2 else .75)
        line=substring(line,a,a+fraction*line.length);xy=np.asarray(line.coords)
        emphasis={'rock':.18,'tree':-.22,'open':.32,'mixed':.14}[context]
        if run in (1,6):xy[:,1]+=emphasis*(xy[:,0]-cx)
        # Reclip modified flow to ownership and white reserve, then corridor.
        geom=LineString(xy).intersection(g.surface.support).difference(g.white_reserve)
        if corridor:geom=geom.difference(corridor.geometry.buffer(.3))
        for k,part in enumerate(line_parts(geom)):
            if part.length<2.8:continue
            r=path_record(p['id']+f'/context-{k}',part.coords,p['owner_id'],'context-ground-flow',.6,4.5,'soil-ink')
            r.update(surface_source_id=host['id'],patch_id=p['patch_id'],context=context,semantic_opaque=False)
            paths.append(r)
    g.surface.paths=paths;g.surface.info.update(version='v03',context=context,perimeter_ink=False)
    return g
