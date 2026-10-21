"""Focused A/D material counts and explicitly synthetic cost recalculation.

No G-code or physical trajectory files are serialized. Actual station travel
and physical job duration remain unresolved until measured profiles exist.
"""
from pathlib import Path
from dataclasses import asdict
from time import perf_counter
import argparse
import gzip
import json
from ..binding import load_bound_spring, digest
from ..layout import Layout
from .profiles import Profile
from .sequence import reference_order, make_plan, verify_plan
from .trajectory import build_job
from .exporter import save_json, verify_draw_lineage, _atomic_output


def compact_manifest(manifest, full_gzip_sha256):
    d = {k:v for k,v in manifest.items() if k != 'jobs'}
    d.update(schema='datascape.compact_execution_manifest.v0.3', full_plan_sha256=digest(manifest),
             full_plan_gzip_sha256=full_gzip_sha256,
             hash_contract='complete_fragment_payload_sha256 covers every point/pressure/location/span/work-coordinate and all serialized Fragment fields',jobs={})
    for name,units in manifest['jobs'].items():
        d['jobs'][name]=[{'job_source_rank':rank,'source_id':u['source_id'],
            'original_sequence':u['original_sequence'],'fragment_id':f['stroke']['stroke_id'],
            'panel':f['panel'],'medium':f['stroke']['medium'],'slot':f['stroke']['color_slot'],
            'pressure_sidecar_sha256':f['stroke']['pressure_sidecar_sha256'],
            'vertex_count':len(f['stroke']['points']),'complete_fragment_payload_sha256':digest(f)}
            for rank,u in enumerate(units) for f in u['fragments']]
    return d


def audit_continuity(commands, crossing_ids):
    """A whole crossing original is exactly one pressure/draw run in D."""
    source=None;active=False;seen=set();samples=0
    for c in commands:
        if c.action=='source_begin':source=c.source_id;active=False
        if source in crossing_ids:
            if c.artistic_pressure is not None:
                if c.action not in ('pressure_variation','draw'):raise ValueError('unexpected crossing pressure action')
                if c.action=='pressure_variation' and source in seen:raise ValueError('crossing source restarted after an artificial interruption')
                active=True;samples+=1;seen.add(source)
            elif active and c.action!='release':
                raise ValueError('non-drawing interruption inside continuous crossing source')
            if c.action=='release':active=False
        if c.action=='source_complete':source=None
    return {'continuous_crossing_sources_checked':len(seen),'crossing_pressure_samples_checked':samples,
            'no_seam_lift_reload_or_pause_inside_drawing_run':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('machine','provenance','s3a-order','scenario','output'):p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args();began=perf_counter()
    strokes,_=load_bound_spring(a.machine,a.provenance);order=reference_order(strokes,a.s3a_order)
    profile=Profile.load(a.scenario)
    if profile.data['status']!='synthetic_fixture':raise ValueError('cost scenario must be explicitly synthetic_fixture')
    slots=sorted({s.color_slot for s in strokes if s.medium=='color'});profile.require('fixture',slots)
    crossings={s.stroke_id for s in strokes if min(p.x for p in s.points)<300<max(p.x for p in s.points)}
    def write(root):
        import hashlib
        report={'schema':'datascape.A_D.cost_recalculation.v0.3',
            'counts_are_exact_for_frozen_S3a_and_reload_policy':True,
            'scenario_is_unverified_not_physical_calibration':True,'scenario_profile_sha256':profile.sha256,
            'ink_reload_mm':profile.data['material']['ink_reload_mm'],
            'color_reload_mm':profile.data['material']['color_reload_mm'],
            'physical_station_travel_mm':None,'physical_job_duration_seconds':None,
            'Gcode_written':False,'hardware_executed':False,'layouts':{}}
        save_json(root/'scenario.json',profile.data)
        for mode in ('A','D'):
            jobs,manifest=make_plan(strokes,Layout(mode),order)
            full=root/('layout_'+mode+'.plan.json.gz');save_json(full,manifest)
            written=json.loads(gzip.decompress(full.read_bytes()))
            validation=verify_plan(written,strokes,Layout(mode));del written
            save_json(root/('layout_'+mode+'.execution_manifest.json.gz'),compact_manifest(manifest,hashlib.sha256(full.read_bytes()).hexdigest()))
            rows={}
            for name,units in jobs.items():
                commands,m=build_job(profile,units,'fixture')
                lineage=verify_draw_lineage(commands,manifest['jobs'][name],profile,'fixture')
                continuity=audit_continuity(commands,crossings) if mode=='D' else None
                if m['M0_count'] or m['M0_reasons']:raise ValueError('standard job has routine M0')
                final=next(c for c in reversed(commands) if c.kind=='move')
                if final.xyz!=tuple(profile.data['motion']['park_xyz']):raise ValueError('final park differs')
                medium=units[0][0].stroke.medium
                rows[name]={'medium':medium,'original_units':len(units),
                    'loads_including_initial':sum(m['loads_per_slot'].values()),
                    'same_material_reloads':m['counts'].get('same_color_reload',0),
                    'color_changes':max(0,len(m['loads_per_slot'])-1) if medium=='color' else 0,
                    'full_washes':m['counts'].get('full_wash',0),
                    'PURGE_contacts':m['counts'].get('absorbent_contact',0),
                    'M0_count':m['M0_count'],'M0_reasons':m['M0_reasons'],
                    'actual_XY_drawing_mm':m['artwork_xy_drawing_mm'],
                    'scenario_station_transfer_3d_mm':m['distances']['station_transfer_3d_mm'],
                    'scenario_station_access_outbound_mm':m['distances'].get('station_access_3d_mm',0),
                    'scenario_station_return_mm':m['distances'].get('station_return_3d_mm',0),
                    'scenario_non_draw_3d_mm':m['distances']['non_draw_mm'],
                    'scenario_commanded_feed_hours':m['commanded_feed_subtotal_seconds']/3600,
                    'scenario_stop_each_segment_hours':m['stop_each_segment_model_seconds']/3600,
                    'scenario_seconds_by_action':m['commanded_feed_seconds_by_action'],
                    'threshold_overruns':m['threshold_overruns'],'lineage_validation':lineage,
                    'D_continuity_validation':continuity}
                print(mode,name,rows[name]['same_material_reloads'],round(rows[name]['scenario_commanded_feed_hours'],3),flush=True)
                del commands
            totals={key:sum(row[key] for row in rows.values()) for key in (
                'loads_including_initial','same_material_reloads','color_changes','full_washes','PURGE_contacts','M0_count',
                'actual_XY_drawing_mm','scenario_station_transfer_3d_mm','scenario_non_draw_3d_mm',
                'scenario_commanded_feed_hours','scenario_stop_each_segment_hours')}
            totals.update(ink_reloads=sum(r['same_material_reloads'] for r in rows.values() if r['medium']=='ink'),
                          color_reloads=sum(r['same_material_reloads'] for r in rows.values() if r['medium']=='color'))
            report['layouts'][mode]={'plan_sha256':digest(manifest),'source_readback':validation,'jobs':rows,'totals':totals}
            del manifest,jobs
        report['elapsed_seconds']=perf_counter()-began
        save_json(root/'cost_recalculation.json',report)
        return report
    _atomic_output(a.output,write)


if __name__=='__main__':main()
