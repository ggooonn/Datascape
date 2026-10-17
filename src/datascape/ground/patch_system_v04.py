"""Surface ownership and relational patch systems, independent of object sizes.

Low-frequency correlated boundaries are nonplotting. One global flow lattice
owns merged/nested supports, so overlapping ownership never doubles the ink.
"""
from dataclasses import dataclass,asdict
import math
import numpy as np
from scipy.interpolate import PchipInterpolator
from shapely.geometry import Polygon,Point,LineString,GeometryCollection,box
from shapely import affinity
from shapely.ops import unary_union,substring
from datascape.ground.grammar import Surface,path_record
from datascape.ground.surface_ground_v02 import GroundStudy
from datascape.vegetation.tree_occlusion_proof import line_parts

@dataclass(frozen=True)
class PatchSpec:
    identity:str
    x_mm:float
    host_offset_mm:float
    area_mm2:float
    aspect_ratio:float=3.2
    irregularity:float=.16
    rotation_deg:float=0.
    density_tier:int=0
    family_phase:float=.4
    contact:str='declared ground; no automatic object attachment'

@dataclass(frozen=True)
class PatchControls:
    spacing_mm:float=3.3
    directional_coherence:float=.9
    edge_dissolution:float=.32
    pigment_fraction:float=.35
    pigment_enabled:bool=True
    relation:str='separate'
    merge_gap_mm:float=0.
    minimum_separation_mm:float=0.
    def validate(self):
        if not 1.5<=self.spacing_mm<=12 or not 0<=self.directional_coherence<=1 or not 0<=self.edge_dissolution<=.8 or not 0<=self.pigment_fraction<=.7:raise ValueError('bounded physical patch controls')
        if not 0<=self.merge_gap_mm<=6 or not 0<=self.minimum_separation_mm<=8 or (self.merge_gap_mm and self.minimum_separation_mm):raise ValueError('choose bridging or minimum separation')
        if self.relation not in ('none','separate','satellites','connected','shared','discontinuous'):raise ValueError('patch relationship preset')


def host_function(record):
    xy=np.asarray(record['xy_mm']);
    if np.any(np.diff(xy[:,0])<=0):raise ValueError('monotone host required')
    return PchipInterpolator(xy[:,0],xy[:,1],extrapolate=True)

def patch_shape(spec,host):
    if spec.area_mm2<=0 or not 1<=spec.aspect_ratio<=8 or not 0<=spec.irregularity<=.35 or abs(spec.rotation_deg)>25:raise ValueError('invalid patch geometry')
    if spec.density_tier not in (0,1):raise ValueError('density tier')
    t=np.linspace(0,2*np.pi,161)
    r=1+spec.irregularity*(.60*np.sin(3*t+spec.family_phase)+.32*np.cos(2*t-spec.family_phase))
    rx=math.sqrt(spec.area_mm2*spec.aspect_ratio/np.pi);ry=math.sqrt(spec.area_mm2/spec.aspect_ratio/np.pi)
    local=np.c_[rx*np.cos(t)*r,ry*np.sin(t)*r]
    scale=math.sqrt(spec.area_mm2/Polygon(local).area);local*=scale
    a=math.radians(spec.rotation_deg);rotation=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    local=local@rotation.T;xx=spec.x_mm+local[:,0]
    yy=host(xx)+spec.host_offset_mm+local[:,1]
    return Polygon(np.c_[xx,yy]).buffer(0)

def patch_system(identity,host_record,specs,controls=PatchControls(),corridor=None,whitespace=None,depth=4.5,cross_flow_record=None):
    c=controls;c.validate();host=host_function(host_record)
    # Geometry construction does not read internal density, edge or pigment controls.
    shapes=[patch_shape(s,host) for s in specs]
    reserve=whitespace if whitespace is not None else GeometryCollection()
    if corridor is not None:reserve=reserve.union(corridor.geometry)
    effective=[g.difference(reserve) for g in shapes]
    for i,g in enumerate(effective):
        for h in effective[i+1:]:
            if c.minimum_separation_mm and g.distance(h)<c.minimum_separation_mm-1e-6:raise ValueError('patch placement violates declared minimum separation')
    raw_union=unary_union(effective) if effective else GeometryCollection()
    support=raw_union.buffer(c.merge_gap_mm/2).buffer(-c.merge_gap_mm/2).difference(reserve) if c.merge_gap_mm and not raw_union.is_empty else raw_union
    connections=support.difference(raw_union)
    paths=[];pigment=GeometryCollection()
    cross_slope=0.
    if cross_flow_record is not None:
        xy=np.asarray(cross_flow_record['xy_mm']);delta=xy[-1]-xy[0]
        if abs(delta[0])<1e-6:raise ValueError('finite synthetic C tangent required')
        # One shared blend of A-host and supplied C tangent, not per-run rotations.
        cross_slope=math.tan((1-c.directional_coherence)*math.atan2(delta[1],delta[0]))
    if specs and not support.is_empty:
        x0,y0,x1,y1=support.bounds
        # Global source-relative q lattice: never one independent hatch stack per blob.
        yy=np.linspace(x0,x1,120);h=np.asarray(host(yy));qlo=y0-float(h.max())-abs(cross_slope)*(x1-x0)/2-2;qhi=y1-float(h.min())+abs(cross_slope)*(x1-x0)/2+2
        fine=(c.spacing_mm/2 if any(s.density_tier for s in specs) else c.spacing_mm)*math.sqrt(1+cross_slope**2)
        for row in range(math.floor(qlo/fine),math.ceil(qhi/fine)+1):
            q=row*fine+.21*c.spacing_mm
            xx=np.linspace(x0-1,x1+1,max(100,int((x1-x0)*2)))
            phase=specs[0].family_phase
            # Coherent bounded directional drift around the actual host tangent.
            slope=cross_slope
            line=LineString(np.c_[xx,host(xx)+q+slope*(xx-(x0+x1)/2)])
            regions=[]
            for spec,g in zip(specs,effective):
                # Shared field is intentionally sparse outside intensified subpatches.
                step=1 if spec.density_tier else (3 if c.relation=='shared' else 2 if fine<c.spacing_mm else 1)
                if row%step==0:regions.append(g)
            ownership=unary_union(regions).union(connections)
            for j,part in enumerate(line_parts(line.intersection(ownership))):
                # Dissolve edges unevenly; do not trace a perimeter or close a base.
                frac=c.edge_dissolution*(.20+.55*(.5+.5*np.sin(row*.73+phase)))
                a=frac*part.length*(.3 if row%2 else .7);b=part.length-frac*part.length*(.7 if row%2 else .3)
                if b-a<2.8:continue
                run=substring(part,a,b)
                p=path_record(f'{identity}/flow-{row}/{j}',run.coords,identity,'surface-patch-flow',.6,depth,'soil-ink')
                p.update(surface_source_id=host_record['id'],semantic_opaque=False,patch_relation=c.relation,patch_members=[s.identity for s,g in zip(specs,effective) if g.intersects(run)],geographic_depth_m=None)
                paths.append(p)
        if c.pigment_enabled and c.pigment_fraction:
            parts=[]
            for s,g in zip(specs,effective):
                # Separate intent; never a plotted fill or boundary.
                cut=affinity.scale(g,math.sqrt(c.pigment_fraction),math.sqrt(c.pigment_fraction),origin=g.centroid)
                parts.append(cut.intersection(g))
            pigment=unary_union(parts).difference(reserve)
    info=dict(version='v04',form='surface-patch-system',raised=False,host_id=host_record['id'],cross_flow_source_id=cross_flow_record['id'] if cross_flow_record is not None else None,directional_blend_slope=cross_slope,specs=[asdict(s) for s in specs],controls=asdict(c),ownership_area_mm2=support.area,patch_count=len(specs),effective_components=len(getattr(support,'geoms',[support])) if not support.is_empty else 0,geographic_depth_m=None)
    surface=Surface(identity,support,paths,[],False,depth,info)
    ground=GroundStudy(surface,pigment,reserve,[dict(spec=asdict(s),geometry=g) for s,g in zip(specs,effective)])
    return ground

def distribution_cases():
    def s(key,x,offset,area,aspect=3.2,irregularity=.18,tier=0,contact='declared contact zone'):
        return PatchSpec(key,x,offset,area,aspect,irregularity,density_tier=tier,contact=contact)
    return [
      ('none','No soil | bare support',[],PatchControls(relation='none'),None),
      ('small','Small neighbor | parent nearly bare',[s('small-neighbor',108,5,155,2.8)],PatchControls(),None),
      ('medium','Medium | irregular shoulder',[s('medium',83,3,850,3.2,.28)],PatchControls(),None),
      ('large-open','Larger | open interior',[s('broad',90,3,2350,4.7,.22)],PatchControls(),box(68,94,82,111)),
      ('separate','Several independent patches',[s('root',22,-8,100,2.6),s('contact',70,0,360,3),s('neighbor',110,5,210,2.8),s('fragment',137,6,100,2.8)],PatchControls(relation='separate'),None),
      ('satellites','Dominant patch + separate satellites',[s('dominant',65,1,640,3.2),s('satellite-a',109,5,150,2.6),s('satellite-b',135,6,100,2.6)],PatchControls(relation='satellites',minimum_separation_mm=3.),None),
      ('connected','Partly connected family + blank interval',[s('family-a',77,2,800,3.4),s('family-b',98,4,370,3.2),s('separate-tail',139,6,105,2.6)],PatchControls(relation='connected',merge_gap_mm=2.),box(121.4,91,124,115)),
      ('shared','Shared field + nested concentrations',[s('field',91,3,1950,4.8,.22),s('inner-a',76,2,320,3,.18,1),s('inner-b',119,5,240,3,.18,1)],PatchControls(relation='shared'),box(91,95,94,110)),
      ('discontinuous','Open discontinuous support | no root patch',[s('left',64,1,250,3.4),s('small-rock-field',124,5,650,3.8)],PatchControls(relation='discontinuous'),box(81,107,101,115)),
    ]
