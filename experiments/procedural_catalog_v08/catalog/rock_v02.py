"""Independent silhouette, face fields, and related rock assemblages in drawing mm."""
from dataclasses import dataclass, replace
import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union, split

from .geometry import CFG, rng, length, poly_parts, curve, stroke

PROFILES = {
    "pointed": ([(-.50,-.08),(-.37,-.25),(-.24,-.51),(.06,-1),(.20,-.61),(.50,-.10)], 1.23, .10, "jointed"),
    "vertical": ([(-.42,-.03),(-.49,-.66),(-.32,-.90),(.27,-.97),(.43,-.73),(.45,-.07)], 1.60, .06, "jointed"),
    "angular": ([(-.53,-.12),(-.45,-.44),(-.10,-.91),(.29,-.70),(.51,-.32),(.52,-.11)], .83, .12, "jointed"),
    "blocky": ([(-.49,-.04),(-.49,-.73),(-.36,-.88),(.39,-.87),(.49,-.68),(.48,-.06)], .82, .07, "jointed"),
    "rounded": ([(-.50,-.11),(-.44,-.46),(-.18,-.70),(.15,-.74),(.39,-.50),(.51,-.08)], .69, .16, "weathered"),
    "layered": ([(-.51,-.09),(-.47,-.29),(-.33,-.30),(-.27,-.53),(.04,-.58),
                 (.13,-.73),(.39,-.71),(.51,-.42),(.54,-.10)], .64, .08, "layered"),
    "fragmented": ([(-.49,-.04),(-.39,-.42),(-.27,-.33),(-.14,-.82),(-.03,-.56),
                    (.16,-.61),(.29,-.48),(.36,-.55),(.49,-.19),(.50,-.05)], .82, .19, "jointed"),
    "bedrock": ([(-.52,-.08),(-.37,-.40),(-.13,-.51),(.21,-.48),(.39,-.34),(.53,-.11)], .52, .33, "layered"),
}
NAMES = {"pointed":"뾰족형","vertical":"직립형","angular":"각진형","blocky":"직각 블록형",
         "rounded":"둥근형","layered":"계단 층상형","fragmented":"파편형","bedrock":"노출 기반암"}

@dataclass
class Mass:
    outline: Polygon
    crest: np.ndarray
    foot: np.ndarray
    width: float
    height: float
    base: tuple
    morphology: str
    bedding: float


def silhouette(key, morphology, base, width, seed, height=None, bedding=.0):
    """Create an outer profile independently of surface treatment."""
    pts, ratio, burial, _ = PROFILES[morphology]
    r=rng("mass-v02",key,seed)
    h=float(height or width*ratio)
    p=np.asarray(pts,float).copy()
    p[:,0]+=r.uniform(-.025,.025,len(p))
    p[:,1]+=r.uniform(-.055,.055,len(p))
    # Move the summit more on the peaked and fragmented profiles, leave the broad top on blocky.
    if morphology in ("pointed","fragmented","angular"):
        p[np.argmin(p[:,1]),0]+=r.uniform(-.075,.085)
    if morphology=="blocky":
        p[1:3,0]=[-.485,-.37]
        p[3:5,0]=[.38,.486]
    p[:,1]=p[:,1]*(1-burial)+p[:,0]*bedding*.1
    p=p*[width,h]+np.asarray(base)
    if morphology in ("rounded","bedrock"):
        p=curve(p,bend=.95)
    toe=np.asarray([[p[0,0],p[0,1]],[base[0]-.29*width,base[1]+.022*h],
                    [base[0]+.02*width,base[1]+r.uniform(.008,.058)*h],
                    [base[0]+.35*width,base[1]+.022*h],p[-1]])
    shape=Polygon(np.vstack([p,toe[1:-1][::-1]])).buffer(0)
    if shape.geom_type!="Polygon":
        shape=max(shape.geoms,key=lambda g:g.area)
    return Mass(shape,p,toe,width,h,tuple(base),morphology,bedding)


def divide_faces(mass, seed, key):
    """Split the silhouette with a skewed surface ridge and a partial buttress."""
    p=mass.outline
    x0,y0,x1,y1=p.bounds
    span=x1-x0
    height=y1-y0
    random=rng("faces-v02",key,seed)
    v=.46 if mass.morphology in ("vertical","blocky") else .56
    y=y0+height*v
    ridge=LineString([(x0-2,y+height*.14),(x0+span*.30,y-height*.11),
                      (x0+span*.63,y-height*.04),(x1+2,y+height*.11)])
    faces=sorted(split(p,ridge).geoms,key=lambda x:x.centroid.y)
    if len(faces)<2:
        return [("front",p)], [ridge.intersection(p)]
    cap=faces[0]
    lower=unary_union(faces[1:])
    flank_x=x0+span*random.uniform(.67,.79)
    dividing=LineString([(flank_x-span*.11,y0-1),(flank_x,y+height*.08),
                         (flank_x+span*.065,y1+1)])
    lower_faces=sorted(split(lower,dividing).geoms,key=lambda g:g.centroid.x)
    named=[("top",cap),("front",lower_faces[0])]
    named.extend([("side",g) for g in lower_faces[1:]])
    return named,[ridge.intersection(p),dividing.intersection(lower)]


def rock(key, morphology, base, width, seed, lod="near", texture=None, bedding=.0, height=None):
    mass=silhouette(key,morphology,base,width,seed,height,bedding)
    faces,ridges=divide_faces(mass,seed,key)
    style=texture or PROFILES[morphology][3]
    group=key.rsplit("/",1)[0]
    minimum=CFG["lod"][lod]["min_ink_mm"]
    r=rng("surface-v02",key,seed)
    paths=[]
    def emit(xy,role,strong=False,pigment="",face=None):
        if len(xy)<2 or length(xy)<minimum:
            return
        paths.append(stroke(f"{key}/{role}/{len(paths):03}",xy,role,group,key,strong,len(paths)%2,pigment,
                           {"morphology":morphology,"lod":lod,"face":face,"texture":style,"seed":seed}))
    emit(mass.crest,"silhouette",True)
    if morphology!="bedrock":
        for segment in (mass.foot[:2],mass.foot[-2:]):
            emit(segment,"foot")
    for i, ridge in enumerate(ridges):
        if lod=="far" and i:
            continue
        for part in poly_parts(ridge,minimum):
            emit(part,"face_boundary",i==0)
    for face, polygon in faces:
        keep=polygon.buffer(-(.62 if lod=="near" else .47))
        if keep.is_empty:
            continue
        x0,y0,x1,y1=polygon.bounds
        w,h=x1-x0,y1-y0
        num={"near":(2,5,3),"mid":(1,4,2),"far":(0,2,1)}[lod][("top","front","side").index(face)]
        slope=bedding+{"top":-.09,"front":.04,"side":.47}[face]
        if style=="weathered":
            slope*=.51
        for j in range(num):
            pos=y0+h*(.16+.68*(j+.4)/max(1,num))
            # Sample from the same bedding direction while preserving local open intervals.
            cx=(x0+x1)/2+w*r.uniform(-.20,.19)
            reach=w*r.uniform(.32,.70)
            warp=h*(.13 if style=="weathered" else .026)
            q=curve([(cx-reach,pos-reach*slope),(cx-reach*.25,pos-reach*.25*slope+warp),
                    (cx+reach*.28,pos+reach*.28*slope+warp*.61),(cx+reach,pos+reach*slope)], .83)
            for part in poly_parts(LineString(q).intersection(keep),minimum):
                role="erosion" if style=="weathered" else "bedding"
                emit(part,role,face=="front" and j==1,face=face)
                if j==0 and face!="top" and lod!="far":
                    for tint in poly_parts(LineString(part+[0,1.05]).intersection(keep),minimum):
                        emit(tint,"mineral_color",pigment=CFG["palette"]["rock"][("top","front","side").index(face)],face=face)
        if lod!="far" and face in ("front","side") and style in ("layered","jointed"):
            n=1 if style=="layered" or lod=="mid" else 2
            for j in range(n):
                x=x0+w*(.32+.34*j)
                q=LineString([(x,y0-.3),(x+w*.09,y0+h*.43),(x+w*.07,y1-.05)])
                for part in poly_parts(q.intersection(keep),max(minimum,5.4)):
                    emit(part,"cross_joint",face=="front" and j==0,face=face)
    return paths,mass.outline,{"id":key,"morphology":morphology,"texture":style,"lod":lod,"seed":seed,
                                "base_mm":list(base),"width_mm":width,"height_mm":mass.height,
                                "bedding":float(bedding),"area_mm2":float(mass.outline.area),
                                "face_count":len(faces),"silhouette":mass.outline.exterior.coords[:],
                                "shape_origin":"synthetic profile; no geological mapping"}


def visible_groups(raw, minimum=4.8):
    """Occlude rear geometry against the union of nearer silhouettes, far to near."""
    final=[]
    covered=None
    for paths,shape,meta in reversed(sorted(raw,key=lambda item:item[2]["base_mm"][1])):
        for s in paths:
            if covered is None or not covered.intersects(LineString(s.xy)):
                final.append(s)
                continue
            parts=poly_parts(LineString(s.xy).difference(covered),minimum)
            for i,q in enumerate(parts):
                cut=stroke(f"{s.id}/visible/{i}",q,s.role,s.group,s.owner,s.medium=="MEDIUM_INK",
                           i%2,s.pigment,dict(s.features,parent=s.id))
                final.append(replace(cut,phase=s.phase))
        covered=shape if covered is None else covered.union(shape)
    return final,covered


def group(key, base, width, seed, lod="near", dominant="angular", supporters=("fragmented","rounded","blocky"),
          bedding=-.14, texture=None):
    """Build one dominant rock and staggered supporting forms on a shared structural axis."""
    r=rng("rock group-v02",seed,key)
    x,y=base
    raw=[rock(f"{key}/R0",dominant,(x,y),width,seed,lod,texture,bedding)]
    for i,f in enumerate(supporters):
        frac=[.38,.23,.18,.31,.19][i%5]*r.uniform(.82,1.15)
        dx=[-.46,.40,.58,-.64,.14][i%5]*width+r.uniform(-.075,.075)*width
        dy=[.13,.12,.26,.22,-.15][i%5]*width + r.uniform(-.035,.035)*width
        sub_lod="far" if width*frac<18 else "mid" if lod=="near" else lod
        raw.append(rock(f"{key}/R{i+1}",f,(x+dx,y+dy),width*frac,seed+29*i+17,
                        sub_lod,None,bedding+r.uniform(-.063,.063)))
    paths,shape=visible_groups(raw)
    return paths,shape,dict(id=key,base_mm=list(base),lod=lod,dominant=dominant,width_mm=width,seed=seed,
                           bedding=bedding,components=[m for _,_,m in raw])


def large_formation(key="formation",seed=410):
    """Ten exposed subgroups on one irregular ledge with a common bedding direction."""
    specs=[(32,84,30,"vertical"),(68,106,42,"layered"),(108,73,38,"fragmented"),
           (132,126,63,"angular"),(181,98,32,"blocky"),(190,147,36,"rounded"),
           (225,120,43,"bedrock"),(260,90,31,"pointed"),(288,135,47,"layered"),(330,109,31,"fragmented")]
    random=rng("formation-v02",key,seed)
    raw=[]
    shapes=list(PROFILES)
    for i,(x,y,w,f) in enumerate(specs):
        rule=tuple(shapes[int(j)] for j in random.choice(len(shapes),int(2+i%3),replace=False))
        lod="near" if i in (3,6,8) else "mid"
        raw.append(group(f"{key}/G{i:02}",(x,y),w,seed+71*i,lod,f,rule,
                         bedding=-.18+float(random.uniform(-.055,.055))))
    paths,p=visible_groups(raw)
    return paths,p,dict(key=key,seed=seed,group_count=len(raw),groups=[m for _,_,m in raw],
                        bedding_axis=-.18,shape_origin="synthetic bench of ten related groups")
