"""PR43-frozen color composition with source-atomic hybrid replenishment."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from math import hypot
import argparse, gzip, hashlib, html, json, shutil, subprocess, zipfile
from . import spring_color_execution as c
from .spring_color_verify import command, decode_coupon

BASE_COMMIT='8f7b1bb0ec2cd0b9fee639f370afe3b0518fa92b'
POLICY=c.ROOT/'config/spring_color_hybrid_v02/policy.json'
OLD='docs/spring_color_execution_v01/review/'
DOC=c.ROOT/'docs/spring_color_hybrid_v02'
PRIMARY='SPRING_P2_COLOR_PR35_HYBRID15_COMPLETE_REVIEW'
STAGES=['01_MINERAL_BASE','02_PALE_GROWTH_AND_LOCAL_OVERLAP','03_GROUPED_CORES','04_FRESH_TIPS_AND_ACCENTS']


def pinned(path):
    return subprocess.check_output(['git','show',BASE_COMMIT+':'+path],cwd=c.ROOT)


def pinned_json(path):
    data=pinned(path)
    return json.loads(gzip.decompress(data) if path.endswith('.gz') else data)


def normalized(value):return json.loads(json.dumps(value))


def locked_inputs(context,policy):
    original=pinned_json('config/spring_color_execution_v01/policy.json')
    allowed={'schema','contact_limit','reload_status','baseline_color_commit','comparison_contact_limits'}
    c.require({k:v for k,v in policy.items() if k not in allowed}==
        {k:v for k,v in original.items() if k not in allowed},'Revision changed composition or physical parameters')
    c.require(policy['baseline_color_commit']==BASE_COMMIT and policy['contact_limit']==15,'Pinned conservative first-test policy')
    context=c.recover(context,policy)
    plan,color,ink,units,palette=c.load_inputs(context,policy)
    c.overlap_audit(units,ink,policy);selected=c.select(units,policy)
    records=[c.unit_record(u) for u in units]
    index=[{k:v for k,v in r.items() if k!='clipped_fragments'} for r in records]
    c.require(normalized(index)==pinned_json(OLD+'source_selection.index.json.gz'),'PR43 source selection, slot, dose or provenance changed')
    edges,shapes=c.layering(selected);order,batches,wet=c.schedule(selected,edges,policy)
    graph=pinned_json(OLD+'layering_constraints.json.gz')
    c.require(graph['edges']==normalized(edges) and graph['unit_ids']==[u['id'] for u in selected],'PR43 layering changed')
    schedule=dict(batches=[b|dict(source_count=len(b['unit_indices']),
        drawing_length_mm=sum(selected[i]['length_mm'] for i in b['unit_indices'])) for b in batches],wet_opportunity=wet)
    c.require(normalized(schedule)==pinned_json(OLD+'schedule.json'),'PR43 source or pigment order changed')
    profile=c.make_profile(policy)
    c.require(profile.data==pinned_json(OLD+'profile.color.UNMEASURED.json'),'Color compression/machine/station/feed profile changed')
    return context,units,selected,order,batches,records,profile,schedule


def paper_blocks(text):
    result=[];active=None
    for line in text.splitlines():
        if line.startswith('; source_fragment_begin'):
            c.require(active is None,'Nested paper fragment');active=[line]
        elif line.startswith('; source_fragment_complete'):
            c.require(active is not None,'Unopened paper fragment');active.append(line);result.append(active);active=None
        elif active is not None:active.append(line)
    c.require(active is None,'Unclosed paper fragment')
    return result


def audit_material(commands,material,units,order,policy):
    """Reconstruct counters from IR paper contacts and actual XY draw motions."""
    unit_map={u['id']:u for u in units};expected_ids=[units[i]['id'] for i in order]
    loads=material['loads'];load_cursor=0;events=material.get('events',[]);event_cursor=0
    pos=(0,900,35);loaded=None;distance=0.;contacts=0;active=None;source_distance=0.;source_contacts=0
    wash=rewet=cloth=0;completed=[];terminal=False;load_rows=[];max_contacts=0;max_distance=0.
    def thresholds():
        return (['distance_limit'] if distance>=policy['distance_limit_mm'] else [])+(
            ['contact_limit'] if policy['contact_limit'] is not None and contacts>=policy['contact_limit'] else [])
    for k,cmd in enumerate(commands):
        if active is not None:c.require(not cmd.action.startswith('station_') and cmd.action not in ('wash','controlled_rewet'),
            'Station service inserted before completing the current source')
        if cmd.kind=='move':
            if cmd.action=='initial_contact':
                c.require(active is not None,'Paper contact outside a complete source')
                source_contacts+=1;contacts+=1
            if cmd.action=='draw':
                c.require(active is not None,'Drawing outside source')
                step=hypot(cmd.xyz[0]-pos[0],cmd.xyz[1]-pos[1]);distance+=step;source_distance+=step
            pos=cmd.xyz
        if cmd.action=='wash':wash+=1
        elif cmd.action=='controlled_rewet':rewet+=1
        # Absorbent primitive is separately checked below using operation records.
        elif cmd.action=='terminal_cleanup_begin':terminal=True
        elif cmd.action.startswith('material_loaded_'):
            c.require(active is None and not terminal,'Material service inside source or after terminal cleanup')
            slot=cmd.action.removeprefix('material_loaded_');triggers=thresholds()
            reasons=['initial_load'] if loaded is None else ['pigment_change'] if loaded!=slot else triggers
            c.require(bool(reasons),'Unnecessary early same-pigment replenishment')
            c.require(load_cursor<len(loads),'IR load missing from material audit')
            row=loads[load_cursor];load_cursor+=1
            c.require(row['distance_limit_mm']==policy['distance_limit_mm'] and row['contact_limit']==policy['contact_limit'],
                'Material record declares the wrong hybrid policy')
            c.require(row['slot']==slot and row['previous_slot']==loaded and row['reasons']==reasons,'Material/trigger audit mismatch')
            c.require(row['threshold_reasons_before_service']==triggers,'Simultaneous threshold audit mismatch')
            c.require(abs(row['previous_distance_mm']-distance)<1e-7 and row['previous_contacts']==contacts,'Reload counter mutation')
            c.require(row['after_load_budget']==dict(distance_mm=0.,actual_paper_contacts=0),'Both counters must reset')
            c.require(row['last_command']==k-1,'Pigment-load IR boundary mismatch')
            change=loaded is not None and loaded!=slot
            c.require(row['wash_performed']==change and wash==int(change) and rewet==int(change),'Washing or rewet on an incorrect material transition')
            load_rows.append(dict(slot=slot,reasons=reasons,previous_distance_mm=distance,previous_contacts=contacts))
            loaded=slot;distance=0.;contacts=0;wash=rewet=0
        elif cmd.action=='source_begin':
            c.require(active is None and not terminal and loaded is not None,'Invalid source boundary/material state')
            c.require(not thresholds(),'Required hybrid replenishment missing before next complete source')
            active=cmd.source_id;source_distance=0.;source_contacts=0
            c.require(loaded==unit_map[active]['physical_slot'],'Wrong physical pigment')
            c.require(event_cursor<len(events),'Missing source budget event')
            row=events[event_cursor]
            c.require(row['before']==dict(distance_mm=row['before']['distance_mm'],actual_paper_contacts=contacts) and
                abs(row['before']['distance_mm']-distance)<1e-7,'Source-entry budget mismatch')
        elif cmd.action=='source_complete':
            c.require(active==cmd.source_id,'Source continuity changed')
            u=unit_map[active];row=events[event_cursor];event_cursor+=1
            c.require(source_contacts==len(u['fragments']) and row['actual_paper_contacts']==source_contacts,'Contacts counted as vertices or source records')
            c.require(abs(source_distance-u['length_mm'])<1e-7,'Drawing length changed')
            c.require(row['source_id']==active and row['contacts_since_load']==contacts and
                abs(row['distance_since_load_mm']-distance)<1e-7,'Post-source hybrid counters changed')
            c.require(row['threshold_reasons_after_source']==thresholds(),'Post-source threshold audit')
            over=max(0,contacts-policy['contact_limit']) if policy['contact_limit'] is not None else 0
            c.require(row['atomic_contact_overrun']==over,'Atomic contact-overrun audit')
            max_contacts=max(max_contacts,contacts);max_distance=max(max_distance,distance)
            completed.append(active);active=None
    c.require(active is None and completed==expected_ids,'Complete-source order/coverage')
    c.require(load_cursor==len(loads) and event_cursor==len(events),'Unconsumed material/source audit records')
    changes=sum(r['reasons']==['pigment_change'] for r in load_rows)
    c.require(changes==material['pigment_changes'],'Pigment-change total mismatch')
    operations=material['station_operations']
    c.require(sum(r['action']=='wash' for r in operations)==changes,'Same-pigment wash in operation audit')
    c.require(sum(r['action']=='controlled_rewet' for r in operations)==changes,'Rewet count mismatch')
    c.require(sum(r['action']=='terminal_wash' for r in operations)==3,'Terminal cleanup changed')
    c.require(sum(r['action']=='pigment_load' for r in operations)==len(load_rows),'Station load-visit count mismatch')
    c.require(sum(cmd.action=='terminal_wash' for cmd in commands)==3,'Terminal IR wash count')
    c.require(pos==(800,800,35),'Terminal park changed')
    return dict(source_atomic_service_verified=True,actual_paper_contacts=sum(e['actual_paper_contacts'] for e in events),
        total_loads=len(load_rows),pigment_changes=changes,
        maximum_contacts_since_load=max_contacts,maximum_distance_since_load_mm=max_distance,
        load_budget_sha256=c.digest(load_rows),both_counters_reset=True,same_pigment_washes=0,
        contacts_from_initial_contact_IR_not_vertices=True)


def diagnostic(material):
    keys=['source_count','contact_count','drawing_length_mm','total_loads','initial_loads','pigment_changes',
        'same_pigment_reloads','same_pigment_trigger_counts','maximum_contacts_since_load',
        'maximum_distance_since_load_mm','maximum_atomic_contact_overrun','maximum_atomic_distance_overrun_mm']
    result={k:material[k] for k in keys}
    result['loads_by_slot']=dict(Counter(r['slot'] for r in material['loads']))
    result['station_operation_visits']=len(material['station_operations'])
    return result


def generate(context,output):
    policy=c.read(POLICY);out=Path(output);c.require(not out.exists(),'Use a fresh output directory');out.mkdir(parents=True)
    print('Checking exact PR43 composition, palette, pressure and layering',flush=True)
    context,units,selected,order,batches,records,profile,schedule=locked_inputs(context,policy)
    c.save(out/'policy.json',policy);c.save(out/'profile.color.UNMEASURED.json',profile.data)
    c.save(out/'source_selection.json.gz',records);c.save(out/'schedule.json',schedule)
    full_manifest=pinned_json(OLD+'FULL_GENERATED_MANIFEST_SHA256.json')
    c.require(c.sha(out/'source_selection.json.gz')==full_manifest['source_selection.json.gz'],'Full PR43 source geometry/pressure/dose changed')
    for name in ['layering_constraints.json.gz','source_selection.index.json.gz','source_to_slot_replacements.json',
        'source_to_slot_replacements.csv','future_dual_brush_compatibility.json.gz','PR35_overlap_audit.json.gz',
        'D4_restrained_comparison.json','fine_color_OFFLINE_ONLY.json','P2_comparison.png','P2_sequence.png']:
        (out/name).write_bytes(pinned(OLD+name))
    comparisons={};primary=None;primary_commands=None
    for limit in [None]+policy['comparison_contact_limits']:
        cfg=deepcopy(policy);cfg['contact_limit']=limit;label='distance_only_PR43' if limit is None else 'contact_'+str(limit)
        print('Generating and auditing',label,flush=True)
        commands,material=c.build(selected,order,profile,cfg)
        proof=audit_material(commands,material,selected,order,cfg)
        timing=c.runtime(commands,profile);ref=timing['models']['configuration_reference']
        row=diagnostic(material)|dict(contact_limit=limit,modeled_seconds=ref['acceleration_sensitive_seconds'],
            modeled_seconds_by_category=ref['acceleration_sensitive_seconds_by_category'],
            commanded_seconds=ref['commanded_feed_seconds'],material_proof=proof)
        text=c.BANNER+c._serialize(commands,profile,c.digest([selected[i]['id'] for i in order]),
            'SPRING_P2_COLOR_PR35_COMPLETE_REVIEW' if limit is None else PRIMARY,'painting')
        old=gzip.decompress(pinned(OLD+'SPRING_P2_COLOR_PR35_COMPLETE_REVIEW.gcode.gz')).decode()
        c.require(paper_blocks(text)==paper_blocks(old),'PR43 numerical paper geometry/pressure/feed order changed')
        if limit is None:
            c.require(text==old,'Distance-only control is not byte-identical to PR43')
            row['exact_PR43_Gcode_control_sha256']=hashlib.sha256(text.encode()).hexdigest()
        else:c.verify_numeric(text,commands,profile,selected,order,cfg)
        c.save(out/(label+'.material.json.gz'),material)
        comparisons[label]=row
        if limit==policy['contact_limit']:
            primary,readbacks=c.export_program(out,PRIMARY,selected,order,profile,cfg,commands,material)
            primary_commands=commands
            primary['material_proof']=proof
            air_timing=c.runtime(c.air_projection(commands,profile),profile)
            row['AIR_modeled_seconds']=air_timing['models']['configuration_reference']['acceleration_sensitive_seconds']
        if commands is not primary_commands:del commands
    c.save(out/'reload_comparison.json',comparisons)
    primary['material_proof']=comparisons['contact_15']['material_proof']
    stages={};all_stage_ids=[]
    group_slots=[{'A2','A4'},{'C1','EARLY_C2'},{'A5','C3'},{'C2','D1'}]
    for label,slots in zip(STAGES,group_slots):
        chosen={i for b in batches if ('EARLY_C2' if b['purpose']=='local C1-to-C2 overlap opportunity' else b['slot']) in slots for i in b['unit_indices']}
        ids=[i for i in order if i in chosen]
        print('Reference alternative stage',label,flush=True)
        name='SPRING_P2_COLOR_PR35_HYBRID15_'+label+'_REVIEW'
        cs,ms=c.build(selected,ids,profile,policy);proof=audit_material(cs,ms,selected,ids,policy)
        ms,reports=c.export_program(out,name,selected,ids,profile,policy,cs,ms)
        text=(out/(name+'.gcode')).read_text()
        old=gzip.decompress(pinned(OLD+'SPRING_P2_COLOR_PR35_'+label+'_REVIEW.gcode.gz')).decode()
        c.require(paper_blocks(text)==paper_blocks(old),'Stage paper program changed')
        all_stage_ids.extend(ids);stages[label]=diagnostic(ms)|dict(modeled_seconds=ms['modeled_seconds'],material_proof=proof)
    c.require(all_stage_ids==order,'Stage partition differs from complete source order')
    c.calibration_outputs(out,selected,profile,policy)
    for name in ['SPRING_P2_COLOR_RESPONSE_COUPON_SPARE_ONLY_REVIEW','SPRING_P2_AIR_RESPONSE_COUPON_SPARE_ONLY_REVIEW',
                 'SPRING_P2_COLOR_STATIONS_ONLY_REVIEW','SPRING_P2_AIR_STATIONS_ONLY_REVIEW']:
        c.require((out/(name+'.gcode.gz')).read_bytes()==pinned(OLD+name+'.gcode.gz'),'PR43 color-response coupon or station trace changed')
    preservation=dict(base_commit=BASE_COMMIT,original_source_selection_sha256=c.sha(out/'source_selection.json.gz'),
        unchanged_original_geometry_pressure_widths_and_dose=True,unchanged_six_slots_and_pigment_order=True,
        unchanged_layering_and_source_order=True,unchanged_profile_sha256=profile.sha256,
        numerical_paper_blocks_equal_PR43=True,distance_only_control_byte_identical=True,
        coupon_and_station_COLOR_AIR_byte_identical=True,existing_PRs_modified=False)
    c.save(out/'PR43_preservation.json',preservation)
    summary=dict(preferred_contact_limit=15,distance_limit_mm=600,primary_program=PRIMARY,
        pigment_order=[b['slot'] for b in batches],selected_sources=len(selected),
        primary=diagnostic(primary)|dict(modeled_seconds=primary['modeled_seconds'],
            modeled_seconds_by_category=primary['modeled_seconds_by_category'],
            AIR_modeled_seconds=comparisons['contact_15']['AIR_modeled_seconds']),
        stages=stages,comparisons=comparisons,preservation=preservation,
        physical_color_response_measured=False,machine_authorized=False,
        role='Complete COLOR/AIR pair primary; four-stage files are mutually exclusive reference alternatives')
    c.save(out/'summary.json',summary)
    from .spring_color_hybrid_review import review
    review(out,summary,primary_commands,selected,order)
    c.save(out/'MANIFEST_SHA256.json',{p.name:c.sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='MANIFEST_SHA256.json'})
    print(json.dumps({k:dict(loads=v['total_loads'],minutes=v['modeled_seconds']/60) for k,v in comparisons.items()},indent=2),flush=True)
    return summary


def verify(output,context,independent=None):
    out=Path(output);policy=c.read(out/'policy.json');c.require(policy==c.read(POLICY),'Hybrid policy changed')
    hashes=c.read(out/'MANIFEST_SHA256.json')
    for name,expected in hashes.items():c.require(c.sha(out/name)==expected,'Delivered byte mutation: '+name)
    context,units,selected,flat,batches,records,profile,schedule=locked_inputs(context,policy)
    c.require(c.read(out/'source_selection.json.gz')==normalized(records),'Delivered full color sources changed')
    coupon=[decode_coupon(u) for u in c.read(out/'calibration_source_units.json.gz')]
    programs={};stage_ids=[]
    for p in sorted(out.glob('*.commands.json.gz')):
        name=p.name.removesuffix('.commands.json.gz');cs=[command(r) for r in c.read(p)]
        us=coupon if 'RESPONSE_COUPON' in name else [] if 'STATIONS_ONLY' in name else selected
        ix={u['id']:i for i,u in enumerate(us)};order=[ix[x.source_id] for x in cs if x.action=='source_begin']
        if 'COMPLETE' in name:c.require(order==flat,'Complete order differs from PR43')
        elif us is selected:stage_ids.extend(order)
        material=c.read(out/(name+'.material.json.gz'))
        proof=audit_material(cs,material,us,order,policy)
        reports={}
        for air in (False,True):
            label=name.replace('COLOR','AIR',1) if air else name
            text=(out/(label+'.gcode')).read_text()
            c.require(text==gzip.decompress((out/(label+'.gcode.gz')).read_bytes()).decode(),'Plain/gzip mismatch')
            commands=c.air_projection(cs,profile) if air else cs
            actual=c.verify_numeric(text,commands,profile,us,order,policy,air)
            c.require(actual==c.read(out/(label+'.readback.json')),'Saved readback mismatch')
            reports['air' if air else 'color']=actual
        programs[name]=dict(readbacks=reports,material_proof=proof)
    c.require(stage_ids==flat,'Four-stage order is not the complete order')
    primary=programs[PRIMARY]['material_proof'];summary=c.read(out/'summary.json')
    c.require(primary['total_loads']==summary['primary']['total_loads'],'Primary summary/load mismatch')
    # Independently recompute diagnostic workloads from the frozen same geometry.
    compared=[]
    for limit in [None,15,20,30]:
        cfg=deepcopy(policy);cfg['contact_limit']=limit;key='distance_only_PR43' if limit is None else 'contact_'+str(limit)
        cs,ms=c.build(selected,flat,profile,cfg);audit_material(cs,ms,selected,flat,cfg)
        saved=c.read(out/(key+'.material.json.gz'))
        # Export adds timing to the preferred in-memory object only; the
        # comparison audit is saved before those presentation fields.
        c.require(ms==saved,'Comparison material/counter reproducibility: '+key)
        model=c.runtime(cs,profile)['models']['configuration_reference']
        row=c.read(out/'reload_comparison.json')[key]
        c.require(abs(model['acceleration_sensitive_seconds']-row['modeled_seconds'])<1e-8,'Comparison runtime changed')
        compared.append(key)
    number=None
    if independent:
        other=Path(independent);c.require(c.sha(other/'MANIFEST_SHA256.json')==c.sha(out/'MANIFEST_SHA256.json'),'Independent manifest changed')
        for name,expected in hashes.items():c.require(c.sha(other/name)==expected,'Independent generation differs: '+name)
        number=len(hashes)+1
    return dict(all_checks_passed=True,program_pairs_verified=len(programs),programs=programs,
        selected_sources=len(selected),actual_paper_contacts=primary['actual_paper_contacts'],
        source_and_stage_order_equal_PR43=True,original_numerical_paper_blocks_equal=True,
        contact_limit=15,distance_limit_mm=600,comparison_workloads_verified=compared,
        independent_files_compared=number,compression_profile_unchanged=True,
        no_same_pigment_washing=True,physical_response_measured=False,machine_authorized=False)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--context',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--verify',action='store_true');ap.add_argument('--independent',type=Path);ap.add_argument('--report',type=Path)
    a=ap.parse_args()
    if a.verify:
        result=verify(a.output,a.context,a.independent)
        if a.report:c.save(a.report,result)
        print(json.dumps({k:v for k,v in result.items() if k!='programs'},indent=2))
    else:generate(a.context,a.output)
