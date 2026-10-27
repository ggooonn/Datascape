"""Geometry-preserving seasonal display intent, separate from machine materials."""
from pathlib import Path
import gzip,hashlib,io,json
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/experiments/seasonal_color_tone_v01'
CONFIG=ROOT/'configs/experiments/seasonal_color_tone_v01.json'
SCENES={'spring':'artworks/spring_v13','summer':'docs/experiments/summer_composition_v03','autumn':'docs/experiments/autumn_composition_v01','winter':'docs/experiments/winter_composition_v01'}
ORDER=list(SCENES)

def read(path):
    p=Path(path);raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def save(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending');t.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');t.replace(p)
def gz(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending');t.write_bytes(gzip.compress(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0));t.replace(p)
def png(path,image):
    buf=io.BytesIO();image.save(buf,format='PNG');raw=buf.getvalue()
    with Image.open(io.BytesIO(raw)) as im:im.load()
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending');t.write_bytes(raw);t.replace(p)
def figure_png(fig,path,dpi=150):
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=dpi)
    with Image.open(io.BytesIO(buf.getvalue())) as im:im.load();png(path,im)
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def token(identity):return int(hashlib.sha256(identity.encode()).hexdigest()[:12],16)/16**12
def length(row):return float(np.linalg.norm(np.diff(row['xy_mm'],axis=0),axis=1).sum())
def rgb(value):return np.array([int(value[i:i+2],16)/255 for i in (1,3,5)])
def smooth(t):t=np.clip(t,0,1);return t*t*(3-2*t)

def to_lab(c):
    c=np.asarray(c);lin=np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
    lms=lin@np.array([[.4122214708,.2119034982,.0883024619],[.5363325363,.6806995451,.2817188376],[.0514459929,.1073969566,.6299787005]])
    return np.cbrt(lms)@np.array([[.2104542553,1.9779984951,.0259040371],[.7936177850,-2.4285922050,.7827717662],[-.0040720468,.4505937099,-.8086757660]])

def from_lab(lab):
    a=np.asarray(lab)@np.array([[1.,1.,1.],[.3963377774,-.1055613458,-.0894841775],[.2158037573,-.0638541728,-1.2914855480]])
    lin=(a**3)@np.array([[4.0767416621,-1.2684380046,-.0041960863],[-3.3077115913,2.6097574011,-.7034186147],[.2309699292,-.3413193965,1.7076147010]])
    return np.clip(np.where(lin<=.0031308,12.92*lin,1.055*np.maximum(lin,0)**(1/2.4)-.055),0,1)

def blend(a,b,t):return from_lab((1-np.asarray(t)[...,None])*to_lab(a)+np.asarray(t)[...,None]*to_lab(b))

def palette_at(config,global_x,role):
    """One continuous painted-coordinate function shared by both seam sides."""
    x=np.asarray(global_x,dtype=float);centers=np.arange(8)*300+150
    index=np.clip(np.searchsorted(centers,x,side='right')-1,0,6)
    t=smooth((x-centers[index])/300)
    colors=np.array([rgb(p[role]) for p in config['panels']])
    return blend(colors[index],colors[index+1],t)

def scalar_at(config,global_x,key):
    x=np.asarray(global_x);centers=np.arange(8)*300+150
    index=np.clip(np.searchsorted(centers,x,side='right')-1,0,6);t=smooth((x-centers[index])/300)
    values=np.asarray([p[key] for p in config['panels']])
    if values.ndim==1:return values[index]*(1-t)+values[index+1]*t
    return values[index]*(1-t[...,None])+values[index+1]*t[...,None]

def load_scene(season):
    p=ROOT/SCENES[season]
    names=['visible_ink.json.gz','visible_color.json.gz'] if season=='spring' else ['ink.json.gz','color_intent.json.gz']
    ink=read(p/names[0])['strokes'];color=read(p/names[1])['strokes']
    files={str((p/n).relative_to(ROOT)):hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names}
    fields=None
    if season!='spring':
        with np.load(p/'fields.npz') as z:fields={k:z[k] for k in ['occupied','depth','retention']}
    return dict(season=season,ink=ink,color=color,fields=fields,source_files=files,
        config=read(p/'config.json') if season!='spring' else None)

def geometry_signature(rows):
    keys=['id','xy_mm','width_mm','width_profile_mm','opacity_profile','expression']
    return digest([{k:r[k] for k in keys if k in r} for r in rows])

def depth(row,scene):
    for key in ['source_object_depth_m','source_forward_m','forward_depth_m']:
        value=row.get(key)
        if isinstance(value,(int,float)) and np.isfinite(value) and value>0:return float(value),'source-depth-metadata'
    site=row.get('source_site',{})
    if isinstance(site,dict) and isinstance(site.get('source_forward_m'),(int,float)):return float(site['source_forward_m']),'source-site'
    if scene['fields'] is not None:
        p=np.asarray(row['xy_mm']);x=int(np.clip(p[:,0].mean(),0,599));y=int(np.clip(p[:,1].mean(),0,899))
        if scene['fields']['occupied'][y,x]:return float(scene['fields']['depth'][y,x]),'saved-depth-raster-at-path-centroid'
    return None,'screen-zone-fallback'

def depth_role(row,scene):
    q,basis=depth(row,scene)
    if q is not None:return ('near' if q<1600 else 'middle' if q<3400 else 'far'),basis
    y=np.mean(np.asarray(row['xy_mm'])[:,1]);return ('near' if y>620 else 'middle' if y>370 else 'far'),basis

def material(row):
    family=str(row.get('source_family',''));layer=str(row.get('layer',''))
    if 'rock' in family+layer or 'soil' in (family+layer).lower() or row.get('color_channel')=='material-C-like':return 'mineral'
    if family in ['V','RSU','tree'] or layer in ['V','tree','derived-vegetation'] or row.get('color_channel')=='RSU' or row.get('color_kind')=='vegetation':return 'vegetation'
    return 'terrain'

def color_style(row,scene,c):
    mat=material(row);zone,basis=depth_role(row,scene);x=float(np.mean(np.asarray(row['xy_mm'])[:,0]));gx=x+ORDER.index(scene['season'])*600
    identity=row.get('growth_branch_id',row.get('owner_id',row['id']))
    u=token(identity+'/color-role')
    season=scene['season'];accent_share={'spring':.11,'summer':.13,'autumn':.25,'winter':.055}[season]
    role='base' if mat=='terrain' or zone=='far' else 'accent' if u<accent_share else 'structural'
    slot=row.get('palette_slot');avoid=season in c['D4_policy']['strong_use_excluded_seasons'] and slot in ['D4','D5']
    if avoid:role='base' if mat=='terrain' else 'structural'
    return dict(source_id=row['id'],source_kind='color',role=role,material=mat,depth_role=zone,depth_basis=basis,legacy_slot=slot,
        D4_strong_use_excluded=season in c['D4_policy']['strong_use_excluded_seasons'],legacy_earth_remap=avoid,physical_station=None,
        display_gain=c['display']['color_gain'][season]*(c['display']['accent_gain'][season] if role=='accent' else 1.))

def ink_style(row,scene,c):
    mat=material(row);zone,basis=depth_role(row,scene);x=np.mean(np.asarray(row['xy_mm'])[:,0])+ORDER.index(scene['season'])*600
    mix=scalar_at(c,x,'ink_mix_target');part=row.get('grammar_part','');priority=.16 if row.get('layer')=='D' else 0.
    if mat=='mineral' and zone=='near':priority+=.17
    if part in ['trunk-contour','branch-contour']:priority+=.12
    if part=='foliage-field':priority-=.10
    if zone=='far':priority-=.10
    u=token(row['id']+'/ink-tone')
    dark=np.clip(mix[2]+priority,0,.6);light=np.clip(mix[0]-priority,.1,.95)
    cohort='dark' if u<dark else 'light' if u<dark+light else 'middle'
    return dict(source_id=row['id'],source_kind='ink',role='structural',material=mat,depth_role=zone,depth_basis=basis,cohort=cohort,
        pressure_profile_modified=False,concentration_calibrated=False)

def subpath(points,a,b):
    p=np.asarray(points,float);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    keep=(arc>a+1e-9)&(arc<b-1e-9)
    at=np.r_[a,arc[keep],b]
    return np.column_stack([np.interp(at,arc,p[:,0]),np.interp(at,arc,p[:,1])])

def guides(scene,c):
    """Color-territory suggestions, never added to the approved scene files."""
    season=scene['season'];g=c['guide_policy'];result=[]
    if season=='spring':return result
    for r in scene['ink']:
        mat=material(r);is_rock='rock' in str(r.get('layer',''));is_a=r.get('layer')=='A'
        if not is_a and not is_rock:continue
        total=length(r);zone,_=depth_role(r,scene)
        u=token(r['id']+'/territory-select')
        probability=g['terrain_selection_probability'][season] if is_a else g['rock_selection_probability']
        if total<(g['terrain_minimum_parent_length_mm'] if is_a else 9):continue
        center=None
        if is_a:
            at=np.linspace(.12,.88,13)*total;probe=np.array([subpath(r['xy_mm'],max(0,a-.01),min(total,a+.01))[0] for a in at])
            score=np.zeros(len(probe))
            for group in scene['config']['near_groups']:
                x,y=group['center_mm'];weight=max(m[2] for m in group['members'])/240
                score=np.maximum(score,weight*np.exp(-.5*(((probe[:,0]-x)/105)**2+((probe[:,1]-y)/90)**2)))
            for group in scene['config']['mid_far_groups']:
                x,y=group['center_mm'];rx,ry=group['radius_mm']
                score=np.maximum(score,.72*np.exp(-.5*(((probe[:,0]-x)/(rx*.9))**2+((probe[:,1]-y)/(ry*1.2))**2)))
            if score.max()<.055:continue
            probability*=.3+1.45*float(score.max());center=float(at[score.argmax()])
        if u>probability:continue
        if is_a and zone=='far' and token(r['id']+'/far')>.42:continue
        limits=g['terrain_length_mm'] if is_a else g['rock_length_mm'];span=min(total*.72,np.interp(token(r['id']+'/span'),[0,1],limits))
        if span<8:continue
        a=(total-span)*(.12+.70*token(r['id']+'/start')) if center is None else float(np.clip(center-span/2,0,total-span))
        b=a+span;p=subpath(r['xy_mm'],a,b)
        width=g['terrain_display_width_mm'][season] if is_a else g['rock_display_width_mm'][season]
        if np.any(p[:,0]<width/2+1) or np.any(p[:,0]>600-width/2-1) or np.any(p[:,1]>898-width/2-1):continue
        opacity=float(np.mean(r.get('opacity_profile',[r.get('preview_opacity',r.get('opacity',1))])))
        result.append(dict(id='territory/'+season+'/'+hashlib.sha256(r['id'].encode()).hexdigest()[:16],source_id=r['id'],source_kind='ink',
            source_arc_mm=[float(a),float(b)],xy_mm=p.tolist(),role='base' if is_a else 'structural',material='terrain' if is_a else 'mineral',depth_role=zone,
            display_width_mm=width,display_alpha=(g['terrain_display_alpha'][season] if is_a else g['rock_display_alpha'][season])*min(1,opacity*1.3),
            canonical_geometry=False,production_color_path=False,physical_station=None,construction='Exact existing visible ink-source arc; broader display envelope only'))
    return result

def styles(scene,c):
    return dict(schema_version=1,baseline_commit=c['baseline_commit'],season=scene['season'],source_files=scene['source_files'],
        geometry_signatures=dict(ink=geometry_signature(scene['ink']),color=geometry_signature(scene['color'])),
        color=[color_style(r,scene,c) for r in scene['color']],ink=[ink_style(r,scene,c) for r in scene['ink']],
        pressure_profiles_modified=False,physical_pigment_schedule=None,production_Gcode=False)
