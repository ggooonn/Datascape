"""Offline study contracts; no new physical approval or production exporter."""
import unittest
from pathlib import Path
from copy import deepcopy
from dataclasses import replace
from studies.brush_pressure_three_region_v01.curves import catalog,load_catalog,offline_profile,summary
from studies.brush_pressure_three_region_v01.benchmark import plan as benchmark_plan
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import build_job
from datascape.gcode.production.sequence import make_plan,verify_plan
from datascape.gcode.production.exporter import export_jobs,verify_draw_lineage,export_calibration
from datascape.gcode.models import Point,Stroke
from datascape.gcode.layout import Layout
from datascape.gcode.binding import SIDECAR_SHA
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def base():return Profile.load(ROOT/'config/plotter_v03/cost_scenario.synthetic.json')


class ThreeRegionStudyTests(unittest.TestCase):
    def test_six_knots_mean_three_principal_regions_and_two_outer_domains(self):
        for c in catalog():
            b=offline_profile(base(),c).brush_for('ink','INK')
            for p,z in c['knots']:self.assertAlmostEqual(b.z_for(p),z)
            if c['model']=='three_region':
                self.assertEqual([p for p,z in b.knots],[0,.2,.4,.6,.93,1])
                self.assertEqual(b.z_for(.2),-3);self.assertEqual(b.z_for(0),0)
                self.assertEqual(b.z_for(1),-c['maximum_compression_mm'])
                self.assertGreater(b.z_for(.93),b.z_for(1))
                slopes=[-(b.z_for(q)-b.z_for(p))/(q-p) for p,q in ((.2,.4),(.4,.6),(.6,.93))]
                self.assertTrue(slopes[0]<slopes[1]<slopes[2])

    def test_all_candidates_monotonic_no_extrapolation_and_explicit_linear_anchor_difference(self):
        for c in catalog():
            b=offline_profile(base(),c).brush_for('color','C1')
            zs=[b.z_for(i/1000) for i in range(1001)]
            self.assertTrue(all(-c['maximum_compression_mm']<=z<=0 for z in zs))
            self.assertTrue(all(a>=z for a,z in zip(zs,zs[1:])))
            for p in (-.001,1.001,float('nan')):
                with self.assertRaises(ValueError):b.z_for(p)
            if c['model']=='global_linear':self.assertNotEqual(b.z_for(.2),-3)
            else:self.assertEqual(b.z_for(.2),-3)

    def test_exact_preferred_values_and_convex_piecewise_reference(self):
        for maximum,expected in [(10,[-3.056,-3.42,-3.56,-4.68,-8.95]),(12,[-3.072,-3.54,-3.72,-5.16,-10.65])]:
            c=next(c for c in catalog() if c['id']==f'three_region_{maximum}')
            b=offline_profile(base(),c).brush_for('ink','INK')
            for p,z in zip((.22,.35,.4,.6,.93),expected):self.assertAlmostEqual(b.z_for(p),z)
        self.assertEqual(summary([1,2,3,4])['median'],2.5)

    def test_rebuilt_deep_trajectories_preserve_pressure_and_seam_without_M0(self):
        ss=(Stroke('cross',(Point(10,10,.22),Point(590,10,.93)),'D','INK','ink',sequence=0),)
        jobs,m=make_plan(ss,Layout('D'),(0,))
        for c in (c for c in catalog() if c['model']=='three_region'):
            p=offline_profile(base(),c);commands,metrics=build_job(p,jobs['SHARED_INK'],'fixture')
            self.assertEqual([x.artistic_pressure for x in commands if x.artistic_pressure is not None],[.22,.93])
            self.assertEqual(verify_draw_lineage(commands,m['jobs']['SHARED_INK'],p,'fixture')['all_artistic_pressure_samples_verified'],2)
            self.assertEqual(metrics['M0_count'],0);self.assertEqual(commands[-2].xyz,(800,900,32))
            self.assertTrue(any(x.xyz and x.xyz[2]<-8 for x in commands))
            self.assertTrue(all(x.axis_velocity_mm_min[2]<=2000+1e-8 for x in commands if x.action in ('draw','pressure_variation')))
        self.assertEqual(verify_plan(m,ss,Layout('D'))['D_X300_crossing_strokes_continuous'],1)

    def test_unmeasured_candidates_cannot_authorize_or_serialize_real_Spring(self):
        p=offline_profile(base(),catalog()[-1]);self.assertTrue(p.issues('painting'))
        ss=(Stroke('bound',(Point(1,1,.3),Point(2,2,.6)),'A','INK','ink',sequence=0,
                   pressure_sidecar_sha256=SIDECAR_SHA),)
        jobs,m=make_plan(ss,Layout('D'),(0,))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'must not serialize real Spring'):
                export_jobs(jobs,m,p,'fixture',None,Path(temp)/'blocked')
            self.assertFalse((Path(temp)/'blocked').exists())

    def test_benchmark_is_a_design_with_explicit_depth_progression_not_a_machine_job(self):
        p=benchmark_plan();self.assertFalse(p['physical_execution_authorized'])
        self.assertEqual(len(p['patterns']),18)
        self.assertEqual(p['stages'][0]['candidate_compression_mm'],[.25,.5,1,2,3])
        self.assertEqual({r['length_mm'] for r in p['patterns']},{5,20,80,100,120})
        self.assertTrue(all(r['feeds_require_separate_physical_approval'] for r in p['patterns']))
        self.assertFalse(any('gcode' in k.lower() for k in p if k!='status'))

    def test_editable_config_reuses_mapper_and_rejects_reversal_or_false_measured_status(self):
        import json
        path=ROOT/'studies/brush_pressure_three_region_v01/candidate_curves.json'
        rows=load_catalog(path);self.assertEqual(len(rows),8)
        data=json.loads(path.read_text());c=data['curves'][3];c['knots'][2][1]=-3.7
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'curves.json';p.write_text(json.dumps(data))
            self.assertEqual(offline_profile(base(),load_catalog(p)[3]).brush_for('ink','INK').z_for(.4),-3.7)
            data['curves'][3]['knots'][2][1]=-2
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'monotonic'):load_catalog(p)
            data=json.loads(path.read_text());data['curves'][0]['status']='measured';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'unmeasured'):load_catalog(p)

    def test_first_depth_request_uses_existing_schema_but_still_requires_physical_gate(self):
        import json
        p=ROOT/'studies/brush_pressure_three_region_v01/first_depth.request.json'
        request=json.loads(p.read_text())
        self.assertEqual(len(request['brush_lines']),1)
        self.assertEqual(request['brush_lines'][0]['z_mm'],-.25)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'EXPORT BLOCKED'):
                export_calibration(request,base(),None,Path(temp)/'blocked')
            self.assertFalse((Path(temp)/'blocked').exists())


if __name__=='__main__':unittest.main()
