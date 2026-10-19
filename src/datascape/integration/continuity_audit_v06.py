"""Focused v06 continuity evidence; measurements are digital proxies, not approvals."""
from pathlib import Path
from collections import Counter
import json,csv,hashlib
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from datascape.strokes.vector import sample,resample,read_vectors
from datascape.integration.visibility import digest
from datascape.integration.cluster_scene import intersects
from datascape.integration.macro_wash import source_basis
from datascape.integration.spring_v05_audit import source_audit,channel_metrics,length


def runs(mask,width):
    best_on=best_off=on=off=0
    for val in mask:
        on=on+1 if val else 0;off=0 if val else off+1;best_on=max(best_on,on);best_off=max(best_off,off)
    return dict(longest_occupied_run_proxy_mm=best_on*width,longest_empty_run_proxy_mm=best_off*width)


def zone_continuity(zone,records,fixed):
    """Longitudinal 12-mm occupancy, excluding baseline terrain A/B/C/D."""
    x0,x1=zone['x'][[0,-1]];n=int(np.ceil((x1-x0)/12));step=(x1-x0)/n;totals=np.zeros(n)
    for r in records:
        fam=r.get('source_family');kind=r.get('color_kind')
        if fam not in ['tree','rock','Soil','RSU'] and kind not in ['vegetation','rock','Soil']:continue
        p=resample(r['xy_mm'],1.5)
        if len(p)<2:continue
        mid=(p[:-1]+p[1:])/2;d=np.linalg.norm(np.diff(p,axis=0),axis=1);x=mid[:,0];valid=(x>=x0)&(x<=x1);at=np.clip(x,x0,x1)
        if 'source_forward_profile_m' in r:
            ar=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))];s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];q=np.interp((s[:-1]+s[1:])/2,ar,r['source_forward_profile_m'])
        elif 'source_object_depth_m' in r:q=np.full(len(mid),r['source_object_depth_m'])
        else:q=sample(fixed['base']['depth_m'],mid)
        valid &= (np.abs(q-zone['qf'](at))<zone['spec']['width_q_m']*2.2)&(np.abs(mid[:,1]-zone['yf'](at))<65)
        bins=np.clip(((x-x0)/step).astype(int),0,n-1);np.add.at(totals,bins[valid],d[valid])
    occupied=totals>=2.
    return dict(zone_id=zone['spec']['id'],span_x_mm=float(x1-x0),bin_width_mm=float(step),occupied_bins=int(occupied.sum()),bins=n,occupation_fraction=float(occupied.mean()),**runs(occupied,step))


def spatial_a(fixed,old,new,anchors):
    q=fixed['base']['depth_m'];xyz=source_basis(fixed,np.nan_to_num(fixed['base']['xyz']));aa=source_basis(fixed,[a['source_xyz_m'] for a in anchors]);_,idx=cKDTree(aa[:,:2]/[220,1000]).query((xyz[...,:2]/[220,1000]).reshape(-1,2));drop=aa[idx,2].reshape(q.shape)-xyz[...,2]
    domain=fixed['base']['occupied']&(fixed['retention']>.23)&(fixed['refined']['global_retention']>0)
    masks=dict(upper=domain&(q>=1600)&(drop>=-80)&(drop<=120),lower=domain&(q>=1600)&(drop>120)&(drop<=650),deep_lower=domain&(q>=1000)&(drop>650)&(drop<=1000),middle=domain&(q>=800)&(q<2200),far=domain&(q>=2200))
    out={}
    for key,mask in masks.items():
        values=[]
        for rows in [old,new]:
            total=0.
            for r in rows:
                p=resample(r['xy_mm'],.7);mid=(p[:-1]+p[1:])/2;inside=sample(mask.astype(float),mid,order=0)>.5;total+=float(np.linalg.norm(np.diff(p,axis=0),axis=1)[inside].sum())
            values.append(total)
        area=int(mask.sum());out[key]=dict(area_mm2=area,v05_length_mm=values[0],v06_length_mm=values[1],v05_density_mm_per_mm2=values[0]/max(1,area),v06_density_mm_per_mm2=values[1]/max(1,area))
    return out


def audit(fixed,native,forest,colors,c,zones,field,out,baseline):
    out=Path(out);control=Path('outputs/spring-integration-v05');oldink=read_vectors(control/'case12_ink.json.gz')['strokes'];oldcolor=read_vectors(control/'case2_color.json.gz')['strokes'];oldA=read_vectors(control/'channel_A.json.gz')['strokes'];ink=native['ink']+forest['ink'];newcolor=colors['expanded']
    sources=baseline+native['new_sources']+forest['raw']+sum(colors['sources'].values(),[]);lineage=source_audit(ink+newcolor,sources)
    hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in dict(xyz=fixed['base']['xyz'],depth_m=fixed['base']['depth_m'],occupied=fixed['base']['occupied'],retention=fixed['retention']).items()};oldrecord=json.loads((control/'record.json').read_text());assert hashes==oldrecord['field_sha256']
    body=omission=0
    for r in colors['channels']['A']+colors['channels']['C']:
        p=resample(r['xy_mm'],.6);b=LineString(r['xy_mm']).bounds;q=sample(fixed['base']['depth_m'],p);omission+=int((sample(fixed['refined']['global_retention'],p)<=0).sum())
        for o in native['objects']:
            if not intersects(b,o['bounds']):continue
            body+=int(((q>=sample(o['q'],p)-25)&(sample(o['regions']['body'].astype(float),p,order=0)>.5)).sum())
    checks=dict(**lineage,field_hashes_equal_v05=True,case1_case2_identical_ink=True,case1_color_exact_subset=all(r in newcolor for r in colors['restrained']),
        unique_ids=len({r['id'] for r in ink+newcolor})==len(ink+newcolor),legacy_V_paths=sum(r.get('source_family')=='V' for r in ink),
        color_minimum_3_2_mm=all(length(r)>=3.2-1e-7 for r in newcolor),terrain_color_in_hard_bodies_samples=body,terrain_color_in_absolute_omission_samples=omission,
        R_S_U_terrain_deleted_mm=forest['terrain_deleted_mm'],B_enabled=False,physical_pressure_calibrated=False)
    flow=[]
    for z in zones:
        a=zone_continuity(z,oldink+oldcolor,fixed);b=zone_continuity(z,ink+newcolor,fixed);flow.append(dict(zone_id=z['spec']['id'],role=z['spec']['role'],v05=a,v06=b))
    rootzones=Counter(s['zone_id'] for s in forest['sites']);longspans=[r for r in forest['raw'] if 'S-zone-support' in r['id'] and '/mist-release' not in r['id']]
    result=dict(study=c['study'],parent_commit=c['parent_commit'],validation=checks,field_sha256=hashes,native_objects=dict(Counter(o['kind'] for o in native['objects'])),
        zones=[dict(**z['spec'],anchors=z['anchors'],accepted_roots=rootzones[z['spec']['id']]) for z in zones],
        forest=dict(roots=len(forest['sites']),rejected=len(forest['rejected']),ink=len(forest['ink']),color=len(forest['color']),long_support_sources=len(longspans),maximum_long_support_mm=max(map(length,longspans),default=0)),
        cases=dict(v05_ink=channel_metrics(oldink),v05_color=channel_metrics(oldcolor),v06_ink=channel_metrics(ink),v06_restrained_color=channel_metrics(colors['restrained']),v06_expanded_color=channel_metrics(newcolor)),
        channels={k:dict(paths=len(v),length_mm=sum(map(length,v)),raw_paths=len(colors['raw'].get(k,[]))) for k,v in colors['channels'].items()},
        A_depth_comparison=spatial_a(fixed,oldA,colors['channels']['A'],colors['anchors']),longitudinal_occupation=flow,display=c['readable_display'],
        interpretation='Occupation is a 12-mm bin proxy for actual object/material marks, not a physical coverage score or artistic acceptance. Zones may overlap.',
        open_issues=['S carrier banding and repeated short canopy signs','Pictorial mass continuity is provisional','Exact roots do not certify 3D crowns or visible attachment','C repetition and palette balance remain visual decisions','Ink/color physical spread and accumulation uncalibrated','OCC-01 through OCC-08 remain open'],publication=False,machine_changes=False)
    (out/'record.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');(out/'validation.json').write_text(json.dumps(checks,indent=2)+'\n');(out/'zones.json').write_text(json.dumps(result['zones'],indent=2)+'\n')
    with (out/'zone_continuity.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['zone','span_mm','v05_occupied_fraction','v06_occupied_fraction','v05_longest_occupied_run_mm','v06_longest_occupied_run_mm','v05_longest_empty_run_mm','v06_longest_empty_run_mm'])
        for row in flow:
            a,b=row['v05'],row['v06'];w.writerow([row['zone_id'],b['span_x_mm'],a['occupation_fraction'],b['occupation_fraction'],a['longest_occupied_run_proxy_mm'],b['longest_occupied_run_proxy_mm'],a['longest_empty_run_proxy_mm'],b['longest_empty_run_proxy_mm']])
    assert not lineage['missing_source_ids'] and not lineage['profile_errors'] and lineage['maximum_source_arc_error_mm']<1e-6
    assert checks['unique_ids'] and checks['color_minimum_3_2_mm'] and checks['case1_color_exact_subset'] and body==0 and omission==0
    return result
