"""Behavioral safety, material-state and exporter integration tests (no devices)."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from datascape.gcode.models import Point, Stroke
from datascape.gcode.layout import Layout, Registration
from datascape.gcode.binding import digest, SIDECAR_SHA
from datascape.gcode.calibration import synthetic_profile
from datascape.gcode.production.profiles import Profile, brush, BASE_CHECKS, PAINT_CHECKS, authorize
from datascape.gcode.production.sequence import make_plan, pressure_distribution, verify_plan, apply_color_order
from datascape.gcode.production.trajectory import Builder, Materials, build_job, station_points, require_path
from datascape.gcode.production.exporter import export_jobs, export_calibration, readback, _serialize, verify_export, verify_draw_lineage

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return Profile.load(ROOT/'tests/fixtures/plotter_v03_synthetic.json')


def strokes():
    return (Stroke('ink-cross', (Point(301,10,.22), Point(299,20,.93)), 'D', 'INK', 'ink', sequence=0),
            Stroke('c-light', (Point(10,20,.22), Point(10.01,20,.93)), 'A', 'C1', 'color', sequence=1),
            Stroke('c-dark', (Point(30,20,.5), Point(31,22,.7)), 'D', 'D1', 'color', sequence=2),
            Stroke('c-light-2', (Point(20,20,.4), Point(22,22,.6)), 'A', 'C1', 'color', sequence=3))


def plan(layout=Layout('A'), resume_after=None):
    return make_plan(strokes(), layout, (0,1,3,2), resume_after)


def measured_test_profile():
    # Only ephemeral unit tests assert synthetic evidence. No such profile ships
    # as a measured machine profile or becomes an authorized Spring export.
    d = deepcopy(fixture().data); d['status'] = 'measured'
    for s in d['stations'].values():
        if s['status'] == 'synthetic_fixture': s['status'] = 'measured'
    for p in d['brush_profiles'].values():
        p.update(status='measured',calibration_date='synthetic-test',substrate_surface_height_mm=3,
            observations=[{'tested_z_mm':z,'stroke_width_mm':1,'feed_mm_min':100,
                           'water_loading':'synthetic','pigment_loading':'synthetic','quality':'synthetic-test',
                           'continuity':'synthetic-test'} for _, z in p['knots']])
    p = Profile.from_dict(d)
    d['evidence'] = [{'check':c,'status':'passed','calibration_sha256':p.calibration_sha256,
                     'operator':'synthetic-test','date':'synthetic-test','method':'invented unit fixture'}
                    for c in (*BASE_CHECKS,'air_run',*PAINT_CHECKS)]
    return Profile.from_dict(d)


def auth(p, manifest, stage, jobs):
    return {'stage':stage,'profile_sha256':p.sha256,'plan_sha256':digest(manifest),
            'job_ids':list(jobs),'operator':'synthetic-test','date':'synthetic-test',
            'explicit_operator_authorization':True}


class ProfileAndGeometryTests(unittest.TestCase):
    def test_real_template_aggregates_blockers_without_fallback(self):
        p = Profile.load(ROOT/'config/plotter_v03/profile.unmeasured.json')
        e = p.issues('painting',['C1'])
        self.assertGreater(len(e),15)
        self.assertTrue(any('brush' in s for s in e))
        self.assertTrue(any('bounds' in s for s in e))
        with self.assertRaisesRegex(ValueError,'EXPORT BLOCKED'): p.require('air')
        self.assertEqual(p.data['motion']['paper_hover_mm'],10)
        self.assertEqual(p.data['motion']['park_xyz'],[800,900,32])

    def test_arbitrary_multi_knots_monotonic_domain_and_unsupported_spline(self):
        d = asdict(synthetic_profile()); d['knots'] = [[.20,-.01],[.3,-.03],[.4,-.06],[.5,-.15],[.6,-.3],[.8,-.6],[.95,-.8]]
        p = brush(d); zs = [p.z_for(.20+.75*i/1000) for i in range(1001)]
        self.assertTrue(all(a>=b for a,b in zip(zs,zs[1:])))
        self.assertAlmostEqual(p.z_for(.45),-.105)
        for x in (.19,.96,float('nan')):
            with self.assertRaises(ValueError):p.z_for(x)
        for knots in ([[.2,-.1],[.6,-.05]],[[.2,-.1],[.2,-.2]]):
            with self.assertRaises(ValueError):brush(dict(d,knots=knots))
        with self.assertRaisesRegex(ValueError,'only monotonic'):brush(dict(d,interpolation='pchip'))

    def test_auth_is_stage_profile_plan_and_selected_job_bound(self):
        p=measured_test_profile();jobs,m=plan();a=auth(p,m,'air',jobs)
        authorize(a,p,digest(m),'air',jobs)
        for bad in (dict(a,stage='painting'),dict(a,plan_sha256='bad'),dict(a,job_ids=['P1_INK']),dict(a,explicit_operator_authorization=False)):
            with self.assertRaises(ValueError):authorize(bad,p,digest(m),'air',jobs)
        changed=deepcopy(p.data);changed['motion']['park_xyz'][0]-=1;q=Profile.from_dict(changed)
        self.assertTrue(any('evidence' in x for x in q.issues('air')))
        with self.assertRaises(ValueError):authorize(a,q,digest(m),'air',jobs)

    def test_complete_swept_segment_checked_not_only_endpoints(self):
        m=deepcopy(fixture().data['machine'])
        m['keepout_boxes']=[[[4,-1,0],[6,1,20]]]
        with self.assertRaisesRegex(ValueError,'keepout'):require_path((0,0,10),(10,0,10),m)
        m['keepout_boxes']=[];m['validated_free_boxes']=[[[0,-1,0],[4,1,20]],[[6,-1,0],[10,1,20]]]
        with self.assertRaisesRegex(ValueError,'corridors'):require_path((0,0,10),(10,0,10),m)
        m['validated_free_boxes'][0][1][0]=6
        require_path((0,0,10),(10,0,10),m)

    def test_machine_offset_and_unreachable_park_fail_without_substitution(self):
        d=deepcopy(fixture().data);d['motion']['park_xyz']=[5000,900,32]
        with self.assertRaisesRegex(ValueError,'unreachable'):build_job(Profile.from_dict(d),plan()[0]['P1_INK'],'fixture')
        d=deepcopy(fixture().data);d['machine']['g54_to_machine_xyz']=[10000,0,0]
        with self.assertRaisesRegex(ValueError,'unreachable'):Builder(Profile.from_dict(d))

    def test_controller_acceleration_must_match_brush_safe_limits(self):
        d=deepcopy(fixture().data);d['machine']['axis_acceleration_mm_s2'][2]=100
        self.assertTrue(any('Z acceleration' in x for x in Profile.from_dict(d).issues('fixture',['C1'])))
        d=deepcopy(fixture().data);d['machine']['axis_acceleration_mm_s2'][0]=1000
        self.assertTrue(any('XY acceleration' in x for x in Profile.from_dict(d).issues('fixture',['C1'])))


class PlanningTests(unittest.TestCase):
    def test_four_split_jobs_exact_source_and_pressure_provenance(self):
        original=strokes();before=asdict(original[0]);jobs,m=plan()
        self.assertEqual(set(jobs),{'P1_INK','P1_COLOR','P2_INK'})
        self.assertEqual([u[0].stroke.origin_id for u in jobs['P1_COLOR']],['c-light','c-light-2','c-dark'])
        self.assertEqual(asdict(original[0]),before)
        for units in jobs.values():
            for u in units:
                for f in u:
                    for point,loc in zip(f.stroke.points,f.stroke.source_locations):
                        source=next(s for s in original if s.stroke_id==f.stroke.origin_id)
                        a,b=source.points[loc.segment:loc.segment+2]
                        self.assertAlmostEqual(point.pressure,a.pressure+loc.t*(b.pressure-a.pressure))
        self.assertFalse(m['canonical_data_modified'])

    def test_shared_gap_source_atomicity_and_full_sheet_compatibility(self):
        for mode,gap in [('B',0),('C',50),('D',0)]:
            jobs,m=plan(Layout(mode,gap));u=jobs['SHARED_INK'][0]
            if mode!='D':
                self.assertEqual([f.panel for f in u],['P2','P1'])
                self.assertLess(u[0].stroke.source_locations[0].arc_mm,u[1].stroke.source_locations[0].arc_mm)
                self.assertGreaterEqual(u[0].work_xy[0][0],300+gap)
            else:self.assertEqual(len(u),1)

    def test_resume_only_completed_source_and_restarts_material_state(self):
        jobs,m=plan(resume_after={'P1_COLOR':'c-light'})
        self.assertEqual(jobs['P1_COLOR'][0][0].stroke.origin_id,'c-light-2')
        commands,_=build_job(fixture(),jobs['P1_COLOR'],'fixture')
        actions=[c.action for c in commands]
        self.assertIn('full_wash',actions);self.assertIn('pigment_load',actions)
        with self.assertRaises(ValueError):plan(resume_after={'P1_COLOR':'invented-fragment'})
        with self.assertRaises(ValueError):plan(resume_after={'P1_COLOR':'c-dark'})

    def test_pressure_distribution_is_from_actual_available_layers(self):
        d=pressure_distribution(strokes());self.assertEqual(sum(v['samples'] for v in d),8)
        self.assertEqual({v['available_family_layer'] for v in d},{'A','D'})


class StationAndMaterialTests(unittest.TestCase):
    def test_inkstone_withdrawal_and_palette_floor_guard(self):
        p=fixture();dip,points=station_points(p.data['stations']['ink'])
        self.assertEqual(dip,(700,200,4));self.assertEqual(points[-1],(700,240,10))
        bad=deepcopy(p.data['stations']['ink']);bad['immersion_mm']=20
        with self.assertRaises(ValueError):station_points(bad)
        bad=deepcopy(p.data['stations']['C1']);bad['immersion_mm']=6
        with self.assertRaisesRegex(ValueError,'scrape'):station_points(bad)
        dip,points=station_points(p.data['stations']['C1'])
        self.assertEqual(len(points),27)
        self.assertEqual(points[-1][2],13)

    def test_optional_agitation_cross_and_gentle_sponge(self):
        d=deepcopy(fixture().data['stations']['ink']);d.update(agitation_cycles=2,agitation_xy_mm=[1,0],agitation_floor_max_z=1)
        self.assertEqual(len(station_points(d)[1]),5)
        d['agitation_floor_max_z']=5
        with self.assertRaises(ValueError):station_points(d)
        d=deepcopy(fixture().data['stations']['C1']);d['pattern']='cross'
        self.assertEqual(len(station_points(d)[1]),9)
        dip,points=station_points(fixture().data['stations']['sponge']);self.assertEqual(points,())
        self.assertAlmostEqual(dip[2],16.6)

    def test_reload_uses_active_material_not_historical_slot_distance(self):
        b=Builder(fixture());mat=Materials(b);jobs,_=plan();units=jobs['P1_COLOR']
        mat.before(units[0]);mat.distance=1001;start=len(b.commands);mat.before(units[1])
        self.assertEqual(mat.distance,0);self.assertTrue(any(c.action=='same_color_reload' for c in b.commands[start:]))
        self.assertFalse(any(c.action=='full_wash' for c in b.commands[start:]))
        mat.distance=900;mat.before(units[2]);self.assertEqual(mat.loaded,'D1');self.assertEqual(mat.distance,0)
        mat.before(units[0]);self.assertEqual(mat.loaded,'C1');self.assertEqual(mat.distance,0)

    def test_reload_deferred_to_original_source_boundary_and_overrun_recorded(self):
        jobs,_=plan(Layout('B'));b=Builder(fixture());mat=Materials(b)
        unit=jobs['SHARED_INK'][0];mat.before(unit);n=len(b.commands);mat.distance=1999;mat.after(unit)
        self.assertEqual(len(b.commands),n)
        self.assertGreater(mat.overruns[-1]['overrun_mm'],0)
        mat.before(unit);self.assertEqual(mat.distance,0)

    def test_station_transit_always_at_global_clearance(self):
        b=Builder(fixture());mat=Materials(b);mat.load('C1')
        self.assertTrue(all(c.xyz[2]>=32 for c in b.commands if c.action=='travel'))
        self.assertEqual(b.position[2],32)
        mat.wash();self.assertIsNone(mat.loaded);self.assertEqual(mat.distance,0)
        self.assertIn('controlled_rewet',[c.action for c in b.commands])


class ExportTests(unittest.TestCase):
    def test_fixture_roundtrip_preserves_every_pressure_and_is_comment_only(self):
        jobs,m=plan();p=fixture()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'out';r=export_jobs(jobs,m,p,'fixture',None,root)
            self.assertEqual(set(r['jobs']),set(jobs))
            self.assertFalse(list(root.glob('*.nc')))
            for name,units in jobs.items():
                text=(root/(name+'.example.txt')).read_text()
                self.assertTrue(all(x.startswith(';') for x in text.splitlines()))
                ir=json.loads(gzip.decompress((root/(name+'.trajectory.json.gz')).read_bytes()))
                samples=[x['artistic_pressure'] for x in ir if x['artistic_pressure'] is not None]
                self.assertEqual(samples,[p.pressure for u in units for f in u for p in f.stroke.points])
            for name,sha in json.loads((root/'MANIFEST_SHA256.json').read_text()).items():
                self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),sha)
            with self.assertRaises(ValueError):export_jobs(jobs,m,p,'fixture',None,root)

    def test_air_is_no_contact_no_station_and_authorization_required(self):
        jobs,m=plan();p=measured_test_profile()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'out'
            with self.assertRaises(ValueError):export_jobs(jobs,m,p,'air',{},root)
            self.assertFalse(root.exists())
            export_jobs(jobs,m,p,'air',auth(p,m,'air',jobs),root)
            for path in root.glob('*.trajectory.json.gz'):
                cmds=json.loads(gzip.decompress(path.read_bytes()))
                self.assertTrue(all(c['xyz'][2]>=10 for c in cmds if c['xyz']))
                self.assertFalse(any(c['action'].startswith('station_') for c in cmds))
            for path in root.glob('*.nc'):
                text=path.read_text();active='\n'.join(x for x in text.splitlines() if not x.startswith(';'))
                self.assertNotIn('G10',active);self.assertNotIn('G92 ',active)
                executable=[x for x in text.splitlines() if x and not x.startswith(';')]
                self.assertEqual(executable[1],'M0')

    def test_missing_calibration_blocks_painting_and_atomic_failure_leaves_no_job(self):
        jobs,m=plan();p=measured_test_profile();bad=deepcopy(p.data);bad['stations']['C1']['immersion_mm']=30
        bad=Profile.from_dict(bad)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'out'
            # Invalid station detected even if an operator supplies renewed test evidence.
            fake=deepcopy(bad.data)
            for e in fake['evidence']:e['calibration_sha256']=bad.calibration_sha256
            bad=Profile.from_dict(fake)
            with self.assertRaises(ValueError):export_jobs(jobs,m,bad,'painting',auth(bad,m,'painting',jobs),root)
            self.assertFalse(root.exists());self.assertEqual(list(Path(d).iterdir()),[])

    def test_synchronized_xyz_velocity_limited_at_rapid_pressure_change(self):
        jobs,m=plan();cmds,r=build_job(fixture(),jobs['P1_COLOR'],'fixture')
        draws=[c for c in cmds if c.action=='draw']
        self.assertTrue(any(c.feed_mm_min<5000 for c in draws))
        self.assertTrue(all(c.axis_velocity_mm_min[2]<=600+1e-8 for c in draws))
        self.assertTrue(all(c.projected_acceleration_mm_s2>0 for c in draws))
        self.assertTrue(any(c.travel_state=='wet_loaded' for c in cmds if c.action=='travel'))

    def test_dialect_and_coordinate_tampering_rejected(self):
        jobs,m=plan();p=fixture();cmds,_=build_job(p,jobs['P1_INK'],'fixture')
        text=_serialize(cmds,p,digest(m),'TEST','fixture')
        for bad in (text.replace('; M2','; G10 L20 P1 X0'),text.replace('X800.000000000','X799.000000000',1)):
            with self.assertRaises(ValueError):readback(bad,cmds,p,'fixture')

    def test_synthetic_fixture_rejected_for_bound_spring_sources(self):
        ss=tuple(replace(s,pressure_sidecar_sha256=SIDECAR_SHA) for s in strokes())
        jobs,m=make_plan(ss,Layout(),(0,1,3,2))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'real Spring'):export_jobs(jobs,m,fixture(),'fixture',None,Path(d)/'out')

    def test_small_calibration_job_uses_separate_stage_and_explicit_depth(self):
        p=measured_test_profile();request={'schema':'datascape.calibration_plan.v0.3','station_roles':['ink'],
             'brush_lines':[{'start_xy':[10,10],'end_xy':[20,10],'z_mm':-.2,'feed_mm_min':300}]}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):export_calibration(request,p,auth(p,request,'air',['CALIBRATION']),Path(d)/'bad')
            export_calibration(request,p,auth(p,request,'calibration',['CALIBRATION']),Path(d)/'out')
            text=(Path(d)/'out/CALIBRATION.nc').read_text();self.assertIn('Z-0.200000000',text)
            request['brush_lines'][0]['z_mm']=-12
            with self.assertRaises(ValueError):export_calibration(request,p,auth(p,request,'calibration',['CALIBRATION']),Path(d)/'bad')


class ReadbackAndReadinessTests(unittest.TestCase):
    def test_authorized_measured_painting_serializer_and_delivered_readback(self):
        p=measured_test_profile();jobs,m=plan();names=['P1_COLOR']
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'painting'
            r=export_jobs(jobs,m,p,'painting',auth(p,m,'painting',names),out,names)
            self.assertEqual(set(r['jobs']),set(names))
            self.assertTrue((out/'P1_COLOR.nc').exists())
            self.assertEqual(verify_export(out)['jobs']['P1_COLOR']['all_artistic_pressure_samples_verified'],6)
            text=(out/'P1_COLOR.nc').read_text();self.assertIn('Z-',text)
            self.assertIn('INK/COLOR checkpoint',text)
            (out/'P1_COLOR.nc').write_text(text+'G10 L20 P1 X0\n')
            with self.assertRaises(ValueError):verify_export(out)

    def test_missing_or_stale_brush_context_and_knot_observations_fail(self):
        p=measured_test_profile();self.assertEqual(p.issues('painting',['C1']),[])
        for mutate in ('substrate','brush','observations'):
            d=deepcopy(p.data)
            if mutate=='substrate':d['brush_profiles']['color']['substrate']='different-paper'
            elif mutate=='brush':d['brush_profiles']['color']['brush_id']='different-brush'
            else:d['brush_profiles']['color']['observations']=d['brush_profiles']['color']['observations'][:1]
            self.assertTrue(any(('context' in x or 'brush/mount' in x or 'knot depth' in x)
                                for x in Profile.from_dict(d).issues('painting',['C1'])))

    def test_air_cannot_start_from_negative_or_contact_work_Z(self):
        d=deepcopy(fixture().data);d['machine']['start_work_xyz'][2]=0
        self.assertTrue(any('initial position' in x for x in Profile.from_dict(d).issues('fixture')))

    def test_written_plan_pressure_or_transform_mutation_rejected(self):
        jobs,m=plan();written=json.loads(json.dumps(m))
        verify_plan(written,strokes(),Layout())
        written['jobs']['P1_COLOR'][0]['fragments'][0]['stroke']['points'][0]['pressure']+=.01
        with self.assertRaises(ValueError):verify_plan(written,strokes(),Layout())
        written=json.loads(json.dumps(m));written['jobs']['P1_COLOR'][0]['fragments'][0]['work_xy'][0][1]+=1
        with self.assertRaises(ValueError):verify_plan(written,strokes(),Layout())

    def test_deterministic_bytes_and_no_partial_outputs_on_late_failure(self):
        p=fixture();jobs,m=plan()
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b'
            export_jobs(jobs,m,p,'fixture',None,a);export_jobs(jobs,m,p,'fixture',None,b)
            self.assertEqual((a/'MANIFEST_SHA256.json').read_bytes(),(b/'MANIFEST_SHA256.json').read_bytes())
            self.assertEqual(verify_export(a)['artifact_hashes_verified'],len(json.loads((a/'MANIFEST_SHA256.json').read_text())))
        cmds,_=build_job(p,jobs['P1_COLOR'],'fixture')
        idx=next(i for i,c in enumerate(cmds) if c.artistic_pressure is not None)
        cmds[idx]=replace(cmds[idx],artistic_pressure=.5)
        with self.assertRaises(ValueError):verify_draw_lineage(cmds,m['jobs']['P1_COLOR'],p,'fixture')


class WorkflowTests(unittest.TestCase):
    def test_cli_readiness_reports_and_does_not_create_motion_files(self):
        from datascape.gcode.production.__main__ import main
        from contextlib import redirect_stdout
        from io import StringIO
        out=StringIO()
        with redirect_stdout(out):
            code=main(['readiness','--profile',str(ROOT/'config/plotter_v03/profile.unmeasured.json'),'--stage','painting','--slots','C1'])
        self.assertEqual(code,2);self.assertTrue(json.loads(out.getvalue())['blocking_issues'])

    def test_pressure_knot_change_keeps_machine_evidence_but_invalidates_brush_evidence(self):
        d=deepcopy(measured_test_profile().data);p=Profile.from_dict(d)
        d['evidence']=[{'check':c,'status':'passed','scope_sha256':p.evidence_scope_sha256(c),
                       'operator':'test','date':'test','method':'synthetic scoped evidence'}
                      for c in (*BASE_CHECKS,'air_run',*PAINT_CHECKS)]
        p=Profile.from_dict(d);self.assertTrue(p.evidence_passed('air_run'))
        d['brush_profiles']['color']['knots'][1][1]-=.001
        p=Profile.from_dict(d)
        self.assertTrue(p.evidence_passed('air_run'));self.assertTrue(p.evidence_passed('homing_limits_estop'))
        self.assertFalse(p.evidence_passed('brush_response'))

    def test_ink_job_does_not_require_unmeasured_color_profile(self):
        d=deepcopy(fixture().data);del d['brush_profiles']['color'];p=Profile.from_dict(d)
        self.assertEqual(p.issues('fixture',[],['ink']),[])
        jobs,m=plan()
        with tempfile.TemporaryDirectory() as out:
            export_jobs(jobs,m,p,'fixture',None,Path(out)/'ink',['P1_INK'])
        self.assertTrue(p.issues('fixture',['C1'],['color']))

    def test_artist_can_configure_measured_pigment_order_without_changing_source(self):
        ss=strokes();before=asdict(ss[1]);order=apply_color_order(ss,(0,1,3,2),('D1','C1'))
        jobs,m=make_plan(ss,Layout(),order,palette_order=('D1','C1'))
        self.assertEqual([u[0].stroke.color_slot for u in jobs['P1_COLOR']],['D1','C1','C1'])
        self.assertEqual(asdict(ss[1]),before)
        with self.assertRaises(ValueError):make_plan(ss,Layout(),(1,0,3,2))
        with self.assertRaises(ValueError):make_plan(ss,Layout(),(0,1,2,3))

    def test_optional_station_air_tour_stays_at_clearance_without_dipping(self):
        d=deepcopy(fixture().data);d['motion']['air_station_roles']=['ink','C1']
        cmds,_=build_job(Profile.from_dict(d),plan()[0]['P1_INK'],'air')
        self.assertEqual(sum(c.action=='station_air_only' for c in cmds),2)
        self.assertFalse(any(c.action in ('station_pigment_load','station_wash') for c in cmds))
        self.assertTrue(all(c.xyz[2]>=10 for c in cmds if c.xyz))


class SharedWorkflowBoundaryTests(unittest.TestCase):
    def test_shared_architecture_does_not_bypass_mandatory_split_panel_workflow(self):
        p=measured_test_profile();jobs,m=plan(Layout('B'))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'separate panel'):
                export_jobs(jobs,m,p,'painting',auth(p,m,'painting',jobs),Path(d)/'out')


class BrushProfileSelectionTests(unittest.TestCase):
    def test_fully_measured_slot_override_needs_no_unused_default_color_curve(self):
        d=deepcopy(measured_test_profile().data)
        d['brush_profiles']['C1']=d['brush_profiles'].pop('color')
        p=Profile.from_dict(d)
        for e in d['evidence']:e['calibration_sha256']=p.calibration_sha256
        p=Profile.from_dict(d)
        self.assertEqual(p.issues('painting',['C1'],['color']),[])
        self.assertTrue(p.issues('painting',['C1','D1'],['color']))

    def test_zero_width_first_contact_observation_is_allowed_without_invented_mark(self):
        d=deepcopy(measured_test_profile().data)
        d['brush_profiles']['ink']['observations'][0]['stroke_width_mm']=0
        p=Profile.from_dict(d)
        for e in d['evidence']:e['calibration_sha256']=p.calibration_sha256
        self.assertEqual(Profile.from_dict(d).issues('painting',[],['ink']),[])


if __name__=='__main__':unittest.main()
