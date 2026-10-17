"""Keep geometric interaction separate from review-only material intent."""
from copy import deepcopy
import math
import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import unary_union,substring
from datascape.ground.grammar import path_record
from datascape.vegetation.tree_occlusion_proof import line_parts

COLORS={'A':'#718f9b','C':'#3985a4','rock':'#90563e','soil':'#a48b3d','support':'#a66c9a','tree':'#3b7155','C-in-rock':'#ae5655','C-in-soil':'#ad9a41'}

def family(p):
    if p.get('source_family'):return p['source_family']
    part=p.get('grammar_part','')
    if part=='C-like':return 'C'
    if part=='A-like':return 'A'
    if 'support' in part or 'protected' in part:return 'support'
    return {'rock-ink':'rock','soil-ink':'soil','tree-ink':'tree','terrain-ink':'A'}.get(p.get('layer'),'A')

def tag(records):
    result=deepcopy(records)
    for p in result:
        f=family(p);p['source_family']=f
        p['material_intent']='color-oriented C; final material deferred' if f=='C' else 'structural ink review'
    return result

def appearance(p,mode='ink'):
    f=family(p)
    if mode=='ink':return None if f.startswith('C') else '#000'
    if mode=='color-ready':return '#3d849f' if f=='C' else '#000'
    if mode=='C-only':return COLORS.get(f) if f.startswith('C') else None
    return COLORS.get(f,'#333')

def angle_audit(records):
    result={}
    for f in sorted({family(p) for p in records}):
        selected=[p for p in records if family(p)==f];length=0.;steep=0.;angles=[]
        for p in selected:
            d=np.diff(np.asarray(p['xy_mm']),axis=0);ll=np.linalg.norm(d,axis=1);aa=np.degrees(np.arctan2(np.abs(d[:,1]),np.abs(d[:,0])))
            length+=float(ll.sum());steep+=float(ll[aa>=50].sum());angles.extend(aa[ll>1e-6].tolist())
        result[f]=dict(paths=len(selected),length_mm=length,steep_length_mm=steep,steep_fraction=steep/max(length,1e-9),minimum_angle_deg=min(angles,default=0),maximum_angle_deg=max(angles,default=0))
    return result

def c_intersections(c_sources,masses,ground):
    output=[];regions=[('C-in-rock',unary_union([m.surface.support for m in masses])),('C-in-soil',ground.surface.support)]
    for p in c_sources:
        source=LineString(p['xy_mm'])
        for role,region in regions:
            for j,g in enumerate(line_parts(source.intersection(region))):
                if g.length<.15:continue
                q=path_record('diagnostic/'+p['id']+'/'+role+'/'+str(j),g.coords,p['owner_id'],'raw-C-intersection',.75,p['forward_depth'],'diagnostic')
                q.update(source_family=role,diagnostic_source_id=p['id'],diagnostic_source_arc_mm=sorted([source.project(Point(g.coords[0])),source.project(Point(g.coords[-1]))]),plot=False)
                output.append(q)
    return output

def ground_gradient(ground,masses,protected_records=(),reach_mm=7.5):
    """Refine ink only; v04 ownership, patch members and pigment stay identical."""
    g=deepcopy(ground);contacts=[];contact_ids=[]
    for m in masses:
        x0,y0,x1,y1=m.surface.support.bounds;anchor=m.surface.info.get('anchor_mm',[(x0+x1)/2,y1]);slope=m.surface.info.get('slope',0.)
        line=LineString([(x0,anchor[1]+slope*(x0-anchor[0])),(x1,anchor[1]+slope*(x1-anchor[0]))]).intersection(m.surface.support.buffer(.15))
        if not line.is_empty:contacts.append(line);contact_ids.append(m.surface.identity+'/declared-contact')
    contacts.extend(LineString(p['xy_mm']) for p in protected_records);contact_ids.extend(p['id'] for p in protected_records)
    influence=unary_union(contacts);paths=[];events=[]
    for p in ground.surface.paths:
        line=LineString(p['xy_mm'])
        row=int(p['id'].split('flow-')[1].split('/')[0]) if 'flow-' in p['id'] else len(events)
        # A smooth row-family threshold gives unequal reach into the same surface,
        # not periodic splitting or independent random marks.
        threshold=.28+.34*(.5+.5*math.cos(row*.67+.4));radius=-reach_mm*math.log(threshold)
        ink=line.intersection(influence.buffer(radius)).difference(ground.white_reserve)
        kept=[]
        for j,part in enumerate(line_parts(ink)):
            if part.length<2.8:continue
            a=line.project(Point(part.coords[0]));b=line.project(Point(part.coords[-1]));lo,hi=sorted([a,b])
            q=path_record(p['id']+f'/contact-gradient-{j}',part.coords,p['owner_id'],'contact-ground-gradient',p['width_mm'],p['forward_depth'],p['layer'])
            q.update(soil_parent_source_id=p['id'],soil_parent_arc_mm=[lo,hi],surface_source_id=p.get('surface_source_id'),patch_members=p.get('patch_members',[]),semantic_opaque=False)
            paths.append(q);kept.append([lo,hi])
        events.append(dict(source_id=p['id'],radius_mm=radius,kept_arc_mm=kept,original_length_mm=line.length))
    g.surface.paths=paths;g.surface.info['ink_refinement']='contact-related reach gradient; ownership unchanged'
    return g,dict(reach_mm=reach_mm,contact_sources=contact_ids,original_paths=len(ground.surface.paths),refined_paths=len(paths),events=events),influence
