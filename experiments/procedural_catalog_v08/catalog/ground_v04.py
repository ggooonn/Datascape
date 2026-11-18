"""Plotter line fields tied to visible rock toes and vegetation roots."""
import numpy as np
import shapely
from shapely.geometry import Polygon

from .canopy_v03 import split_sampled
from .color_v03 import project_clip, tint
from .geometry import rng, resample, stroke
from .rock_mass_v04 import V04, vertical_slice

GROUND=V04["ground"]


def basal_anchors(records,body):
    anchors=[]
    for r in records:
        x,y=r["base"]
        part=vertical_slice(body,x)
        visible_y=max(y,part[1]) if part else y
        anchors.append((x,visible_y,.43*r["width"],GROUND["rock_reach_mm"]*(.88+r["width"]/176)))
    return anchors


def root_anchors(logs):
    return [(m["base_xy"][0],m["base_xy"][1]+.6,
             6.7+.159*m["height_mm"],GROUND["vegetation_reach_mm"]*(.68+.006*m["height_mm"]))
            for m in logs]


def ground_patch(key, anchors, kind, seed, protect=None):
    """Use related contour runs with irregular edges and a sparse second layer."""
    if not anchors:
        return []
    protect=protect if protect is not None else Polygon()
    random=rng("ground patch v04",key,kind,seed)
    a=np.asarray(anchors,float)
    x=np.linspace(np.min(a[:,0]-1.32*a[:,2]),np.max(a[:,0]+1.30*a[:,2]),
                  max(60,int(np.ptp(a[:,0])*1.7+68)))
    h=np.exp(-.5*((x[:,None]-a[:,0])/a[:,2])**2)
    level=h.max(axis=1)+(.36 if kind=="rock" else .16)*(h.sum(axis=1)-h.max(axis=1))
    y=(h@a[:,1])/h.sum(axis=1)
    spread=(h@a[:,3])/h.sum(axis=1)
    if kind=="rock":
        toe=np.asarray([vertical_slice(protect,xx) for xx in x],dtype=object)
        for i,item in enumerate(toe):
            if item is not None:
                y[i]=.55*y[i]+.45*item[1]
    colors=GROUND["colors"][kind]
    result=[]
    for layer in range(2):
        d=1.0 if layer==0 else 2.05
        row=0
        while d<21:
            off=d/17.0
            wave=(.82+.18*d)*.41*np.sin(x*.076+row*.54)+.52*np.sin(x*.17-row*.65)
            if layer:
                wave+=.37*np.sin(x*.24+row*.61)
            trace=np.c_[x,y+off*spread+wave]
            falloff=np.exp(-.5*(off/(.79+.12*np.sin(x*.069)))**2)
            edge=level*falloff+.108*np.sin(x*.159+row*.71)+.078*np.sin(x*.31-row*.49)
            primary=.54 if kind=="vegetation" else .49
            live=edge>(primary if layer==0 else .84)
            if layer:
                live &= np.sin(x*.066+row*.89)>-.26
            for j,q in enumerate(split_sampled(trace,live,GROUND["minimum_mm"])):
                q=resample(q,.74)
                rel=np.interp(q[:,0],x,edge)
                strength=(.47+.43*np.clip((rel-.43)/.71,0,1))*(.76 if layer else 1.0)
                tone=1 if layer else 2 if row%4==3 else 0
                s=stroke(f"{key}/ground{layer}.{row}.{j}",q,f"{kind}_ground_patch",key,key,
                         pigment=colors[tone],features={"row":row,"layer":layer,"kind":kind})
                result.extend(project_clip(tint(s,strength),protect.buffer(.34),GROUND["minimum_mm"],"ground_clearance"))
            d+=random.uniform(*GROUND["spacing_mm"])*(2.50 if layer else 1.)
            row+=1
    return result
