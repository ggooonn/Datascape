"""Rock silhouettes, explicit faces, structural texture and formation-aware visibility."""
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from .geometry import CFG, rng, stroke, length, curve, poly_parts

def rock_geometry(key, xy, width, height, morphology, dip, seed):
    random=rng("rock",seed,key)
    setup=CFG["formations"][morphology]
    x,y=np.asarray(xy,float)
    w,h=width,height
    crown=setup["crown"]
    burial=setup["burial"]
    jitter=random.uniform(-.08,.08,6)
    upper=np.array([[-.53,-.25],[-.40,-crown*.77],[-.12,-crown],
                    [.20,-crown*.92],[.44,-crown*.67],[.54,-.30]],float)
    upper[:,1]+=jitter
    if morphology=="angular":
        upper[2]=[-.26,-.94]
        upper[3]=[.26,-.69]
    if morphology=="bedrock":
        upper[2]=[-.25,-.66]
        upper[3]=[.25,-.62]
    if morphology in ["rounded","buried"]:
        upper=curve(upper,bend=1,step=.09)
    ridge=[];toe=[]
    for i,(u,v) in enumerate(upper):
        shade=.025*np.sin((u+.5)*np.pi)
        ridge.append([u*.98-.035,v*.69+shade-setup["facet_skew"]*.28*u])
        toe.append([u*.88+.025, -.035-.07*np.cos((u+.13)*np.pi)+burial*.08])
    def world(p):
        q=np.asarray(p).copy()
        q[:,1]=q[:,1]*(1-burial)+q[:,0]*dip*.43
        return q*[w,h]+[x,y]
    upper,ridge,toe=map(world,(upper,ridge,toe))
    # Front is split into unequal planes. Top and side use the same structural ridge.
    j=max(2,int(.60*(len(upper)-1)))
    k=max(j+1,int(.81*(len(upper)-1)))
    ring=np.vstack([upper,toe[::-1]])
    outline=Polygon(ring).buffer(0)
    top=Polygon(np.vstack([upper[:k+1],ridge[:k+1][::-1]])).buffer(0)
    front=Polygon(np.vstack([ridge[:j+1],toe[:j+1][::-1]])).buffer(0)
    flank=Polygon(np.vstack([ridge[j:],toe[j:][::-1],upper[-1:],upper[k:k+1],ridge[k:k+1]])).buffer(0).difference(top).difference(front)
    # Independent top and front face orientation contributes to texture and open area.
    faces=[("top",top,dip-.21,.34),("front",front,dip+.04,.87),("side",flank,dip+.29,.60)]
    return upper,ridge,toe,outline,faces,j,k

def rock(key,xy,width,height,morphology,seed,lod="near",regime=None,dip=.0,mode="refined"):
    setup=CFG["formations"][morphology]
    regime=regime or setup["texture"]
    random=rng("surface",seed,key)
    upper,ridge,toe,shape,faces,j,k=rock_geometry(key,xy,width,height,morphology,dip,seed)
    level=CFG["lod"][lod]
    plan=[]
    group=key.rsplit("/",1)[0]
    def emit(p,role,strong=False,layer=0,pigment="",face=None,min_len=None):
        if len(p)<2 or length(p)<(min_len or level["min_ink_mm"]):return
        ident=f"{key}/{role}/{len(plan):03}"
        plan.append(stroke(ident,p,role,group,key,strong,layer,pigment,
                           dict(morphology=morphology,regime=regime,face=face,lod=lod,specimen_seed=seed)))
    emit(upper,"silhouette",True)
    emit([upper[0],ridge[0],toe[0]],"silhouette",True,1)
    emit([upper[-1],ridge[-1],toe[-1]],"silhouette",True,1)
    if setup["burial"]<.4:
        split=max(2,int(.49*len(toe)))
        emit(toe[:split],"foot",False,1)
        emit(toe[min(split+1,len(toe)-2):],"foot",False,0)
    else:
        emit(toe[:max(2,len(toe)//3)],"buried_foot",False,1)
    emit(ridge[:k+1],"face_boundary",True,0)
    if lod!="far":
        emit([ridge[j],.52*ridge[j]+.48*toe[j]+[width*.028,0],toe[j]],"face_boundary",False,1)
        if morphology in ["angular","bedrock"]:
            emit([upper[k],ridge[k],toe[k]],"face_boundary",True,1)
    for face,polygon,angle,richness in faces:
        p=polygon.buffer(-.7 if lod=="near" else -.52)
        if p.is_empty:continue
        xmin,ymin,xmax,ymax=p.bounds
        ww,hh=xmax-xmin,ymax-ymin
        center=np.array(p.representative_point().coords[0])
        beds=max(1,int(round(level["rock_beds"]*richness*(.82 if mode=="refined" else 1))))
        for i,v in enumerate(np.linspace(-.44,.41,beds)):
            # Shape-local dense zones alternate with clean planes. Top faces stay sparse.
            if mode=="refined" and face=="top" and i%3==1:continue
            y=center[1]+v*hh
            x=center[0]
            theta=angle+(0.025 if face=="front" else -.05)
            half=ww*.88
            if mode=="refined":
                x+=ww*(.15*np.sin(i*1.7)+random.uniform(-.10,.10))
                half*=random.uniform(.29,.78) if face!="side" else random.uniform(.37,.61)
                y+=hh*random.uniform(-.031,.031)
                if face=="front":
                    y+=hh*.07*np.sin(i*1.6)
            if regime=="jointed":
                theta+=.52 if face=="side" else -.33
            elif regime=="weathered":
                theta=.42*theta
            if mode=="regular":
                theta=dip;half=ww*1.1
            points=[[x-half,y-half*theta],[x-half*.42,y-half*.42*theta+(hh*.05 if regime=="weathered" else 0)],
                    [x+half*.27,y+half*.27*theta-(hh*.12 if regime=="weathered" else hh*.038)],
                    [x+half,y+half*theta]]
            for part in poly_parts(LineString(curve(points,bend=1)).intersection(p),level["min_ink_mm"]):
                emit(part,"bedding" if regime!="weathered" else "erosion",face=="front" and i%4==0,
                     i%2,face=face)
                if (i+int(face=="side"))%3==0:
                    seg=part[max(0,len(part)//8):max(2,len(part)*7//8)]
                    seg=seg+[0,.95 if face=="front" else -.80]
                    for c in poly_parts(LineString(seg).intersection(p),4.2):
                        emit(c,"mineral_color",pigment=CFG["palette"]["rock"][["top","front","side"].index(face)],face=face)
        if regime=="layered" and mode=="refined" and face=="front" and lod=="near":
            # Sparse transverse breaks anchor the bedding field to a real face.
            for i,z in enumerate([.24,.68]):
                x=xmin+z*ww
                pts=[[x,ymin], [x+ww*.043,ymin+hh*.32], [x+ww*.026,ymin+hh*.7]]
                for part in poly_parts(LineString(pts).intersection(p),5.2):
                    emit(part,"cross_joint",False,i,face=face)
        if regime=="jointed" and face!="top" and lod!="far":
            for i,z in enumerate([.22,.53,.79] if lod=="near" else [.48]):
                x=xmin+z*ww;y=ymin-.08*hh
                pts=[[x,y],[x+ww*.065,y+hh*.36],[x+ww*.038,y+hh*.60],[x+ww*.13,y+hh*1.13]]
                for part in poly_parts(LineString(pts).intersection(p),4.7):
                    emit(part,"cross_joint",i%2==0,1,face=face)
        if mode=="refined" and level["micro"] and face=="front":
            for i in range(6):
                x=xmin+random.uniform(.12,.57)*ww;y=ymin+random.uniform(.35,.85)*hh
                span=random.uniform(4.8,9.0)
                pts=[[x,y],[x+span*.48,y+span*angle*.39],
                     [x+span,y+span*angle+random.uniform(-.8,.8)]]
                for part in poly_parts(LineString(curve(pts)).intersection(p),4.4):
                    emit(part,"surface_grain",False,i%2,face=face)
    return plan,shape,dict(id=key,seed=seed,morphology=morphology,regime=regime,dip=dip,lod=lod,
                width_mm=width,height_mm=height,burial=setup["burial"],
                face_area_mm2={k:round(p.area,3) for k,p,_,_ in faces},outline_mm2=shape.area)

def formation(key,base_xy,width,height,seed,lod="near",policy="B",regime="layered",mode="refined"):
    r=rng("formation",seed,key)
    dip=float(r.uniform(-.38,.18))
    x,y=base_xy
    if policy=="A":
        members=[(0,0,1,1,"bedrock")]
    else:
        members=[(-.26,-.15,.44,.77,"angular"),(.21,-.11,.46,.72,"compact"),
                 (-.04,.01,.58,1.0,"bedrock"),
                 (.29,.11,.28,.62,"rounded")]
        if lod=="far":
            members=[members[0],members[2],members[3]]
    raw=[]
    for i,(dx,dy,w,h,family) in enumerate(members):
        p,shape,meta=rock(f"{key}/R{i:02}",(x+dx*width,y+dy*height),w*width,h*height,
                         family,seed+i*19,lod,regime,dip+float(r.uniform(-.075,.075)),mode)
        raw.append((p,shape,meta))
    members_meta=[]
    out=[]
    for i,(p,shape,meta) in enumerate(raw):
        front=unary_union([s for _,s,_ in raw[i+1:]]) if i+1<len(raw) else None
        obscured=0.
        for item in p:
            if front is None:
                out.append(item)
                continue
            parts=poly_parts(LineString(item.xy).difference(front),CFG["lod"][lod]["min_ink_mm"])
            obscured+=max(0,item.length-sum(length(q) for q in parts))
            for j,q in enumerate(parts):
                f=dict(item.features,previous_id=item.id,visible_fragment=j)
                out.append(stroke(f"{item.id}/visible{j}",q,item.role,key,item.owner,
                           item.medium=="MEDIUM_INK",int(item.phase[-1])%2 if item.phase!="COLOR" else 0,
                           item.pigment,f))
        members_meta.append(dict(meta,occluded_length_mm=obscured))
    return out,unary_union([s for _,s,_ in raw]),dict(group=key,seed=seed,policy=policy,
           bed_dip=dip,regime=regime,lod=lod,members=members_meta,depth_order="back to front",
           texture_origin="pictorial structural hypothesis, not DEM-derived bedding")
