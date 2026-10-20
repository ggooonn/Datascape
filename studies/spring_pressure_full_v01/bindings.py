"""Strict ID/vertex binding of provisional artistic intent; no machine conversion."""
import gzip,hashlib,json
from pathlib import Path

def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def load_bound_pressure(snapshot_directory,pressure_file):
 root=Path(snapshot_directory);data=read(pressure_file)
 assert data['schema']=='datascape.pressure_intent.v0.1' and not data['calibrated']
 assert data['baseline_commit']=='67ba146b1213644d40bc9dabed9d52024d2bbe58'
 config_path=Path(__file__).with_name('config.json');config=read(config_path)
 assert hashlib.sha256(config_path.read_bytes()).hexdigest()==data['config_sha256']
 rows=sum((read(root/f'visible_{m}.json.gz')['strokes'] for m in ['ink','color']),[])
 phases=read(root/'ordering.json')['phases']
 assert len(rows)==len(data['strokes'])==14951
 result={}
 for i,(r,p) in enumerate(zip(rows,data['strokes'])):
  assert p['stroke_id']==r['id'] and p['sequence']==i and r['id'] not in result
  assert p['source_record_sha256']==digest(r) and p['xy_sha256']==digest(r['xy_mm'])
  assert p['medium']==('color' if 'palette_slot' in r else 'ink') and p['layer']==r['layer']
  assert p['color_slot']==r.get('palette_slot','INK')
  phase=next(x for x in phases if x['start']<=i<x['start']+x['count'])
  assert p['order_group']==phase['order_group']
  assert p['width_profile_sha256']==digest({k:r[k] for k in ['width_mm','width_profile_mm','expression','expressive_width_intent'] if k in r})
  v=p['pressure_intent_samples'];assert len(v)==p['vertex_count']==len(r['xy_mm'])
  assert all(isinstance(x,(int,float)) and 0<x<1 for x in v)
  lo,hi=config['limits'][p['family']];assert all(lo<=x<=hi for x in v)
  assert p['pressure_origin']=='new_painterly_pressure_intent_v01'
  assert not p['reorderable'] and not p['reversible']
  result[r['id']]=list(v)
 return result
