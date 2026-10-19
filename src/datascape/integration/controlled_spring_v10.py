"""Review-only variants from immutable v09 vectors and numeric F2 fields.

No catalog, camera, terrain ink, palette, machine file or baseline is edited.
Root-locked shape adapters vary existing catalog graphs; new small units use
the inherited R/S/U generators. New sites reference visible A support and
sample saved F2 fields; they do not claim recovered full triangle precision.
"""
from pathlib import Path
from copy import deepcopy
from collections import defaultdict, Counter
import argparse, json, hashlib
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from datascape.strokes.vector import read_vectors, sample, resample, phase
from datascape.integration.visibility import burn, signed_clearance, digest
from datascape.integration.local_refinement_v09 import load_inputs, cut, canopy_gate, coverage
from datascape.integration.landscape_depth_v08 import crown_units, vegetation_palette
from datascape.integration.spring_unified_v05 import normalize_rsu
from datascape.vegetation.territorial_mid_far_v04 import generate
from datascape.rendering.spring_macro_study import write_gz, width_envelope
from datascape.vegetation.tree_final_scale import make_tree, vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.integration.cluster_scene import catalog_seed, pose_tree, q_sheet
from datascape.integration.diverse_scene import representation_records, add_metadata
from datascape.integration.macro_wash import foliage_candidates

ROOT = Path(__file__).resolve().parents[3]
CHANNELS = ['A', 'C', 'rock_soil', 'gestures', 'trunk', 'RSU']


def load_baseline(path):
    return dict(ink=read_vectors(path/'case1_ink.json.gz')['strokes'],
                channels={k: read_vectors(path/f'case1_channel_{k}.json.gz')['strokes'] for k in CHANNELS})


def length(r):
    return float(np.linalg.norm(np.diff(r['xy_mm'], axis=0), axis=1).sum())


def root_warp(xy, root, height, sx=1., sy=1., lean=0., bend=0.):
    """Fix the lower root zone while adapting crown proportion and posture."""
    p = np.asarray(xy, float); root = np.asarray(root)
    d = p-root; t = np.clip(-d[:, 1]/max(height, 1.), 0., 1.3)
    lock = np.clip((t-.10)/.42, 0., 1.); lock = lock*lock*(3-2*lock)
    out = p.copy()
    out[:, 0] += lock*((sx-1)*d[:, 0]+height*(lean*t+bend*np.sin(np.pi*t)*t))
    out[:, 1] += lock*(sy-1)*d[:, 1]
    return out


def authored(r, xy, tag, params=None):
    out = deepcopy(r); ident = tag+'/'+r['id']
    out.update(id=ident, source_stroke_id=ident, xy_mm=np.asarray(xy).tolist(),
               source_arc_mm=[0., float(LineString(xy).length)],
               v10_parent_id=r['id'], v10_operation=tag,
               v10_parent_geometry_sha256=digest(r['xy_mm']))
    if params is not None: out['v10_shape_parameters'] = params
    return out


def owner(r):
    return r.get('grounding_tree_id') or r.get('owner_id', '')


def prepare_fields(fixed, inherited):
    reserve = unary_union([Polygon(s['vertices_mm']) for s in inherited['corridors']])
    return dict(global_clear=signed_clearance(fixed['refined']['global_retention']<=0),
                reserve_clear=signed_clearance(burn(reserve)))


def ground_gate(fields, fixed, r, margin=0.8):
    def gate(xy, arcs, rec):
        w=max(rec.get('width_profile_mm', [rec['width_mm']]))/2+margin
        good=np.minimum.reduce([sample(fields['global_clear'],xy)-w,
             sample(fields['reserve_clear'],xy)-w, sample(fixed['retention'],xy)-.075,
             xy[:,0]-w,600-w-xy[:,0],xy[:,1]-w,898-w-xy[:,1]])
        return good, ['unchanged-global-mist-and-reserves','v10-review-footprint']
    return gate


def A_displacement(case, fixed, fields, c):
    index={r['id']:r for r in case['ink']};out=[];stats=[];sources=[]
    for r in case['channels']['A']:
        refs=r.get('support_references',[]);host=next((index[x.get('visible_fragment_id',x.get('source_id'))] for x in refs if x.get('visible_fragment_id',x.get('source_id')) in index),None)
        if host is None:out.append(r);continue
        hp=resample(host['xy_mm'],.25);t=np.gradient(hp,axis=0);t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-9);n=np.c_[-t[:,1],t[:,0]]
        p=np.array(r['xy_mm']);_,ii=cKDTree(hp).query(p);normal=n[ii]
        signed=np.einsum('ij,ij->i',p-hp[ii],normal);sign=np.where(signed>=0,1.,-1.)
        add=np.clip(np.abs(signed)*c['A_extra_normal_fraction'],c['A_extra_normal_min_mm'],c['A_extra_normal_max_mm'])
        # Endpoint taper avoids an abrupt offset at neighboring episode ends.
        u=np.linspace(0,1,len(p));add*=.78+.22*np.sin(np.pi*u)
        delta=normal*(add*sign)[:,None];trial=p+delta
        gate=ground_gate(fields,fixed,r,0.25);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        # Preserve an inherited path if no positive displacement fits its existing opening.
        original,_=gate(p,arc,r);safe,_=gate(trial,arc,r);factor=np.where(safe>=np.minimum(original,0),1.,0.)
        for _ in range(2):factor=np.minimum(factor,np.convolve(np.pad(factor,(1,1),mode='edge'),[.25,.5,.25],mode='valid'))
        xy=p+delta*factor[:,None];r2=authored(r,xy,'v10/shared-A');r2['v10_added_displacement_mm']=np.linalg.norm(xy-p,axis=1).tolist()
        sources.append(r2);out.append(r2);stats.extend(np.linalg.norm(xy-p,axis=1).tolist())
    return out, dict(paths_changed=len(sources),point_extra_mean_mm=float(np.mean(stats)),point_extra_max_mm=float(max(stats))),sources


def shared_native_plans(context,c):
    plans={}
    for o in context['objects']:
        if o['kind']!='tree' or not c['mid_native_depth_range_m'][0]<=o['site']['source_forward_m']<=c['mid_native_depth_range_m'][1]:continue
        k=o['id'];u=phase(k+'/height',c['seed']);v=phase(k+'/width',c['seed'])
        plans[k]=dict(sx=float(np.interp(v,[0,1],c['native_width_scale_range'])),sy=float(np.interp(u,[0,1],c['native_height_scale_range'])),lean=(phase(k+'/lean',c['seed'])-.5)*.42,bend=(phase(k+'/shape',c['seed'])-.5)*.22,density=.72+.28*phase(k+'/density',c['seed']))
    return plans


def apply_native(case, context, plans, removed, tag, fields, fixed, sources, ledger):
    objects={o['id']:o for o in context['objects']};out=dict(ink=[],channels={k:[] for k in CHANNELS})
    for channel, rows in [('ink',case['ink'])]+list(case['channels'].items()):
        target=out['ink'] if channel=='ink' else out['channels'][channel]
        for r in rows:
            key=owner(r)
            if key in removed or any(key.startswith(x+'/root-contact-Soil') for x in removed):
                ledger.append(dict(parent_id=r['id'],operation=tag,decision='whole-object-removal'));continue
            if key not in plans or r.get('grounding_tree_id'):
                target.append(r);continue
            o=objects[key];p=plans[key];foliage=(r.get('grammar_part')=='foliage-field' or channel=='gestures')
            cohort=r.get('growth_branch_id',r.get('gesture_group',r.get('unit_id',r['id'])))
            if foliage and phase(cohort+'/v10-density',2026101901)>p.get('density',1.):
                ledger.append(dict(parent_id=r['id'],operation=tag,decision='selective-foliage-release'));continue
            xy=root_warp(r['xy_mm'],o['site']['xy_mm'],o['height_mm'],**{k:p[k] for k in ['sx','sy','lean','bend']})
            rr=authored(r,xy,tag,p);rr['source_forward_profile_m']=[o['site']['source_forward_m']]*len(xy)
            sources.append(rr)
            pieces,decision=cut(rr,ground_gate(fields,fixed,rr,.25),3.2 if 'palette_slot' in r else 2.8,tag+'-fixed-mist')
            target+=pieces;ledger.append(decision)
    return out


def native_masks(case,context,removed):
    by=defaultdict(list)
    for r in case['ink']+case['channels']['gestures']:by[r['owner_id']].append(r)
    trees=[]
    for old in context['objects']:
        if old['kind']!='tree' or old['id'] in removed:continue
        rows=by[old['id']];fol=[];body=[]
        for r in rows:
            if r.get('grammar_part')=='foliage-field' or 'palette_slot' in r:
                fol.append(width_envelope(r) if r.get('expressive_width_intent') else LineString(r['xy_mm']).buffer(max(r.get('width_profile_mm',[r['width_mm']]))/2))
            elif 'palette_slot' not in r:body.append(LineString(r['xy_mm']).buffer(max(r.get('width_profile_mm',[r['width_mm']]))/2+.65))
        if not rows:continue
        o=dict(old);shape=unary_union(fol);bod=unary_union(body);o['combined_occupancy']=gaussian_filter(burn(shape).astype('float32'),old['sigma_mm']);o['body_distance']=signed_clearance(burn(bod));o['bounds']=unary_union([shape,bod]).buffer(4).bounds;trees.append(o)
    return trees


def RSU_variation(case,c,sources,ledger):
    plans={};out=dict(ink=[],channels={k:list(v) for k,v in case['channels'].items()});out['channels']['RSU']=[]
    for channel,rows in [('ink',case['ink']),('RSU',case['channels']['RSU'])]:
        target=out['ink'] if channel=='ink' else out['channels']['RSU']
        for r in rows:
            if r['source_family']!='RSU' or not 650<=r.get('source_forward_m',0)<=3000 or 'root_xy_mm' not in r:
                target.append(r);continue
            key=r.get('source_member_ids',[r['owner_id']])[0];root=r['root_xy_mm'];q=r['source_forward_m'];h=float(np.interp(q,[650,3000],[29,11]))
            if key not in plans:
                plans[key]=dict(sx=float(np.interp(phase(key+'/width',c['seed']),[0,1],c['RSU_width_scale_range'])),sy=float(np.interp(phase(key+'/height',c['seed']),[0,1],c['RSU_height_scale_range'])),lean=(phase(key+'/lean',c['seed'])-.5)*.58,bend=(phase(key+'/shape',c['seed'])-.5)*.32,density=.76+.24*phase(key+'/density',c['seed']))
            pp=plans[key]
            if channel=='RSU' and phase(r['source_stroke_id']+'/density',c['seed'])>pp['density']:
                ledger.append(dict(parent_id=r['id'],operation='v10/shared-RSU',decision='local-density-release'));continue
            xy=root_warp(r['xy_mm'],root,h,**{k:pp[k] for k in ['sx','sy','lean','bend']});rr=authored(r,xy,'v10/shared-RSU',pp);sources.append(rr);target.append(rr)
    return out,plans


def new_sites(case,context,fixed,fields,c):
    candidates=[];support=[]
    for r in case['ink']:
        if r['source_family']!='A':continue
        p=resample(r['xy_mm'],5.7);q=sample(fixed['base']['depth_m'],p);keep=(q>=700)&(q<=3400)&(p[:,1]>345)&(p[:,1]<710)&(sample(fixed['retention'],p)>.21)&(sample(fields['reserve_clear'],p)>8)&(sample(fields['global_clear'],p)>10)
        for pt,qq in zip(p[keep],q[keep]):candidates.append([*pt,qq]);support.append(r['id'])
    pts=np.array(candidates);cells=defaultdict(list)
    for i,p in enumerate(pts):cells[(int(p[0]//c['new_field_cell_mm'][0]),int(p[1]//c['new_field_cell_mm'][1]))].append(i)
    sites=[];used=[];rocks=[o for o in context['objects'] if o['kind']=='rock'];near=cKDTree(np.array([o['site']['xy_mm'] for o in rocks]))
    for cell,indices in sorted(cells.items()):
        key=f'v10/field/{cell[0]}-{cell[1]}'
        if phase(key+'/open',c['seed'])<.22:continue
        pick=indices[int(phase(key+'/center',c['seed'])*len(indices))];center=pts[pick,:2]
        count=[1,2,3,4][min(3,int(phase(key+'/group',c['seed'])*4))]
        local=sorted(indices,key=lambda i:float(np.linalg.norm(pts[i,:2]-center)))
        chosen=[]
        for i in local:
            xy=pts[i,:2]
            if np.linalg.norm(xy-center)>19 or any(np.linalg.norm(xy-n)<4.8 for n in used):continue
            if any(sample(o['body_distance'],[xy])[0]<5 for o in context['objects']):continue
            chosen.append(i);used.append(xy)
            if len(chosen)>=count:break
        for j,i in enumerate(chosen):
            xy=pts[i,:2];q=float(pts[i,2]);ident=key+f'/unit-{j}';dist,rockindex=near.query(xy);role='rock-fringe' if dist<27 else 'isolated' if len(chosen)==1 else 'small-group'
            site=dict(xy_mm=xy.tolist(),source_forward_m=q,source_xyz_utm_m=[float(sample(fixed['base']['xyz'][:,:,k],[xy])[0]) for k in range(3)],exact_contact=False,depth_provider='saved-F2-1mm-sampled-fields',support_A_id=support[i],contact_method='point on unchanged visible A centerline; sampled source depth',crs='EPSG:32652')
            h=float(np.interp(q,[700,1700,3400],[23,16,8]))*(.65+.62*phase(ident+'/height',c['seed']))
            family=['R','S','U'][int(phase(ident+'/family',c['seed'])*3)]
            sites.append(dict(id=ident,stand_id=key,patch_id=key,stand_index=j,stand_role='subordinate',member_index=j,member_count=len(chosen),root_xy_mm=xy.tolist(),height_mm=h,form=['P','B','U'][j%3],site=site,guide_u=xy[0]/600,guide_source_id=support[i],tangent_xy=[1.,0.],family=family,mode='M2' if q<1700 else 'F1' if q<2700 else 'F2',zone_id=key,relationship=role,nearby_rock_id=rocks[int(rockindex)]['id'] if dist<27 else None))
    return sites


def generate_small(sites,c):
    mc=json.load(open(ROOT/'configs/experiments/mid_far_vegetation_v04.json'));mc={**json.load(open(ROOT/mc['v02_config'])),**mc};raw=[]
    for s in sites:
        graphs,ink,col,_=generate([s],s['mode'],s['family'],mc)
        if s['family']=='S':col,_=crown_units([s],graphs,mc,c)
        for r in ink+col:
            r=normalize_rsu(r);r.update(depth_provider='saved-F2-1mm-sampled-fields-with-visible-A-anchor',v10_new_site_id=s['id'],v10_relationship=s['relationship'],nearby_rock_id=s['nearby_rock_id'])
            if length(r)>=(3.2 if 'palette_slot' in r else 2.8):raw.append(r)
    col=vegetation_palette([r for r in raw if 'palette_slot' in r],c)
    return [r for r in raw if 'palette_slot' not in r]+col


def place_RSU(case,context,trees,fixed,fields,c,sources,ledger,composition=False):
    out=dict(ink=[],channels={k:list(v) for k,v in case['channels'].items()});out['channels']['RSU']=[]
    for channel,rows in [('ink',case['ink']),('RSU',case['channels']['RSU'])]:
        target=out['ink'] if channel=='ink' else out['channels']['RSU']
        for r in rows:
            if r['source_family']!='RSU':target.append(r);continue
            if not composition and not (r.get('v10_operation')=='v10/shared-RSU' or r.get('v10_new_site_id')):
                target.append(r);continue
            canopy=canopy_gate(trees,c,r);ground=ground_gate(fields,fixed,r,.6)
            line=LineString(r['xy_mm']);peers=[o for o in context['objects'] if o['kind']=='rock' and line.intersects(Polygon.from_bounds(*o['bounds']))]
            def gate(xy,arcs,rec):
                g,why=ground(xy,arcs,rec);cg,cr=canopy(xy,arcs,rec);g=np.minimum(g,cg)
                q=np.interp(arcs,np.r_[0,np.cumsum(np.linalg.norm(np.diff(rec['xy_mm'],axis=0),axis=1))],rec['source_forward_profile_m'])
                for o in peers:g=np.minimum(g,np.where(q>np.interp(xy[:,0],np.arange(600)+.5,o['q_row'])+25,sample(o['body_distance'],xy)-rec['assumed_footprint_mm']/2-.6,1e6))
                # Existing global mist and source order release rather than paint over distant terrain.
                g=np.minimum(g,np.where(sample(fixed['base']['occupied'],xy)>.5,sample(fixed['base']['depth_m'],xy)-q+35,1e6))
                return g,why+cr+['depth-ordered-rock-partial-masking']
            pieces,d=cut(r,gate,3.2 if channel=='RSU' else 2.8,'v10-RSU-existing-global-visibility');target+=pieces;ledger.append(d)
    return out


def composition_plans(context,option):
    plans={};removed=set()
    for o in context['objects']:
        if o['kind']!='tree':continue
        key=o['id'];p=dict(sx=1.,sy=1.,lean=0.,bend=0.,density=1.)
        if o['group']=='near-left-grove':
            if option==2:
                keep=['low-left','forward-shrub','dissolving-end','v07-grove-0','v07-grove-5','v07-grove-6']
                if key.rsplit('/',1)[-1] not in keep:removed.add(key);continue
                p.update(sx=.88,sy=.72,lean=.08,density=.78)
            else:
                keep=['low-left','forward-shrub','serial-end','v07-grove-1','v07-grove-4','v07-grove-6']
                if key.rsplit('/',1)[-1] not in keep:removed.add(key);continue
                p.update(sx=1.10,sy=.56,lean=.18,bend=.04,density=.82)
            plans[key]=p
        if key.endswith('near-right-exposure/behind-main'):
            p.update(sx=.78 if option==2 else .91,sy=1.45 if option==2 else 1.14,lean=-.12 if option==2 else -.06,density=.92);plans[key]=p
        if option==3 and ('left-step/' in key or 'left-bench-transition/' in key):
            p.update(sx=.90,sy=1.18 if 'left-bench' in key else 1.10,lean=.19,bend=-.04,density=.92);plans[key]=p
        if option==2 and 'left-bench-transition/' in key:
            p.update(sx=.94,sy=1.09,lean=.12,density=.96);plans[key]=p
    return plans,removed


def open_left_RSU(case,option,c,ledger):
    out=dict(ink=[],channels={k:list(v) for k,v in case['channels'].items()});out['channels']['RSU']=[]
    for channel,rows in [('ink',case['ink']),('RSU',case['channels']['RSU'])]:
        target=out['ink'] if channel=='ink' else out['channels']['RSU']
        for r in rows:
            root=r.get('root_xy_mm',[999,0]);key=r.get('source_member_ids',[r['owner_id']])[0]
            if r['source_family']=='RSU' and root[0]<270 and root[1]>745:
                rate=.29 if option==2 else .40
                if phase(key+'/left-opening',c['seed'])>rate:
                    ledger.append(dict(parent_id=r['id'],operation=f'v10_{option}',decision='left-foreground-unit-release'));continue
                if option==3:
                    rr=authored(r,root_warp(r['xy_mm'],root,42,sx=1.12,sy=.62,lean=.20),'v10_3/lower-left');target.append(rr);continue
            target.append(r)
    return out


def native_vertical(case,context,option,inherited,fields,fixed,sources,ledger):
    """Regenerate the changed catalog tree before occlusion, avoiding stretched
    fragments inherited from the shorter tree's already-clipped silhouette.
    """
    key='v03/tree/near-right-exposure/behind-main';o=next(x for x in context['objects'] if x['id']==key)
    group=next(g for g in inherited['groups'] if g['id']=='near-right-exposure');spec=next(s for s in group['trees'] if s['key']=='behind-main')
    height=155 if option==2 else 130;ident=f'v10_{option}/vertical-tree';site=o['site']
    tree=make_tree(spec['form'],root=site['xy_mm'],height=height,seed=catalog_seed(inherited['seed'],key),identity=key,posture='upright',profile='refined',growth_controls=GrowthControls(stem_ratio=spec['stem_ratio'],vigor=spec['vigor']))
    tree,_,_=pose_tree(tree,-.3 if option==2 else -.65)
    raw=add_metadata(representation_records(tree,vector_records(tree.marks,[tree]),group['representation']),key,'tree',site,group,'behind-main')
    obj=dict(id=key,tree=tree,group=group['id'],height_mm=height,q=q_sheet(site))
    color=list(foliage_candidates(fixed,obj,raw,inherited))
    for channel in case['channels']:case['channels'][channel]=[r for r in case['channels'][channel] if owner(r)!=key]
    case['ink']=[r for r in case['ink'] if owner(r)!=key]
    # The rooted tree stands behind the retained foreground rock. Its original
    # mapped root/depth are retained; visible portions respect real rock bodies.
    peers=[x for x in context['objects'] if x['kind']=='rock' and x['group']=='near-right-exposure']
    for r in raw+color:
        r=deepcopy(r);r['id']=ident+'/'+r['id'];r['source_stroke_id']=r['id'];r['source_arc_mm']=[0.,length(r)];r['source_forward_profile_m']=[site['source_forward_m']]*len(r['xy_mm']);r.update(v10_operation='native-catalog-vertical-regeneration',v10_catalog_height_mm=height,v10_replaces_owner=key)
        sources.append(r);basegate=ground_gate(fields,fixed,r,.25)
        def gate(xy,arcs,rec):
            g,why=basegate(xy,arcs,rec);w=max(rec.get('width_profile_mm',[rec['width_mm']]))/2+.55
            for rock in peers:g=np.minimum(g,sample(rock['body_distance'],xy)-w)
            return g,why+['rooted-catalog-tree-behind-existing-rock']
        pp,d=cut(r,gate,3.2 if 'palette_slot' in r else 2.8,'v10-native-vertical-rock-integration');ledger.append(d)
        if 'palette_slot' in r:case['channels']['gestures']+=pp
        else:case['ink']+=pp
    return case


def save_case(out,name,case):
    write_gz(out/f'{name}_ink.json.gz',dict(strokes=case['ink']))
    color=sum(case['channels'].values(),[]);write_gz(out/f'{name}_color.json.gz',dict(strokes=color))
    for k,rows in case['channels'].items():write_gz(out/f'{name}_channel_{k}.json.gz',dict(strokes=rows))


def run(control,inputs,output):
    output.mkdir(parents=True,exist_ok=False);c=json.load(open(ROOT/'configs/scenes/seoul_spring_controlled_v10.json'));oldc=json.load(open(control/'config.json'));context,fixed=load_inputs(inputs);fields=prepare_fields(fixed,oldc);base=load_baseline(control);sources=[];ledger=[]
    common=dict(ink=list(base['ink']),channels={k:list(v) for k,v in base['channels'].items()});common['channels']['A'],a_stats,aa=A_displacement(base,fixed,fields,c);sources+=aa;print('SHARED_A',a_stats,flush=True)
    native=shared_native_plans(context,c);common=apply_native(common,context,native,set(),'v10/shared-native',fields,fixed,sources,ledger)
    common,rsplans=RSU_variation(common,c,sources,ledger);sites=new_sites(base,context,fixed,fields,c);raw=generate_small(sites,c);sources+=raw;print('SHARED_VEGETATION',len(native),len(rsplans),len(sites),flush=True)
    common['ink'] += [r for r in raw if 'palette_slot' not in r];common['channels']['RSU'] += [r for r in raw if 'palette_slot' in r]
    common_unclipped=common;trees=native_masks(common,context,set());case1=place_RSU(common,context,trees,fixed,fields,c,sources,ledger);del trees
    cases={'baseline':base,'v10_1':case1};plans_record={};print('CASE v10_1',flush=True)
    for option in [2,3]:
        pp,removed=composition_plans(context,option);name=f'v10_{option}';local=[]
        # Reuse shared authored geometry; re-evaluate receiving vegetation after
        # the foreground occupancy changes, instead of retaining false holes.
        case=apply_native(common_unclipped,context,pp,removed,name+'/composition',fields,fixed,sources,local)
        case=open_left_RSU(case,option,c,local);case=native_vertical(case,context,option,oldc,fields,fixed,sources,local);tt=native_masks(case,context,removed);case=place_RSU(case,context,tt,fixed,fields,c,sources,local,composition=True);del tt;cases[name]=case
        for decision in local:decision['v10_case']=name
        plans_record[name]=dict(native_parameters=pp,removed_objects=sorted(removed),native_vertical_height_mm=155 if option==2 else 130);ledger+=local;print('CASE',name,flush=True)
    checks={};fixed_families=['A','B','D','rock']
    for name,case in cases.items():
        color=sum(case['channels'].values(),[]);allrows=case['ink']+color;profile_errors=[]
        for r in allrows:
            for key in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
                if key in r and len(r[key])!=len(r['xy_mm']):profile_errors.append([r['id'],key])
        exact={k:digest([r for r in base['ink'] if r['source_family']==k])==digest([r for r in case['ink'] if r['source_family']==k]) for k in fixed_families}
        checks[name]=dict(exact_fixed_ink=exact,unique_ids=len({r['id'] for r in allrows})==len(allrows),profile_errors=profile_errors,color_slots_unchanged=set(r['palette_slot'] for r in color)<=set(r['palette_slot'] for r in sum(base['channels'].values(),[])),ink_paths=len(case['ink']),color_paths=len(color),RSU_grid_cells=len(coverage([r for r in allrows if r['source_family']=='RSU'])))
        assert all(exact.values()) and checks[name]['unique_ids'] and not profile_errors and checks[name]['color_slots_unchanged'],checks[name]
        save_case(output,name,case)
    for name in ['v10_2','v10_3']:
        assert cases[name]['channels']['A']==cases['v10_1']['channels']['A']
        assert cases[name]['channels']['C']==cases['v10_1']['channels']['C']
    for decision in ledger:decision.setdefault('v10_case','v10_1')
    meta=dict(config=c,A_displacement=a_stats,shared_native_plans=native,shared_RSU_plans=rsplans,new_sites=sites,new_site_relationships=dict(Counter(s['relationship'] for s in sites)),composition_plans=plans_record,checks=checks,baseline_input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in control.glob('*.json.gz')},source_field_hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in fixed['base'].items()},published=False,merged=False,machine_output=False)
    (output/'record.json').write_text(json.dumps(meta,indent=2)+'\n');(output/'config.json').write_text(json.dumps(oldc,indent=2)+'\n');write_gz(output/'authored_sources.json.gz',dict(strokes=sources));write_gz(output/'change_ledger.json.gz',dict(decisions=ledger));print(json.dumps(dict(A=a_stats,new_sites=len(sites),checks=checks),indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',default='outputs/spring-integration-v09');p.add_argument('--inputs',default='outputs/spring-integration-v09/reproduction_inputs');p.add_argument('--output',required=True);a=p.parse_args();run(Path(a.control),Path(a.inputs),Path(a.output))
