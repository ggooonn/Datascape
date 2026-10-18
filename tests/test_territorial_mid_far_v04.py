"""Behavioral tests for occupation, multi-body surfaces and source-depth color."""
from pathlib import Path
from copy import deepcopy
import json,unittest
import numpy as np
from shapely.geometry import LineString,Point
from datascape.vegetation.mid_far import load_evidence,digest,read_vectors,bounds_filter
from datascape.strokes.vector import sample,resample
from datascape.vegetation.structural_mid_far_v02 import terrain_guide,body_sites
from datascape.vegetation.pictorial_families_v03 import arrange,preview
from datascape.vegetation.territorial_mid_far_v04 import (
    support_field,generate,visibility,vegetation_overlap,colorize,terrain_treatment,arc,clip_profiled)
from datascape.rendering.mid_far_catalog_support import geometry_digest
from datascape.rendering.mid_far_catalog_support import occupation
from datascape.rendering.spring_checkpoint import verify

ROOT=Path(__file__).resolve().parents[1]


class TerritorialMidFarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v04.json').read_text());old=json.loads((ROOT/cfg['v02_config']).read_text());cls.c={**old,**cfg}
        cls.e=load_evidence(ROOT,old,ROOT/'docs/checkpoints/spring_integration_v04')
        scene=old['scenes'][0];original=body_sites(scene,terrain_guide(scene,cls.e),cls.e,old)
        cls.control=original
        cls.territory,_=support_field('A','territory',original,cls.e,cls.c)
        cls.clustered,_=support_field('A','clustered',original,cls.e,cls.c)
        common={s['id'] for s in cls.territory}&{s['id'] for s in cls.clustered}
        cls.territory=[s for s in cls.territory if s['id'] in common];cls.clustered=[s for s in cls.clustered if s['id'] in common]

    def test_occupation_expands_support_without_adding_internal_rays(self):
        self.assertGreater(len(self.territory),len(self.control)*3)
        _,_,a,_=generate(self.control,'M2','R',self.c);_,_,b,_=generate(self.territory,'M2','R',self.c)
        self.assertEqual(len(a),9*len(self.control));self.assertEqual(len(b),9*len(self.territory))
        bounds=self.c['regions']['A']['bounds_mm']
        aocc=occupation(dict(sites=self.control,raw_color=a,color=a),bounds,self.e)
        bocc=occupation(dict(sites=self.territory,raw_color=b,color=b),bounds,self.e)
        self.assertGreater(bocc['territorial_root_5mm_support_fraction'],aocc['territorial_root_5mm_support_fraction']*2)

    def test_concentration_has_matched_members_heights_and_measured_contacts(self):
        self.assertEqual([s['id'] for s in self.territory],[s['id'] for s in self.clustered])
        for a,b in zip(self.territory,self.clustered):
            self.assertEqual(a['height_mm'],b['height_mm'])
            for s in [a,b]:
                p=np.array(s['root_xy_mm']).reshape(1,2)
                self.assertAlmostEqual(float(sample(self.e.depth,p)[0]),s['site']['source_forward_m'],places=6)
        self.assertGreater(np.ptp([s['site']['source_forward_m'] for s in self.clustered]),300)
        result,_=support_field('A','territory',self.control,self.e,self.c)
        self.assertEqual(digest([s for s in result if s['id'] in {r['id'] for r in self.territory}]),digest(self.territory))

    def test_surfaces_share_members_and_retain_variable_depth_profiles(self):
        _,_,color,links=generate(self.clustered,'M2','S',self.c)
        shared=[r for r in color if len(r['source_member_ids'])>1]
        self.assertTrue(shared);self.assertTrue(any(np.ptp(r['source_forward_profile_m'])>10 for r in shared))
        self.assertTrue(all(len(r['source_forward_profile_m'])==len(r['xy_mm']) for r in color))
        self.assertTrue(all(l['nonplotting'] for l in links))
        self.assertTrue(all('ink_parent_id' not in r for r in color))

    def test_jointed_sides_are_connected_to_distinct_leader_joints(self):
        _,_,color,_=generate(self.clustered[:3],'M2','U',self.c)
        laterals=[r for r in color if '/lateral-' in r['id']]
        self.assertEqual(len(laterals),6)
        for r in laterals:
            self.assertEqual(r['xy_mm'][0],r['joint_xy_mm'])
            self.assertIn(r['joint_xy_mm'],r['joint_chain_xy_mm'])
        self.assertGreater(len({r['hierarchy_tier'] for r in color}),2)

    def test_length_roles_have_real_geometric_hierarchy(self):
        for fam in ['R','S','U']:
            with self.subTest(family=fam):
                _,_,rows,_=generate(self.clustered,'M2',fam,self.c)
                tiers={t:[LineString(r['xy_mm']).length for r in rows if r['hierarchy_tier']==t] for t in ['short','medium','long']}
                self.assertTrue(all(tiers.values()))
                self.assertGreater(np.median(tiers['long']),np.median(tiers['short'])*1.6)
                self.assertTrue(all(LineString(r['xy_mm']).length>=3.2 for r in rows))

    def test_profiled_clipping_composes_raw_arc_and_depth_even_after_second_clip(self):
        r=dict(id='profile-test',source_stroke_id='raw',source_arc_mm=[4.,24.],xy_mm=[[100.,100.],[120.,100.]],
            source_forward_m=1200.,source_forward_profile_m=[1000.,1400.],palette_slot='C2',width_mm=.95,
            width_profile_mm=[.8,1.1],opacity_profile=[.28,.28])
        def gate(xy,aa,rec):return xy[:,0]-105.,['test-window']
        p,_=clip_profiled(r,gate,self.c);self.assertEqual(len(p),1);a=p[0]
        self.assertAlmostEqual(a['source_arc_mm'][0],9.);self.assertAlmostEqual(a['source_forward_profile_m'][0],1100.)
        b,_=clip_profiled(a,lambda xy,aa,rec:(np.ones(len(xy)),[]),self.c)
        self.assertEqual(b[0]['source_arc_mm'],a['source_arc_mm']);self.assertEqual(b[0]['source_forward_profile_m'],a['source_forward_profile_m'])

    def test_real_visibility_and_overlap_preserve_raw_profiles_and_floors(self):
        _,ri,rc,_=generate(self.clustered,'M2','S',self.c);initial=digest(ri+rc);lookup={r['id']:r for r in ri+rc}
        i,_=visibility(ri,self.e,self.c);c,_=visibility(rc,self.e,self.c);i,c,_=vegetation_overlap(i,c,self.c)
        self.assertEqual(digest(ri+rc),initial)
        for r in i+c:
            length=LineString(r['xy_mm']).length;a,b=r['source_arc_mm'];raw=lookup[r['source_stroke_id']]
            self.assertAlmostEqual(b-a,length,places=6);self.assertGreaterEqual(length,3.2 if 'palette_slot' in r else 2.8)
            expected=np.interp(a+arc(r['xy_mm']),arc(raw['xy_mm']),raw['source_forward_profile_m'])
            self.assertTrue(np.allclose(r['source_forward_profile_m'],expected))
            self.assertTrue(np.all(sample(self.e.protected_clearance,resample(r['xy_mm'],.1),order=0)>r['assumed_footprint_mm']/2))

    def test_palette_gradient_changes_slots_without_relocating_or_fading_geometry(self):
        _,_,color,_=generate(self.clustered,'M2','R',self.c);before=digest(color)
        near=colorize(color,self.c,depth_override=400);far=colorize(color,self.c,depth_override=3300)
        self.assertEqual(geometry_digest(near),geometry_digest(far));self.assertEqual(before,digest(color))
        self.assertTrue(all(r['palette_slot'] in self.c['vegetation_slots'] for r in near+far))
        self.assertTrue(any(r['palette_slot']=='C5' for r in near));self.assertFalse(any(r['palette_slot']=='C5' for r in far))
        self.assertGreater(sum(r['palette_slot'] in ['C1','A5','A3'] for r in far),sum(r['palette_slot'] in ['C1','A5','A3'] for r in near))
        self.assertEqual([r['source_forward_m'] for r in near],[r['source_forward_m'] for r in far])
        self.assertEqual(geometry_digest(preview(near,.28)),geometry_digest(preview(near,1.)))

    def test_terrain_diagnostics_keep_sources_and_ridges_and_respect_limit(self):
        base=read_vectors(ROOT/'docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz')['strokes']
        bounds=self.c['regions']['A']['bounds_mm'];ctx=[r for r in bounds_filter(base,bounds) if r['layer'] in ['A','B','D']]
        initial=digest(ctx);_,_,raw,_=generate(self.clustered,'M2','R',self.c);color,_=visibility(raw,self.e,self.c)
        overlay,note=terrain_treatment(ctx,color,self.e,'overlay',self.c,bounds);limited,ln=terrain_treatment(ctx,color,self.e,'limited',self.c,bounds)
        self.assertEqual(digest(ctx),initial);self.assertEqual(digest(overlay),initial);self.assertLessEqual(ln['fraction_removed'],.08+1e-8)
        self.assertEqual(digest([r for r in limited if r['layer']=='D']),digest([r for r in ctx if r['layer']=='D']))
        verify(ROOT/'docs/checkpoints/spring_integration_v04')


if __name__=='__main__':unittest.main()
