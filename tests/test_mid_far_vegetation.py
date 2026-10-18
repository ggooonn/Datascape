"""Physical geometry, source-depth and preservation checks for exploratory LOD.

Synthetic visibility fixtures exercise safety only. Scene evidence is loaded
from the exact checkpoint and reduced-precision inherited F2 archives.
"""
from pathlib import Path
from copy import deepcopy
import json
import unittest

import numpy as np
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString

from datascape.vegetation.mid_far import (Evidence, load_evidence, local_flow_index,
    make_scaffold, native_sources, derive, visible_records, color_support,
    root_visibility, digest, read_vectors, resample)
from datascape.rendering.mid_far_catalog_support import footprint_metrics
from datascape.rendering.spring_checkpoint import verify
from datascape.strokes.vector import sample

ROOT=Path(__file__).resolve().parents[1]


def synthetic_evidence(retention=1.):
    shape=(900,600);depth=np.full(shape,1200.);keep=np.full(shape,retention)
    occ=np.ones(shape,bool);global_r=np.ones(shape);xyz=np.zeros((*shape,3))
    safe=np.full(shape,1e6)
    return Evidence(depth,xyz,np.full(shape,.4),np.full(shape,25.),occ,keep,global_r,safe,
                    dict(scope='Synthetic safety fixture; never scene evidence'))


def source_record(identity,xy):
    return dict(id=identity,xy_mm=xy,source_forward_m=1200.,unit_id=identity,
                width_mm=.26,grammar_part='directional-foliage',catalog_source_ids=['fixture/native'],
                physical_plotting_validated=False,owner_id='fixture',group_id='fixture')


class MidFarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v01.json').read_text())
        cls.checkpoint=ROOT/'docs/checkpoints/spring_integration_v04'
        cls.evidence=load_evidence(ROOT,cls.config,cls.checkpoint)
        cls.sites=json.loads((cls.checkpoint/'artifacts/sites.json').read_text())
        cls.baseline=read_vectors(ROOT/'docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz')['strokes']
        cls.flow=local_flow_index(cls.baseline)
        cls.crop={**cls.config['crops'][0],'root_count':4}
        cls.scaffold=make_scaffold(cls.crop,cls.evidence,cls.sites,cls.flow,cls.config)
        cls.sources,cls.templates,_=native_sources(cls.scaffold,cls.config)

    def test_checkpoint_preservation_and_precision_disclosure(self):
        verify(self.checkpoint)
        self.assertTrue(self.evidence.provenance['occupancy_exact_checkpoint_hash'])
        self.assertFalse(self.evidence.provenance['full_float64_field_hash_equality'])
        self.assertEqual(self.config['checkpoint_commit'],'90bb2572a35731ccdb38ec332456f2f94ac76456')

    def test_real_scaffold_is_deterministic_and_depth_eligible(self):
        again=make_scaffold(self.crop,self.evidence,self.sites,self.flow,self.config)
        self.assertEqual(digest(self.scaffold['roots']),digest(again['roots']))
        lo,hi=self.crop['source_q_range_m']
        for r in self.scaffold['roots']:
            self.assertGreaterEqual(r['native_height_mm'],22)
            self.assertTrue(lo<=r['site']['source_forward_m']<=hi)
            self.assertEqual(r['site']['depth_provider'],'saved-F2-1mm-raster-float32')
            self.assertIn('source_id',r['flow']['A'])

    def test_derived_unit_provenance_and_spacing(self):
        before=digest(self.sources)
        a,_=derive(self.scaffold,self.sources,self.templates,self.crop,'field',self.config)
        b,_=derive(self.scaffold,self.sources,self.templates,self.crop,'field',self.config)
        self.assertEqual(digest(a),digest(b));self.assertEqual(before,digest(self.sources))
        native_ids={r['id'] for r in self.sources}
        self.assertTrue(a)
        for r in a:
            self.assertTrue(r['catalog_source_ids'])
            self.assertTrue(set(r['catalog_source_ids'])<=native_ids)
            self.assertGreaterEqual(LineString(r['xy_mm']).length,2.8-1e-8)
        self.assertEqual(footprint_metrics(a)['units_below_requested_clearance'],0)

    def test_reserve_split_never_bridges_gap(self):
        e=synthetic_evidence();mask=np.zeros((900,600),bool);mask[390:410,290:310]=True
        e.retention[mask]=0;e.protected_clearance=distance_transform_edt(~mask)-distance_transform_edt(mask)
        raw=source_record('cross-reserve',[[270,400],[330,400]])
        out,_=visible_records([raw],e,self.config,'inherited')
        self.assertEqual(len(out),2)
        for r in out:
            p=resample(r['xy_mm'],.05)
            self.assertTrue(np.all(sample(e.protected_clearance,p,order=0)>.8/2))
            self.assertGreaterEqual(LineString(r['xy_mm']).length,2.8)
            self.assertFalse(LineString(r['xy_mm']).intersects(__import__('shapely').geometry.box(290,390,310,410)))

    def test_mist_is_source_depth_dependent(self):
        e=synthetic_evidence(.15);p=np.array([[200,400],[210,400]])
        back=source_record('back',p.tolist());front={**back,'source_forward_m':300.}
        ret_back,_=root_visibility(e,back,p);ret_front,_=root_visibility(e,front,p)
        self.assertTrue(np.all(ret_front>ret_back+.7))
        e.global_retention[:]=0
        ret,_=root_visibility(e,front,p);self.assertTrue(np.all(ret==0))

    def test_weak_mist_changes_geometry_and_retains_floor(self):
        e=synthetic_evidence(.25)
        raw=[source_record(f'unit-{i}',[[150+i*5,400],[154+i*5,401]]) for i in range(30)]
        original=digest(raw)
        inherited,_=visible_records(raw,e,self.config,'inherited')
        improved,ledger=visible_records(raw,e,self.config,'improved')
        self.assertEqual(digest(raw),original)
        self.assertLess(sum(LineString(r['xy_mm']).length for r in improved),
                        sum(LineString(r['xy_mm']).length for r in inherited))
        self.assertTrue(any(r['reason']=='whole-unit-mist-omission' for r in ledger))
        self.assertTrue(all(LineString(r['xy_mm']).length>=2.8-1e-8 for r in improved))
        lookup={r['id']:LineString(r['xy_mm']).length for r in raw}
        for r in improved:
            a,b=r['source_arc_mm']
            self.assertTrue(0<=a<b<=lookup[r['source_stroke_id']]+1e-8)
            self.assertAlmostEqual(b-a,LineString(r['xy_mm']).length,places=6)

    def test_color_uses_same_parent_and_existing_slots(self):
        e=synthetic_evidence();raw=[source_record(f'color-{i}',[[150+i*5,400],[154+i*5,401]]) for i in range(20)]
        colors,_=color_support(raw,e,self.config,{'C1':38,'C2':34,'A5':10,'C3':8,'C4':4,'D1':4,'B4':2})
        self.assertTrue(colors)
        for r in colors:
            self.assertIn(r['ink_parent_id'],{p['id'] for p in raw})
            self.assertIn(r['palette_slot'],['C1','C2','A5','C3','C4','D1','B4'])
            self.assertFalse(r['physical_plotting_validated'])
            self.assertEqual(len(r['xy_mm']),len(r['width_profile_mm']))


if __name__=='__main__':unittest.main()
