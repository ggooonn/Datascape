"""Same unified profile -> existing canonical Spring prepare/export/verify CLI.

No artwork generation, fallback profile or fabricated commissioning evidence.
Input machine/provenance are the existing PR25 adapter outputs; binding rejects
any changed source geometry, pressure or canonical sequence metadata.
"""
import argparse
from pathlib import Path

from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import SLOT_ORDER
from datascape.gcode.production.__main__ import main as backend


def require_unified_profile(p):
    v=p.data['motion']
    expected=dict(ordinary_travel_mm_min=12000,wet_loaded_mm_min=9000,draw_mm_min=6000,
        z_travel_mm_min=7000,paper_approach_mm_min=7000,station_approach_mm_min=7000,paper_contact_mm_min=2000,
        paper_release_mm_min=2000,pressure_z_mm_min=2000,paper_hover_mm=15,
        station_clearance_mm=35,park_xyz=[800,800,35])
    if any(v.get(k)!=x for k,x in expected.items()) or v.get('local_hover',{}).get('enabled') is not False:
        raise ValueError('Spring must use unified benchmark motion profile, normalZ15/local disabled')
    if p.data['machine']['start_work_xyz']!=[0,898,35]:raise ValueError('Spring starts after rehoming, not at previous park')
    if tuple(p.data['material']['color_order'])!=SLOT_ORDER:raise ValueError('preserve canonical Spring12/S3a palette order')
    if p.data['material']['ink_reload_mm']!=1000 or p.data['material']['color_reload_mm']!=800:
        raise ValueError('preserve independent ink1000/color800 original-boundary reload')
    if any(p.data['material'][k] is not None for k in ('manual_refill_every_loads','water_change_every_washes')):
        raise ValueError('no routine refill/water M0 in Spring')
    if p.data['material']['end_cleanup'] is not False:raise ValueError('end cleanup remains optional, disabled')


def run(mode,machine,provenance,profile,output,authorization=None):
    require_unified_profile(Profile.load(profile))
    if mode not in ('prepare','air','ink','color'):raise ValueError('unknown Spring stage')
    root=Path(__file__).resolve().parents[2]
    args=['prepare' if mode=='prepare' else 'export','--machine',str(machine),
          '--provenance',str(provenance),'--s3a-order',str(root/'config/plotter_v03/spring_s3a_order.json'),
          '--profile',str(profile),'--layout','D','--output',str(output)]
    if mode!='prepare':
        if authorization is None:raise ValueError('explicit current-profile stage authorization required')
        args+=['--stage','air' if mode=='air' else 'painting','--authorization',str(authorization),'--extension','.gcode']
        if mode!='air':args+=['--jobs','SHARED_'+mode.upper()]
    status=backend(args)
    if status==0 and mode!='prepare':status=backend(['verify','--output',str(output)])
    return status


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('prepare','air','ink','color'),required=True)
    for name in ('machine','provenance','profile','output'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--authorization',type=Path)
    raise SystemExit(run(**vars(ap.parse_args())))
