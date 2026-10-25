"""Separate ordered dot plans; no stroke workaround or canonical source mutation."""
from collections import Counter,defaultdict
from dataclasses import asdict
from math import ceil
from .data import load_dots,settings,COLOR_ORDER,PANEL_MAP,INPUT_SHA,integer,number


def order_dots(dots,mode,start='right',colors=COLOR_ORDER):
    if mode not in ('global','local') or start not in ('left','right'): raise ValueError('invalid coordinate mode/start')
    result=[]
    for color in colors:
        rows=defaultdict(list)
        for d in dots:
            if d.color_id==color: rows[d.row_global if mode=='global' else d.row_local].append(d)
        for rank,y in enumerate(sorted(rows)):
            descending=(start=='right') != bool(rank%2)
            key=lambda d:((d.global_x_mm if mode=='global' else d.local_x_mm),d.study_dot_id)
            result.extend(sorted(rows[y],key=key,reverse=descending))
    if len(result)!=len(dots) or {d.study_dot_id for d in result}!={d.study_dot_id for d in dots}: raise ValueError('order does not cover dots once')
    return tuple(result)


def make_plan(dots,job_id,mode,panel=None,config=None):
    config=config or settings();ordered=order_dots(dots,mode,config['first_row_start'],config['color_order'])
    n=config['refill_every_contacts'];integer(n,'refill count',1)
    rows=[];previous=None;contact=0;batch=0;within_color=0
    for d in ordered:
        change=d.color_id!=previous
        if change: contact=0;within_color=0
        service='first_load' if change and previous is None else 'color_change' if change else 'same_color_reload' if contact==n else ''
        if service: contact=0;batch+=1
        contact+=1;within_color+=1
        row={**d.original,'execution_sequence':len(rows)+1,'coordinate_mode':mode,'artwork_x_mm':d.global_x_mm if mode=='global' else d.local_x_mm,'artwork_y_mm':d.global_y_mm if mode=='global' else d.local_y_mm,'load_batch':batch,'contact_in_batch':contact,'contact_in_color':within_color,'service_before':service}
        rows.append(row);previous=d.color_id
    counts=Counter(d.color_id for d in ordered);loads=sum(ceil(v/n) for v in counts.values())
    assert batch==loads
    return dict(schema='hanji.dot_execution_plan.v01',job_id=job_id,coordinate_mode=mode,physical_panel_id=panel,source_panel_id=None if panel is None else PANEL_MAP[panel],input_sha256=INPUT_SHA,config=config,used_color_order=[c for c in config['color_order'] if c in counts],dot_count=len(rows),colors=dict(counts),loads=loads,same_color_reloads=max(0,loads-len(counts)),color_changes=max(0,len(counts)-1),dots=rows,completed_dot_ids=[],physical_completion_record=None)


def standard_plans(dots=None,config=None):
    dots=load_dots() if dots is None else dots;config=config or settings()
    p=[make_plan(dots,'hanji_full_600x600','global',config=config)]
    p += [make_plan([d for d in dots if d.physical_panel_id==n],f'hanji_panel_{n:02d}_local','local',n,config) for n in range(1,10)]
    assert Counter(int(r['study_dot_id']) for q in p[1:] for r in q['dots'])==Counter(d.study_dot_id for d in dots)
    return p


def c4_test(dots=None,config=None):
    dots=load_dots() if dots is None else dots;config=config or settings()
    candidates=[d for d in dots if d.physical_panel_id==4 and d.color_id=='C4']
    if len(candidates)!=253: raise ValueError('P04 C4 source mismatch')
    first=order_dots(candidates,'local',config['first_row_start'])[:40]
    result=make_plan(first,'hanji_panel_04_C4_first40','local',4,config)
    result['next_C4_study_dot_id']=order_dots(candidates,'local',config['first_row_start'])[40].study_dot_id
    return result


def remaining(plan,record,scenario=None):
    """An explicit physically confirmed ledger; AIR or planned tests are not completion."""
    if record.get('schema')!='hanji.physical_completion.v01' or record.get('physically_completed') is not True or record.get('mode')!='paint': raise ValueError('actual paint completion must be explicitly confirmed')
    from datascape.gcode.binding import digest
    if scenario is None or record.get('registration_sha256')!=digest(scenario): raise ValueError('completion requires the same recorded mounting/surface registration')
    if record.get('input_sha256')!=INPUT_SHA or record.get('physical_panel_id')!=plan['physical_panel_id']: raise ValueError('completion refers to different artwork/panel')
    if not all(isinstance(record.get(k),str) and record[k].strip() for k in ('operator','date','record')): raise ValueError('completion record provenance required')
    for key in ('compression_depth_mm','dwell_at_depth_s'):
        number(record.get(key),key,0)
        if record[key]!=plan['config'][key]: raise ValueError('completion contact conditions differ')
    ids=record.get('completed_dot_ids')
    if not isinstance(ids,list): raise ValueError('completion IDs must be a list')
    for i in ids: integer(i,'completed ID',1)
    if len(ids)!=len(set(ids)) or set(ids)-{int(r['study_dot_id']) for r in plan['dots']}: raise ValueError('invalid/duplicate completed IDs')
    keep={int(r['study_dot_id']) for r in plan['dots']}-set(ids)
    # Retain original execution order. Removing a prefix of a color must not restart serpentine parity.
    canonical={d.study_dot_id:d for d in load_dots()}
    ordered=[canonical[int(r['study_dot_id'])] for r in plan['dots'] if int(r['study_dot_id']) in keep]
    if not ordered: raise ValueError('no unpainted dots remain')
    p=make_plan(ordered,plan['job_id']+'_remaining','local' if plan['physical_panel_id'] else 'global',plan['physical_panel_id'],plan['config'])
    # Scheduling from a filtered plan uses its original ordering, not a new spatial order.
    byid={int(r['study_dot_id']):r for r in p['dots']};rows=[];prev=None;count=0;batch=0;incolor=0;n=p['config']['refill_every_contacts']
    for d in ordered:
        r=byid[d.study_dot_id].copy();change=d.color_id!=prev
        if change:count=0;incolor=0
        service='first_load' if change and prev is None else 'color_change' if change else 'same_color_reload' if count==n else ''
        if service:count=0;batch+=1
        count+=1;incolor+=1;r.update(execution_sequence=len(rows)+1,load_batch=batch,contact_in_batch=count,contact_in_color=incolor,service_before=service);rows.append(r);prev=d.color_id
    p.update(dots=rows,completed_dot_ids=ids,physical_completion_record=record)
    return p
