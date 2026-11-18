"""Attach short, single-pass ground color strokes to visible object contacts."""
from dataclasses import asdict,dataclass,replace
import math

import numpy as np
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union

from .color_v03 import project_clip,tint
from .geometry import poly_parts,rng,stroke
from .ground_bands_v05 import G
from .rock_mass_v04 import vertical_slice


@dataclass(frozen=True)
class TerrainFrame:
    """Register legacy XY to depth and elevation from the original synthetic A rows.

    The screen uses X=east and y=depth−elevation in drawing units. A rows have
    an authored neutral depth and a deformed screen y, so this is an invertible
    local frame for the catalog model, with no claim about measured elevation.
    """
    rows: tuple

    @classmethod
    def from_lines(cls,paths,box):
        _,y0,_,y1=box
        nominal=np.linspace(y0,y1,23)
        grouped={}
        for p in paths:
            index=p.features["line_index"]
            grouped.setdefault(index,[]).extend(p.xy)
        return cls(tuple((float(nominal[i]),np.asarray(sorted(q))) for i,q in sorted(grouped.items())))

    def frame_at(self,x):
        depths=np.asarray([depth for depth,_ in self.rows])
        ys=np.asarray([np.interp(x,q[:,0],q[:,1]) for _,q in self.rows])
        if len(depths)>1 and np.any(np.diff(ys)<=0):
            raise ValueError("Ground projection requires ordered A rows")
        return depths,ys

    @staticmethod
    def interpolate(value,reference,mapped):
        if not len(reference):
            return value
        clipped=float(np.clip(value,reference[0],reference[-1]))
        return float(np.interp(clipped,reference,mapped)+(value-clipped))

    def contact_xyz(self,x,y):
        d,ys=self.frame_at(x)
        depth=self.interpolate(y,ys,d)
        return float(x),depth,depth-y

    def project_xy(self,x,depth):
        d,ys=self.frame_at(x)
        return float(x),self.interpolate(depth,d,ys)

    def slope_at(self,x,depth):
        return (self.project_xy(x+1.1,depth)[1]-self.project_xy(x-1.1,depth)[1])/2.2


@dataclass(frozen=True)
class Contact:
    key: str
    owner: str
    kind: str
    xy: tuple
    xyz: tuple
    width: float
    scale: float
    rank: int | None
    visible: bool
    footprint: tuple = ()


def root_contacts(specimens,solid,frame):
    result=[]
    for owner in specimens:
        x,y=owner["base_xy"]
        size=owner["height_mm"]
        result.append(Contact(owner["id"],owner["id"],"root",(x,y),frame.contact_xyz(x,y),
                              float(np.clip(size*.48,9.5,21)),size,None,not solid.covers(Point(x,y))))
    return result


def rock_contacts(objects,frame):
    """Sample each object's lower silhouette and retain only its exposed contact runs."""
    result=[]
    for obj in sorted(objects,key=lambda o:o.depth):
        owner=obj.record["id"]
        scale=obj.record["width"]
        x0,_,x1,_=obj.outline.bounds
        x,base_y=obj.record["base"]
        xs=np.linspace(max(x0+.65,x-.44*scale),min(x1-.65,x+.44*scale),
                       max(9,int(scale*1.2)))
        q=LineString([(a,vertical_slice(obj.outline,a)[1]) for a in xs])
        near=unary_union([b.outline for b in objects if b.depth>obj.depth]).buffer(.22)
        sections=[(part,flag) for flag,geometry in ((True,q.difference(near)),(False,q.intersection(near)))
                  for part in poly_parts(geometry,2.)]
        for j,(part,exposed) in enumerate(sections):
            span=np.ptp(part[:,0])
            visible=bool(exposed and span>=6.5)
            # A large contact may carry two local accents instead of a full-width stripe.
            centers=(.32,.69) if visible and span>40. else (.5,)
            for k,t in enumerate(centers):
                x=float(np.min(part[:,0])+t*span)
                sec=vertical_slice(obj.outline,x)
                y=sec[1] if sec is not None else base_y
                # The footprint is measured before clipping its colored stroke.
                width=float(np.clip(.65*span if len(centers)==1 else .39*span,8.4,26))
                result.append(Contact(f"{owner}/contact{j}.{k}",owner,"rock",(x,y),frame.contact_xyz(x,y),
                                      width,scale,obj.depth,visible,
                                      tuple(tuple(row) for row in part)))
    return result


def draft_bands(key,contacts,frame,seed):
    if not contacts:
        return []
    depths=[c.xyz[1] for c in contacts]
    low,high=min(depths),max(depths)
    limit=math.tan(math.radians(G["max_tangent_deg"]))
    bias_limit=math.tan(math.radians(G["base_slope_limit_deg"]))
    out=[]
    for c in contacts:
        random=rng("object ground band v07",key,c.key,seed)
        x0,y0=c.xy
        depth=c.xyz[1]
        near=(depth-low)/max(1.,high-low)
        terrain_slope=frame.slope_at(x0,depth)
        bias=float(np.clip(G["a_weight"]*terrain_slope,-bias_limit,bias_limit))
        rows=3 if c.width>21 and c.scale>39 and near>.41 else 2 if c.width>=11 else 1
        top=.91+random.uniform(-.20,.31)
        spacing=(3.40 if c.kind=="root" else 2.95)+random.uniform(-.32,.53)
        for j in range(rows):
            width=c.width*(1-.15*j)*random.uniform(.95,1.14)
            x0_shift=random.uniform(-.12,.12)*c.width
            x=np.linspace(x0+x0_shift-width/2,x0+x0_shift+width/2,max(16,int(width/.57)))
            smooth=.024*np.cos((x[:-1]-x0)*.22+random.uniform(-math.pi,math.pi))
            derivative=np.clip(bias+smooth,-limit,limit)
            y=np.r_[0.,np.cumsum(derivative*np.diff(x))]
            y+=y0+top+spacing*j-float(np.interp(x0,x,y))
            pigment=G["colors"][c.kind][int(j==2 or j==1 and random.random()<.23)]
            s=stroke(f"{key}/{c.key}/band{j}",np.c_[x,y],f"{c.kind}_ground_band",key,c.owner,
                     pigment=pigment,features={"anchors":[c.key],"owners":[c.owner],"row":j,
                     "projected_contact":list(c.xy),"ground_xyz":list(c.xyz),
                     "a_slope":round(terrain_slope,8),"a_weight":G["a_weight"]})
            out.append(tint(s,(.62-.115*j)*(.89+.11*near)))
    return out


def merge_pair(a,b,mask):
    """Join compatible adjacent passes through their short overlap, with a slope limit."""
    if a.role!=b.role or a.pigment!=b.pigment or set(a.features["owners"])&set(b.features["owners"]):
        return None
    pa,pb=np.asarray(a.xy),np.asarray(b.xy)
    if pa[0,0]>pb[0,0]:
        a,b,pa,pb=b,a,pb,pa
    lo,hi=pb[0,0],pa[-1,0]
    if not 2.4<=hi-lo<=9.0 or pb[-1,0]<=hi or pb[-1,0]-pa[0,0]>29.0:
        return None
    x=np.unique(np.r_[pa[:,0],pb[:,0]])
    overlap=(x>=lo)&(x<=hi)
    ya=np.interp(x,pa[:,0],pa[:,1])
    yb=np.interp(x,pb[:,0],pb[:,1])
    if float(np.max(np.abs(ya[overlap]-yb[overlap])))>.95:
        return None
    t=np.clip((x-(lo-3.2))/(hi-lo+6.4),0,1)
    ease=t*t*(3-2*t)
    softened=(1-ease)*ya+ease*yb
    baseline=np.interp(x,[x[0],x[-1]],[ya[0],yb[-1]])
    y=.76*baseline+.24*softened
    xy=np.c_[x,y]
    max_slope=math.tan(math.radians(G["max_tangent_deg"]))
    if np.any(np.abs(np.diff(y))>max_slope*np.diff(x)+1e-9) or LineString(xy).intersection(mask).length>1e-6:
        return None
    za=np.interp(x,pa[:,0],a.pressure_mm)
    zb=np.interp(x,pb[:,0],b.pressure_mm)
    pressure=((1-ease)*za+ease*zb).round(6).tolist()
    feature=dict(a.features,anchors=a.features["anchors"]+b.features["anchors"],
                 owners=a.features["owners"]+b.features["owners"],
                 merged_from=a.features.get("merged_from",[a.id])+b.features.get("merged_from",[b.id]))
    return replace(a,id=f"{a.id}/merge/{b.id}",xy=xy.tolist(),pressure_mm=pressure,features=feature)


def ground_patches(key,contacts,frame,solid,seed):
    draft=draft_bands(key,contacts,frame,seed)
    buffer=solid.buffer(.24) if not solid.is_empty else Polygon()
    exposed={c.key for c in contacts if c.visible}
    eligible=[s for s in draft if s.features["anchors"][0] in exposed]
    clipped=[p for s in eligible for p in project_clip(s,buffer,G["min_path_mm"],"masked")]
    final=[]
    merged=0
    culled=0
    for s in sorted(clipped,key=lambda p:(p.features["row"],p.xy[0][1],p.id)):
        for i,p in enumerate(final):
            merged_path=merge_pair(s,p,buffer)
            if merged_path is not None:
                final[i]=merged_path
                merged+=1
                break
        else:
            line=LineString(s.xy)
            # Thin redundant secondary color only. Each object's first visible pass stays eligible.
            duplicate=s.features["row"]>0 and any(
                p.role==s.role and LineString(p.xy).buffer(.63).intersection(line).length>.72*line.length
                for p in final
            )
            if duplicate:
                culled+=1
            else:
                final.append(s)
    hidden=sum(not c.visible for c in contacts)
    audit=dict(contacts=[asdict(c) for c in contacts],not_painted_contacts=hidden,draft=len(draft),
               rejected_hidden_bands=len(draft)-len(eligible),
               clip_length_mm=round(sum(p.length for p in eligible)-sum(p.length for p in clipped),3),
               joined=merged,culled_secondary=culled)
    return final,draft,clipped,audit
