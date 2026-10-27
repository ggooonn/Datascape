"""Independent TIFF-field and near-A replay, with a deliberately narrow claim."""
from shared import *
from recipes import config
from flow import release
from scenes import load_reference_phase,output_dir
import argparse

def run(master,vegetation):
    c=config('summer');scene=read(accepted.BASE/'C_east_scene.json');out=output_dir('summer')
    f=accepted.cache_fields(master,vegetation,scene,'summer',c['seed'],cache=None)
    recipe=next(r for r in c['flow_candidates'] if r['id']==c['selected_flow'])
    f,_,_=release(f,recipe)
    with np.load(out/'fields.npz') as z:
        equal={k:bool(np.array_equal(actual,z[k])) for k,actual in [('occupied',f['base']['occupied']),('depth',f['base']['depth_m'].astype('float32')),('retention',f['retention'].astype('float32'))]}
    if not all(equal.values()):raise ValueError('Independent TIFF-field replay differs')
    c=read(out/'config.json');contacts=read(out/'placement.json')['contacts']
    selected,raw,_,_,_,solver=accepted.foreground(f,load_reference_phase(),contacts,c)
    lookup={r['id']:r for r in read(out/'authoring_sources.json.gz')['strokes']}
    maximum=0.;checked=0
    for r in raw+selected:
        expected=lookup[r['id']]
        p=np.asarray(r['xy_mm']);q=np.asarray(expected['xy_mm'])
        if p.shape!=q.shape:raise ValueError('Replay vertex count differs')
        err=float(np.abs(p-q).max());maximum=max(maximum,err)
        if err>1e-7:raise ValueError('Near A source geometry replay differs')
        for key in ['width_profile_mm','opacity_profile']:
            if key in r and not np.allclose(r[key],expected[key],atol=1e-8,rtol=0):raise ValueError('Replay artistic profile differs')
        checked+=1
    result=dict(status='passed',independent_process=True,private_field_or_stage_cache_used=False,TIFF_hashes_verified=True,
        diagnostic_fields_equal=equal,raw_near_A_sources=len(raw),selected_near_A_proposals=len(selected),source_or_proposal_records_checked=checked,
        maximum_geometry_error_mm=maximum,near_phase_topology=portable(solver),full_scene_byte_identity_asserted=False,
        scope='Independent original-TIFF reconstruction of Summer fields and near-A sources/proposals. Does not independently rebuild every catalog, final visibility result, preview or Autumn/Winter scene.')
    save(ROOT/'docs/experiments/seasonal_composition_v03/reproduction.json',result);print('Independent field / A replay passed',checked,'records',flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--master',required=True);p.add_argument('--vegetation',required=True);a=p.parse_args();run(a.master,a.vegetation)
