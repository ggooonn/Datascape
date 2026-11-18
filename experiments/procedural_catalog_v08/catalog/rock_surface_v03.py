"""Projected UV faces, geometry-driven ink and color, and rock assemblies."""
from dataclasses import dataclass
import numpy as np
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from .canopy_v03 import V03
from .color_v03 import project_clip, tint
from .geometry import curve, length, poly_parts, rng, stroke
from .rock_v02 import PROFILES, silhouette, divide_faces

STYLE = {
    "pointed":"fractured", "vertical":"columns", "angular":"fractured", "blocky":"planes",
    "rounded":"weathered", "layered":"laminated", "fragmented":"fractured", "bedrock":"exposed"
}
R = V03["rock"]


@dataclass
class FaceUV:
    """Two projected face axes plus a local fold/curvature term in normalized coordinates."""

    role: str
    polygon: object
    origin: np.ndarray
    u_axis: np.ndarray
    v_axis: np.ndarray
    low: np.ndarray
    size: np.ndarray
    bow: float

    @classmethod
    def from_mass(cls, mass, role, polygon, style):
        coords = np.asarray(polygon.exterior.coords)[:-1]
        origin = np.asarray(polygon.centroid.coords[0])
        relief = np.asarray([mass.width,mass.height])
        principal = np.linalg.eigh(np.cov((coords-origin).T))[1][:, -1]
        if principal[0] < 0:
            principal *= -1
        angle = np.arctan2(principal[1],principal[0])
        if style=="columns" and role!="top":
            angle = np.sign(angle or 1)*np.clip(abs(angle),1.16,1.43)
        elif role=="side":
            angle = np.clip(.68*angle+.36,-.90,.94)
        elif style in {"laminated","exposed"}:
            angle = np.clip(.32*angle+.22*mass.bedding,-.34,.32)
        elif style=="weathered":
            angle = np.clip(.47*angle,-.49,.48)
        else:
            angle = np.clip(.60*angle + .06*relief[1]/relief[0],-.68,.65)
        axis = np.array([np.cos(angle),np.sin(angle)])
        normal = np.array([-axis[1],axis[0]])
        local = (coords-origin) @ np.array([axis,normal]).T
        return cls(role,polygon,origin,axis,normal,local.min(axis=0),np.ptp(local,axis=0),
                   {"weathered":.39,"exposed":.17,"laminated":.095,"fractured":.065,
                    "planes":.035,"columns":.075}[style]*(.73 if role=="top" else 1.0))

    def point(self, u, v, jitter=0.):
        u,v = np.broadcast_arrays(u,v)
        # Local curved contours fan out near the edge of a weathered face.
        v1 = v + self.bow*((2*u-1)**2-.23)*(1-.45*v) + jitter
        u1 = u + .13*(v-.5)*(u-.48)*(1 if self.role=="side" else -.4)
        return self.origin + (self.low[0]+u1*self.size[0])[...,None]*self.u_axis + (self.low[1]+v1*self.size[1])[...,None]*self.v_axis

    def record(self):
        return dict(role=self.role,u_axis=self.u_axis.tolist(),v_axis=self.v_axis.tolist(),
                    uv_size_mm=self.size.tolist(),bow=self.bow)


def face_strokes(key, uv, style, lod, seed):
    r = rng("face uv",key,uv.role,seed)
    view = {"near":1.0,"mid":.71,"far":.45}[lod]
    shape = uv.polygon
    inside = shape.buffer(-.69 if lod=="near" else -.54)
    if inside.is_empty:
        return []
    minimum = R["ink_min_mm"][lod]
    result = []

    def emit(q, role, med=False, color="", weight=1.):
        threshold = R["color_min_mm"][lod] if color else minimum
        for part in poly_parts(LineString(q).intersection(inside),threshold):
            s = stroke(f"{key}/{uv.role}/{role}/{len(result):03d}",part,role,key.rsplit("/",1)[0],key,
                       med,len(result)%2,color,{"face":uv.role,"style":style,"uv":True})
            result.append(tint(s,weight))

    # Long lines articulate the plane. Open caps and the centre of large slabs remain visible.
    positions = {
        "fractured":[.21,.48,.61,.79], "columns":[.23,.42,.70], "planes":[.31,.68],
        "weathered":[.27,.46,.78], "laminated":[.21,.30,.53,.59,.78,.88], "exposed":[.32,.41,.63,.77]
    }[style]
    if uv.role=="top":
        positions = positions[::2]
    count = max(1,round(len(positions)*view))
    choices = np.linspace(0,len(positions)-1,count).round().astype(int)
    for j,v in enumerate(np.asarray(positions)[choices]):
        v += r.uniform(-.048,.048)
        u0,u1 = r.uniform(.03,.26),r.uniform(.76,.99)
        if uv.role=="top":
            u0+=.12
        t = np.linspace(u0,u1,36)
        if style in {"laminated","exposed"}:
            wave = .018*np.sin(t*9.4+1.7*j)
        elif style=="weathered":
            wave = .024*np.sin(t*6.1+.4*j)
        else:
            wave = .017*np.tanh((t-.53)*8)*(1 if j%2 else -1)
        q = uv.point(t,v,wave)
        emit(q,"rock_structure",uv.role=="front" and j==0,weight=.92)
    if lod!="far" and uv.role!="top":
        if style in {"columns","fractured","planes"}:
            for j in range(2 if style=="fractured" and lod=="near" else 1):
                u = .34+.24*j + r.uniform(-.10,.084)
                vv = np.linspace(r.uniform(.16,.29),r.uniform(.64,.93),26)
                shift = (vv-.46)*r.uniform(-.29,.24) + .049*np.tanh((vv-.52)*10)
                emit(uv.point(u+shift,vv),"rock_fracture",j==0 and style=="fractured",weight=.85)
        # Place the short secondary marks in a local patch with a real blank beside it.
        if lod=="near" or style in {"weathered","laminated"}:
            for j in range(3 if lod=="near" else 2):
                start = .48+r.uniform(.01,.19) if uv.role=="side" else r.uniform(.11,.35)
                span = r.uniform(.18,.38)
                t = np.linspace(start,min(.98,start+span),18)
                v = .70+.067*j+r.uniform(-.05,.043)
                q = uv.point(t,v,r.uniform(-.04,.04)*np.sin(t*10.0+j))
                emit(q,"rock_surface_secondary",weight=.73)
    # The same UV frame controls color streaks, with more open lit faces.
    colors = V03["color"]
    spacing = R["color_spacing_mm"][lod]
    v = .18 if uv.role=="side" else .54 if uv.role=="top" else .31
    row = 0
    while v < (.91 if uv.role!="top" else .82):
        if row%5!=3 or uv.role=="side":
            left = .11 + .16*np.sin(row*.86+.2) + r.uniform(.04,.15)
            right = .82 + .10*np.sin(row*.72+1) + r.uniform(-.04,.03)
            t = np.linspace(left,right,36)
            q=uv.point(t,v,.029*np.sin(t*8.4+row*.76))
            if uv.role=="side" or style in {"columns","weathered"} and row%3!=1:
                pigment=colors["rock_gray"]
            elif v>.64 and row%3==1:
                pigment=colors["rock_brown"]
            elif style in {"exposed","weathered"} and v>.7 and row%3==0:
                pigment=colors["rock_green"]
            else:
                pigment=colors["rock_ochre"]
            if uv.role=="front" and row%4==2 and v<.7:
                q=q[len(q)//3:]
            emit(q,"rock_face_color",color=pigment,weight=.54 if uv.role=="top" else .70 if uv.role=="side" else .62)
        row+=1
        v+=spacing/max(1.0,uv.size[1])*r.uniform(.79,1.26)
    return result


def rock(key, morphology, base, width, seed, lod="near", style=None, bedding=0.):
    mass = silhouette(key,morphology,base,width,seed,bedding=bedding)
    faces,ridges = divide_faces(mass,seed,key)
    style = style or STYLE[morphology]
    min_ink = R["ink_min_mm"][lod]
    min_color = R["color_min_mm"][lod]
    strokes = []

    def outer(xy, role, med=False):
        if length(xy)>=min_ink:
            strokes.append(stroke(f"{key}/{role}/{len(strokes):03d}",xy,role,key.rsplit("/",1)[0],key,
                                  med,len(strokes)%2,features={"style":style,"morphology":morphology}))

    outer(mass.crest,"silhouette",True)
    if morphology!="bedrock":
        outer(mass.foot[:2],"foot")
        outer(mass.foot[-2:],"foot")
    for i,ridge in enumerate(ridges):
        if lod=="far" and i:
            continue
        for q in poly_parts(ridge,min_ink):
            outer(q,"face_boundary",i==0)
    frames = [FaceUV.from_mass(mass,role,polygon,style) for role,polygon in faces]
    for uv in frames:
        strokes.extend(face_strokes(key,uv,style,lod,seed))
    # Color and lithic ground traces continue out of the toe, lighter away from it.
    rand = rng("ground transition",key,seed)
    x0,y0,x1,y1 = mass.outline.bounds
    bars = 2 if width>=34 else 1 if width>=22 else 0
    for i in range(bars):
        x = np.linspace(x0-width*rand.uniform(.08,.19)-i*.9,x1+width*rand.uniform(-.04,.11)+i*1.2,72)
        v = (x-base[0])/width
        y = base[1]+1.8+i*R["color_spacing_mm"][lod]*.86 + .018*width*np.cos(v*4.3+i*.49)
        y += v*width*bedding*.24+rand.uniform(-.6,.7)*np.sin(v*7.3)
        if i%2==1:
            x,y=x[len(x)//6:],y[len(y)//6:]
        color = V03["color"]["rock_green" if i==1 and morphology in {"rounded","bedrock"}
                             else "ground_ochre" if i else "rock_brown"]
        s=stroke(f"{key}/ground_color/{i}",np.c_[x,y],"rock_ground_color",key,key,pigment=color,
                 features={"distance_band":i,"style":style})
        s=tint(s,.67-.10*i)
        strokes.extend(project_clip(s,mass.outline.buffer(.45),min_color,"ground_edge"))
    return strokes,mass.outline,dict(id=key,shape=morphology,style=style,base=list(base),width=width,
                                     height=mass.height,lod=lod,seed=seed,
                                     outline=list(mass.outline.exterior.coords),
                                     frames=[f.record() for f in frames])


def occlude(groups):
    """Keep closer outlines above farther rock traces, preserving their materials."""
    covered = None
    strokes = []
    for paths,outline,meta in sorted(groups,key=lambda x:x[2]["base"][1],reverse=True):
        for s in paths:
            if covered is None:
                strokes.append(s)
                continue
            minimum = R["color_min_mm" if s.medium=="COLOR" else "ink_min_mm"][meta["lod"]]
            strokes.extend(project_clip(s,covered,minimum,"behind_rock"))
        covered = outline if covered is None else covered.union(outline)
    # Ground color belongs outside every visible solid, including nearer neighbors.
    out = []
    for s in strokes:
        if s.role=="rock_ground_color":
            out.extend(project_clip(s,covered.buffer(.35),R["color_min_mm"]["near"],"outside_formation"))
        else:
            out.append(s)
    return out,covered


def formation(key, variant, base=(98,92), seed=223, scale=1.):
    """Four rock relationships with contrasting size ratios and spacing."""
    x,y = base
    arrangements = {
        "serial":[(-65,-13,35,"vertical"),(-27,0,44,"angular"),(11,-14,31,"pointed"),
                  (47,2,40,"blocky"),(69,18,12,"fragmented")],
        "anchor":[(-9,-2,66,"layered"),(-52,8,13,"fragmented"),(-39,15,9,"angular"),
                  (31,8,10,"rounded"),(47,19,12,"bedrock"),(58,12,7.5,"fragmented")],
        "medium":[(-54,6,29,"rounded"),(-29,-10,26,"angular"),(-7,8,31,"blocky"),
                  (20,-8,30,"layered"),(44,10,26,"rounded"),(67,0,22,"bedrock")],
        "field":[(-73,-27,29,"vertical"),(-57,-9,22,"layered"),
                 (-36,-22,29,"angular"),(-23,3,35,"layered"),(3,-20,23,"fragmented"),
                 (17,11,28,"rounded"),(32,-13,23,"bedrock"),(48,5,32,"blocky"),
                 (64,13,25,"layered"),(77,-16,22,"pointed")],
    }
    r=rng("rock formation v03",key,seed)
    specs=arrangements[variant]
    components=[]
    subgroups=[]
    for i,(dx,dy,w,shape) in enumerate(specs):
        bed = -.13 + r.uniform(-.1,.1)
        widths = []
        loc=(x+dx*scale,y+dy*scale)
        if variant=="field":
            local = [(0,0,w,shape),(-.54*w,.23*w,.30*w,"fragmented"),
                     (.55*w,.14*w,.25*w,"bedrock" if i%2 else "rounded")]
            if i%3==0:
                local.append((.69*w,.26*w,.18*w,"angular"))
        else:
            local=[(0,0,w,shape)]
        for j,(ox,oy,ww,morphology) in enumerate(local):
            view="near" if ww>=35 else "mid" if ww>=19 else "far"
            components.append(rock(f"{key}/G{i:02}R{j:02}",morphology,(loc[0]+ox*scale,loc[1]+oy*scale),
                                   ww*scale,seed+37*i+11*j,view,bedding=bed))
            widths.append(ww*scale)
        subgroups.append(dict(base=list(loc),dominant=shape,widths_mm=widths))
    paths,mask=occlude(components)
    # Broad ground runs group neighboring visible toes; small fragments share these accents.
    if variant=="anchor":
        joins=[(0,2),(0,4)]
    elif variant=="serial":
        joins=[(0,1),(2,3)]
    elif variant=="medium":
        joins=[(0,2),(2,4),(4,5)]
    else:
        joins=[(1,3),(3,5),(5,7),(7,8)]
    for j,(a,b) in enumerate(joins):
        left,right=sorted([subgroups[a],subgroups[b]],key=lambda g:g["base"][0])
        ax,ay=left["base"]
        bx,by=right["base"]
        w=bx-ax
        ay+=left["widths_mm"][0]*.15+1
        by+=right["widths_mm"][0]*.15+1
        control=[[ax-.24*left["widths_mm"][0],ay+2.4],
                 [ax+.24*w,ay+2.1],[ax+.73*w,by+1.4],
                 [bx+.21*right["widths_mm"][0],by+3.4]]
        q=curve(control,.82)
        s=stroke(f"{key}/formation_ground/{j}",q,"rock_ground_color",key,key,
                 pigment=V03["color"]["rock_green" if j%3==1 else "ground_ochre"],
                 features={"joins":[a,b]})
        paths.extend(project_clip(tint(s,.52),mask.buffer(.6),R["color_min_mm"]["near"],"toe_transition"))
    return paths,mask,dict(arrangement=variant,seed=seed,groups=subgroups,
                            rocks=[m for _,_,m in components])
