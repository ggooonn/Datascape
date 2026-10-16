"""A-density v4 on the locked v3 F2-C scene; no composition search."""
from pathlib import Path
import argparse, hashlib, io, json, platform
import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from datascape.data.quality import sha256_file
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors, resample, sample
from datascape.strokes.generators import continuity_mask
from datascape.strokes.density_rhythm import density_profile, layer_digest, transfer
from datascape.strokes.mass_density import mass_coordinates, generate_a
from datascape.strokes.spacing_schedule import phase_ablation
from datascape.strokes.accordion import mountain_target, foreground_target, local_monotone_projection
from datascape.rendering.a_density_v03_study import _render, _compose, _physical_pair, _crossings, _band_spacing, BANDS
from datascape.rendering.grammar_study import validate
from datascape.rendering.hierarchy_study import publish_png, publish_vectors, metrics
from datascape.rendering.density_rhythm_study import compare, length_map, crossing_spacing

STAGES={'crest':'#9a374a','shoulder':'#2788ae','descending':'#b46c24','foot':'#65a28a','support':'#a6a6a6'}
NAMES={'baseline':'Locked v3','candidate1':'1 · Mountain breathing','candidate2':'2 · Mountain + near breathing'}


def save(fig,path):
    b=io.BytesIO();fig.savefig(b,format='png',dpi=150,facecolor='white');plt.close(fig);publish_png(b.getvalue(),path)


def near_path(s,fixed,cutoff):
    return np.mean(sample(fixed['base']['depth_m'],resample(s['xy_mm'],1)))<cutoff


def summary(record):
    return {k:v for k,v in record.items() if not isinstance(v,np.ndarray)}


def diagnostic_render(strokes,path,fixed,mass,near,mode='stages',bounds=(0,0,600,900)):
    """Display-only stage colors or visible C; canonical records are untouched."""
    x0,y0,x1,y1=bounds;pw=1200;ph=round(pw*(y1-y0)/(x1-x0))
    fig=plt.figure(figsize=(pw/150,ph/150),dpi=150);ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    ordered=strokes if mode=='stages' else sorted(strokes,key=lambda s:s['layer']=='C')
    lines=[];widths=[];colors=[]
    for s in ordered:
        p=np.asarray(s['xy_mm']);layer=s['layer']
        if mode=='stages' and layer!='A':continue
        if mode=='C_only' and layer!='C':continue
        mid=(p[:-1]+p[1:])/2
        stages=['support']*len(mid)
        if mode=='stages':
            labels=sample(mass['labels'],mid,order=0).astype(int);tt=sample(mass['t'],mid)
            q=sample(fixed['base']['depth_m'],mid);island=sample(near['island'],mid);channel=sample(near['channel'],mid)
            for i in range(len(mid)):
                if labels[i]:stages[i]=next((k for k,(lo,hi) in BANDS.items() if lo<=tt[i]<hi),'support')
                if q[i]<1600:stages[i]='descending' if island[i]>.12 else ('shoulder' if channel[i]>.20 else 'support')
        for i,(a,b) in enumerate(zip(p[:-1],p[1:])):
            if mode=='stages':color=STAGES[stages[i]];alpha=1.;width=.32
            elif layer=='C':color='#087bb3';alpha=1.;width=.34
            else:color='#707070';alpha=.22;width=s['width_mm']
            lines.append([a,b]);widths.append(width);colors.append(matplotlib.colors.to_rgba(color,alpha))
    ax.add_collection(LineCollection(lines,linewidths=np.array(widths)*pw/(x1-x0)*72/150,colors=colors,capstyle='round',joinstyle='round'))
    b=io.BytesIO();fig.savefig(b,format='png',dpi=150,facecolor='white');plt.close(fig);publish_png(b.getvalue(),path)


def spacing_gaps(strokes,mass,label,x,yb):
    yy=_crossings(strokes,x,yb);result={k:[] for k in BANDS}
    for a,b in zip(yy[:-1],yy[1:]):
        iy=int((a+b)/2);ix=int(x)
        if mass['labels'][iy,ix]!=label:continue
        t=mass['t'][iy,ix]
        for k,(lo,hi) in BANDS.items():
            if lo<=t<hi:result[k].append(float(b-a));break
    return result


def pooled_spacing(strokes,mass,item):
    x0,y0,x1,y1=item['bounds_mm'];values={k:[] for k in BANDS}
    xs=np.linspace(x0+.15*(x1-x0),x1-.15*(x1-x0),9)
    for x in xs:
        for k,v in spacing_gaps(strokes,mass,item['label'],float(x),(y0,y1)).items():values[k].extend(v)
    med={k:float(np.median(v)) if v else None for k,v in values.items()};dense=[med[k] for k in ['crest','descending'] if med[k] is not None]
    return {'probe_x_mm':xs.tolist(),'band_gap_medians_mm':med,'gap_samples':{k:len(v) for k,v in values.items()},
        'open_to_dense_mean_ratio':float(med['shoulder']/np.mean(dense)) if med['shoulder'] and len(dense)==2 else None}


def spacing_figure(raw,sets,mass,out):
    fig,axes=plt.subplots(2,4,figsize=(12,8),sharey='row');records=[]
    for row,(lab,x,yb) in enumerate([(5,442.5,(317,455)),(9,586.5,(350,533))]):
        rec={'form':lab,'x_mm':x,'y_bounds_mm':yb,'paths':{}}
        for col,(label,ss) in enumerate([('v3 before',raw['baseline']),('v3 after',[s for s in sets['baseline'] if s['layer']=='A']),('v4 before',raw['candidate1']),('v4 after',[s for s in sets['candidate1'] if s['layer']=='A'])]):
            ys=_crossings(ss,x,yb);d=_band_spacing(ss,mass,lab,x,yb);rec['paths'][label]=d
            ax=axes[row,col];ax.hlines(ys,.15,.85,color='black',lw=.8);ax.set(xlim=(0,1),ylim=(yb[1],yb[0]));ax.set_xticks([]);ax.grid(axis='y',alpha=.2)
            mm=[d[k]['median_mm'] for k in ['crest','shoulder','descending']];r=d['open_to_dense_mean_ratio']
            ax.set_title(label+'\n'+ '/'.join('—' if v is None else f'{v:.2f}' for v in mm)+f' mm\nOpen/dense {r:.2f}×',fontsize=8)
        axes[row,0].set_ylabel(f'Form {lab} · y (mm)');axes[row,0].set_xlabel(f'x={x} mm');records.append(rec)
    fig.suptitle('Actual A path intersections · same opaque width · crest / open / descending gaps');fig.tight_layout(rect=(0,0,1,.95));save(fig,out/'spacing_profiles.png')
    return records


def fields_figure(fixed,mass,near,record1,sets,raw,out):
    occ=fixed['base']['occupied'];labels=mass['labels'];t=mass['t']
    one0=length_map([s for s in sets['baseline'] if s['layer']=='A'],10)
    one2=length_map([s for s in sets['candidate2'] if s['layer']=='A'],10)
    maps=[('Within-form stage coordinate t',np.where(labels>0,t,np.nan),'viridis',0,1),
        ('Achieved phase frequency / old source phase',np.where(labels>0,record1['phase_ratio'],np.nan),'coolwarm',.2,2.4),
        ('Existing retention R · unchanged',np.where(occ,fixed['retention'],np.nan),'viridis',0,1),
        ('Measured mound / gentle-ground support',np.where(occ,near['island'],np.nan),'YlOrBr',0,.5),
        ('Measured low-flow A opening support',np.where(occ,near['channel'],np.nan),'Blues',0,.6),
        ('Actual final A density difference · mm/mm²',one2-one0,'coolwarm',-.15,.15)]
    fig,axes=plt.subplots(2,3,figsize=(12,10))
    for ax,(title,a,cmap,lo,hi) in zip(axes.flat,maps):
        im=ax.imshow(a,extent=[0,600,900,0],cmap=cmap,vmin=lo,vmax=hi);ax.set_title(title,fontsize=9);fig.colorbar(im,ax=ax,shrink=.65)
    fig.suptitle('A-placement diagnostics only · no DEM shade or field edit in production');fig.tight_layout();save(fig,out/'density_fields.png')
    fig,axes=plt.subplots(2,3,figsize=(12,10))
    for col,name in enumerate(['baseline','candidate1','candidate2']):
        before=length_map(raw[name],10);after=length_map([s for s in sets[name] if s['layer']=='A'],10)
        for row,a in enumerate([before,after]):
            ax=axes[row,col];im=ax.imshow(a,extent=[0,600,900,0],cmap='magma',vmin=0,vmax=.8);ax.set_title(NAMES[name]+(' · before mist' if row==0 else ' · after mist'),fontsize=9)
    fig.suptitle('Actual vector centerline length / 10×10 mm paper cell · display alpha excluded');fig.tight_layout();save(fig,out/'density_mist.png')


def run(master,veg,config_path,output,repo_root=None,prepared=None):
    import osqp
    cp=Path(config_path);root=Path(repo_root) if repo_root else cp.resolve().parents[2];c=json.loads(cp.read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    for path,digest in c['locked_source_sha256'].items():
        if sha256_file(root/path)!=digest:raise ValueError('Locked input changed: '+path)
    if prepared is None:
        print('Reconstruct exact locked F2-C and working v3',flush=True)
        v2=json.loads((root/c['v2_config']).read_text());old=json.loads((root/v2['baseline_config']).read_text());selection=json.loads((root/c['selection']).read_text())
        f=load_selected_scene(master,veg,root,selection);f['_grammar_safe']=distance_transform_edt((f['retention']>1e-8)&f['base']['occupied']);f['_grammar_xyz']=np.nan_to_num(f['base']['xyz'])
        parent=read_vectors(root/c['baseline_vectors'])['strokes'];profile=density_profile(f,old);mass=mass_coordinates(f,parent,v2);v3=phase_ablation(f,mass,profile,v2,minimum_derivative_ratio=.05)
    else:f,parent,profile,mass,v3,v2=(prepared[k] for k in ['fixed','parent','profile','mass','v3','v2config'])
    retention_hash=hashlib.sha256(f['retention'].tobytes()).hexdigest();xyz_hash=hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    mist=json.loads((root/c['mist_config']).read_text());cutoff=c['foreground']['cutoff_m']
    print('Local constrained mountain redistribution',flush=True)
    target,mt=mountain_target(f,mass,profile,v2,release_strength=c['mountain']['release_strength']);target=v3['phase']+c['mountain']['target_strength']*(target-v3['phase'])
    phase1,r1=local_monotone_projection(f,v3['phase'],target,profile['phase_field'],(mass['labels']>0)&(f['retention']>.01),**c['mountain']['solver'])
    a1,raw1,s1=generate_a(f,{'phase':phase1},parent,v2,mist)
    print('A-only near-ground island/channel redistribution',flush=True)
    nt,near=foreground_target(f,phase1,cutoff,settings=c['foreground']['field']);nt=phase1+c['foreground']['target_strength']*(nt-phase1)
    phase2,r2=local_monotone_projection(f,phase1,nt,profile['phase_field'],f['base']['occupied']&(f['base']['depth_m']<cutoff)&(f['retention']>.01),**c['foreground']['solver'])
    _,raw2,s2=generate_a(f,{'phase':phase2},parent,v2,mist);all2=transfer(raw2,f,mist)
    a2=[{**s,'id':'v4n-'+s['id']} for s in all2 if near_path(s,f,cutoff)]+[s for s in a1 if not near_path(s,f,cutoff)]
    sets={'baseline':parent,'candidate1':_compose(parent,a1),'candidate2':_compose(parent,a2)}
    raw={'baseline':read_vectors(root/c['baseline_candidates'])['strokes'],'candidate1':raw1,'candidate2':raw2}
    provenance={'study':c['study'],'parent_commit':c['parent_commit'],'seed':c['seed'],'config_sha256':sha256_file(cp),
        'baseline_vectors_sha256':sha256_file(root/c['baseline_vectors']),'retention_float64_sha256':retention_hash,
        'composition':'Locked F2-C, 70/30 retention, same camera/projection/DEM/NDVI/B/C/D/V and mist transfer',
        'implementation_sha256':{p:sha256_file(root/p) for p in ['src/datascape/strokes/accordion.py','src/datascape/rendering/accordion_study.py']}}
    print('Validate and render actual canonical vectors',flush=True)
    for name,ss in sets.items():
        validate(ss,f)
        for layer in ['B','C','D','V']:assert layer_digest(ss,layer)==layer_digest(parent,layer)
        assert len({s['id'] for s in ss})==len(ss)
        if name!='baseline':
            publish_vectors(out/f'{name}_strokes.json.gz',ss,{**provenance,'candidate':name});ss=read_vectors(out/f'{name}_strokes.json.gz')['strokes'];sets[name]=ss
        _render(ss,out/f'{name}_production.png');_physical_pair(out/f'{name}_production.png',out/f'{name}_physical.png')
        for role,bounds in c['crops_mm'].items():
            pixels=(1200,round(1200*(bounds[3]-bounds[1])/(bounds[2]-bounds[0])))
            _render(ss,out/f'{name}_{role}_production.png',bounds=tuple(bounds),pixels=pixels)
            _render(ss,out/f'{name}_{role}_A.png',bounds=tuple(bounds),pixels=pixels,mode='A_only')
    compare({NAMES[n]:out/f'{n}_production.png' for n in sets},out/'production_comparison.png','Same production styling · only A geometry changes')
    compare({NAMES[n]:out/f'{n}_physical.png' for n in sets},out/'physical_comparison.png','600×900 mm continuous content · 40 mm physical interval',(0,0,640,900))
    for role in ['mountain','foreground']:
        compare({NAMES[n]:out/f'{n}_{role}_A.png' for n in sets},out/f'{role}_A_comparison.png','Opaque 0.32 mm A centerlines · no opacity density cue',tuple(c['crops_mm'][role]))
    compare({NAMES[n]:out/f'{n}_foreground_production.png' for n in sets},out/'foreground_production_comparison.png','Same C/B/D/V context, same lower reserve',tuple(c['crops_mm']['foreground']))
    for name in ['baseline','candidate1']:
        _render(raw[name],out/f'{name}_before_mist_A.png',bounds=tuple(c['crops_mm']['mountain']),pixels=(1200,round(1200*(c['crops_mm']['mountain'][3]-c['crops_mm']['mountain'][1])/(c['crops_mm']['mountain'][2]-c['crops_mm']['mountain'][0]))),mode='A_only')
    compare({'v3 candidates':out/'baseline_before_mist_A.png','v4 candidates':out/'candidate1_before_mist_A.png'},out/'before_mist_comparison.png','Rhythm exists before the unchanged omission transfer',tuple(c['crops_mm']['mountain']))
    diagnostic_render(sets['candidate2'],out/'stage_vectors.png',f,mass,near)
    diagnostic_render(sets['candidate2'],out/'C_visible_context.png',f,mass,near,'C_context')
    diagnostic_render(sets['candidate2'],out/'C_only.png',f,mass,near,'C_only')
    diagnostic_render(sets['candidate2'],out/'C_near_context.png',f,mass,near,'C_context',tuple(c['crops_mm']['foreground']))
    compare({'C in fixed context':out/'C_visible_context.png','Identical C paths alone':out/'C_only.png'},out/'C_visibility.png','Diagnostic C: blue, opaque, 0.34 mm · production C remains unchanged')
    probes=spacing_figure(raw,sets,mass,out);fields_figure(f,mass,near,r1,sets,raw,out)
    stats={name:metrics(ss,f['base']) for name,ss in sets.items()};near_region=f['base']['occupied']&(f['base']['depth_m']<cutoff)&(f['retention']>.05)
    masks={'island':near_region&(near['island']>.12),'channel':near_region&(near['channel']>.20)&(near['island']<.05)}
    foreground={};mist_bins={};local_spacing={}
    for name,ss in sets.items():
        aa=[s for s in ss if s['layer']=='A'];after=length_map(aa,1);before=length_map(raw[name],1)
        foreground[name]={key:{'area_mm2':int(m.sum()),'actual_A_length_mm':float(after[m].sum()),'A_length_per_mm2':float(after[m].mean())} for key,m in masks.items()}
        mist_bins[name]=[]
        for lo,hi in zip([0,.2,.4,.6,.8],[.2,.4,.6,.8,1.00001]):
            mm=(mass['labels']>0)&(f['retention']>=lo)&(f['retention']<hi)
            mist_bins[name].append({'retention_range':[lo,min(hi,1)],'area_mm2':int(mm.sum()),'before_A_length_per_mm2':float(before[mm].mean()) if mm.any() else None,'after_A_length_per_mm2':float(after[mm].mean()) if mm.any() else None})
        local_spacing[name]={str(item['label']):pooled_spacing(aa,mass,item) for item in mass['masses']}
    qy,qx=np.gradient(f['base']['depth_m']);py,px=np.gradient(profile['phase_field']);den=px*qx+py*qy;safe=binary_erosion(continuity_mask(f['base']),iterations=2)&(den>1e-8);topology={}
    for name,phase in [('baseline',v3['phase']),('candidate1',phase1),('candidate2',phase2)]:
        yy,xx=np.gradient(phase);rr=(xx*qx+yy*qy)/np.maximum(den,1e-8);topology[name]={'nonpositive_pixels':int(np.sum(safe&(rr<=0))),'minimum_directional_ratio':float(rr[safe].min())}
        assert topology[name]['nonpositive_pixels']==0
    assert retention_hash==hashlib.sha256(f['retention'].tobytes()).hexdigest();assert xyz_hash==hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    record={'study':c['study'],'config':c,'provenance':provenance,'input_sha256':f['selection']['input_sha256'],
        'solver':{'mountain':summary(r1),'foreground':summary(r2)},'generation':{'candidate1':s1,'candidate2':s2},
        'metrics':stats,'foreground_density':foreground,'spacing_probes':probes,'nine_probe_mass_spacing':local_spacing,
        'all_scene_screen_spacing':{name:crossing_spacing(ss,f['base']) for name,ss in sets.items()},'mist_by_retention_bin':mist_bins,'phase_topology':topology,
        'invariants':{'B_C_D_V_identical_except_draw_index':True,'candidate1_foreground_A_exact':layer_digest([s for s in sets['candidate1'] if s['layer']=='A' and near_path(s,f,cutoff)],'A')==layer_digest([s for s in parent if s['layer']=='A' and near_path(s,f,cutoff)],'A'),
            'retention_float64_unchanged':True,'source_XYZ_unchanged':True,'bottom_2mm_empty':True,'terrain_omission_cores_empty':True,'C_paths_and_material_metadata_unchanged':True},
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':__import__('scipy').__version__,'osqp':osqp.__version__,'matplotlib':matplotlib.__version__}}
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)


if __name__=='__main__':main()
