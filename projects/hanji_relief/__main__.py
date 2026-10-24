"""Generate or verify offline reviews only; never connect to the controller."""
import argparse,json
from .export import generate,verify

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output');p.add_argument('--verify');p.add_argument('--scenario');p.add_argument('--settings');p.add_argument('--completed-record')
a=p.parse_args()
if bool(a.output)==bool(a.verify):p.error('choose --output NEW_DIR or --verify DIR')
r=verify(a.verify) if a.verify else generate(a.output,a.scenario,a.settings,a.completed_record)
print(json.dumps(r if a.verify else {k:{'dots':v['readback']['planned_dots'],'loads':v['loads'],'modeled_minutes':round(v['timing']['acceleration_sensitive_seconds']/60,2)} for k,v in r['jobs'].items()},indent=2))
