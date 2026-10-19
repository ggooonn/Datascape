"""One local review on saved v10_3; immutable inherited source and fields.

The anchor is regenerated from the approved catalog at the same exact root.
Orphan low-right owners and their shared patch/C context are resolved together.
Small additions use inherited R/S/U generators and sampled F2/A-line contacts.
"""
from pathlib import Path
from collections import defaultdict,Counter
from copy import deepcopy
import argparse,json,hashlib
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString,Point,box
from shapely import contains_xy,distance,points as geometry_points
from datascape.strokes.vector import read_vectors,resample,sample,phase
from datascape.integration.visibility import digest
from datascape.integration.local_refinement_v09 import load_inputs,cut,canopy_gate,coverage
from datascape.integration.controlled_spring_v10 import (CHANNELS,owner,length,prepare_fields,
    ground_gate,native_masks,generate_small,save_case)
from datascape.vegetation.tree_final_scale import make_tree,vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.integration.cluster_scene import catalog_seed,pose_tree,q_sheet,intersects
from datascape.integration.diverse_scene import representation_records,add_metadata
from datascape.integration.macro_wash import foliage_candidates,paired_supports,trunk_candidates
from datascape.rendering.spring_macro_study import write_gz

ROOT=Path(__file__).resolve().parents[3]
ANCHOR='v03/tree/near-right-exposure/behind-main'


def baseline(path):
    return dict(ink=read_vectors(path/'v10_3_ink.json.gz')['strokes'],channels={k:read_vectors(path/f'v10_3_channel_{k}.json.gz')['strokes'] for k in CHANNELS})


def drop_owner(r,removed):
    k=owner(r);return k in removed or any(k.startswith(x+'/root-contact-Soil') for x in removed)


def regenerate_anchor(case,context,fixed,fields,oldc,c,sources,ledger):
    o=next(x for x in context['objects'] if x['id']==ANCHOR);group=next(x for x in oldc['groups'] if x['id']=='near-right-exposure');spec=next(x for x in group['trees'] if x['key']=='behind-main');site=o['site'];h=c['anchor_height_mm']
    tree=make_tree(spec['form'],root=site['xy_mm'],height=h,seed=catalog_seed(oldc['seed'],ANCHOR),identity=ANCHOR,posture='upright',profile='refined',growth_controls=GrowthControls(stem_ratio=spec['stem_ratio'],vigor=spec['vigor']))
    tree,_,_=pose_tree(tree,c['anchor_flow']);ink=add_metadata(representation_records(tree,vector_records(tree.marks,[tree]),group['representation']),ANCHOR,'tree',site,group,'behind-main')
    obj=dict(id=ANCHOR,tree=tree,group=group['id'],height_mm=h,q=q_sheet(site),records=ink,representation=group['representation'])
    color=list(foliage_candidates(fixed,obj,ink,oldc));trunk_pairs=list(trunk_candidates(fixed,obj,oldc,paired_supports(obj)));trunk=[r for r,region in trunk_pairs];trunk_regions={r['id']:region for r,region in trunk_pairs}
    case['ink']=[r for r in case['ink'] if owner(r)!=ANCHOR]
    for k in CHANNELS:case['channels'][k]=[r for r in case['channels'][k] if owner(r)!=ANCHOR]
    rocks=[x for x in context['objects'] if x['kind']=='rock' and x['group']=='near-right-exposure']
    for channel,rows in [('ink',ink),('gestures',color),('trunk',trunk)]:
        for old in rows:
            r=deepcopy(old);r['id']='v11/anchor/'+r['id'];r['source_stroke_id']=r['id'];r['source_arc_mm']=[0.,length(r)];r['source_forward_profile_m']=[site['source_forward_m']]*len(r['xy_mm']);r.update(v11_rule='same-root-approved-P-catalog-165mm',v11_anchor_height_mm=h);sources.append(r);basegate=ground_gate(fields,fixed,r,.25);region=trunk_regions.get(old['id'])
            def gate(xy,arc,rec):
                g,why=basegate(xy,arc,rec);w=max(rec.get('width_profile_mm',[rec['width_mm']]))/2+.55
                for rock in rocks:g=np.minimum(g,sample(rock['body_distance'],xy)-w)
                if region is not None:
                    inset=region.buffer(-w)
                    if inset.is_empty:g=np.minimum(g,-1.)
                    else:g=np.minimum(g,np.where(contains_xy(inset,xy[:,0],xy[:,1]),1.,-1.)*distance(inset.boundary,geometry_points(xy)))
                return g,why+['same-source-root','retained-rock-body-occlusion']
            pp,d=cut(r,gate,2.8 if channel=='ink' else 3.2,'v11-rock-tree-anchor');ledger.append(d)
            if channel=='ink':case['ink']+=pp
            else:case['channels'][channel]+=pp
    return dict(old_height_mm=130,new_height_mm=h,site=site,catalog_form=spec['form'],trunk_color_candidates=len(trunk))


def rhythm_weight(xy,c):
    p=np.asarray(xy);scores=[np.exp(-.5*(((p[:,0]-x)/rx)**2+((p[:,1]-y)/ry)**2)) for x,y,rx,ry in c['transition_gatherings']]
    return np.maximum.reduce(scores)


def resolve_patch(case,context,c,ledger):
    removed=set(c['remove_low_right_owners']);counts=Counter();rock_objects=[o for o in context['objects'] if o['kind']=='rock' and o['group']=='near-right-exposure']
    bounds=c['right_patch_bounds_mm'];region=box(*bounds)
    out=dict(ink=[],channels={k:[] for k in CHANNELS})
    for channel,rows in [('ink',case['ink'])]+list(case['channels'].items()):
        target=out['ink'] if channel=='ink' else out['channels'][channel]
        for r in rows:
            if drop_owner(r,removed):
                counts['whole-low-right-'+channel]+=1;ledger.append(dict(source_id=r['id'],reason='v11-remove-low-right-owner-with-its-ground',kept_intervals_mm=[]));continue
            line=LineString(r['xy_mm']);parts=[r]
            soil=(r['source_family']=='Soil' or r.get('color_kind')=='Soil')
            if (channel=='C' or soil) and line.intersects(region):
                # Retain coherent contact next to real rock bodies. Below them
                # the old scattered planting resolves to open terrain, without
                # synthesizing a replacement band or new ground underlines.
                ph=phase(r.get('carrier_basis',r['source_stroke_id'])+'/patch-release',c['seed'])
                def gate(xy,arcs,rec):
                    inside=(xy[:,0]>bounds[0])&(xy[:,0]<bounds[2])&(xy[:,1]>bounds[1])&(xy[:,1]<bounds[3]);d=np.minimum.reduce([sample(o['body_distance'],xy) for o in rock_objects]);near=11.-d
                    shoulder=817.+3.5*np.sin((xy[:,0]-350)/37+ph*2)-xy[:,1]
                    coherent=np.minimum(near,shoulder)
                    # A smaller unequal subset remains near the grounded mass.
                    pulse=np.sin(arcs/(5.8+4*ph)+ph*6);coherent=np.minimum(coherent,2.2+pulse*3.2) if ph>.46 else coherent
                    return np.where(inside,coherent,1e6),['v11-joint-patch-C-resolution','real-rock-contact','open-lower-right']
                parts,d=cut(r,gate,3.2 if 'palette_slot' in r else 2.8,'v11-joint-patch-C-resolution');ledger.append(d)
                if d['removed_mm']>1e-7:counts['changed-'+channel]+=1
            target+=parts
    return out,dict(counts)


def transition_units(case,c,ledger):
    out=dict(ink=[],channels={k:list(v) for k,v in case['channels'].items()});out['channels']['RSU']=[];removed=set()
    for channel,rows in [('ink',case['ink']),('RSU',case['channels']['RSU'])]:
        target=out['ink'] if channel=='ink' else out['channels']['RSU']
        for r in rows:
            root=r.get('root_xy_mm');key=r.get('source_member_ids',[r['owner_id']])[0]
            if r['source_family']=='RSU' and root is not None and 350<root[0]<590 and 625<root[1]<785:
                weight=float(rhythm_weight([root],c)[0]);prob=.24+.75*weight
                if phase(key+'/v11-gather-release',c['seed'])>prob:
                    removed.add(key);ledger.append(dict(source_id=r['id'],reason='v11-cohort-level-transition-release',kept_intervals_mm=[]));continue
            target.append(r)
    return out,len(removed)


def supported_candidates(base,context,fixed,fields,c,far=True):
    candidates=[];refs=[]
    for r in base['ink']:
        if r['source_family']!='A':continue
        p=resample(r['xy_mm'],3.7);q=sample(fixed['base']['depth_m'],p)
        if far:valid=(q>=1900)&(q<=3700)&(p[:,1]>275)&(p[:,1]<520)&(p[:,0]>18)&(p[:,0]<582)
        else:valid=(q>=400)&(q<1300)&(p[:,0]>350)&(p[:,0]<570)&(p[:,1]>610)&(p[:,1]<785)&(rhythm_weight(p,c)>.52)
        valid&=(sample(fields['reserve_clear'],p)>7)&(sample(fields['global_clear'],p)>8)&(sample(fixed['retention'],p)>.22)
        for xy,qq in zip(p[valid],q[valid]):candidates.append([*xy,qq]);refs.append(r['id'])
    pts=np.array(candidates);cells=defaultdict(list);sizes=(73,43) if far else (30,26)
    for i,p in enumerate(pts):cells[(int(p[0]//sizes[0]),int(p[1]//sizes[1]))].append(i)
    sites=[];used=[];label='far' if far else 'transition';rocks=[o for o in context['objects'] if o['kind']=='rock'];lookup=cKDTree([o['site']['xy_mm'] for o in rocks])
    # Unequal local neighborhoods leave deliberate light cells between denser ones.
    for cell,indices in sorted(cells.items(),key=lambda item:phase(str(item[0])+'/'+label,c['seed'])):
        key=f'v11/{label}/{cell[0]}-{cell[1]}';u=phase(key+'/density',c['seed'])
        if far and u<.20:continue
        count=(1 if u<.51 else 3 if u>.83 else 2) if far else 3
        center=pts[indices[int(phase(key+'/center',c['seed'])*len(indices))],:2]
        chosen=[]
        for i in sorted(indices,key=lambda i:np.linalg.norm(pts[i,:2]-center)):
            xy=pts[i,:2]
            if np.linalg.norm(xy-center)>19 or any(np.linalg.norm(xy-v)<6 for v in used):continue
            if any(sample(o['body_distance'],[xy])[0]<4 for o in context['objects']):continue
            used.append(xy);chosen.append(i)
            if len(chosen)>=count:break
        for j,i in enumerate(chosen):
            xy=pts[i,:2];q=float(pts[i,2]);ident=key+f'/unit-{j}';_,ri=lookup.query(xy)
            site=dict(xy_mm=xy.tolist(),source_forward_m=q,source_xyz_utm_m=[float(sample(fixed['base']['xyz'][:,:,k],[xy])[0]) for k in range(3)],exact_contact=False,depth_provider='saved-F2-1mm-sampled-fields',support_A_id=refs[i],contact_method='unchanged visible A centerline + sampled source fields',crs='EPSG:32652')
            h=float(np.interp(q,[400,1300,3700],[23,17,7]))*(.72+.48*phase(ident+'/height',c['seed']))
            sites.append(dict(id=ident,stand_id=key,patch_id=key,stand_index=j,stand_role='subordinate',member_index=j,member_count=len(chosen),root_xy_mm=xy.tolist(),height_mm=h,form=['P','B','U'][j%3],site=site,guide_u=xy[0]/600,guide_source_id=refs[i],tangent_xy=[1.,0.],family=['S','R','U'][int(phase(ident+'/family',c['seed'])*3)],mode='M2' if q<1700 else 'F1' if q<2700 else 'F2',zone_id=key,relationship=label,nearby_rock_id=rocks[int(ri)]['id']))
    return sites


def visible_new(raw,trees,context,fixed,fields,c,ledger):
    out=[]
    for r in raw:
        rr=deepcopy(r);rr['v11_new_site_id']=rr.pop('v10_new_site_id');rr['v11_role']=rr.pop('v10_relationship');rr['v11_rule']='inherited-RSU-generator-sampled-F2-support';cg=canopy_gate(trees,c,rr);gg=ground_gate(fields,fixed,rr,.6);peers=[o for o in context['objects'] if o['kind']=='rock' and intersects(LineString(rr['xy_mm']).bounds,o['bounds'])]
        def gate(xy,arcs,rec):
            g,why=gg(xy,arcs,rec);co,cr=cg(xy,arcs,rec);q=rec['source_forward_m'];g=np.minimum(g,co)
            g=np.minimum(g,np.where(sample(fixed['base']['occupied'],xy)>.5,sample(fixed['base']['depth_m'],xy)-q+35,1e6))
            for o in peers:g=np.minimum(g,np.where(q>np.interp(xy[:,0],np.arange(600)+.5,o['q_row'])+25,sample(o['body_distance'],xy)-rec['assumed_footprint_mm']/2-.6,1e6))
            return g,why+cr+['v11-source-depth-local-addition']
        pp,d=cut(rr,gate,3.2 if 'palette_slot' in rr else 2.8,'v11-new-RSU-visible-support');out+=pp;ledger.append(d)
    return out


def anchor_occlusion(case,anchor,c,ledger):
    out=dict(ink=[],channels={k:[] for k in CHANNELS});changed=Counter()
    for channel,rows in [('ink',case['ink'])]+list(case['channels'].items()):
        target=out['ink'] if channel=='ink' else out['channels'][channel]
        for r in rows:
            vegetation=r['source_family'] in ['RSU','tree'] or channel in ['gestures','trunk']
            if vegetation and owner(r)!=ANCHOR and intersects(LineString(r['xy_mm']).bounds,anchor['bounds']):
                pp,d=cut(r,canopy_gate([anchor],c,r),3.2 if 'palette_slot' in r else 2.8,'v11-new-anchor-depth-occupancy');ledger.append(d);target+=pp
                if d['removed_mm']>1e-7:changed[channel]+=1
            else:target.append(r)
    return out,dict(changed)


def run(control,inputs,output):
    output.mkdir(parents=True,exist_ok=False);c=json.load(open(ROOT/'configs/scenes/seoul_spring_focused_v11.json'));oldc=json.load(open(control/'config.json'));base=baseline(control);context,fixed=load_inputs(inputs);fields=prepare_fields(fixed,oldc);case=dict(ink=list(base['ink']),channels={k:list(v) for k,v in base['channels'].items()});ledger=[];sources=[]
    anchor=regenerate_anchor(case,context,fixed,fields,oldc,c,sources,ledger);print('ANCHOR',anchor['new_height_mm'],flush=True)
    case,patch=resolve_patch(case,context,c,ledger);case,release=transition_units(case,c,ledger);removed=set(c['remove_low_right_owners']);trees=native_masks(case,context,removed);am=next(o for o in trees if o['id']==ANCHOR);case,occlusion=anchor_occlusion(case,am,c,ledger)
    far_sites=supported_candidates(base,context,fixed,fields,c,True);transition_sites=supported_candidates(base,context,fixed,fields,c,False);raw=generate_small(far_sites+transition_sites,c);sources+=raw;new=visible_new(raw,trees,context,fixed,fields,c,ledger);print('NEW_CANDIDATES',len(far_sites),len(transition_sites),flush=True)
    far0=sum(length(r) for r in base['channels']['RSU'] if r.get('source_forward_m',0)>=1900);budget=far0*c['far_extra_color_length_fraction'];groups=defaultdict(list)
    for r in new:groups[r['v11_new_site_id']].append(r)
    # One unit per cell first, then denser cell companions. Stop near +10% of
    # saved far R/S/U color length; do not fill every possible candidate site.
    ordered=sorted(groups,key=lambda k:(int(k.rsplit('-',1)[-1]),phase(k+'/budget',c['seed'])));selected=[];spent=0.;selected_ids=[];site_lookup={s['id']:s for s in far_sites+transition_sites};transition_count=Counter()
    for key in ordered:
        rows=groups[key];cost=sum(length(r) for r in rows if 'palette_slot' in r);isfar='/far/' in key
        if isfar and (spent+cost>budget or cost==0):continue
        if not isfar:
            root=site_lookup[key]['root_xy_mm'];node=min(range(2),key=lambda i:sum(((root[j]-c['transition_gatherings'][i][j])/c['transition_gatherings'][i][j+2])**2 for j in range(2)))
            if transition_count[node]>=9:continue
            transition_count[node]+=1
        if isfar:spent+=cost
        selected+=rows;selected_ids.append(key)
    case['ink'] += [r for r in selected if 'palette_slot' not in r];case['channels']['RSU'] += [r for r in selected if 'palette_slot' in r]
    far1=sum(length(r) for r in case['channels']['RSU'] if r.get('source_forward_m',0)>=1900);checks={k:digest([r for r in base['ink'] if r['source_family']==k])==digest([r for r in case['ink'] if r['source_family']==k]) for k in ['A','B','D','rock']};assert all(checks.values());assert base['channels']['A']==case['channels']['A']
    rows=case['ink']+sum(case['channels'].values(),[]);errors=[]
    for r in rows:
        for key in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
            if key in r and len(r[key])!=len(r['xy_mm']):errors.append([r['id'],key])
    assert not errors;assert len({r['id'] for r in rows})==len(rows)
    for name,obj in [('before',base),('after',case)]:save_case(output,name,obj)
    rec=dict(config=c,anchor=anchor,patch_changes=patch,transition_units_released=release,anchor_depth_occlusion=occlusion,new_sites=far_sites+transition_sites,selected_new_site_ids=selected_ids,far_RSU_color_length_before_mm=far0,far_RSU_color_length_after_mm=far1,far_RSU_color_length_ratio=far1/far0,far_added_budget_mm=budget,selected_new_roles=dict(Counter('far' if '/far/' in k else 'transition' for k in selected_ids)),exact_fixed_ink=checks,A_color_exact=True,profile_errors=errors,unique_ids=True,source_field_hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in fixed['base'].items()},baseline_input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in control.glob('v10_3*.json.gz')},published=False,merged=False,machine_output=False)
    (output/'record.json').write_text(json.dumps(rec,indent=2)+'\n');(output/'config.json').write_text(json.dumps(oldc,indent=2)+'\n');write_gz(output/'authored_sources.json.gz',dict(strokes=sources));write_gz(output/'change_ledger.json.gz',dict(decisions=ledger));print(json.dumps({k:v for k,v in rec.items() if k not in ['new_sites','selected_new_site_ids','anchor','baseline_input_hashes']},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',default='outputs/spring-controlled-v10');p.add_argument('--inputs',default='outputs/spring-integration-v09/reproduction_inputs');p.add_argument('--output',required=True);a=p.parse_args();run(Path(a.control),Path(a.inputs),Path(a.output))
