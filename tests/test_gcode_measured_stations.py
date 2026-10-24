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
        self.assertFalse(prior['new_hover15_Z7000_and_other_feedback_refinements_physically_verified']);self.assertEqual(p.data['evidence'],[])

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
            self.assertIn((840,y),shallow_wipe_xy(st));self.assertIn((830,y+20),shallow_wipe_xy(st))
            w=st['shallow_wipe']
            self.assertEqual([w[k] for k in ('surface_z','compression_mm','reentry_lift_mm')],[9.0,1.5,10.0])
            self.assertIn('NOT newly measured',w['contact_status'])
            missing=deepcopy(st);missing['shallow_wipe']['surface_z']=None
            with self.assertRaisesRegex(ValueError,'requires surface_z'):shallow_wipe_points(missing)
        self.assertEqual(p.data['stations']['A2']['liquid_reference_z'],6)
        self.assertEqual(p.data['stations']['A2']['bottom_z'],1)

    def test_air_paint_pairing_real_two_pass_contact_and_z10_links(self):
        r,p,*_=inputs(ROOT); air=build(r,p,'air');paint=build(r,p,'paint')
        self.assertEqual(xy_route(air),xy_route(paint))
        self.assertTrue(all(c.xyz[2]>=15 for c in air if c.kind=='move'))
        substitutions=[c for c in paint if c.travel_phase=='NONCONTACT_SUBSTITUTION']
        self.assertEqual(substitutions,[])
        wipes=[c for c in paint if c.travel_phase=='shallow_wipe']
        self.assertEqual([c.xyz for c in wipes],[(840,465,7.5),(830,465,7.5)]*2+[(840,315,7.5),(830,315,7.5)])
        self.assertTrue(all(c.feed_mm_min==1000 for c in wipes))
        # Exactly 36 within-column links, at normal hover rather than Z35.
        pos=p.data['machine']['start_work_xyz'];low_links=0
        for c in paint:
            if c.kind=='move':
                if c.action=='travel' and c.xyz[:2]!=tuple(pos[:2]) and min(pos[2],c.xyz[2])==15:low_links+=1
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
        self.assertEqual([c.xyz for c in purge],[(840,137.5,1.5),(840,137.5,3.5)])
        d=deepcopy(p.data);d['motion']['contact_mm_min']=60
        self.assertEqual(station_phase_feed(d['stations']['A2'],d['motion'],'palette_loading'),1000)

    def test_strict_production_solid_wipe_and_pre_motion_failure(self):
        # Synthetic, NOT real machine evidence. This tests the production path.
        r,p,*_=inputs(ROOT);st=deepcopy(p.data['stations']['ink'])
        b=Builder(unit_profile())
        with self.assertRaises((ValueError,TypeError)):emit_station_operation(b,st,'pigment_load','ordinary_travel')
        self.assertEqual(b.commands,[])
        st['contact_box_xyz']=[[820,370,0],[860,480,20]]
        st['shallow_wipe'].update(surface_z=12,compression_mm=1,reentry_lift_mm=3)
        d=deepcopy(unit_profile().data);d['motion'].update(p.data['motion']);d['stations']['ink']=st
        b=Builder(bind(d));Materials(b).station('ink','pigment_load')
        wipes=[c for c in b.commands if c.travel_phase=='shallow_wipe']
        self.assertEqual([c.xyz for c in wipes],[(840,465,11),(830,465,11)])
        self.assertTrue(all(c.feed_mm_min==1000 for c in wipes))
        reentry=[c for c in b.commands if c.travel_phase=='reentry']
        self.assertTrue(any(c.xyz==(830,402.5,14) for c in reentry))
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
            self.assertFalse(verify(out)['solid_contact_Z_pending'])
            for name,job in report['jobs'].items():
                self.assertFalse(job['controller_bounds']['recorded_installed_X850_bounds_pass'])
                self.assertEqual(job['controller_bounds']['maximum_commanded_X'],855)
                self.assertEqual(job['M0_count'],0);self.assertTrue(job['M2_verified'])
                self.assertEqual(job['solid_wipe_contact_emitted'],'AIR' not in name)
                self.assertFalse(job['extended_surface_newly_measured'])
                self.assertTrue((out/(name+'.gcode')).read_text().endswith('M2\n'))
            path=out/(NAMES['water']+'.gcode')
            path.write_text(path.read_text().replace('F1000.000000000','F60.000000000',1))
            hashes=json.loads((out/'MANIFEST_SHA256.json').read_text())
            hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (out/'MANIFEST_SHA256.json').write_text(json.dumps(hashes))
            with self.assertRaisesRegex(ValueError,'shared plan'):verify(out)

    def test_lift_from_contact_before_any_lateral_offset_and_reject_low_clearance(self):
        r,p,*_=inputs(ROOT);commands=build(r,p,'paint')
        moves=[c for c in commands if c.kind=='move']
        first=[i for i,c in enumerate(moves) if c.travel_phase=='shallow_wipe' and c.xyz[0]==840]
        self.assertEqual(len(first),3)
        for i in first:
            end=moves[i].xyz
            self.assertEqual([c.xyz for c in moves[i+1:i+4]],
                             [(840,end[1],9),(840,end[1],17.5),(830,end[1],17.5)])
            self.assertEqual([c.feed_mm_min for c in moves[i+1:i+4]],[750,3000,3000])
            self.assertEqual(moves[i+2].xyz[2]-end[2],10)
        st=deepcopy(p.data['stations']['ink'])
        st['shallow_wipe']['reentry_lift_mm']=1
        with self.assertRaisesRegex(ValueError,'does not clear'):shallow_wipe_points(st,tuple)
        # Missing physical contact volume is still rejected by the official sink.
        with self.assertRaises((TypeError,ValueError)):emit_station_operation(Builder(unit_profile()),p.data['stations']['ink'],'pigment_load','ordinary_travel')

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
        self.assertTrue(second_link);self.assertTrue(all(c.xyz[2]==15 for c in second_link))

    def test_final_feedback_hover_feed_palette_and_zero_compression_purge(self):
        from datascape.gcode.production.trajectory import _station_geometry
        r,p,*_=inputs(ROOT);commands=build(r,p,'paint');air=build(r,p,'air')
        self.assertTrue(all(c.xyz[2]>=15 for c in air if c.kind=='move'))
        self.assertTrue(any(c.action=='paper_hover' and c.xyz[2]==15 and c.feed_mm_min==7000 for c in commands))
        self.assertTrue(all(c.feed_mm_min==7000 for c in commands if c.kind=='move' and c.action in ('lift','retract','paper_hover','approach','station_approach','park')))
        self.assertTrue(all(c.feed_mm_min==2000 for c in commands if c.kind=='move' and c.action in ('initial_contact','calibration_compression','release','paper_release_clearance')))
        for slot in p.data['material']['color_order']:
            st=p.data['stations'][slot];self.assertEqual(st['immersion_mm'],1)
            self.assertEqual(st['radius_mm'],5);self.assertEqual(_station_geometry(st,tuple)[0][2],5)
        sponge=p.data['stations']['sponge'];self.assertEqual(sponge['compression_mm'],0)
        self.assertEqual(_station_geometry(sponge,tuple)[0],(840,137.5,1.5))
        bad=deepcopy(sponge);bad['compression_mm']=-.1
        with self.assertRaises(ValueError):_station_geometry(bad,tuple)

    def test_pressed_lengths_and_configurable_endpoints_and_depth(self):
        from benchmarks.integrated_330_v01.measured_stations import job_check
        from datascape.gcode.production.exporter import _serialize
        from benchmarks.integrated_330_v01.numeric_review import BANNER
        r,p,_,prior,_,rec,_=inputs(ROOT)
        self.assertTrue(prior['previous_revision_both_Paint_completed_UGS_TCP'])
        d=deepcopy(p.data)
        for role,y in (('ink',475),('water',325)):
            d['stations'][role]['shallow_wipe']['end_xy'][1]=y
            d['stations'][role]['shallow_wipe']['compression_mm']=1.0
        alt=Profile.from_dict(d);commands=build(r,alt,'paint')
        text=BANNER+_serialize(commands,alt,digest(r),'alternate-offline-test','offline_review')
        checked=job_check(text,commands,alt,'paint',rec)
        self.assertEqual(checked['pressed_wiping_lengths_mm'],[30]*6)
        self.assertEqual(checked['wiping_parameters']['ink']['contact_z'],8)
        self.assertFalse(checked['controller_bounds']['actual_controller_configuration_reconciled'])

    def test_runtime_sink_matches_actual_production_geometry_and_feed_limits(self):
        from datascape.gcode.production.trajectory import build_job
        from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder
        _,p,*_=inputs(ROOT)
        d=deepcopy(unit_profile().data);d['motion'].update(p.data['motion'])
        d['motion']['paper_contact_z_range']=[-10,0];profile=bind(d)
        same=(strokes()[0],replace(strokes()[0],stroke_id='second',sequence=1))
        jobs,_=make_plan(same,Layout('D'),(0,1));units=jobs['SHARED_INK']
        from datascape.gcode.production.trajectory import draw_fragment
        strict=Builder(profile);offline=RuntimeBuilder(profile)
        for unit in units:
            draw_fragment(strict,unit[0],None,'painting');draw_fragment(offline,unit[0],None,'painting')
        compare=lambda rows:[(c.kind,c.action,c.xyz,c.feed_mm_min,c.source_id,c.source_vertex,c.artistic_pressure) for c in rows]
        self.assertEqual(compare(strict.commands),compare(offline.commands))

    def test_authorized_test_export_gcode_extension_remains_hash_verified_and_gated(self):
        from test_gcode_v03 import plan,measured_test_profile,auth
        from datascape.gcode.production.exporter import export_jobs,verify_export
        jobs,manifest=plan(Layout('D'));p=measured_test_profile()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'export'
            export_jobs(jobs,manifest,p,'air',auth(p,manifest,'air',jobs),out,program_extension='.gcode')
            self.assertTrue((out/'SHARED_INK.gcode').read_text().endswith('M2\n'))
            self.assertTrue(verify_export(out)['artifact_hashes_verified'])
            with self.assertRaises(ValueError):export_jobs(jobs,manifest,p,'air',None,Path(tmp)/'blocked',program_extension='.gcode')
            self.assertFalse((Path(tmp)/'blocked').exists())


if __name__=='__main__':unittest.main()
