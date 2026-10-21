"""Local hover and comment-only incomplete-review contracts; no device access."""
import unittest,tempfile,gzip,json
import hashlib
from dataclasses import asdict
from copy import deepcopy
from pathlib import Path
from math import dist
from test_gcode_v03 import fixture,measured_test_profile,auth
from datascape.gcode.models import Stroke,Point
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import make_plan
from datascape.gcode.production.trajectory import build_job,local_transition_height
from datascape.gcode.production.exporter import export_jobs
from studies.local_hover_v01.config import candidate_profile,curve_knots
from studies.local_hover_v01.review import Review,with_local,write_preview,timing
from studies.local_hover_v01.verify import verify
from datascape.gcode.binding import digest

ROOT=Path(__file__).resolve().parents[1]
LOW={'axis_max_rate_mm_min':[15000,15000,6000],'axis_acceleration_mm_s2':[100,100,20],'junction_deviation_mm':.01}


def units(mixed=False,long=False):
    a=(Point(0,0,.3),Point(500,0,.6),Point(0,0,.4)) if long else (Point(10,20,.3),Point(20,20,.6))
    ss=(Stroke('first',a,'A','C1' if mixed else 'INK','color' if mixed else 'ink',sequence=0),
        Stroke('second',(Point(30,20,.3),Point(40,20,.5)),'A','D1' if mixed else 'INK','color' if mixed else 'ink',sequence=1))
    j,m=make_plan(ss,Layout('D'),(0,1));return j,m


def enabled(height=5,distance=10):
    d=deepcopy(fixture().data);d['motion']['local_hover']={'enabled':True,'height_mm':height,'max_distance_mm':distance}
    return Profile.from_dict(d)


class LocalHoverTests(unittest.TestCase):
    def test_local_transition_retracts_once_and_next_approach_starts_at_selected_height(self):
        for h in (5,3):
            c,m=build_job(enabled(h),units()[0]['SHARED_INK'],'fixture')
            end=next(i for i,x in enumerate(c) if x.action=='source_complete' and x.source_id=='first')
            approach=next(i for i,x in enumerate(c) if x.action=='approach' and x.source_id=='second')
            self.assertEqual(c[end-1].xyz[2],h)
            self.assertTrue(all(x.xyz[2]==h for x in c[end:approach] if x.kind=='move'))
            self.assertEqual(c[approach].xyz[2],1)
            self.assertEqual(m['counts']['local_hover_transfer'],1);self.assertEqual(m['M0_count'],0)
            self.assertEqual([x.artistic_pressure for x in c if x.artistic_pressure is not None],[.3,.6,.3,.5])

    def test_distance_material_and_pending_reload_exclude_shortcut(self):
        self.assertEqual(build_job(enabled(distance=5),units()[0]['SHARED_INK'],'fixture')[1]['counts'].get('local_hover_transfer',0),0)
        self.assertEqual(build_job(enabled(),units(True)[0]['SHARED_COLOR'],'fixture')[1]['counts'].get('local_hover_transfer',0),0)
        c,m=build_job(enabled(distance=1000),units(long=True)[0]['SHARED_INK'],'fixture')
        self.assertEqual(m['counts'].get('local_hover_transfer',0),0);self.assertEqual(m['counts']['same_color_reload'],1)

    def test_blocked_low_corridor_falls_back_to_normal_validated_height(self):
        p=enabled();d=deepcopy(p.data);d['machine']['keepout_boxes']=[[[24,879,4.9],[26,881,5.1]]]
        c,m=build_job(Profile.from_dict(d),units()[0]['SHARED_INK'],'fixture')
        self.assertEqual(m['counts'].get('local_hover_transfer',0),0)
        end=next(i for i,x in enumerate(c) if x.action=='source_complete' and x.source_id=='first')
        self.assertEqual(c[end-1].xyz[2],10)

    def test_air_never_uses_local_height(self):
        c,m=build_job(enabled(3),units()[0]['SHARED_INK'],'air')
        self.assertTrue(all(x.xyz[2]>=10 for x in c if x.kind=='move'))
        self.assertEqual(m['counts'].get('local_hover_transfer',0),0)

    def test_painting_requires_scoped_clearance_and_recovery_evidence(self):
        data=deepcopy(measured_test_profile().data);data['motion']['local_hover']={'enabled':True,'height_mm':5,'max_distance_mm':10}
        p=Profile.from_dict(data)
        for e in data['evidence']:e['calibration_sha256']=p.calibration_sha256
        p=Profile.from_dict(data);jobs,m=units()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'local_hover_clearance'):
                export_jobs(jobs,m,p,'painting',auth(p,m,'painting',jobs),Path(temp)/'blocked')
            data['evidence'].append({'check':'local_hover_clearance','status':'passed','scope_sha256':p.evidence_scope_sha256('local_hover_clearance'),
                                     'operator':'synthetic','date':'synthetic','method':'synthetic corridor/recovery test'})
            q=Profile.from_dict(data);export_jobs(jobs,m,q,'painting',auth(q,m,'painting',jobs),Path(temp)/'unit-only')
            data['motion']['local_hover']['height_mm']=3
            self.assertFalse(Profile.from_dict(data).evidence_passed('local_hover_clearance'))

    def test_nominal_station_Z_candidates_do_not_fabricate_unknown_geometry(self):
        p=candidate_profile(ROOT);d=p.data
        self.assertIsNone(d['machine']['g54_to_machine_xyz']);self.assertFalse(d['motion']['local_hover']['enabled'])
        for role in ('water','ink','sponge'):
            self.assertIsNone(d['stations'][role]['contact_box_xyz'])
        self.assertIsNone(d['stations']['water']['deep_surface_xyz']);self.assertIsNone(d['stations']['ink']['shallow_surface_xyz'])
        self.assertIsNone(d['stations']['sponge']['surface_z']);self.assertEqual(d['stations']['sponge']['compression_mm'],2)
        c=d['stations']['C1'];z=c['liquid_reference_z']-c['immersion_mm']
        self.assertEqual(z,7);self.assertEqual(z-c['bottom_z'],8);self.assertEqual(z-(c['bottom_z']+c['bottom_gap_mm']),6)
        self.assertTrue(p.issues('air'));self.assertTrue(p.issues('painting',['C1']))

    def test_review_local_changes_only_clear_transfers_and_reduces_Z_exactly(self):
        p=candidate_profile(ROOT);u=units()[0]['SHARED_INK'];b=Review(p,LOW);c,links=b.build(u)
        for h in (5,3):
            changed,m=with_local(c,links,h,10)
            def zdist(cmds):
                v=(800,900,32);total=0
                for x in cmds:
                    if x.kind=='move':total+=abs(x.xyz[2]-v[2]);v=x.xyz
                return total
            self.assertAlmostEqual(zdist(c)-zdist(changed),m['reduced_Z_mm'])
            self.assertEqual([x for x in c if x.artistic_pressure is not None],[x for x in changed if x.artistic_pressure is not None])
            self.assertEqual(m['physically_authorized_local_transitions'],0)

    def test_preview_keeps_unresolved_operations_and_cannot_be_an_nc_file(self):
        p=candidate_profile(ROOT);b=Review(p,LOW);c,_=b.build(units(True)[0]['SHARED_COLOR'])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'job.preview.txt.gz';r=write_preview(path,c,p,'test','SHARED_COLOR')
            text=gzip.decompress(path.read_bytes()).decode()
            self.assertTrue(all(line.startswith(';') for line in text.splitlines()))
            self.assertIn('UNRESOLVED',text);self.assertTrue(text.endswith('; M2\n'));self.assertEqual(r['M0_count'],0)
            self.assertFalse(r['machine_reachability_verified'])
            with self.assertRaises(ValueError):write_preview(Path(temp)/'SHARED_COLOR.nc',c,p,'test','SHARED_COLOR')
        self.assertFalse(any(x.kind=='pause' for x in c))

    def test_new_pressure_candidate_preserves_explicit_monotonic_domains(self):
        for preload in (2,3):
            knots=curve_knots(preload);self.assertEqual(knots[1],(.2,-preload));self.assertEqual(knots[-1],(1.,-10.))
            self.assertTrue(all(a[0]<z[0] and a[1]>=z[1] for a,z in zip(knots,knots[1:])))
        self.assertEqual(curve_knots(2)[2:],[(.4,-2.64),(.6,-3.92),(.93,-8.8),(1.,-10.)])

    def test_delivered_review_verifier_checks_numbers_beyond_the_file_manifest(self):
        p=candidate_profile(ROOT)
        job_units={'SHARED_INK':units()[0]['SHARED_INK'],'SHARED_COLOR':units(True)[0]['SHARED_COLOR']}
        plan={'jobs':{'SHARED_INK':units()[1]['jobs']['SHARED_INK'],'SHARED_COLOR':units(True)[1]['jobs']['SHARED_COLOR']}}
        context={'authorized':False,'clearance_verified':False}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'profile.provisional.json').write_text(json.dumps(p.data))
            (root/'REVIEW_CONTEXT.json').write_text(json.dumps(context))
            (root/'D.plan.json.gz').write_bytes(gzip.compress(json.dumps(plan).encode()))
            for name,u in job_units.items():
                commands,_=Review(p,LOW).build(u)
                with gzip.open(root/(name+'.trajectory.jsonl.gz'),'wt') as f:
                    for c in commands:f.write(json.dumps(asdict(c))+'\n')
                write_preview(root/(name+'.preview.txt.gz'),commands,p,digest(plan),name,context)
            def hashes():
                (root/'MANIFEST_SHA256.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.iterdir() if f.name!='MANIFEST_SHA256.json'}))
            hashes();self.assertFalse(verify(root)['authorized'])
            target=root/'SHARED_COLOR.preview.txt.gz';text=gzip.decompress(target.read_bytes()).decode()
            target.write_bytes(gzip.compress(text.replace(' F5000.000000000',' F5001.000000000',1).encode()))
            hashes()  # A refreshed checksum cannot legitimize coordinate/feed drift.
            with self.assertRaisesRegex(ValueError,'G54/feed mismatch'):verify(root)


if __name__=='__main__':unittest.main()
