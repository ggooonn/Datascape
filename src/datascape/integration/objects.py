"""Small accepted-catalog adapters with explicit F2 supporting-surface records."""
from copy import deepcopy
import numpy as np
from scipy.ndimage import binary_dilation
from shapely.geometry import LineString, Point, GeometryCollection
from shapely.ops import unary_union
from datascape.vegetation.tree_final_scale import make_tree,vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.vegetation.tree_catalog import Mark
from datascape.ground.structural_detail_v05 import formation,FormationControls,base_mass,feature_detail
from datascape.ground.patch_system_v04 import PatchSpec,PatchControls,patch_system,host_function
from datascape.ground.material_review_v05 import ground_gradient
from datascape.rendering.rock_ground_catalog import place
from datascape.integration.visibility import (SHAPE,contact,depth_field,visibility_field,
    regions_from_tree,signed_clearance,burn,adapt,digest)
from datascape.strokes.vector import sample


def supporting_a(records,xy,reach=25):
    candidates=[]
    for r in records:
        if r['layer']!='A':continue
        p=np.asarray(r['xy_mm']);dx=np.diff(p[:,0])
        if np.all(dx<0):p=p[::-1]
        elif not np.all(dx>0):continue
        if p[0,0]>xy[0]-reach or p[-1,0]<xy[0]+reach:continue
        yy=float(np.interp(xy[0],p[:,0],p[:,1]))
        candidates.append((abs(yy-xy[1]),r['id'],p,r))
    if not candidates:raise ValueError('No monotone original A support spans site')
    distance,_,points,source=min(candidates,key=lambda x:(x[0],x[1]))
    if distance>30:raise ValueError('A contact too far from target')
    return dict(id=source['id'],xy_mm=points.tolist()),distance


def supporting_surface(fixed,baseline,spec):
    xy=spec['target_mm'];reach=spec['width_mm']*.72
    try:
        host,distance=supporting_a(baseline,xy,reach=reach)
        if distance<=15:return host,distance,'existing monotone A arc'
    except ValueError:pass
    # An A gap is not license to extrapolate a short A fragment. Use an
    # explicitly nonplotting section of the actual visible F2 terrain at the
    # contact's source forward coordinate. No baseline stroke is generated.
    site=contact(fixed,xy);q=site['source_forward_m'];points=[]
    xx=np.linspace(max(.6,xy[0]-reach),min(599.4,xy[0]+reach),161)
    yy=np.linspace(max(.6,xy[1]-48),min(897.4,xy[1]+48),481)
    for x in xx:
        probes=np.c_[np.full(len(yy),x),yy]
        value=sample(fixed['base']['depth_m'],probes)-q
        occupied=sample(fixed['base']['occupied'].astype(float),probes)>.999
        candidates=[]
        for i in np.flatnonzero((value[:-1]*value[1:]<=0)&occupied[:-1]&occupied[1:]):
            a,b=value[i:i+2]
            y=yy[i]+(yy[i+1]-yy[i])*a/(a-b) if a!=b else yy[i]
            candidates.append(y)
        if not candidates:raise ValueError('Visible terrain section interrupted; choose another bounded site')
        points.append([float(x),float(min(candidates,key=lambda y:abs(y-xy[1])))])
    return dict(id='nonplotting/F2-source-q-section/'+spec['key'],xy_mm=points),0.,'visible source-q terrain section; nonplotting'


def build_objects(fixed,baseline,config,variant,corridor):
    objects=[];replace_v=set();patches=[];contacts=[]
    roots={r['source_root_id']:r for r in baseline if r['layer']=='V' and r.get('grammar_part')=='trunk'}
    for spec in config['trees']:
        if variant=='B' and spec['variant']=='C':continue
        old=roots[spec['root_id']];xy=old['source_root_xy_mm'];site=contact(fixed,xy)
        if abs(site['source_forward_m']-old['source_object_depth_m'])>1e-5:
            raise ValueError('Existing root/source q no longer matches fixed terrain')
        ident='spring-integration-v01/tree/'+spec['key']
        profile='v09' if spec['form']=='U' else 'refined'
        tree=make_tree(spec['form'],root=xy,height=spec['height_mm'],seed=config['seed'],identity=ident,
                       profile=profile,growth_controls=GrowthControls(stem_ratio=.9,vigor=1.))
        raw=vector_records(tree.marks,[tree])
        recs=[adapt(r,'new-catalog',ident,'tree') for r in raw]
        for r in recs:
            r.update(layer='tree-ink',assumed_footprint_mm=.8,source_root_xyz_m=site['source_xyz_utm_m'],
                     placement_basis='exact F2 triangle contact; authored upright 2.5D object',
                     source_object_depth_m=site['source_forward_m'],scene_integration_status='diagnostic-v01',
                     ground_visibility_status='selected support; pictorial acceptance pending')
        q=depth_field(site);ret,visible=visibility_field(fixed,q)
        effective=visible&(ret>.25)&~burn(corridor)
        obj=dict(id=ident,kind='tree',tree=tree,records=recs,q=q,retention=ret,visible=effective,
                 site=site,group=spec['group'],replaces_root_id=spec['root_id'],
                 raw_catalog_sha256=digest(raw),height_mm=spec['height_mm'])
        obj['regions']=regions_from_tree(tree,effective)
        obj['body_distance']=signed_clearance(obj['regions']['body'])
        objects.append(obj);replace_v.add(spec['root_id'])
    for spec in config['rocks']:
        if variant=='B' and spec['variant']=='C':continue
        host,offset,host_basis=supporting_surface(fixed,baseline,spec)
        hf=host_function(host);x=spec['target_mm'][0];y=float(hf(x))
        ident='spring-integration-v01/rock/'+spec['key']
        ms=place(formation(ident,FormationControls(width_mm=spec['width_mm'],height_mm=spec['height_mm'],
                 major_count=spec['major_count'],seed=config['seed'])),x,y)
        # Regenerate each smaller child at its own physical dimensions, sharing
        # the larger formation's parent. No scaled finished-path copies.
        for side,ratio in [(-1,.16),(1,.21)]:
            xx=x+side*spec['width_mm']*.49;yy=float(hf(xx))
            child=base_mass(ident+f'/stone-{side}',spec['width_mm']*ratio,
                max(7,spec['height_mm']*.27),'compact' if side<0 else 'angular',
                'rounded' if side<0 else 'layered',anchor=(xx,yy),seed=config['seed'],
                field_id=ident+'/parent-field')
            child.parent_id=ident+'/parent';ms.append(child)
        placed=[]
        for m in ms:
            refined,_,_=feature_detail(m);placed.append(refined)
            anchor=m.surface.info['anchor_mm'];site=contact(fixed,anchor)
            q=depth_field(site);ret,visible=visibility_field(fixed,q)
            body=burn(refined.surface.support)&visible&(ret>.25)&~burn(corridor)
            recs=[adapt(r,'new-catalog',m.surface.identity,'rock') for r in refined.surface.paths]
            for r in recs:
                r.update(assumed_footprint_mm=.65,parent_mass_id=ident+'/parent',
                         synthetic=True,geographic_depth_m=site['source_forward_m'],
                         depth_provider='F2-support-relative-2.5D-v01',depth_units='source forward meters',
                         forward_depth=site['source_forward_m'],
                         geological_evidence='authored rock; no observed geology at contact',
                         placement_uncertainty='upright 2.5D; local rock overhang depth unresolved')
            obj=dict(id=m.surface.identity,kind='rock',records=recs,q=q,retention=ret,
                     visible=visible&(ret>.25)&~burn(corridor),site=site,group=spec['group'],
                     regions=dict(body=body,soft=np.zeros(SHAPE)),support=refined.surface.support,
                     parent_mass_id=ident+'/parent',catalog_local_rank=m.surface.depth,host_source_id=host['id'],host_basis=host_basis)
            obj['body_distance']=signed_clearance(body);objects.append(obj)
            host_y=float(hf(anchor[0]));contacts.append(dict(object_id=obj['id'],
                source_id=host['id'],source_arc_mm=float(LineString(host['xy_mm']).project(Point(anchor[0],host_y))),
                anchor_xy_mm=anchor,host_xy_mm=[anchor[0],host_y],vertical_offset_mm=float(anchor[1]-host_y),
                status='authored partial burial; review signed offset'))
        site=contact(fixed,[x,y]);q=depth_field(site);ret,visible=visibility_field(fixed,q)
        area=spec['width_mm']*6.2
        specs=[PatchSpec('parent-contact',x,3,area,aspect_ratio=4.2,irregularity=.23),
               PatchSpec('satellite-contact',x+spec['width_mm']*.36,2,area*.24,aspect_ratio=2.5)]
        # Do not extrapolate the actual A host into a patch. Clip ownership to its
        # real x domain and reject global/mist/corridor cells before plotting.
        from rasterio.features import shapes
        allowed=(fixed['retention']>.18)&(fixed['refined']['global_retention']>0)&visible
        from shapely.geometry import shape,box
        reserve=unary_union([shape(g) for g,v in shapes((~allowed).astype('uint8'),mask=~allowed) if v])
        ground=patch_system(ident+'/soil',host,specs,PatchControls(spacing_mm=3.8,
             edge_dissolution=.45,relation='connected',merge_gap_mm=1.5),
             whitespace=reserve.union(corridor),depth=site['source_forward_m'])
        p=np.asarray(host['xy_mm']);domain=box(p[0,0],0,p[-1,0],898)
        ground.surface.support=ground.surface.support.intersection(domain)
        ground.pigment_support=ground.pigment_support.intersection(domain)
        ground,ga,_=ground_gradient(ground,placed,reach_mm=6.)
        recs=[adapt(r,'new-catalog',ident+'/soil','Soil') for r in ground.surface.paths
              if LineString(r['xy_mm']).within(domain)]
        for r in recs:r.update(assumed_footprint_mm=.6,material_channel='structural-ink',
             depth_provider='F2-support-relative-2.5D-v01',forward_depth=site['source_forward_m'])
        soil=dict(id=ident+'/soil',kind='soil',records=recs,q=q,retention=ret,
             visible=visible,site=site,group=spec['group'],support=ground.surface.support,
             pigment=ground.pigment_support,host_source_id=host['id'],host_distance_mm=offset,host_basis=host_basis,
             regions=dict(body=np.zeros(SHAPE,bool),soft=np.zeros(SHAPE)),gradient=ga,host=host)
        soil['body_distance']=signed_clearance(soil['regions']['body'])
        objects.append(soil);patches.append((soil,ground.surface.support))
    return objects,replace_v,patches,contacts


def final_regions(obj,visible_records):
    """Masks come from retained visible marks; hidden rear ink cannot erase."""
    if obj['kind']=='tree':
        tree=deepcopy(obj['tree'])
        tree.marks=[Mark(r['id'],np.asarray(r['xy_mm']),r['width_mm'],r['grammar_part'],
                         owner=obj['id']) for r in visible_records]
        initial=obj['regions']
        reg=regions_from_tree(tree,obj['visible'])
        reg['v10']=initial['v10']&obj['visible']
        reg['full']=initial['full']&obj['visible']
        structural=[LineString(r['xy_mm']).buffer(max(.8,obj['height_mm']*.024))
                    for r in visible_records if r['grammar_part']!='foliage-field']
        reg['body'] &= burn(unary_union(structural)) if structural else False
        obj['regions']=reg
    elif obj['kind']=='rock':
        # A solid can have an intentionally open contour. Preserve its semantic
        # body only in visible terrain/object cells, never in a hidden rear part.
        if not visible_records:obj['regions']['body'][:]=False
    obj['body_distance']=signed_clearance(obj['regions']['body'])
