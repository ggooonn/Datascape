"""Summer near-ground refinement; preserve the pinned middle/far vectors."""
from common import *
OUT=ROOT/'docs/experiments/summer_foreground_v02'

def config():
    c=read(ROOT/'studies/summer_scene_v01/config.json');c.update(case='summer-v02',season='summer',panels=[3,4],ground=dict(support_radius_m=[165,130]))
    c['summer_progression'].update(foliage_vigor=[1.03,1.28],foliage_unit_count_scale=[1.03,1.22],stem_ratio=[.92,.88])
    recipes=[('left-bank',[108,779],[[-45,6,80,'U'],[-25,-5,118,'B'],[-4,-3,158,'P'],[21,2,133,'B'],[44,9,98,'B'],[53,15,58,'U']]),
        ('central-relay',[257,732],[[-21,2,78,'B'],[0,-4,120,'P'],[24,5,58,'U']]),
        ('right-grove',[442,795],[[-54,10,103,'B'],[-32,-1,142,'B'],[-9,-7,188,'B'],[15,-1,161,'P'],[39,8,132,'B'],[57,17,92,'B'],[62,24,53,'U']]),
        ('right-back',[526,705],[[-18,2,81,'P'],[3,-3,118,'B'],[24,9,54,'U']])]
    c['near_groups']=[dict(id='v02-'+k,center_mm=xy,members=members) for k,xy,members in recipes]
    c['rocks']=[dict(id='v02-'+name+'-formation',group='v02-'+name,target_mm=xy,width_mm=w,height_mm=h,major_count=n,support_dx_mm=dx,support_dy_mm=dy)
        for name,xy,w,h,n,dx,dy in [('left-bank',[108,779],164,53,3,0,18),('central-relay',[257,732],100,34,2,8,12),('right-grove',[442,795],196,64,4,0,20),('right-back',[526,705],88,29,2,0,13)]]
    return c

def run(master,veg,field_cache,baseline_fields,output=OUT):
    out=Path(output);out.mkdir(parents=True,exist_ok=True);c=config();scene=read(BASE/'C_east_scene.json')
    f=cache_fields(master,veg,scene,'summer',c['seed'],field_cache)
    c,contacts=supported_groups(f,c)
    with np.load(baseline_fields) as z:
        saved_phase=z['phase'];reference=saved_phase.astype(float)
    phase_binding=read(Path(__file__).with_name('reference_phase.json'))
    if saved_phase.shape!=(900,600) or hashlib.sha256(saved_phase.tobytes()).hexdigest()!=phase_binding['phase_array_sha256']:raise ValueError('Pinned Summer phase mismatch')
    print('New near A phase and source-related ground masses',flush=True)
    a,raw_a,ground_ledger,g,phase_field,solver=foreground(f,reference,contacts,c)
    oldink=read(BASE/'summer_ink.json.gz')['strokes'];oldcolor=read(BASE/'summer_color_intent.json.gz')['strokes'];oldsource=read(BASE/'authoring_sources.json.gz')['strokes']
    oldterrain=[r for r in oldink if r['layer'] in 'ABCD' and len(r['layer'])==1]
    locked_terrain,far_ledger=split_domain(oldterrain,f,near=False)
    near_bcd,_=split_domain([r for r in oldsource if r['layer'] in ['B','C','D']],f,near=True,prefix='summer-v02')
    near=a+near_bcd
    print('New terrain-supported tree and rock groups',flush=True)
    objects,color,notes=catalog(f,near,c)
    vfar=[r for r in oldink if r['layer']=='V' and r.get('source_object_depth_m',r.get('source_forward_m',0))>=1600]
    vnear=[deepcopy(r) for r in oldink if r['layer']=='V' and r not in vfar]
    cfar=[r for r in oldcolor if r.get('source_family')=='V' and r.get('source_object_depth_m',r.get('source_forward_m',0))>=1600]
    cnear=[deepcopy(r) for r in oldcolor if r.get('source_family')=='V' and r not in cfar]
    for r in vnear+cnear:r['id']='summer-v02/retained-near-growth/'+r['id']
    sources=oldsource+oldink+oldcolor+raw_a+near+[r for obj in objects for r in obj['records']]+vnear+color+cnear
    lookup={}
    for r in sources:
        if r['id'] in lookup and lookup[r['id']]['xy_mm']!=r['xy_mm']:raise ValueError('Conflicting same-ID geometry')
        lookup[r['id']]=r
    ink,col,visibility=prior.resolve(f,near,objects,vnear,color+cnear,c)
    fully_far=[r for r in oldterrain if np.min(sample(f['base']['depth_m'],resample(r['xy_mm'],1)))>=1600]+vfar
    locked=locked_terrain+vfar;ink=locked+ink;col=cfar+col
    diagnostics=dict(case=c['case'],baseline='f2d03a592aec0e43368557391696f3b4c940db69',Summer_camera_unchanged=True,Spring_unchanged=True,
        unchanged_full_middle_far_records=len(fully_far),unchanged_full_middle_far_sha256=digest(fully_far),
        locked_record_ids=[r['id'] for r in fully_far],frozen_color_ids=[r['id'] for r in cfar],
        original_terrain_far_intervals_sha256=digest(locked_terrain),foreground_solver=solver,
        ground_policy='Source-XYZ patches around measured mound supports, local relief and valley openings; monotone A phase plus connected occurrence; no mist edit',
        original_field_precision='Pinned 1 mm float32 phase snapshot; new field computation uses full source TIFF precision',
        no_production_Gcode=True,artistic_status='provisional-v02')
    publish(out,ink,col,list(lookup.values()),visibility,f,c,contacts,notes,diagnostics)
    gz(out/'ground_selection_ledger.json.gz',dict(entries=ground_ledger,far_domain_entries=far_ledger))
    buf=io.BytesIO();np.savez_compressed(buf,mass=g['mass'].astype('float32'),opening=g['opening'].astype('float32'),keep=g['keep'].astype('float32'),phase=phase_field.astype('float32'))
    (out/'ground_fields.npz').write_bytes(buf.getvalue())
    print('Summer checkpoint',len(ink),len(col),'paths',flush=True)
    return ink,col

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--master',required=True);p.add_argument('--vegetation',required=True);p.add_argument('--field-cache');p.add_argument('--baseline-fields',required=True);p.add_argument('--output',type=Path,default=OUT);a=p.parse_args();run(a.master,a.vegetation,a.field_cache,a.baseline_fields,a.output)
