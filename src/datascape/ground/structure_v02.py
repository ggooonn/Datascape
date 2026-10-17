"""Structural interpretations on v01 mass scaffolds; no scene extraction.

Bedding, joints and rounded weathering are pictorial regimes. Their directions
are explicitly authored synthetic fields, not geology inferred from a DEM.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
import math
import numpy as np
from shapely.geometry import LineString, Polygon, Point, box, GeometryCollection
from shapely import affinity
from shapely.ops import unary_union, substring
from datascape.ground.grammar import Surface, rock as mass_v01, path_record, rng_for
from datascape.vegetation.tree_occlusion_proof import line_parts

VERSION='rock-ground-candidate-0.2'
MINIMUM_MM=2.8


@dataclass(frozen=True)
class StructuralField:
    identity: str = 'structural-field-0'
    regime: str = 'layered'
    orientation_deg: float = -12.
    spacing_mm: float = 4.5
    origin: tuple = (0.,0.)
    curvature: float = .6
    separation_mm: float = 1.2
    seed: int = 20261017
    local_rotation_deg: float = 0.

    def validate(self):
        if self.regime not in ('layered','jointed','rounded'):raise ValueError('unknown structural regime')
        values=[self.orientation_deg,self.spacing_mm,*self.origin,self.curvature,self.separation_mm,self.local_rotation_deg]
        if not np.isfinite(values).all() or not 1.2<=self.spacing_mm<=30 or not 0<=self.curvature<=3 or not 0<=self.separation_mm<=8:
            raise ValueError('invalid structural field dimensions')
        if abs(self.local_rotation_deg)>12:raise ValueError('local rotation must remain correlated and bounded')

    @property
    def angle(self): return math.radians(self.orientation_deg+self.local_rotation_deg)

    @property
    def tangent(self): return np.array([math.cos(self.angle),math.sin(self.angle)])

    @property
    def normal(self): return np.array([-math.sin(self.angle),math.cos(self.angle)])


@dataclass
class StructuralMass:
    surface: Surface
    field: StructuralField
    white_reserve: object
    gaps: list
    pigment_support: object
    parent_id: str | None = None


def _ellipse(x,y,rx,ry):
    return affinity.scale(Point(x,y).buffer(1,quad_segs=32),rx,ry)


def scaffold(identity,anchor=(80,100),width=78,height=58,form='compact',
             seed=20261017,burial=.12,slope=0.,depth=3.,scaffold_id=None):
    """Reuse v01 outer masses; small stones keep only a scaled scaffold.

    A ground half-plane crops actual visible mass. No ground-cut edge is drawn
    as a closed bottom contour. Child support remains nonplotting geometry.
    """
    if min(width,height)<3 or max(width,height)>500 or not 0<=burial<=.4 or abs(slope)>.6:
        raise ValueError('invalid mass dimensions or ground relation')
    vw,vh=max(12,width),max(12,height)
    base=mass_v01(scaffold_id or identity,anchor=anchor,width=vw,height=vh,form=form,
                  seed=seed,burial=burial,depth=depth,texture=False)
    sx,sy=width/vw,height/vh
    support=affinity.scale(base.support,sx,sy,origin=anchor)
    planes=[(np.asarray(p)-anchor)*[sx,sy]+anchor for p in base.planes]
    # The slope belongs to the declared supporting fixture, not arbitrary noise.
    def warp(p):
        p=np.asarray(p,float).copy();p[:,1]+=slope*(p[:,0]-anchor[0]);return p
    support=Polygon(warp(support.exterior.coords)).buffer(0)
    planes=[warp(p) for p in planes]
    x,y=anchor
    ground=Polygon([(x-width*2,y+slope*(-width*2)),(x+width*2,y+slope*width*2),
                    (x+width*2,y-height*4),(x-width*2,y-height*4)])
    visible=support.intersection(ground)
    return Surface(identity,visible,[],planes,form!='bedrock',depth,
        dict(version=VERSION,scaffold_source='unchanged v01 mass geometry',scaffold_id=scaffold_id or identity,
             form=form,seed=seed,anchor_mm=list(anchor),width_mm=width,height_mm=height,
             burial=burial,slope=slope,geographic_depth_m=None,
             evidence='synthetic mass and authored structure; no observed rock type'))


def _record(identity,key,xy,part,width,depth,field,construction,role='rock-ink'):
    r=path_record(f'{identity}/{key}',xy,identity,part,width,depth,role)
    r.update(geometry_revision=VERSION,catalog_version=VERSION,structural_field_id=field.identity,
             structural_regime=field.regime,structural_orientation_deg=field.orientation_deg,
             local_rotation_deg=field.local_rotation_deg,generator_seed=field.seed,
             structural_source_id=construction,geological_evidence='authored synthetic interpretation',
             geographic_depth_m=None,placement_uncertainty='fixture only; actual structural orientation unknown')
    return r


def _emit(result,identity,key,xy,part,support,field,depth,width=.55,cut=None):
    original=LineString(xy)
    if original.length<MINIMUM_MM:return
    geometry=original if support is None else original.intersection(support)
    if cut is not None:geometry=geometry.difference(cut)
    for j,g in enumerate(sorted(line_parts(geometry),key=lambda p:original.project(p.interpolate(.5,normalized=True)))):
        if g.length<MINIMUM_MM:continue
        points=np.array(g.coords)
        q=[original.project(Point(p)) for p in [points[0],points[-1]]]
        if q[0]>q[1]:points=points[::-1];q=q[::-1]
        if LineString(points).is_ring:continue
        r=_record(identity,f'{key}/fragment-{j}',points,part,width,depth,field,
                  f'{field.identity}/{key}')
        r['construction_arc_mm']=q
        result.append(r)


def _field_line(field,level,bounds,secondary=False):
    d,n=field.tangent,field.normal
    lo,hi=bounds
    t=np.linspace(lo,hi,max(50,int((hi-lo)/.7)))
    bend=field.curvature*np.sin(t/35+.45)
    if field.regime=='layered':
        # A common offset across a fracture moves all neighboring bands in
        # the same way; it is not independent per-line vertex randomness.
        bend+=field.separation_mm*.45*np.tanh((t-55)/1.7)
    p=np.asarray(field.origin)+t[:,None]*d+(level+bend)[:,None]*n
    return p


def _field_bounds(support,field):
    x0,y0,x1,y1=support.bounds
    corners=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])-field.origin
    a=corners@field.tangent;b=corners@field.normal
    return (a.min()-10,a.max()+10),(b.min()-5,b.max()+5)


def structural_mass(base,field,identity=None,parent_id=None,omit_reserve=True,contours=True):
    field.validate();identity=identity or base.identity
    s=deepcopy(base);s.identity=identity
    x0,y0,x1,y1=s.support.bounds;w=x1-x0;h=y1-y0
    if min(w,h)<=0:raise ValueError('empty visible mass')
    center=np.array([(x0+x1)/2,(y0+y1)/2])
    # One bounded open shoulder, not a full-body white silhouette. It is recorded
    # separately from opacity and from global mist, and applies to optional color.
    white=_ellipse(x0+w*.69,y0+h*.32,min(w*.19,14.),min(h*.18,9.)).intersection(s.support) if omit_reserve and w>=20 else GeometryCollection()
    if w>100: white=white.intersection(s.support.buffer(-4.))
    paths=[];gaps=[]
    anchor=s.info.get('anchor_mm',[center[0],y1]);slope=s.info.get('slope',0.)
    yy=lambda x:anchor[1]+slope*(x-anchor[0])
    # Omit the contact/burial edge rather than cutting the perimeter at fixed
    # fractions. It remains a body boundary but is never a plotted baseline.
    ground_cut=Polygon([(x0-5,yy(x0-5)-1.0),(x1+5,yy(x1+5)-1.0),
                        (x1+5,y1+h+10),(x0-5,y1+h+10)])
    gaps.append(dict(reason='burial / soil contact',geometry=ground_cut.intersection(s.support.buffer(.8)),plot=False))
    if not white.is_empty:gaps.append(dict(reason='pictorial open shoulder / surface turn',geometry=white,plot=False))
    joint_cuts=[]
    if field.regime in ('layered','jointed') and w>20:
        for i,u in enumerate([.36,.74]):
            xx=x0+w*u
            joint=LineString([(xx-w*.06,y0-h*.1),(xx+w*.06,y1+h*.1)])
            # Only a narrow fracture mouth interrupts an otherwise structural
            # perimeter. The same mouth also splits crossing bedding bands.
            joint_cuts.append(joint.buffer(.6+field.separation_mm*.25,cap_style=2))
            gaps.append(dict(reason=f'fracture mouth {i}',geometry=joint_cuts[-1].intersection(s.support.buffer(.6)),plot=False))
    if contours:
        border=s.support.boundary
        cut=unary_union([ground_cut,white,*joint_cuts])
        for i,g in enumerate(line_parts(border.difference(cut))):
            _emit(paths,identity,f'visible-contour-{i}',g.coords,'ink-contour',None,field,s.depth,.65)
    inset=s.support.buffer(-.7)
    if inset.is_empty:inset=s.support
    small=w<17 or h<11
    if small:
        # Pebble-like marks get one optional crease, never a miniature hatch fill.
        if w>=10:
            p=np.array([[x0+w*.30,y0+h*.32],[x0+w*.45,y0+h*.70]])
            _emit(paths,identity,'small-crease',p,'small-structure',inset,field,s.depth,.55)
    elif field.regime=='layered':
        tr,nr=_field_bounds(s.support,field)
        indices=np.arange(math.floor(nr[0]/field.spacing_mm)-1,math.ceil(nr[1]/field.spacing_mm)+2)
        for i in indices:
            # Paired beds and wider openings produce local structural rhythm.
            if int(i)%7 in (4,5):continue
            level=i*field.spacing_mm + (.28*field.spacing_mm if int(i)%3==1 else 0)
            p=_field_line(field,level,tr)
            _emit(paths,identity,f'bedding-{int(i)}',p,'bedding-band',inset,field,s.depth,.55,
                  unary_union([white,*joint_cuts]))
        for i,cut in enumerate(joint_cuts):
            # Two locally bounded fracture paths; neither fills the whole face.
            xx=x0+w*[.36,.74][i]
            t=np.linspace(.25+.1*i,.76-.08*i,32)
            p=np.c_[xx+w*.10*(t-.5),y0+h*t]
            _emit(paths,identity,f'cross-joint-{i}',p,'secondary-fracture',inset,field,s.depth,.6,white)
    elif field.regime=='jointed':
        tr,nr=_field_bounds(s.support,field)
        for i in range(math.floor(nr[0]/field.spacing_mm)-1,math.ceil(nr[1]/field.spacing_mm)+2):
            if i%5==3:continue
            # Correlated nonuniform joint spacing and a shared bent lower face.
            offset=(.13 if i%3==0 else -.10 if i%3==1 else 0.)*field.spacing_mm
            p=_field_line(field,i*field.spacing_mm+offset,tr)
            t=np.linspace(0,1,len(p))
            p+=field.normal[None,:]*(np.maximum(t-.48,0)*h*.18)[:,None]
            clipped=line_parts(LineString(p).intersection(inset))
            for j,g in enumerate(clipped):
                # Most joints terminate at selected cross-break zones, while a
                # few carry structure through the whole exposed face.
                aa,bb=([.0,.80] if i%4==1 else [.22,1.] if i%4==2 else [0.,1.])
                run=substring(g,aa,bb,normalized=True)
                _emit(paths,identity,f'primary-joint-{i}/{j}',run.coords,'primary-joint',None,field,s.depth,.65,white)
                if i%3==0 and g.length>22:
                    tail=substring(g,.52,.88,normalized=True)
                    tailxy=np.asarray(tail.coords)+field.normal*1.4
                    _emit(paths,identity,f'joint-shoulder-{i}/{j}',tailxy,'joint-shoulder',inset,field,s.depth,.50,white)
        crossing=replace(field,orientation_deg=field.orientation_deg-63,local_rotation_deg=0.,curvature=.25)
        cr,cn=_field_bounds(s.support,crossing)
        for i in range(math.floor(cn[0]/(field.spacing_mm*1.10)),math.ceil(cn[1]/(field.spacing_mm*1.10))+1):
            if i%3==2:continue
            p=_field_line(crossing,i*field.spacing_mm*1.10,cr)
            for j,g in enumerate(line_parts(LineString(p).intersection(inset))):
                aa,bb=([.05,.59] if i%2 else [.38,.95])
                part=substring(g,aa,bb,normalized=True)
                _emit(paths,identity,f'cross-fracture-{i}/{j}',part.coords,'cross-fracture',None,field,s.depth,.55,white)
    else:
        # Open meridians broaden around the shoulder of a rounded mass. Sparse
        # transverse spall seams are incomplete arcs, never nested closed loops.
        us=[-.88,-.69,-.48,-.28,.52,.73,.88] if w>=40 else [-.70,-.32,.64]
        for i,u in enumerate(us):
            t=np.linspace(.13+.04*(i%2),.91-.05*(i%3),64)
            xx=center[0]+w*.49*u*(.42+.58*np.sin(t*np.pi*.82))
            xx+=math.tan(math.radians(field.local_rotation_deg))*(t-.5)*h
            yy0=y0+h*t
            _emit(paths,identity,f'weathered-meridian-{i}',np.c_[xx,yy0],
                  'curved-surface',inset,field,s.depth,.55,white)
        for i,t in enumerate([.36,.70]):
            u=np.linspace(-.8,.18,42) if i==0 else np.linspace(.25,.8,30)
            p=np.c_[center[0]+w*.46*u,y0+h*(t+.22*(1-u*u))]
            _emit(paths,identity,f'spall-seam-{i}',p,'partial-spall-seam',inset,field,s.depth,.6,white)
    s.paths=paths
    s.info.update(regime=field.regime,structural_field_id=field.identity,
                  structural_orientation_deg=field.orientation_deg,local_rotation_deg=field.local_rotation_deg,
                  spacing_mm=field.spacing_mm,parent_id=parent_id,contour_policy='contact and fracture motivated; separate pictorial shoulder')
    for p in paths:p['parent_mass_id']=parent_id or identity
    # Optional later color is an irregular partial surface support; no paint
    # simulation, alpha prediction or executable fill is generated.
    color_parts=[]
    for i,face in enumerate(s.planes):
        if i%3!=1:continue
        a,b,c,d=np.asarray(face)
        def q(u,v):return ((1-u)*a+u*b)*(1-v)+((1-u)*d+u*c)*v
        patch=Polygon([q(.14,.35),q(.80,.35),q(.87,.88),q(.20,.90)])
        color_parts.append(patch.intersection(s.support))
    support_color=unary_union(color_parts).difference(white)
    return StructuralMass(s,field,white,gaps,support_color,parent_id)


def make_mass(identity='mass-0',field=None,**kw):
    return structural_mass(scaffold(identity,**kw),field or StructuralField(),identity)


@dataclass(frozen=True)
class FormationControls:
    orientation_deg: float = -12.
    separation_mm: float = 1.2
    size_hierarchy: float = 1.
    burial: float = .13
    slope: float = .045
    spacing_mm: float = 4.5

    def validate(self):
        if not np.isfinite(list(self.__dict__.values())).all() or not .7<=self.size_hierarchy<=1.3 or not 0<=self.separation_mm<=6 or not 0<=self.burial<=.35 or abs(self.slope)>.3:
            raise ValueError('invalid correlated formation controls')


@dataclass
class Formation:
    identity: str
    masses: list
    field: StructuralField
    parent_support: object
    children: list
    controls: FormationControls
    parent_reference: dict


def formation(identity='formation',controls=None,correlated=True,seed=20261017):
    """Connected parent exposure -> separated blocks -> sparse detached stones.

    Three intersecting exposure supports share one field evaluated on their union.
    Detached members inherit its orientation with bounded position-correlated tilt.
    """
    c=controls or FormationControls();c.validate()
    field=StructuralField(identity+'/parent-field','layered',c.orientation_deg,c.spacing_mm,
                          (8.,18.),.65,c.separation_mm,seed)
    recipes=[('exposure-a',55.,96.,80.,62.),('exposure-b',105.,93.,57.,42.),
             ('exposure-c',130.,96.,33.,24.)]
    children=[];bases=[]
    for i,(name,x,y,w,h) in enumerate(recipes):
        x+=max(0.,c.separation_mm-1.2)*i*.75
        base=scaffold(identity+'/'+name,(x,y+c.slope*(x-55)),w,h,form='bedrock',seed=seed,
                      burial=c.burial,slope=c.slope,depth=4.+i*.1,scaffold_id='formation-scaffold/'+name)
        bases.append(base);children.append(dict(object_id=base.identity,parent_id=identity,
            role='connected-exposure',width_mm=w,height_mm=h,depth=base.depth,
            field_id=field.identity,anchor_mm=base.info['anchor_mm']))
    parent_support=unary_union([s.support for s in bases])
    detachment=GeometryCollection()
    if c.separation_mm>2:
        gap=c.separation_mm-1.2
        detachment=Polygon([(86,55),(86+gap,55),(91+gap,110),(91,110)])
        parent_support=parent_support.difference(detachment)
    parent=Surface(identity+'/connected-exposure',parent_support,[],[p for s in bases for p in s.planes],False,4.,
        dict(anchor_mm=[55.,96.],slope=c.slope,form='connected-bedrock',width_mm=132.,height_mm=62.,
             seed=seed,version=VERSION,component_ids=[s.identity for s in bases],
             surface_source_id='declared-group-ground',attachment_status='synthetic support only'))
    main=structural_mass(parent,field,parent_id=identity)
    if not detachment.is_empty:main.gaps.append(dict(reason='authored physical fracture separation',geometry=detachment,plot=False))
    if not correlated:
        # Matched negative control: same connected body but separately reset
        # directions/phases. No random independent placement is introduced.
        ink=[];claimed=GeometryCollection()
        for i,b in enumerate(bases):
            b=deepcopy(b);b.support=b.support.difference(claimed);claimed=claimed.union(b.support)
            if b.support.is_empty:continue
            independent=replace(field,identity=identity+f'/reset-field-{i}',orientation_deg=[-12,24,-29][i],origin=(i*13.,i*7.))
            ink+=structural_mass(b,independent,contours=False).surface.paths
        main.surface.paths=[p for p in main.surface.paths if p['grammar_part']=='ink-contour']+ink
    masses=[main]
    detached=[('block',153.,101.,35.,26.,2.7),('stone',174.,104.,16.,12.,2.1),
              ('pebble-a',159.,107.,8.,6.,1.8),('pebble-b',181.,106.,6.,4.5,1.5)]
    for i,(name,x,y,w,h,depth) in enumerate(detached):
        w=w/(c.size_hierarchy**(.4+i*.2));h=h/(c.size_hierarchy**(.4+i*.2))
        x+=c.separation_mm*(.8+i*.4);y+=c.slope*(x-153)
        rotation=5.5*math.sin((x-55)/43)
        f=replace(field,local_rotation_deg=rotation)
        if not correlated:f=replace(f,identity=identity+f'/reset-detached-{i}',orientation_deg=(-1)**i*24.)
        m=make_mass(identity+'/'+name,f,anchor=(x,y),width=w,height=h,
                    form='compact' if i in (2,3) else 'angular',burial=min(.35,c.burial+.07),slope=c.slope,
                    seed=seed,depth=depth,scaffold_id='formation-scaffold/'+name)
        m.parent_id=identity
        for p in m.surface.paths:p['parent_mass_id']=identity
        masses.append(m);children.append(dict(object_id=m.surface.identity,parent_id=identity,
            role='detached-block' if i==0 else 'small-stone',width_mm=w,height_mm=h,depth=depth,
            field_id=f.identity,local_rotation_deg=rotation,anchor_mm=[x,y]))
    return Formation(identity,masses,field,parent_support,children,c,
        dict(identity=identity+'/parent-structural-mass',geometry_role='nonplotting structural relation',
             evidence='synthetic correlated arrangement; geological relationship not observed',
             geographic_depth_m=None,detachment_direction='down-slope authored',seed=seed))


def cliff_segment(identity='cliff-segment',seed=20261017):
    """One explicit 340 mm local exposure strip, not a mountain system."""
    c=FormationControls(orientation_deg=77.,spacing_mm=14.,separation_mm=1.7,slope=.015)
    f=StructuralField(identity+'/shared-joints','jointed',77.,14.,(0.,10.),.45,1.7,seed)
    specs=[(70,102,95,58),(142,103,99,80),(216,104,103,66),(286,105,73,43)]
    bases=[scaffold(f'{identity}/face-{i}',(x,y),w,h,form='bedrock',seed=seed,
                    burial=.10,slope=.015,depth=4.) for i,(x,y,w,h) in enumerate(specs)]
    support=unary_union([b.support for b in bases])
    parent=Surface(identity,support,[],[p for b in bases for p in b.planes],False,4.,
        dict(anchor_mm=[70,102],slope=.015,form='connected-cliff-segment',seed=seed,version=VERSION,
             surface_source_id='synthetic-cliff-foot-profile',width_mm=support.bounds[2]-support.bounds[0],
             height_mm=support.bounds[3]-support.bounds[1],component_ids=[b.identity for b in bases],
             attachment_status='local synthetic segment for future terrain ownership; no F2 replacement'))
    m=structural_mass(parent,f,parent_id=identity+'/structural-parent')
    return m,bases
