"""Focused automatic A/D production corrections; no controller or physical data."""
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
import tempfile
import unittest
from test_gcode_v03 import fixture, measured_test_profile, auth, plan, ROOT
from datascape.gcode.models import Point, Stroke
from datascape.gcode.layout import Layout
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import make_plan, verify_plan
from datascape.gcode.production.trajectory import Builder, Materials, build_job
from datascape.gcode.production.exporter import export_jobs, verify_export, export_calibration
from datascape.gcode.production.costs import audit_continuity


def same_material(medium, lengths):
    # Unsplit vertical originals, each within the 900-mm paper height.
    slot='INK' if medium=='ink' else 'C1'
    return tuple(Stroke('unit-'+str(i),(Point(20+i,0,.3),Point(20+i,n,.6)),
                        'A',slot,medium,sequence=i) for i,n in enumerate(lengths))


class AutomaticWorkflowTests(unittest.TestCase):
    def test_current_defaults_and_nominal_PURGE_remain_unmeasured(self):
        p=Profile.load(ROOT/'config/plotter_v03/profile.unmeasured.json');m=p.data['material']
        self.assertEqual((m['ink_reload_mm'],m['color_reload_mm']),(1000,800))
        self.assertIsNone(m['manual_refill_every_loads']);self.assertIsNone(m['water_change_every_washes'])
        self.assertFalse(m['end_cleanup'])
        self.assertEqual(p.data['stations']['sponge']['center_xy'],[840.,137.5])
        self.assertEqual(p.data['stations']['sponge']['status'],'unverified')
        self.assertTrue(p.issues('painting'))

    def test_automatic_reload_at_next_original_boundary_for_ink_and_color(self):
        for medium,lengths,expected in [('color',[799,2,3],800),('ink',[899,102,3],1000)]:
            ss=same_material(medium,lengths);jobs,_=make_plan(ss,Layout('D'),tuple(range(3)))
            units=jobs['SHARED_'+medium.upper()];b=Builder(fixture());mat=Materials(b)
            self.assertEqual(mat.p[medium+'_reload_mm'],expected)
            mat.before(units[0]);mat.after(units[0]);mat.before(units[1]);mat.after(units[1])
            self.assertEqual(b.counts['same_color_reload'],0)
            self.assertEqual(mat.overruns[-1]['source_id'],'unit-1')
            mat.before(units[2]);self.assertEqual(b.counts['same_color_reload'],1)
            self.assertEqual(mat.distance,0);self.assertEqual(b.counts['full_wash'],0)
            self.assertEqual(b.result()['M0_count'],0)

    def test_D_continuity_and_services_never_interrupt_long_X300_source(self):
        ss=(Stroke('long-cross',(Point(10,10,.3),Point(590,10,.5),Point(10,890,.6)),
                   'A','C1','color',sequence=0),
            Stroke('next',(Point(40,20,.3),Point(50,20,.5)),'A','C1','color',sequence=1))
        jobs,m=make_plan(ss,Layout('D'),(0,1));u=jobs['SHARED_COLOR']
        self.assertEqual(len(u[0]),1);self.assertEqual(u[0][0].stroke.points,ss[0].points)
        commands,r=build_job(fixture(),u,'fixture')
        begin=next(i for i,c in enumerate(commands) if c.action=='source_begin' and c.source_id=='long-cross')
        complete=next(i for i,c in enumerate(commands) if c.action=='source_complete' and c.source_id=='long-cross')
        samples=[c for c in commands[begin:complete] if c.artistic_pressure is not None]
        self.assertEqual([c.xyz[0] for c in samples],[10,590,10])
        self.assertEqual([c.artistic_pressure for c in samples],[.3,.5,.6])
        self.assertFalse(any(c.action.startswith('station_') or c.kind=='pause' for c in commands[begin:complete]))
        self.assertEqual(r['counts']['same_color_reload'],1);self.assertEqual(r['M0_count'],0)
        self.assertEqual(verify_plan(m,ss,Layout('D'))['D_X300_crossing_strokes_continuous'],1)
        self.assertEqual(audit_continuity(commands, {'long-cross'})['continuous_crossing_sources_checked'],1)
        bad=deepcopy(m);bad['jobs']['SHARED_COLOR'][0]['fragments']*=2
        with self.assertRaises(ValueError):verify_plan(bad,ss,Layout('D'))

    def test_color_starts_prepared_washes_only_between_colors_and_finishes_without_M0(self):
        jobs,_=plan();commands,r=build_job(fixture(),jobs['P1_COLOR'],'fixture')
        actions=[c.action for c in commands]
        self.assertLess(actions.index('pigment_load'),actions.index('full_wash'))
        self.assertEqual(r['counts']['full_wash'],1)
        self.assertEqual(r['M0_count'],0);self.assertEqual(r['M0_reasons'],[])
        moves=[c for c in commands if c.kind=='move'];self.assertEqual(moves[-1].xyz,(800,900,32))

    def test_periodic_manual_pauses_are_explicit_opt_in_not_startup(self):
        d=deepcopy(fixture().data);d['material'].update(water_change_every_washes=1,manual_refill_every_loads=1)
        b=Builder(Profile.from_dict(d));mat=Materials(b)
        mat.load('C1');self.assertEqual(b.result()['M0_count'],0)
        mat.load('C1',True);self.assertEqual(b.result()['M0_count'],1)
        mat.wash();self.assertEqual(b.result()['M0_count'],1)
        mat.wash();self.assertEqual(b.result()['M0_count'],2)
        self.assertIn('CHANGE/INSPECT',b.result()['M0_reasons'][-1])

    def test_centered_PURGE_has_only_vertical_contact_and_material_specific_parameters(self):
        d=deepcopy(fixture().data);d['stations']['sponge']['material_overrides']={'ink':{'compression_mm':.2,'dwell_seconds':.3},'color':{'compression_mm':.4,'dwell_seconds':.6}}
        p=Profile.from_dict(d);self.assertEqual(p.issues('fixture',['C1']),[])
        for material,z,dwell in [('ink',16.8,.3),('C1',16.6,.6)]:
            b=Builder(p);mat=Materials(b);mat.station('sponge','absorbent_contact',material)
            contact=[c for c in b.commands if c.action=='station_absorbent_contact']
            self.assertEqual(len(contact),1);self.assertEqual(contact[0].xyz,(840,137.5,z))
            self.assertEqual([c.seconds for c in b.commands if c.kind=='dwell'],[dwell])
            arrived=next(i for i,c in enumerate(b.commands) if c.action=='station_approach')
            self.assertTrue(all(c.xyz[:2]==(840,137.5) for c in b.commands[arrived:] if c.kind=='move'))
            self.assertEqual(b.position,(840,137.5,32))

    def test_A_four_jobs_share_paper_origin_and_D_two_jobs(self):
        ss=(Stroke('i1',(Point(13,900,.3),Point(14,899,.5)),'A','INK','ink',sequence=0),
            Stroke('i2',(Point(313,900,.3),Point(314,899,.5)),'A','INK','ink',sequence=1),
            Stroke('c1',(Point(13,890,.3),Point(14,889,.5)),'A','C1','color',sequence=2),
            Stroke('c2',(Point(313,890,.3),Point(314,889,.5)),'A','C1','color',sequence=3))
        a,_=make_plan(ss,Layout('A'),(0,1,2,3));d,m=make_plan(ss,Layout('D'),(0,1,2,3))
        self.assertEqual(set(a),{'P1_INK','P1_COLOR','P2_INK','P2_COLOR'})
        self.assertEqual(a['P1_INK'][0][0].work_xy[0],a['P2_INK'][0][0].work_xy[0])
        self.assertEqual(set(d),{'SHARED_INK','SHARED_COLOR'})
        p=measured_test_profile()
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out';r=export_jobs(d,m,p,'painting',auth(p,m,'painting',d),out)
            v=verify_export(out)
            for name in d:
                self.assertEqual(r['jobs'][name]['metrics']['M0_count'],0)
                self.assertEqual(v['jobs'][name]['M0_count'],0)
                text=(out/(name+'.nc')).read_text();active=[s for s in text.splitlines() if s and not s.startswith(';')]
                self.assertNotIn('M0',active);self.assertEqual(active[-1],'M2')
                self.assertIn('X800.000000000 Y900.000000000 Z32.000000000',active[-2])

    def test_pre_run_confirmations_and_adjacent_D_seam_gate(self):
        p=measured_test_profile();jobs,m=plan(Layout('D'));a=auth(p,m,'painting',jobs)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'pre-run'):export_jobs(jobs,m,p,'painting',dict(a,pre_run_confirmations={}),Path(temp)/'bad')
            data=deepcopy(p.data);data['machine']['substrate_assembly']='adjacent_panels'
            q=Profile.from_dict(data)
            for e in data['evidence']:e['calibration_sha256']=q.calibration_sha256
            q=Profile.from_dict(data)
            with self.assertRaisesRegex(ValueError,'continuous_seam'):export_jobs(jobs,m,q,'painting',auth(q,m,'painting',jobs),Path(temp)/'bad')
            data['evidence'].append({'check':'continuous_seam','status':'passed','scope_sha256':q.evidence_scope_sha256('continuous_seam'),'operator':'test','date':'test','method':'synthetic seam test'})
            q=Profile.from_dict(data);export_jobs(jobs,m,q,'painting',auth(q,m,'painting',jobs),Path(temp)/'ok')

    def test_explicit_end_cleanup_is_optional_and_calibration_pauses_are_reported(self):
        d=deepcopy(fixture().data);d['material']['end_cleanup']=True
        commands,r=build_job(Profile.from_dict(d),plan()[0]['P1_INK'],'fixture')
        self.assertEqual(r['counts']['full_wash'],1);self.assertEqual(r['M0_count'],0)
        p=measured_test_profile();request={'schema':'datascape.calibration_plan.v0.3','station_roles':['ink'], 'brush_lines':[{'start_xy':[10,10],'end_xy':[20,10],'z_mm':-.2,'feed_mm_min':300}]}
        with tempfile.TemporaryDirectory() as temp:
            r=export_calibration(request,p,auth(p,request,'calibration',['CALIBRATION']),Path(temp)/'out')
            self.assertEqual(r['metrics']['M0_count'],5);self.assertEqual(len(r['metrics']['M0_reasons']),5)
            self.assertEqual(r['readback']['M0_count'],5)


if __name__=='__main__':unittest.main()
