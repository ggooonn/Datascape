"""Frozen PR34 single-pass panels and contact-budget comparison; offline only."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from math import dist
import argparse, base64, gzip, hashlib, json, subprocess

from . import spring_physical_ink as s
from .spring_physical_ink_review import render, sheet

PIN = '9665b92a7ab78ce44a135c191eb6c259a3cb03f6'
BASE = 'docs/spring_physical_ink_v01/review/'
POLICY = s.ROOT / 'config/spring_panels_contact20_v01/policy.json'


def frozen_bytes(relative):
    """Bind inherited inputs to the published PR34 Git object, not local guesses."""
    original = subprocess.check_output(['git', 'show', PIN + ':' + relative], cwd=s.ROOT)
    s.require((s.ROOT / relative).read_bytes() == original, 'Inherited PR34 input changed: ' + relative)
    return original


def frozen(name):
    raw = frozen_bytes(BASE + name)
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)


def owner_for_x(xs):
    """Exact centerline ownership; never clip, round, duplicate or split a source."""
    s.require(xs and all(s.np.isfinite(x) for x in xs), 'Invalid boundary coordinates')
    lo, hi = min(xs), max(xs)
    s.require(0 <= lo <= hi <= 600, 'Outside continuous artwork bounds')
    s.require(not lo < 300 < hi, 'Crossing INK source requires explicit unsplit policy')
    if hi <= 300:
        return 'P1'
    return 'P2'


def partition(fragments, rows=None):
    owners = {}; sources = []
    for i, f in enumerate(fragments):
        xs = [p.x for p in f.stroke.points]; ys = [p.y for p in f.stroke.points]
        s.require(all(0 <= y <= 900 for y in ys), 'Artwork Y outside bounds')
        panel = owner_for_x(xs); owners[i] = panel
        sources.append(dict(index=i, source_id=f.stroke.origin_id, panel=panel,
                            x_min=min(xs), x_max=max(xs), boundary_vertices=sum(x == 300 for x in xs),
                            first_on_boundary=xs[0] == 300, last_on_boundary=xs[-1] == 300,
                            boundary_only=all(x == 300 for x in xs), vertices=len(xs),
                            xy_pressure_sha256=s.digest([[p.x, p.y, p.pressure] for p in f.stroke.points]),
                            canonical_stroke_sha256=s.digest(asdict(f.stroke))))
        if rows is not None:
            sources[-1]['rich_source_record_sha256']=s.digest(rows[i])
            sources[-1]['authored_width_sha256']=s.digest(dict(width_mm=rows[i]['width_mm'],width_profile_mm=rows[i].get('width_profile_mm')))
    return owners, dict(sources=sources, original_sources=len(sources),
                       strict_X300_crossings=0, boundary_only_owner='P1',
                       boundary_touching_sources=sum(r['boundary_vertices'] > 0 for r in sources),
                       boundary_only_sources=sum(r['boundary_only'] for r in sources),
                       boundary_endpoint_sources=sum(r['first_on_boundary'] or r['last_on_boundary'] for r in sources),
                       no_clipping_splitting_rounding_or_translation=True)


def panel_groups(groups, owners, panel):
    if panel=='P1P2':return deepcopy(groups)
    selected = []
    for group in groups:
        run=[]
        for event in group:
            if owners[event['source']]==panel:run.append(deepcopy(event))
            elif run:selected.append(run);run=[]
        if run:selected.append(run)
    return selected


def seam_connections(groups,owners,fragments):
    records=[]
    for group in groups:
        for a,b in zip(group,group[1:]):
            if owners[a['source']]==owners[b['source']]:continue
            left=fragments[a['source']].work_xy[-1];right=fragments[b['source']].work_xy[0]
            s.require(left==right and left[0]==300,'Only an exact X300 source-endpoint join may separate for independent panels')
            records.append(dict(from_source=fragments[a['source']].stroke.origin_id,
                                to_source=fragments[b['source']].stroke.origin_id,work_xy=left,
                                combined_connection_preserved=True,
                                independent_panel_contact_separation=True,
                                canonical_geometry_or_pressure_changed=False))
    return records


class Budget(s.HybridBudget):
    """None disables only the contact trigger for a labeled numerical diagnostic."""
    def __init__(self, distance, contacts):
        super().__init__(distance, 1 if contacts is None else contacts)
        self.contact_limit = contacts

    def reasons(self, slot):
        b = self.slots[slot]
        return (['distance_limit'] if b['distance'] >= self.limit else []) + (
            ['contact_limit'] if self.contact_limit is not None and b['contacts'] >= self.contact_limit else [])


class Materials(s.InkMaterials):
    """PR34 material sequence with an explicit disabled-contact diagnostic mode."""
    def __init__(self, builder, policy, contacts):
        super().__init__(builder, dict(policy, contact_limit=1 if contacts is None else contacts))
        self.budget = Budget(policy['distance_limit_mm'], contacts)

    def before(self, group):
        slot=group[0]['ink']
        reasons=self.budget.reasons(slot) if self.loaded==slot else ['initial_load' if self.loaded is None else 'concentration_change']
        if not reasons:return
        previous=deepcopy(self.budget.slots)
        if self.loaded is not None and self.loaded!=slot:
            self.water('wash'); self.station('sponge','absorbent_contact'); self.water('controlled_rewet',0,1)
        self.station('light_ink' if slot=='LIGHT_INK' else 'dark_ink','pigment_load')
        self.loads.append(dict(before_event=group[0]['id'],ink=slot,reasons=reasons,previous_slot=self.loaded,
            previous_budgets=previous,distance_limit_mm=self.budget.limit,contact_limit=self.budget.contact_limit,
            distance_overrun_before_reload_mm=max(0,previous[slot]['distance']-self.budget.limit) if self.loaded==slot else 0,
            contact_overrun_before_reload=max(0,previous[slot]['contacts']-self.budget.contact_limit)
                if self.loaded==slot and self.budget.contact_limit is not None else 0,
            both_counters_reset=True))
        self.loaded=slot; self.budget.reset(slot)


def build(groups, fragments, profile, policy, contacts=20):
    """Retain every PR34 draw/station primitive and existing group boundary."""
    cfg = deepcopy(policy); cfg['contact_limit'] = contacts
    b = s.RuntimeBuilder(profile); material = Materials(b, cfg, contacts)
    b.commands.append(s.Command('pause', 'calibration_gate', message='REVIEW ONLY: verify small-brush compression, registration and new-container swept clearance before any contact. AIR first.'))
    audit = []
    for rank, group in enumerate(groups):
        material.before(group); before = deepcopy(material.budget.slots[group[0]['ink']]); start = len(b.commands)
        s.draw_gesture(b, group, fragments, material)
        drawn = sum(s.length(fragments[e['source']].work_xy) for e in group)
        bridge = sum(dist(fragments[a['source']].work_xy[-1], fragments[c['source']].work_xy[0])
                     for a, c in zip(group, group[1:]))
        material.after(group, drawn + bridge); after = deepcopy(material.budget.slots[group[0]['ink']])
        audit.append(dict(gesture_rank=rank, events=[e['id'] for e in group],
                          source_ids=[fragments[e['source']].stroke.origin_id for e in group], ink=group[0]['ink'],
                          source_count=len(group), actual_paper_engagements=1, drawn_mm=drawn + bridge,
                          connector_mm=bridge, before=before, after=after,
                          distance_overrun_mm=max(0, after['distance'] - cfg['distance_limit_mm']),
                          contacts_overrun=max(0, after['contacts'] - contacts) if contacts is not None else 0,
                          first_command=start, last_command=len(b.commands)-1))
    material.terminal()
    loads = material.loads
    result = dict(loads=loads, station_operations=material.operations, gestures=audit,
                  terminal_budgets=material.budget.slots, contact_limit=contacts,
                  total_loads=len(loads), same_concentration_reloads=sum(
                      'initial_load' not in x['reasons'] and 'concentration_change' not in x['reasons'] for x in loads),
                  concentration_changes=sum('concentration_change' in x['reasons'] for x in loads),
                  maximum_contacts_before_reload=max((a['after']['contacts'] for a in audit), default=0),
                  maximum_distance_before_reload_mm=max((a['after']['distance'] for a in audit), default=0),
                  maximum_atomic_distance_overrun_mm=max((a['distance_overrun_mm'] for a in audit), default=0),
                  maximum_atomic_contact_overrun=max((a['contacts_overrun'] for a in audit), default=0),
                  actual_paper_engagements=len(groups), no_service_inside_original_or_joined_gesture=True)
    return b.commands, result


def summary(commands, manifest, profile):
    timing = s.runtime(commands, profile)
    reference = timing['models']['configuration_reference']
    count = Counter(x['ink'] for x in manifest['loads'])
    reasons = Counter(r for x in manifest['loads'] for r in x['reasons'])
    # Both triggers can be true simultaneously. Report the intersection explicitly.
    both = sum('distance_limit' in x['reasons'] and 'contact_limit' in x['reasons'] for x in manifest['loads'])
    operations = Counter(c.action for c in commands if c.kind == 'marker')
    return dict(total_loads=manifest['total_loads'], light_loads=count['LIGHT_INK'], dark_loads=count['DARK_INK'],
                reloads_excluding_initial=manifest['total_loads']-1, initial_loads=reasons['initial_load'],
                distance_trigger_including_both=reasons['distance_limit'], contact_trigger_including_both=reasons['contact_limit'],
                both_thresholds=both, distance_only_trigger=reasons['distance_limit']-both,
                contact_only_trigger=reasons['contact_limit']-both,
                concentration_switches=reasons['concentration_change'],
                concentration_full_washes=operations['wash'], terminal_full_wash_visits=operations['terminal_wash'],
                all_full_wash_visits=operations['wash']+operations['terminal_wash'],
                actual_paper_engagements=manifest['actual_paper_engagements'],
                maximum_contacts=manifest['maximum_contacts_before_reload'],
                maximum_accumulated_distance_mm=manifest['maximum_distance_before_reload_mm'],
                maximum_atomic_distance_overrun_mm=manifest['maximum_atomic_distance_overrun_mm'],
                maximum_atomic_contact_overrun=manifest['maximum_atomic_contact_overrun'],
                modeled_seconds=reference['acceleration_sensitive_seconds'],
                modeled_seconds_by_category=reference['acceleration_sensitive_seconds_by_category'],
                commanded_seconds_by_category=reference['commanded_feed_seconds_by_category'],
                runtime_assumptions=timing)


def station_records(commands, profile):
    position = tuple(profile.data['machine']['start_work_xyz']); records = []
    for index, c in enumerate(commands):
        if c.kind == 'move':
            if c.time_category in ('station_transfer', 'station_handling'):
                records.append(dict(command=index, action=c.action, category=c.time_category,
                                    from_xyz=position, to_xyz=c.xyz, feed_mm_min=c.feed_mm_min,
                                    travel_state=c.travel_state, travel_phase=c.travel_phase))
            position = c.xyz
        elif c.kind == 'dwell':
            records.append(dict(command=index, action=c.action, xyz=position, dwell_seconds=c.seconds))
        elif c.kind == 'marker' and c.action in ('pigment_load','wash','controlled_rewet','terminal_wash','absorbent_contact'):
            records.append(dict(command=index, action=c.action, station=c.message, xyz=position))
    return records


def audit_ir(commands, material, groups, fragments, profile):
    contacts = loads = peak = 0; active = None; order = []; samples = 0
    for c in commands:
        if c.kind == 'marker' and c.action == 'pigment_load':
            s.require(active is None, 'Pigment operation inside original source')
            loads += 1; contacts = 0
            s.require(c.message in ('WELL_1','WELL_2'), 'Ink station changed')
        if c.action == 'initial_contact':contacts += 1; peak = max(peak, contacts)
        if c.action == 'source_begin':
            s.require(active is None, 'Nested source'); active = c.message; order.append(c.message)
        if c.action == 'source_complete':
            s.require(active == c.message, 'Source closure'); active = None
        if active:
            s.require(c.time_category not in ('station_handling','station_transfer'), 'Station inside source')
        if c.artistic_pressure is not None:samples += 1
    s.require(loads == material['total_loads'] and peak == material['maximum_contacts_before_reload'], 'Material/IR disagreement')
    s.require(order == [e['id'] for g in groups for e in g], 'Source order changed')
    s.require(samples == sum(len(fragments[e['source']].stroke.points) for g in groups for e in g), 'Pressure sample mismatch')
    return dict(actual_paper_contacts_verified=sum(c.action == 'initial_contact' for c in commands),
                pressure_values_verified=samples, all_loads_and_contacts_match_IR=True,
                source_station_atomicity_verified=True)


def verify_output(output, context, independent=None):
    out = Path(output); report = s.read(out/'verification.json')
    _, rows, fragments = s.load_inputs(Path(context)); p = s.Profile.load(out/'profile.PR34.unchanged.json')
    frozen_groups = frozen('SINGLE_PASS.execution_manifest.json.gz')['groups']
    owners, boundary = partition(fragments,rows)
    s.require(boundary == s.read(out/'partition.json.gz'), 'Boundary provenance differs')
    expected = set(range(3345)); seen = set(); checks = {}
    for panel in ('P1','P2','P1P2'):
        groups = s.read(out/(panel+'.execution_manifest.json.gz'))['groups']
        s.require(groups == panel_groups(frozen_groups, owners, panel), 'Frozen groups/direction/order changed')
        ids = [e['source'] for g in groups for e in g]
        s.require(len(ids) == len(set(ids)), 'Duplicated panel source')
        if panel != 'P1P2':
            s.require(not seen.intersection(ids), 'Duplicated panel ownership'); seen.update(ids)
        commands = [s.Command(**{**c,'xyz':tuple(c['xyz']) if c['xyz'] is not None else None})
                    for c in s.read(out/(panel+'.numeric_IR.json.gz'))]
        material = s.read(out/(panel+'.reload_manifest.json.gz'))
        audit_ir(commands, material, groups, fragments, p)
        air = s.air_projection(commands,p)
        for suffix, ir, is_air in [('INK',commands,False),('AIR',air,True)]:
            name = f'SPRING_{panel}_{suffix}_CONTACT20_REVIEW'
            raw = (out/(name+'.gcode')).read_bytes()
            s.require(gzip.decompress((out/(name+'.gcode.gz')).read_bytes()) == raw, 'Lossless gzip mismatch')
            s.require(hashlib.sha256(raw).hexdigest() == report['jobs'][name]['gcode_sha256'], 'G-code SHA mismatch')
            checks[name] = s.verify_numeric(raw.decode(),ir,p,groups,fragments,is_air)
        s.require([c.xyz[:2] for c in commands if c.kind=='move'] == [c.xyz[:2] for c in air if c.kind=='move'], 'AIR XY differs')
        if panel == 'P2':
            for air_mode, source_ir in [(False,commands),(True,air)]:
                name=f'SPRING_P2_{"AIR" if air_mode else "INK"}_CONTACT20_REVIEW.gcode'
                text=(out/name).read_text()
                bad=text.replace('Z35.000000000','Z20.000000000',1) if air_mode else text.replace('M0\n','',1)
                rejected=False
                try:s.verify_numeric(bad,source_ir,p,groups,fragments,air_mode)
                except ValueError:rejected=True
                s.require(rejected,'Gate/AIR mutation accepted')
    s.require(seen == expected, 'P1/P2 union incomplete')
    manifest=s.read(out/'MANIFEST_SHA256.json')
    s.require(set(manifest)=={str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name not in ('MANIFEST_SHA256.json','delivered_readback.json')},'Manifest coverage')
    s.require(all(s.sha(out/name)==value for name,value in manifest.items()),'Delivered file SHA mismatch')
    equality={}
    if independent:
        other=Path(independent)
        for name in manifest:
            s.require((other/name).exists(),'Independent output missing '+name)
            equality[name]=(out/name).read_bytes()==(other/name).read_bytes()
        s.require(all(equality.values()),'Reproduction byte mismatch')
    result=dict(numeric_programs_verified=6,original_ink_sources=3345,original_ink_pressure_samples=69101,
                panels_disjoint_and_complete=True,exact_original_source_subsequences=True,
                original_groups_preserved_except_documented_independent_seam_separation=True,
                combined_approved_joins_preserved=3,independent_seam_join_separations=3,
                no_new_connections_or_repeat_passes=True,all_AIR_moves_Z35=True,
                all_numeric_XYZ_feed_dwell_and_lineage_verified=True,gate_and_AIR_mutations_rejected=True,
                independent_byte_reproduction=equality,published_baseline=PIN,
                physical_compression_and_swept_clearance_verified=False,machine_authorized=False)
    s.save(out/'delivered_readback.json',result)
    return result


def generate(output, context):
    out=Path(output); s.require(not out.exists(),'New output directory required'); out.mkdir(parents=True)
    config=s.read(POLICY); s.require(config['baseline_commit']==PIN and config['selected_contact_limit']==20,'Selected policy changed')
    context=s.recover_context(Path(context)); plan,rows,fragments=s.load_inputs(context)
    source_hash=s.digest(plan); policy=frozen('policy.json'); policy['contact_limit']=20
    frozen_profile=frozen('profile.small_baegunmo.json'); p=s.Profile.from_dict(frozen_profile)
    original=frozen('SINGLE_PASS.execution_manifest.json.gz'); fs=frozen('source_features.json.gz')
    edges=frozen('protected_source_dependencies.json.gz')['edges']; owners,boundary=partition(fragments,rows)
    seam=seam_connections(original['groups'],owners,fragments)
    s.require(len(seam)==3,'PR34 seam connection count changed')
    s.save(out/'seam_connections.PR34.json',seam)
    s.require(len({f.stroke.origin_id for f in fragments})==3345,'Duplicate canonical source IDs')
    s.require([e for g in original['groups'] for e in g]==original['events'],'Frozen event/group mismatch')
    s.require(all(e['pass_index']==0 and e['ink']==fs[e['source']]['ink'] for e in original['events']),'Single-pass/material assignment changed')
    s.save(out/'source_pressure_integrity.json',dict(
        original_sources=3345,original_pressure_samples=69101,
        canonical_plan_sha256=s.PLAN_SHA,pressure_sidecar_sha256=s.SIDECAR_SHA,
        rich_source_file_sha256=s.INK_SHA,unique_original_source_ids=True,
        all_XY_pressure_width_direction_source_records_unchanged=True,
        all_existing_material_assignments_unchanged=True,
        source_records_include_width_and_canonical_hashes='partition.json.gz',
        panel_source_counts=dict(Counter(owners.values())),
        panel_pressure_counts={panel:sum(len(f.stroke.points) for i,f in enumerate(fragments) if owners[i]==panel) for panel in ('P1','P2')},
        X300_strict_crossings=0,X300_touching_sources=boundary['boundary_touching_sources'],
        X300_boundary_only_sources=boundary['boundary_only_sources'],
        approved_combined_joins=len(seam),independent_panel_seam_separations=len(seam)))
    s.save(out/'policy.contact20.json',config); s.save(out/'profile.PR34.unchanged.json',p.data)
    s.save(out/'partition.json.gz',boundary); s.save(out/'protected_dependencies.PR34.json.gz',dict(edges=edges))
    s.save(out/'compression_calibration_audit.PR34.json.gz',frozen('compression_calibration_audit.json.gz'))
    report=dict(baseline_commit=PIN,canonical_plan_sha256=s.PLAN_SHA,pressure_sidecar_sha256=s.SIDECAR_SHA,
                original_source_count=3345,original_pressure_sample_count=69101,
                primary_execution='SINGLE_PASS',selected_contacts=20,distance_limit_mm=800,
                G54_translated=False,backing_offset_added_mm=0,machine_authorized=False,jobs={},panels={})
    comparisons={}; groups_by_panel={}
    # Generate the primary P2 contact20 pair before any comparison or other panel.
    for panel in ('P2','P1','P1P2'):
        groups=panel_groups(original['groups'],owners,panel); groups_by_panel[panel]=groups
        events=[e for g in groups for e in g]; ids={e['source'] for e in events}
        rank={e['source']:i for i,e in enumerate(events)}
        internal=[(a,b) for a,b in edges if a in ids and b in ids]
        s.require(all(rank[a]<rank[b] for a,b in internal),'Protected panel dependency violated')
        commands,material=build(groups,fragments,p,policy,20)
        audit=audit_ir(commands,material,groups,fragments,p)
        model=summary(commands,material,p)
        included={e['id'] for e in events}
        s.save(out/(panel+'.execution_manifest.json.gz'),dict(groups=groups,events=events,approved_joins=[j for j in original['joins'] if j['from_event'] in included and j['to_event'] in included],protected_internal_edges=len(internal),seam_contact_separations=len(seam) if panel!='P1P2' else 0))
        s.save(out/(panel+'.reload_manifest.json.gz'),material)
        s.save(out/(panel+'.station_operations.json.gz'),station_records(commands,p))
        s.save(out/(panel+'.numeric_IR.json.gz'),[asdict(c) for c in commands])
        for kind,ir,air in [('INK',commands,False),('AIR',s.air_projection(commands,p),True)]:
            name=f'SPRING_{panel}_{kind}_CONTACT20_REVIEW'
            report['jobs'][name]=s.write_job(out,name,ir,p,groups,fragments,air)
        report['panels'][panel]=dict(sources=len(events),pressure_samples=audit['pressure_values_verified'],
            joined_contacts_saved=len(events)-len(groups),allocation=dict(Counter(e['ink'] for e in events)),
            ink_drawing_mm={slot:sum(fs[e['source']]['length_mm'] for e in events if e['ink']==slot) for slot in ('LIGHT_INK','DARK_INK')},
            source_order_sha256=s.digest([fragments[e['source']].stroke.origin_id for e in events]),
            pressure_XY_width_records_sha256=s.digest([boundary['sources'][i] for i in sorted(ids)]),
            protected_internal_dependencies=len(internal),execution=model)
        if panel=='P2':comparisons['C_contact20']=model
        print(panel,'sources',len(events),'loads',model['total_loads'],'minutes',round(model['modeled_seconds']/60,3),flush=True)
    for label,contacts in [('A_contact12',12),('B_contact15',15),('D_distance_only',None)]:
        commands,material=build(groups_by_panel['P2'],fragments,p,policy,contacts)
        audit_ir(commands,material,groups_by_panel['P2'],fragments,p)
        comparisons[label]=summary(commands,material,p)
        s.save(out/(label+'.P2.reload_manifest.json.gz'),material)
        s.save(out/(label+'.P2.station_operations.json.gz'),station_records(commands,p))
    # A full-scene12 control proves the new builder preserves the prior primitives.
    commands,material=build(original['groups'],fragments,p,policy,12)
    old_commands,old_material=s.build(original['groups'],fragments,p,policy,12)
    s.require(commands==old_commands and material==dict(old_material,maximum_atomic_contact_overrun=0),'PR34 builder comparison differs')
    old_name='SPRING_INK_SINGLE_PASS_REVIEW'
    old_text=s.BANNER+'; SPRING SMALL BAEGUNMO / NUMERICAL REVIEW / NOT MACHINE AUTHORIZED\n'+s._serialize(commands,p,s.PLAN_SHA,old_name,'offline_review')
    s.require(old_text.encode()==gzip.decompress(frozen_bytes(BASE+old_name+'.gcode.gz')),'PR34 full12 program no longer byte-identical')
    report['PR34_full12_byte_identical']=True
    report['PR34_full12']=summary(commands,material,p)
    cross=[(a,b) for a,b in edges if owners[a]!=owners[b]]
    s.save(out/'cross_panel_dependencies.json',dict(edges=cross,count=len(cross),
        note='Independent panels preserve restricted PR34 order. Cross-panel temporal edges cannot be enforced between independent jobs; no centerline crosses the seam. Authored-width overlap is not calibrated wet-brush overlap.'))
    s.require(s.digest(plan)==source_hash,'Canonical plan changed')
    s.save(out/'P2_reload_runtime_comparison.json',comparisons); s.save(out/'verification.json',report)
    previews(out,rows,fs,groups_by_panel,report,comparisons)
    s.save(out/'MANIFEST_SHA256.json',{str(f.relative_to(out)):s.sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='MANIFEST_SHA256.json'})
    return verify_output(out,context)


def previews(out,rows,fs,groups,report,comparison):
    for panel in ('P1','P2','P1P2'):
        bounds=(0,0,300,900) if panel=='P1' else (300,0,600,900) if panel=='P2' else (0,0,600,900)
        render(out/(panel+'.png'),rows,fs,[e for g in groups[panel] for e in g],bounds,2)
    sheet(out,[out/'P1.png',out/'P2.png'],['P1 / global X0-300','P2 / global X300-600'],'P1_P2_comparison.png',(620,1800))
    lines=['# Spring panels / numerical runtime comparison','','All times modeled, not measured. PR34 acceleration references, assumed JD0.01/full lookahead. No changed feeds or physical authorization.','',
           '| P2 case | Loads L/D | Switches | Distance/contact/both triggers | Station handling | Station transfer | Drawing | Paper engagement | Non-drawing | Total |',
           '| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key in ('A_contact12','B_contact15','C_contact20','D_distance_only'):
        r=comparison[key];c=r['modeled_seconds_by_category']
        nums=' | '.join(f'{c.get(k,0)/60:.3f}' for k in ('station_handling','station_transfer','drawing','paper_engagement','non_drawing_travel'))
        lines.append(f"| {key} | {r['total_loads']} ({r['light_loads']}/{r['dark_loads']}) | {r['concentration_switches']} | {r['distance_only_trigger']}/{r['contact_only_trigger']}/{r['both_thresholds']} | {nums} | {r['modeled_seconds']/60:.3f} |")
    lines+=['','Minutes in every time column. Threshold categories are exclusive; switch/initial events are separate. Each concentration switch performs a full wash; each job also has three terminal wash visits. Atomic overruns and simultaneous triggers remain in JSON. No modeled manual-M0 or drying delay.','',
            '| P2 case | Full washes (switch + terminal visits) | Max contacts | Max accumulated mm | Max distance overrun mm | Max contact overrun |',
            '| --- | --- | ---: | ---: | ---: | ---: |']
    for key in ('A_contact12','B_contact15','C_contact20','D_distance_only'):
        r=comparison[key]
        lines.append(f"| {key} | {r['concentration_full_washes']} + {r['terminal_full_wash_visits']} | {r['maximum_contacts']} | {r['maximum_accumulated_distance_mm']:.3f} | {r['maximum_atomic_distance_overrun_mm']:.3f} | {r['maximum_atomic_contact_overrun']} |")
    lines+=['',
            '| Selected job | Sources | Contacts | Loads | Modeled minutes |','| --- | ---: | ---: | ---: | ---: |']
    for panel,r in report['panels'].items():
        e=r['execution'];lines.append(f"| {panel} | {r['sources']} | {e['actual_paper_engagements']} | {e['total_loads']} | {e['modeled_seconds']/60:.3f} |")
    (out/'RUNTIME.md').write_text('\n'.join(lines)+'\n')
    def img(name):return 'data:image/png;base64,'+base64.b64encode((out/name).read_bytes()).decode()
    html='<!doctype html><html lang="en"><meta charset="utf-8"><title>Spring P1/P2 contact20 review</title><style>body{font:16px/1.6 system-ui;max-width:1200px;margin:auto;padding:24px;background:#f5f4ef}img{max-width:100%}pre{white-space:pre-wrap}</style><h1>Spring P1/P2 / contact20</h1><p>Frozen PR34 single-pass artwork, allocation, pressure and source-order subsequences. No optional repeats. P2 stays at global X300–600. The three approved D joins span the seam: the combined program retains them, while independent panels separate contact only at the existing source endpoints on X300. No canonical source is split and no XY/pressure vertex is changed. Cross-panel temporal edges cannot be enforced between independent jobs. Authored-width previews are illustrative, not measured small-brush width, spreading or pigment response.</p><img src="'+img('P1_P2_comparison.png')+'"><h2>Numerical timing</h2><pre>'+'\n'.join(lines)+'</pre><p>Complete OFFLINE REVIEW programs. Confirmed touch10/approach15/hover20, no extra3mm. Inherited compression reaches10.2mm/Z−0.2 and is not certified safe for the small brush. Container bottom/holder/vertical agitation/lip/connecting clearances and actual registration remain unverified. Contact jobs start with M0 before movement, not a safety interlock. AIR allZ35 is not a collision certificate. Each independent file assumes prepared brush/materials, G54 start0/900/35 and terminal800/800/35. Do not run panel and combined programs on the same paper unintentionally.</p></html>'
    (out/'Review.html').write_text(html)


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--context',type=Path,required=True)
    parser.add_argument('--verify',action='store_true'); parser.add_argument('--independent',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify_output(args.output,args.context,args.independent) if args.verify else generate(args.output,args.context),indent=2))
