"""Reconstruct the recorded narrow v12-to-v13 operation, not original identity.

Numeric settings, cohort rules and namespace handling are transcribed from
the visible Work conversation. Frozen v12 vectors are loaded directly. No
unrelated native tree, vegetation or terrain generator is rerun.
"""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,json,hashlib
import numpy as np
from shapely.geometry import LineString,Point,box
from datascape.strokes.vector import phase
from datascape.integration.visibility import digest
from datascape.integration.local_refinement_v09 import load_inputs,cut
from datascape.integration.controlled_spring_v10 import CHANNELS,owner,length,prepare_fields,native_masks,save_case
from datascape.integration.final_local_spring_v12 import load,ground_patches
from datascape.rendering.spring_macro_study import write_gz

ROOT=Path(__file__).resolve().parents[3]


def run(control,inputs,output):
    output.mkdir(parents=True,exist_ok=False)
    c=json.load(open(ROOT/'configs/scenes/seoul_spring_v13_recovered_candidate.json'))
    oldc=json.load(open(control/'config.json'));base=load(control)
    context,fixed=load_inputs(inputs);fields=prepare_fields(fixed,oldc)
    groups=set(c['remove_native_groups'])
    native={o['id'] for o in context['objects'] if o['group'] in groups}
    region=box(*c['receiving_release_bounds_mm']);units=defaultdict(list)
    for r in base['channels']['RSU']:
        if region.contains(Point(np.mean(r['xy_mm'],axis=0))) and r.get('source_forward_m',1e6)<c['receiving_release_max_source_q_m']:
            units[r.get('source_member_ids',[owner(r)])[0]].append(r)
    parent_record=json.load(open(control/'record.json'))
    site_heights={s['id']:s['height_mm'] for s in parent_record.get('low_sites',[])}
    removed_units={k for k,rows in units.items() if max(x.get('height_mm',x.get('source_height_mm',site_heights.get(k,20))) for x in rows)>c['retained_low_site_max_height_mm'] or phase(k+'/open-left',c['seed'])>.28}
    case=dict(ink=[],channels={k:[] for k in CHANNELS});ledger=[];removed=[]
    def native_group(r):
        k=owner(r)
        return any(k==v or k.startswith(v+'/') for v in native) or any(k=='v03/Soil/'+g or k.startswith('v03/Soil/'+g+'/') for g in groups)
    for ch,rows in [('ink',base['ink'])]+list(base['channels'].items()):
        target=case['ink'] if ch=='ink' else case['channels'][ch]
        for r in rows:
            key=r.get('source_member_ids',[owner(r)])[0]
            if native_group(r) or (r['source_family']=='RSU' and key in removed_units):
                removed.append(r);ledger.append(dict(source_id=r['id'],owner_id=owner(r),channel=ch,reason='whole-left-foreground-cohort-release',kept_intervals_mm=[]));continue
            if ch=='C' and length(r)>12 and box(*c['short_C_bounds_mm']).intersects(LineString(r['xy_mm'])):
                L=length(r);ph=phase(r['id']+'/short-C',c['seed']);a=(.10+.20*ph)*L;b=min(a+6+5*ph,.82*L)
                def gate(xy,arc,rec):
                    inside=(xy[:,0]>=0)&(xy[:,0]<295)&(xy[:,1]>700)&(xy[:,1]<860)
                    return np.where(inside,np.minimum(arc-a,b-arc),1e6),['v13-short-discontinuous-left-C-only']
                pp,d=cut(r,gate,3.2,'v13-short-left-C');target+=pp;ledger.append(d)
            else:target.append(r)
    sources=[];trees=native_masks(case,context,native)
    first_ground_decision=len(ledger)
    ground,patches=ground_patches(case,fixed,fields,trees,oldc,c,sources,ledger)
    def namespace(value):
        if isinstance(value,str):return value.replace('v12/ground/','v13/ground/').replace('v12/left-ground/','v13/left-ground/')
        if isinstance(value,list):return [namespace(v) for v in value]
        if isinstance(value,dict):return {k:namespace(v) for k,v in value.items()}
        return value
    ground=namespace(ground);patches=namespace(patches);sources=namespace(sources);ledger[first_ground_decision:]=namespace(ledger[first_ground_decision:])
    for r in ground:r['v13_rule']='minimal-open-left-ground'
    case['ink']+=[r for r in ground if 'palette_slot' not in r]
    case['channels']['C']+=[r for r in ground if 'palette_slot' in r]
    checks={k:digest([r for r in base['ink'] if r['source_family']==k])==digest([r for r in case['ink'] if r['source_family']==k]) for k in ['A','B','C','D']}
    assert all(checks.values()) and base['channels']['A']==case['channels']['A']
    for name,case_ in [('before',base),('after',case)]:save_case(output,name,case_)
    rows=case['ink']+sum(case['channels'].values(),[]);errors=[]
    for r in rows:
        for k in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
            if k in r and len(r[k])!=len(r['xy_mm']):errors.append([r['id'],k])
    assert not errors and len({r['id'] for r in rows})==len(rows)
    record=dict(config=c,removed_native_owners=sorted(native),removed_RSU_units=sorted(removed_units),removed_paths_by_family=dict(Counter(r['source_family'] for r in removed)),removed_path_count=len(removed),removed_length_mm=sum(map(length,removed)),added_patches=patches,added_ink_paths=sum('palette_slot' not in r for r in ground),added_C_paths=sum('palette_slot' in r for r in ground),fixed_terrain_ink_exact=checks,A_color_exact=True,profile_errors=errors,unique_ids=True,parent_vector_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in control.glob('after*.json.gz')},status='v13_recovered_candidate; original v13 source identity unproven; awaiting reference PNG and visual approval',published=False,merged=False,machine_output=False)
    (output/'record.json').write_text(json.dumps(record,indent=2)+'\n');(output/'config.json').write_text(json.dumps(oldc,indent=2)+'\n')
    write_gz(output/'removed_objects.json.gz',dict(strokes=removed));write_gz(output/'authored_sources.json.gz',dict(strokes=sources));write_gz(output/'change_ledger.json.gz',dict(decisions=ledger))
    print('RECOVERED_CANDIDATE_READY',len(removed),len(ground),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--control',default='outputs/spring-final-local-v12');p.add_argument('--inputs',default='outputs/spring-integration-v09/reproduction_inputs');p.add_argument('--output',required=True);a=p.parse_args();run(Path(a.control),Path(a.inputs),Path(a.output))
