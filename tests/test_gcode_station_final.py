"""Focused final-station regressions; physical profiles here are synthetic only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_gcode_integrated_330 import unit_profile, bind
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.trajectory import Builder, Materials, station_phase_feed
from benchmarks.integrated_330_v01.station_final import final_inputs, build_final, export_final, verify_final, NAMES, SLOTS
from studies.local_hover_v01.config import historical_xy

ROOT=Path(__file__).resolve().parents[1]


class FinalStationTests(unittest.TestCase):
    def test_production_phase_feeds_do_not_inherit_legacy_f60(self):
        d=deepcopy(unit_profile().data)
        d['motion'].update(station_clearance_mm=35,park_xyz=[800,800,35],station_approach_mm_min=3000,z_travel_mm_min=3000,
                           station_phase_limits_mm_min={'immersion':1000,'agitation':1000,'withdrawal':1000,'purge_contact':500})
        d['motion']['contact_mm_min']=60
        d['stations']['ink'].update(feed_mm_min=750,approach_z=11,agitation_cycles=1,
            agitation_bidirectional=True,agitation_xy_mm=[.5,0],agitation_floor_max_z=1,
            phase_feeds_mm_min={'immersion':750,'agitation':500,'withdrawal':1000,'purge_contact':500})
        b=Builder(bind(d)); Materials(b).station('ink','pigment_load')
        feeds={c.travel_phase:c.feed_mm_min for c in b.commands if c.action=='station_pigment_load'}
        self.assertEqual(feeds,{'immersion':750,'agitation':500,'withdrawal':1000})
        self.assertTrue(any(c.action=='station_approach' and c.xyz[2]==11 and c.feed_mm_min==3000 for c in b.commands))
        self.assertEqual(b.position[2],35)
        st=d['stations']['ink']; st.pop('phase_feeds_mm_min')
        self.assertEqual(station_phase_feed(st,d['motion'],'immersion'),60)  # legacy remains explicit

    def test_same_strokes_source_depths_and_station_visits_include_one_purge(self):
        r,p,_,prior,_=final_inputs(ROOT)
        old=json.loads((ROOT/'benchmarks/integrated_330_v01/review_numeric/plan.json').read_text())
        self.assertEqual(digest(r['benchmark_columns']),digest(old['benchmark_columns']))
        self.assertTrue(prior['large_baegunmo_strokes_to_G54_minus10_successful'])
        self.assertFalse(prior['new_Z35_station_phase_agitation_purge_pigment_policy_verified'])
        commands=build_final(r,p,'paint'); strokes=[c for c in commands if c.action=='draw']
        self.assertEqual(len(strokes),40); self.assertTrue(all(c.feed_mm_min==5000 for c in strokes))
        self.assertEqual([c.xyz[2] for c in strokes],(list(range(-1,-11,-1))+list(range(-10,0)))*2)
        self.assertFalse(any(c.kind=='pause' for c in commands))
        self.assertEqual([c.message for c in commands if c.action=='benchmark_station_visit'],
                         ['ink:pigment_load','ink:same_color_reload','water:wash','sponge:absorbent_contact','A2:pigment_load','A2:same_color_reload'])
        self.assertEqual(commands[-2].xyz,(800,800,35))

    def test_fast_approach_short_contact_agitation_and_vertical_purge(self):
        r,p,_,_,_=final_inputs(ROOT); commands=build_final(r,p,'paint')
        stations=[c for c in commands if c.kind=='move' and c.action.startswith('station_')]
        self.assertFalse(any(c.feed_mm_min==60 for c in stations))
        self.assertEqual({c.feed_mm_min for c in stations},{500,750,1000,3000})
        self.assertTrue(any(c.xyz==(840,380,8) and c.travel_phase=='immersion' for c in stations))
        self.assertTrue(any(c.xyz==(839.5,380,8) and c.travel_phase=='agitation' for c in stations))
        self.assertTrue(any(c.xyz==(840.5,380,8) and c.travel_phase=='agitation' for c in stations))
        purge=[c for c in stations if c.action=='station_absorbent_contact']
        self.assertEqual([c.xyz for c in purge],[(840,137.5,.5),(840,137.5,3.5)])
        self.assertTrue(all(c.feed_mm_min==500 for c in purge))
        position=p.data['machine']['start_work_xyz']
        for c in commands:
            if c.kind=='move':
                if c.action=='travel' and position[:2]!=c.xyz[:2]: self.assertGreaterEqual(min(position[2],c.xyz[2]),35)
                if c.action=='station_approach':
                    self.assertEqual(position[:2],c.xyz[:2]); self.assertEqual(c.feed_mm_min,3000)
                position=c.xyz

    def test_all20_registered_centers_and_existing12_slot_order_preserved(self):
        _,p,_,_,mapping=final_inputs(ROOT); xy=historical_xy(ROOT/'hardware/fluidnc/tool_coordinates.yaml')
        self.assertEqual(len(mapping['all_registered_centers']),20)
        self.assertEqual(set(p.data['material']['color_order']),set(SLOTS))
        for slot,center in mapping['all_registered_centers'].items():
            self.assertEqual(center,[xy[slot]['x'],xy[slot]['y']])
            self.assertEqual(p.data['stations'][slot]['center_xy'],center)
        for slot in ('D1','D2','D4','D5'):
            assessment=mapping['slot_assessments'][slot]
            self.assertEqual(assessment['axis_X850_headroom_mm'],2)
            self.assertFalse(assessment['full_brush_holder_clearance_verified'])
        self.assertEqual(p.data['stations']['A2']['liquid_reference_z'],6)
        self.assertEqual(p.data['stations']['A2']['immersion_mm'],2)

    def test_package_variants_readback_hashes_and_rehashed_command_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'final'; report=export_final(ROOT,out)
            self.assertTrue(verify_final(out)['water_pigment_commands_identical'])
            self.assertTrue(report['water_pigment_executable_commands_identical'])
            for name in NAMES.values():
                text=(out/(name+'.gcode')).read_text()
                self.assertTrue(text.endswith('M2\n')); self.assertNotIn('\nM0\n',text)
            path=out/(NAMES['water']+'.gcode')
            path.write_text(path.read_text().replace('F750.000000000','F60.000000000',1))
            manifest=json.loads((out/'MANIFEST_SHA256.json').read_text())
            manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (out/'MANIFEST_SHA256.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'shared plan'):verify_final(out)

    def test_explicit_phase_caps_and_official_readiness_remain_required(self):
        _,p,_,_,_=final_inputs(ROOT)
        self.assertEqual(p.data['evidence'],[])
        with self.assertRaises(ValueError):p.require('air')
        st=deepcopy(p.data['stations']['ink']); st['phase_feeds_mm_min']['immersion']=1001
        with self.assertRaisesRegex(ValueError,'independent'):station_phase_feed(st,p.data['motion'],'immersion')


if __name__=='__main__':unittest.main()
