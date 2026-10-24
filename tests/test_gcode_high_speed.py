"""Candidate limits/return transitions and real reload, without device I/O."""
from copy import deepcopy
from pathlib import Path
from dataclasses import asdict
import json
import tempfile
import unittest

from benchmarks.integrated_330_v01.high_speed import (candidate_profile,controller_candidate,
    build_benchmark,elevated_air,verify_numeric,endurance_plan,PROFILE_PATH,export,verify_package)
from benchmarks.integrated_330_v01.measured_stations import inputs,build,verify
from benchmarks.integrated_330_v01.numeric_review import BANNER,xy_route,check_move
from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder,RuntimeMaterials
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import travel_segments,emit_station_operation
from datascape.gcode.production.exporter import _serialize
from datascape.gcode.production.timing import requested_feed

ROOT=Path(__file__).resolve().parents[1]


class HighSpeedTests(unittest.TestCase):
    def test_yaml_exactly_four_scalars_and_no_installation_claim(self):
        raw,diff,record=controller_candidate(ROOT)
        original=(ROOT/'benchmarks/integrated_330_v01/review_measured_stations/config.X860.candidate.yaml').read_bytes()
        restored=raw.replace(b'max_rate_mm_per_min: 20000.0',b'max_rate_mm_per_min: 15000.0').replace(b'acceleration_mm_per_sec2: 1500.0',b'acceleration_mm_per_sec2: 1200.0')
        self.assertEqual(restored,original);self.assertEqual(len(record['changes']),4)
        self.assertFalse(record['installed']);self.assertFalse(record['read_back'])
        self.assertTrue(record['Z_configuration_unchanged']);self.assertIn('+    max_rate_mm_per_min: 20000.0',diff)

    def test_separate_profile_keeps_pressure_and_prior_baseline(self):
        base=Profile.load(ROOT/PROFILE_PATH);before=deepcopy(base.data)
        p=candidate_profile(ROOT)
        self.assertEqual(base.data,before);self.assertEqual(base.data['brush_profiles'],p.data['brush_profiles'])
        self.assertEqual(p.data['motion']['paper_contact_z_range'],[-10,0])
        self.assertEqual(p.data['material']['ink_reload_mm'],1200);self.assertEqual(base.data['material']['ink_reload_mm'],1000)
        self.assertEqual(p.data['material']['color_reload_mm'],800)
        self.assertEqual(p.data['machine']['axis_max_rate_mm_min'],[20000,20000,8000])
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):p.require(stage)

    def test_long_return_has_real15000_main_and35mm_capped_arrival(self):
        p=candidate_profile(ROOT);rows=travel_segments((100,100,35),(840,380,35),'partially_depleted',p.data['motion'],True)
        self.assertEqual([r[1] for r in rows],[3000,15000,3000])
        from math import dist
        self.assertAlmostEqual(dist(rows[-2][0],rows[-1][0]),35)
        self.assertEqual(rows[-1][0],(840,380,35))
        block=(10,(1,0,0),15000,'station_transfer','travel','partially_depleted','arrival')
        self.assertEqual(requested_feed(block,p.data['motion']),3000)

    def test_short_moves_skip_high_feed_and_geometry_stays_collinear(self):
        p=candidate_profile(ROOT)
        for state in ('wet_loaded','ordinary_travel','partially_depleted'):
            rows=travel_segments((0,0,35),(3,4,35),state,p.data['motion'],True)
            self.assertEqual([r[2] for r in rows],['departure','arrival'])
            self.assertEqual([r[1] for r in rows],[3000,3000])
            self.assertEqual(rows[-1][0],(3,4,35))
            self.assertAlmostEqual(rows[0][0][1]/rows[0][0][0],4/3)

    def test_wet_paper_edges_distinct_from_station_arrival(self):
        p=candidate_profile(ROOT)
        a=travel_segments((0,0,35),(100,0,35),'wet_loaded',p.data['motion'])
        b=travel_segments((0,0,35),(100,0,35),'wet_loaded',p.data['motion'],True)
        self.assertEqual(a[-2][0],(95,0,35));self.assertEqual(b[-2][0],(65,0,35))
        self.assertEqual(a[1][1],12000)
        self.assertEqual(travel_segments((0,0,35),(100,0,35),'wet_loaded',candidate_profile(ROOT,15000).data['motion'])[1][1],15000)

    def test_40_sources_exact_depths_and_matched_air_no_contacts(self):
        p=candidate_profile(ROOT);plan,commands=build_benchmark(ROOT,p)
        oldreq,oldp,*_=inputs(ROOT);old=build(oldreq,oldp,'paint')
        draw=lambda rows:[(c.source_id,c.xyz,c.feed_mm_min) for c in rows if c.action=='draw']
        self.assertEqual(plan,oldreq);self.assertEqual(draw(commands),draw(old))
        air=elevated_air(commands,p);self.assertEqual(xy_route(air),xy_route(commands))
        self.assertTrue(all(c.xyz[2]>=15 for c in air if c.kind=='move'))
        for kind,rows in [('paint',commands),('air',air)]:
            text=BANNER+_serialize(rows,p,'plan','test','offline_review')
            report=verify_numeric(text,rows,p,kind,40)
            self.assertEqual(report['M0_count'],0);self.assertTrue(report['F15000_partially_depleted_main_segments'])
            with self.assertRaises(ValueError):verify_numeric(text.replace('F15000.000000000','F21000.000000000',1),rows,p,kind,40)
        agitation=[c for c in commands if c.travel_phase=='agitation']
        self.assertTrue(any(c.xyz==(830,380,8) and c.feed_mm_min==1500 for c in agitation))
        self.assertFalse(any(c.kind=='move' and c.feed_mm_min==60 for c in commands))

    def test_endurance_reload_after1200_at_next_original_boundary(self):
        p=candidate_profile(ROOT);plan,commands=build_benchmark(ROOT,p,True)
        self.assertEqual(plan['total_drawing_mm'],1440)
        self.assertEqual([c.message for c in commands if c.action=='endurance_reload_boundary'],['16'])
        first_reload=next(i for i,c in enumerate(commands) if c.action=='endurance_reload_boundary')
        self.assertEqual(sum(c.action=='draw' for c in commands[:first_reload]),15)
        self.assertEqual(sum(c.action=='draw' for c in commands[first_reload:]),3)
        self.assertEqual([c.message for c in commands if c.action=='benchmark_station_visit'],['ink:pigment_load','ink:same_color_reload'])
        d=deepcopy(p.data);d['material']['ink_reload_mm']=1000
        _,comparison=build_benchmark(ROOT,Profile.from_dict(d),True)
        self.assertEqual([c.message for c in comparison if c.action=='endurance_reload_boundary'],['14'])

    def test_lip_placeholder_is_disabled_and_enabling_fails_before_motion(self):
        p=candidate_profile(ROOT)
        for role in ('ink','water'):
            st=deepcopy(p.data['stations'][role]);lip=st['lip_stripping']
            self.assertFalse(lip['enabled']);self.assertIsNone(lip['measured_contact_xyz']);self.assertEqual(lip['relative_x_mm'],-20)
            st['lip_stripping']['enabled']=True;b=RuntimeBuilder(p)
            with self.assertRaisesRegex(ValueError,'stone-lip contact'):emit_station_operation(b,st,'wash','wet_loaded')
            self.assertEqual(b.commands,[])

    def test_color_change_used_return_then_water_is_wet_not_dry(self):
        p=candidate_profile(ROOT);b=RuntimeBuilder(p);m=RuntimeMaterials(b)
        b.position=(100,100,15);m.loaded='ink';m.distance=450
        m.wash()
        moves=[c for c in b.commands if c.action=='travel']
        self.assertEqual(moves[0].travel_state,'partially_depleted')
        self.assertTrue(any(c.travel_state=='wet_loaded' for c in moves))
        self.assertFalse(any(c.travel_state=='ordinary_travel' for c in moves))

    def test_baseline_stays_regenerable_and_bounds_checks_reject_crossing(self):
        verify(ROOT/'benchmarks/integrated_330_v01/review_measured_stations')
        p=candidate_profile(ROOT)
        with self.assertRaises(ValueError):check_move((840,380,35),(861,380,35),15000,'travel',p,'paint')
        with self.assertRaises(ValueError):check_move((0,898,35),(0,898,34),8000,'lift',p,'paint')

    def test_all_eight_saved_files_regenerate_and_modified_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'new';export(ROOT,out)
            self.assertEqual(verify_package(ROOT,out)['regenerated_numeric_Gcode_files'],8)
            file=out/'INK_ENDURANCE_1200_INK_REVIEW.gcode'
            file.write_text(file.read_text().replace('F15000.000000000','F16000.000000000',1))
            with self.assertRaisesRegex(ValueError,'SHA256'):verify_package(ROOT,out)


if __name__=='__main__':unittest.main()
