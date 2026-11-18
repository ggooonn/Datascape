"""Connected projected lithic masses. v03 supplies each free face and its UV frame."""
from dataclasses import dataclass
import json

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union, linemerge

from .color_v03 import project_clip, tint
from .geometry import ROOT, curve, poly_parts, rng, stroke
from .rock_surface_v03 import rock, occlude
from .canopy_v03 import V03

V04=json.loads((ROOT/"config/catalog_v04.json").read_text())
CONTACT=V04["contact"]


@dataclass(frozen=True)
class RockSpec:
    shape: str
    x: float
    y: float
    width: float
    bedding: float=-.12


@dataclass
class Contact:
    """One real polygonal shoulder, plus a local ruled UV surface."""
    boundary: Polygon
    crown: np.ndarray
    foot: np.ndarray
    left_slope: float
    right_slope: float
    pair: tuple

    def uv(self, u, v):
        u=np.asarray(u)
        samples=np.linspace(0,1,len(self.crown))
        x=np.interp(u,samples,self.crown[:,0])
        top=np.interp(u,samples,self.crown[:,1])
        toe=np.interp(u,samples,self.foot[:,1])
        # Preserve local end directions while the middle follows the linking bench.
        end_warp=(self.right_slope-self.left_slope)*(u-.5)*u*(1-u)*6
        return np.c_[x,top+(toe-top)*v+end_warp*np.sin(np.pi*v)]


def vertical_slice(shape,x):
    if shape.is_empty or x<shape.bounds[0] or x>shape.bounds[2]:
        return None
    _,lo,_,hi=shape.bounds
    p=shape.intersection(LineString([(x,lo-1),(x,hi+1)]))
    if p.is_empty:
        return None
    return p.bounds[1],p.bounds[3]


def face_slope(record):
    f=next((f for f in record["frames"] if f["role"]=="front"),record["frames"][0])
    x,y=f["u_axis"]
    return float(np.clip(y/max(.15,x),-.42,.42))


def link_faces(key,i,left,right,seed):
    p,l=left
    q,r=right
    px=p.bounds[2]-l["width"]*CONTACT["inset_fraction"]
    qx=q.bounds[0]+r["width"]*CONTACT["inset_fraction"]
    if qx<px+5.0:
        middle=(px+qx)/2
        px=max(p.bounds[0]+1,min(px,middle-3))
        qx=min(q.bounds[2]-1,max(qx,middle+3))
    if qx<=px:
        raise ValueError("Use left-to-right facing contacts")
    a,b=vertical_slice(p,px),vertical_slice(q,qx)
    if a is None or b is None or min(a[1]-a[0],b[1]-b[0])<2.5:
        raise ValueError("Rock shoulder needs an exposed face on each side")
    random=rng("joined shoulder v04",key,seed,i)
    t=np.linspace(0,1,max(28,int((qx-px)/.53)))
    x=px+(qx-px)*t
    # The shoulder enters both faces at different heights. A shallow notch remains above the seam.
    ay=a[0]+(a[1]-a[0])*random.uniform(.40,.52)
    by=b[0]+(b[1]-b[0])*random.uniform(.35,.51)
    slope_l,slope_r=face_slope(l),face_slope(r)
    def saddle(t):
        return np.sin(np.pi*t)*(random_impulse+1.7*np.sin(2*np.pi*t+notch_phase))
    random_impulse=random.uniform(3.6,7.8)
    notch_phase=random.uniform(-1,1)
    ty=(1-t)*ay+t*by+saddle(t)+2.4*t*(1-t)*((1-t)*slope_l+t*slope_r)
    fy=(1-t)*(a[1]-.85)+t*(b[1]-.85)+3.9*np.sin(np.pi*t)+1.20*t*(1-t)*np.sin(9*t)
    ty=np.minimum(ty,fy-4.0)
    crown=np.c_[x,ty]
    foot=np.c_[x,fy]
    geo=Polygon(np.vstack([crown,foot[::-1]])).buffer(0)
    return Contact(geo,crown,foot,slope_l,slope_r,(i,i+1))


def contact_strokes(key,index,band):
    palette=V03["color"]
    output=[]
    bounds=band.boundary.buffer(-.24)
    for j,(v,u0,u1) in enumerate(zip(CONTACT["local_uv_rows"],(.025,.14,.05),(.98,.85,.92))):
        # One bedding line connects the faces. Lower strata alternate long runs and breaks.
        pieces=[(u0,u1)] if j!=2 else [(u0,.40),(.51,u1)]
        for k,(start,end) in enumerate(pieces):
            u=np.linspace(start,end,45)
            bend=.035*np.tanh((u-.54)*8)*(1 if index%2 else -1)
            vline=v+.044*np.sin(2*np.pi*u+j*.96)+bend
            s=stroke(f"{key}/join{index}/ink{j}.{k}",band.uv(u,vline),"rock_join_uv",key,key,
                     strong=j==0,layer=j%2,features={"neighbors":list(band.pair),"v":v})
            output.extend(project_clip(tint(s,.86 if j==0 else .75),bounds,CONTACT["ink_min_mm"],
                                       "local_uv",inside=True))
    u=np.linspace(.61,.71,25)
    v=np.linspace(.27,.78,25)
    q=band.uv(u+.024*np.tanh((v-.48)*13),v)
    s=stroke(f"{key}/join{index}/fracture",q,"rock_join_fracture",key,key,features={"neighbors":list(band.pair)})
    output.extend(project_clip(tint(s,.62),bounds,CONTACT["ink_min_mm"],"local_uv",inside=True))
    for j,v in enumerate(CONTACT["color_rows"]):
        u=np.linspace(.07+.05*j,.96-.04*j,58)
        y=v+.076*np.sin(2*np.pi*u+j)*np.sin(np.pi*u)
        pigment=palette["rock_gray" if j==1 else "rock_ochre"]
        s=stroke(f"{key}/join{index}/color{j}",band.uv(u,y),"rock_join_color",key,key,
                 pigment=pigment,features={"neighbors":list(band.pair),"v":v})
        output.extend(project_clip(tint(s,.58),bounds,6.2,"local_uv",inside=True))
    return output


def connected_formation(key,specs,links,seed=517,lod="near"):
    """Re-use v03 faces, remove buried contours, and apply shared strata at chosen contacts."""
    specs=list(specs)
    links=sorted(set(links))
    if not specs or any(a.x>=b.x for a,b in zip(specs,specs[1:])):
        raise ValueError("Provide at least one rock and strictly increasing X positions")
    if any(i<0 or i>=len(specs)-1 for i in links):
        raise ValueError("Link indices must refer to an adjacent pair")
    parts=[rock(f"{key}/R{i:02}",s.shape,(s.x,s.y),s.width,seed+i*31,lod,bedding=s.bedding)
           for i,s in enumerate(specs)]
    if not links:
        paths,body=occlude(parts)
        return paths,body,dict(rocks=[m for _,_,m in parts],contacts=[],contact_links=[],components=component_count(body))
    bands=[link_faces(key,i,parts[i][1:],parts[i+1][1:],seed) for i in links]
    body=unary_union([p for _,p,_ in parts]+[b.boundary for b in bands])
    contact_union=unary_union([b.boundary for b in bands])
    paths=[]
    # Preserve the free faces. Where a new shoulder covers them, remove the old closed outline.
    old,_=occlude(parts)
    for s in old:
        if s.role=="rock_ground_color":
            continue
        if s.role in {"silhouette","foot","face_boundary"}:
            mask=contact_union.buffer(.12)
        else:
            mask=contact_union.buffer(-1.0)
        paths.extend(project_clip(s,mask,5.2 if s.medium!="COLOR" else 6.2,"buried"))
    side=unary_union([p for _,p,_ in parts])
    for band in bands:
        index=band.pair[0]
        # Only the exposed part of the shoulder crest is drawn. The lower margin is left to the ground field.
        exposed=LineString(band.crown).difference(side.buffer(.08))
        for j,q in enumerate(poly_parts(exposed,CONTACT["ink_min_mm"])):
            s=stroke(f"{key}/join{index}/rim{j}",q,"connected_rim",key,key,strong=True,
                     features={"neighbors":list(band.pair)})
            paths.append(tint(s,.84))
        paths.extend(contact_strokes(key,index,band))

    contacts=[]
    for band in bands:
        a,b=band.pair
        contacts.append(dict(pair=list(band.pair),polygon=list(band.boundary.exterior.coords),
                             entry_overlap_mm2=[band.boundary.intersection(parts[k][1]).area for k in (a,b)],
                             slopes=[band.left_slope,band.right_slope]))
    return paths,body,dict(rocks=[m for _,_,m in parts],contacts=contacts,contact_links=links,
                           components=component_count(body))


def component_count(body):
    return len(body.geoms) if body.geom_type=="MultiPolygon" else int(not body.is_empty)
