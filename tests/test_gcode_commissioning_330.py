"""Commissioning contracts exercised only with ephemeral synthetic unit evidence."""
import gzip,json,hashlib,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from test_gcode_v03 import measured_test_profile,auth
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.benchmark import air_plan,require_air_profile
from datascape.gcode.production.calibration_jobs import build_calibration,validate_request
from datascape.gcode.production.exporter import export_calibration,export_jobs,verify_export
from datascape.gcode.production.__main__ import main
from benchmarks.commissioning_330_v01.design import designs,profile,KNOTS
from benchmarks.commissioning_330_v01.preview import calibration_review,air_review,write_review,verify_review

ROOT=Path(__file__).resolve().parents[1]


def unit_profile(stations=True):
    d=deepcopy(measured_test_profile().data)
    d['machine']['start_work_xyz']=[0,898,35];d['motion']['park_xyz']=[800,800,32]
    d['motion']['paper_contact_z_range']=[-3,0];d['motion']['local_hover']={'enabled':False,'height_mm':5,'max_distance_mm':10}
    d['brush_profiles']['ink']['knots']=deepcopy(KNOTS)
    if not stations:d['stations']={}
    p=Profile.from_dict(d)
    for e in d['evidence']:e['calibration_sha256']=p.calibration_sha256
    return Profile.from_dict(d)


class CommissioningTests(unittest.TestCase):
    def test_provisional_profile_keeps_reported_frame_but_not_invented_offsets_or_station_points(self):
        p=profile(ROOT);m=p.data['machine'];s=p.data['stations']
        self.assertEqual(m['start_work_xyz'],[0,898,35]);self.assertEqual(p.data['motion']['park_xyz'],[800,800,32])
        self.assertIsNone(m['g54_to_machine_xyz']);self.assertIsNone(m['installed_config_sha256']);self.assertFalse(p.data['evidence'])
        self.assertFalse(p.data['motion']['local_hover']['enabled'])
        for r in ('water','ink'):
            self.assertIsNone(s[r]['deep_surface_xyz']);self.assertIsNone(s[r]['shallow_surface_xyz']);self.assertIsNone(s[r]['liquid_reference_z'])
            self.assertEqual(s[r]['immersion_mm'],2)
        self.assertIsNone(s['sponge']['surface_z']);self.assertEqual(s['sponge']['compression_mm'],.5)
        self.assertTrue(p.issues('air'))
        self.assertFalse(any('sponge' in e for e in p.issues('calibration',[])))

    def test_work_coordinate_benchmark_keeps_exact_XY_in_330_region(self):
        request=designs()['A_SHORT'];strokes,jobs,m=air_plan(request)
        for path,unit in zip(request['paths'],jobs['BENCHMARK_A_AIR']):self.assertEqual(path['work_xy'],[list(xy) for xy in unit[0].work_xy])
        self.assertTrue(m['benchmark']['not_a_Spring_job']);self.assertTrue(all(s.pressure_sidecar_sha256 is None for s in strokes))
        bad=deepcopy(request);bad['paths'][0]['work_xy'][0]=[321,20]
        with self.assertRaisesRegex(ValueError,'margin'):air_plan(bad)

    def test_authorized_synthetic_air_uses_existing_export_and_delivered_verifier(self):
        p=unit_profile(False);r=designs()['A_SHORT'];_,jobs,m=air_plan(r)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'air';export_jobs(jobs,m,p,'air',auth(p,m,'air',jobs),out)
            check=verify_export(out);self.assertEqual(check['jobs']['BENCHMARK_A_AIR']['M0_count'],0)
            text=(out/'BENCHMARK_A_AIR.nc').read_text();self.assertTrue(text.endswith('M2\n'));self.assertIn('X800.000000000 Y800.000000000 Z32.000000000',text)
            commands=json.loads(gzip.decompress((out/'BENCHMARK_A_AIR.trajectory.json.gz').read_bytes()))
            self.assertTrue(all(c['xyz'][2]>=10 for c in commands if c['kind']=='move'))
            self.assertFalse(any(c['action'].startswith('station_') for c in commands))

    def test_unmeasured_no_authorization_cannot_create_executable_artifacts(self):
        p=profile(ROOT);r=designs()['A_SHORT'];_,jobs,m=air_plan(r)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'blocked'
            with self.assertRaises(ValueError):export_jobs(jobs,m,p,'air',None,out)
            self.assertFalse(out.exists())
            with self.assertRaises(ValueError):export_calibration(designs()['B_DEPTH_1'],p,None,out)
            self.assertFalse(out.exists())

    def test_manually_loaded_constant_lines_need_no_Purge_or_color_calibration(self):
        p=unit_profile(False);r=designs()['B_DEPTH_1']
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'contact';export_calibration(r,p,auth(p,r,'calibration',['CALIBRATION']),out)
            check=verify_export(out)['jobs']['CALIBRATION'];self.assertEqual(check['M0_count'],3)
            data=json.loads((out/'trajectory.json').read_text())
            self.assertFalse(any(c['action'].startswith('station_') for c in data))
            self.assertTrue(any(c['xyz']==[90,40,-1] for c in data if c['kind']=='move'))
            self.assertTrue(all(c['travel_state']=='wet_loaded' for c in data if c['action']=='travel'))

    def test_pressure_samples_use_exact_multi_knot_mapping_and_Z_caps(self):
        p=unit_profile(False);r=designs()['C_LOW'];commands,_=build_calibration(r,p)
        samples=r['pressure_lines'][0]['samples'];actual=[c for c in commands if c.artistic_pressure is not None]
        self.assertEqual([c.artistic_pressure for c in actual],[s['pressure'] for s in samples])
        for c,s in zip(actual,samples):self.assertEqual(c.xyz,(*s['xy'],p.brush_for('ink','INK').z_for(s['pressure'])))
        for c in commands:
            if c.kind=='move':self.assertLessEqual(c.axis_velocity_mm_min[2],p.data['motion']['pressure_z_mm_min'] if c.action in ('draw','pressure_variation') else p.data['motion']['z_travel_mm_min'])
        with self.assertRaisesRegex(ValueError,'test envelope'):build_calibration(designs()['C_EXTENDED_LATER'],p)
        bad=deepcopy(r);bad['pressure_lines'][0]['samples'][1]['pressure']=1.1
        with self.assertRaisesRegex(ValueError,'no extrapolation'):build_calibration(bad,p)
        bad=deepcopy(r);bad['pressure_lines'][0]['samples'][1]['xy'][0]=321
        with self.assertRaisesRegex(ValueError,'benchmark region'):build_calibration(bad,p)
        d=deepcopy(p.data);d['motion']['draw_mm_min']=300;q=Profile.from_dict(d)
        for e in d['evidence']:e['calibration_sha256']=q.calibration_sha256
        capped,_=build_calibration(r,Profile.from_dict(d))
        self.assertTrue(all(c.feed_mm_min<=300 for c in capped if c.action=='draw'))

    def test_pressure_and_hover_require_prior_contact_but_do_not_mark_production_clearance(self):
        d=deepcopy(unit_profile(False).data);d['evidence']=[e for e in d['evidence'] if e['check']!='paper_contact'];p=Profile.from_dict(d)
        for key in ('C_LOW','D_HOVER'):
            with self.assertRaisesRegex(ValueError,'paper_contact'):build_calibration(designs()[key],p)
        before=deepcopy(unit_profile(False).data);q=Profile.from_dict(before);build_calibration(designs()['D_HOVER'],q)
        self.assertEqual(q.data,before);self.assertFalse(q.evidence_passed('local_hover_clearance'))

    def test_local_hover_stays_at_selected_height_between_separate_strokes(self):
        p=unit_profile(False);commands,metrics=build_calibration(designs()['D_HOVER'],p)
        group=next(i for i,c in enumerate(commands) if c.kind=='pause' and 'LOCAL HOVER TEST 1:' in c.message)
        tail=commands[group+1:];first=next(i for i,c in enumerate(tail) if c.action=='draw')
        next_contact=next(i for i,c in enumerate(tail[first+1:],first+1) if c.action=='initial_contact')
        lateral=[c for c in tail[first+1:next_contact] if c.action=='travel']
        self.assertTrue(lateral);self.assertTrue(all(c.xyz[2]==5 for c in lateral))
        self.assertEqual(metrics['M0_count'],4)
        # All six strokes have independent contact/release; no painted join is synthesized.
        self.assertEqual(sum(c.action=='initial_contact' for c in commands),6);self.assertEqual(sum(c.action=='release' for c in commands),6)

    def test_hover_gap_boundary_and_full_low_corridor_collisions_fail(self):
        p=unit_profile(False);r=deepcopy(designs()['D_HOVER']);r['hover_groups'][1]['strokes'][1]['start_xy'][0]=61
        with self.assertRaisesRegex(ValueError,'distance'):build_calibration(r,p)
        r=deepcopy(designs()['D_HOVER']);r['hover_groups'][1]['hover_mm']=.5
        with self.assertRaisesRegex(ValueError,'approach boundary'):build_calibration(r,p)
        d=deepcopy(p.data);d['machine']['keepout_boxes']=[[[51,249,4.9],[54,251,5.1]]];q=Profile.from_dict(d)
        for e in d['evidence']:e['calibration_sha256']=q.calibration_sha256
        with self.assertRaisesRegex(ValueError,'keepout'):build_calibration(designs()['D_HOVER'],Profile.from_dict(d))

    def test_color_station_and_cloth_are_not_required_for_brush_only_preview(self):
        p=profile(ROOT)
        with tempfile.TemporaryDirectory() as t:
            for key,r in designs().items():
                commands=air_review(r,p) if key.startswith('A_') else calibration_review(r,p)
                path=Path(t)/(key+'.preview.txt');result=write_review(path,commands,p,r)
                self.assertTrue(result['all_lines_commented']);self.assertFalse(result['authorized'])
                with self.assertRaisesRegex(ValueError,'.nc is prohibited'):write_review(Path(t)/'bad.nc',commands,p,r)
            r=designs()['C_LOW'];c=calibration_review(r,p);path=Path(t)/'drift.preview.txt';write_review(path,c,p,r)
            path.write_text(path.read_text().replace(' F600.000000000',' F601.000000000',1))
            with self.assertRaisesRegex(ValueError,'G54/feed mismatch'):verify_review(path,c,p,r)

    def test_delivered_calibration_rebuild_detects_IR_and_Gcode_tampering_after_rehash(self):
        p=unit_profile(False);r=designs()['C_LOW']
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'contact';export_calibration(r,p,auth(p,r,'calibration',['CALIBRATION']),out);verify_export(out)
            data=json.loads((out/'trajectory.json').read_text());i=next(i for i,c in enumerate(data) if c['artistic_pressure'] is not None)
            c=data[i];old_line='G1 '+' '.join(k+f'{v:.9f}' for k,v in zip('XYZ',c['xyz']))+f" F{c['feed_mm_min']:.9f}"
            data[i]['xyz'][2]-=.001;(out/'trajectory.json').write_text(json.dumps(data))
            new_line='G1 '+' '.join(k+f'{v:.9f}' for k,v in zip('XYZ',c['xyz']))+f" F{c['feed_mm_min']:.9f}"
            nc=out/'CALIBRATION.nc';nc.write_text(nc.read_text().replace(old_line,new_line,1))
            hashes=json.loads((out/'MANIFEST_SHA256.json').read_text())
            for name in ('trajectory.json','CALIBRATION.nc'):hashes[name]=hashlib.sha256((out/name).read_bytes()).hexdigest()
            (out/'MANIFEST_SHA256.json').write_text(json.dumps(hashes))
            with self.assertRaisesRegex(ValueError,'authorized test request'):verify_export(out)

    def test_station_air_tour_requires_exact_profile_roles_and_measured_centers_at_API(self):
        r=designs()['A_STATION_OPTIONAL'];p=unit_profile();_,jobs,m=air_plan(r)
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'station tour differs'):export_jobs(jobs,m,p,'air',auth(p,m,'air',jobs),Path(t)/'blocked')
            d=deepcopy(p.data);d['motion']['air_station_roles']=r['station_air_roles']
            for role in r['station_air_roles']:d['stations'][role]['center_xy']=d['stations'][role]['deep_surface_xyz'][:2]
            q=Profile.from_dict(d)
            for e in d['evidence']:e['calibration_sha256']=q.calibration_sha256
            q=Profile.from_dict(d);out=Path(t)/'air';export_jobs(jobs,m,q,'air',auth(q,m,'air',jobs),out)
            verify_export(out)
            data=json.loads(gzip.decompress((out/'BENCHMARK_A_AIR.trajectory.json.gz').read_bytes()))
            self.assertEqual(sum(c['action']=='station_air_only' for c in data),2)
            self.assertTrue(all(c['xyz'][2]>=10 for c in data if c['kind']=='move'))

    def test_station_trial_evidence_is_invalidated_by_liquid_or_cloth_changes(self):
        d=deepcopy(unit_profile().data);p=Profile.from_dict(d)
        d['evidence'].append({'check':'station_ink_trial','status':'passed','scope_sha256':p.evidence_scope_sha256('station_ink_trial'),'operator':'synthetic','date':'synthetic','method':'unit fixture only'})
        self.assertTrue(Profile.from_dict(d).evidence_passed('station_ink_trial'));d['stations']['ink']['liquid_reference_z']+=1
        self.assertFalse(Profile.from_dict(d).evidence_passed('station_ink_trial'))

    def test_cli_prepare_and_painting_rejection_are_independent_of_Spring_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t);r=t/'request.json';r.write_text(json.dumps(designs()['A_SHORT']))
            self.assertEqual(main(['prepare','--benchmark-plan',str(r),'--output',str(t/'prepared')]),0)
            p=t/'profile.json';p.write_text(json.dumps(profile(ROOT).data));a=t/'auth.json';a.write_text('{}')
            self.assertEqual(main(['export','--benchmark-plan',str(r),'--stage','painting','--profile',str(p),'--authorization',str(a),'--output',str(t/'blocked')]),2)
            self.assertFalse((t/'blocked').exists())


if __name__=='__main__':unittest.main()
