"""Terrain-related foreground organization and seasonal catalog placement.

The pinned Summer generator and all accepted grammar modules stay unchanged.
Coordinates are top-down mm. Design envelopes are not measured brush widths.
"""
from pathlib import Path
from copy import deepcopy
import argparse,gzip,hashlib,io,json,pickle,sys
import numpy as np
from scipy.ndimage import gaussian_filter,distance_transform_edt,label
from shapely.geometry import LineString,Point
ROOT=Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT/'studies/summer_scene_v01'))
import generate as prior
from datascape.strokes.vector import sample,resample,phase
from datascape.strokes.generators import continuity_mask
from datascape.strokes.accordion import integrated_target,local_monotone_projection
from datascape.strokes.spacing_schedule import trace_phase
from datascape.strokes.density_rhythm import transfer
from datascape.projection.composition import smoothstep
from datascape.composition.fields import smooth_supported
from datascape.integration.visibility import contact
from datascape.vegetation.pictorial_families_v03 import supported_root
from datascape.vegetation.mid_far import Evidence
from datascape.vegetation.tree_form_calibration import GrowthControls
BASE=ROOT/'docs/experiments/summer_scene_v01'

def read(p):
    raw=Path(p).read_bytes();return json.loads(gzip.decompress(raw) if str(p).endswith('.gz') else raw)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):prior.save(p,value)
def gz(p,value):prior.gz(p,value)
def length(r):return float(LineString(r['xy_mm']).length)
def digest(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def cache_fields(master,veg,scene,season,seed,cache=None):
    actual=dict(master=sha(master),vegetation=sha(veg));expected=read(ROOT/'studies/summer_scene_v01/config.json')['input_sha256']
    if actual!=expected:raise ValueError('GIS inputs differ from the pinned verified source datasets')
    key=digest(dict(scene=scene,season=season,seed=seed,**actual))
    if cache and Path(cache).exists():
        with open(cache,'rb') as f:k,data=pickle.load(f)
        if k!=key:raise ValueError('Stale private field cache')
        return data
    from datascape.rendering.painterly_layers import load_features
    from datascape.composition.multidepth import source_features,build_reserves
    from datascape.composition.refinement import refine_reserves
    from datascape.rendering.ground_study import make_camera
    from datascape.projection.ground import GroundComposite
    import rasterio
    lc=read(ROOT/'configs/scenes/seoul_f2_painterly_layers_v01.json');lc.update(season=season.upper(),seed=seed)
    terrain,b,ndvi,counts,source=load_features(master,veg,scene,lc)
    v2=read(ROOT/'configs/scenes/seoul_f2_multidepth_whitespace_v02.json');v2['seed']=seed;v2['vegetation']['season']=season.upper()
    f=source_features(master,b,{**v2['terrain'],'seed':seed});old=build_reserves(b,f,v2)
    refined=refine_reserves(b,old,[],read(ROOT/'configs/scenes/seoul_f2_painterly_composition_v03.json'),v2)
    ret=(.7*refined['legacy_local_retention']+.3*refined['local_core_retention'])*refined['global_retention']*b['occupied']
    fixed=dict(base=b,terrain=terrain,features=f,old=old,refined=refined,retention=ret,scene=scene,source=source,
        vegetation_config=v2['vegetation'],_grammar_xyz=np.nan_to_num(b['xyz']),_grammar_safe=distance_transform_edt((ret>0)&b['occupied']))
    with rasterio.open(master) as ds:cam,site=make_camera(ds,scene['primary_eye_xy_m'],scene['look_target_xy_m'],2,0,36,1)
    fixed['projection']=GroundComposite(cam,site['source_dem_at_eye_m'],**scene['composite'])
    if cache:
        with open(cache,'wb') as f:pickle.dump((key,fixed),f)
    return fixed

def evidence(f):
    b=f['base'];return Evidence(b['depth_m'],np.nan_to_num(b['xyz']),np.nan_to_num(b['current_ndvi']),np.nan_to_num(b['current_observations']),b['occupied'],f['retention'],f['refined']['global_retention'],f['_grammar_safe'],{})

def supported_groups(f,c):
    """Select actual mound/ridge contacts inside declared composition regions."""
    c=deepcopy(c);b=f['base'];ev=evidence(f);yy,xx=np.mgrid[:900,:600]
    gentle=1-smoothstep((np.nan_to_num(b['slope_deg'],nan=45)-4)/24)
    form=.55*f['features']['mound']+.25*f['features']['ridge']+.20*gentle
    good=b['occupied']&(f['retention']>.34)&np.isfinite(b['current_ndvi'])&(b['current_observations']>=6)&(b['depth_m']<1350)&(yy<852)&(xx>36)&(xx<562)
    contacts=[]
    for group in c['near_groups']:
        x0,y0=group['center_mm'];d=((xx+.5-x0)/55)**2+((yy+.5-y0)/48)**2
        min_dx=min(m[0] for m in group['members']);max_dx=max(m[0] for m in group['members'])
        allowed=good&(d<1)&(xx>30-min_dx)&(xx<570-max_dx)
        if not allowed.any():raise ValueError('No supported ground mass '+group['id'])
        score=form-.45*d+.12*f['retention'];y,x=np.unravel_index(np.argmax(np.where(allowed,score,-np.inf)),d.shape)
        center=[x+.5,y+.5];site=contact(f,center);members=[];chosen=[]
        for dx,dy,h,form_name in group['members']:
            wanted=np.array(center)+[dx,dy]
            # All members share a source-depth section with bounded offsets.
            try:p=supported_root(ev,float(wanted[0]),site['source_forward_m']+dy*2,float(wanted[1]),[center[1]-40,center[1]+42])
            except ValueError:p=wanted
            dd=(xx+.5-p[0])**2+(yy+.5-p[1])**2;valid=good&(dd<60**2)
            for oldxy in chosen:valid &= ((xx+.5-oldxy[0])**2+(yy+.5-oldxy[1])**2)>8**2
            if not valid.any():raise ValueError('No supported member '+group['id'])
            yy0,xx0=np.unravel_index(np.argmin(np.where(valid,dd,np.inf)),dd.shape)
            chosen.append([xx0+.5,yy0+.5])
            members.append([float(xx0+.5-center[0]),float(yy0+.5-center[1]),h,form_name])
        group['center_mm']=center;group['members']=members
        contacts.append(dict(group=group['id'],site=site,original_target_mm=[x0,y0],support_score=float(form[y,x])))
    bygroup={g['id']:g for g in c['near_groups']}
    for rock in c['rocks']:
        g=bygroup[rock['group']];rock['target_mm']=[g['center_mm'][0]+rock.get('support_dx_mm',0),g['center_mm'][1]+rock.get('support_dy_mm',14)]
    return c,contacts

def ground_fields(f,contacts,c):
    """Ground islands are geographic support patches shaped by measured relief."""
    b=f['base'];xyz=b['xyz'];occ=b['occupied'];q=b['depth_m'];feat=f['features']
    islands=np.zeros_like(q)
    for item in contacts:
        sx,sy=item['site']['source_xyz_utm_m'][:2]
        world=np.nan_to_num(np.exp(-.5*(((xyz[:,:,0]-sx)/c['ground']['support_radius_m'][0])**2+((xyz[:,:,1]-sy)/c['ground']['support_radius_m'][1])**2)))
        match=np.exp(-.5*((q-item['site']['source_forward_m'])/260)**2)
        islands=np.maximum(islands,world*match)
    gentle=1-smoothstep((np.nan_to_num(b['slope_deg'],nan=45)-4)/24)
    structure=smooth_supported((.65*feat['mound']+.35*feat['ridge'])*(.4+.6*gentle),occ,5)
    mass=np.clip(islands*(.80+.20*structure)+.35*structure,0,1)*occ
    valleys=smooth_supported(np.maximum(feat['valley_small'],.65*feat['valley_medium']),occ,5)
    mass*=1-.48*valleys
    # A source-surface valley is an opening policy, never an arbitrary X stripe.
    opening=np.clip(valleys*(1-.75*islands),0,1)
    density=np.clip(.45+3.5*mass-1.10*opening,.20,3.0)
    keep=np.clip(.22+.78*smoothstep(mass/.55)-.24*opening,.16,.99)
    return dict(mass=mass,opening=opening,density=density,keep=keep,structure=structure)

def foreground(f,reference,contacts,c):
    g=ground_fields(f,contacts,c);b=f['base'];q=b['depth_m'];domain=continuity_mask(b)&(q<1600)&(f['retention']>.01)
    labels,_=label(domain)
    target,_=integrated_target(f,reference,labels,g['density'],feather_mm=10,smoothing_mm=2,maximum_displacement=16)
    scope=1-smoothstep((q-1300)/300);target=reference+(target-reference)*scope
    new,solver=local_monotone_projection(f,reference,target,reference,domain,smoothness=2.,maximum_change=16,time_limit=120)
    raw,_=trace_phase(new,f)
    mc=read(ROOT/'configs/scenes/seoul_spring_stroke_grammar_v03.json');mc['seed']=c['seed']
    # Keep the existing mist transfer; new A-specific occurrence distinguishes
    # meaningful connected ground from long low-value bands between masses.
    priority_fixed={**f,'retention':np.where(f['retention']>0,np.minimum(1,f['retention']+.72*g['mass']*(1-f['retention'])),0.)}
    candidates=transfer(raw,priority_fixed,mc);sources=[];audit=[]
    for i,r in enumerate(candidates):
        r=deepcopy(r);r.update(id=c['case']+'/A-near/'+str(i),source_family='A',owner_id=c['case']+'/ground',medium='ink')
        def gate(p,arc,r):
            scope=(1600-sample(q,p))/100
            u=phase(r['id'],c['seed']);occurrence=sample(g['keep'],p)-(.05+.88*u)
            return np.minimum(scope,occurrence),['source-near-domain','mound-ground-organization']
        parts,a=prior.clip_review(r,gate,minimum_mm=3.5);sources.append(r);audit.append(a)
        for part in parts:part['source_stroke_id']=r['id']
        # The visible pre-object pieces become direct sources in the final pass.
        g.setdefault('proposals',[]).extend(parts)
    arrays={k:v for k,v in solver.items() if isinstance(v,np.ndarray)}
    summary={k:v for k,v in solver.items() if k not in arrays}
    return g['proposals'],sources,audit,g,new,summary

def split_domain(rows,f,near=True,prefix=None):
    result=[];audit=[]
    for r in rows:
        q=sample(f['base']['depth_m'],resample(r['xy_mm'],1))
        values=1600-q if near else q-1600
        if values.min()>=0:
            rr=deepcopy(r)
            if prefix:rr['id']=prefix+'/'+rr['id']
            result.append(rr);continue
        if values.max()<=0:continue
        rr=deepcopy(r)
        if prefix:rr['id']=prefix+'/'+rr['id']
        gate=lambda p,arc,r:((1600-sample(f['base']['depth_m'],p))*(1 if near else -1),['near-domain-split'])
        out,a=prior.clip_review(rr,gate,minimum_mm=2.8);result+=out;audit.append(a)
    return result,audit

def catalog(f,terrain,c):
    """Seasonal controls feed unchanged v10 internals; no finished-tree scaling."""
    original=prior.make_tree
    def tree(*args,**kwargs):
        form=args[0] if args else kwargs.get('form','B');identity=kwargs['identity'];growth=kwargs['growth_controls']
        variation=.72+.45*phase(identity+'/seasonal-vigor',c['seed'])
        vigor=growth.vigor*variation
        if c['season']=='winter' and form=='P':vigor=max(.65,vigor)
        if c['season']=='autumn' and form=='P':vigor=max(.82,vigor)
        kwargs['growth_controls']=GrowthControls(stem_ratio=growth.stem_ratio,vigor=min(1.5,vigor))
        t=original(*args,**kwargs);t.structure['seasonal_control']=dict(season=c['season'],vigor=float(vigor),variation=float(variation))
        return t
    prior.make_tree=tree
    try:objects,color,notes=prior.catalog_objects(f,terrain,c)
    finally:prior.make_tree=original
    if c['season']!='summer':
        selected=[]
        for r in color:
            x=np.mean(np.array(r['xy_mm'])[:,0]);t=float(prior.progress(x));owner=r['owner_id']
            keep=(.78-.35*t) if c['season']=='autumn' else (.28-.13*t)
            token=owner+'/'+r['id'].split('/color/')[-1].split('-0.')[0]
            if phase(token,c['seed'])<=keep:
                r=deepcopy(r);r['preview_opacity']=.22 if c['season']=='autumn' else .12
                r['color_group']='canopy_edge' if c['season']=='autumn' else 'distance';selected.append(r)
        color=selected
    notes.append(dict(catalog_objects=[dict(id=o['id'],kind=o['kind'],site=o['site'],group=o.get('group'),height_mm=o.get('height_mm')) for o in objects]))
    return objects,color,notes

def mid_far(f,c):
    vi,vc,roots=prior.mid_far(f,c)
    if c['season']=='summer':return vi,vc,roots
    selected=[]
    forms={r['id']:r['form'] for r in roots}
    for r in vc:
        x=np.mean(np.array(r['xy_mm'])[:,0]);t=float(prior.progress(x));base=.78-.30*t if c['season']=='autumn' else .26-.12*t
        if forms.get(r['owner_id'])=='P':base=max(base,.62)
        # Whole branch/color territories survive together, never random ray dots.
        token=r['owner_id']+'/'+r.get('growth_branch_id','whole')
        if phase(token,c['seed'])<base:
            r=deepcopy(r);r['color_group']='canopy_edge' if c['season']=='autumn' else 'distance';r['preview_opacity']=.34 if c['season']=='autumn' else .18;selected.append(r)
    return vi,selected,roots

def publish(out,ink,color,sources,ledger,f,c,contacts,notes,diagnostics):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    # Retag new-season authoring namespaces after grammar evaluation.
    if c['season']!='summer':
        def rename(value):
            if isinstance(value,str):return value.replace('summer/',c['case']+'/')
            if isinstance(value,list):return [rename(x) for x in value]
            if isinstance(value,dict):return {k:rename(v) for k,v in value.items()}
            return value
        ink,color,sources,ledger,contacts,notes=map(rename,[ink,color,sources,ledger,contacts,notes])
    gz(out/'ink.json.gz',dict(continuous_mm=[600,900],strokes=ink));gz(out/'color_intent.json.gz',dict(continuous_mm=[600,900],strokes=color))
    unique={r['id']:r for r in sources}
    if len(unique)!=len(sources):raise ValueError('Duplicate authoring sources')
    gz(out/'authoring_sources.json.gz',dict(strokes=sources));gz(out/'visibility_ledger.json.gz',dict(entries=ledger))
    from diagnostics import svg
    svg(ink+color,out/'scene.svg',c);svg(ink,out/'ink.svg',c)
    panel_stats={}
    for local,n in enumerate(c['panels']):
        ii=prior.panel_rows(ink,3+local);cc=prior.panel_rows(color,3+local)
        for r in ii+cc:r['panel']=n
        gz(out/f'P{n}.vectors.json.gz',dict(panel=n,size_mm=[300,900],continuous_x_offset_mm=300*local,strokes=ii+cc))
        svg(ii+cc,out/f'P{n}.svg',c,300);panel_stats[f'P{n}']=dict(ink=prior.stats(ii),color=prior.stats(cc))
    active={e['source_id'] for e in ledger}|{r['source_stroke_id'] for r in ink+color}
    authoring=[r for r in sources if r['id'] in active and r.get('medium')!='color-intent' and r['layer']!='color']
    save(out/'statistics.json',dict(authoring_ink=prior.stats(authoring),ink=prior.stats(ink),color=prior.stats(color),panels=panel_stats))
    save(out/'placement.json',dict(contacts=contacts,rock_notes=notes));save(out/'config.json',c);save(out/'generation.json',diagnostics)
    buf=io.BytesIO();np.savez_compressed(buf,occupied=f['base']['occupied'],depth=f['base']['depth_m'].astype('float32'),xyz=f['base']['xyz'].astype('float32'),retention=f['retention'].astype('float32'))
    (out/'fields.npz').write_bytes(buf.getvalue())
    return ink,color
