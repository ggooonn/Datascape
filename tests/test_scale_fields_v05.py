"""Scale-field behavior, typed contacts and immutable A/B/C comparisons."""
from pathlib import Path
from copy import deepcopy
import json,unittest
import numpy as np
from shapely.geometry import LineString
from datascape.strokes.vector import sample,resample
from datascape.vegetation.mid_far import load_evidence,digest,read_vectors
from datascape.vegetation.scale_fields_v05 import Ground,density,macro_field,micro_field,assemble
from datascape.vegetation.territorial_mid_far_v04 import arc
from datascape.rendering.mid_far_catalog_support import fixed_scene,preview_svg
from datascape.rendering.spring_checkpoint import verify,channels

ROOT=Path(__file__).resolve().parents[1]


class ScaleFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v05.json').read_text());v4=json.loads((ROOT/cfg['v04_config']).read_text());old=json.loads((ROOT/v4['v02_config']).read_text());cls.c={**old,**v4,**cfg}
        cls.e=load_evidence(ROOT,old,ROOT/'docs/checkpoints/spring_integration_v04');cls.g=Ground(cls.e,cfg['regions']['M'])
        cls.raw,cls.macro,cls.ledger,cls.support=macro_field('M',cls.g,cls.e,cls.c)
        cls.mraw,cls.micro,_=micro_field('M',cls.g,cls.e,cls.c)

    def test_large_field_is_continuous_terrain_construction_not_tree_multiplication(self):
        self.assertTrue(self.macro)
        p=np.concatenate([r['xy_mm'] for r in self.macro]);self.assertGreater(np.ptp(p[:,0]),160)
        self.assertGreater(np.ptp(p[:,1]),30)
        self.assertGreater(sum(LineString(r['xy_mm']).length>20 for r in self.macro),10)
        self.assertTrue(all(r['scale_tier']=='macro' for r in self.macro))
        self.assertTrue(all('tree' not in r['owner_id'] for r in self.macro))
        self.assertTrue(any(np.ptp(r['source_forward_profile_m'])>25 for r in self.macro))

    def test_field_has_coherent_dense_centers_and_an_open_neck(self):
        self.assertGreater(density(.2,0),.8)
        self.assertLess(density(.405,.3),.08)
        self.assertGreater(density(.59,.05),density(.59,.96)*2)
        self.assertTrue(all(s['nonplotting'] for s in self.support))

    def test_small_texture_has_typed_contacts_and_compact_continuous_marks(self):
        taps=[r for r in self.micro if r['primitive']=='tap'];lines=[r for r in self.micro if r['primitive']=='stroke']
        self.assertTrue(taps);self.assertTrue(lines)
        for r in taps:
            self.assertEqual(len(r['xy_mm']),1);self.assertEqual(r['source_arc_mm'],[0.,0.])
            self.assertTrue(r['requires_contact_calibration']);self.assertFalse(r['physical_plotting_validated'])
            self.assertEqual(r['diameter_mm'],.9)
        for r in lines:
            self.assertGreaterEqual(LineString(r['xy_mm']).length,3.2)
            self.assertLess(np.ptp(np.array(r['xy_mm']),axis=0).max(),3.)
        self.assertTrue(all('trunk' not in r['generation_rule'] for r in self.micro))

    def test_visibility_keeps_profiles_raw_intervals_and_protected_regions(self):
        lookup={r['id']:r for r in self.raw+self.mraw}
        for r in self.macro+self.micro:
            p=np.array(r['xy_mm'])
            if r['primitive']=='stroke':
                a,b=r['source_arc_mm'];raw=lookup[r['source_stroke_id']]
                self.assertAlmostEqual(b-a,LineString(p).length,places=6)
                expected=np.interp(a+arc(p),arc(raw['xy_mm']),raw['source_forward_profile_m'])
                self.assertTrue(np.allclose(expected,r['source_forward_profile_m']))
                p=resample(p,.1)
            self.assertTrue(np.all(sample(self.e.protected_clearance,p,order=0)>r['assumed_footprint_mm']/2))

    def test_ABC_comparison_keeps_medium_and_macro_exact_and_micro_is_subset(self):
        medium=[dict(id='medium-control',scale_tier='medium',xy_mm=[[10,10],[10,15]])]
        before=digest(self.macro+self.micro+medium);cases={k:assemble(self.macro,self.micro,medium,k) for k in ['A','B','C']}
        for rows in cases.values():self.assertEqual([r for r in rows if r['scale_tier']=='medium'],medium)
        self.assertEqual([r for r in cases['A'] if r['scale_tier']=='macro'],[r for r in cases['C'] if r['scale_tier']=='macro'])
        cids={r['id'] for r in cases['C'] if r['scale_tier']=='micro'};bids={r['id'] for r in cases['B'] if r['scale_tier']=='micro'}
        self.assertTrue(cids);self.assertLess(len(cids),len(bids));self.assertTrue(cids<=bids)
        self.assertEqual(before,digest(self.macro+self.micro+medium))

    def test_deterministic_contacts_and_svg_use_actual_circles(self):
        import yaml,xml.etree.ElementTree as ET
        _,again,_=micro_field('M',Ground(self.e,self.c['regions']['M']),self.e,self.c)
        self.assertEqual(digest(again),digest(self.micro))
        pal=yaml.safe_load((ROOT/'configs/palettes/palette_20.yaml').read_text())
        root=ET.fromstring(preview_svg([],self.micro,pal));ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(len(root.findall('.//s:circle',ns)),sum(r['primitive']=='tap' for r in self.micro))

    def test_scene_keeps_canonical_sources_and_non_target_objects(self):
        baseline=read_vectors(ROOT/'docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz')['strokes'];oldi,oldc=channels(ROOT/'docs/checkpoints/spring_integration_v04');before=digest(baseline+oldi+oldc['caseC'])
        ink,color,excluded=fixed_scene(baseline,oldi,oldc,self.c)
        terrain=[r for r in baseline if r['layer'] in ['A','B','D']]
        self.assertEqual(ink[:len(terrain)],terrain)
        ids={r['id'] for r in ink}
        for r in oldi:
            if r.get('source_family') in ['tree','rock','Soil'] and r.get('owner_id') not in excluded:self.assertIn(r['id'],ids)
        self.assertEqual(before,digest(baseline+oldi+oldc['caseC']))
        verify(ROOT/'docs/checkpoints/spring_integration_v04')


if __name__=='__main__':unittest.main()
