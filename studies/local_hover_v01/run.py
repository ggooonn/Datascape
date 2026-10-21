"""Fixed-S3a local-hover study and incomplete, comment-only Spring review package."""
import argparse,gzip,json,hashlib,subprocess
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict
from collections import defaultdict
from math import dist
from time import perf_counter
from datascape.gcode.binding import load_bound_spring,digest
from datascape.gcode.layout import Layout
from datascape.gcode.production.sequence import reference_order,make_plan,verify_plan,SLOT_ORDER
from datascape.gcode.production.exporter import save_json,verify_draw_lineage
from datascape.gcode.production.profiles import require_physical_layout
from datascape.gcode.production.motion_comparison import unverified_yaml_axes
from datascape.gcode.production.costs import audit_continuity
from .config import candidate_profile,curve_knots
from .review import Review,with_local,timing,write_preview

PIN='12b28bd5b7ad575b1438ed5af61618746c7effe9'
PREVIOUS='cc83b34f18c2498b0f6dd4f559333c9cbfe8e307'


def routing_audit(strokes,order,reference,pressure_root):
    def xy(s):return (s.points[0].x,s.points[0].y),(s.points[-1].x,s.points[-1].y)
    rows=[]
    for slot in SLOT_ORDER:
        before=[s for s in strokes if s.medium=='color' and s.color_slot==slot]
        after=[strokes[i] for i in order if strokes[i].medium=='color' and strokes[i].color_slot==slot]
        def length(ss):return sum(dist(xy(a)[1],xy(b)[0]) for a,b in zip(ss,ss[1:]))
        rows.append({'slot':slot,'sources':len(after),'grouped_original_XY_mm':length(before),'S3a_XY_mm':length(after),
                     'order_differs_from_grouped_source': [s.stroke_id for s in before]!=[s.stroke_id for s in after]})
    sources={}
    for name in ['study_v02.py','optimization.py']:
        p=reference/'source'/name
        sources[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
          'S3a_code_excerpt': '\n'.join(p.read_text().splitlines()[234:242]) if name=='study_v02.py' else
          'schedule(route=True): min ready same-color source by squared distance from previous endpoint to candidate start; no stroke reversal; DAG-ready pool only'}
    archived=reference/'results/schedules/S3a.execution_order.json.gz'
    if hashlib.sha256(archived.read_bytes()).hexdigest()!='df46a0aed239813af6b79f082b0551a447ca7198d421e28e8d8609b2b8d9c48f':raise ValueError('wrong original S3a archive')
    rich=[]
    for medium in ('ink','color'):
        rich+=json.loads(gzip.decompress((pressure_root/'artworks/spring_v13'/('visible_'+medium+'.json.gz')).read_bytes()))['strokes']
    if len(rich)!=len(strokes) or any(r['id']!=s.stroke_id for r,s in zip(rich,strokes)):raise ValueError('rich object/source identity mismatch')
    field={'terrain-A','terrain-C','terrain-C-field'};groups=defaultdict(list)
    for rank,i in enumerate(order):
        owner=rich[i].get('owner_id')
        if owner and owner not in field:groups[(owner,strokes[i].medium,strokes[i].color_slot)].append(rank)
    repeated={k:v for k,v in groups.items() if len(v)>1}
    return {'per_color':rows,'algorithm_sources':sources,'S3a_archived_order_sha256':hashlib.sha256(archived.read_bytes()).hexdigest(),
            'ink_order_original_and_unoptimized':True,'color_routing':'directed nearest-ready endpoint/start heuristic inside each color batch; not merely grouping; not globally optimal',
            'grouped_original_total_XY_mm':sum(r['grouped_original_XY_mm'] for r in rows),'S3a_total_XY_mm':sum(r['S3a_XY_mm'] for r in rows),
            'optional_same_object':{'applied':False,'source_flags_allow_reordering':any(s.reorderable for s in strokes),
                'field_owners_excluded':sorted(field),'repeated_owner_material_groups':len(repeated),
                'groups_with_intervening_other_strokes':sum(any(b>a+1 for a,b in zip(v,v[1:])) for v in repeated.values()),
                'reason':'owner membership alone is not proof of compositing independence; no new order or edge changes evaluated'}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('machine','provenance','pressure-root','routing-reference','output'):p.add_argument('--'+arg,required=True,type=Path)
    a=p.parse_args();root=Path('.');out=a.output
    if out.exists():raise ValueError('output must be new')
    out.mkdir(parents=True);began=perf_counter()
    strokes,_=load_bound_spring(a.machine,a.provenance);order=reference_order(strokes,root/'config/plotter_v03/spring_s3a_order.json')
    profile=candidate_profile(root);save_json(out/'profile.provisional.json',profile.data)
    old=json.loads(subprocess.check_output(['git','show',PREVIOUS+':studies/brush_pressure_three_region_v01/results/full_study.json'],text=True))
    low={'start_work_xyz':[800,900,32],'axis_max_rate_mm_min':[15000,15000,6000],
         'axis_acceleration_mm_s2':[100,100,20],'junction_deviation_mm':.01}
    rates,acc=unverified_yaml_axes(root/'hardware/fluidnc/config_DEV_2026-10-10_UNVERIFIED.yaml');dev=dict(low,axis_max_rate_mm_min=rates,axis_acceleration_mm_s2=acc)
    report={'schema':'datascape.local_hover_study.v01','backend_pin':PIN,'S3a_routing':routing_audit(strokes,order,a.routing_reference,a.pressure_root),
        'actual_station_handling_seconds':None,'actual_full_execution_seconds':None,'physical_clearance_verified':False,
        'model_assumptions':{'synthetic_low':low,'unverified_DEV':dev,'approach_boundary_mm':1,
            'timing_only_wet_departure_arrival_mm':[10,10],
            'start':'provisional park, not measured machine start','station_transport':'nominal historical centers only; actual sloped exits unresolved',
            'unresolved_station_timing':'excluded with rest boundaries in model, not presumed zero; prior study fixed station allowance shown separately',
            'curve_budget_fractions_after_preload':{'.4':.08,'.6':.24,'.93':.85}},'layouts':{}}
    report['blockers']={}
    for stage in ('air','calibration','painting'):
        slots=[] if stage!='painting' else list(SLOT_ORDER)
        issues=profile.issues(stage,slots)
        if stage=='painting':
            try:require_physical_layout(profile,{'layout':{'mode':'D'}},stage)
            except ValueError as e:issues.append(str(e))
        report['blockers'][stage]=issues
    preferred=(5,10)
    context={'authorized':False,'profile_local_hover_enabled':False,
             'hypothetical_local_hover':{'height_mm':5,'max_distance_mm':10},
             'clearance_verified':False,'approach_boundary_mm':1,
             'wet_departure_arrival_mm':[10,10],
             'meaning':'Offline overrides only; the physical profile is incomplete and local hover is disabled'}
    save_json(out/'REVIEW_CONTEXT.json',context)
    for mode in ('D','A'):
        jobs,manifest=make_plan(strokes,Layout(mode),order);plan=out/(mode+'.plan.json.gz');save_json(plan,manifest)
        verified=verify_plan(json.loads(gzip.decompress(plan.read_bytes())),strokes,Layout(mode))
        crossing={s.stroke_id for s in strokes if min(p.x for p in s.points)<300<max(p.x for p in s.points)}
        results={}
        for preload in (2,3):
            data=deepcopy(profile.data)
            for b in data['brush_profiles'].values():b['knots']=curve_knots(preload)
            from datascape.gcode.production.profiles import Profile
            case_profile=Profile.from_dict(data);rows={}
            for name,units in jobs.items():
                review=Review(case_profile,low);commands,links=review.build(units)
                lineage=verify_draw_lineage(commands,manifest['jobs'][name],case_profile,'fixture')
                continuity=audit_continuity(commands,crossing) if mode=='D' else None
                row={'source_lineage':lineage,'D_continuity':continuity,'reloads':review.reloads,'full_washes':review.washes,'PURGE_contacts':review.purges,
                     'same_order_XY_transition_mm':sum(x['distance_mm'] for x in links),'curve_knots':curve_knots(preload),
                     'prior_fixed_station_allowance_hours':old['layouts'][mode]['curves']['three_region_10'][name]['unverified_DEV']['acceleration_sensitive_seconds_by_category']['station_handling']/3600,
                     'cases':{}}
                if mode=='D' and preload==2:save_json(out/(name+'.transitions.json.gz'),links)
                for height,threshold in [(10,None)]+[(h,d) for h in (5,3) for d in (5,10,20,30)]:
                    altered,metrics=(commands,{'conditional_local_transitions':0,'local_XY_mm':0.,'reduced_Z_mm':0.,'clearance_verified':False,'physically_authorized_local_transitions':0}) if height==10 else with_local(commands,links,height,threshold)
                    case={'local_height_mm':height,'max_distance_mm':threshold,**metrics,
                          'partial_commanded_feed_and_low_model':timing(altered,low),
                          'partial_DEV_model':timing(altered,dev)}
                    row['cases'][f'H{height}_D{threshold}']=case
                    if mode=='D' and preload==2 and (height,threshold)==preferred:
                        verify_draw_lineage(altered,manifest['jobs'][name],case_profile,'fixture');audit_continuity(altered,crossing)
                        check=write_preview(out/(name+'.preview.txt.gz'),altered,case_profile,digest(manifest),name,context)
                        row['preferred_preview_readback']=check
                        with gzip.open(out/(name+'.trajectory.jsonl.gz'),'wt',encoding='utf-8') as f:
                            for c in altered:f.write(json.dumps(asdict(c),sort_keys=True,separators=(',',':'))+'\n')
                        text=gzip.decompress((out/(name+'.preview.txt.gz')).read_bytes()).decode().splitlines()
                        (out/(name+'.example.txt')).write_text('\n'.join(text[:160]+['; ... FULL COMMENT-ONLY PREVIEW CONTINUES IN GZIP ...']+text[-15:])+'\n')
                rows[name]=row
                print(mode,'preload',preload,name,'reload',review.reloads,'preferred',round(row['cases']['H5_D10']['partial_DEV_model']['acceleration_sensitive_seconds']/3600,3),flush=True)
                del commands,links
            results[str(preload)]=rows
        report['layouts'][mode]={'plan_sha256':digest(manifest),'plan_readback':verified,'preloads':results}
        del jobs,manifest
    report['elapsed_seconds']=perf_counter()-began;save_json(out/'study_results.json',report)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    save_json(out/'MANIFEST_SHA256.json',hashes)


if __name__=='__main__':main()
