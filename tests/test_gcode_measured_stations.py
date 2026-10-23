"""Measured XY review and strict production Z contracts; no device activity."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from test_gcode_integrated_330 import unit_profile, bind
from test_gcode_v03 import strokes
from datascape.gcode.binding import digest
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import make_plan
from datascape.gcode.production.trajectory import (Builder, Materials, draw_fragment,
    shallow_wipe_points, shallow_wipe_xy, emit_station_operation, station_phase_feed)
from benchmarks.integrated_330_v01.measured_stations import (inputs, build, export, verify,
    controller_candidate, NAMES, PHASE_FEEDS)
from benchmarks.integrated_330_v01.numeric_review import xy_route, check_move
from benchmarks.integrated_330_v01.spring_pipeline import require_unified_profile, run

ROOT=Path(__file__).resolve().parents[1]


class MeasuredStationTests(unittest.TestCase):
    def test_controller_candidate_is_one_setting_and_not_installed(self):
        candidate,rec=controller_candidate(ROOT)
        old=(ROOT/'benchmarks/integrated_330_v01/config.installed.yaml').read_bytes()
        self.assertEqual(candidate.replace(b'    max_travel_mm: 860.0',b'    max_travel_mm: 850.0'),old)
        self.assertEqual(rec['installed_sha256'],'884fb232dfbe9f5396155f5ad90c231458913a29aaa723e415ba5a4ee2ed3280')
        self.assertFalse(rec['candidate_installed_or_read_back']); self.assertFalse(rec['soft_limits_setting_changed'])

    def test_same_geometry_depth_order_and_40_sources_new_feeds(self):
        r,p,_,prior,_,_,_=inputs(ROOT)
        old=json.loads((ROOT/'benchmarks/integrated_330_v01/review_station_final/plan.json').read_text())
        def geometry(req):
            cols=deepcopy(req['benchmark_columns'])
            for c in cols:
                for line in c['brush_lines']:line.pop('feed_mm_min')
            return cols
        self.assertEqual(geometry(r),geometry(old))
        commands=build(r,p,'paint'); draw=[c for c in commands if c.action=='draw']
        self.assertEqual(len(draw),40); self.assertTrue(all(c.feed_mm_min==6000 for c in draw))
        self.assertEqual([c.xyz[2] for c in draw],(list(range(-1,-11,-1))+list(range(-10,0)))*2)
        self.assertTrue(all(c.source_id for c in draw));self.assertFalse(any(c.kind=='pause' for c in commands))
        self.assertTrue(prior['X860_physically_measured_reported'])
        self.assertTrue(prior['large_baegunmo_strokes_to_G54_minus10_successful'])
        self.assertFalse(prior['new_unified_speeds_physically_verified']);self.assertEqual(p.data['evidence'],[])

    def test_measured_xy_and_nominal_z_stay_distinct(self):
        r,p,_,_,mapping,_,_=inputs(ROOT)
        self.assertEqual(len(mapping['all_registered_centers']),20)
        for slot in ('D1','D2','D4','D5'):
            a=mapping['slot_assessments'][slot]
            self.assertEqual(a['path_x_range'],[842,852]);self.assertEqual(a['axis_X860_headroom_mm'],8)
            self.assertTrue(a['brush_holder_XY_space_operator_confirmed'])
        for role,y in (('ink',445),('water',295)):
            st=p.data['stations'][role]
            self.assertEqual(st['agitation_xy_mm'],[15,0])
            self.assertIn((840,y),shallow_wipe_xy(st));self.assertIn((830,y+10),shallow_wipe_xy(st))
            with self.assertRaisesRegex(ValueError,'actual surface_z'):shallow_wipe_points(st)
        self.assertEqual(p.data['stations']['A2']['liquid_reference_z'],6)
        self.assertEqual(p.data['stations']['A2']['bottom_z'],1)

    def test_air_paint_pairing_safe_substitution_and_z10_links(self):
        r,p,*_=inputs(ROOT); air=build(r,p,'air');paint=build(r,p,'paint')
        self.assertEqual(xy_route(air),xy_route(paint))
        self.assertTrue(all(c.xyz[2]>=10 for c in air if c.kind=='move'))
        substitutions=[c for c in paint if c.travel_phase=='NONCONTACT_SUBSTITUTION']
        self.assertTrue(substitutions);self.assertTrue(all(c.xyz[2]==35 for c in substitutions))
        self.assertFalse(any(c.travel_phase in ('shallow_wipe','shallow_contact') for c in paint))
        # Exactly 36 within-column links, at normal hover rather than Z35.
        pos=p.data['machine']['start_work_xyz'];low_links=0
        for c in paint:
            if c.kind=='move':
                if c.action=='travel' and c.xyz[:2]!=tuple(pos[:2]) and min(pos[2],c.xyz[2])==10:low_links+=1
                pos=c.xyz
        self.assertEqual(low_links,36*3)  # retained wet departure/main/arrival
        self.assertEqual(paint[-2].xyz,(800,800,35))

    def test_phases_dwell_and_no_f60_clamp(self):
        r,p,*_=inputs(ROOT); commands=build(r,p,'paint')
        self.assertEqual([c.seconds for c in commands if c.kind=='dwell'],[2,2,5,4,1,1])
        self.assertFalse(any(c.kind=='move' and c.feed_mm_min==60 for c in commands))
        self.assertTrue(any(c.travel_phase=='agitation' and c.xyz==(825,380,8) and c.feed_mm_min==1000 for c in commands))
        self.assertTrue(any(c.travel_phase=='agitation' and c.xyz==(855,380,8) for c in commands))
        self.assertTrue(any(c.travel_phase=='palette_loading' and c.feed_mm_min==1000 for c in commands))
        purge=[c for c in commands if c.action=='station_absorbent_contact']
        self.assertEqual([c.xyz for c in purge],[(840,137.5,.5),(840,137.5,3.5)])
        d=deepcopy(p.data);d['motion']['contact_mm_min']=60
        self.assertEqual(station_phase_feed(d['stations']['A2'],d['motion'],'palette_loading'),1000)

    def test_strict_production_solid_wipe_and_pre_motion_failure(self):
        # Synthetic, NOT real machine evidence. This tests the production path.
        r,p,*_=inputs(ROOT);st=deepcopy(p.data['stations']['ink'])
        b=Builder(unit_profile())
        with self.assertRaises((ValueError,TypeError)):emit_station_operation(b,st,'pigment_load','ordinary_travel')
        self.assertEqual(b.commands,[])
        st['contact_box_xyz']=[[820,370,0],[860,460,20]]
        st['shallow_wipe'].update(surface_z=12,compression_mm=1,reentry_lift_mm=3)
        d=deepcopy(unit_profile().data);d['motion'].update(p.data['motion']);d['stations']['ink']=st
        b=Builder(bind(d));Materials(b).station('ink','pigment_load')
        wipes=[c for c in b.commands if c.travel_phase=='shallow_wipe']
        self.assertEqual([c.xyz for c in wipes],[(840,455,11),(830,455,11),(830,455,11)])
        self.assertTrue(all(c.feed_mm_min==1000 for c in wipes))
        reentry=[c for c in b.commands if c.travel_phase=='reentry']
        self.assertTrue(any(c.xyz==(830,402.5,15) for c in reentry))
        self.assertEqual(b.position[2],35)

    def test_both_controller_bounds_and_formal_gates(self):
        r,p,*_=inputs(ROOT)
        with self.assertRaises(ValueError):p.require('air')
        self.assertTrue(any('controller target' in issue for issue in p.issues('air')))
        d=deepcopy(p.data);d['machine']['machine_bounds_xyz'][1][0]=850
        with self.assertRaisesRegex(ValueError,'envelope'):build(r,Profile.from_dict(d),'paint')
        self.assertFalse(p.data['machine']['target_config_installed'])
        with self.assertRaisesRegex(ValueError,'Z velocity'):check_move((20,30,0),(20,30,-1),2001,'calibration_compression',p,'paint')

    def test_evidence_scope_covers_extended_xy_and_agitation(self):
        _,p,*_=inputs(ROOT);scope=p.evidence_scope_sha256('air_run')
        for key in ('agitation','wipe'):
            d=deepcopy(p.data)
            if key=='agitation':d['stations']['ink']['agitation_xy_mm'][0]=14
            else:d['stations']['ink']['shallow_wipe']['end_xy'][1]=454
            self.assertNotEqual(scope,Profile.from_dict(d).evidence_scope_sha256('air_run'))

    def test_review_round_trip_and_rehashed_gcode_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'review';report=export(ROOT,out)
            self.assertTrue(verify(out)['solid_contact_Z_pending'])
            for name,job in report['jobs'].items():
                self.assertFalse(job['controller_bounds']['recorded_installed_X850_bounds_pass'])
                self.assertEqual(job['controller_bounds']['maximum_commanded_X'],855)
                self.assertEqual(job['M0_count'],0);self.assertTrue(job['M2_verified'])
                self.assertTrue((out/(name+'.gcode')).read_text().endswith('M2\n'))
            path=out/(NAMES['water']+'.gcode')
            path.write_text(path.read_text().replace('F1000.000000000','F60.000000000',1))
            hashes=json.loads((out/'MANIFEST_SHA256.json').read_text())
            hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (out/'MANIFEST_SHA256.json').write_text(json.dumps(hashes))
            with self.assertRaisesRegex(ValueError,'shared plan'):verify(out)

    def test_spring_profile_no_fallback_no_authorization_and_paper10(self):
        _,p,*_=inputs(ROOT);require_unified_profile(p)
        d=deepcopy(p.data);d['motion']['draw_mm_min']=5000
        with self.assertRaisesRegex(ValueError,'unified'):require_unified_profile(Profile.from_dict(d))
        with tempfile.TemporaryDirectory() as tmp:
            profile=Path(tmp)/'p.json';profile.write_text(json.dumps(p.data))
            with self.assertRaisesRegex(ValueError,'authorization'):run('ink','missing','missing',profile,Path(tmp)/'out')
        # Exercise actual Spring draw_fragment without a fake real calibration.
        same=(strokes()[0],replace(strokes()[0],stroke_id='second',sequence=1))
        jobs,_=make_plan(same,Layout('D'),(0,1))
        units=jobs['SHARED_INK'];d=deepcopy(unit_profile().data);d['motion'].update(p.data['motion'])
        d['motion']['paper_contact_z_range']=[-10,0];b=Builder(bind(d))
        for unit in units:draw_fragment(b,unit[0],None,'painting')
        begins=[i for i,c in enumerate(b.commands) if c.action=='initial_contact']
        self.assertEqual(len(begins),2)
        second_link=[c for c in b.commands[begins[0]+1:begins[1]] if c.action=='travel']
        self.assertTrue(second_link);self.assertTrue(all(c.xyz[2]==10 for c in second_link))


if __name__=='__main__':unittest.main()
