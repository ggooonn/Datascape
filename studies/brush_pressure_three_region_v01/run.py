"""Full frozen-Spring mapping/trajectory study. No G-code, device or backend edits."""
import argparse
from collections import defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
from math import hypot,dist
from pathlib import Path
from time import perf_counter
from datascape.gcode.binding import load_bound_spring, digest, SIDECAR_SHA
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import reference_order, make_plan, verify_plan, source_hash
from datascape.gcode.production.trajectory import build_job
from datascape.gcode.production.timing import prepare_timing, estimate_prepared
from datascape.gcode.production.exporter import save_json, verify_draw_lineage, _atomic_output
from datascape.gcode.production.costs import audit_continuity
from datascape.gcode.production.motion_comparison import unverified_yaml_axes
from studies.brush_pressure_three_region_v01.curves import load_catalog,offline_profile,summary

PIN='12b28bd5b7ad575b1438ed5af61618746c7effe9'


def accepted_groups(strokes, sidecar):
    raw=sidecar.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SIDECAR_SHA:raise ValueError('accepted sidecar SHA mismatch')
    records=json.loads(gzip.decompress(raw))['strokes'];groups=defaultdict(list)
    for s,r in zip(strokes,records,strict=True):
        if s.stroke_id!=r['stroke_id'] or [p.pressure for p in s.points]!=r['pressure_intent_samples']:
            raise ValueError('accepted family/pressure/source binding mismatch')
        groups[(s.medium,r['family'])].append(s)
    return groups


def analyze(strokes,groups,base,curves):
    out=[]
    for (medium,family),ss in sorted(groups.items()):
        ps=[p.pressure for s in ss for p in s.points]
        row={'medium':medium,'family':family,'original_strokes':len(ss),'pressure':summary(ps),
             'XY_length_mm':sum(hypot(b.x-a.x,b.y-a.y) for s in ss for a,b in zip(s.points,s.points[1:])),
             'pressure_bins':{label:sum(lo<=p<hi for p in ps) for label,lo,hi in
                 [('below_0_2',0,.2),('0_2_to_0_4',.2,.4),('0_4_to_0_6',.4,.6),('0_6_to_0_93',.6,.93),('0_93_to_1',.93,1.00001)]},
             'samples_0_22_to_0_35':sum(.22<=p<=.35 for p in ps),
             'samples_above_0_8':sum(p>.8 for p in ps),'mapped_Z_mm':{}}
        for curve in curves:
            b=offline_profile(base,curve).brush_for(medium,ss[0].color_slot)
            row['mapped_Z_mm'][curve['id']]=summary([b.z_for(p) for p in ps])
        out.append(row)
    return out


def extra_metrics(commands,profile):
    start=tuple(profile.data['machine']['start_work_xyz']);z_travel=defaultdict(float);limited=0;draws=0
    first=[];last=[];samples=[]
    for c in commands:
        if c.kind!='move':continue
        z_travel[c.time_category]+=abs(c.xyz[2]-start[2])
        if c.action=='draw':
            draws+=1
            if c.feed_mm_min<profile.data['motion']['draw_mm_min']-1e-8:limited+=1
        if c.action=='pressure_variation':first.append(-c.xyz[2])
        if c.artistic_pressure is not None:samples.append(c.xyz[2])
        if c.action=='release':last.append(-start[2])
        if c.action in ('draw','pressure_variation') and c.axis_velocity_mm_min[2]>2000+1e-6:
            raise ValueError('pressure-Z cap violated')
        start=c.xyz
    return {'drawing_segments':draws,'rate_limited_drawing_segments':limited,
            'initial_compression_mm':summary(first),'release_compression_mm':summary(last),
            'mapped_Z_mm':summary(samples),'absolute_Z_travel_mm_by_category':dict(z_travel)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('machine','provenance','sidecar','output'):p.add_argument('--'+arg,required=True,type=Path)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--curves',type=Path,help='editable unmeasured candidate knot JSON')
    a=p.parse_args();began=perf_counter()
    strokes,_=load_bound_spring(a.machine,a.provenance);canonical=source_hash(strokes)
    order=reference_order(strokes,a.root/'config/plotter_v03/spring_s3a_order.json')
    base=Profile.load(a.root/'config/plotter_v03/cost_scenario.synthetic.json')
    curve_path=a.curves or a.root/'studies/brush_pressure_three_region_v01/candidate_curves.json'
    curves=load_catalog(curve_path)
    groups=accepted_groups(strokes,a.sidecar)
    axes=a.root/'hardware/fluidnc/config_DEV_2026-10-10_UNVERIFIED.yaml';rates,accels=unverified_yaml_axes(axes)
    dev=deepcopy(base.data['machine']);dev.update(axis_max_rate_mm_min=rates,axis_acceleration_mm_s2=accels)
    crossing={s.stroke_id for s in strokes if min(p.x for p in s.points)<300<max(p.x for p in s.points)}
    previous=json.loads((a.root/'docs/plotter_backend_v03/review/motion_comparison.json').read_text())
    def write(root):
        result={'schema':'datascape.three_region_pressure_study.v01','backend_pin':PIN,
                'artwork_modified':False,'pressure_modified':False,'S3a_modified':False,
                'Gcode_written':False,'hardware_executed':False,'production_authorized':False,
                'physical_runtime_seconds':None,'source_sha256':canonical,'pressure_sidecar_sha256':SIDECAR_SHA,
                'base_scenario_sha256':base.sha256,'curve_config_sha256':hashlib.sha256(curve_path.read_bytes()).hexdigest(),
                'controller_candidate_sha256':hashlib.sha256(axes.read_bytes()).hexdigest(),
                'motion':base.data['motion'],'curves':curves,'families':analyze(strokes,groups,base,curves),
                'dynamics':{name:{k:m[k] for k in ('axis_max_rate_mm_min','axis_acceleration_mm_s2','junction_deviation_mm')}
                            for name,m in [('synthetic_low',base.data['machine']),('unverified_DEV',dev)]},
                'assumptions':['all profiles synthetic; no measured brush/station/clearance data',
                    'DEV file is unverified; its high accelerations exceed fixture brush limits',
                    'junction deviation 0.01 mm is synthetic and absent from DEV YAML',
                    'full lookahead/continuous streaming assumed; no finite buffer/step/serial emulation',
                    'no width, pigment or recovery prediction from compression alone'],
                'layouts':{}}
        save_json(root/'candidate_curves.json',{'schema':'datascape.unmeasured_response_candidates.v01','curves':curves})
        for mode in ('D','A'):
            jobs,manifest=make_plan(strokes,Layout(mode),order)
            path=root/(mode+'.plan.json.gz');save_json(path,manifest)
            validation=verify_plan(json.loads(gzip.decompress(path.read_bytes())),strokes,Layout(mode))
            if digest(manifest)!=previous['layouts'][mode]['plan_sha256']:raise ValueError('S3a plan changed')
            rows={}
            for curve in curves:
                profile=offline_profile(base,curve)
                profile.require('fixture',sorted({s.color_slot for s in strokes if s.medium=='color'}))
                cases={}
                for name,units in jobs.items():
                    commands,m=build_job(profile,units,'fixture')
                    lineage=verify_draw_lineage(commands,manifest['jobs'][name],profile,'fixture')
                    continuity=audit_continuity(commands,crossing) if mode=='D' else None
                    before=previous['layouts'][mode]['jobs'][name]
                    if m['M0_count'] or m['M0_reasons']:raise ValueError('routine pause inserted')
                    if m['counts'].get('same_color_reload',0)!=before['reloads']:raise ValueError('reload policy changed')
                    if m['counts'].get('full_wash',0)!=before['washes']:raise ValueError('wash policy changed')
                    if abs(m['distances']['station_transfer_3d_mm']-before['station_transfer_3d_mm'])>1e-7:raise ValueError('station transfer changed')
                    if next(c for c in reversed(commands) if c.kind=='move').xyz!=tuple(profile.data['motion']['park_xyz']):raise ValueError('park changed')
                    high=estimate_prepared(prepare_timing(commands,profile),dev)
                    cases[name]={'lineage':lineage,'D_continuity':continuity,'M0_count':0,'M0_reasons':[],
                        'reloads':m['counts'].get('same_color_reload',0),'washes':m['counts'].get('full_wash',0),
                        'PURGE_contacts':m['counts'].get('absorbent_contact',0),
                        'station_transfer_3d_mm':m['distances']['station_transfer_3d_mm'],
                        'synthetic_low':m['timing'],'unverified_DEV':high,
                        'geometry_diagnostics':extra_metrics(commands,profile)}
                    del commands
                    print(mode,curve['id'],name,round(high['acceleration_sensitive_seconds']/3600,3),flush=True)
                rows[curve['id']]=cases
                save_json(root/'partial_results.json',{'layout':mode,'finished_curves':list(rows)})
            result['layouts'][mode]={'plan_sha256':digest(manifest),'source_readback':validation,'curves':rows}
            del jobs,manifest
        if source_hash(strokes)!=canonical:raise ValueError('immutable artistic source changed')
        result['elapsed_seconds']=perf_counter()-began;save_json(root/'results.json',result)
        return result
    _atomic_output(a.output,write)


if __name__=='__main__':main()
