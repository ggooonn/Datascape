"""Full canonical Spring hover/Z-speed impact; no G-code or safety evidence.

Uses the production renderer/material policy with a labeled offline envelope-only
sink, synchronized axis/Z feed limiting, and the existing acceleration model.
No invented collision-free box or controller junction measurement is supplied.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from math import dist
from pathlib import Path
import argparse
import json

from datascape.gcode.binding import load_bound_spring,digest
from datascape.gcode.layout import Layout
from datascape.gcode.production.sequence import reference_order,make_plan,verify_plan
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import Builder,Materials,build_job,emit_station_operation,_station_geometry,shallow_wipe_points,material_station
from datascape.gcode.production.timing import prepare_timing,estimate_prepared
from datascape.gcode.production.exporter import _atomic_output,save_json
from benchmarks.commissioning_330_v01.preview import ReviewBuilder
from .numeric_review import check_move


class RuntimeBuilder(ReviewBuilder):
    def __init__(self,profile):
        super().__init__(profile);self.lengths=Counter();self.in_paper=False;self.at_station=False
        self.last_panel=None;self.time_context=None;self.paper_transfer_height=self.v['paper_hover_mm']

    def move(self,target,feed,action,state='ordinary_travel',**lineage):
        length=dist(self.position,target);rates=(0.,0.,0.);accel=min(self.m['axis_acceleration_mm_s2'])
        if length:
            unit=[abs(b-a)/length for a,b in zip(self.position,target)]
            feed=min(feed,*(cap/u for cap,u in zip(self.m['axis_max_rate_mm_min'],unit) if u))
            cap=self.v['pressure_z_mm_min'] if action in ('draw','pressure_variation') else self.v['z_travel_mm_min']
            if unit[2]:feed=min(feed,cap/unit[2])
            rates=tuple(feed*u for u in unit)
            accel=min(a/u for a,u in zip(self.m['axis_acceleration_mm_s2'],unit) if u)
        check_move(self.position,target,feed,action,self.profile,'paint',exact_benchmark_draw=False)
        category=self.time_context or ('drawing' if action=='draw' else
            'paper_engagement' if action in ('approach','initial_contact','pressure_variation','release','paper_release_clearance','retract') else
            'station_handling' if action.startswith('station_') else 'non_drawing_travel')
        super().move(target,feed,action,state,projected_acceleration_mm_s2=accel,
                     axis_velocity_mm_min=rates,time_category=category,**lineage)
        self.lengths['synchronized_drawing_3d_mm' if action=='draw' else 'non_draw_mm']+=length

    def dwell(self,seconds,action):
        super().dwell(seconds,action);self.commands[-1]=replace(self.commands[-1],time_category='station_handling')

    def park(self,state='ordinary_travel'):Builder.park(self,state)

    def result(self):return dict(offline_axis_envelope_only=True,collision_clearance_verified=False,M0_count=sum(c.kind=='pause' for c in self.commands))


class RuntimeMaterials(Materials):
    def station(self,role,action,material_key=None):
        st=deepcopy(self.b.profile.data['stations'][role])
        if role=='sponge':st=material_station(st,material_key or self.loaded)
        if action=='controlled_rewet':
            st.update(immersion_mm=st['rewet_immersion_mm'],dwell_seconds=st['rewet_dwell_seconds'],agitation_cycles=0)
        emit_station_operation(self.b,st,action,self.state,lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
        self.b.marker(action,role)


def calculate(machine,provenance,profile,output):
    root=Path(__file__).resolve().parents[2];p=Profile.load(profile)
    strokes,_=load_bound_spring(machine,provenance);order=reference_order(strokes,root/'config/plotter_v03/spring_s3a_order.json')
    jobs,manifest=make_plan(strokes,Layout('D'),order,palette_order=p.data['material']['color_order'])
    preserved=verify_plan(manifest,strokes,Layout('D'))
    report=dict(profile_sha256=p.sha256,plan_sha256=digest(manifest),canonical_preservation=preserved,
        physical_runtime_verified=False,production_Gcode_written=False,controller_installation_inferred=False,
        curves_unchanged=True,scenarios={},dynamics={
            'low_acceleration':{'axis_acceleration_mm_s2':[100,100,100],'junction_deviation_mm':0.01,'status':'synthetic conservative comparison'},
            'recorded_controller_reference':{'axis_acceleration_mm_s2':p.data['machine']['axis_acceleration_mm_s2'],
                'junction_deviation_mm':0.01,'status':'recorded installed YAML acceleration; junction0.01 ASSUMED, attained dynamics not measured'}})
    for name,hover,speed in [('hover10_Z6000',10,6000),('hover15_Z6000',15,6000),('hover15_Z7000',15,7000)]:
        d=deepcopy(p.data);d['motion'].update(paper_hover_mm=hover,z_travel_mm_min=speed,paper_approach_mm_min=speed,station_approach_mm_min=speed)
        scenario=Profile.from_dict(d);results={}
        for job,units in jobs.items():
            b=RuntimeBuilder(scenario);commands,metrics=build_job(scenario,units,'painting',offline_builder=b,offline_material=RuntimeMaterials(b))
            blocks=prepare_timing(commands,scenario);models={}
            for label,dynamics in report['dynamics'].items():
                m=deepcopy(scenario.data['machine']);m.update({k:v for k,v in dynamics.items() if k!='status'})
                models[label]=estimate_prepared(blocks,m)
            results[job]=dict(source_units=len(units),moves=sum(c.kind=='move' for c in commands),
                M0_count=metrics['M0_count'],loads_per_slot=metrics['loads_per_slot'],
                commanded_feed_seconds=models['recorded_controller_reference']['commanded_feed_seconds'],
                commanded_feed_seconds_by_category=models['recorded_controller_reference']['commanded_feed_seconds_by_category'],
                acceleration_models=models,end_G54_xyz=list(b.position),paper_hover_mm=hover,noncontact_Z_mm_min=speed)
            print(name,job,round(results[job]['commanded_feed_seconds']/60,2),'commanded minutes',flush=True)
            del commands,blocks,b
        report['scenarios'][name]=results
    report['hover_impact_seconds']={job:{
        'hover_only_at_Z6000':report['scenarios']['hover15_Z6000'][job]['commanded_feed_seconds']-report['scenarios']['hover10_Z6000'][job]['commanded_feed_seconds'],
        'combined_hover15_Z7000_vs_hover10_Z6000':report['scenarios']['hover15_Z7000'][job]['commanded_feed_seconds']-report['scenarios']['hover10_Z6000'][job]['commanded_feed_seconds']}
        for job in jobs}
    def write(out):save_json(out/'spring_runtime.json',report);return report
    return _atomic_output(output,write)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('machine','provenance','profile','output'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();calculate(**vars(a))
