"""Exact ink-only distances and final local lip/first-departure policy."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from benchmarks.integrated_330_v01 import final_ink_endurance as final
from benchmarks.integrated_330_v01 import final_lip as baseline
from benchmarks.integrated_330_v01.numeric_review import xy_route
from benchmarks.integrated_330_v01.spring_runtime import RuntimeBuilder, RuntimeMaterials
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import emit_station_operation, _station_geometry, shallow_wipe_points, travel_segments

ROOT=Path(__file__).resolve().parents[1]


class FinalInkEnduranceTests(unittest.TestCase):
    def test_exact_plan_distances_depths_paper_bounds_and_common_prefix(self):
        a=final.plan('A1200');b=final.plan('B1500')
        self.assertEqual(a['strokes'],b['strokes'][:12])
        for case,n,total in [('A1200',12,1200),('B1500',15,1500)]:
            p=final.plan(case);self.assertEqual(len(p['strokes']),n)
            self.assertEqual(sum(s['drawing_xy_mm'] for s in p['strokes']),total)
            self.assertEqual(p['strokes'][-1]['cumulative_xy_mm'],total)
            self.assertEqual([s['z_mm'] for s in p['strokes']],[-(1+i%7) for i in range(n)])
            for s in p['strokes']:
                self.assertEqual(s['end_xy'][0]-s['start_xy'][0],100)
                for xy in (s['start_xy'],s['end_xy']):self.assertTrue(all(10<=v<=320 for v in xy))
        with self.assertRaises(ValueError):final.plan('C')

    def test_only_requested_profile_parameters_change_and_yaml_pressure_stay_fixed(self):
        old=baseline.profile(ROOT);p=final.profile(ROOT)
        for key in ('machine','material','brush_profiles'):self.assertEqual(p.data[key],old.data[key])
        new_motion=deepcopy(p.data['motion'])
        for state in ('ordinary_travel','partially_depleted'):
            self.assertEqual(new_motion['segmented_travel'][state]['departure_mm_min'],15000)
            new_motion['segmented_travel'][state]['departure_mm_min']=old.data['motion']['segmented_travel'][state]['departure_mm_min']
        self.assertEqual(new_motion,old.data['motion'])
        for role in old.data['stations']:
            actual=deepcopy(p.data['stations'][role]);expected=deepcopy(old.data['stations'][role])
            if role in ('ink','water'):
                lip=actual.pop('lip_stripping');old_lip=expected.pop('lip_stripping')
                for k in ('measured_contact_xyz','relative_x_mm','safe_retract_z','coordinate_source'):
                    self.assertEqual(lip[k],old_lip[k])
                self.assertEqual(lip['contact_feed_mm_min'],1500);self.assertEqual(lip['approach_clearance_z'],20)
            self.assertEqual(actual,expected)
        self.assertEqual(p.data['material']['ink_reload_mm'],1200)
        self.assertEqual(p.data['material']['color_reload_mm'],800)
        self.assertEqual(baseline.yaml_candidate(ROOT)[0],(ROOT/'benchmarks/integrated_330_v01/review_final_lip/config.X860.Y900.final_lip.candidate.yaml').read_bytes())

    def test_both_independent_jobs_load_once_do_not_reload_and_park_used_brush(self):
        p=final.profile(ROOT)
        for case,total in final.CASES.items():
            request,programs=final.build(ROOT,p,case)
            self.assertEqual(xy_route(programs['AIR']),xy_route(programs['INK']))
            for kind,commands in programs.items():
                checked=final.readback(final.render(commands,p,request,kind),commands,p,request,kind)
                self.assertEqual(checked['drawing_xy_mm'],total)
                self.assertEqual(checked['station_visits'],['ink:pigment_load'])
                self.assertEqual(checked['reloads_during_test'],0)
                self.assertEqual(checked['start_work_xyz'],[0,900,35]);self.assertEqual(checked['end_work_xyz'],[800,800,35])
                self.assertEqual(checked['M0_count'],0);self.assertTrue(checked['M2_verified'])
                self.assertEqual(checked['departure_feeds']['ordinary_travel'],[15000])
                self.assertEqual(checked['departure_feeds']['partially_depleted'],[15000])

    def test_ink_and_water_local_connection_have_no_global_height_round_trip(self):
        p=final.profile(ROOT)
        for role in ('ink','water'):
            b=RuntimeBuilder(p);RuntimeMaterials(b).station(role,'pigment_load' if role=='ink' else 'wash')
            moves=[c for c in b.commands if c.kind=='move']
            report=final.check_lip(moves,'INK',p,role)
            self.assertEqual(report['local_connection_z'],20)
            self.assertEqual(report['lip_end'][0],795)
            self.assertEqual(report['approach_and_strip_feed_mm_min'],1500)
            self.assertFalse(any(c.travel_phase=='lip_contact' for c in moves))
            self.assertEqual(b.position[2],35)

    def test_immediate_dry_return_feed_and_slow_arrival_in_short_routes(self):
        p=final.profile(ROOT)
        for state in ('ordinary_travel','partially_depleted'):
            for length in (10,100,500):
                rows=travel_segments((0,0,35),(length,0,35),state,p.data['motion'],True)
                self.assertEqual(rows[0][1],15000);self.assertEqual(rows[-1][1],3000)
                self.assertEqual(rows[-1][0],(length,0,35))
            long=travel_segments((0,0,35),(500,0,35),state,p.data['motion'],True)
            self.assertEqual(500-long[-2][0][0],35)
        wet=travel_segments((0,0,35),(500,0,35),'wet_loaded',p.data['motion'],True)
        self.assertEqual([r[1] for r in wet],[3000,12000,3000])

    def test_unsafe_local_connection_is_rejected_before_any_station_move(self):
        p=final.profile(ROOT)
        for field,value in [('approach_clearance_z',19),('approach_clearance_z',36),
            ('approach_clearance_z',float('nan')),('approach_xy_mm_min',15000),('contact_feed_mm_min',1501)]:
            st=deepcopy(p.data['stations']['ink']);st['lip_stripping'][field]=value;b=RuntimeBuilder(p)
            with self.assertRaises(ValueError):emit_station_operation(b,st,'pigment_load','ordinary_travel',
                lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
            self.assertEqual(b.commands,[])
        st=deepcopy(p.data['stations']['ink']);st['shallow_wipe']['surface_z']=21
        b=RuntimeBuilder(p)
        with self.assertRaisesRegex(ValueError,'vertically'):
            emit_station_operation(b,st,'pigment_load','ordinary_travel',
                lambda s:_station_geometry(s,tuple),lambda s:shallow_wipe_points(s,tuple))
        self.assertEqual(b.commands,[])

    def test_numeric_checker_rejects_reload_distance_depth_and_station_mutations(self):
        p=final.profile(ROOT);request,programs=final.build(ROOT,p,'B1500');original=programs['INK']
        draw=next(i for i,c in enumerate(original) if c.action=='draw')
        strip=next(i for i,c in enumerate(original) if c.travel_phase=='lip_strip')
        mutations=[(draw,dict(xyz=(121,20,-1))),(draw,dict(xyz=(120,20,-8))),
            (strip,dict(feed_mm_min=300)),(strip-1,dict(xyz=(815,458,35)))]
        for index,change in mutations:
            commands=list(original);commands[index]=replace(commands[index],**change)
            with self.assertRaises(ValueError):final.readback(final.render(commands,p,request,'INK'),commands,p,request,'INK')
        commands=list(original);i=next(i for i,c in enumerate(commands) if c.action=='benchmark_station_visit')
        commands[i]=replace(commands[i],message='ink:same_color_reload')
        with self.assertRaises(ValueError):final.readback(final.render(commands,p,request,'INK'),commands,p,request,'INK')

    def test_authorization_and_installation_evidence_are_not_fabricated(self):
        p=final.profile(ROOT)
        self.assertEqual(p.data['status'],'nominal_review');self.assertEqual(p.data['evidence'],[])
        self.assertFalse(p.data['machine']['target_config_installed'])
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):p.require(stage)

    def test_four_complete_programs_regenerate_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'review';final.export(ROOT,out)
            self.assertEqual(len(list(out.glob('*.gcode'))),4)
            self.assertEqual(final.verify(ROOT,out)['numeric_review_files_regenerated'],4)
            path=out/'INK_ENDURANCE_B1500_INK_REVIEW.gcode'
            path.write_text(path.read_text().replace('F1500.000000000','F300.000000000',1))
            with self.assertRaisesRegex(ValueError,'SHA256'):final.verify(ROOT,out)

    def test_previous_40_stroke_lip_baseline_reproduces_without_new_policy(self):
        self.assertEqual(baseline.verify(ROOT,ROOT/'benchmarks/integrated_330_v01/review_final_lip')['numeric_review_files_regenerated'],3)


if __name__=='__main__':unittest.main()
