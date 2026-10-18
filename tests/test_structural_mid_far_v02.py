"""Behavioral checks for growth-first mid/far representation and physical floors."""
from pathlib import Path
import json
import unittest
import numpy as np
from shapely.geometry import LineString

from datascape.vegetation.structural_mid_far_v02 import (terrain_guide,body_sites,
    growth_graph,build_representation,apply_visibility)
from datascape.vegetation.mid_far import load_evidence,digest,read_vectors,resample
from datascape.strokes.vector import sample
from datascape.rendering.spring_checkpoint import verify

ROOT=Path(__file__).resolve().parents[1]


class StructuralMidFarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v02.json').read_text())
        cls.evidence=load_evidence(ROOT,cls.config,ROOT/'docs/checkpoints/spring_integration_v04')
        cls.scene=cls.config['scenes'][0]
        cls.guide=terrain_guide(cls.scene,cls.evidence)
        cls.sites=body_sites(cls.scene,cls.guide,cls.evidence,cls.config)

    def test_guide_samples_actual_q_and_roots_remain_attached(self):
        p=np.asarray(self.guide['xy_mm']);q=sample(self.evidence.depth,p)
        self.assertLess(np.max(np.abs(q-self.scene['source_q_m'])),.25)
        line=LineString(p)
        for site in self.sites:
            self.assertLess(line.distance(__import__('shapely').geometry.Point(site['root_xy_mm'])),1e-6)
            self.assertIn('source_forward_m',site['site'])
        self.assertTrue(self.guide['nonplotting'])
        self.assertFalse(self.guide['exact_mesh_contact'])

    def test_unequal_collective_scaffold_is_deterministic(self):
        again=body_sites(self.scene,self.guide,self.evidence,self.config)
        self.assertEqual(digest(again),digest(self.sites))
        self.assertEqual(len({r['stand_id'] for r in self.sites if r['stand_role']!='relay'}),3)
        self.assertTrue(any(r['stand_role']=='relay' for r in self.sites))
        self.assertGreater(np.ptp([r['height_mm'] for r in self.sites]),8)
        u=np.array([r['guide_u'] for r in self.sites]);self.assertGreater(np.max(np.diff(u)),np.min(np.diff(u))*1.7)

    def test_branches_emerge_from_their_parent_axis(self):
        g=growth_graph(self.sites[5],'M2',self.config);axis=LineString(g['axis_xy_mm'])
        for b in g['branches']:
            self.assertEqual(b['parent_axis_id'],g['axis_id'])
            self.assertLess(axis.distance(__import__('shapely').geometry.Point(b['origin_xy_mm'])),1e-6)
            self.assertTrue(np.allclose(np.array(b['xy_mm'])[0],b['origin_xy_mm']))

    def test_color_descends_from_growth_nodes_not_ink_paths(self):
        graphs,ink,color=build_representation(self.sites,'M2',self.config)
        branches={b['id']:b for g in graphs for b in g['branches']}
        self.assertGreater(len(color),len(ink)*2)
        self.assertTrue(color)
        for r in color:
            self.assertNotIn('ink_parent_id',r)
            self.assertIn(r['growth_branch_id'],branches)
            node=np.array(r['foliage_origin_xy_mm']);p=np.array(r['xy_mm'])
            self.assertGreater(np.linalg.norm(p[-1]-node),np.linalg.norm(p[0]-node))
            self.assertGreater(np.dot(p[-1]-p[0],r['growth_direction_xy']),0)
            self.assertGreaterEqual(LineString(p).length,self.config['minimum_color_mm'])

    def test_native_small_tree_simplification_and_open_paths(self):
        small={**self.sites[0],'height_mm':12.}
        large={**self.sites[0],'height_mm':24.}
        gs,si,sc=build_representation([small],'M1',self.config)
        gl,li,lc=build_representation([large],'M1',self.config)
        self.assertLess(len(si),len(li)+1)
        self.assertEqual(gs[0]['nominal_height_mm'],12)
        for r in si+li:
            self.assertGreaterEqual(LineString(r['xy_mm']).length,self.config['minimum_ink_mm'])
            self.assertFalse(np.allclose(r['xy_mm'][0],r['xy_mm'][-1]))

    def test_real_mist_preserves_cores_floors_and_source_arcs(self):
        scene=self.config['scenes'][2];guide=terrain_guide(scene,self.evidence);sites=body_sites(scene,guide,self.evidence,self.config)
        _,rawi,rawc=build_representation(sites,'F3',self.config);lookup={r['id']:r for r in rawi+rawc}
        initial=digest(rawi+rawc)
        i,_=apply_visibility(rawi,self.evidence,self.config);c,_=apply_visibility(rawc,self.evidence,self.config)
        self.assertTrue(c);self.assertEqual(initial,digest(rawi+rawc))
        for r in i+c:
            p=resample(r['xy_mm'],.08)
            self.assertTrue(np.all(sample(self.evidence.protected_clearance,p,order=0)>r['assumed_footprint_mm']/2))
            minimum=self.config['minimum_color_mm'] if 'palette_slot' in r else self.config['minimum_ink_mm']
            self.assertGreaterEqual(LineString(r['xy_mm']).length,minimum-1e-8)
            a,b=r['source_arc_mm'];length=LineString(lookup[r['source_stroke_id']]['xy_mm']).length
            self.assertTrue(0<=a<b<=length+1e-7)
            self.assertAlmostEqual(b-a,LineString(r['xy_mm']).length,places=6)

    def test_depth_visibility_is_deterministic_and_not_alpha_fade(self):
        _,_,raw=build_representation(self.sites,'M2',self.config)
        a,la=apply_visibility(raw,self.evidence,self.config);b,lb=apply_visibility(raw,self.evidence,self.config)
        self.assertEqual(digest(a),digest(b));self.assertEqual(digest(la),digest(lb))
        parents={r['id']:r for r in raw}
        for r in a:self.assertEqual(r['preview_opacity'],parents[r['source_stroke_id']]['preview_opacity'])
        self.assertLess(sum(LineString(r['xy_mm']).length for r in a),sum(LineString(r['xy_mm']).length for r in raw))

    def test_checkpoint_and_foreground_catalog_remain_exact(self):
        verify(ROOT/'docs/checkpoints/spring_integration_v04')
        baseline=read_vectors(ROOT/'docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz')['strokes'];before=digest(baseline)
        build_representation(self.sites,'M3',self.config)
        self.assertEqual(digest(baseline),before)


if __name__=='__main__':unittest.main()
