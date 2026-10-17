"""Archived v04 comparison recipe only; not the accepted v05 detail entry point."""
from copy import deepcopy
from dataclasses import dataclass,asdict
import math
import numpy as np
from shapely.geometry import Point,LineString,GeometryCollection
from shapely import affinity
from shapely.ops import unary_union,substring
from datascape.ground.structure_v02 import scaffold,structural_mass,StructuralField,_field_line,_field_bounds
from datascape.ground.grammar import path_record
from datascape.ground.refinement_v03 import rhythm,footprint
from datascape.vegetation.tree_occlusion_proof import line_parts

@dataclass(frozen=True)
class DensityControls:
    detail_level:int=1
    local_length_density_mm_per_mm2:float=.55
    dense_area_coverage:float=.24
    meso_spacing_mm:float=2.7
    secondary_patch_count:int=2
    secondary_scale:float=1.
    omission:float=.18
    micro_spacing_mm:float=1.7
    micro_length_mm:tuple=(3.2,7.2)
    overlap_limit:float=.20
    def validate(self):
        if self.detail_level not in (0,1,2) or self.secondary_patch_count not in (0,1,2,3):raise ValueError('discrete detail/patch preset')
        if not 0<=self.dense_area_coverage<=.4 or not 1.4<=self.meso_spacing_mm<=12 or not .1<=self.local_length_density_mm_per_mm2<=1.:raise ValueError('physical density bounds')
        if not .5<=self.secondary_scale<=1.4 or not 0<=self.omission<=.45 or not 0<=self.overlap_limit<=.35:raise ValueError('bounded variation required')
        if not 1.2<=self.micro_spacing_mm<=5 or not 2.8<=self.micro_length_mm[0]<=self.micro_length_mm[1]<=10:raise ValueError('physical micro limits')

def ellipse(cx,cy,rx,ry):return affinity.scale(Point(cx,cy).buffer(1,quad_segs=40),rx,ry)

def alternatives():
    """A: one scaffold, one apex. B: genuinely occluding finite exposures."""
    field=StructuralField('v04/parent-field','jointed',77,14,(0,10),.45,1.7)
    specs={'A':[('A-parent',(174,105),324,90,'bedrock',.12,4.,field)],
           'B':[('B-parent',(147,108),252,85,'bedrock',.12,4.,field),
                ('B-rear',(267,92),123,68,'bedrock',.16,4.7,StructuralField(field.identity,'jointed',77,16,(0,10),.45,1.7,local_rotation_deg=5)),
                ('B-front',(244,113),145,61,'angular',.22,2.8,StructuralField(field.identity,'layered',-13,8,(0,10),.55,1.7,local_rotation_deg=-6))]}
    result={}
    for variant,recipe in specs.items():
        masses=[]
        for name,anchor,w,h,form,burial,rank,f in recipe:
            s=scaffold('v04/'+name,anchor=anchor,width=w,height=h,form=form,burial=burial,depth=rank,scaffold_id='v04/shared/'+name)
            # Same mass/plane engine, explicitly finite local exposed bodies.
            s.opaque=True;s.info['visibility_basis']='authored finite local exposed body; not DEM'
            m=structural_mass(s,f,parent_id='v04/'+variant+'-parent')
            m.surface.paths,event=rhythm(m.surface.paths,'interruption',structural_gaps=[g['geometry'] for g in m.gaps if g['reason'].startswith('fracture')])
            m.surface.info['rhythm']=event;masses.append(m)
        result[variant]=masses
    return result

def detail_zones(mass,c):
    x0,y0,x1,y1=mass.surface.support.bounds;w=x1-x0;h=y1-y0
    specs=[(.25,.56,40.,23.),(.82,.58,26.,17.),(.53,.84,19.,10.)][:c.secondary_patch_count]
    zones=[ellipse(x0+w*x,y0+h*y,rx*c.secondary_scale,ry*c.secondary_scale).intersection(mass.surface.support.buffer(-1.0)) for x,y,rx,ry in specs]
    if c.dense_area_coverage==0:zones=[]
    total=unary_union(zones).area
    budget=mass.surface.support.area*c.dense_area_coverage
    if total>budget and total:
        factor=math.sqrt(budget/total)
        zones=[affinity.scale(z,factor,factor,origin=z.centroid) for z in zones]
    # Equal-area measurement windows: physical mm, fixed across all detail levels.
    dense=ellipse(x0+w*.25,y0+h*.56,17,13).intersection(mass.surface.support)
    sparse=ellipse(x0+w*.54,y0+h*.42,17,13).intersection(mass.surface.support)
    return zones,dense,sparse

def hierarchical_detail(mass,controls=DensityControls()):
    c=controls;c.validate();m=deepcopy(mass);base=deepcopy(m.surface.paths)
    zones,dense,sparse=detail_zones(m,c);events=[];added=[]
    x0,y0,x1,y1=m.surface.support.bounds
    eligible=x1-x0>=120 and y1-y0>=55
    cuts=unary_union([m.white_reserve,*[g['geometry'] for g in m.gaps if g['reason'].startswith('fracture')]])
    occupied=footprint(base)
    def accept(line,zone,key,level):
        nonlocal occupied
        g=line.intersection(zone).intersection(m.surface.support.buffer(-.9)).difference(cuts)
        for j,part in enumerate(line_parts(g)):
            if part.length<2.8:continue
            p=path_record(m.surface.identity+'/'+key+f'/{j}',part.coords,m.surface.identity,level,.55,m.surface.depth,'rock-ink')
            p.update(detail_level=level,structural_field_id=m.field.identity,generator_seed=m.field.seed,assumed_footprint_mm=.6)
            candidate=LineString(p['xy_mm']).buffer(.3)
            overlap=candidate.intersection(occupied).area/candidate.area
            used=sum(LineString(q['xy_mm']).intersection(zone).length for q in base+added)
            allowed=overlap<=c.overlap_limit and used+part.length<=zone.area*c.local_length_density_mm_per_mm2
            events.append(dict(source_id=p['id'],level=level,overlap_fraction=overlap,accepted=allowed))
            if allowed:added.append(p);occupied=occupied.union(candidate)
    if c.detail_level and eligible:
        for zi,zone in enumerate(zones):
            # Shared local plane tendency. Spacing is physical, not scaled with rock width.
            f=StructuralField(m.field.identity,'jointed',m.field.orientation_deg,c.meso_spacing_mm,m.field.origin,.32,1.7,local_rotation_deg=(-4 if zi%2==0 else 5))
            tr,nr=_field_bounds(zone,f)
            for i in range(math.floor(nr[0]/c.meso_spacing_mm),math.ceil(nr[1]/c.meso_spacing_mm)+1):
                if i%9==4 and c.omission>.1:continue
                line=LineString(_field_line(f,(i+.36)*c.meso_spacing_mm,tr))
                # Unequal shoulder release within a chosen secondary plane.
                for k,run in enumerate(line_parts(line.intersection(zone))):
                    a=.06+.07*((i+zi)%3);b=.92-.05*((i+2*zi)%2)
                    accept(substring(run,a,b,normalized=True),zone,f'meso-{zi}/{i}/{k}','meso')
            if c.detail_level>=2 and x1-x0>=180 and y1-y0>=65:
                cx,cy=zone.centroid.coords[0]
                micro=ellipse(cx-5,cy+6,11,8).intersection(zone)
                d=f.tangent;n=f.normal
                # A bounded local fan of short fractures, never recursive subdivision.
                for i in range(-5,6):
                    center=np.array([cx-5,cy+6])+n*i*c.micro_spacing_mm+d*(1.3*np.sin(i*.7+zi))
                    length=c.micro_length_mm[0]+(c.micro_length_mm[1]-c.micro_length_mm[0])*(.5+.5*np.sin(i*.9+zi))
                    xy=np.array([center-d*length*.45,center+d*length*.55])+n[None,:]*np.array([.25,.85])[:,None]
                    accept(LineString(xy),micro,f'micro-{zi}/{i}','micro')
    m.surface.paths=base+added
    m.surface.info['hierarchy_controls']=asdict(c)
    def density(region,records):return sum(LineString(p['xy_mm']).intersection(region).length for p in records)/region.area if region.area else 0.
    audit=dict(controls=asdict(c),eligible=eligible,events=events,added_paths=len(added),
        dense_coverage=unary_union(zones).area/m.surface.support.area if zones else 0.,
        dense_window_area_mm2=dense.area,sparse_window_area_mm2=sparse.area,
        dense_length_density=density(dense,m.surface.paths),sparse_length_density=density(sparse,m.surface.paths),
        meso_spacing_mm=c.meso_spacing_mm,micro_length_mm=list(c.micro_length_mm),
        omission_basis='existing fractures and white reserve plus selected plane shoulder releases; no recursive texture')
    audit['dense_sparse_ratio']=audit['dense_length_density']/max(audit['sparse_length_density'],1e-9)
    return m,audit,dict(zones=zones,dense=dense,sparse=sparse)
