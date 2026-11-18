"""Family morphology, shared community traits, individually articulated growth."""
from dataclasses import dataclass, replace
import numpy as np
from shapely.geometry import LineString, Point
from .geometry import CFG, Environment, rng, stroke, curve, length, resample, poly_parts

@dataclass(frozen=True)
class Growth:
    crown: float
    lean: float
    openness: float
    spread: float
    fork: float
    vigor: float
    handedness: int

def family_traits(code,random):
    f=CFG["families"][code]
    return Growth(*(f[k] for k in ["crown","lean","openness","spread","fork"]),1.0,int(random.choice([-1,1])))

def specimen(key, family, height, base_xy, lod="near", season="spring", traits=None, seed=1):
    """A stem graph and sustained directional foliage strokes in drawing space."""
    random=rng("specimen",seed,key)
    traits=traits or family_traits(family,random)
    level=CFG["lod"][lod]
    season_data=CFG["seasons"][season]
    base=np.asarray(base_xy,float)
    h=height
    s=traits.handedness
    lean=h*traits.lean*s
    plan=[]
    crowns=[]
    order=0
    def emit(points,role,strong=False,tone="",bend=.78):
        nonlocal order
        p=curve(points,bend=bend)
        if len(p)<2 or length(p)<level["min_ink_mm"]:
            return
        key_path=f"{key}/{role}/{order:03}"
        plan.append(stroke(key_path,p,role,key.rsplit("/",1)[0],key,strong,order%2,tone,
                   dict(family=family,lod=lod,season=season,specimen_seed=seed)))
        order+=1

    if family=="U":
        stems=[(-.47,.69),(-.20,.84),(.12,.97),(.42,.63)]
        if lod=="far":stems=stems[::2]
        for j,(side,fac) in enumerate(stems):
            tip=base+[s*(h*side*traits.crown+lean*.45),-h*fac]
            fork=base+(tip-base)*.57+[-s*h*.13,h*.028]
            emit([base,base+(tip-base)*.27+[-s*h*.09,0],fork,tip],"trunk",j==1)
            crowns.append((tip+[0,-h*.03],h*.30*traits.crown,h*.15,side*.20))
            if lod=="near":
                flank=fork+[s*(.12 if side>0 else -.13)*h,-.15*h]
                emit([fork,flank],"branch")
                crowns.append((flank,h*.19,h*.105,side*.37))
    else:
        ys=np.array([0,.24,.47,.70,.88,1.0])
        bumps={"P":[0,-.018,.012,-.028,.014,.028],"B":[0,.01,.02,-.012,-.02,.004],"W":[0,-.04,.026,.055,.01,-.07]}[family]
        trunk=base+np.column_stack([lean*ys**1.22+s*h*np.array(bumps),-h*ys])
        mids=trunk[:4] if lod=="far" else trunk
        emit(mids if lod!="far" else np.vstack([mids,trunk[-1]]),"trunk",True)
        if family=="B":
            fork_at=.34+.14*traits.fork
            root=base+[lean*fork_at,-h*fork_at]
            twin=base+[-s*.23*h,-.88*h]
            emit([root,root+[-s*.070*h,-.18*h],twin],"codominant",True)
            crowns.append((twin+[-s*.025*h,-.025*h],h*.20,h*.118,-s*.10))
        if lod=="near":
            width=h*(.031 if family=="P" else .047)
            emit(trunk[:4]+np.column_stack([width*np.array([1,.67,.42,0])*s,np.zeros(4)]),"trunk_edge")
        n=min(level["branch_slots"],CFG["families"][family]["layers"]+(2 if lod=="near" else 0))
        for j, frac in enumerate(np.linspace(traits.fork*.44+.19,.91,n)):
            root=np.array([np.interp(frac,ys,trunk[:,i]) for i in range(2)])
            sign=s*(-1 if j%2 else 1)
            span=(.36 if family=="P" else .25 if family=="B" else .28)*h*traits.crown*traits.spread/CFG["families"][family]["spread"]
            taper=(1-.58*(j/n)) if family=="P" else (.88+.24*np.sin(j/n*np.pi))*(1-.20*j/n)
            reach=span*taper*random.uniform(.80,1.19)
            drop={"P":-.045,"B":-.47,"W":.47}[family]
            if family=="P" and sign==s:
                reach*=1.25
            tip=root+[sign*reach,drop*reach]
            elbow=root+[sign*reach*.46,(-.13 if family!="B" else -.45)*reach]
            emit([root,elbow,tip],"branch",j in [0,2])
            crowns.append((tip+[sign*.09*reach,-.065*h],(reach*.90 if family=="P" else reach*.86),
                           h*(.060 if family=="P" else .127 if family=="B" else .13),(drop*.43 if family!="W" else drop*.93)))
            if lod=="near" and (j%2==0 or family=="B"):
                secondary=elbow+[sign*reach*.29,-reach*(.42 if family!="W" else -.63)]
                emit([elbow,secondary],"secondary")
                crowns.append((secondary,reach*.48,h*.061,drop*.28))
        crowns.append((trunk[-1]+[0,.025*h],.20*h*traits.crown,.104*h if family=="B" else .065*h, -.11 if family=="P" else 0.0))

    for i,(center,width,depth,dip) in enumerate(crowns):
        bands=max(1,int(round(level["canopy_bands"] * traits.vigor * season_data["foliage"] *
                                (1.0-traits.openness-season_data["openness"]*.55) * (.67 if i%3==1 else 1))))
        if season=="winter" and (i%3==1 or (lod=="far" and i%2)):
            continue
        # Fan-like bands share their local pad axis. Deeper marks fall short in dense cores.
        for j,u in enumerate(np.linspace(-.72,.78,bands)):
            half=width*np.sqrt(max(.12,1-u*u))*.58*random.uniform(.80,1.12)
            lift=depth*(.27+.15*np.cos(u*2))*CFG["families"][family]["band_relief"]*random.uniform(.78,1.16)
            off=center+[random.uniform(-.15,.15)*width,u*depth]
            if bands>2 and j>0 and j<bands-1 and (j+i)%5==2 and traits.openness>.28:
                half*=.75
                off=off+[.10*width*s,0]
            if family=="P":
                stroke_dip=dip+.055*s*np.sin(i)
                points=[off+[-half, -half*stroke_dip + lift*.5],
                        off+[-.5*half,-.5*half*stroke_dip-lift*.25],
                        off+[.4*half,.4*half*stroke_dip-lift*.48],
                        off+[half,half*stroke_dip+lift*.13]]
            elif family=="B":
                points=[off+[-half,lift*.82-half*dip],
                        off+[-.63*half,-lift*.33-.63*half*dip],
                        off+[-.14*half,-lift*.63-.14*half*dip],
                        off+[.30*half,-lift*.20+.30*half*dip],
                        off+[half,lift*.36+half*dip]]
            elif family=="W":
                points=[off+[-s*.74*half,-.58*lift],
                        off+[s*.14*half,-.38*lift],
                        off+[s*.56*half,.37*lift],
                        off+[s*.65*half,lift*(1.35+.55*u)]]
            else:
                points=[off+[-half,lift*.76-half*dip],off+[-.43*half,-lift*.21-.43*half*dip],
                        off+[.35*half,-lift*.36+.35*half*dip],off+[half,lift*.52+half*dip]]
            emit(points,"canopy",j==bands-1 and i%3==0)
        if season!="winter" or i%2==0:
            a=center+[-width*.54,-depth*.08]
            b=center+[width*.53,depth*.28+width*dip*.53]
            if family=="W":
                a=center+[-s*.24*width,-depth*.10]
                b=center+[s*.49*width,depth*.65]
            emit([a,center+[0,-depth*.22],b],"canopy_color",tone=season_data["colors"][i%3])

    # Observable footprint assembled from canopy bands, separate from plot paths.
    pads=[(float(c[0]),float(c[1]),float(max(w*.70,1.8)),float(max(d*1.17,1.3))) for c,w,d,_ in crowns]
    return plan,pads,dict(id=key,family=family,height_mm=h,base_xy=list(map(float,base)),
                          growth={name:getattr(traits,name) for name in traits.__dataclass_fields__},
                          crown_pads=len(pads),lod=lod,season=season,seed=seed)

def community(key,family,base_xy,width,height,seed,count=7,lod="near",season="spring",
              environment=None,mixed=(),mode="refined"):
    """Community structure: shared traits, spatial residuals and crowding response."""
    random=rng("community",seed)
    env=environment or Environment(CFG["environment_fixture"])
    cfg=CFG["community"]
    base=np.asarray(base_xy,float)
    shared_latent=random.normal(0,1,4)
    run=np.linspace(-.42,.42,count)*width
    def terrain_sample(offset):
        if environment is None:
            return env.sample(float(offset+width*.52),float(base[1]*.33))
        return env.sample(float(base[0]+offset),float(base[1]))
    sample=[terrain_sample(x) for x in run]
    weights=np.array([x["cover_proxy"] for x in sample])
    # Cover influences spacing, retaining suitable gaps in the lower-cover pockets.
    u=np.r_[0,np.cumsum(1/(.42+weights[1:]))]
    if u[-1]>0:
        run=(u/u[-1]-.5)*width*.84
    run+=random.uniform(-.018,.018,count)*width
    sample=[terrain_sample(x) for x in run]
    rank_order=random.permutation(count)
    base_jitter=random.uniform(-.04,.04,count)*height
    uncorrelated=rng("independent-control",seed)
    latent=random.normal(0,1,(count,4))
    corr=cfg["spatial_residual_correlation"]
    for i in range(1,count):
        latent[i]=corr*latent[i-1]+(1-corr*corr)**.5*latent[i]
    specimens=[];strokes=[];pads=[]
    predominant=family_traits(family,random)
    for i,x in enumerate(run):
        r=rank_order[i]
        role="dominant" if r==0 else "mid" if r<=max(2,count//2) else "support"
        rr=latent[i]
        common=cfg["shared_trait_weight"]
        p=cfg["latent_amplitude"]*(common*shared_latent+(1-common)*rr)
        local_sample=sample[i]
        fam=mixed[(i+seed)%len(mixed)] if mixed and (i+1)%3==0 else family
        exemplar=predominant if fam==family else family_traits(fam,random)
        gap=min(abs(x-other) for j,other in enumerate(run) if i!=j) if count>1 else width
        crowd=float(np.clip(1-gap/(height*.34),0,.70))
        stage={"dominant":1.0,"mid":.78,"support":.59}[role]
        if mode=="independent":
            stage=uncorrelated.uniform(.53,1.1)
            p=uncorrelated.normal(0,.28,4)
        size=height*stage*(.91+.18*local_sample["cover_proxy"])*float(np.clip(1+.11*rr[1],.84,1.17))
        tr=Growth(
            exemplar.crown*float(np.clip(1+p[0]-.30*crowd,.62,1.20)),
            float(np.clip(exemplar.lean+.055*p[1]+.16*local_sample["slope_dx"],0,.32)),
            float(np.clip(exemplar.openness+p[2]*.31+.16*crowd,.13,.60)),
            float(np.clip(exemplar.spread+p[3]*.16,.45,1.1)),
            float(np.clip(exemplar.fork+p[3]*.25,.05,.92)),
            float(np.clip(1+p[2]+(.13 if role=="dominant" else -.12 if role=="support" else .02),.57,1.24)),
            exemplar.handedness if mode!="independent" else int(uncorrelated.choice([-1,1])))
        coord=base+[x,-x*local_sample["slope_dx"]*.54+base_jitter[i]]
        spec,pad,log=specimen(f"{key}/T{i:02}",fam,size,coord,lod,season,tr,seed+i*31)
        strokes+=spec
        pads += [(a,b,c,d,log["id"]) for a,b,c,d in pad]
        specimens.append(dict(log,role=role,crowding=crowd,environment=local_sample))
    return strokes,pads,dict(group=key,seed=seed,family=family,lod=lod,season=season,mode=mode,shared_latent=shared_latent.tolist(),
                             shared_growth=predominant.__dict__,specimens=specimens)
