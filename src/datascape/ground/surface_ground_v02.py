"""Local surface-density patches, separate from optional mound geometry.

A shared host path and its lateral direction carry the strokes. The patches
are omission/replacement ownership, never opaque objects or raised platforms.
"""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import PchipInterpolator
from shapely.geometry import LineString, Point, GeometryCollection
from shapely import affinity
from shapely.ops import unary_union
from datascape.ground.grammar import Surface,path_record,rng_for
from datascape.ground.structure_v02 import VERSION,MINIMUM_MM
from datascape.vegetation.tree_occlusion_proof import line_parts


@dataclass
class GroundStudy:
    surface: Surface
    pigment_support: object
    white_reserve: object
    patches: list


def ground_source(width=184,identity='ground-source',depth=5.,base_y=88.):
    out=[];xx=np.linspace(4,width-4,180)
    # Same modest synthetic surface bend for every source row. It does not
    # create an isolated mound or claim a geographic surface.
    host=base_y+.025*(xx-40)+1.6*np.sin((xx-20)/35)
    for i,v in enumerate([-13.,-8.,-3.,2.,7.,12.,17.]):
        out.append(path_record(f'{identity}/A/{i}',np.c_[xx,host+v],identity,'A-like',.6,depth,'terrain-ink'))
    for i,x in enumerate(np.arange(19,width-8,27)):
        t=np.linspace(0,1,45)
        out.append(path_record(f'{identity}/C/{i}',np.c_[x+11*t,base_y-10+26*t+.025*(x-40)],identity,'C-like',.6,depth,'terrain-ink'))
    return out


def localized_ground(identity='local-ground',host_record=None,
                     patches=((40.,90.,24.,8.),(103.,92.,28.,11.),(155.,99.,19.,7.)),
                     depth=4.5,seed=20261017,corridor=None):
    if host_record is None:host_record=ground_source()[2]
    host=np.asarray(host_record['xy_mm'],float)
    if np.any(np.diff(host[:,0])<=0):raise ValueError('ground host must be monotone in x')
    if not all(np.isfinite(q).all() and min(q[2:])>0 for q in map(np.asarray,patches)):
        raise ValueError('positive finite patch radii required')
    sample=PchipInterpolator(host[:,0],host[:,1],extrapolate=True)
    paths=[];regions=[];pigment=[];metadata=[]
    # Deliberately uneven source-relative spacing; length and occupancy vary
    # coherently by row, not by per-vertex noise or a texture-count budget.
    offsets=np.array([-1.,-.73,-.47,-.25,-.07,.12,.36,.64,.97])
    for j,(cx,cy,rx,ry) in enumerate(patches):
        phase=float(rng_for(seed,identity+f'/patch-{j}').uniform(-.15,.15))
        region=affinity.scale(Point(cx,cy).buffer(1,quad_segs=32),rx,ry)
        regions.append(region)
        # White paper within the patch stays distinct from the corridor.
        white=affinity.scale(Point(cx+rx*.40,cy-ry*.25).buffer(1,quad_segs=24),rx*.20,ry*.37)
        color=region.intersection(affinity.scale(Point(cx-rx*.18,cy+ry*.25).buffer(1,quad_segs=24),rx*.66,ry*.56)).difference(white)
        if corridor is not None:color=color.difference(corridor.geometry)
        pigment.append(color)
        for i,z in enumerate(offsets):
            extent=np.sqrt(max(.12,1-z*z*.83))
            # Staggered lengths, a shared terrain tangent and no base/upper
            # silhouette stop these marks reading as a bounded little platform.
            left=rx*extent*(.72+.15*np.sin(i*.79+j+phase))
            right=rx*extent*(.72+.18*np.cos(i*.73+j*.6+phase))
            xx=np.linspace(cx-left,cx+right,60)
            yy=cy+ry*z+sample(xx)-sample(cx)
            yy+=.12*ry*np.sin((xx-cx)/rx*.9+j*.4)*(1-z*z)
            xy=np.c_[xx,yy]
            geom=LineString(xy).intersection(region).difference(white)
            if corridor is not None:geom=geom.difference(corridor.geometry.buffer(.3))
            for k,g in enumerate(line_parts(geom)):
                if g.length<MINIMUM_MM:continue
                r=path_record(f'{identity}/patch-{j}/run-{i}/{k}',g.coords,identity,'ground-flow',.6,depth,'soil-ink')
                r.update(geometry_revision=VERSION,catalog_version=VERSION,generator_seed=seed,
                         surface_source_id=host_record['id'],patch_id=f'{identity}/patch-{j}',
                         semantic_opaque=False,ground_relief='surface-only; no raised mound',
                         geographic_depth_m=None,evidence='synthetic local ground-density interpretation')
                paths.append(r)
        metadata.append(dict(identity=f'{identity}/patch-{j}',center_mm=[cx,cy],radii_mm=[rx,ry],
                             source_host_id=host_record['id'],raised=False))
    support=unary_union(regions)
    if corridor is not None:support=support.difference(corridor.geometry)
    surface=Surface(identity,support,paths,[],False,depth,
        dict(version=VERSION,seed=seed,form='localized-ground-density',surface_source_id=host_record['id'],
             ground_relief='surface-only',patches=metadata,geographic_depth_m=None))
    # The local white supports are recorded for color/ink decisions separately.
    whites=unary_union([affinity.scale(Point(cx+rx*.40,cy-ry*.25).buffer(1,quad_segs=24),rx*.20,ry*.37)
                       for cx,cy,rx,ry in patches])
    return GroundStudy(surface,unary_union(pigment),whites,metadata)
