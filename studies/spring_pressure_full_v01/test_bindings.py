"""Positive and mutation-rejection binding checks; no source file writes."""
from pathlib import Path
from unittest.mock import patch
import argparse,json
import bindings as b

def verify(snapshot,pressure_file):
 snap=Path(snapshot);file=Path(pressure_file);positive=b.load_bound_pressure(snap,file);assert len(positive)==14951 and sum(map(len,positive.values()))==240974
 original_read=b.read;ink=original_read(snap/'visible_ink.json.gz');data=original_read(file);results={'all_IDs_and_vertices_bind':True}
 for kind in ['changed_XY','changed_width','reordered_pressure','missing_pressure_record','out_of_family_range']:
  local_ink=dict(ink);local_ink['strokes']=list(ink['strokes']);local_data=dict(data);local_data['strokes']=list(data['strokes'])
  if kind in ['changed_XY','changed_width']:
   r=dict(ink['strokes'][0]);local_ink['strokes'][0]=r
   if kind=='changed_XY':r['xy_mm']=[list(p) for p in r['xy_mm']];r['xy_mm'][0][0]+=.001
   else:r['width_mm']+=.001
  elif kind=='reordered_pressure':local_data['strokes'][0],local_data['strokes'][1]=local_data['strokes'][1],local_data['strokes'][0]
  elif kind=='missing_pressure_record':local_data['strokes']=local_data['strokes'][:-1]
  else:
   r=dict(data['strokes'][0]);r['pressure_intent_samples']=list(r['pressure_intent_samples']);r['pressure_intent_samples'][0]=.99;local_data['strokes'][0]=r
  def fake(path):
   path=Path(path)
   if path==file:return local_data
   if path==snap/'visible_ink.json.gz':return local_ink
   return original_read(path)
  with patch.object(b,'read',side_effect=fake):
   try:b.load_bound_pressure(snap,file)
   except AssertionError:results[kind+'_rejected']=True
   else:raise AssertionError('Binder did not reject '+kind)
 return results

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--pressure',type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.snapshot,a.pressure),indent=2))
