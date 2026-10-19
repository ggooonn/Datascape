"""Digital review evidence, separated from physical brush calibration."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,hashlib,json
import numpy as np
from shapely.geometry import LineString,Point,box
from shapely.ops import substring,unary_union
from datascape.integration.visibility import burn,digest
from datascape.integration.cluster_scene import intersects
from datascape.integration.macro_wash import source_basis
from scipy.spatial import cKDTree
from datascape.strokes.vector import resample,sample
from datascape.rendering.spring_checkpoint import channels


def length(r):return LineString(r['xy_mm']).length


def ordered_travel(rows):
    if len(rows)<2:return 0.
    return float(sum(np.linalg.norm(np.asarray(a['xy_mm'][-1])-b['xy_mm'][0]) for a,b in zip(rows[:-1],rows[1:])))


def greedy_travel(rows):
    """Reversible nearest-endpoint heuristic; not a machine route or wetness plan."""
    result=0.
    for slot in sorted({r.get('palette_slot','INK') for r in rows}):
        group=[r for r in rows if r.get('palette_slot','INK')==slot]
        starts=np.array([r['xy_mm'][0] for r in group]);ends=np.array([r['xy_mm'][-1] for r in group]);done=np.zeros(len(group),bool);done[0]=True;p=ends[0]
        for _ in range(1,len(group)):
            d0=np.linalg.norm(starts-p,axis=1);d1=np.linalg.norm(ends-p,axis=1);d=np.minimum(d0,d1);d[done]=np.inf;i=int(np.argmin(d));result+=d[i];p=ends[i] if d0[i]<=d1[i] else starts[i];done[i]=True
    return float(result)


def channel_metrics(rows):
    lengths=np.array([length(r) for r in rows]);seam=LineString([(300,0),(300,900)])
    counts=Counter();lengths_by=defaultdict(float)
    for r,l in zip(rows,lengths):
        key=r.get('palette_slot',r.get('source_family',r['layer']));counts[key]+=1;lengths_by[key]+=float(l)
    return dict(paths=len(rows),total_length_mm=float(lengths.sum()),minimum_mm=float(lengths.min()) if len(rows) else 0.,
        bins={name:int(((lengths>=a)&(lengths<b)).sum()) for name,a,b in [('lt_0.9',0,.9),('0.9_to_2.8',.9,2.8),('2.8_to_3.2',2.8,3.2),('3.2_to_5',3.2,5),('5_to_10',5,10),('10_plus',10,np.inf)]},
        starts=len(rows),stops=len(rows),between_path_lifts=max(0,len(rows)-1),listed_travel_mm=ordered_travel(rows),
        slot_grouped_greedy_travel_mm=greedy_travel(rows),seam_crossing_paths=sum(LineString(r['xy_mm']).crosses(seam) for r in rows),
        counts_by_layer_or_slot=dict(counts),lengths_by_layer_or_slot_mm=dict(lengths_by),
        route_limit='Listed order is archival. Greedy figure excludes stations/inter-slot travel, clearance, wetness, reload and seams; not executable motion.')


def source_audit(records,sources):
    lookup={r['id']:r for r in sources};maximum=0.;missing=[];profiles=[]
    for r in records:
        for k in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
            if k in r and len(r[k])!=len(r['xy_mm']):profiles.append([r['id'],k])
        key=r['source_stroke_id'];src=lookup.get(key)
        if src is None:
            if r['id'] in lookup and r['id']==key:src=r
            else:missing.append(key);continue
        a,b=r['source_arc_mm'];expected=substring(LineString(src['xy_mm']),a,b)
        maximum=max(maximum,float(expected.hausdorff_distance(LineString(r['xy_mm']))))
    return dict(maximum_source_arc_error_mm=maximum,missing_source_ids=sorted(set(missing)),profile_errors=profiles)


def audit(fixed,native,forest,colors,config,output,baseline):
    output=Path(output);control,cs=channels();ink=native['ink']+forest['ink'];c1=colors['restrained'];c2=colors['expanded']
    sources=baseline+native['new_sources']+forest['raw']+sum(colors['sources'].values(),[])
    lineage=source_audit(ink+c2,sources)
    old=json.loads((Path('docs/checkpoints/spring_integration_v04/artifacts/record.json')).read_text())
    hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in dict(xyz=fixed['base']['xyz'],depth_m=fixed['base']['depth_m'],occupied=fixed['base']['occupied'],retention=fixed['retention']).items()}
    field_equal={k:hashes[k]==old['field_sha256'][k] for k in hashes}
    current={s['object_id']:s for s in native['sites']};original=json.loads(Path('docs/checkpoints/spring_integration_v04/artifacts/sites.json').read_text());original={s['object_id']:s for s in original}
    rows=[]
    for row in csv.DictReader(open('docs/checkpoints/spring_integration_v04/placement_inventory.csv')):
        ident=row['object_id'];new=current.get(ident)
        if new is None:action='removed tree site / replaced mid-far role' if row['kind']=='tree' else 'old Soil support not regenerated'
        else:
            oldsite=original[ident];changed=np.linalg.norm(np.array(new['site']['xy_mm'])-oldsite['site']['xy_mm'])>1e-6 or new.get('height_mm')!=oldsite.get('height_mm') or new.get('support_bounds_mm')!=oldsite.get('support_bounds_mm')
            action='repositioned / native-size rebuilt' if changed else 'retained provisional placement'
        rows.append({**row,'v05_action':action})
    with open(output/'placement_audit_119.csv','w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    common=fixed['base']['occupied']&(fixed['retention']>.23)&(fixed['refined']['global_retention']>0)
    q=fixed['base']['depth_m'];focus=colors['context']['slope_focus']
    basis=source_basis(fixed,np.nan_to_num(fixed['base']['xyz']));anchors=source_basis(fixed,[x['source_xyz_m'] for x in colors['anchors']])
    scale=np.array([185.,650.]);_,nearest=cKDTree(anchors[:,:2]/scale).query((basis[...,:2]/scale).reshape(-1,2))
    descent=anchors[nearest,2].reshape(q.shape)-basis[...,2]
    zones=dict(focused_upper=common&(q>=1600)&(focus>.1)&(descent>=-80)&(descent<=120),focused_lower=common&(q>=1600)&(focus>.1)&(descent>120)&(descent<=650),adjacent_midfar=common&(q>=1600)&(focus<=.10),near=common&(q<800),middle=common&(q>=800)&(q<2200),far=common&(q>=2200))
    spatial={}
    for key,mask in zones.items():
        totals=[]
        for rr in [cs['A'],colors['channels']['A']]:
            value=0.
            for r in rr:
                p=resample(r['xy_mm'],.6);mid=(p[:-1]+p[1:])/2;inside=sample(mask.astype(float),mid,order=0)>.5
                value+=float(np.linalg.norm(np.diff(p,axis=0),axis=1)[inside].sum())
            totals.append(value)
        area=int(mask.sum());spatial[key]=dict(area_mm2=area,v04_A_length_mm=totals[0],v05_A_length_mm=totals[1],v04_density_mm_per_mm2=totals[0]/max(1,area),v05_density_mm_per_mm2=totals[1]/max(1,area))
    # Fixed one-mm proxy of maximum width, deliberately conservative at crossings.
    overlap=np.zeros((900,600),np.uint16)
    for r in c2:overlap+=burn(LineString(r['xy_mm']).buffer(max(r.get('width_profile_mm',[r['width_mm']]))/2))
    ground=unary_union([LineString(r['xy_mm']) for r in ink if r.get('source_family') in ['A','rock','Soil']]);contacts=[]
    for o in native['objects']:
        if o['kind']!='tree':continue
        root=Point(o['site']['xy_mm']);exposed=any(LineString(r['xy_mm']).distance(root)<3 for r in native['visible_by_owner'][o['id']] if r['grammar_part']!='foliage-field')
        contacts.append(dict(object_id=o['id'],visible_root_proxy=exposed,nearest_ground_centerline_mm=ground.distance(root)))
    terrain_color=[r for r in c2 if r.get('owner_id') in ['terrain-A','terrain-C','terrain-C-field']]
    omitted_samples=0;body_samples=0;trunk_outside=0
    for r in terrain_color:
        pp=resample(r['xy_mm'],.5);omitted_samples+=int((sample(fixed['refined']['global_retention'],pp)<=0).sum())
        qq=sample(fixed['base']['depth_m'],pp);bounds=LineString(r['xy_mm']).bounds
        for obj in native['objects']:
            if not intersects(bounds,obj['bounds']):continue
            body_samples+=int(((qq>=sample(obj['q'],pp)-25)&(sample(obj['regions']['body'].astype(float),pp,order=0)>.5)).sum())
    for r in colors['channels']['trunk']:
        region=colors['regions'][r['structural_region_id']]
        trunk_outside+=int(not region.buffer(1e-7).covers(LineString(r['xy_mm']).buffer(max(r['width_profile_mm'])/2)))
    checks=dict(terrain_color_samples_in_absolute_omission=omitted_samples,terrain_color_samples_in_hard_object_bodies=body_samples,trunk_maximum_width_outside_paired_boundaries=trunk_outside,case1_case2_identical_ink=True,ink_digest=digest(ink),case1_color_exact_subset=all(r in c2 for r in c1),
        unique_ids=len({r['id'] for r in ink+c2})==len(ink+c2),legacy_V_paths=sum(r.get('source_family')=='V' for r in ink),
        field_hashes_equal=field_equal,color_minimum_3_2=all(length(r)>=3.2-1e-7 for r in c2),**lineage,
        RSU_terrain_deleted_mm=forest['terrain_deleted_mm'],B_enabled=False,pressure_calibrated=False)
    report=dict(source_commit=config['parent_commit'],recovery_note=config['recovery_note'],validation=checks,field_sha256=hashes,
        cases=dict(case0_ink=channel_metrics(control),case0_color=channel_metrics(cs['caseC']),case12_ink=channel_metrics(ink),case1_color=channel_metrics(c1),case2_color=channel_metrics(c2)),
        placement_actions=dict(Counter(r['v05_action'] for r in rows)),native_objects=dict(Counter(o['kind'] for o in native['objects'])),
        RSU=dict(sites=len(forest['sites']),rejected=len(forest['rejected']),ink=len(forest['ink']),color=len(forest['color']),by_passage=dict(Counter(s['id'].split('/patch-')[0] for s in forest['sites']))),
        channels={k:dict(paths=len(v),length_mm=sum(map(length,v)),raw_paths=len(colors['raw'].get(k,[])),raw_length_mm=sum(map(length,colors['raw'].get(k,[])))) for k,v in colors['channels'].items()},
        A_spatial_comparison=spatial,root_contacts=contacts,visible_roots_more_than_2mm_from_ground=sum(r['visible_root_proxy'] and r['nearest_ground_centerline_mm']>2 for r in contacts),
        footprint_proxy=dict(grid_mm=1,covered_mm2=int((overlap>0).sum()),at_least_3_mm2=int((overlap>=3).sum()),at_least_6_mm2=int((overlap>=6).sum()),maximum_overlap=int(overlap.max()),physical_accumulation_validated=False),
        layout=dict(continuous_mm=[600,900],panel_boundary_x_mm=300,display_gap_mm=40,gap_in_drawing_coordinates=False,seam_split_implemented=False),
        short_ink_records=[dict(id=r['id'],source_id=r['source_stroke_id'],family=r['source_family'],length_mm=length(r),canonical_source_preserved=True) for r in ink if length(r)<2.8],
        station_configuration=dict(path='hardware/fluidnc/tool_coordinates.yaml',status='unverified',coordinate_frame=None,well_mapping_1_2=None,paint_slots=20,physical_station_mapping_validated=False),
        physical_readiness='Not ready for plotting: measured footprint, short-contact, pigment, wetness and station/frame tests are pending. No YAML or G-code created.')
    (output/'record.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');(output/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    assert all(field_equal.values()) and checks['case1_color_exact_subset'] and checks['color_minimum_3_2'] and checks['unique_ids']
    assert not lineage['profile_errors'] and not lineage['missing_source_ids'] and lineage['maximum_source_arc_error_mm']<1e-6
    return report
