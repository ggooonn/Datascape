"""Offline generation/verification only; no device transport."""
import argparse,json
from .benchmark import generate,verify
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output');p.add_argument('--verify');p.add_argument('--config');a=p.parse_args()
if bool(a.output)==bool(a.verify):p.error('choose --output NEW_DIR or --verify DIR')
r=verify(a.verify) if a.verify else generate(a.output,a.config)
print(json.dumps(r if a.verify else {k:{'contacts':v['readback']['contact_count'],'loads':v['readback']['pigment_loads'],'minutes':v['timing']['acceleration_sensitive_seconds']/60} for k,v in r['jobs'].items()},indent=2))
