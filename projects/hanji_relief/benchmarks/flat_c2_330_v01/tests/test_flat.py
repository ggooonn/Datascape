"""Source-spacing, flat-reference, four-condition service and serialization tests."""
import unittest,tempfile,json,hashlib
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from decimal import Decimal
from itertools import combinations
from projects.hanji_relief.data import PROJECT,load_dots,load_json
from projects.hanji_relief.plan import standard_plans,remaining
from projects.hanji_relief.benchmarks.flat_c2_330_v01.benchmark import *

class FlatComparisonTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cfg=config();cls.plan=make_plan();cls.p,cls.cs=build(cls.plan);cls.text=serialize(cls.plan,cls.p,cls.cs)
 def test_deterministic_source_patch_and_bounds(self):
  a,meta=select_patch();b,meta2=select_patch()
  self.assertEqual(meta,meta2);self.assertEqual(len(a),40);self.assertTrue(all(d.physical_panel_id==4 and d.color_id=='C2' for d in a))
  self.assertLessEqual(meta['width_mm'],125);self.assertLessEqual(meta['height_mm'],125)
  self.assertEqual([d.study_dot_id for d in a],[d.study_dot_id for d in b])
 def test_translation_only_all_pairwise_displacements(self):
  source,_=select_patch()
  for q in ORDER:
   rows=[r for r in self.plan['rows'] if r['quadrant']==q]
   self.assertEqual([r['study_dot_id'] for r in rows],[d.study_dot_id for d in source])
   for i,j in combinations(range(40),2):
    self.assertAlmostEqual(rows[j]['paper_x_mm']-rows[i]['paper_x_mm'],source[j].local_x_mm-source[i].local_x_mm)
    self.assertAlmostEqual(rows[j]['paper_y_mm']-rows[i]['paper_y_mm'],source[j].local_y_mm-source[i].local_y_mm)
 def test_requested_quadrant_geometry_and_conditions(self):
  for q,c in self.cfg['conditions'].items():
   rows=[r for r in self.plan['rows'] if r['quadrant']==q];low,hi=c['allowed_centers_xy_mm']
   for r in rows:self.assertTrue(low[0]<=r['paper_x_mm']<=hi[0] and low[1]<=r['paper_y_mm']<=hi[1])
   self.assertAlmostEqual((min(r['paper_x_mm'] for r in rows)+max(r['paper_x_mm'] for r in rows))/2,c['center_mm'][0])
   self.assertAlmostEqual((min(r['paper_y_mm'] for r in rows)+max(r['paper_y_mm'] for r in rows))/2,c['center_mm'][1])
   self.assertEqual((c['compression_depth_mm'],c['dwell_at_depth_s']),{'Q1':(4,.5),'Q2':(3,.5),'Q3':(3,1),'Q4':(4,1)}[q])
 def test_same_bottom_up_right_first_serpentine(self):
  for q in ORDER:
   rows=[r for r in self.plan['rows'] if r['quadrant']==q];ys=[r['paper_y_mm'] for r in rows];self.assertEqual(ys,sorted(ys))
   by_y={}
   for r in rows:by_y.setdefault(r['paper_y_mm'],[]).append(r['paper_x_mm'])
   for rank,xs in enumerate(by_y.values()):self.assertEqual(xs,sorted(xs,reverse=not bool(rank%2)))
 def test_contacts_loads_and_initial_preparation(self):
  r=readback(self.text,self.plan,self.p,self.cs);self.assertEqual(r['contact_count'],160);self.assertEqual(r['pigment_loads'],8);self.assertEqual(r['condition_preparations'],4)
  self.assertEqual(sum(c.action=='pigment_load' for c in self.cs),4);self.assertEqual(sum(c.action=='same_color_reload' for c in self.cs),4);self.assertEqual(sum(c.action=='full_wash' for c in self.cs),4)
 def test_same_preparation_geometry_for_all_conditions(self):
  geometries=[]
  for q in ORDER:
   start=next(i for i,c in enumerate(self.cs) if c.action=='flat_preparation_begin' and c.message==q);end=next(i for i,c in enumerate(self.cs) if c.action=='flat_preparation_complete' and c.message==q)
   subset=self.cs[start:end];geometries.append([(c.action,c.xyz,c.feed_mm_min,c.seconds) for c in subset if c.action.startswith('station_') or c.kind=='dwell'])
  self.assertTrue(all(g==geometries[0] for g in geometries))
 def test_preparation_after_first_water_is_identical_fresh_wet_travel(self):
  suffixes=[]
  for q in ORDER:
   start=next(i for i,c in enumerate(self.cs) if c.action=='flat_preparation_begin' and c.message==q);end=next(i for i,c in enumerate(self.cs) if c.action=='flat_preparation_complete' and c.message==q)
   region=self.cs[start:end];water_done=next(i for i,c in enumerate(region) if c.action=='wash')
   suffixes.append([(c.kind,c.xyz,c.feed_mm_min,c.seconds,c.travel_state) for c in region[water_done+1:] if c.kind in ('move','dwell')])
  self.assertTrue(all(s==suffixes[0] for s in suffixes))
 def test_refill_after_retract20_before21_no_wash_or_extra40(self):
  for q in ORDER:
   rows=[r for r in self.plan['rows'] if r['quadrant']==q]
   start=next(i for i,c in enumerate(self.cs) if c.action=='flat_dot_complete' and c.source_id==rows[19]['experiment_contact_id']);end=next(i for i,c in enumerate(self.cs) if c.action=='flat_dot_begin' and c.source_id==rows[20]['experiment_contact_id'])
   self.assertEqual(sum(c.action=='same_color_reload' for c in self.cs[start+1:end]),1)
   self.assertFalse(any(c.action=='full_wash' for c in self.cs[start+1:end]))
   before=self.cs[start-1];self.assertEqual(before.action,'retract');self.assertEqual(before.xyz[2],20)
 def test_flat_Z_replaces_relief_Z_and_depth_dwell(self):
  self.assertGreater(len({r['source_z_design_mm_REFERENCE_ONLY'] for r in self.plan['rows']}),5)
  for r in self.plan['rows']:
   self.assertEqual(r['flat_first_touch_g54_z_mm'],10);self.assertEqual(r['press_g54_z_mm'],6 if r['quadrant'] in ('Q1','Q4') else 7)
  r=readback(self.text,self.plan,self.p,self.cs);self.assertEqual(r['at_depth_dwell_s'],120)
  self.assertEqual(sum(c.seconds for c in self.cs if c.action=='flat_dot_dwell'),120)
 def test_serialized_half_and_full_seconds_tamper_rejected(self):
  self.assertIn('G4 P0.500000000',self.text);self.assertIn('G4 P1.000000000',self.text)
  bad=self.text.replace('G4 P0.500000000','G4 P1.000000000',1)
  with self.assertRaises(ValueError):readback(bad,self.plan,self.p,self.cs)
 def test_point_xy_fixed_no_artistic_pressure_or_guide_draw(self):
  for row in self.plan['rows']:
   group=[c for c in self.cs if c.source_id==row['experiment_contact_id'] and c.kind=='move']
   self.assertTrue(all(c.xyz[:2]==(row['g54_x_mm'],row['g54_y_mm']) for c in group))
  self.assertFalse(any(c.artistic_pressure is not None or c.action=='draw' for c in self.cs));self.assertEqual(self.text.count('\nM2\n'),1);self.assertNotIn('\nM0\n',self.text)
 def test_experiment_namespace_cannot_complete_artwork(self):
  ids=[r['experiment_contact_id'] for r in self.plan['rows']];self.assertEqual(len(ids),len(set(ids)));self.assertTrue(all(i.startswith(NAMESPACE+':') for i in ids))
  self.assertFalse(self.plan['artwork_completion_eligible']);self.assertTrue(all(not r['artwork_completion_eligible'] for r in self.plan['rows']))
  with self.assertRaises(ValueError):remaining(standard_plans()[4],self.plan,{})
 def test_all_individual_jobs_independent_with_same_positions(self):
  for q in ORDER:
   plan=make_plan([q]);p,c=build(plan);r=readback(serialize(plan,p,c),plan,p,c)
   self.assertEqual((r['contact_count'],r['pigment_loads'],r['condition_preparations'],r['terminal_cleanup_count']),(40,2,1,1))
   self.assertEqual(r['start_G54_xyz'],[0,900,35]);self.assertEqual(r['end_G54_xyz'],[800,800,35])
   self.assertEqual(plan['rows'],[{**r,'condition_execution_rank':1,'execution_sequence':r['sequence_in_condition']} for r in self.plan['rows'] if r['quadrant']==q])
 def test_terminal_cleanup_once_without_final_rewet(self):
  self.assertEqual(sum(c.action=='terminal_cleanup_begin' for c in self.cs),1)
  tail=self.cs[next(i for i,c in enumerate(self.cs) if c.action=='terminal_cleanup_begin'):]
  self.assertEqual([c.seconds for c in tail if c.kind=='dwell'],[10,10,10,4,4]);self.assertFalse(any(c.action in ('controlled_rewet','pigment_load') for c in tail))
 def test_mount_translation_does_not_move_stations(self):
  cfg=deepcopy(self.cfg);cfg['registration']['paper_lower_left_g54_xy_mm']=[12,19];plan=make_plan(cfg=cfg);p,c=build(plan)
  station=lambda commands:[(c.xyz,c.feed_mm_min) for c in commands if c.action.startswith('station_')]
  self.assertEqual(station(c),station(self.cs))
  for a,b in zip(plan['rows'],self.plan['rows']):self.assertAlmostEqual(a['g54_x_mm']-b['g54_x_mm'],12);self.assertAlmostEqual(a['g54_y_mm']-b['g54_y_mm'],19)
 def test_original_stations_and_motion_unchanged(self):
  original=Profile.load(PROFILE_PATH)
  self.assertEqual(self.p.data['stations'],original.data['stations'])
  for key in ['machine_bounds_xyz','axis_max_rate_mm_min','axis_acceleration_mm_s2','g54_to_machine_xyz']:self.assertEqual(self.p.data['machine'][key],original.data['machine'][key])
  for key in ['ordinary_travel_mm_min','partially_depleted_mm_min','wet_loaded_mm_min','segmented_travel','z_travel_mm_min','paper_contact_mm_min','paper_release_mm_min']:self.assertEqual(self.p.data['motion'][key],original.data['motion'][key])
 def test_nonfinite_and_out_of_bounds_rejected(self):
  for key,val in [('flat_first_touch_g54_z_mm',float('nan')),('paper_hover_g54_z_mm',36),('paper_approach_g54_z_mm',9)]:
   d=deepcopy(self.cfg);d['registration'][key]=val
   with tempfile.TemporaryDirectory() as tmp:
    f=Path(tmp)/'c.json';f.write_text(json.dumps(d))
    with self.assertRaises(ValueError):config(f)
  d=deepcopy(self.cfg);d['registration']['paper_lower_left_g54_xy_mm']=[1000,0]
  with self.assertRaises(ValueError):build(make_plan(cfg=d))
  with self.assertRaises(ValueError):make_plan([])
 def test_used_brush_state_works_at_zero_distance(self):
  b=RuntimeBuilder(self.p);m=ComparisonMaterials(b,20);m.load('C2');m.complete_contact();self.assertEqual(m.distance,0);self.assertEqual(m.station_travel_state(),'partially_depleted')
  before=len(b.commands);m.wash();self.assertEqual(next(c.travel_state for c in b.commands[before:] if c.action=='travel'),'partially_depleted')
 def test_depth_dwell_timing_not_consumed_by_descent(self):
  model=timing(self.cs,self.p);self.assertEqual(model['acceleration_sensitive_seconds_by_category']['depth_dwell'],120);self.assertGreater(model['acceleration_sensitive_seconds'],120)

if __name__=='__main__':unittest.main()
