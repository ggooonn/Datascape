"""Vector clipping, depth applicability, sparse gaps and root protection."""
from copy import deepcopy
import unittest
from shapely.geometry import LineString, Point, box
from datascape.vegetation import tree_final_scale as gram
from datascape.vegetation import tree_occlusion_proof as proof


class OcclusionProofTests(unittest.TestCase):
    def test_difference_splits_real_paths_keeps_direction_and_parent(self):
        source=[{'id':'a','xy_mm':[[10.,0.],[0.,0.]],'forward_depth_m':2000.,'layer':'A'}];old=deepcopy(source)
        rr,note=proof.clip_vectors(source,box(4,-1,6,1),1200)
        self.assertEqual(source,old);self.assertEqual(len(rr),2)
        self.assertTrue(all(r['xy_mm'][0][0]>r['xy_mm'][-1][0] for r in rr))
        self.assertTrue(all(r['source_stroke_id']=='a' for r in rr));self.assertAlmostEqual(note['removed_length_mm'],2.)
        self.assertTrue(all(LineString(r['xy_mm']).intersection(box(4.001,-1,5.999,1)).is_empty for r in rr))

    def test_nearer_and_supporting_depth_are_not_erased(self):
        source=[{'id':str(d),'xy_mm':[[0.,0.],[20.,0.]],'forward_depth_m':d} for d in [900.,1200.,1210.,1800.]]
        rr,note=proof.clip_vectors(source,box(5,-1,15,1),1200)
        for row in source[:3]:self.assertIn(row,rr)
        self.assertEqual(note['eligible_source_paths'],1)

    def test_selective_masks_preserve_more_terrain_than_full_support(self):
        t=gram.make_tree('B',root=(110,170),height=95);a=proof.MaskAssumptions();m=proof.masks(t,a);p=proof.synthetic_probes()
        full,f=proof.clip_vectors(p,m['full'],1200,a);select,s=proof.clip_vectors(p,m['selective'],1200,a)
        self.assertGreater(f['removed_length_mm'],s['removed_length_mm'])
        self.assertGreater(s['removed_length_mm'],0)
        self.assertTrue(any(r['id']=='nearer-depth-ruler' for r in select))
        self.assertTrue(m['selective'].intersection(m['root_protection']).area<1e-9)
        self.assertTrue(m['body'].difference(m['selective']).area<1e-9)
        root=Point(t.root);self.assertTrue(m['body'].distance(root)<1)

    def test_bare_tree_does_not_erase_an_empty_canopy_support(self):
        t=gram.make_tree('B',growth_controls=gram.prior.GrowthControls(vigor=0));m=proof.masks(t)
        self.assertTrue(m['canopy'].is_empty)
        self.assertGreater(m['full'].area,m['selective'].area)

    def test_minimum_fragments_and_width_tolerance_are_real_geometry(self):
        source=[{'id':'a','xy_mm':[[0.,0.],[20.,0.]],'forward_depth_m':1800.}]
        rr,n=proof.clip_vectors(source,box(1,-1,19,1),1200)
        self.assertEqual(rr,[]);self.assertAlmostEqual(n['short_fragment_length_dropped_mm'],2.)
        t=gram.make_tree('P');a=proof.masks(t);b=proof.masks(t,proof.MaskAssumptions(terrain_width_mm=1.2,edge_tolerance_mm=.3))
        self.assertGreater(b['selective'].area,a['selective'].area)
        with self.assertRaises(ValueError):proof.masks(t,proof.MaskAssumptions(vegetation_width_mm=0))


if __name__=='__main__':unittest.main()
