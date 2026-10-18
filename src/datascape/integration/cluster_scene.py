"""Catalog-only serial clusters on the immutable F2 surface, local study v02.

The baseline V placement is excluded in derived output, not deleted from source.
No generator in the accepted catalogs or v01 integration is modified.
"""
from copy import deepcopy
import hashlib
import numpy as np
from shapely.geometry import LineString,Point,box,GeometryCollection
from shapely.ops import unary_union
from datascape.integration.visibility import (SHAPE,adapt,contact,visibility_field,
    regions_from_tree,burn,signed_clearance,clip_source,behind_object,digest)
from datascape.integration.objects import supporting_surface,final_regions
from datascape.vegetation.tree_final_scale import make_tree,vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.ground.structural_detail_v05 import formation,FormationControls,base_mass,feature_detail
from datascape.ground.patch_system_v04 import PatchSpec,PatchControls,patch_system,host_function
from datascape.ground.material_review_v05 import ground_gradient
from datascape.ground.grammar import path_record
from datascape.rendering.rock_ground_catalog import place
from datascape.strokes.vector import sample


def q_sheet(site):
    row=site['source_forward_m']+np.clip((np.arange(600)+.5-site['xy_mm'][0])*site['lateral_q_per_mm'],-35,35)
    return np.broadcast_to(row[None,:],SHAPE)


def compact_regions(reg):
    for key in ('soft','occupancy'):
        if key in reg:reg[key]=reg[key].astype('float32')
    return reg


def catalog_seed(seed,key):
    token=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)
    return (seed+token)%(2**32-1)


def pose_tree(tree,flow):
    """Rigid placement pose only; keep every native mark length and anatomy.

    Catalog seed selection cannot reverse a family with a fixed axis bias.
    Rotate the complete visible object and its mask metadata around its root,
    rather than editing leaf rays, skeleton members or catalog source code.
    """
    out=deepcopy(tree);root=np.asarray(out.root)
    axis=np.asarray(out.structure['axis_nodes_mm']);tip=axis[-1]-root
    current=np.degrees(np.arctan2(tip[0],-tip[1]));target=12.*flow
    degrees=float(np.clip(target-current,-25.,25.));angle=np.radians(degrees)
    rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    def points(p):return (np.asarray(p)-root)@rot.T+root
    for m in out.marks:m.xy=points(m.xy)
    for lobe in out.lobes:
        lobe['center']=points(lobe['center']);lobe['angle']+=angle
    for key in ['axis_nodes_mm','branch_terminals_mm']:
        out.structure[key]=points(out.structure[key]).tolist()
    out.structure['members']={k:points(p).tolist() for k,p in out.structure['members'].items()}
    for item in out.structure['terminal_behavior']:
        item['tip_mm']=points(item['tip_mm']).tolist()
        item['end_tangent_xy']=(np.asarray(item['end_tangent_xy'])@rot.T).tolist()
        item['downward_tangent']=bool(item['end_tangent_xy'][1]>0)
    out.structure['integration_rigid_pose_deg']=degrees
    tip=np.asarray(out.structure['axis_nodes_mm'])[-1]-root
    return out,degrees,float(tip[0]/out.height)


def bounds_of(records,pad=12):
    if not records:return (0,0,0,0)
    p=np.concatenate([r['xy_mm'] for r in records]);lo=p.min(axis=0)-pad;hi=p.max(axis=0)+pad
    return (*lo,*hi)


def intersects(a,b):
    return a[0]<=b[2] and a[2]>=b[0] and a[1]<=b[3] and a[3]>=b[1]


def initialize(obj,fixed,corridor,ground=False):
    if ground:
        obj['q']=fixed['base']['depth_m']
        ret=np.asarray(fixed['retention']);visible=fixed['base']['occupied']
        obj['depth_provider']='actual-visible-F2-ground-surface'
    else:
        obj['q']=q_sheet(obj['site']);ret,visible=visibility_field(fixed,obj['q'])
        obj['depth_provider']='bounded-upright-F2-contact-sheet'
    obj['retention']=ret.astype('float32')
    obj['visible']=visible&(ret>.20)&~burn(corridor)&(fixed['refined']['global_retention']>0)
    if obj['kind']=='tree':obj['regions']=compact_regions(regions_from_tree(obj['tree'],obj['visible']))
    else:
        body=burn(obj['support'])&obj['visible'] if obj['kind']=='rock' else np.zeros(SHAPE,bool)
        obj['regions']=dict(body=body,soft=np.zeros(SHAPE,dtype='float32'))
    obj['body_distance']=signed_clearance(obj['regions']['body']).astype('float32')
    obj['bounds']=bounds_of(obj['records'])
    return obj


def create_objects(fixed,baseline,c,level,corridor):
    objects=[];sites=[];hosts={};cluster_notes=[]
    for group in c['clusters']:
        gid=group['id'];center=group['center_mm'];span=group['span_mm']
        host,offset,basis=supporting_surface(fixed,baseline,dict(key=gid,target_mm=center,width_mm=max(group['rock_width_mm'],span)*1.15))
        hosts[gid]=host;hf=host_function(host);trees=[]
        count=group['clean_members'] if level=='clean' else group['members']
        for i,spec in enumerate(c['member_template'][:count]):
            ident=f'spring-cluster-v02/tree/{gid}/{spec["key"]}'
            flow=group['flow'] if i!=2 else -group['flow']
            x=center[0]+spec['u']*span;y=float(hf(x))+spec['v_mm']
            root=[float(x),float(y)];site=contact(fixed,root)
            height=max(22,round(group['height_mm']*spec['size']))
            seed=catalog_seed(c['seed'],ident)
            tree=make_tree(spec['form'],root=root,height=height,seed=seed,identity=ident,
                posture=spec['posture'] if group['flow'] else 'upright',
                profile='v09' if spec['form']=='U' else 'refined',
                growth_controls=GrowthControls(stem_ratio=.9,vigor=1.))
            canonical=vector_records(tree.marks,[tree])
            tree,pose,lean=pose_tree(tree,flow)
            raw=vector_records(tree.marks,[tree]);records=[adapt(r,'new-catalog',ident,'tree') for r in raw]
            for r in records:r.update(layer='tree-ink',assumed_footprint_mm=.8,
                source_root_xyz_m=site['source_xyz_utm_m'],source_object_depth_m=site['source_forward_m'],
                catalog_entry='vegetation.tree_final_scale.make_tree',catalog_version='v10',
                placement_basis='new serial cluster on exact F2 contact; not observed vegetation',
                group_id=gid,cluster_role=spec['role'])
            obj=dict(id=ident,kind='tree',tree=tree,records=records,site=site,group=gid,
                height_mm=height,form=spec['form'],flow=flow,contact_rank=-spec['v_mm'],
                seed=seed,pose_rotation_deg=pose,axis_lean_ratio=lean,
                raw_catalog_sha256=digest(canonical),role=spec['role'])
            objects.append(initialize(obj,fixed,corridor));trees.append(obj)
            sites.append(dict(object_id=ident,kind='tree',group=gid,role=spec['role'],form=spec['form'],
                height_mm=height,flow=flow,axis_lean_ratio=lean,seed=seed,site=site,
                host_id=host['id'],host_basis=basis,pose_rotation_deg=pose,catalog_sha256=digest(canonical),posed_vector_sha256=digest(raw)))
        # Main/subordinate/scatter masses share a parent field and cluster host.
        rx=center[0]+(group['flow'] or -1)*16;ry=float(hf(rx))+3
        rock_id='spring-cluster-v02/rock/'+gid
        if group['rock_count']>1:
            masses=place(formation(rock_id,FormationControls(width_mm=group['rock_width_mm'],
                height_mm=group['rock_height_mm'],major_count=group['rock_count'],seed=c['seed'])),rx,ry)
        else:
            masses=[base_mass(rock_id+'/main',group['rock_width_mm'],group['rock_height_mm'],
                form='compact' if gid=='upper-right' else 'angular',regime='rounded' if gid=='upper-right' else 'layered',
                anchor=(rx,ry),seed=c['seed'],field_id=rock_id+'/parent-field')]
        scatter=[(-.51,.19),(.47,.24)] if level=='clean' else [(-.57,.13),(-.43,.21),(.48,.25),(.62,.11)]
        for j,(u,ratio) in enumerate(scatter):
            xx=rx+u*group['rock_width_mm'];yy=float(hf(xx))+5+(j%2)*2
            m=base_mass(rock_id+f'/scatter-{j}',max(9,group['rock_width_mm']*ratio),
                max(6,group['rock_height_mm']*ratio*.9),form='compact' if j%2 else 'angular',
                regime='rounded' if j%2 else 'layered',anchor=(xx,yy),seed=c['seed'],field_id=rock_id+'/parent-field')
            masses.append(m)
        detailed=[]
        for m in masses:
            refined,_,_=feature_detail(m);detailed.append(refined)
            ident=m.surface.identity;site=contact(fixed,m.surface.info['anchor_mm'])
            records=[adapt(r,'new-catalog',ident,'rock') for r in refined.surface.paths]
            for r in records:r.update(assumed_footprint_mm=.65,parent_mass_id=rock_id+'/parent',
                catalog_entry='ground.structural_detail_v05',catalog_version='v05',
                source_object_depth_m=site['source_forward_m'],group_id=gid,
                geological_evidence='authored catalog mass, not observed local geology')
            obj=dict(id=ident,kind='rock',records=records,site=site,group=gid,
                support=refined.surface.support,parent_mass_id=rock_id+'/parent',catalog_local_rank=m.surface.depth,
                role='scatter' if '/scatter-' in ident else 'main exposure')
            objects.append(initialize(obj,fixed,corridor))
            sites.append(dict(object_id=ident,kind='rock',group=gid,role=obj['role'],site=site,
                parent_mass_id=obj['parent_mass_id'],catalog_local_rank=m.surface.depth,host_id=host['id']))
        # Root contact carriers are nonplotting contact intent, not fake A paths.
        contact_carriers=[]
        for t in trees[:3]:
            x,y=t['site']['xy_mm'];pts=[[x-7,y+2],[x+7,y+2]]
            contact_carriers.append(path_record(t['id']+'/contact-carrier',pts,t['id'],'nonplotting-root-contact',depth=t['site']['source_forward_m']))
        area=group['soil_area_mm2'];x=center[0]
        specs=[PatchSpec('anchor-ground',x,8,area,aspect_ratio=4.2,irregularity=.24,density_tier=1),
               PatchSpec('serial-ground',x+span*.30,9,area*.40,aspect_ratio=3.,irregularity=.20),
               PatchSpec('dissolve-ground',x-span*.35,7,area*.22,aspect_ratio=2.7,irregularity=.25)]
        cross_candidates=[]
        for r in baseline:
            if r['layer']!='C':continue
            p=np.asarray(r['xy_mm']);delta=p[-1]-p[0]
            if abs(delta[0])<.08*max(np.linalg.norm(delta),1e-9):continue
            if delta[0]<0:p=p[::-1]
            cross_candidates.append((LineString(p).distance(Point(center)),r['id'],p))
        _,cross_id,cross_points=min(cross_candidates,key=lambda x:(x[0],x[1]))
        cross=dict(id=cross_id,xy_mm=cross_points.tolist())
        ground=patch_system('spring-cluster-v02/Soil/'+gid,host,specs,
            PatchControls(spacing_mm=4.0,directional_coherence=.55,edge_dissolution=.48,relation='connected',merge_gap_mm=1.5,pigment_enabled=False),
            whitespace=corridor,depth=0.,cross_flow_record=cross)
        ground,gradient,_=ground_gradient(ground,detailed,contact_carriers,reach_mm=9.)
        ident=ground.surface.identity;site=contact(fixed,[center[0],float(hf(center[0]))])
        records=[adapt(r,'new-catalog',ident,'Soil') for r in ground.surface.paths]
        for r in records:r.update(assumed_footprint_mm=.6,catalog_entry='ground.patch_system_v04 + ground_gradient v05',
            material_channel='structural-ink',surface_source_id=host['id'],group_id=gid,
            depth_provider='actual-visible-F2-ground-surface',semantic_opaque=False)
        obj=dict(id=ident,kind='soil',records=records,site=site,group=gid,support=ground.surface.support,
            host=host,gradient=gradient,role='root-rock ground carrier')
        objects.append(initialize(obj,fixed,corridor,ground=True))
        sites.append(dict(object_id=ident,kind='soil',group=gid,site=site,nonplotting_host=host,
            depth_provider=obj['depth_provider'],contact_carriers=[r['xy_mm'] for r in contact_carriers]))
        cluster_notes.append(dict(group_id=gid,trees=len(trees),rock_masses=len(masses),root_flow=group['flow'],
            heights_mm=[t['height_mm'] for t in trees],host_basis=basis,host_target_offset_mm=offset))
    return objects,sites,cluster_notes


def behind(own,other,qa,qb):
    b=behind_object(own,other,qa,qb)
    if own['kind']==other['kind']=='tree' and own['group']==other['group']:
        b |= (np.abs(qa-qb)<=25)&(own['contact_rank']>other['contact_rank'])
    return b


def object_gate_v02(fixed,obj,peers):
    hard=signed_clearance(~obj['visible'])
    if '_v02_global_safe' not in fixed:fixed['_v02_global_safe']=signed_clearance(fixed['refined']['global_retention']<=0)
    global_safe=fixed['_v02_global_safe']
    def gate(xy,arc,r):
        width=r.get('assumed_footprint_mm',r['width_mm']);margin=width/2+.15+1.
        g=np.minimum(sample(hard,xy)-margin,sample(global_safe,xy)-margin)
        g=np.minimum.reduce([g,xy[:,0]-width/2,600-width/2-xy[:,0],898-width/2-xy[:,1]])
        ph=int(hashlib.sha256((r['id']+'/object-mist').encode()).hexdigest()[:8],16)/16**8
        threshold=.06+.40*(.5+.5*np.sin(arc/19+ph*2*np.pi))
        g=np.minimum(g,sample(obj['retention'],xy)-threshold);reasons=['locked-reserves','nearer-terrain','depth-matched-mist']
        qa=sample(obj['q'],xy)
        for other in peers:
            if obj['id']==other['id']:continue
            b=behind(obj,other,qa,sample(other['q'],xy))
            ph=int(hashlib.sha256((r['id']+'/'+other['id']).encode()).hexdigest()[:8],16)/16**8
            dg=np.minimum(sample(other['body_distance'],xy)-margin,.12+.78*ph-sample(other['regions']['soft'],xy))
            if np.any(b&(dg<0)):reasons.append('visible-object:'+other['id'])
            g=np.minimum(g,np.where(b,dg,1e6))
        return g,reasons
    return gate


def terrain_gate_v02(fixed,objects,replacements=()):
    def gate(xy,arc,r):
        q=sample(fixed['base']['depth_m'],xy);width=max(r.get('width_profile_mm',[r['width_mm']]))
        margin=width/2+.15+1.;g=np.full(len(xy),1e6);reasons=[]
        for obj in objects:
            delta=q-sample(obj['q'],xy);back=delta>25;equal=np.abs(delta)<=25
            body=sample(obj['body_distance'],xy)-margin
            ph=int(hashlib.sha256((r['id']+'/'+obj['id']).encode()).hexdigest()[:8],16)/16**8
            soft=.12+.78*ph+.08*np.sin(arc/17+ph*5)-sample(obj['regions']['soft'],xy)
            g=np.minimum(g,np.where(back|equal,body,1e6));g=np.minimum(g,np.where(back,soft,1e6))
            if np.any((back|equal)&(body<0)) or np.any(back&(soft<0)):reasons.append('occupied-core:'+obj['id'])
        if r['source_family'] in ('A','C'):
            for obj,region in replacements:
                from shapely import contains_xy
                hit=contains_xy(region,xy[:,0],xy[:,1])
                if hit.any():g=np.minimum(g,np.where(hit,-1.,1e6));reasons.append('local-Soil-duplicate-clearance:'+obj['id'])
        return g,reasons
    return gate


def resolve_clusters(fixed,baseline,c,level,corridor):
    objects,sites,notes=create_objects(fixed,baseline,c,level,corridor)
    print('Built',level,len(objects),'catalog objects',flush=True)
    initial={o['id']:o['regions']['body'].copy() for o in objects}
    for o in objects:
        for front in objects:
            if o['id']==front['id'] or not intersects(o['bounds'],front['bounds']):continue
            hidden=initial[front['id']]&behind(o,front,o['q'],front['q'])
            o['visible'] &= ~hidden;o['regions']['body'] &= ~hidden;o['regions']['soft'] *= ~hidden
        o['body_distance']=signed_clearance(o['regions']['body']).astype('float32')
    visible={};object_ledger=[]
    for o in objects:
        peers=[p for p in objects if intersects(o['bounds'],p['bounds'])]
        gate=object_gate_v02(fixed,o,peers);records=[]
        for r in o['records']:
            parts,a=clip_source(r,gate);records+=parts;object_ledger.append(a)
        visible[o['id']]=records
    for o in objects:
        final_regions(o,visible[o['id']]);compact_regions(o['regions'])
        o['body_distance']=o['body_distance'].astype('float32')
    # Only surviving Soil ink owns a small duplicate-clearance strip; no entire
    # patch erases A/C merely because a soil ownership region was declared.
    replacements=[]
    for o in objects:
        if o['kind']=='soil':
            footprint=unary_union([LineString(r['xy_mm']).buffer(.8) for r in visible[o['id']]])
            replacements.append((o,footprint))
    terrain=[];ledger=[]
    for s in baseline:
        r=adapt(s,'baseline','baseline/'+s['layer'],s['layer'])
        if s['layer']=='V':
            _,a=clip_source(r,force_reason='v02-remove-all-legacy-V-placement');ledger.append(a);continue
        bb=LineString(r['xy_mm']).bounds
        peers=[o for o in objects if intersects(bb,o['bounds'])]
        reps=[(o,g) for o,g in replacements if not g.is_empty and intersects(bb,g.bounds)]
        parts,a=clip_source(r,terrain_gate_v02(fixed,peers,reps));terrain+=parts;ledger.append(a)
    new=[r for o in sorted(objects,key=lambda o:o['id']) for r in visible[o['id']]]
    return dict(objects=objects,sites=sites,clusters=notes,terrain=terrain,new=new,
        ink=[r for r in terrain+new if r['source_family']!='C'],
        color_sources=[r for r in terrain if r['source_family']=='C'],
        terrain_ledger=ledger,object_ledger=object_ledger,new_sources=[r for o in objects for r in o['records']],
        visible_by_owner=visible,legacy_V_paths_removed=sum(r['layer']=='V' for r in baseline))
