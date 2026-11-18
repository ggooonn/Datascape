"""Stable woody framework, selectable crown grammar, and coupled 2D communities."""
from dataclasses import replace
import json

import numpy as np
from shapely.geometry import LineString

from .context import Cover
from .geometry import CFG, ROOT, curve, length, rng, stroke
from .vegetation import family_traits, specimen as v01_specimen

REF = json.loads((ROOT / "config/refinement.json").read_text())
WOODY = {"trunk", "trunk_edge", "codominant", "branch", "secondary"}
DEPTH = {"near": 0, "mid": 1, "far": 2}


def crown_path(center, width, depth, sign, family, band, variant=0):
    """Sample a single smooth lobe or hanging arc without piecewise bends."""
    t = np.linspace(0, 1, max(13, int(3 * width)))
    if family == "W":
        x = sign * width * (-.81 + 1.61 * t - .24 * t**3)
        y = depth * (-.38 + band + .12 * t + 1.22 * t**2.2)
    else:
        u = 2 * t - 1
        x = width * u
        arch = REF["B"]["arch"] if family == "B" else .25 if family == "P" else .43
        y = depth * (band - arch * (1 - u**2) + .13 * sign * u + .10 * variant * np.sin(np.pi * t))
    return center + np.column_stack([x, y])


def specimen(key, family, height, base_xy, lod="near", season="spring", traits=None, seed=1,
             sparse=0., variant="v02", seasonal=False):
    """Generate reference trunk/branches once, then apply family and season rules."""
    if variant == "v01":
        return v01_specimen(key, family, height, base_xy, lod, season, traits, seed)
    old, old_pads, meta = v01_specimen(key, family, height, base_xy, lod, "spring", traits, seed)
    if not seasonal and family not in ("B", "W"):
        return old, old_pads, meta
    random = rng("v02 crown", seed, key)
    sign = meta["growth"]["handedness"]
    paths = [s for s in old if s.role in WOODY]
    season_style = REF["same_site_seasons"][season] if seasonal else {
        "width": 1.0, "volume": 1.0, "pad_pattern": "family_sample"
    }
    pigment = CFG["seasons"][season]["colors"]
    crown_pads = []
    candidates = []
    if season_style["pad_pattern"] != "exposed_twigs":
        gap_selector = {
            "family_sample": lambda i: (i % (5 if family == "B" else 4) == 2 and i != len(old_pads)-1),
            "terminal_buds": lambda i: i % 3 == 1,
            "linked_canopy": lambda i: i % 6 == 3 and sparse > .5,
            "broken_lobes": lambda i: i % 4 == 1,
        }[season_style["pad_pattern"]]
        for i, (x, y, w, d) in enumerate(old_pads):
            if gap_selector(i) or (sparse > .25 and i % 5 == 3):
                continue
            bw = REF[family] if family in ("B","W") else REF["B"]
            half = w * bw["reach"] * season_style["width"] * random.uniform(.94, 1.09)
            half = max(half, height * (.095 if family == "W" else .078))
            depth = d * season_style["volume"]
            center = np.array([x, y]) + ([-.07*half*sign, -.12*depth] if season == "summer" else [0,0])
            if season_style["pad_pattern"] == "broken_lobes":
                center += [half*.19*sign*(-1)**i, depth*.21*(-1)**i]
                half *= .84 if i % 2 else 1.02
            count = bw["passes"][lod]
            if seasonal and season == "summer" and lod!="far":
                count += 1
            if seasonal and season == "spring":
                count = max(1, count-1)
            if sparse>.4:
                count=max(1,count-1)
            spacing=bw["spacing_mm"]
            if count>1 and depth*.98/(count-1)<spacing:
                count=max(1,int(depth*.98/spacing)+1)
            offsets = [0.] if count==1 else np.linspace(-.49,.49,count)
            for j, b in enumerate(offsets):
                length_scale=1-.12*abs(b) + .045*(-1)**i
                q = crown_path(center, half*length_scale, depth, sign, family, float(b), (-1)**i)
                if length(q)>=CFG["lod"][lod]["min_ink_mm"]:
                    candidates.append((i,j,q,center,half,depth))
        kept = []
        # Compare sustained nearby runs instead of rejecting all crossing lines.
        for i,j,q,center,half,depth in sorted(candidates,key=lambda z:(z[1],z[0])):
            inkline=LineString(q)
            distances = np.array([inkline.distance(line) for line in kept])
            if len(kept) and int(np.sum(distances<.52))>=2 and j>0:
                continue
            kept.append(inkline)
            paths.append(stroke(f"{key}/canopy_v02/{i:02}.{j}",q,"canopy",key.rsplit("/",1)[0],key,
                          strong=False,layer=(i+j)%2,features={"family":family,"lod":lod,"season":season,
                          "curve":"descending continuous" if family=="W" else "continuous lobed arch"}))
            if j==0:
                crown_pads.append(tuple(map(float,(*center,half*.8,max(1.5,depth*.88)))))
                if i % (3 if season=="autumn" else 2) != 2:
                    qq=crown_path(center+[0,depth*.24],half*.93,depth,sign,family,.03,1)
                    paths.append(stroke(f"{key}/color_v02/{i:02}",qq,"canopy_color",key.rsplit("/",1)[0],
                                        key,pigment=pigment[i%len(pigment)],features={"season":season}))
    else:
        # Winter uses visible terminal forks on the common branches. P retains needle pads.
        for i,s in enumerate([s for s in paths if s.role in ("branch","codominant","secondary")]):
            if i% (2 if lod=="near" else 3):
                continue
            q=np.asarray(s.xy)
            tip=q[-1]
            vec=tip-q[max(0,len(q)-5)]
            u=vec/max(1e-9,np.linalg.norm(vec))
            n=np.array([u[1],-u[0]])
            if n[1]>0:
                n*=-1
            d=max(4.7,height*.14)
            vv=curve([tip-u*d*.26,tip+u*d*.24+n*.18*d,tip+u*d*.58+n*.51*d],.82)
            if length(vv)>=CFG["lod"][lod]["min_ink_mm"]:
                paths.append(stroke(f"{key}/winter_twig/{i}",vv,"winter_twig",s.group,s.owner,layer=i%2,
                                    features={"family":family,"season":season}))
            # Coherent needle strip only for evergreen-shaped P specimens.
            if family=="P" and i%4==0 and lod!="far":
                qs=crown_path(tip+np.array([0,-1.8]),max(3.1,height*.105),height*.055,sign,"P",0)
                paths.append(stroke(f"{key}/winter_needle/{i}",qs,"canopy",s.group,s.owner,layer=i%2,
                                    features={"family":family,"season":season}))
                crown_pads.append(tuple(map(float,(*tip, max(2.7,height*.08),2.0))))
    return paths,crown_pads,dict(meta,season=season,crown_pads=len(crown_pads),
                                 canopy_grammar=season_style["pad_pattern"],sparse=float(sparse))


def spatial_centers(width, depth, count, key, seed, layout):
    c=REF["placement"][layout]
    r=rng("layout-v02",seed,key)
    used=[]
    sites=np.asarray(c["sites"])
    limit=c["min_spacing_mm"]
    # Alternate weighted growth pockets and reject a tapered open corridor.
    weights=np.asarray([1.35 if i==0 else .9+.16*i for i in range(len(sites))])
    for trial in range(2400):
        if len(used)==count:
            break
        idx=int(r.choice(len(sites),p=weights/weights.sum()))
        u,v=sites[idx]+r.normal(0,c["spread"],2)
        if abs(u)>.48 or abs(v)>.48 or abs(u-c["gap_x"]-.10*v)<c["gap_halfwidth"]*(1+.32*v):
            continue
        xy=np.array([u*width,v*depth])
        if used and min(np.linalg.norm(xy-item[0]) for item in used)<limit:
            continue
        used.append((xy,idx))
    if len(used)!=count:
        raise ValueError(f"Only {len(used)} stems fit within the footprint for {key}; adjust density or dimensions")
    return sorted(used,key=lambda p:(p[0][1],p[0][0]))


def community(key, base_xy, width, depth, height, seed, families="BBWBUBWUB", layout="depth",
              lod="mid", season="spring", seasonal=False, vegetation_mask=True, variant="v02"):
    placements=spatial_centers(width,depth,len(families),key,seed,layout)
    random=rng("growth-v02",seed,key)
    common={f:family_traits(f,random) for f in sorted(set(families))}
    latent=random.normal(0,.24,(len(REF["placement"][layout]["sites"]),3))
    stages=[.90 if i==len(families)//2 else .49 if i%5 in (1,4) else .68 for i in range(len(families))]
    stages[int(len(families)*.81)]=1.0
    plan=[]
    logs=[]
    pads=[]
    for i,((offset,site),f) in enumerate(zip(placements,families)):
        y=float(offset[1]/depth)
        h=height*stages[i]*(.82+.35*(.5+y))*random.uniform(.93,1.07)
        crowd=min(np.linalg.norm(offset-q) for j,(q,_) in enumerate(placements) if i!=j) if len(placements)>1 else 30
        stress=float(np.clip(1-crowd/18,0,.6))
        local=latent[site] + random.normal(0,.05,3)
        tr=common[f]
        tr=replace(tr,crown=float(tr.crown*(1+local[0]*.34-.24*stress)),
                   openness=float(np.clip(tr.openness + local[1]*.25+.19*stress,.13,.72)),
                   lean=float(np.clip(tr.lean + local[2]*.12,.01,.37)),
                   fork=float(np.clip(tr.fork+local[2]*.19,.05,.92)))
        view=lod
        if lod=="mid" and y<-.26:
            view="far"
        if lod=="mid" and y>.28 and h>height*.68:
            view="near"
        stem=np.asarray(base_xy)+offset
        ident=f"{key}/T{i:02}"
        p,q,m=specimen(ident,f,h,stem,view,season,tr,seed+i*23,
                       sparse=.48 if layout=="sparse" else stress*.48,seasonal=seasonal,variant=variant)
        plan+=p
        pads.extend([(*r,ident) for r in q])
        logs.append(dict(m,depth_y=float(offset[1]),pocket=site,stage=float(stages[i]),crowding=stress))
    if vegetation_mask:
        plan=soft_vegetation_occlusion(plan,pads,logs)
    return plan,pads,dict(key=key,layout=layout,seed=seed,size_mm=[width,depth],specimens=logs,
                          shape_origin="synthetic growth pockets; X/Y in image space; no landcover claim")


def soft_vegetation_occlusion(plan,pads,logs):
    canopy=Cover(pads)
    y={s["id"]:s["depth_y"] for s in logs}
    front={ident:Cover([p for p in pads if y[p[4]]>j+12])
           for ident,j in y.items()}
    result=[]
    for s in plan:
        if s.role not in WOODY|{"canopy","canopy_color"}:
            result.append(s)
            continue
        same=canopy.at(s.xy,exclude=s.owner)
        other=np.clip((front[s.owner].at(s.xy)-.68)/.32,0,1)
        factor=1-REF["weak_mutual_ink_loss"]*same-REF["foreground_ink_loss"]*other
        # Preserve woody pressure between the four same-site season frames.
        if s.role in WOODY:
            factor=np.ones_like(factor)
        result.append(replace(s,pressure_mm=(np.asarray(s.pressure_mm)*factor).round(6).tolist(),
                              features=dict(s.features,weak_mask_peak=float(1-factor.min()),
                                            depth_mask_peak=float((REF["foreground_ink_loss"]*other).max())
                                            if s.role not in WOODY else 0)))
    return result


def undergrowth(key, logs, season):
    r=rng("low cover",key)
    form=REF["same_site_seasons"][season]
    result=[]
    for i,m in enumerate(logs):
        if r.random()>form["undergrowth"]:
            continue
        a=np.asarray(m["base_xy"]) + [r.uniform(-9,9),r.uniform(1,5)]
        for j in range(2 if season in ("spring","summer") else 1):
            w=r.uniform(5,10)
            dy={"spring":3.0,"summer":5.6,"autumn":1.8,"winter":.7}[season]
            q=curve([a+[-w*.6,.7],a+[-w*.22,-dy],a+[w*.28,-.8*dy],a+[w*.60,.3]])
            role={"spring":"shoots","summer":"ground_cover","autumn":"dry_grasses","winter":"low_remnant"}[season]
            result.append(stroke(f"{key}/undergrowth/{i}.{j}",q,role,key,key,layer=j%2))
    return result
