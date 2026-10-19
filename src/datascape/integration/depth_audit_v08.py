"""Independent, digital-only evidence for the v08 visual comparison."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib
import numpy as np
from shapely.geometry import LineString,Point
from shapely.ops import substring,unary_union
from datascape.strokes.vector import read_vectors,resample,sample
from datascape.integration.spring_v05_audit import source_audit,length
from datascape.integration.visibility import contact,digest
from datascape.integration.cluster_scene import intersects


def metrics(rows):
    ls=[length(r) for r in rows];depth=defaultdict(lambda:dict(paths=0,length_mm=0.));palette=defaultdict(float)
    for r,l in zip(rows,ls):
        q=float(np.mean(r.get('source_forward_profile_m',[r.get('source_object_depth_m',0)])))
        band='near' if q<800 else 'middle' if q<2200 else 'far';depth[band]['paths']+=1;depth[band]['length_mm']+=l
        palette[r.get('palette_slot',r.get('source_family','ink'))]+=l
    return dict(paths=len(rows),length_mm=sum(ls),maximum_mm=max(ls,default=0),median_mm=float(np.median(ls)) if ls else 0.,p90_mm=float(np.percentile(ls,90)) if ls else 0.,depth=dict(depth),palette_length_mm=dict(palette))


def audit(fixed,native,forest,colors,c,zones,out,baseline):
    out=Path(out);old=Path('outputs/spring-integration-v07');oldrecord=json.loads((old/'record.json').read_text())
    hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in dict(xyz=fixed['base']['xyz'],depth_m=fixed['base']['depth_m'],occupied=fixed['base']['occupied'],retention=fixed['retention']).items()}
    sources=baseline+native['new_sources']+forest['raw']+sum(colors['sources'].values(),[])
    lineage=source_audit(native['ink']+forest['ink']+colors['expanded'],sources)
    # Reconstruct each final cut directly from the recorded already-visible parent.
    parents={r['id']:r for rr in colors['sources'].values() for r in rr};arc_error=0.;envelope_excess=0.
    for channel in ['A','C']:
        for r in colors['channels'][channel]:
            par=parents[r['episodic_parent_id']];a,b=r['episodic_parent_arc_mm'];expected=substring(LineString(par['xy_mm']),a,b)
            arc_error=max(arc_error,LineString(r['xy_mm']).hausdorff_distance(expected))
            # The tapered widths never exceed parent widths at the same arc.
            arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(par['xy_mm'],axis=0),axis=1))];at=a+np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
            envelope_excess=max(envelope_excess,float(np.max(np.array(r['width_profile_mm'])-np.interp(at,arc,par['width_profile_mm']))))
    body=omission=0;Coutside=0;trunk_outside=0;green=0
    for r in colors['channels']['A']+colors['channels']['C']:
        p=resample(r['xy_mm'],.5);q=sample(fixed['base']['depth_m'],p);b=LineString(r['xy_mm']).bounds
        omission+=int((sample(fixed['refined']['global_retention'],p)<=0).sum());green+=int(r['palette_slot'] in ['C1','C2','C3','C4','C5','A5'])
        if r['episodic_channel']=='C':
            ar=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))];at=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];rq=np.interp(at,ar,r['source_forward_profile_m'])
            Coutside+=int(((rq>=1750)|(p[:,1]<=545)).sum())
        for obj in native['objects']:
            if intersects(b,obj['bounds']):body+=int(((q>=sample(obj['q'],p)-25)&(sample(obj['regions']['body'].astype(float),p,order=0)>.5)).sum())
    for r in colors['channels']['trunk']:
        region=colors['regions'][r['structural_region_id']];trunk_outside+=int(not region.buffer(1e-7).covers(LineString(r['xy_mm']).buffer(max(r['width_profile_mm'])/2)))
    exact=0
    for s in native['sites']+[s['site'] for s in forest['sites']]:
        site=s.get('site',s);new=contact(fixed,site['xy_mm']);exact+=int(new['mapped_face_id']==site['mapped_face_id'] and np.allclose(new['source_xyz_utm_m'],site['source_xyz_utm_m'],atol=1e-7))
    oldink=read_vectors(old/'case12_ink.json.gz')['strokes'];oldcolor=read_vectors(old/'case2_color.json.gz')['strokes']
    cases=[tuple(read_vectors(out/f'case{i}_{k}.json.gz')['strokes'] for k in ['ink','color']) for i in range(3)]
    oldvegetation=[r for r in oldcolor if r.get('color_kind')=='vegetation'];newvegetation=[r for r in colors['expanded'] if r.get('color_kind')=='vegetation']
    # Source-space roots are exact; visible grounding remains a separate problem.
    ground=unary_union([LineString(r['xy_mm']) for r in native['ink'] if r.get('source_family') in ['A','rock','Soil']]);roots=[]
    for obj in native['objects']:
        if obj['kind']!='tree':continue
        root=Point(obj['site']['xy_mm']);exposed=any(LineString(r['xy_mm']).distance(root)<3 for r in native['visible_by_owner'][obj['id']] if r['grammar_part']!='foliage-field')
        roots.append(dict(id=obj['id'],root_xy_mm=list(root.coords)[0],visible_root=exposed,nearest_ground_mm=ground.distance(root),visible_ink_paths=len(native['visible_by_owner'][obj['id']])))
    checks=dict(**lineage,fixed_field_hashes_match_v07=hashes==oldrecord['field_sha256'],case0_exact_frozen_ink=digest(cases[0][0])==digest(oldink),case0_exact_frozen_color=digest(cases[0][1])==digest(oldcolor),case0_case1_exact_ink=digest(cases[0][0])==digest(cases[1][0]),case1_nonterrain_color_identical=digest([r for r in cases[0][1] if r.get('color_kind')!='terrain'])==digest([r for r in cases[1][1] if r.get('color_kind')!='terrain']),
        unique_case2_ids=len({r['id'] for r in cases[2][0]+cases[2][1]})==len(cases[2][0]+cases[2][1]),new_color_minimum_3_2_mm=all(length(r)>=3.2-1e-7 for r in colors['expanded']),C_outside_lower_support_samples=Coutside,terrain_green_paths=green,terrain_color_in_hard_body_samples=body,terrain_color_in_absolute_omission_samples=omission,trunk_maximum_width_outside_paired_boundaries=trunk_outside,
        episode_parent_arc_error_mm=arc_error,episode_width_excess_mm=envelope_excess,exact_contact_count=exact,contact_count=len(native['sites'])+len(forest['sites']),RSU_terrain_deleted_mm=forest['terrain_deleted_mm'],long_S_connectors=sum('S-zone-support' in r['id'] for r in forest['color']),B_enabled=c['far_B']['enabled'])
    summary=dict(study=c['study'],parent_commit=c['parent_commit'],validation=checks,field_sha256=hashes,cases={str(i):dict(ink=metrics(ink),color=metrics(color)) for i,(ink,color) in enumerate(cases)},channels={str(i):{k:metrics(read_vectors(out/f'case{i}_channel_{k}.json.gz')['strokes']) for k in colors['channels']} for i in range(3)},
        vegetation=dict(v07=metrics(oldvegetation),v08=metrics(newvegetation)),native_objects=dict(Counter(o['kind'] for o in native['objects'])),forest=dict(roots=len(forest['sites']),rejected=len(forest['rejected']),ink=len(forest['ink']),color=len(forest['color']),by_zone=dict(Counter(s['zone_id'] for s in forest['sites']))),root_contacts=roots,visible_roots_more_than_2mm_from_ground=sum(r['visible_root'] and r['nearest_ground_mm']>2 for r in roots),
        upward_extensions={g['id']:dict(center_mm=g['center_mm'],visible_tree_owners=sum(o['kind']=='tree' and o['group']==g['id'] and bool(native['visible_by_owner'][o['id']]) for o in native['objects'])) for g in c['groups'] if g['id'] in ['left-lower-middle-rise','right-lower-middle-rise','left-bench-transition']},
        limitations=['C is color only; A/B/D baseline source remains unchanged, with catalog-body occlusion recomputed for Case 2.','Case 2 combines placement and vegetation refinements; compare Case 0/1 to isolate A/C changes.','Local crown and contour repetition may remain.','Exact root contacts do not certify visible attachment or full 3D occlusion.','Widths, alpha and pigment appearance remain uncalibrated.'],published=False,merged=False,machine_changes=False)
    (out/'record.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');(out/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    for key in ['fixed_field_hashes_match_v07','case0_exact_frozen_ink','case0_exact_frozen_color','case0_case1_exact_ink','case1_nonterrain_color_identical','unique_case2_ids','new_color_minimum_3_2_mm']:assert checks[key],key
    assert not lineage['missing_source_ids'] and not lineage['profile_errors'] and lineage['maximum_source_arc_error_mm']<1e-6,lineage
    assert body==omission==Coutside==green==trunk_outside==0,checks
    assert arc_error<1e-6 and envelope_excess<1e-8 and exact==checks['contact_count'],checks
    return summary
