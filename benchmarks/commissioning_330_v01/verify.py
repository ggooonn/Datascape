"""Independently verify a delivered offline package without granting readiness."""
import argparse,json,hashlib
from pathlib import Path
from dataclasses import asdict
from datascape.gcode.binding import digest
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.benchmark import air_plan
from .preview import calibration_review,air_review,verify_review


def verify(root):
    root=Path(root);hashes=json.loads((root/'MANIFEST_SHA256.json').read_text())
    for name,expected in hashes.items():
        f=root/name
        if not f.resolve().is_relative_to(root.resolve()) or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:raise ValueError('artifact hash/path mismatch: '+name)
    actual={str(f.relative_to(root)) for f in root.rglob('*') if f.is_file() and f.name!='MANIFEST_SHA256.json'}
    if set(hashes)!=actual:raise ValueError('unmanifested package artifact')
    if list(root.rglob('*.nc')):raise ValueError('offline commissioning review may not contain executable .nc')
    p=Profile.load(root/'profile.provisional.json');s=json.loads((root/'summary.json').read_text())
    if s['authorized'] is not False or s['executable_files_delivered']!=0 or p.data['evidence']:raise ValueError('offline package must not manufacture authorization/evidence')
    results={}
    for name,row in s['stages'].items():
        request=json.loads((root/'plans'/(name+'.json')).read_text());is_air=name.startswith('A_')
        commands=air_review(request,p) if is_air else calibration_review(request,p)
        if digest(json.loads((root/'previews'/(name+'.trajectory.json')).read_text()))!=digest([asdict(c) for c in commands]):raise ValueError('review IR differs from request')
        r=verify_review(root/'previews'/(name+'.preview.txt'),commands,p,request)
        if r!=row['readback']:raise ValueError('delivered read-back report differs')
        if is_air and any(c.kind=='move' and c.xyz[2]<p.data['motion']['paper_hover_mm'] for c in commands):raise ValueError('Air preview contains contact')
        if any(c.kind=='move' and c.action=='travel' and c.xyz[2]<=0 for c in commands):raise ValueError('lateral travel at paper contact')
        last=next(c for c in reversed(commands) if c.kind=='move')
        if tuple(last.xyz)!=(800,800,32):raise ValueError('commissioning park changed')
        expected_hash=digest(air_plan(request)[2]) if is_air else digest(request)
        if expected_hash!=row['plan_sha256']:raise ValueError('stage plan hash differs')
        a=json.loads((root/'authorization_templates'/(name+'.UNAUTHORIZED.json')).read_text())
        if a['explicit_operator_authorization'] is not False or a['profile_sha256']!=p.sha256 or a['plan_sha256']!=expected_hash:raise ValueError('authorization template must remain unapproved and correctly bound')
        results[name]={'all_lines_commented':True,'M0_count':r['M0_count'],'unresolved_operations':r['unresolved_operations'],'request_IR_G54_feed_verified':True}
    return {'file_hashes_verified':len(hashes),'stages_verified':results,'physically_ready':False,'authorized':False,'executable_files':0,'hardware_executed':False}


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--package',type=Path,required=True)
    print(json.dumps(verify(a.parse_args().package),indent=2))
