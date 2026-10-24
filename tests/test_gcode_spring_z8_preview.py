"""Spring response candidate stays separate from art, benchmark and authorization."""
from copy import deepcopy
from pathlib import Path
import unittest

from datascape.gcode.production.profiles import Profile
from benchmarks.integrated_330_v01.spring_z8_preview import candidate_profile

ROOT=Path(__file__).resolve().parents[1]


class SpringZ8ReviewTests(unittest.TestCase):
    def setUp(self):
        self.base=Profile.load(ROOT/'benchmarks/integrated_330_v01/review_measured_stations/profile.review.json')

    def test_reversible_candidate_preserves_machine_stations_and_benchmark_range(self):
        before=deepcopy(self.base.data);candidate=candidate_profile(self.base)
        self.assertEqual(self.base.data,before)
        for field in ('motion','machine','stations','material','evidence'):
            self.assertEqual(candidate.data[field],self.base.data[field])
        self.assertEqual(candidate.data['motion']['paper_contact_z_range'],[-10,0])
        self.assertNotEqual(candidate.sha256,self.base.sha256)
        for stage in ('air','calibration','painting'):
            with self.assertRaises(ValueError):candidate.require(stage)

    def test_exact_operator_knots_and_no_scaling_clamping_or_extrapolation(self):
        p=candidate_profile(self.base)
        expected=((0,0),(.2,-1),(.4,-1.56),(.6,-2.68),(.93,-6.95),(1,-8))
        for medium,slot in (('ink','INK'),('color','A2')):
            curve=p.brush_for(medium,slot)
            self.assertEqual(curve.knots,expected)
            # Independent interior examples exercise every distinct slope.
            for pressure,z in ((.1,-.5),(.3,-1.28),(.5,-2.12),(.765,-4.815),(.965,-7.475)):
                self.assertAlmostEqual(curve.z_for(pressure),z,places=12)
            self.assertNotAlmostEqual(curve.z_for(.2),self.base.brush_for(medium,slot).z_for(.2)*.8)
            self.assertEqual(curve.z_for(1),-8)
            for pressure in (-.001,1.001):
                with self.assertRaises(ValueError):curve.z_for(pressure)
            values=[curve.z_for(i/1000) for i in range(1001)]
            self.assertTrue(all(b<=a for a,b in zip(values,values[1:])))

    def test_ink_and_color_can_be_revised_independently(self):
        p=candidate_profile(self.base)
        p.data['brush_profiles']['ink']['knots'][1][1]=-.9
        self.assertEqual(p.brush_for('color','A2').z_for(.2),-1)
        self.assertEqual(p.brush_for('ink','INK').z_for(.2),-.9)
        self.assertEqual(self.base.brush_for('ink','INK').z_for(.2),-2)


if __name__=='__main__':unittest.main()
