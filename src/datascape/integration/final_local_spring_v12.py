"""One bounded refinement on frozen v11, without changing the catalogs.

Two related P trees use existing exact roots and source-depth order with rocks.
The left S/R accumulation is replaced with low, separated inherited R/S/U units.
Small accepted ground patches borrow fixed pre-object A/C hosts; A ink itself
is never restored or redrawn in the former object-occlusion opening.
"""
from pathlib import Path
from copy import deepcopy
from collections import defaultdict,Counter
import argparse,json,csv,hashlib
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString,Point,box
from shapely.ops import substring
from shapely import contains_xy,distance,points as geometry_points
from datascape.strokes.vector import read_vectors,resample,sample,phase
from datascape.integration.visibility import digest
from datascape.integration.local_refinement_v09 import load_inputs,cut,q_at
from datascape.integration.controlled_spring_v10 import (CHANNELS,owner,length,prepare_fields,ground_gate,native_masks,generate_small,save_case)
from datascape.integration.landscape_depth_v08 import vegetation_palette,terrain_slot
from datascape.integration.cluster_scene import catalog_seed,pose_tree,q_sheet,intersects
from datascape.integration.diverse_scene import representation_records,add_metadata
from datascape.integration.diverse_color import make_carrier,local_frame
from datascape.integration.macro_wash import foliage_candidates,paired_supports,trunk_candidates
from datascape.vegetation.tree_final_scale import make_tree,vector_records
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.ground.patch_system_v04 import patch_system,PatchSpec,PatchControls,host_function
from datascape.rendering.spring_macro_study import write_gz

ROOT=Path(__file__).resolve().parents[3]


def load(path):return dict(ink=read_vectors(path/'after_ink.json.gz')['strokes'],channels={k:read_vectors(path/f'after_channel_{k}.json.gz')['strokes'] for k in CHANNELS})


def local_depth_gate(masks,c,r,tolerance=5.):
    """Actual source q, strong body/core occupancy and graduated edge release."""
    peers=[o for o in masks if intersects(LineString(r['xy_mm']).bounds,o['bounds']) and o['id']!=owner(r)]
    def gate(xy,arcs,rec):
        q=q_at(rec,xy,arcs);good=np.full(len(xy),1e6);cohort=rec.get('source_member_ids',[owner(rec)])[0];w=max(rec.get('width_profile_mm',[rec.get('assumed_footprint_mm',rec['width_mm'])]));p=np.array(rec['xy_mm']);t=np.gradient(p,axis=0);t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-9);n=np.c_[-t[:,1],t[:,0]];aa=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];nn=np.c_[np.interp(arcs,aa,n[:,0]),np.interp(arcs,aa,n[:,1])]
        for o in peers:
            behind=q>np.interp(xy[:,0],np.arange(600)+.5,o['q_row'])+tolerance
            occ=np.maximum.reduce([sample(o['combined_occupancy'],xy),sample(o['combined_occupancy'],xy+nn*w/2),sample(o['combined_occupancy'],xy-nn*w/2)])
            threshold=.045+.225*(.57+.40*phase(cohort+'/'+o['id']+'/v12-edge',c['seed']));body=sample(o['body_distance'],xy)-w/2-.65;good=np.minimum(good,np.where(behind,np.minimum(body,threshold-occ),1e6))
        return good,['v12-measured-source-q-order','body-core-protection','graduated-canopy-edge']
    return gate


def remove_left_accumulation(case,c,ledger):
    region=box(*c['left_accumulation_bounds_mm']);units=defaultdict(list)
    for r in case['channels']['RSU']:
        center=np.mean(r['xy_mm'],axis=0)
        if region.contains(Point(center)):units[r.get('source_member_ids',[owner(r)])[0]].append(r)
    table=[]
    for key,rows in units.items():table.append(dict(unit_id=key,family=rows[0].get('pictorial_family'),root_xy_mm=rows[0].get('root_xy_mm'),source_q_m=rows[0].get('source_forward_m'),paths_in_accumulation=len(rows),color_length_mm=sum(map(length,rows))))
    removed=set(units);out=dict(ink=[],channels={k:[] for k in CHANNELS})
    for ch,rows in [('ink',case['ink'])]+list(case['channels'].items()):
        target=out['ink'] if ch=='ink' else out['channels'][ch]
        for r in rows:
            key=r.get('source_member_ids',[owner(r)])[0]
            if r['source_family']=='RSU' and key in removed:ledger.append(dict(source_id=r['id'],reason='v12-whole-source-unit-left-accumulation-release',kept_intervals_mm=[]));continue
            if ch=='rock_soil' and owner(r)=='v03/Soil/middle-left-attached' and length(r)>18 and LineString(r['xy_mm']).intersects(region):
                L=length(r);ph=phase(r['id']+'/left-Soil',c['seed']);a=.09*L;b=(.40+.10*ph)*L;cc=(.64+.08*ph)*L;d=.94*L
                pp,decision=cut(r,lambda xy,arc,rec:(np.maximum(np.minimum(arc-a,b-arc),np.minimum(arc-cc,d-arc)),['v12-interrupt-color-reinforcing-old-shrub-band']),3.2,'v12-left-Soil-color-release');ledger.append(decision);target+=pp
            else:target.append(r)
    return out,table


def raw_tree(spec,context,fixed,oldc,c):
    ident=spec['owner'];obj=next(o for o in context['objects'] if o['id']==ident);site=obj['site'];group=next(g for g in oldc['groups'] if g['id']=='near-right-exposure')
    tree=make_tree(spec['form'],root=site['xy_mm'],height=spec['height_mm'],seed=catalog_seed(c['seed'],ident),identity=ident,posture=spec['posture'],accent=spec['accent'],profile='refined',growth_controls=GrowthControls(stem_ratio=spec['stem_ratio'],vigor=spec['vigor']))
    tree,rotation,lean=pose_tree(tree,spec['flow']);ink=add_metadata(representation_records(tree,vector_records(tree.marks,[tree]),group['representation']),ident,'tree',site,group,'v12-paired-P')
    obj2=dict(id=ident,tree=tree,group=group['id'],height_mm=spec['height_mm'],q=q_sheet(site),records=ink,representation=group['representation']);pairs=list(trunk_candidates(fixed,obj2,oldc,paired_supports(obj2)));trunk=[r for r,poly in pairs];regions={r['id']:poly for r,poly in pairs};col=vegetation_palette(list(foliage_candidates(fixed,obj2,ink,oldc)),oldc)
    records=[]
    for ch,rows in [('ink',ink),('gestures',col),('trunk',trunk)]:
        for original in rows:
            r=deepcopy(original);r.update(id='v12/pair/'+r['id'],source_stroke_id='v12/pair/'+r['id'],source_arc_mm=[0.,length(r)],source_forward_profile_m=sample(obj2['q'],r['xy_mm']).tolist(),v12_rule='paired-approved-P-tree',v12_pair_height_mm=spec['height_mm']);records.append((ch,r,regions.get(original['id'])))
    return records,dict(owner=ident,site=site,form=spec['form'],height_mm=spec['height_mm'],source_q_m=site['source_forward_m'],pose_rotation_deg=rotation,axis_lean_ratio=lean,axis_nodes_mm=tree.structure['axis_nodes_mm'],members=list(tree.structure['members']))


def regenerate_pair(case,context,fixed,fields,oldc,c,sources,ledger):
    ids={c['main_tree']['owner'],c['secondary_tree']['owner']};case['ink']=[r for r in case['ink'] if owner(r) not in ids]
    for k in CHANNELS:case['channels'][k]=[r for r in case['channels'][k] if owner(r) not in ids]
    existing=native_masks(case,context,set());rocks=[o for o in context['objects'] if o['kind']=='rock' and o['group']=='near-right-exposure'];infos=[]
    for spec in [c['main_tree'],c['secondary_tree']]:
        raw,info=raw_tree(spec,context,fixed,oldc,c);infos.append(info)
        for ch,r,region in raw:
            sources.append(r);gg=ground_gate(fields,fixed,r,.25);ng=local_depth_gate(existing,c,r,5.)
            def gate(xy,arc,rec):
                g,why=gg(xy,arc,rec);n,nr=ng(xy,arc,rec);g=np.minimum(g,n);q=q_at(rec,xy,arc);w=max(rec.get('width_profile_mm',[rec['width_mm']]))/2+.55
                for rock in rocks:
                    behind=q>np.interp(xy[:,0],np.arange(600)+.5,rock['q_row'])+5.;g=np.minimum(g,np.where(behind,sample(rock['body_distance'],xy)-w,1e6))
                if region is not None:
                    inset=region.buffer(-w)
                    g=np.minimum(g,-1. if inset.is_empty else np.where(contains_xy(inset,xy[:,0],xy[:,1]),1.,-1.)*distance(inset.boundary,geometry_points(xy)))
                return g,why+nr+['v12-tree-behind-nearer-rocks-only']
            pp,d=cut(r,gate,2.8 if ch=='ink' else 3.2,'v12-pair-source-depth-rock-order');ledger.append(d)
            if ch=='ink':case['ink']+=pp
            else:case['channels'][ch]+=pp
    del existing
    trees=native_masks(case,context,set());pair=[o for o in trees if o['id'] in ids];changed=Counter();out=dict(ink=[],channels={k:[] for k in CHANNELS})
    for ch,rows in [('ink',case['ink'])]+list(case['channels'].items()):
        target=out['ink'] if ch=='ink' else out['channels'][ch]
        for r in rows:
            eligible=r['source_family'] in ['tree','RSU','rock'] or ch in ['gestures','trunk'] or (ch=='rock_soil' and r.get('color_kind')=='rock')
            if eligible and any(intersects(LineString(r['xy_mm']).bounds,o['bounds']) and owner(r)!=o['id'] for o in pair):
                pp,d=cut(r,local_depth_gate(pair,c,r,5. if r['source_family']=='rock' or owner(r) in ids else 25.),2.8 if ch=='ink' else 3.2,'v12-pair-front-of-deeper-rock-and-vegetation');ledger.append(d);target+=pp
                if d['removed_mm']>1e-7:changed[owner(r)]+=1
            else:target.append(r)
    return out,infos,dict(changed)


def supported_low_sites(base,context,trees,fixed,fields,c,oldc):
    region=c['low_vegetation_field_mm'];pts=[];refs=[];layers=[]
    for r in read_vectors(ROOT/oldc['baseline'])['strokes']:
        if r.get('layer') not in ['A','C']:continue
        p=resample(r['xy_mm'],3.);q=sample(fixed['base']['depth_m'],p);ok=(p[:,0]>region[0])&(p[:,0]<region[2])&(p[:,1]>region[1])&(p[:,1]<region[3])&(q>350)&(q<900)&(sample(fields['global_clear'],p)>5)&(sample(fields['reserve_clear'],p)>5)&(sample(fixed['retention'],p)>.14)
        for xy,qq in zip(p[ok],q[ok]):pts.append([*xy,qq]);refs.append(r['id']);layers.append(r['layer'])
    pts=np.array(pts);cells=defaultdict(list)
    for i,p in enumerate(pts):cells[(int(p[0]//20),int(p[1]//16))].append(i)
    chosen=[];sites=[];used=[]
    for cell,indices in sorted(cells.items(),key=lambda x:phase(str(x[0])+'/scatter',c['seed'])):
        indices=sorted(indices,key=lambda i:phase(refs[i]+str(pts[i,:2]),c['seed']))
        for i in indices:
            p=pts[i,:2]
            qq=pts[i,2]
            if any(np.linalg.norm(p-v)<11 for v in used) or any(qq>np.interp(p[0],np.arange(600)+.5,o['q_row'])+25 and sample(o['body_distance'],[p])[0]<3 for o in trees):continue
            chosen.append(i);used.append(p);break
        if len(chosen)>=c['low_vegetation_sites']:break
    for j,i in enumerate(chosen):
        p=pts[i,:2];q=float(pts[i,2]);key=f'v12/low-ground/{j}';site=dict(xy_mm=p.tolist(),source_forward_m=q,source_xyz_utm_m=[float(sample(fixed['base']['xyz'][:,:,k],[p])[0]) for k in range(3)],support_source_id=refs[i],support_layer=layers[i],exact_contact=False,depth_provider='saved-F2-1mm-fields-on-fixed-pre-object-terrain-source',crs='EPSG:32652')
        sites.append(dict(id=key,stand_id=key,patch_id=key,stand_index=j,stand_role='subordinate',member_index=j,member_count=1,root_xy_mm=p.tolist(),height_mm=7.5+5*phase(key+'/height',c['seed']),form=['P','B','U'][j%3],site=site,guide_u=p[0]/600,guide_source_id=refs[i],tangent_xy=[1.,0.],family=['S','R','U'][j%3],mode='M3',zone_id=key,relationship='dispersed-low-ground',nearby_rock_id=None))
    return sites


def clip_low(raw,trees,context,fixed,fields,c,sources,ledger):
    out=[]
    for old in raw:
        key=old['v10_new_site_id'];r=deepcopy(old)
        if 'palette_slot' in r:
            if r.get('hierarchy_tier')=='long' or phase(r['id']+'/touch-release',c['seed'])>.62:continue
        r.update(v12_rule='dispersed-low-ground',v12_site_id=key);sources.append(r);gg=ground_gate(fields,fixed,r,.5);ng=local_depth_gate(trees,c,r,25.)
        def gate(xy,arc,rec):
            g,why=gg(xy,arc,rec);n,nr=ng(xy,arc,rec);q=q_at(rec,xy,arc);g=np.minimum(g,n);g=np.minimum(g,np.where(sample(fixed['base']['occupied'],xy)>.5,sample(fixed['base']['depth_m'],xy)-q+35,1e6));return g,why+nr
        pp,d=cut(r,gate,3.2 if 'palette_slot' in r else 2.8,'v12-low-ground-visible-sites');out+=pp;ledger.append(d)
    return out


def ground_patches(case,fixed,fields,trees,oldc,c,sources,ledger):
    parents=read_vectors(ROOT/oldc['baseline'])['strokes'];hosts=[r for r in parents if r.get('layer')=='A'];crosses=[r for r in parents if r.get('layer')=='C'];specs=[];added=[]
    for j,(x,y,area,aspect,angle) in enumerate(c['left_ground_patches']):
        goal=Point(x,y);host=min(hosts,key=lambda r:LineString(r['xy_mm']).distance(goal));p=np.array(host['xy_mm']);p=p[np.argsort(p[:,0])];p=p[np.r_[True,np.diff(p[:,0])>1e-5]]
        if len(p)<3:continue
        h=dict(id=host['id'],xy_mm=p.tolist());xx=float(np.clip(x,p[0,0]+2,p[-1,0]-2));host_y=float(host_function(h)(xx));yy=float(y);offset=yy-host_y;xy=[xx,yy];q=float(sample(fixed['base']['depth_m'],[xy])[0]);key=f'v12/left-ground/patch-{j}'
        def cross_score(r):
            a=np.array(r['xy_mm']);delta=a[-1]-a[0];slope=abs(delta[1]/delta[0]);return LineString(a).distance(Point(xy))+max(0.,.23-slope)*100
        cross=deepcopy(min([r for r in crosses if abs(np.array(r['xy_mm'])[-1,0]-np.array(r['xy_mm'])[0,0])>2],key=cross_score))
        if cross['xy_mm'][-1][0]<cross['xy_mm'][0][0]:cross['xy_mm']=cross['xy_mm'][::-1]
        spec=PatchSpec(key,xx,offset,area,aspect_ratio=aspect,irregularity=.22+.025*(j%3),rotation_deg=angle,family_phase=.7+j*.91,contact='fixed A tangent plus declared local ground offset; original A ink unchanged')
        patch=patch_system(key,h,[spec],PatchControls(spacing_mm=4.0+j*.15,directional_coherence=.36+.12*(j%3),edge_dissolution=.43,pigment_enabled=False,relation='discontinuous'),depth=q,cross_flow_record=cross)
        specs.append(dict(id=key,center_xy_mm=xy,host_id=h['id'],host_offset_mm=offset,cross_flow_id=cross['id'],source_q_m=q,area_mm2=area,bounds=list(patch.surface.support.bounds)))
        for i,old in enumerate(patch.surface.paths):
            old=deepcopy(old);original=LineString(old['xy_mm']);ph=phase(old['id']+'/unequal-ground-episode',c['seed']);a=(.03+.16*ph)*original.length;b=(.64+.32*phase(old['id']+'/ground-end',c['seed']))*original.length
            if b-a<2.8:continue
            old['xy_mm']=list(substring(original,a,b).coords);old['catalog_patch_arc_mm']=[a,b]
            r=deepcopy(old);n=len(r['xy_mm']);ph=phase(r['id'],c['seed']);u=np.linspace(0,1,n);w=(.36+.07*ph)*(.70+.30*np.sin(np.pi*u));r.update(id='v12/ground/'+r['id'],source_family='Soil',owner_id=key,source_stroke_id='v12/ground/'+r['id'],source_arc_mm=[0.,length(r)],width_mm=float(w.mean()),width_profile_mm=w.tolist(),preview_opacity=.75,source_forward_profile_m=sample(fixed['base']['depth_m'],r['xy_mm']).tolist(),v12_rule='open-left-ground-patch',support_references=[dict(source_id=h['id'],role='unchanged pre-object A host with declared offset',offset_mm=offset),dict(source_id=cross['id'],role='restrained C directional blend')],assumed_footprint_mm=float(w.max()),physical_plotting_validated=False)
            sources.append(r);gg=ground_gate(fields,fixed,r,.45);ng=local_depth_gate(trees,c,r,25.)
            def gate(xy,arc,rec):
                a,ar=gg(xy,arc,rec);b,br=ng(xy,arc,rec);return np.minimum(a,b),ar+br+['v12-low-open-foreground-support']
            pp,d=cut(r,gate,2.8,'v12-left-patch-ground');added+=pp;ledger.append(d)
            if phase(key+f'/C-{i}',c['seed'])>.52:continue
            p=np.array(r['xy_mm']);t,normal=local_frame(p);p=p+normal*(.45+.5*ph);col=make_carrier(p,r['id']+'/C-companion',key,'terrain',sample(fixed['base']['depth_m'],p),oldc,h['id'],'C-derived',r['support_references'])
            if col is None:continue
            col.update(v12_rule='restrained-left-C-ground-cue',width_mm=.85,width_profile_mm=[.85*(.58+.42*np.sin(np.pi*v)) for v in np.linspace(0,1,len(col['xy_mm']))],palette_slot=terrain_slot(q,xy,col['id'],oldc),color_logic='v08-gray-earth-yellow-depth-gradient',color_subchannel='v12-low-ground-C',assumed_footprint_mm=.85)
            sources.append(col);cp,cd=cut(col,gate,3.2,'v12-restrained-left-C');added+=cp;ledger.append(cd)
    return added,specs


def run(control,inputs,output):
    output.mkdir(parents=True,exist_ok=False);c=json.load(open(ROOT/'configs/scenes/seoul_spring_final_local_v12.json'));oldc=json.load(open(control/'config.json'));base=load(control);context,fixed=load_inputs(inputs);fields=prepare_fields(fixed,oldc);sources=[];ledger=[];case,contributors=remove_left_accumulation(base,c,ledger);case,pair,pair_changes=regenerate_pair(case,context,fixed,fields,oldc,c,sources,ledger);print('PAIR_READY',flush=True)
    trees=native_masks(case,context,set());sites=supported_low_sites(base,context,trees,fixed,fields,c,oldc);low=clip_low(generate_small(sites,c),trees,context,fixed,fields,c,sources,ledger);ground,patches=ground_patches(case,fixed,fields,trees,oldc,c,sources,ledger)
    case['ink']+=[r for r in low+ground if 'palette_slot' not in r];case['channels']['RSU']+=[r for r in low if 'palette_slot' in r];case['channels']['C']+=[r for r in ground if 'palette_slot' in r]
    checks={k:digest([r for r in base['ink'] if r['source_family']==k])==digest([r for r in case['ink'] if r['source_family']==k]) for k in ['A','B','D']};assert all(checks.values());assert base['channels']['A']==case['channels']['A'];rows=case['ink']+sum(case['channels'].values(),[]);errors=[]
    for r in rows:
        for k in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
            if k in r and len(r[k])!=len(r['xy_mm']):errors.append([r['id'],k])
    assert not errors and len({r['id'] for r in rows})==len(rows)
    for name,obj in [('before',base),('after',case)]:save_case(output,name,obj)
    rec=dict(config=c,pair=pair,pair_occlusion_changes=pair_changes,left_accumulation_contributors=contributors,left_source_family_counts=dict(Counter(x['family'] for x in contributors)),low_sites=sites,left_ground_patches=patches,added_ground_ink_paths=sum('palette_slot' not in r for r in ground),added_ground_C_paths=sum('palette_slot' in r for r in ground),added_low_color_paths=sum('palette_slot' in r for r in low),exact_fixed_ink=checks,A_color_exact=True,profile_errors=errors,unique_ids=True,field_hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in fixed['base'].items()},baseline_input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in control.glob('after*.json.gz')},status='interim-finished vector candidate; awaiting visual review',published=False,merged=False,machine_output=False)
    (output/'record.json').write_text(json.dumps(rec,indent=2)+'\n');(output/'config.json').write_text(json.dumps(oldc,indent=2)+'\n');write_gz(output/'authored_sources.json.gz',dict(strokes=sources));write_gz(output/'change_ledger.json.gz',dict(decisions=ledger))
    with (output/'left_accumulation.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(contributors[0]));w.writeheader();w.writerows(contributors)
    print('V12_READY',len(sites),len(ground),len(contributors),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',default='outputs/spring-focused-v11');p.add_argument('--inputs',default='outputs/spring-integration-v09/reproduction_inputs');p.add_argument('--output',required=True);a=p.parse_args();run(Path(a.control),Path(a.inputs),Path(a.output))
