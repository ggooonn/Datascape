"""Focused fixed-S3a A/D feed comparison; no artwork or G-code output."""
import argparse
from copy import deepcopy
from pathlib import Path
import gzip
import hashlib
import json
import re
from time import perf_counter
from ..binding import load_bound_spring, digest
from ..layout import Layout
from .profiles import Profile
from .sequence import reference_order, make_plan, verify_plan
from .trajectory import build_job
from .timing import prepare_timing, estimate_prepared
from .exporter import verify_draw_lineage, save_json, _atomic_output
from .costs import audit_continuity


def unverified_yaml_axes(path):
    """Read only the three rate/acceleration entries; never install this YAML."""
    text = path.read_text(); rates=[]; accelerations=[]
    for axis in ('x','y','z'):
        section = re.search(r'^  '+axis+r':\s*\n(.*?)(?=^  [a-z]+:|\Z)',text,re.M|re.S)
        if section is None: raise ValueError('missing candidate axis '+axis)
        for key, target in (('max_rate_mm_per_min',rates),('acceleration_mm_per_sec2',accelerations)):
            target.append(float(re.search(r'^    '+key+r':\s*([0-9.]+)',section[1],re.M)[1]))
    return rates,accelerations


def scenarios(base):
    rows=[]
    for approach in (3000,5000,6000):
        for contact in (1000,1500,2000):
            m=dict(base,paper_approach_mm_min=approach,paper_contact_mm_min=contact,
                   paper_release_mm_min=contact,pressure_z_mm_min=2000,
                   wet_departure_mm_min=3000,wet_loaded_mm_min=9000,wet_arrival_mm_min=3000)
            rows.append((f'approach{approach}_contact{contact}_wet3000',m))
    for edge,main in ((1000,9000),(5000,5000)):
        rows.append((f'approach5000_contact2000_wet{edge}',dict(base,
                     paper_approach_mm_min=5000,paper_contact_mm_min=2000,paper_release_mm_min=2000,
                     pressure_z_mm_min=2000,wet_departure_mm_min=edge,wet_arrival_mm_min=edge,wet_loaded_mm_min=main)))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('machine','provenance','s3a-order','scenario','controller-candidate','before','output'):
        p.add_argument('--'+arg,required=True,type=Path)
    a=p.parse_args();start=perf_counter();profile=Profile.load(a.scenario)
    if profile.data['status']!='synthetic_fixture':raise ValueError('requires explicit synthetic fixture')
    strokes,_=load_bound_spring(a.machine,a.provenance);order=reference_order(strokes,a.s3a_order)
    profile.require('fixture',sorted({s.color_slot for s in strokes if s.medium=='color'}))
    rates,accels=unverified_yaml_axes(a.controller_candidate)
    hypothetical=deepcopy(profile.data['machine'])
    hypothetical.update(axis_max_rate_mm_min=rates,axis_acceleration_mm_s2=accels)
    dynamics={'inherited_slow_fixture':profile.data['machine'],'unverified_DEV_yaml':hypothetical}
    old=json.loads(a.before.read_text());crossings={s.stroke_id for s in strokes if min(p.x for p in s.points)<300<max(p.x for p in s.points)}
    def write(root):
        report={'schema':'datascape.motion_comparison.v0.3','profile_sha256':profile.sha256,
                'source_commit':'e424782585818de7c9b98fa6a4af196da9aff198',
                'before_report_sha256':hashlib.sha256(a.before.read_bytes()).hexdigest(),
                'controller_candidate':{'path':str(a.controller_candidate),'sha256':hashlib.sha256(a.controller_candidate.read_bytes()).hexdigest(),
                    'status':'UNVERIFIED file; installed settings unknown; not physical brush approval',
                    'junction_deviation_mm':profile.data['machine']['junction_deviation_mm'],
                    'junction_deviation_status':'synthetic 0.01; absent from candidate YAML',
                    'hypothetical_dynamics_exceed_fixture_brush_acceleration_limits':
                        max(accels[:2])>profile.data['motion']['wet_max_xy_acceleration_mm_s2']
                        or accels[2]>profile.data['motion']['contact_max_z_acceleration_mm_s2']},
                'dynamics':{name:{k:m[k] for k in ('axis_max_rate_mm_min','axis_acceleration_mm_s2','junction_deviation_mm')} for name,m in dynamics.items()},
                'motion':profile.data['motion'],
                'ink_reload_mm':profile.data['material']['ink_reload_mm'],
                'color_reload_mm':profile.data['material']['color_reload_mm'],
                'physical_printing_time_seconds':None,'Gcode_written':False,'hardware_executed':False,'layouts':{}}
        for mode in ('D','A'):
            jobs,manifest=make_plan(strokes,Layout(mode),order)
            path=root/(mode+'.plan.json.gz');save_json(path,manifest)
            validation=verify_plan(json.loads(gzip.decompress(path.read_bytes())),strokes,Layout(mode))
            rows={}
            for name,units in jobs.items():
                commands,metrics=build_job(profile,units,'fixture')
                lineage=verify_draw_lineage(commands,manifest['jobs'][name],profile,'fixture')
                continuity=audit_continuity(commands,crossings) if mode=='D' else None
                blocks=prepare_timing(commands,profile)
                final=next(c for c in reversed(commands) if c.kind=='move')
                if metrics['M0_count'] or final.xyz!=tuple(profile.data['motion']['park_xyz']):raise ValueError('production contract changed')
                expected=old['layouts'][mode]['jobs'][name]
                if metrics['counts'].get('same_color_reload',0)!=expected['same_material_reloads']:raise ValueError('reload count changed')
                if abs(metrics['distances']['station_transfer_3d_mm']-expected['scenario_station_transfer_3d_mm'])>1e-7:
                    raise ValueError('station transfer geometry changed')
                for action,key in (('full_wash','full_washes'),('absorbent_contact','PURGE_contacts')):
                    if metrics['counts'].get(action,0)!=expected[key]:raise ValueError('material operation count changed')
                times={}
                report['timing_model']={k:metrics['timing'][k] for k in ('model','verified_physical_time','limitations')}
                for label,motion in scenarios(profile.data['motion']):
                    times[label]={key:{k:v for k,v in estimate_prepared(blocks,machine,motion).items()
                                       if k not in ('model','verified_physical_time','limitations')}
                                  for key,machine in dynamics.items()}
                rows[name]={'original_units':len(units),'pressure_lineage':lineage,'D_continuity':continuity,
                            'reloads':metrics['counts'].get('same_color_reload',0),'washes':metrics['counts'].get('full_wash',0),
                            'PURGE_contacts':metrics['counts'].get('absorbent_contact',0),'M0_count':metrics['M0_count'],'M0_reasons':metrics['M0_reasons'],
                            'station_transfer_3d_mm':metrics['distances']['station_transfer_3d_mm'],
                            'station_transfer_distance_and_operation_counts_unchanged':True,
                            'before_commanded_feed_hours':expected['scenario_commanded_feed_hours'],
                            'before_stop_each_segment_hours':expected['scenario_stop_each_segment_hours'],
                            'before_seconds_by_action':expected['scenario_seconds_by_action'],
                            'scenarios':times}
                print(mode,name,'complete',flush=True)
                del commands,blocks
            report['layouts'][mode]={'plan_sha256':digest(manifest),'source_readback':validation,'jobs':rows}
            del jobs,manifest
        report['elapsed_seconds']=perf_counter()-start
        save_json(root/'motion_comparison.json',report)
        return report
    _atomic_output(a.output,write)


if __name__=='__main__':main()
