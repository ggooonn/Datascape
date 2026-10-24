"""Append a checked terminal wash/purge to frozen Spring numeric reviews.

The complete painting prefix is retained; no running stream is modified.
Standalone cleanup starts only from the previous job's verified final park.
"""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from math import dist
import argparse
import gzip
import hashlib
import json

from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.exporter import _serialize, _MOVE, _DWELL
from .spring_runtime import RuntimeBuilder, RuntimeMaterials
from .spring_large_baegunmo import project_air, runtime
from .numeric_review import BANNER, check_move

POLICY = dict(water_visits=3, immersion_dwell_seconds=10, agitation_cycles=3,
              sponge_repetitions=2, sponge_dwell_seconds=4, final_rewet=False)
PARK = (800,800,35)


def cleanup(profile, medium, air=False):
    d=deepcopy(profile.data)
    d['profile_id']+='-TERMINAL-CLEANUP-'+medium.upper()
    d['machine']['start_work_xyz']=list(PARK)
    d['stations']['water'].update(dwell_seconds=POLICY['immersion_dwell_seconds'],
                                   agitation_cycles=POLICY['agitation_cycles'])
    d['stations']['sponge'].update(repetitions=POLICY['sponge_repetitions'],
                                    dwell_seconds=POLICY['sponge_dwell_seconds'])
    p=Profile.from_dict(d);b=RuntimeBuilder(p);m=RuntimeMaterials(b)
    loaded='ink' if medium=='ink' else p.data['material']['color_order'][-1]
    m.loaded=loaded;m.distance=1
    b.marker('terminal_cleanup_begin')
    for _ in range(POLICY['water_visits']):
        m.station('water','wash');m.loaded='water'
    m.station('sponge','absorbent_contact',loaded)
    b.park('partially_depleted');b.marker('terminal_cleanup_complete')
    commands=project_air(b.commands,p,{}) if air else b.commands
    return p,commands


def numeric_audit(text,start,p):
    rows=[s for s in text.splitlines() if s and not s.startswith(';')]
    if rows[0]!='G21 G90 G94 G54' or rows[-1]!='M2':raise ValueError('bad modal/end')
    pos=tuple(start);moves=0
    for row in rows[1:-1]:
        if m:=_MOVE.fullmatch(row):
            x,y,z,f=map(float,m.groups());q=(x,y,z)
            check_move(pos,q,f,'station_cleanup',p,'paint',exact_benchmark_draw=False)
            length=dist(pos,q)
            if length and any(abs(a-b)/length*f>cap+1e-6 for a,b,cap in zip(pos,q,p.data['machine']['axis_max_rate_mm_min'])):
                raise ValueError('axis rate exceeded')
            pos=q;moves+=1
        elif not _DWELL.fullmatch(row):raise ValueError('unexpected command: '+row)
    if pos!=PARK:raise ValueError('final park mismatch')
    return dict(numeric_bounds_feeds_verified=True,moves=moves,M0_count=0,M2_verified=True,final_park=list(pos))


def generate(base,out):
    base=Path(base);out=Path(out);out.mkdir(exist_ok=False)
    profile=Profile.load(base/'profile.spring.large_baegunmo.json')
    prior=json.loads((base/'verification.json').read_text());report=dict(policy=POLICY,
        baseline_profile_sha256=profile.sha256,ink_reload_mm=1100,color_reload_mm=700,
        artwork_or_pressure_or_order_changed=False,machine_authorized=False,jobs={})
    for job,medium,air in [('SHARED_INK','ink',False),('SHARED_COLOR','color',False),('SPRING_AIR','color',True)]:
        original=(base/(job+'_REVIEW.gcode')).read_bytes()
        if hashlib.sha256(original).hexdigest()!=prior['jobs'][job]['gcode_sha256']:raise ValueError('baseline SHA mismatch')
        p,commands=cleanup(profile,medium,air)
        tail=BANNER+_serialize(commands,p,'TERMINAL-CLEANUP',job+'_CLEANUP','offline_review')
        checked=numeric_audit(tail,PARK,p)
        # Tail starts at the baseline's final park, with no embedded homing or offset changes.
        lines=tail.splitlines();body=lines[lines.index('G21 G90 G94 G54')+1:]
        prefix=original.decode().removesuffix('M2\n')
        if prefix==original.decode():raise ValueError('baseline termination mismatch')
        full=prefix+'; TERMINAL CLEANUP PROFILE '+p.sha256+'\n'+'\n'.join(body)+'\n'
        assert full.encode().startswith(prefix.encode())
        total=numeric_audit(full,profile.data['machine']['start_work_xyz'],profile)
        name=job+'_END_CLEANUP_REVIEW.gcode'
        (out/name).write_text(full);(out/(name+'.gz')).write_bytes(gzip.compress(full.encode(),mtime=0))
        clean_name=('END_CLEANUP_AIR' if air else 'END_CLEANUP_'+medium.upper()+'_FROM_PARK')+'.gcode'
        (out/clean_name).write_text(tail)
        (out/('profile.cleanup.'+('air' if air else medium)+'.json')).write_text(json.dumps(p.data,indent=2)+'\n')
        service=[c.action for c in commands if c.kind=='marker' and c.action in ('wash','absorbent_contact','controlled_rewet','pigment_load')]
        if service!=['wash']*3+['absorbent_contact']:raise ValueError('terminal operation order')
        if not air:
            assert sum(c.travel_phase=='lip_strip' for c in commands)==3
            assert sum(c.kind=='dwell' and c.action=='absorbent_contact_dwell' for c in commands)==2
        else:assert all(c.xyz[2]==35 for c in commands if c.kind=='move')
        model=runtime(commands,p)['models']['configuration_reference']
        report['jobs'][job]=dict(**total,baseline_gcode_sha256=hashlib.sha256(original).hexdigest(),
            baseline_prefix_sha256=hashlib.sha256(prefix.encode()).hexdigest(),baseline_prefix_preserved_verbatim=True,
            gcode_sha256=hashlib.sha256(full.encode()).hexdigest(),cleanup_sha256=hashlib.sha256(tail.encode()).hexdigest(),
            cleanup_filename=clean_name,filename=name,source_readback=prior['jobs'][job],
            terminal_order=service,cleanup_estimated_seconds=model['acceleration_sensitive_seconds'],
            standalone_start=list(PARK),tail_audit=checked)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'README.md').write_text('''# Spring terminal cleanup review

Selected reloads remain ink1100/color700. Painting prefixes are preserved byte-for-byte except removal of their final M2; cleanup is appended after the previous final park, then the machine parks again and terminates with M2.
Terminal routine: three water visits, each10s dwell/three agitation cycles with existing shallow wipe/lip; sponge twice4s, then Z35/park/M2. No final rewet or pigment load. Contact XYZ/feed/depth are unchanged; intermediate color-change routines are unchanged.
Standalone END_CLEANUP_INK_FROM_PARK / COLOR_FROM_PARK files require the PREVIOUS job to have completed at G54 X800 Y800 Z35, with registration preserved. Do not run concurrently, from post-home, or from an interrupted/unknown position. Full files independently start0/900/35.
AIR includes noncontact terminal XY at35. No hardware was operated. Cleanliness is not certified; existing execution gates remain.
''')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    (out/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();r=generate(a.base,a.output)
    print(json.dumps({k:dict(cleanup_seconds=v['cleanup_estimated_seconds'],sha256=v['gcode_sha256']) for k,v in r['jobs'].items()}))
