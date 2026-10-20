"""Behavioral regression tests for offline clipping, registration and calibration."""
import json
import math
import os
from pathlib import Path
import random
import tempfile
import unittest
from dataclasses import replace
from datascape.gcode.models import Point,Stroke,PANELS,Panel
from datascape.gcode.clipping import clip_stroke
from datascape.gcode.io import load_strokes
from datascape.gcode.layout import Layout,Registration,WorkToMachine
from datascape.gcode.motion import (fragments,stroke_events,MotionSettings,Action,
                                     commented_preview,require_output_level)
from datascape.gcode.calibration import synthetic_profile,benchmarks,BrushCalibration
from datascape.gcode.stations import StationSimulator,StationConfiguration,ReloadPolicy
from datascape.gcode.estimation import Estimator,EstimateAssumptions,rest_to_rest_seconds
from datascape.gcode.binding import load_bound_spring


def stroke(points,ident='test',**kw):
    return Stroke(ident,tuple(Point(*p) for p in points),'A','INK','ink',**kw)


class GeometryTests(unittest.TestCase):
    def test_seam_owned_once_but_crossings_on_both_edges(self):
        s=stroke([(300,10,.2),(300,20,.9)])
        self.assertEqual(len(clip_stroke(s,PANELS[0])),1)
        self.assertEqual(clip_stroke(s,PANELS[1]),())
        for xy in ([(299,20,.2),(301,30,.8)],[(301,30,.8),(299,20,.2)]):
            parts=[clip_stroke(stroke(xy),p)[0] for p in PANELS]
            self.assertAlmostEqual(sum(v.source_spans[-1].arc_end_mm-v.source_spans[0].arc_start_mm for v in parts),math.sqrt(104))
            values=[point.pressure for part in parts for point in part.points if point.x==300]
            self.assertEqual(len(values),2)
            self.assertAlmostEqual(values[0],.5)
            self.assertAlmostEqual(values[1],.5)

    def test_no_bridge_after_seam_or_omitted_interval(self):
        s=stroke([(301,10,.2),(300,20,.4),(300,30,.8),(301,10,.2)])
        parts=clip_stroke(s,PANELS[1])
        self.assertEqual(len(parts),2)
        self.assertEqual([v.segment for p in parts for v in p.source_spans],[0,2])
        # Same XY upon return must still not weld across an outside excursion.
        s=stroke([(299,10,.2),(301,10,.4),(299,10,.2),(298,10,.6)])
        self.assertEqual(len(clip_stroke(s,PANELS[0])),2)

    def test_original_profiles_tiny_paths_and_arc_provenance(self):
        s=stroke([(299.999,10,.22),(300.001,10,.93),(300.1,11,.4)],pressure_sidecar_sha256='a'*64)
        pieces=[v for p in PANELS for v in clip_stroke(s,p)]
        self.assertEqual(len(pieces),2)
        for p in pieces:
            self.assertEqual(p.pressure_sidecar_sha256,'a'*64)
            for pt,loc in zip(p.points,p.source_locations):
                a,b=s.points[loc.segment:loc.segment+2]
                self.assertAlmostEqual(pt.pressure,a.pressure+loc.t*(b.pressure-a.pressure))
                self.assertAlmostEqual(pt.x,a.x+loc.t*(b.x-a.x))
            self.assertGreater(p.source_locations[-1].arc_mm,p.source_locations[0].arc_mm)
        tiny=stroke([(1,1,.22),(1.0000000001,1,.93)])
        self.assertEqual(len(clip_stroke(tiny,PANELS[0])),1)

    def test_random_partition_conserves_length_and_source_parameter(self):
        rng=random.Random(73)
        for _ in range(80):
            s=stroke([(rng.uniform(0,600),rng.uniform(0,900),rng.random()) for i in range(8)])
            original=sum(math.hypot(b.x-a.x,b.y-a.y) for a,b in zip(s.points,s.points[1:]))
            total=0
            for panel in PANELS:
                for piece in clip_stroke(s,panel):
                    total+=sum(math.hypot(b.x-a.x,b.y-a.y) for a,b in zip(piece.points,piece.points[1:]))
                    self.assertTrue(all(panel.x_min-1e-8<=p.x<=panel.x_max+1e-8 for p in piece.points))
            self.assertAlmostEqual(total,original,places=7)

    def test_corners_asymmetric_landmark_and_offsets(self):
        for mode,gap in (('A',0),('B',0),('C',50),('C',17),('D',0)):
            layout=Layout(mode,gap)
            panel=layout.panels[-1]
            start=0 if mode in ('A','D') else 300+gap
            self.assertEqual(layout.work_xy(panel,panel.x_min,900),(start,0))
            self.assertEqual(layout.work_xy(panel,panel.x_min,0),(start,900))
            self.assertEqual(layout.work_xy(panel,panel.x_min+13,123),(start+13,777))
        l=Layout('A',registrations=(Registration('P2',10,20,90),))
        x,y=l.work_xy(PANELS[1],313,877)
        self.assertAlmostEqual(x,-13);self.assertAlmostEqual(y,33)
        with self.assertRaises(ValueError): Layout('B',50)
        with self.assertRaises(ValueError): WorkToMachine((0,0,0)).xyz((0,0,0))

    def test_shared_order_streams_direction_and_gap_lift(self):
        strokes=(stroke([(301,5,.2),(299,5,.8)],'a',sequence=0),
                 stroke([(310,8,.4),(320,7,.6)],'b',sequence=1))
        shared=list(fragments(strokes,Layout('C',50)))
        self.assertEqual([f.stroke.origin_id for f in shared],['a','a','b'])
        self.assertEqual([f.panel for f in shared],['P2','P1','P2'])
        self.assertLess(shared[0].stroke.source_locations[-1].arc_mm,shared[1].stroke.source_locations[-1].arc_mm)
        for f in shared:
            events=list(stroke_events(f,MotionSettings(synthetic_profile())))
            self.assertEqual(events[-1].action,Action.LIFT)
            self.assertEqual(events[1].action,Action.TRAVEL)
            self.assertEqual(events[1].preview_z_mm,3)
            self.assertTrue(all(e.machine_xyz is None and e.calibrated_z_mm is None for e in events))
            if f.panel=='P2': self.assertTrue(all(x>=350 for x,y in f.work_xy))
        full=list(fragments(strokes,Layout('D')))
        self.assertEqual(len(full),2)
        self.assertEqual(full[0].stroke.points,strokes[0].points)


class MotionAndCalibrationTests(unittest.TestCase):
    def test_preserve_all_artistic_samples_in_constant_and_variable_modes(self):
        s=stroke([(10,10,.22),(20,15,.5),(40,10,.93)])
        f=next(fragments((s,),Layout()))
        for settings in (MotionSettings(synthetic_profile()),MotionSettings(mode='constant',constant_z_mm=-.2),MotionSettings()):
            events=list(stroke_events(f,settings))
            samples=[e for e in events if e.artistic_pressure is not None]
            self.assertEqual([e.artistic_pressure for e in samples],[.22,.5,.93])
            self.assertEqual(events[3].action,Action.CONTACT)
            self.assertEqual(events[-2].action,Action.RELEASE)
            if settings.mode=='constant': self.assertEqual({e.preview_z_mm for e in samples},{-.2})
            elif settings.profile is None: self.assertTrue(all(e.preview_z_mm is None for e in samples))
            self.assertTrue(all(line.startswith(';') for line in ''.join(commented_preview(events)).splitlines()))
        for level in (0,2,3):
            with self.assertRaises(ValueError): require_output_level(level)

    def test_nonlinear_mapping_domain_and_measurement_requirements(self):
        p=synthetic_profile()
        self.assertAlmostEqual(p.z_for(.35),-.19)
        self.assertNotEqual(p.z_for(.5),p.z_for(1)*.5)
        for value in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError): p.z_for(value)
        with self.assertRaises(ValueError): replace(p,status='measured')
        with self.assertRaises(ValueError): replace(p,knots=((.5,-.5),(.2,-.1)))
        with self.assertRaises(ValueError): MotionSettings(mode='constant')

    def test_benchmark_families(self):
        b=benchmarks(); names=[x.name for x in b]
        self.assertEqual(len(names),len(set(names)))
        self.assertIn('short-0.1',names)
        self.assertIn('entry-exit-artistic-taper',names)
        self.assertEqual({x.stroke.medium for x in b},{'ink','color'})
        self.assertEqual({x.feed_mm_min for x in b},{600,1200,2400})
        self.assertEqual(b,benchmarks())

    def test_station_sequence_reload_manual_refill_and_restart(self):
        sim=StationSimulator(ReloadPolicy(ink_distance_mm=1,color_distance_mm=1,manual_refill_every_loads=1))
        s=stroke([(10,10,.2),(20,10,.8)])
        a=next(fragments((s,),Layout()))
        initial=sim.before(a);sim.after(a)
        self.assertIn('ink_reload',[o.action for o in initial])
        self.assertIn('same_color_replenishment_request',[o.action for o in sim.before(a)])
        color=replace(s,stroke_id='c',medium='color',color_slot='A1')
        f=next(fragments((color,),Layout()))
        ops=sim.before(f);names=[o.action for o in ops]
        self.assertEqual(names,['color_tool_request','wash','sponge_wipe','controlled_rewet','gouache_load'])
        self.assertTrue(all(o.work_xyz is None for o in ops))
        sim.after(f);self.assertIn('manual_palette_refill_pause',[o.action for o in sim.before(f)])
        sim.interrupt();names=[o.action for o in sim.before(f)]
        self.assertIn('resume_preparation',names);self.assertIn('manual_brush_condition_check',names)
        with self.assertRaises(ValueError): StationConfiguration().contact_trajectory()
        with self.assertRaises(ValueError): StationConfiguration(status='measured',coordinate_frame='G54').require_measured()

    def test_estimates_analytic_distance_and_assumptions(self):
        a=EstimateAssumptions();self.assertAlmostEqual(rest_to_rest_seconds(100,6000,100),2)
        s=stroke([(1,1,.2),(4,5,.8)])
        estimator=Estimator()
        for e in stroke_events(next(fragments((s,),Layout())),MotionSettings(synthetic_profile())): estimator.add(e)
        result=estimator.result();self.assertAlmostEqual(result['drawing_mm'],5)
        self.assertEqual(result['counts']['initial_contact'],1)
        self.assertIsNone(result['station_travel_mm'])
        with self.assertRaises(ValueError): EstimateAssumptions(draw_mm_min=0)

    def test_missing_pressure_numeric_and_duplicate_ids_fail(self):
        source={'schema':'datascape.machine_vectors.v0.1','artwork_size_mm':[600,900],
                'strokes':[{'stroke_id':'s','points':[{'x':1,'y':1,'pressure':.2},{'x':2,'y':2,'pressure':.8}],
                            'layer':'A','medium':'ink','color_slot':'INK'}]}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.json'
            for mutation in ('missing','bool','duplicate'):
                obj=json.loads(json.dumps(source))
                if mutation=='missing': del obj['strokes'][0]['points'][0]['pressure']
                if mutation=='bool': obj['strokes'][0]['points'][0]['pressure']=True
                if mutation=='duplicate': obj['strokes']*=2
                path.write_text(json.dumps(obj))
                with self.assertRaises((ValueError,KeyError)): load_strokes(path)


@unittest.skipUnless(os.environ.get('DATASCAPE_BOUND_MACHINE'),'set bound paths to run pinned full-scene verification')
class FullSpringTests(unittest.TestCase):
    def test_full_bound_pressure_and_source_parameter_preservation(self):
        strokes,provenance=load_bound_spring(os.environ['DATASCAPE_BOUND_MACHINE'],os.environ['DATASCAPE_BOUND_PROVENANCE'])
        self.assertEqual(len(strokes),14951)
        self.assertEqual(sum(len(s.points) for s in strokes),240974)
        # Exercise every source vertex and every newly interpolated boundary value.
        from datascape.gcode.validation import validate_layout
        result=validate_layout(strokes,Layout())
        self.assertEqual(result['sources_covered'],14951)
        self.assertTrue(result['all_pressure_segment_bindings_valid'])
        with tempfile.TemporaryDirectory() as d:
            obj=json.loads(Path(os.environ['DATASCAPE_BOUND_MACHINE']).read_text())
            obj['strokes'][0]['points'][0]['pressure']=.5
            path=Path(d)/'mutated.json';path.write_text(json.dumps(obj))
            with self.assertRaises(ValueError): load_bound_spring(path,os.environ['DATASCAPE_BOUND_PROVENANCE'])


if __name__=='__main__': unittest.main()
