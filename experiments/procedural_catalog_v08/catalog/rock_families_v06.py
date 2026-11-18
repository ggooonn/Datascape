"""Related outlines and shared UV orientations, rendered through the v05 depth mask."""
from dataclasses import replace
import json

import numpy as np
from shapely import affinity
from shapely.geometry import LineString

from .geometry import ROOT,length,poly_parts,rng,stroke
from .rock_overlap_v05 import RockObject,compose
from .rock_surface_v03 import FaceUV,R,face_strokes
from .rock_v02 import divide_faces,silhouette

V06=json.loads((ROOT/"config/catalog_v06.json").read_text())
FAMILIES=V06["families"]

# Increasing screen Y corresponds to the closer foot in these study layouts.
COMPOSITIONS={
    "anchor":[(104,108,106,0),(58,110,36,2),(136,117,41,1),
              (81,121,29,1),(168,121,22,2)],
    "sequence":[(53,104,66,2),(100,96,83,0),(150,107,71,1),
                (191,111,58,0),(132,119,31,2),(73,118,30,2)],
    "medium":[(52,99,48,0),(83,104,52,1),(119,94,55,0),
              (151,105,51,1),(180,111,43,2),(111,115,45,2)],
    "formation":[(58,94,61,1),(99,90,77,0),(142,92,81,1),(184,96,57,0),
                 (72,107,51,1),(120,106,62,0),(164,110,49,2),(201,114,38,1),
                 (42,117,29,2),(102,121,38,2),(143,124,44,1)]
}


def aligned_frame(mass,role,face,style,front_deg,side_deg):
    local=FaceUV.from_mass(mass,role,face,style)
    angle=np.arctan2(local.u_axis[1],local.u_axis[0])
    target={"front":front_deg,"side":side_deg,"top":front_deg*.55}[role]
    target=np.deg2rad(target)
    # Keep distinction between planes while stabilizing the axis on corresponding faces.
    angle=target+np.clip(angle-target,-.28,.28)*(.32 if role=="front" else .52)
    axis=np.array([np.cos(angle),np.sin(angle)])
    normal=np.array([-axis[1],axis[0]])
    uv=(np.asarray(face.exterior.coords)[:-1]-local.origin) @ np.array([axis,normal]).T
    return replace(local,u_axis=axis,v_axis=normal,low=np.min(uv,axis=0),size=np.ptp(uv,axis=0))


def shared_joints(key,uv,lod,seed,lean):
    if uv.role=="top" or lod=="far":
        return []
    random=rng("related fractures v06",key,uv.role,seed)
    keep=uv.polygon.buffer(-.65)
    result=[]
    starts=[.31,.66] if uv.role=="front" and lod=="near" else [.49]
    for i,start in enumerate(starts):
        bottom=random.uniform(.73,.94)
        t=np.linspace(random.uniform(.18,.32),bottom,30)
        u=start+lean*(t-.49)+.034*np.tanh((t-.57)*10)
        for j,part in enumerate(poly_parts(LineString(uv.point(u,t)).intersection(keep),R["ink_min_mm"][lod])):
            result.append(stroke(f"{key}/{uv.role}/family_joint/{i}.{j}",part,"rock_fracture",
                                 key.rsplit("/",1)[0],key,strong=uv.role=="front" and i==0,layer=i%2,
                                 features={"face":uv.role,"style":"fractured","uv":True,"shared_lean":lean}))
    return result


def family_member(key,base,width,depth,profile,seed,family):
    cfg=FAMILIES[family]
    profile_index=profile%len(cfg["profiles"])
    shape=cfg["profiles"][profile_index]
    random=rng("rock family member v06",key,seed)
    height=width*cfg["height_ratio"]*([1.0,1.05,.78][profile_index])*random.uniform(.89,1.11)
    front=cfg["front_deg"]+random.uniform(-1.8,1.8)
    side=cfg["side_deg"]+random.uniform(-2.,2.)
    mass=silhouette(key,shape,base,width,seed,height=height,bedding=np.tan(np.deg2rad(front)))
    # A family-specific lean ties together successive crests without connecting their shapes.
    shear=(cfg["edge_lean"]+random.uniform(-.032,.032))
    mass.outline=affinity.affine_transform(mass.outline,[1,-shear,0,1,base[1]*shear,0])
    for line in (mass.crest,mass.foot):
        line[:,0]+=shear*(base[1]-line[:,1])
    faces,ridges=divide_faces(mass,seed,key)
    lod="near" if width>=36 else "mid" if width>=24 else "far"
    minimum=R["ink_min_mm"][lod]
    paths=[]

    def outer(xy,role,strong):
        if length(xy)>=minimum:
            paths.append(stroke(f"{key}/{role}/{len(paths):03d}",xy,role,key.rsplit("/",1)[0],key,
                                strong=strong,layer=len(paths)%2,
                                features={"family":family,"shape":shape,"style":cfg["style"]}))

    outer(mass.crest,"silhouette",True)
    if shape!="bedrock":
        outer(mass.foot[:2],"foot",False)
        outer(mass.foot[-2:],"foot",False)
    for i,ridge in enumerate(ridges):
        if lod!="far" or i==0:
            for q in poly_parts(ridge,minimum):
                outer(q,"face_boundary",i==0)
    frames=[aligned_frame(mass,role,face,cfg["style"],front,side) for role,face in faces]
    for uv in frames:
        work=face_strokes(key,uv,cfg["style"],lod,seed)
        if family=="jointed":
            work=[s for s in work if s.role!="rock_fracture"]+shared_joints(key,uv,lod,seed,cfg["joint_lean"])
        paths.extend(work)
    record=dict(id=key,shape=shape,family=family,style=cfg["style"],width=width,height=height,lod=lod,
                seed=seed,base=list(base),outline=list(mass.outline.exterior.coords),
                frames=[f.record() for f in frames],edge_lean=shear,group_front_deg=cfg["front_deg"])
    return RockObject(paths,mass.outline,record,depth)


def family_objects(key,family,arrangement,seed,spread=1.,scale=1.,origin=(0.,0.)):
    layout=COMPOSITIONS[arrangement]
    order={i:z for z,i in enumerate(sorted(range(len(layout)),key=lambda i:(layout[i][1],i)))}
    return [family_member(f"{key}/R{i:02}",(origin[0]+scale*(122+(x-122)*spread),origin[1]+scale*y),
                          scale*width,order[i],profile,seed+37*i,family)
            for i,(x,y,width,profile) in enumerate(layout)]


def rock_family(key,family,arrangement,seed,spread=1.,scale=1.,origin=(0.,0.)):
    original=family_objects(key,family,arrangement,seed,spread,scale,origin)
    paths,solid,detail=compose(original)
    return original,paths,solid,dict(detail,family=family,arrangement=arrangement,spread=spread)
