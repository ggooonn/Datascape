"""Small native-mm review adapters; no historical study runners or scene loading."""
from copy import deepcopy
import hashlib,json
import numpy as np
from shapely.geometry import LineString
from datascape.ground.interaction import Region
from datascape.vegetation.tree_final_scale import make_tree,vector_records
from datascape.vegetation.tree_occlusion_proof import masks,MaskAssumptions

def tree_fixture(root=(31,76), height=45, identity='unchanged-v10-B45', depth=3.):
    tree=make_tree('B',root=root,height=height,seed=20261017,identity=identity,profile='refined')
    canonical=vector_records(tree.marks,[tree])
    digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    out=deepcopy(canonical)
    for r in out:
        r.update(owner_id=identity,layer='tree-ink',forward_depth=depth,
                 depth_provider='synthetic-local-rank-v1',geographic_depth_m=None,
                 source_stroke_id=r['id'],source_arc_mm=[0.,LineString(r['xy_mm']).length],
                 assumed_footprint_mm=.8)
    # masks() already adds receiver width/2 + edge. Track this explicitly,
    # so the common consumer never buffers the same allowance twice.
    a=MaskAssumptions(vegetation_width_mm=.8,terrain_width_mm=.6,edge_tolerance_mm=.15)
    m=masks(tree,a)
    body=Region(identity+'/solid',identity,m['body'],depth,'opaque-body',
                'legacy-v10-prebuffered',.45)
    canopy=Region(identity+'/canopy-v10',identity,m['canopy'],depth,'canopy-v10',
                  'legacy-v10-prebuffered',.45)
    return tree,out,[body,canopy],dict(identity=identity,height_mm=height,canonical_sha256=digest,
        canonical_paths=len(canonical),canonical_geometry_unchanged=True,
        preview_footprint_mm=.8,canonical_width_profiles_retained=True,
        masking='unchanged v10 footprint proof; canopy-core problem remains open')
def body_regions(masses):
    return [Region(m.surface.identity+'/body',m.surface.identity,m.surface.support,m.surface.depth,
                   boundary_ink_width_mm=.65) for m in masses if m.surface.opaque]

def _paths(masses): return [p for m in masses for p in m.surface.paths]

def _poly(points,attrs):
    return '<polyline points="'+' '.join(f'{x:.4f},{y:.4f}' for x,y in points)+'" '+attrs+'/>'

def _geometry(g,color='#aaa',dash='1.7 1',width=.18,fill='none'):
    if g.is_empty:return ''
    if g.geom_type=='Polygon':
        def coords(r):return ' '.join(f'{x:.4f},{y:.4f}' for x,y in r.coords)
        d=' '.join('M '+' L '.join(f'{x:.4f},{y:.4f}' for x,y in r.coords)+' Z' for r in [g.exterior,*g.interiors])
        return f'<path d="{d}" fill="{fill}" fill-rule="evenodd" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>'
    return ''.join(_geometry(p,color,dash,width,fill) for p in getattr(g,'geoms',[]))
