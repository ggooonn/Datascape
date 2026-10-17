"""Local shallow ground-plane fixtures for catalog review, never terrain placement.

u is lateral distance and depth is normalized far distance. Projection offsets
roots vertically and attenuates physical size. This is a pictorial 2.5D stage,
not a 3D camera, DEM sampler, surface attachment or replacement placement system.
"""
from dataclasses import dataclass,asdict
import numpy as np


@dataclass(frozen=True)
class GroupMember:
    identity:str
    form:str
    u:float
    depth:float
    size_weight:float=1.
    role:str='core'


def members(kind='three'):
    if kind=='two':data=[('P',-.16,.65,1.,'companion'),('B',.13,.12,1.,'anchor')]
    elif kind=='three':data=[('B',-.19,.80,.94,'core'),('P',.16,.62,1.,'core'),('U',.02,.08,.62,'front support')]
    elif kind=='five':data=[('B',-.12,.84,1.,'core'),('B',.17,.63,1.,'core'),('W',-.42,.40,.84,'edge'),
                           ('U',.43,.47,.58,'edge support'),('B',.01,.06,1.04,'anchor')]
    elif kind=='eight':data=[('B',-.92,.76,.94,'rear subgroup'),('P',-.68,.45,1.,'rear subgroup'),
                            ('B',-.47,.08,1.,'front subgroup'),('B',-.04,.82,.92,'rear subgroup'),
                            ('U',.12,.18,.64,'front support'),('B',.32,.51,1.,'middle subgroup'),
                            ('W',.72,.66,.90,'edge'),('B',.91,.05,1.,'anchor')]
    else:raise ValueError('group kind must be two, three, five or eight')
    return [GroupMember(f'{kind}-{i}',*row) for i,row in enumerate(data)]


def project(group,mode='spatial',center=(145,155),span_mm=100,depth_mm=30,height_mm=65,depth_size=.30):
    if mode not in ('array','spatial'):raise ValueError('unknown local projection')
    if len({m.identity for m in group})!=len(group):raise ValueError('unique identities required')
    if not 0<=depth_size<=.5 or span_mm<=0 or depth_mm<0 or height_mm<35:raise ValueError('invalid fixture dimensions')
    if any(not np.isfinite([m.u,m.depth,m.size_weight]).all() or not 0<=m.depth<=1 or m.size_weight<=0 for m in group):
        raise ValueError('finite local coordinates, depth in 0–1 and positive weight required')
    ordered=sorted(group,key=lambda m:-m.depth) if mode=='spatial' else group
    lateral=sorted(group,key=lambda m:m.u)
    ranks={m.identity:i for i,m in enumerate(lateral)}
    lo=min(m.u for m in group);hi=max(m.u for m in group)
    specs=[]
    for m in ordered:
        array_u=lo+(hi-lo)*ranks[m.identity]/max(1,len(group)-1)
        root=[center[0]+m.u*span_mm,center[1]-m.depth*depth_mm] if mode=='spatial' else [center[0]+array_u*span_mm,center[1]]
        h=height_mm*m.size_weight*(1-depth_size*m.depth if mode=='spatial' else 1)
        specs.append({'member':asdict(m),'root':root,'height':max(20.,h),
                      'depth_scale':1-depth_size*m.depth if mode=='spatial' else 1.,'mode':mode})
    return specs
