"""Behavioral tests for distinct foliage construction and depth-aware fields."""
from copy import deepcopy
from pathlib import Path
import gzip,json,unittest
import numpy as np
from shapely.geometry import LineString,Point
from datascape.vegetation.pictorial_families_v03 import (
    arrange,larger_sites,generate,depth_overlap,palette_treatment,preview)
from datascape.vegetation.structural_mid_far_v02 import terrain_guide,body_sites,build_representation,apply_visibility
from datascape.vegetation.mid_far import load_evidence,digest,resample
from datascape.strokes.vector import sample
from datascape.rendering.mid_far_catalog_support import geometry_digest
from datascape.rendering.spring_checkpoint import verify

ROOT=Path(__file__).resolve().parents[1]


class PictorialMidFarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v03.json').read_text())
        old=json.loads((ROOT/cfg['v02_config']).read_text());cls.config={**old,**cfg}
        cls.e=load_evidence(ROOT,old,ROOT/'docs/checkpoints/spring_integration_v04')
        cls.original={}
        for scene in old['scenes']:
            cls.original[scene['id']]=body_sites(scene,terrain_guide(scene,cls.e),cls.e,old)
        cls.mid=arrange(cls.original['A'],'staggered',cfg['regions']['A'],cls.e,cfg)

    def test_staggering_uses_measured_source_depth_not_screen_row(self):
        original=digest(self.original)
        self.assertEqual(len(self.mid),len(self.original['A']))
        self.assertGreater(np.ptp([s['site']['source_forward_m'] for s in self.mid]),150)
        for a,b in zip(self.original['A'],self.mid):
            self.assertEqual(a['height_mm'],b['height_mm'])
            self.assertEqual(b['source_v02_body_id'],a['id'])
            p=np.array(b['root_xy_mm']).reshape(1,2)
            self.assertAlmostEqual(float(sample(self.e.depth,p)[0]),b['site']['source_forward_m'],places=6)
            self.assertTrue(sample(self.e.occupied.astype(float),p,order=0)[0]>.5)
        self.assertEqual(original,digest(self.original))
        again=arrange(self.original['A'],'staggered',self.config['regions']['A'],self.e,self.config)
        self.assertEqual(digest(again),digest(self.mid))

    def test_expanded_field_has_multiple_depth_lobes_and_unequal_groups(self):
        sites=arrange(self.original['C'],'expanded',self.config['regions']['C'],self.e,self.config)
        self.assertGreater(len(sites),len(self.original['C']))
        self.assertGreater(np.ptp([s['site']['source_forward_m'] for s in sites]),250)
        extra=[s for s in sites if s['stand_role']=='extension']
        self.assertGreater(len({s['subcluster_id'] for s in extra}),1)
        self.assertGreater(np.ptp([s['height_mm'] for s in sites]),4)
        self.assertLess(len(extra),15)

    def test_radial_control_delegates_exactly_to_v02(self):
        a,ai,ac=generate(self.original['A'],'M2','R',self.config)
        b,bi,bc=build_representation(self.original['A'],'M2',self.config)
        self.assertEqual(digest(a),digest(b))
        self.assertEqual([r['xy_mm'] for r in ai],[r['xy_mm'] for r in bi])
        self.assertEqual([r['xy_mm'] for r in ac],[r['xy_mm'] for r in bc])

    def test_surface_sections_have_distributed_starts_and_coherent_surfaces(self):
        _,i,c=generate(self.mid[:2],'M2','S',self.config)
        groups={}
        for r in c:
            groups.setdefault(r['surface_id'],[]).append(r)
            self.assertNotIn('ink_parent_id',r)
            self.assertIn('curved canopy surface',r['generation_rule'])
        for records in groups.values():
            starts=np.array([r['xy_mm'][0] for r in records])
            self.assertGreater(np.ptp(starts,axis=0).max(),2.)
            self.assertGreater(len({r['surface_level'] for r in records}),2)
            self.assertEqual(len({tuple(r['surface_axis_xy']) for r in records}),1)
        _,other_i,_=generate(self.mid[:2],'M2','U',self.config)
        self.assertEqual([r['xy_mm'] for r in i],[r['xy_mm'] for r in other_i])

    def test_shoot_offshoot_is_attached_to_interior_joint_of_its_axis(self):
        _,_,c=generate(self.mid[:2],'M2','U',self.config);groups={}
        for r in c:groups.setdefault(r['shoot_id'],{})[r['shoot_role']]=r
        for pair in groups.values():
            axis=pair['axis'];off=pair['offshoot'];joint=Point(off['xy_mm'][0]);line=LineString(axis['xy_mm'])
            self.assertLess(line.distance(joint),1e-8)
            self.assertGreater(line.project(joint),1.)
            self.assertLess(line.project(joint),line.length-1.)
            self.assertEqual(off['xy_mm'][0],off['joint_xy_mm'])
            self.assertNotEqual(axis['xy_mm'][0],off['xy_mm'][0])

    def test_real_visibility_and_rear_overlap_keep_floors_and_raw_intervals(self):
        for family in ['R','S','U']:
            with self.subTest(family=family):
                _,ri,rc=generate(self.mid,'M2',family,self.config);before=digest(ri+rc);lookup={r['id']:r for r in ri+rc}
                i,_=apply_visibility(ri,self.e,self.config);c,_=apply_visibility(rc,self.e,self.config)
                ink,color,ledger=depth_overlap(i,c,self.config)
                if family=='R':self.assertGreater(sum(r['removed_mm'] for r in ledger),0)
                # Sparse U marks need not form an opaque core. Do not invent
                # masking just to force a family-independent occlusion ratio.
                self.assertEqual(before,digest(ri+rc))
                for r in ink+color:
                    length=LineString(r['xy_mm']).length;a,b=r['source_arc_mm']
                    floor=3.2 if 'palette_slot' in r else 2.8
                    self.assertGreaterEqual(length,floor-1e-7)
                    self.assertTrue(0<=a<b<=LineString(lookup[r['source_stroke_id']]['xy_mm']).length+1e-6)
                    self.assertAlmostEqual(b-a,length,places=6)
                    p=resample(r['xy_mm'],.1)
                    self.assertTrue(np.all(sample(self.e.protected_clearance,p,order=0)>r['assumed_footprint_mm']/2))

    def test_second_clip_composes_offset_even_when_entire_path_survives(self):
        rows=[]
        for j in range(4):
            rows.append(dict(id=f'near-{j}',source_stroke_id=f'near-{j}',source_arc_mm=[0.,15.],
                xy_mm=[[95,100],[110,100]],owner_id='near',source_forward_m=1000.,assumed_footprint_mm=1.2,palette_slot='C2'))
        rear=dict(id='rear',source_stroke_id='raw-rear',source_arc_mm=[4.,14.],xy_mm=[[140,100],[150,100]],
            owner_id='rear',source_forward_m=2000.,assumed_footprint_mm=1.2,palette_slot='C2')
        _,color,_=depth_overlap([],rows+[rear],self.config)
        retained=next(r for r in color if r['owner_id']=='rear')
        self.assertEqual(retained['source_arc_mm'],[4.,14.])
        self.assertEqual(retained['source_stroke_id'],'raw-rear')

    def test_native_larger_forms_are_uncommon_and_not_scaled_finished_paths(self):
        one=larger_sites(self.mid,'one');varied=larger_sites(self.mid,'varied')
        self.assertEqual(sum(r['height_mm']>35 for r in one),1)
        self.assertEqual(sorted(r['height_mm'] for r in varied if r['height_mm']>35),[36.,55.])
        first=deepcopy(self.mid[0]);first['height_mm']=24.
        big=deepcopy(first);big['height_mm']=55.
        gs,si,sc=generate([first],'M1','R',self.config);gl,li,lc=generate([big],'M1','R',self.config)
        self.assertEqual(gl[0]['nominal_height_mm'],55.)
        self.assertNotEqual(len(si[0]['xy_mm']),len(li[0]['xy_mm']))
        self.assertGreater(max(LineString(r['xy_mm']).length for r in li),max(LineString(r['xy_mm']).length for r in si))

    def test_palette_and_alpha_change_no_geometry_or_ink(self):
        _,ink,color=generate(self.mid,'M2','S',self.config);before=digest(ink)
        treatments=[palette_treatment(color,t,self.config) for t in ['global','local','combined']]
        self.assertEqual(len({geometry_digest(rows) for rows in treatments}),1)
        self.assertGreater(len({tuple(r['palette_slot'] for r in rows) for rows in treatments}),1)
        for rows in treatments:self.assertTrue(all(r['palette_slot'] in self.config['global_slots'] for r in rows))
        self.assertEqual(geometry_digest(preview(color,1.)),geometry_digest(preview(color,.28)))
        self.assertEqual(before,digest(ink))

    def test_checkpoint_and_v02_sources_remain_read_only(self):
        verify(ROOT/'docs/checkpoints/spring_integration_v04')
        # This test does not require untracked review output dependencies.
        self.assertEqual(self.config['parent_commit'],'6bc9860070dac4aa99212ae14900589e3d1cc693')


if __name__=='__main__':unittest.main()
