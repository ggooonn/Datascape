"""Generate Summer v03 and actual provisional Autumn/Winter vectors."""
from shared import *
from recipes import config
from flow import release
import argparse

def output_dir(season):
    return ROOT/'docs/experiments'/('summer_composition_v03' if season=='summer' else season+'_composition_v01')

def stage_key(c,scene):
    code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py') if p.name in ['shared.py','flow.py','recipes.py','scenes.py']}
    return digest(dict(config=c,scene=scene,code=code))

def load_reference_phase():
    p=ROOT/'studies/seasonal_screen_v01/reference_phase.npz'
    with np.load(p) as z:reference=z['phase']
    binding=read(p.with_suffix('.json'))
    if reference.shape!=(900,600) or hashlib.sha256(reference.tobytes()).hexdigest()!=binding['phase_array_sha256']:
        raise ValueError('Pinned Summer phase binding failed')
    return reference.astype(float)

def inherited_growth(rows,case):
    """Separate retained far identities from regenerated middle stand IDs."""
    result=[]
    for original in rows:
        r=deepcopy(original)
        r['inherited_checkpoint_id']=r['id'];r['id']=case+'/inherited-far-growth/'+r['id']
        r['owner_id']=case+'/inherited-far-growth/'+r['owner_id']
        result.append(r)
    return result

def summer_terrain(f,c,reference):
    """Keep far source contours; re-transfer existing phase through new mist."""
    v2=ROOT/'docs/experiments/summer_foreground_v02'
    old=read(v2/'ink.json.gz')['strokes']
    oldterrain=[r for r in old if r['layer'] in ['A','B','C','D']]
    far,far_sources,far_ledger=clip_depth(oldterrain,f,3600,np.inf,c['case']+'/far-reference')
    raw,_=accepted.trace_phase(reference,f)
    mc=read(ROOT/'configs/scenes/seoul_spring_stroke_grammar_v03.json');mc['seed']=c['seed']
    raw_mid=[]
    for j,r in enumerate(raw):
        q=sample(f['base']['depth_m'],np.asarray(r['xy_mm']))
        if q.max()>=1600 and q.min()<=3600:
            rr=deepcopy(r);rr['id']=c['case']+'/middle-phase/'+str(j);raw_mid.append(rr)
    transferred=accepted.transfer(raw_mid,f,mc)
    middle,mid_sources,mid_ledger=clip_depth(transferred,f,1600,3600,c['case']+'/middle-domain')
    oldsources=read(accepted.BASE/'authoring_sources.json.gz')['strokes']
    bcd,bcd_sources,bcd_ledger=clip_depth([r for r in oldsources if r['layer'] in ['B','C','D']],f,0,3600,c['case']+'/structural-domain')
    return far+middle+bcd,far_sources+raw_mid+transferred+mid_sources+bcd_sources,far_ledger+mid_ledger+bcd_ledger,

def run(season,master,vegetation,cache_dir,preview=True):
    c=config(season);out=output_dir(season);out.mkdir(parents=True,exist_ok=True)
    cache_dir=Path(cache_dir);cache_dir.mkdir(parents=True,exist_ok=True)
    scene=read(accepted.BASE/(c['selected_view']+'_scene.json'))
    key=stage_key(c,scene);stage=cache_dir/(season+'.stage.pkl')
    fields_path=cache_dir/(season+'.fields.pkl')
    f=accepted.cache_fields(master,vegetation,scene,season,c['seed'],fields_path)
    chosen=next(r for r in c['flow_candidates'] if r['id']==c['selected_flow'])
    f,flow,flow_record=release(f,chosen)
    save(out/'requested_config.json',c);save(out/'scene.json',scene);save(out/'flow_review.json',flow_record)
    if stage.exists():
        with open(stage,'rb') as h:state=pickle.load(h)
        if state['key']!=key:raise ValueError('Stale stage cache; use a new cache directory after implementation changes')
        print('Read same-input source/catalog stage',season,flush=True)
    else:
        c,contacts=accepted.supported_groups(f,c)
        if season=='summer':
            reference=load_reference_phase()
            terrain,ancestors,domain_ledger=summer_terrain(f,c,reference)
            terrain_audit=dict(reference_phase_unchanged=True,far_geometry_source=PIN,far_domain_min_m=3600)
        else:
            print('Build native terrain for',season,flush=True)
            terrain_cache=cache_dir/(season+'.terrain.pkl')
            terrain_key=digest(dict(scene=scene,seed=c['seed'],flow=chosen,baseline=PIN,implementation=hashlib.sha256((Path(__file__).parent/'flow.py').read_bytes()).hexdigest()))
            if terrain_cache.exists():
                with open(terrain_cache,'rb') as h:tk,terrain,terrain_audit,reference=pickle.load(h)
                if tk!=terrain_key:raise ValueError('Stale terrain-stage cache')
            else:
                terrain,terrain_audit,reference=prior.terrain_vectors(f,master,c)
                temp=terrain_cache.with_suffix('.pending')
                with open(temp,'wb') as h:pickle.dump((terrain_key,terrain,terrain_audit,reference),h)
                temp.replace(terrain_cache)
            terrain,ancestors,domain_ledger=clip_depth(terrain,f,1600,np.inf,c['case']+'/middle-far-domain')
        print('Redistribute supported near A',season,flush=True)
        near,raw_a,ground_ledger,ground,new_phase,solver=accepted.foreground(f,reference,contacts,c)
        if season=='summer':
            # B/C/D below the middle boundary are already included above.
            pass
        else:
            # Reuse structural source candidates for the near domain. The
            # parent terrain generator has already selected B/C/D by role.
            with open(cache_dir/(season+'.terrain-reference.pkl'),'wb') as h:
                pickle.dump(dict(phase=reference,diagnostics=portable(terrain_audit)),h)
            # New-view near B/C/D are not borrowed from a different camera.
            base_candidates=[]
            for r in ancestors:
                if r['layer'] in ['B','C','D']:base_candidates.append(r)
            near_bcd,extra,extra_ledger=clip_depth(base_candidates,f,0,1600,c['case']+'/near-structure')
            near+=near_bcd;ancestors+=extra;domain_ledger+=extra_ledger
        terrain=near+terrain
        for r in terrain:r.setdefault('source_family',r['layer']);r.setdefault('medium','ink')
        print('Build larger shared-support catalogs',season,flush=True)
        objects,colors,notes=accepted.catalog(f,terrain,c)
        vi,vc,roots=accepted.mid_far(f,c)
        if season=='summer':
            oldink=read(ROOT/'docs/experiments/summer_foreground_v02/ink.json.gz')['strokes']
            oldcolor=read(ROOT/'docs/experiments/summer_foreground_v02/color_intent.json.gz')['strokes']
            # Preserve the already reviewed far-growth grammar at its source
            # sites; final near-object visibility is still resolved honestly.
            vi += inherited_growth([r for r in oldink if r['layer']=='V' and r.get('source_object_depth_m',0)>=3600],c['case'])
            vc += inherited_growth([r for r in oldcolor if r.get('source_family')=='V' and r.get('source_object_depth_m',0)>=3600],c['case'])
        colors+=vc
        state=dict(key=key,c=c,contacts=contacts,terrain=terrain,ancestors=ancestors,domain_ledger=domain_ledger,
            raw_a=raw_a,ground_ledger=ground_ledger,objects=objects,colors=colors,notes=notes,vegetation=vi,roots=roots,
            terrain_audit=portable(terrain_audit),near_solver=portable(solver),near_phase_sha256=hashlib.sha256(new_phase.tobytes()).hexdigest())
        tmp=stage.with_suffix('.pending')
        with open(tmp,'wb') as h:pickle.dump(state,h)
        tmp.replace(stage)
    c=state['c']
    ink,color,ledger=prior.resolve(f,state['terrain'],state['objects'],state['vegetation'],state['colors'],c)
    sources=state['ancestors']+state['raw_a']+state['terrain']+[r for o in state['objects'] for r in o['records']]+state['vegetation']+state['colors']
    placement=dict(contacts=state['contacts'],catalog=[dict(id=o['id'],kind=o['kind'],group=o.get('group'),site=o['site'],height_mm=o.get('height_mm'),catalog_local_rank=o.get('catalog_local_rank'),parent_mass_id=o.get('parent_mass_id')) for o in state['objects']],mid_far=state['roots'],rock_notes=state['notes'])
    generation=dict(case=c['case'],baseline=PIN,selected_view=c['selected_view'],camera=scene,flow=flow_record,
        terrain=state['terrain_audit'],near_solver=state['near_solver'],near_phase_sha256=state['near_phase_sha256'],
        Summer_camera_unchanged=season=='summer',Spring_modified=False,earlier_checkpoint_files_modified=False,
        far_micro_B_enabled=False,production_Gcode_generated=False,artistic_acceptance=False,
        visibility='Native catalogs and depth-aware reciprocal structural/partial-canopy clipping; nominal 1 mm / upright 2.5D evidence, not a physical simulation')
    ink,color,sources,ledger,placement=map(lambda v:rename(v,c['case']),[ink,color,sources,ledger,placement])
    publish(out,ink,color,sources,ledger,f,c,placement,generation)
    gz(out/'organization_ledger.json.gz',dict(source_domain_entries=rename(state['domain_ledger'],c['case']),near_ground_entries=rename(state['ground_ledger'],c['case'])))
    print('Published local vectors',season,len(ink),len(color),'paths',flush=True)
    if preview:
        accepted_review.season_previews(out)
        from review import scene_review
        scene_review(out,f,flow)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('season',choices=['summer','autumn','winter']);p.add_argument('--master',required=True);p.add_argument('--vegetation',required=True);p.add_argument('--cache-dir',required=True);p.add_argument('--no-preview',action='store_true');a=p.parse_args()
    run(a.season,a.master,a.vegetation,a.cache_dir,not a.no_preview)
