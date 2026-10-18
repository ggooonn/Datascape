"""Reversible v03 scene integration: authored relationships on immutable F2 data.

Accepted object catalogs are called at native dimensions. Far representation
selects complete catalog marks; it never shrinks finished glyphs or invents a
species map. Ordinal contact ranks are bounded to equal-depth local groups.
"""
from copy import deepcopy
import hashlib
import numpy as np
from shapely.geometry import LineString,Point,GeometryCollection,box
from shapely.ops import unary_union
from datascape.integration.cluster_scene import (initialize,compact_regions,catalog_seed,
    pose_tree,intersects,terrain_gate_v02)
from datascape.integration.visibility import (adapt,contact,burn,signed_clearance,clip_source,
    digest,regions_from_tree)
from datascape.integration.objects import supporting_surface,final_regions
from datascape.vegetation.tree_final_scale import make_tree,vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.ground.structural_detail_v05 import formation,FormationControls,base_mass,feature_detail
from datascape.ground.patch_system_v04 import PatchSpec,PatchControls,patch_system,host_function
from datascape.ground.material_review_v05 import ground_gradient
from datascape.ground.grammar import path_record
from datascape.rendering.rock_ground_catalog import place
from datascape.strokes.vector import sample


def behind_v03(own,other,qa,qb):
    back=qa>qb+25.
    if own['group']==other['group']:
        # Explicit reciprocal composition intent, only in the uncertainty band.
        a=(own.get('overlap_rank',0),own.get('local_rank',0),own['id'])
        b=(other.get('overlap_rank',0),other.get('local_rank',0),other['id'])
        back |= (np.abs(qa-qb)<=25.) & (a>b)
    return back


def object_gate_v03(fixed,obj,peers):
    if 'visible_clearance' not in obj:obj['visible_clearance']=signed_clearance(~obj['visible']).astype('float32')
    if '_v03_global_safe' not in fixed:fixed['_v03_global_safe']=signed_clearance(fixed['refined']['global_retention']<=0)
    def gate(xy,arc,r):
        width=r.get('assumed_footprint_mm',r['width_mm']);margin=width/2+1.15
        g=np.minimum(sample(obj['visible_clearance'],xy)-margin,sample(fixed['_v03_global_safe'],xy)-margin)
        g=np.minimum.reduce([g,xy[:,0]-width/2,600-width/2-xy[:,0],898-width/2-xy[:,1]])
        ph=int(hashlib.sha256((r['id']+'/object-mist').encode()).hexdigest()[:8],16)/16**8
        threshold=.06+.40*(.5+.5*np.sin(arc/19+ph*2*np.pi))
        g=np.minimum(g,sample(obj['retention'],xy)-threshold)
        reasons=['locked-reserves','source-q-terrain','depth-matched-mist'];qa=sample(obj['q'],xy)
        for other in peers:
            if other['id']==obj['id']:continue
            back=behind_v03(obj,other,qa,sample(other['q'],xy))
            if not back.any():continue
            ph=int(hashlib.sha256((r['id']+'/'+other['id']).encode()).hexdigest()[:8],16)/16**8
            dg=np.minimum(sample(other['body_distance'],xy)-margin,.12+.78*ph-sample(other['regions']['soft'],xy))
            if np.any(back&(dg<0)):reasons.append('visible-object:'+other['id'])
            g=np.minimum(g,np.where(back,dg,1e6))
        return g,reasons
    return gate


def representation_records(tree,records,role):
    """Select exact catalog strokes for scene LOD, without changing the catalog."""
    if role=='full':return records
    chosen=[]
    for r in records:
        part=r['grammar_part'];key=r.get('component_key',r['id'])
        if role=='aggregate':
            # At v10's native 20-mm floor the canopy is shown as an aggregate;
            # no repeated miniature trunk silhouette is enlarged into a symbol.
            keep=part=='foliage-field' or (part=='branch-contour' and '/0' in key)
        else:
            keep=part not in ('bark','bark-detail','trunk-detail','collar-accent')
        if keep:chosen.append(r)
    return chosen


def add_metadata(records,ident,kind,site,group,role):
    result=[adapt(r,'new-catalog',ident,kind) for r in records]
    for r in result:r.update(group_id=group['id'],composition_role=group['role'],representation=group['representation'],
        source_object_depth_m=site['source_forward_m'],source_root_xyz_m=site['source_xyz_utm_m'],
        placement_basis='authored relationship; contact on exact F2 terrain; no observed species/geology claim',
        catalog_version='v10' if kind=='tree' else 'v05',assumed_footprint_mm=.8 if kind=='tree' else .65 if kind=='rock' else .6)
    return result


def finish_object(obj,fixed,corridor):
    initialize(obj,fixed,corridor,ground=obj['kind']=='soil')
    obj['visible_clearance']=signed_clearance(~obj['visible']).astype('float32')
    return obj


def group_host(fixed,baseline,g):
    width=max([g['span_mm']]+[s['width_mm'] for s in g['rocks']])
    return supporting_surface(fixed,baseline,dict(key=g['id'],target_mm=g['center_mm'],width_mm=width))


def create_diverse_objects(fixed,baseline,config,corridor):
    objects=[];sites=[];notes=[]
    for g in config['groups']:
        gid=g['id'];cx,cy=g['center_mm'];host,offset,basis=group_host(fixed,baseline,g);hf=host_function(host)
        trees=[];rocks=[];start=len(objects)
        for s in g['trees']:
            ident=f'v03/tree/{gid}/{s["key"]}';x=cx+s['x_offset_mm'];y=float(hf(x))+s['host_offset_mm']
            site=contact(fixed,[x,y]);seed=catalog_seed(config['seed'],ident)
            tree=make_tree(s['form'],root=[x,y],height=s['height_mm'],seed=seed,identity=ident,
                posture=s['posture'],profile='v09' if s['form']=='U' else 'refined',
                growth_controls=GrowthControls(stem_ratio=s['stem_ratio'],vigor=s['vigor']))
            native=vector_records(tree.marks,[tree]);canonical_hash=digest(native)
            tree,pose,lean=pose_tree(tree,s['flow']);posed=vector_records(tree.marks,[tree])
            selected=representation_records(tree,posed,g['representation'])
            retained={r['component_key'] for r in selected}
            # Mask occupancy follows the exact same selected marks as the ink.
            tree.marks=[m for m in tree.marks if m.key in retained]
            records=add_metadata(selected,ident,'tree',site,g,s['key'])
            obj=dict(id=ident,kind='tree',tree=tree,records=records,site=site,group=gid,
                composition_role=g['role'],representation=g['representation'],height_mm=s['height_mm'],
                form=s['form'],flow=s['flow'],overlap_rank=s['overlap_rank'],local_rank=0.,seed=seed,
                pose_rotation_deg=pose,axis_lean_ratio=lean,role=s['key'],raw_catalog_sha256=canonical_hash,
                native_paths=len(posed),selected_paths=len(selected))
            objects.append(finish_object(obj,fixed,corridor));trees.append(obj)
            sites.append(dict(object_id=ident,kind='tree',group=gid,role=g['role'],member=s['key'],
                representation=g['representation'],height_mm=s['height_mm'],site=site,flow=s['flow'],
                overlap_rank=s['overlap_rank'],native_catalog_sha256=canonical_hash,
                pose_rotation_deg=pose,host_id=host['id'],host_basis=basis,
                native_paths=len(posed),selected_paths=len(selected),data_evidence='DEM depth/contact only; authored planting'))
        for s in g['rocks']:
            rid=f'v03/rock/{gid}/{s["key"]}';rx=cx+s['x_offset_mm'];ry=float(hf(rx))+s['host_offset_mm']
            if s['count']>1:
                masses=place(formation(rid,FormationControls(width_mm=s['width_mm'],height_mm=s['height_mm'],
                    major_count=s['count'],burial=s['burial'],seed=catalog_seed(config['seed'],rid))),rx,ry)
            else:
                masses=[base_mass(rid,s['width_mm'],s['height_mm'],s['form'],s['regime'],anchor=(rx,ry),
                    seed=catalog_seed(config['seed'],rid),field_id='v03/rock/'+gid+'/parent-field',burial=s['burial'])]
            for m in masses:
                refined,_,detail=feature_detail(m);rocks.append(refined);ident=m.surface.identity
                site=contact(fixed,m.surface.info['anchor_mm'])
                records=add_metadata(refined.surface.paths,ident,'rock',site,g,s['key'])
                for r in records:r.update(parent_mass_id=rid+'/parent',structural_field_id=m.field.identity)
                obj=dict(id=ident,kind='rock',records=records,site=site,group=gid,support=refined.surface.support,
                    composition_role=g['role'],representation=g['representation'],role=s['key'],
                    overlap_rank=s['overlap_rank'],local_rank=m.surface.depth,
                    parent_mass_id=rid+'/parent',catalog_local_rank=m.surface.depth,
                    field_tangent=m.field.tangent.tolist(),field_regime=m.field.regime,
                    feature_sources=[f['source_id'] for f in detail['features']],native_width_mm=s['width_mm'],
                    native_height_mm=s['height_mm'],host=host)
                objects.append(finish_object(obj,fixed,corridor))
                sites.append(dict(object_id=ident,kind='rock',group=gid,role=g['role'],member=s['key'],site=site,
                    support_bounds_mm=list(m.surface.support.bounds),overlap_rank=s['overlap_rank'],
                    local_rank=m.surface.depth,parent_mass_id=rid+'/parent',host_id=host['id'],
                    burial_fraction=s['burial'],field_regime=m.field.regime))
        if g['soils']:
            specs=[PatchSpec(s['key'],cx+s['x_offset_mm'],s['host_offset_mm'],s['area_mm2'],
                aspect_ratio=4.0 if j==0 else 3.1,irregularity=.25,density_tier=s['density_tier'],family_phase=.3+j*.8)
                for j,s in enumerate(g['soils'])]
            cs=[]
            for r in baseline:
                if r['layer']!='C':continue
                p=np.asarray(r['xy_mm']);delta=p[-1]-p[0]
                if abs(delta[0])<.08*max(np.linalg.norm(delta),1e-9):continue
                if delta[0]<0:p=p[::-1]
                cs.append((LineString(p).distance(Point(cx,cy)),r['id'],p))
            _,cross_id,cross=min(cs,key=lambda x:(x[0],x[1]))
            ground=patch_system('v03/Soil/'+gid,host,specs,
                PatchControls(spacing_mm=3.8,directional_coherence=.5,edge_dissolution=.48,relation='shared',
                    merge_gap_mm=1.5,pigment_enabled=False),whitespace=corridor,
                    cross_flow_record=dict(id=cross_id,xy_mm=cross.tolist()))
            carriers=[path_record(t['id']+'/contact',[[t['site']['xy_mm'][0]-5,t['site']['xy_mm'][1]+1],
                [t['site']['xy_mm'][0]+5,t['site']['xy_mm'][1]+1]],t['id'],'nonplotting-root-contact') for t in trees]
            ground,gradient,_=ground_gradient(ground,rocks,carriers,reach_mm=8.)
            ident=ground.surface.identity;site=contact(fixed,[cx,float(hf(cx))]);records=add_metadata(ground.surface.paths,ident,'Soil',site,g,'ground')
            obj=dict(id=ident,kind='soil',records=records,site=site,group=gid,support=ground.surface.support,
                host=host,gradient=gradient,role='selective-support',composition_role=g['role'],
                representation=g['representation'],overlap_rank=20,local_rank=0.,
                color_expansion=g['color_support_expansion'],cross_flow_source_id=cross_id)
            objects.append(finish_object(obj,fixed,corridor))
            sites.append(dict(object_id=ident,kind='soil',group=gid,role=g['role'],site=site,
                support_area_mm2=ground.surface.support.area,host_id=host['id'],cross_flow_source_id=cross_id,
                nonplotting_host=host,color_support_expansion=g['color_support_expansion']))
        notes.append(dict(group_id=gid,role=g['role'],representation=g['representation'],host_basis=basis,
            host_target_offset_mm=offset,trees=len(trees),rocks=len(rocks),soils=bool(g['soils']),
            object_count=len(objects)-start,center_mm=g['center_mm'],span_mm=g['span_mm']))
        print('Built',gid,'objects',len(objects)-start,flush=True)
    return objects,sites,notes


def resolve_diverse(fixed,baseline,config,corridor,_prepared=None):
    if _prepared is None:objects,sites,notes=create_diverse_objects(fixed,baseline,config,corridor)
    else:
        objects,sites,notes=_prepared
        for o in objects:finish_object(o,fixed,corridor)
    initial={o['id']:o['regions']['body'].copy() for o in objects}
    for o in objects:
        for other in objects:
            if o['id']==other['id'] or not intersects(o['bounds'],other['bounds']):continue
            hidden=initial[other['id']]&behind_v03(o,other,o['q'],other['q'])
            o['visible'] &= ~hidden;o['regions']['body'] &= ~hidden;o['regions']['soft'] *= ~hidden
        o['body_distance']=signed_clearance(o['regions']['body']).astype('float32')
        o['visible_clearance']=signed_clearance(~o['visible']).astype('float32')
    visible={};object_ledger=[]
    for o in objects:
        peers=[p for p in objects if intersects(o['bounds'],p['bounds'])];gate=object_gate_v03(fixed,o,peers);records=[]
        for r in o['records']:
            parts,a=clip_source(r,gate);records+=parts;object_ledger.append(a)
        visible[o['id']]=records
    for o in objects:
        final_regions(o,visible[o['id']]);compact_regions(o['regions']);o['body_distance']=o['body_distance'].astype('float32')
    replacements=[]
    for o in objects:
        if o['kind']=='soil':replacements.append((o,unary_union([LineString(r['xy_mm']).buffer(.8) for r in visible[o['id']]])))
    terrain=[];ledger=[]
    for s in baseline:
        r=adapt(s,'baseline','baseline/'+s['layer'],s['layer'])
        if s['layer']=='V':
            _,a=clip_source(r,force_reason='v03-exclude-all-legacy-V');ledger.append(a);continue
        bb=LineString(r['xy_mm']).bounds;peers=[o for o in objects if intersects(bb,o['bounds'])]
        reps=[(o,g) for o,g in replacements if not g.is_empty and intersects(bb,g.bounds)]
        parts,a=clip_source(r,terrain_gate_v02(fixed,peers,reps));terrain+=parts;ledger.append(a)
    new=[r for o in sorted(objects,key=lambda o:o['id']) for r in visible[o['id']]]
    result=dict(objects=objects,sites=sites,clusters=notes,terrain=terrain,new=new,
        ink=[r for r in terrain+new if r['source_family']!='C'],color_sources=[r for r in terrain if r['source_family']=='C'],
        terrain_ledger=ledger,object_ledger=object_ledger,new_sources=[r for o in objects for r in o['records']],
        visible_by_owner=visible,legacy_V_paths_removed=sum(r['layer']=='V' for r in baseline))

    if _prepared is None:
        repairs=contact_repairs(fixed,baseline,config,corridor,result)
        if repairs:
            result=resolve_diverse(fixed,baseline,config,corridor,(objects,sites,notes))
        result['contact_repairs']=repairs
    return result


def contact_repairs(fixed,baseline,config,corridor,result):
    """Add catalog Soil only at exposed, unsupported root ends after clipping.

    Hidden rear roots and distant canopy aggregates do not get decorative
    patches. A failed contact may stay unresolved if locked mist removes it.
    """
    ground=[LineString(r['xy_mm']) for r in result['ink'] if r['source_family'] in ('A','rock','Soil')]
    repairs=[]
    for obj in sorted(result['objects'][:],key=lambda o:o['id']):
        if obj['kind']!='tree' or obj['representation']=='aggregate':continue
        root=Point(obj['site']['xy_mm']);disk=root.buffer(7)
        nearby=sum(line.intersection(disk).length for line in ground if line.distance(root)<7)
        exposed=any(LineString(r['xy_mm']).distance(root)<3 for r in result['visible_by_owner'][obj['id']] if r['grammar_part']!='foliage-field')
        if nearby>2 or not exposed:continue
        ident=obj['id']+'/root-contact-Soil';x,y=obj['site']['xy_mm']
        host,_,basis=supporting_surface(fixed,baseline,dict(key=ident,target_mm=[x,y],width_mm=30))
        hf=host_function(host);offset=y-float(hf(x))+3
        patch=patch_system(ident,host,[PatchSpec('exposed-root',x,offset,180 if obj['height_mm']>45 else 100,aspect_ratio=3.8,irregularity=.2,density_tier=1)],
            PatchControls(spacing_mm=3.3,directional_coherence=.6,edge_dissolution=.32,pigment_enabled=False),whitespace=corridor)
        carrier=path_record(ident+'/intent',[[x-5,y+1],[x+5,y+1]],obj['id'],'nonplotting-root-contact')
        patch,gradient,_=ground_gradient(patch,[],[carrier],reach_mm=7.)
        recs=[adapt(r,'new-catalog',ident,'Soil') for r in patch.surface.paths]
        for r in recs:r.update(group_id=obj['group'],catalog_version='v05',assumed_footprint_mm=.6,repair_for=obj['id'])
        soil=dict(id=ident,kind='soil',records=recs,site=contact(fixed,[x,y+2]),group=obj['group'],
            support=patch.surface.support,host=host,gradient=gradient,role='exposed-root-repair',
            composition_role=obj['composition_role'],representation=obj['representation'],
            overlap_rank=20,local_rank=0.,color_expansion=1.15,cross_flow_source_id=host['id'])
        result['objects'].append(finish_object(soil,fixed,corridor))
        result['sites'].append(dict(object_id=ident,kind='soil',group=obj['group'],role='exposed-root-repair',
            site=soil['site'],repair_for=obj['id'],host_id=host['id'],host_basis=basis,nonplotting_host=host))
        repairs.append(dict(tree_id=obj['id'],soil_id=ident,before_ground_length_within_7mm=nearby,
            exposed_root=True,method='native catalog patch on actual F2 support; no terrain/ink source edit'))
    return repairs
