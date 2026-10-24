"""Terminal cleaning sequence and safe noncontact projection."""
from pathlib import Path
import unittest
from datascape.gcode.production.profiles import Profile
from benchmarks.integrated_330_v01 import spring_end_cleanup as clean

ROOT=Path(__file__).resolve().parents[1]

class SpringEndCleanupTests(unittest.TestCase):
    def test_both_brushes_finish_with_three_water_visits_then_two_purges(self):
        base=Profile.load(ROOT/'benchmarks/integrated_330_v01/review_spring_reload_1100_700/profile.spring.large_baegunmo.json')
        for medium in ('ink','color'):
            p,commands=clean.cleanup(base,medium)
            actions=[c.action for c in commands if c.kind=='marker']
            self.assertEqual([a for a in actions if a in ('wash','absorbent_contact','controlled_rewet','pigment_load')],['wash']*3+['absorbent_contact'])
            self.assertEqual(sum(c.action=='wash_dwell' and c.seconds==10 for c in commands),3)
            self.assertEqual(sum(c.action=='absorbent_contact_dwell' and c.seconds==4 for c in commands),2)
            self.assertEqual(sum(c.travel_phase=='lip_strip' for c in commands),3)
            self.assertFalse(any(c.artistic_pressure is not None for c in commands))
            self.assertEqual(commands[-2].xyz,clean.PARK)
            self.assertEqual(p.data['machine']['start_work_xyz'],list(clean.PARK))

    def test_terminal_air_preserves_xy_and_never_descends_below35(self):
        base=Profile.load(ROOT/'benchmarks/integrated_330_v01/review_spring_reload_1100_700/profile.spring.large_baegunmo.json')
        _,wet=clean.cleanup(base,'color');_,air=clean.cleanup(base,'color',True)
        wm=[c for c in wet if c.kind=='move'];am=[c for c in air if c.kind=='move']
        self.assertEqual([c.xyz[:2] for c in wm],[c.xyz[:2] for c in am])
        self.assertTrue(all(c.xyz[2]==35 for c in am))

if __name__=='__main__':unittest.main()
