"""Verify delivered review artifacts without granting physical readiness."""
import argparse,gzip,hashlib,json,re
from pathlib import Path
from datascape.gcode.production.trajectory import Command
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.exporter import verify_draw_lineage
from datascape.gcode.production.sequence import verify_plan,reference_order
from datascape.gcode.production.costs import audit_continuity
from datascape.gcode.binding import load_bound_spring,digest
from datascape.gcode.layout import Layout


def verify(root,strokes=None):
    root=Path(root);manifest=json.loads((root/'MANIFEST_SHA256.json').read_text())
    for name,expected in manifest.items():
        p=root/name
        if not p.resolve().is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('review artifact hash mismatch: '+name)
    if list(root.rglob('*.nc')):raise ValueError('review package must not contain executable .nc')
    profile=Profile.load(root/'profile.provisional.json')
    context=json.loads((root/'REVIEW_CONTEXT.json').read_text())
    if context['authorized'] is not False or context['clearance_verified'] is not False or profile.data['motion']['local_hover']['enabled'] is not False:
        raise ValueError('offline review must not claim authorization or enabled physical local hover')
    plan=json.loads(gzip.decompress((root/'D.plan.json.gz').read_bytes()))
    result={'authorized':False,'physical_readiness_verified':False,'file_hashes_verified':len(manifest),'jobs':{}}
    if strokes is not None:
        result['source_plan']=verify_plan(plan,strokes,Layout('D'))
        order=reference_order(strokes,Path(__file__).resolve().parents[2]/'config/plotter_v03/spring_s3a_order.json')
        rank={strokes[i].stroke_id:n for n,i in enumerate(order)}
        for mode in ('D','A'):
            candidate=json.loads(gzip.decompress((root/(mode+'.plan.json.gz')).read_bytes()))
            verify_plan(candidate,strokes,Layout(mode))
            for units in candidate['jobs'].values():
                ids=[u['source_id'] for u in units]
                if ids!=sorted(set(ids),key=rank.__getitem__):raise ValueError('written job does not retain exact source-atomic S3a order')
        result['A_and_D_source_atomic_S3a_order_verified']=True
    for name in ('SHARED_INK','SHARED_COLOR'):
        with gzip.open(root/(name+'.trajectory.jsonl.gz'),'rt',encoding='utf-8') as f:
            commands=[Command(**dict(c,xyz=None if c.get('xyz') is None else tuple(c['xyz']))) for c in map(json.loads,f)]
        lineage=verify_draw_lineage(commands,plan['jobs'][name],profile,'fixture')
        crossing={u['source_id'] for u in plan['jobs'][name]
                  if min(p['x'] for p in u['fragments'][0]['stroke']['points'])<300<max(p['x'] for p in u['fragments'][0]['stroke']['points'])}
        continuity=audit_continuity(commands,crossing)
        text=gzip.decompress((root/(name+'.preview.txt.gz')).read_bytes()).decode().splitlines()
        if any(line not in text for line in ('; PROFILE '+profile.sha256,'; PLAN '+digest(plan),'; JOB '+name)):
            raise ValueError('preview profile, plan or job binding mismatch')
        if '; HYPOTHETICAL_POLICY '+json.dumps(context,sort_keys=True) not in text:raise ValueError('missing review override disclosure')
        if any(not s.startswith(';') for s in text) or text[-1]!='; M2':raise ValueError('uncommented review line or lost M2')
        samples=[json.loads(s[9:]) for s in text if s.startswith('; SAMPLE ')]
        if samples!=[{'source':c.source_id,'fragment':c.fragment_id,'vertex':c.source_vertex,'pressure':c.artistic_pressure} for c in commands if c.artistic_pressure is not None]:raise ValueError('sample provenance mismatch')
        moves=[s for s in text if s.startswith('; G1 ')];expected=[c for c in commands if c.kind=='move']
        if len(moves)!=len(expected):raise ValueError('lost preview motion')
        for row,c in zip(moves,expected):
            values=[float(x[1:]) for x in row[5:].split()]
            if any(abs(a-b)>5.1e-10 for a,b in zip(values,[*c.xyz,c.feed_mm_min])):raise ValueError('preview G54/feed mismatch')
        if expected[-1].xyz!=(800,900,32):raise ValueError('park target changed')
        if any(re.fullmatch(r';\s*M0\s*',s) for s in text):raise ValueError('routine pause in review')
        actual_unknown=[c.action+' '+c.message for c in commands if c.kind=='unresolved']
        if [s[len('; UNRESOLVED '):] for s in text if s.startswith('; UNRESOLVED ')]!=actual_unknown:raise ValueError('symbolic station operation changed')
        result['jobs'][name]={'source_samples':lineage,'D_continuity':continuity,'all_preview_lines_commented':True,'unresolved_operations_preserved':len(actual_unknown),'M0_count':0,'commented_M2':True}
        del commands
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',required=True,type=Path)
    p.add_argument('--machine',type=Path);p.add_argument('--provenance',type=Path);a=p.parse_args()
    if bool(a.machine)!=bool(a.provenance):raise ValueError('supply both accepted input paths')
    strokes=None if a.machine is None else load_bound_spring(a.machine,a.provenance)[0]
    print(json.dumps(verify(a.package,strokes),indent=2))
