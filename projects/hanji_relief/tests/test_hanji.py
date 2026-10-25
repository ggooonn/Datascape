"""Meaningful contact-budget, source, coordinate, material and readback regressions."""
import unittest,tempfile,json,hashlib
from pathlib import Path
from copy import deepcopy
from collections import Counter
from dataclasses import replace
from projects.hanji_relief.data import *
from projects.hanji_relief.plan import *
from projects.hanji_relief.motion import *

class HanjiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # Keep the original 20-contact regression fixture independently reproducible.
  cls.dots=load_dots();cls.cfg=settings(PROJECT/'review/nominal_offset0/settings.json');cls.scenario=load_json(PROJECT/'config/review.nominal_offset0.json');cls.main=standard_plans(cls.dots,cls.cfg);cls.test=c4_test(cls.dots,cls.cfg)
  cls.p,cls.cmds,cls.rows,cls.services=build_paint(cls.test,cls.scenario)
 def test_counts_and_exact_panel_union(self):
  self.assertEqual(self.main[0]['dot_count'],6200);self.assertEqual(self.main[4]['dot_count'],890)
  self.assertEqual(Counter(int(d['study_dot_id']) for p in self.main[1:] for d in p['dots']),Counter(d.study_dot_id for d in self.dots))
  self.assertEqual((self.main[0]['loads'],self.main[0]['same_color_reloads'],self.main[0]['color_changes']),(313,305,7))
  self.assertEqual((self.main[4]['loads'],self.main[4]['same_color_reloads'],self.main[4]['color_changes']),(47,41,5))
 def test_source_hashes_and_original_columns_preserved(self):
  for name,sha in load_json(PROJECT/'provenance/source_hashes.json').items():self.assertEqual(hashlib.sha256((PROJECT/'input'/name).read_bytes()).hexdigest(),sha)
  ids={d.study_dot_id:d for d in self.dots}
  for r in self.main[0]['dots']:
   for k,v in ids[int(r['study_dot_id'])].original.items():self.assertEqual(r[k],v)
 def test_local_origin_and_design_z_not_renormalized(self):
  p=self.main[4];self.assertEqual(p['source_panel_id'],4)
  for r in p['dots']:
   self.assertEqual(r['artwork_x_mm'],float(r['local_x_mm']));self.assertEqual(r['artwork_y_mm'],float(r['local_y_mm']))
   self.assertAlmostEqual(float(r['global_y_mm']),float(r['local_y_mm'])+200)
  self.assertGreater(min(float(r['local_y_mm']) for r in p['dots']),0)
  self.assertAlmostEqual(min(float(r['z_design_mm']) for r in p['dots']),3.995497)
 def test_color_groups_bottom_up_right_first(self):
  for p in self.main:
   groups=[]
   for r in p['dots']:
    if not groups or groups[-1]!=r['color_id']:groups.append(r['color_id'])
   self.assertEqual(groups,p['used_color_order'])
   for c in p['used_color_order']:
    rs=[r for r in p['dots'] if r['color_id']==c];ys=[r['artwork_y_mm'] for r in rs];self.assertEqual(ys,sorted(ys))
    rows={}
    for r in rs:rows.setdefault(r['artwork_y_mm'],[]).append(r['artwork_x_mm'])
    for rank,xs in enumerate(rows.values()):self.assertEqual(xs,sorted(xs,reverse=not bool(rank%2)))
 def test_left_start_is_configurable_without_moving_points(self):
  cfg=deepcopy(self.cfg);cfg['first_row_start']='left';p=standard_plans(self.dots,cfg)[4]
  self.assertEqual({r['study_dot_id'] for r in p['dots']},{r['study_dot_id'] for r in self.main[4]['dots']})
  rs=[r for r in p['dots'] if r['color_id']=='C2'];y=rs[0]['artwork_y_mm'];xs=[r['artwork_x_mm'] for r in rs if r['artwork_y_mm']==y];self.assertEqual(xs,sorted(xs))
 def test_contact_boundaries(self):
  candidates=[d for d in self.dots if d.color_id=='C2']
  for n in (0,1,19,20,21,40,41):
   with self.subTest(n=n):
    p=make_plan(candidates[:n],'TEST','global',config=self.cfg)
    self.assertEqual(p['loads'],(n+19)//20)
    expected=[1]+([21] if n>=21 else [])+([41] if n>=41 else []) if n else []
    self.assertEqual([r['execution_sequence'] for r in p['dots'] if r['service_before']],expected)
 def test_color_end_multiple_20_no_redundant_load(self):
  a=[d for d in self.dots if d.color_id=='C2'][:20];b=[d for d in self.dots if d.color_id=='A4'][:1]
  p=make_plan(a+b,'TEST','global',config=self.cfg)
  self.assertEqual(p['dots'][20]['service_before'],'color_change');self.assertEqual(p['same_color_reloads'],0);self.assertEqual(p['loads'],2)
 def test_first40_c4_is_canonical_prefix(self):
  full=[r for r in self.main[4]['dots'] if r['color_id']=='C4']
  self.assertEqual([r['study_dot_id'] for r in self.test['dots']],[r['study_dot_id'] for r in full[:40]])
  self.assertEqual([s['before_sequence'] for s in self.services],[1,21])
 def test_explicit_dot_primitive_and_full_one_second(self):
  self.assertFalse(any(c.artistic_pressure is not None or c.action=='draw' for c in self.cmds))
  checked=readback(serialize(self.cmds,self.p,self.test,self.scenario),self.cmds,self.p,self.test,self.rows,self.services)
  self.assertEqual(checked['serialized_dot_dwell_s'],40)
  for r in self.rows:self.assertAlmostEqual(r['review_first_touch_z_mm']-r['review_press_z_mm'],3)
 def test_move_then_dwell_tamper_rejected(self):
  text=serialize(self.cmds,self.p,self.test,self.scenario).replace('G4 P1.000000000','G4 P0.500000000',1)
  with self.assertRaisesRegex(ValueError,'dwell'):readback(text,self.cmds,self.p,self.test,self.rows,self.services)
 def test_paper_xy_dither_rejected(self):
  cmds=list(self.cmds);i=next(i for i,c in enumerate(cmds) if c.action=='pressure_variation');c=cmds[i];cmds[i]=replace(c,xyz=(c.xyz[0]+.1,c.xyz[1],c.xyz[2]))
  with self.assertRaises(ValueError):readback(serialize(cmds,self.p,self.test,self.scenario),cmds,self.p,self.test,self.rows,self.services)
 def test_unused_unmeasured_registration_not_silently_zero(self):
  with self.assertRaises(ValueError):build_paint(self.test,load_json(PROJECT/'config/mounting.unmeasured.json'))
 def test_mount_offset_applied_once_stations_unchanged(self):
  s=deepcopy(self.scenario);s['individual_mount'].update(g54_x_mm=11,g54_y_mm=13,hanji_surface_offset_z_mm=2)
  p,cmd,rows,service=build_paint(self.test,s)
  for a,b in zip(rows,self.rows):self.assertAlmostEqual(a['review_press_z_mm']-b['review_press_z_mm'],2);self.assertAlmostEqual(a['g54_x_mm']-b['g54_x_mm'],11)
  station=lambda cs:[c.xyz for c in cs if c.action.startswith('station_')]
  self.assertEqual(station(cmd),station(self.cmds))
 def test_nan_and_invalid_configuration_rejected(self):
  for key,bad in [('dwell_at_depth_s',float('nan')),('compression_depth_mm',float('inf')),('dwell_at_depth_s',-1),('refill_every_contacts',0),('refill_every_contacts',20.5),('refill_every_contacts',True)]:
   cfg=deepcopy(self.cfg);cfg[key]=bad
   with tempfile.TemporaryDirectory() as d:
    f=Path(d)/'config.json';f.write_text(json.dumps(cfg))
    with self.assertRaises(ValueError):settings(f)
 def test_z_limit_and_approach_bound_rejected(self):
  for offset,hover in [(20,35),(0,36)]:
   s=deepcopy(self.scenario);s['individual_mount'].update(hanji_surface_offset_z_mm=offset,fixed_hover_g54_z_mm=hover)
   with self.assertRaises(ValueError):build_paint(self.test,s)
 def test_air_has_no_contacts_dwell_or_immersion(self):
  cs=project_air(self.p,self.cmds)
  self.assertTrue(all(c.xyz[2]==35 for c in cs if c.kind=='move'));self.assertFalse(any(c.kind=='dwell' for c in cs))
  checked=readback(serialize(cs,self.p,self.test,self.scenario,True),cs,self.p,self.test,self.rows,self.services,True)
  self.assertEqual(checked['serialized_paper_contact_events'],0);self.assertEqual(checked['physically_completed_contacts'],0)
 def test_counted_used_brush_does_not_invent_distance(self):
  b=RuntimeBuilder(self.p);m=DotMaterials(b,20);m.load('C4');m.complete_contact()
  self.assertEqual(m.distance,0);self.assertEqual(m.station_travel_state(),'partially_depleted')
  before=len(b.commands);m.wash();travel=next(c for c in b.commands[before:] if c.action=='travel')
  self.assertEqual(travel.travel_state,'partially_depleted');self.assertEqual(m.distance,0)
 def test_same_color_reload_no_wash_and_terminal_once(self):
  self.assertEqual(sum(c.action=='same_color_reload' for c in self.cmds),1);self.assertEqual(sum(c.action=='full_wash' for c in self.cmds),0)
  self.assertEqual(sum(c.action=='terminal_cleanup_begin' for c in self.cmds),1)
  tail=self.cmds[next(i for i,c in enumerate(self.cmds) if c.action=='terminal_cleanup_begin'):]
  self.assertEqual([c.seconds for c in tail if c.kind=='dwell'],[10,10,10,4,4]);self.assertFalse(any(c.action in ('controlled_rewet','pigment_load') for c in tail))
 def test_exact_850_continuation_requires_actual_same_condition_record(self):
  ids=[int(r['study_dot_id']) for r in self.test['dots']]
  record=dict(schema='hanji.physical_completion.v01',physically_completed=True,mode='paint',input_sha256=INPUT_SHA,registration_sha256=digest(self.scenario),physical_panel_id=4,operator='synthetic test only',date='not a physical result',record='unit fixture',compression_depth_mm=3.,dwell_at_depth_s=1.,completed_dot_ids=ids)
  p=remaining(self.main[4],record,self.scenario);self.assertEqual(p['dot_count'],850)
  self.assertFalse(set(ids)&{int(r['study_dot_id']) for r in p['dots']})
  self.assertEqual([r['study_dot_id'] for r in p['dots']],[r['study_dot_id'] for r in self.main[4]['dots'] if int(r['study_dot_id']) not in ids])
  for key,value in [('mode','air'),('physically_completed',False),('dwell_at_depth_s',.5),('completed_dot_ids',ids+ids[:1])]:
   r=deepcopy(record);r[key]=value
   with self.assertRaises(ValueError):remaining(self.main[4],r,self.scenario)
 def test_official_export_gates_still_block(self):
  with self.assertRaises(ValueError):require_physical_export(self.p,self.test,self.cmds,{})
 def test_backend_stations_preserved_and_start_not_cleanup_park(self):
  original=Profile.load(PROFILE_PATH)
  self.assertEqual(original.data['stations'],self.p.data['stations']);self.assertEqual(self.p.data['machine']['start_work_xyz'],[0,900,35])
  self.assertEqual(self.p.data['motion']['paper_contact_z_range'][1]>10,True)
 def test_timing_dwell_is_not_travel_time(self):
  t=timing(self.cmds,self.p);self.assertEqual(t['acceleration_sensitive_seconds_by_category']['dot_dwell'],40)
  self.assertGreater(t['acceleration_sensitive_seconds'],40)

if __name__=='__main__':unittest.main()
