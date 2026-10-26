"""Actual-vector spacing, source-depth workload and review graphics."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from PIL import Image,ImageDraw,ImageFont
from rasterio.features import rasterize
from affine import Affine
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def palette(c):return dict(slots=deepcopy(c['virtual_color_groups']))
def svg(rows,path,c,width=600):
    import html
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="900mm" viewBox="0 0 {width} 900">',f'<title>{c["case"]} review centerlines; full profiles in companion JSON</title>']
    for r in rows:
        p=' '.join(f'{x:.6f},{y:.6f}' for x,y in r['xy_mm']);rgb=c['virtual_color_groups'][r['color_group']]['preview_hex'] if r.get('medium')=='color-intent' else '#202725'
        w=float(np.mean(r.get('width_profile_mm',[r['width_mm']])));alpha=float(np.mean(r.get('opacity_profile',[r.get('preview_opacity',.8)])))
        parts.append(f'<polyline data-source="{html.escape(r["id"],quote=True)}" points="{p}" fill="none" stroke="{rgb}" stroke-width="{w}" opacity="{alpha}" stroke-linecap="round"/>')
    Path(path).write_text('\n'.join(parts+['</svg>'])+'\n')

def render(ink,color,path,c,bounds=(0,0,600,900),pixels=None):
    colored=deepcopy(color)
    for r in colored:r['palette_slot']=r['color_group']
    prior.render(ink,colored,path,palette(c),bounds,pixels=pixels)

def season_previews(out):
    out=Path(out);c=read(out/'config.json');ink=read(out/'ink.json.gz')['strokes'];color=read(out/'color_intent.json.gz')['strokes']
    render(ink,color,out/'full.png',c);render(ink,[],out/'ink.png',c);render([],color,out/'color_intent.png',c)
    svg(ink+color,out/'scene.svg',c);svg(ink,out/'ink.svg',c)
    for local,n in enumerate(c['panels']):
        x=300*local;render(ink,color,out/f'P{n}.png',c,bounds=(x,0,x+300,900),pixels=(600,1800))
        panel=read(out/f'P{n}.vectors.json.gz')['strokes'];svg(panel,out/f'P{n}.svg',c,300)
    with Image.open(out/'full.png') as im:
        im=im.convert('RGB');pair=Image.new('RGB',(1280,1800),'#e3e0d7');pair.paste(im.crop((0,0,600,1800)),(0,0));pair.paste(im.crop((600,0,1200,1800)),(680,0));pair.save(out/'physical_pair.png')
    panels=[]
    for family in ['A','B','C','D','V','tree','rock','Soil']:
        p=out/f'layer_{family}.png';render([r for r in ink if r['layer']==family],[],p,c,pixels=(600,900));panels.append((p,family))
    prior.grid(panels,out/'layers.png',c['case']+' / final ink layers',cell=(300,450),columns=4,note='Same scale; only actual vectors. Color intent remains separate.')
    return ink,color,c

def occupancy(rows):
    shapes=[(LineString(r['xy_mm']),1) for r in rows if length(r)>0]
    return rasterize(shapes,out_shape=(900,600),transform=Affine.identity(),all_touched=True,dtype='uint8').astype(bool) if shapes else np.zeros((900,600),bool)

def qprofile(r,p,f):
    if len(r.get('source_forward_profile_m',[]))==len(r['xy_mm']):
        arcs=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
        at=np.linspace(0,arcs[-1],len(p));return np.interp(at,arcs,r['source_forward_profile_m'])
    for key in ('source_object_depth_m','source_forward_m','forward_depth_m','forward_depth'):
        value=r.get(key)
        if isinstance(value,(int,float)):return np.full(len(p),value)
    site=r.get('source_site',{})
    if 'source_forward_m' in site:return np.full(len(p),site['source_forward_m'])
    depth=f['depth'] if 'depth' in f else f['base']['depth_m']
    return sample(depth,p)

def workload(rows,f):
    roles={name:dict(paths_touching=0,length_mm=0.) for name in ['near','middle','far']};unknown=0
    for r in rows:
        p=resample(r['xy_mm'],1);q=qprofile(r,p,f);ds=np.linalg.norm(np.diff(p,axis=0),axis=1);qm=(q[:-1]+q[1:])/2
        for role,lo,hi in [('near',0,1600),('middle',1600,3400),('far',3400,np.inf)]:
            m=(qm>=lo)&(qm<hi);roles[role]['length_mm']+=float(ds[m].sum());roles[role]['paths_touching']+=int(m.any())
        unknown+=int((~np.isfinite(q)).any())
    lengths=np.array([length(r) for r in rows]);bins=[0,2.8,5,15,50,150,np.inf]
    return dict(canonical_strokes=len(rows),drawing_length_mm=float(lengths.sum()),length_quantiles_mm=np.quantile(lengths,[0,.1,.5,.9,1]).tolist(),
        short_length_bins=dict(zip(['under2.8','2.8to5','5to15','15to50','50to150','over150'],map(int,np.histogram(lengths,bins)[0]))),
        depth_roles=roles,unknown_depth_paths=unknown,minimum_atomic_engagements=len(rows),runtime_estimate=None,
        metric_scope='Visible canonical centerlines before panel clipping; paths touching roles can overlap. No loading, brush, drying or execution-time inference.')

def spacing(rows,mass,f):
    groups=dict(dense=[],open=[],transition=[]);probes=[]
    for x in np.arange(15,590,10):
        yy=[]
        for r in rows:
            p=np.asarray(r['xy_mm']);a=p[:-1];b=p[1:];dx=b[:,0]-a[:,0]
            mask=(np.minimum(a[:,0],b[:,0])<=x)&(np.maximum(a[:,0],b[:,0])>x)&(abs(dx)>1e-10)
            vals=a[mask,1]+(x-a[mask,0])/dx[mask]*(b[mask,1]-a[mask,1]);yy.extend(vals[(vals>=560)&(vals<880)])
        y=np.array(sorted(set(round(float(v),4) for v in yy)))
        for a,b in zip(y[:-1],y[1:]):
            if b-a<.1:continue
            p=np.array([[x,(a+b)/2]])
            if sample(f['base']['depth_m'],p)[0]>=1600 or sample(f['retention'],p)[0]<.12:continue
            value=float(sample(mass,p)[0]);role='dense' if value>=.5 else 'open' if value<=.18 else 'transition'
            groups[role].append(float(b-a));probes.append(dict(x_mm=float(x),y_interval_mm=[float(a),float(b)],spacing_mm=float(b-a),role=role,mass=value))
    result={k:dict(samples=len(v),p10_p50_p90_mm=np.quantile(v,[.1,.5,.9]).tolist() if v else None) for k,v in groups.items()}
    result['open_to_dense_median_spacing_ratio']=(float(np.median(groups['open'])/np.median(groups['dense'])) if groups['open'] and groups['dense'] else None)
    return result,probes

def summer_comparison(out,field_cache):
    out=Path(out);old=read(BASE/'summer_ink.json.gz')['strokes'];new=read(out/'ink.json.gz')['strokes'];c=read(out/'config.json')
    with open(field_cache,'rb') as h:_,f=pickle.load(h)
    with np.load(out/'ground_fields.npz') as z:mass=z['mass'];opening=z['opening']
    old_a=[r for r in old if r['layer']=='A'];new_a=[r for r in new if r['layer']=='A']
    result={};probes={}
    near_masks=f['base']['occupied']&(f['base']['depth_m']<1600)&(f['retention']>.12)
    for key,rows in [('before',old_a),('after',new_a)]:
        near,_=split_domain(rows,f,True);cov=occupancy(near);s,p=spacing(rows,mass,f);probes[key]=p
        result[key]=dict(A_near_paths=len(near),A_near_length_mm=sum(length(r) for r in near),A_all_length_mm=sum(length(r) for r in rows),
            path_lengths_mm=np.quantile([length(r) for r in near],[.1,.5,.9,1]).tolist(),near_paths_over150mm=sum(length(r)>150 for r in near),spacing=s,
            local_coverage={role:float(cov[near_masks&mask].mean()) if (near_masks&mask).any() else None for role,mask in [('dense',mass>=.5),('open',mass<=.18),('valley_opening',opening>=.25)]})
    save(out/'foreground_diagnostics.json',result);gz(out/'spacing_probes.json.gz',dict(probes=probes,definition='Vertical probe intersections of actual A centerlines, in source-near terrain. Coverage is 1 mm line-cell occupancy, not wet pigment.'))
    panels=[]
    bounds=(0,560,600,898)
    for name,rows in [('before',old),('after',new)]:
        p=out/f'foreground_{name}.png';render(rows,[],p,c,bounds=bounds,pixels=(1800,1014));panels.append((p,name+' / ink foreground'))
    prior.grid(panels,out/'foreground_before_after.png','Summer foreground / identical camera and display scale',cell=(1000,564),columns=2,note='Upper terrain is preserved; view is cropped to foreground.')
    contacts=read(out/'placement.json')['contacts'];crops=[]
    for j,item in enumerate(contacts[:3]):
        x,y=item['site']['xy_mm'];x0=max(0,min(420,x-90));y0=max(540,min(748,y-95));b=(x0,y0,x0+180,y0+150)
        for name,rows in [('before',old),('after',new)]:
            p=out/f'crop_{j}_{name}.png';render(rows,[],p,c,bounds=b,pixels=(900,750));crops.append((p,f'{item["group"]} / {name}'))
    prior.grid(crops,out/'foreground_crops.png','Local ground / vegetation / rock relations',cell=(480,400),columns=2,note='Matched crops; exact original and new vector geometries.')
    fig,axes=plt.subplots(1,3,figsize=(14,6))
    axes[0].imshow(mass,vmin=0,vmax=1,cmap='YlGn',extent=[0,600,900,0]);axes[0].set_ylim(900,550);axes[0].set_title('Source-supported ground mass')
    axes[1].imshow(opening,vmin=0,vmax=1,cmap='Blues',extent=[0,600,900,0]);axes[1].set_ylim(900,550);axes[1].set_title('Valley / passage importance')
    for key,color in [('before','#94735d'),('after','#3c7168')]:
        for role,style in [('dense','-'),('open','--')]:
            v=[r['spacing_mm'] for r in probes[key] if r['role']==role]
            if v:axes[2].hist(v,bins=np.linspace(0,30,31),histtype='step',density=True,label=key+' '+role,color=color,ls=style)
    axes[2].set(xlabel='Adjacent A-row spacing (mm)',ylabel='Normalized sample frequency',xlim=(0,30));axes[2].legend(fontsize=8)
    fig.tight_layout();fig.savefig(out/'ground_spacing_diagnostics.png',dpi=160);plt.close(fig)
    return result
