"""Target mount, monotonic physical mapping, station invariance and stepwise gates."""
import unittest
from dataclasses import replace
import numpy as np
from benchmarks.integrated_330_v01 import spring_fine_profile as f
from benchmarks.integrated_330_v01 import spring_physical_ink as s
from benchmarks.integrated_330_v01 import spring_panels_contact20 as n
from tests.test_gcode_spring_panels_contact20 import fragment,groups

class FinePhysicalProfileTests(unittest.TestCase):
    def setUp(self):self.cfg=s.read(f.POLICY)
    def test_monotonic_lighter_than_small_and_exact_target(self):
        small=s.Profile.from_dict(f.frozen('profile.small.json'))
        for peak in (5,5.5,6):
            p=f.profile(peak,self.cfg);self.assertEqual(p.paper_heights_for('ink','INK'),(10,20,15))
            values=[10-p.brush_for('ink','INK').work_z_for(float(x)) for x in np.linspace(0,1,101)]
            self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
            self.assertAlmostEqual(values[-1],peak)
            self.assertTrue(all(c<=10-small.brush_for('ink','INK').work_z_for(float(x))+1e-10 for c,x in zip(values,np.linspace(0,1,101))))
    def test_curve_ceiling_not_dataset_normalization(self):
        p=f.profile(5.5,self.cfg)
        self.assertAlmostEqual(10-p.brush_for('ink','INK').work_z_for(.27),.83875)
        self.assertAlmostEqual(p.brush_for('ink','INK').work_z_for(.7368563078158471),6.584112883766052)
    def test_stations_do_not_follow_paper_reference(self):
        old=s.Profile.from_dict(f.frozen('profile.fine.PROVISIONAL.json'));new=f.profile(5.5,self.cfg)
        self.assertEqual(old.data['stations'],new.data['stations'])
        policy=n.frozen('policy.json');policy['distance_limit_mm']=450
        c,m=n.build(groups(1),[fragment(0)],s.Profile.from_dict(f.frozen('profile.small.json')),policy,10)
        oldcmd=f.a.v.fine_transform(c,old);newcmd=f.retarget(oldcmd,new)
        self.assertTrue(f.station_audit(oldcmd,newcmd,m)['all_station_XYZ_feeds_dwell_and_sequence_unchanged'])
        bad=[replace(x,xyz=(840,45,18)) if x.action=='station_container_immersion' else x for x in newcmd]
        with self.assertRaises(ValueError):f.station_audit(oldcmd,bad,m)
    def test_retarget_preserves_original_pressure_and_xy(self):
        policy=n.frozen('policy.json');policy['distance_limit_mm']=450
        c,m=n.build(groups(1),[fragment(0)],s.Profile.from_dict(f.frozen('profile.small.json')),policy,10)
        old=f.a.v.fine_transform(c,s.Profile.from_dict(f.frozen('profile.fine.PROVISIONAL.json')))
        new=f.retarget(old,f.profile(5.5,self.cfg))
        self.assertEqual([x.artistic_pressure for x in old],[x.artistic_pressure for x in new])
        self.assertEqual([x.xyz[:2] for x in old if x.kind=='move'],[x.xyz[:2] for x in new if x.kind=='move'])
    def test_progressive_program_has_no_automatic_station_contact(self):
        p=f.profile(5.5,self.cfg);cmd,log=f.calibration(p,self.cfg)
        self.assertEqual(log[0]['compression_mm'],.25);self.assertEqual(log[-1]['compression_mm'],5.5)
        self.assertTrue(all(a['compression_mm']<b['compression_mm'] for a,b in zip(log,log[1:])))
        self.assertEqual(sum(x.action=='initial_contact' for x in cmd),13)
        self.assertFalse(any(x.action.startswith('station_') for x in cmd))
        self.assertEqual(max(x['contacts_since_manual_reload'] for x in log),10)
        self.assertEqual(sum(x['manual_same_ink_reload_before'] for x in log),1)
        self.assertEqual(sum(x.kind=='pause' for x in cmd),14)
    def test_numeric_mutation_and_missing_gate_rejected(self):
        p=f.profile(5.5,self.cfg);cmd,_=f.calibration(p,self.cfg)
        text=s.BANNER+s._serialize(cmd,p,s.PLAN_SHA,'test','offline_review')
        f.verify(text,cmd,p,[],[],test=True)
        with self.assertRaises(ValueError):f.verify(text.replace('M0\n','',1),cmd,p,[],[],test=True)
        air=s.air_projection(cmd,p);text=s.BANNER+s._serialize(air,p,s.PLAN_SHA,'test','offline_review')
        with self.assertRaises(ValueError):f.verify(text.replace('Z35.000000000','Z20.000000000',1),air,p,[],[],air=True,test=True)

if __name__=='__main__':unittest.main()
