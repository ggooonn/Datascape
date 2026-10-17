"""Feature-linked details and physical scale policy on the unchanged rock engine."""
from copy import deepcopy
from dataclasses import dataclass,asdict
import math
import numpy as np
from shapely.geometry import LineString,Point,Polygon,GeometryCollection
from shapely.ops import unary_union,substring,nearest_points
from datascape.ground.grammar import path_record
from datascape.ground.structure_v02 import scaffold,structural_mass,StructuralField
from datascape.ground.refinement_v03 import rhythm,footprint
from datascape.vegetation.tree_occlusion_proof import line_parts

@dataclass(frozen=True)
class PhysicalDetailPolicy:
    minimal_width_mm:float=26.
    secondary_min_width_mm:float=50.
    secondary_min_height_mm:float=24.
    two_features_width_mm:float=150.
    micro_min_width_mm:float=140.
    micro_min_height_mm:float=45.
    small_structure_max_mm:float=6.5

@dataclass(frozen=True)
class FormationControls:
    width_mm:float=200.
    height_mm:float=70.
    major_count:int=3
    dominance:float=.72
    overlap:float=.26
    burial:float=.17
    orientation_deg:float=77.
    local_deviation_deg:float=5.
    seed:int=20261017
    def validate(self):
        if not 65<=self.width_mm<=330 or not 25<=self.height_mm<=130 or self.major_count not in (2,3,4):raise ValueError('local B composition bounds')
        if not .6<=self.dominance<=.8 or not .1<=self.overlap<=.4 or not 0<=self.burial<=.35 or abs(self.local_deviation_deg)>10:raise ValueError('bounded composition controls')

def base_mass(identity,width,height,form='angular',regime='layered',anchor=(70,95),depth=3.,seed=20261017,field_id=None,rotation=0.,burial=.18):
    spacing=4.3 if width<50 else 6.5 if width<110 else 10. if width<200 else 14.
    if regime=='jointed':spacing*=1.13
    f=StructuralField(field_id or identity+'/field',regime,-12 if regime=='layered' else 77,spacing,(0,10),.5,1.2,seed,rotation)
    s=scaffold(identity,anchor=anchor,width=width,height=height,form=form,seed=seed,burial=burial,depth=depth)
    s.opaque=True;m=structural_mass(s,f)
    m.surface.paths,event=rhythm(m.surface.paths,'interruption',structural_gaps=[g['geometry'] for g in m.gaps if g['reason'].startswith('fracture')])
    m.surface.info['rhythm']=event
    return m

def formation(identity='v05/B',controls=FormationControls()):
    c=controls;c.validate();w,h=c.width_mm,c.height_mm;field=identity+'/parent-field';foot=h+20
    # Count, overlap, dominance and exposure are independent composition controls.
    rear_x=.78+(c.overlap-.26)*-.25;front_x=.70+(c.overlap-.26)*-.55
    recipe=[('parent',(.42*w,foot),w*c.dominance,h,'bedrock','jointed',4.,0.,c.burial)]
    if c.major_count>=3:recipe.append(('rear',(rear_x*w,foot-h*.19),w*.40,h*.65,'bedrock','jointed',4.7,c.local_deviation_deg,min(.35,c.burial+.03)))
    if c.major_count==4:recipe.append(('back-shoulder',(.23*w,foot-h*.10),w*.29,h*.48,'angular','jointed',4.4,-c.local_deviation_deg*.6,min(.35,c.burial+.06)))
    recipe.append(('front',(front_x*w,foot+h*.10),w*.48,h*.62,'angular','layered',2.8,-c.local_deviation_deg,min(.35,c.burial+.06)))
    masses=[]
    for name,a,ww,hh,form,regime,rank,rot,bury in recipe:
        m=base_mass(identity+'/'+name,ww,hh,form,regime,a,rank,c.seed,field,rot,bury)
        m.parent_id=identity+'/parent';m.surface.info['composition_controls']=c.__dict__
        for p in m.surface.paths:p['parent_mass_id']=m.parent_id
        masses.append(m)
    return masses

def scale_base(mass,policy=PhysicalDetailPolicy()):
    """Simplify before detail; physical marks are regenerated at each requested size."""
    m=deepcopy(mass);w=m.surface.support.bounds[2]-m.surface.support.bounds[0]
    if w>=policy.secondary_min_width_mm:return m
    contours=[p for p in m.surface.paths if p['grammar_part']=='ink-contour']
    interior=[p for p in m.surface.paths if p['grammar_part']!='ink-contour']
    limit=1 if w<policy.minimal_width_mm else 3
    # Retain distinct long directions, not every small copy of the full field.
    chosen=sorted(interior,key=lambda p:(p['grammar_part'] not in ('small-structure','partial-spall-seam'),-LineString(p['xy_mm']).length,p['id']))[:limit]
    if w<policy.minimal_width_mm:
        shortened=[]
        for p in chosen:
            line=LineString(p['xy_mm']);length=min(policy.small_structure_max_mm,line.length)
            g=substring(line,(line.length-length)/2,(line.length+length)/2)
            q=deepcopy(p);q.update(path_record(p['id']+'/physical-small',g.coords,p['owner_id'],p['grammar_part'],p['width_mm'],p['forward_depth'],p['layer']))
            q['scale_parent_source_id']=p['id'];shortened.append(q)
        chosen=shortened
    m.surface.paths=contours+chosen;m.surface.info['scale_policy']='minimal contour + one crease' if w<policy.minimal_width_mm else 'contour + at most three structural runs'
    return m

def _carriers(m):
    paths=m.surface.paths
    if m.field.regime=='jointed':
        prefer=[p for p in paths if p['grammar_part']=='cross-fracture']
    elif m.field.regime=='layered':prefer=[p for p in paths if p['grammar_part']=='secondary-fracture']
    else:prefer=[p for p in paths if p['grammar_part']=='partial-spall-seam']
    return sorted(prefer,key=lambda p:(-LineString(p['xy_mm']).length,p['id']))

def feature_detail(mass,enabled=True,physical_policy=PhysicalDetailPolicy()):
    """A decaying one-sided structural shoulder, not a clipped hatch window.

    Marks are attached to existing fracture/spall carriers. Their fan distances,
    spacing, physical lengths and sparse terminal micro accents are bounded.
    """
    m=scale_base(mass,physical_policy);base=deepcopy(m.surface.paths);b=m.surface.support.bounds;w,h=b[2]-b[0],b[3]-b[1]
    cuts=unary_union([g['geometry'] for g in m.gaps]);occupied=footprint(base)
    carriers=_carriers(m);features=[];events=[];added=[];zones=[]
    count=0 if w<physical_policy.secondary_min_width_mm or h<physical_policy.secondary_min_height_mm else 1 if w<physical_policy.two_features_width_mm else 2
    if not enabled:count=0
    for fi,p in enumerate(carriers[:count]):
        line=LineString(p['xy_mm']);center=line.interpolate(.45 if fi%2==0 else .62,normalized=True)
        s=line.project(center);half=min(line.length*.36,14 if w<110 else 22)
        carrier=substring(line,max(0,s-half),min(line.length,s+half))
        if carrier.length<5:continue
        mid=carrier.interpolate(.5,normalized=True)
        d=np.asarray(carrier.coords[-1])-np.asarray(carrier.coords[0]);d=d/np.linalg.norm(d)
        # Jointed: secondary joints enter a cross-fracture. Layered: short beds
        # terminate beside a cross-joint. Rounded: marks follow the curved seam.
        tangent=m.field.tangent if m.field.regime!='rounded' else d
        side=np.array([-d[1],d[0]])*(1 if fi%2==0 else -1)
        if np.dot(tangent,side)<0:tangent=-tangent
        zone=carrier.buffer(12 if w>=110 else 8,cap_style=2).intersection(m.surface.support).difference(cuts)
        zones.append(zone);features.append(dict(source_id=p['id'],kind=p['grammar_part'],carrier=carrier,zone=zone))
        junctions=[]
        expected=('primary-joint',) if m.field.regime=='jointed' else ('bedding-band',) if m.field.regime=='layered' else ('curved-surface',)
        for other in base:
            if other['grammar_part'] not in expected:continue
            other_line=LineString(other['xy_mm']);hit=carrier.intersection(other_line)
            points=[hit] if hit.geom_type=='Point' else [g for g in getattr(hit,'geoms',[]) if g.geom_type=='Point']
            if not points and m.field.regime=='layered':
                points=[Point(xy) for xy in (other_line.coords[0],other_line.coords[-1]) if carrier.distance(Point(xy))<2.1]
            for point in points:
                t=carrier.project(point)
                if 1<t<carrier.length-2:junctions.append((t,other['id']))
        unique=[]
        for item in sorted(junctions):
            if not unique or item[0]-unique[-1][0]>3.5:unique.append(item)
        if len(unique)>3:unique=[unique[0],unique[len(unique)//2],unique[-1]]
        if not unique:unique=[(carrier.length*.34,p['id'])]
        features[-1]['junction_sources']=[q[1] for q in unique]
        for episode,(position,junction_id) in enumerate(unique):
            # Small unequal bundles respond to real carrier intersections or
            # nearby bedding terminations, with open intervals between events.
            offsets=(1.15,3.1,5.8) if episode==0 else (1.35,4.0) if episode==1 else (1.65,)
            for i,offset in enumerate(offsets):
                t=min(carrier.length-.8,position+offset)
                anchor=np.asarray(carrier.interpolate(t).coords[0])
                fade=max(.25,1-episode*.24-i*.22)
                length=(4.0+(8.0 if w>=110 else 4.5)*fade)
                start=anchor+tangent*.95
                normal=np.array([-tangent[1],tangent[0]])
                xy=np.array([start,start+tangent*length*.48+normal*.18,start+tangent*length+normal*(.55+.3*fade)])
                candidate=LineString(xy).intersection(m.surface.support.buffer(-.9)).difference(cuts)
                for j,g in enumerate(line_parts(candidate)):
                    if g.length<2.8:continue
                    q=path_record(m.surface.identity+f'/feature-{fi}/episode-{episode}/run-{i}/{j}',g.coords,m.surface.identity,'feature-shoulder',.55,m.surface.depth,'rock-ink')
                    q.update(feature_source_id=p['id'],junction_source_id=junction_id,feature_kind=p['grammar_part'],detail_level='meso',generator_seed=m.field.seed,structural_field_id=m.field.identity,assumed_footprint_mm=.6)
                    shape=g.buffer(.3);overlap=shape.intersection(occupied).area/shape.area
                    inside=g.intersection(zone).length/max(g.length,1e-9)
                    accept=overlap<=.20 and inside>=.65
                    events.append(dict(id=q['id'],carrier=p['id'],junction=junction_id,length_mm=g.length,overlap=overlap,accepted=accept))
                    if accept:added.append(q);occupied=occupied.union(shape)
        # At a large exposed seam end, at most one short offset, physically bounded.
        if w>=physical_policy.micro_min_width_mm and h>=physical_policy.micro_min_height_mm:
            anchor=np.asarray(carrier.interpolate(.12,normalized=True).coords[0])+tangent*2.3+d*1.1
            xy=np.array([anchor,anchor+tangent*4.2+normal*.45])
            for j,g in enumerate(line_parts(LineString(xy).intersection(m.surface.support.buffer(-1)).difference(cuts))):
                if g.length<2.8:continue
                shape=g.buffer(.3);overlap=shape.intersection(occupied).area/shape.area
                ok=overlap<=.20;events.append(dict(id=m.surface.identity+f'/micro-{fi}',carrier=p['id'],length_mm=g.length,overlap=overlap,accepted=ok))
                if ok:
                    q=path_record(m.surface.identity+f'/feature-{fi}/micro-{j}',g.coords,m.surface.identity,'feature-terminal',.55,m.surface.depth,'rock-ink');q.update(feature_source_id=p['id'],feature_kind=p['grammar_part'],detail_level='micro',assumed_footprint_mm=.6)
                    added.append(q);occupied=occupied.union(shape)
    m.surface.paths=base+added
    support=unary_union(zones) if zones else GeometryCollection()
    # Derive the sample from actual carrier neighborhoods. The open area is the
    # remaining inset body, not a preselected rectangle or ellipse.
    open_area=m.surface.support.buffer(-2).difference(support.buffer(3)).difference(m.white_reserve)
    def dens(g,records):return sum(LineString(p['xy_mm']).intersection(g).length for p in records)/g.area if g.area else 0.
    a=dict(body_width_mm=w,body_height_mm=h,base_paths=len(base),added_paths=len(added),feature_count=len(features),events=events,
           detail_area_mm2=support.area,detail_area_fraction=support.area/m.surface.support.area,
           detail_density_mm_per_mm2=dens(support,m.surface.paths),open_density_mm_per_mm2=dens(open_area,m.surface.paths),
           physical_policy=asdict(physical_policy),
           feature_sources=[dict(source_id=f['source_id'],kind=f['kind']) for f in features])
    return m,a,dict(features=features,dense=support,open=open_area)
