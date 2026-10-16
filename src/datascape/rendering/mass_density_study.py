"""A-density v2: conserved local rhythm and readable frozen C diagnostics."""
from pathlib import Path
from copy import deepcopy
import argparse,json,io,hashlib,platform
import numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from datascape.data.quality import sha256_file
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,sample,resample,finalize
from datascape.strokes.density_rhythm import density_profile,a_proposals,foreground_a,layer_digest
from datascape.strokes.mass_density import mass_coordinates,phase_redistribution,generate_a
from datascape.rendering.color_ready_study import render,write_svg,overlap
from datascape.rendering.grammar_study import validate
from datascape.rendering.hierarchy_study import publish_png,publish_vectors,metrics
from datascape.rendering.density_rhythm_study import length_map,physical_pair,compare,crossing_spacing

COLORS={'A':'#7a7a7a','B':'#8e2b97','C':'#0069d2','D':'#b71921','V':'#b0c9bc'}
BANDS={'crest':(0,.18),'shoulder':(.25,.45),'descending':(.55,.75),'foot':(.85,1.01)}


def save(fig,path):
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150);plt.close(fig);publish_png(buf.getvalue(),path)


def readable(strokes,path,mode='layers',bounds=(0,0,600,900),pixels=(1200,1800)):
    """Diagnostic-only widths/alpha; stored production vectors are untouched."""
    x0,y0,x1,y1=bounds;pw,ph=pixels;fig=plt.figure(figsize=(pw/150,ph/150),dpi=150);ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    for layer in ['A','V','C','B','D']:
        lines=[];widths=[]
        for s in strokes:
            if s['layer']!=layer or (mode=='A' and layer!='A') or (mode=='C' and layer!='C'):continue
            lines.append(np.array(s['xy_mm']))
            widths.append(.28 if mode=='A' else (.60 if layer=='C' else s['width_mm']))
        color='black' if mode=='A' else COLORS[layer]
        ax.add_collection(LineCollection(lines,linewidths=np.array(widths)*pw/(x1-x0)*72/150,colors=color,alpha=1,capstyle='round',joinstyle='round'))
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150,facecolor='white');plt.close(fig);publish_png(buf.getvalue(),path)


def mass_metrics(fixed,mass,fields,baseline,updated,raw0,raw1):
    maps={k:length_map(v,1) for k,v in [('baseline_before',raw0),('v2_before',raw1),('baseline_after',baseline),('v2_after',updated)]}
    records=[]
    for item in mass['masses']:
        mask=mass['labels']==item['label'];core=distance_transform_edt(mask)>10;t=mass['t'];bands={}
        for name,(lo,hi) in BANDS.items():
            m=core&(t>=lo)&(t<hi);area=int(m.sum())
            if not area:continue
            bands[name]={'area_mm2':area,'phase_density_ratio_p50':float(np.median(fields['directional_phase_ratio'][m])),
                'existing_retention_mean':float(np.mean(fixed['retention'][m])),
                **{k+'_length_per_mm2':float(v[m].mean()) for k,v in maps.items()}}
        records.append({'label':item['label'],'bands':bands})
    return records


def field_diagnostics(fixed,mass,fields,out):
    labels=mass['labels'];mask=labels>0;t=mass['t'];fig,axes=plt.subplots(1,4,figsize=(15,4.2))
    panels=[('Source-connected form labels',np.where(mask,labels,np.nan),'tab20',None,None),
        ('Local crest-to-foot coordinate',np.where(mask,t,np.nan),'viridis',0,1),
        ('Effective phase density / baseline',np.where(mask,fields['directional_phase_ratio'],np.nan),'coolwarm',.25,1.75),
        ('Existing retention R (unchanged)',np.where(fixed['base']['occupied'],fixed['retention'],np.nan),'viridis',0,1)]
    for ax,(title,a,cmap,lo,hi) in zip(axes,panels):
        im=ax.imshow(a,extent=[0,600,900,0],cmap=cmap,vmin=lo,vmax=hi);ax.set(xlim=(0,600),ylim=(565,205));ax.set_title(title,fontsize=9);ax.set_xlabel('mm');fig.colorbar(im,ax=ax,shrink=.55)
    for item in mass['masses']:
        x,y=item['seed_pixel_xy'];axes[0].text(x,y,str(item['label']),fontsize=8,color='black',bbox={'facecolor':'white','alpha':.6,'pad':1})
    fig.suptitle('Analysis coordinates only | no camera, terrain or whitespace change');fig.tight_layout();save(fig,out/'mass_fields.png')


def cadence_diagnostic(fixed,mass,fields,records,out):
    # Require all three structural stages, sufficient area and observed opening.
    eligible=[]
    for rec in records:
        b=rec['bands']
        if all(k in b and b[k]['area_mm2']>=100 for k in ['crest','shoulder','descending']):
            contrast=min(b['crest']['phase_density_ratio_p50'],b['descending']['phase_density_ratio_p50'])/max(b['shoulder']['phase_density_ratio_p50'],1e-8)
            eligible.append((contrast,rec))
    chosen=[r for _,r in sorted(eligible,key=lambda v:-v[0])[:3]]
    fig,axes=plt.subplots(1,3,figsize=(13,4.6))
    for ax,rec in zip(axes,chosen):
        b=rec['bands'];names=[n for n in BANDS if n in b];ratio=[b[n]['phase_density_ratio_p50'] for n in names]
        ax.plot(names,ratio,'o-',color='#235b8c',label='Actual phase density / v1');ax.axhline(1,ls='--',color='gray');ax.set_ylim(.3,1.7);ax.set_title('Form '+str(rec['label']));ax.tick_params(axis='x',rotation=20)
        right=ax.twinx();right.plot(names,[b[n]['v2_after_length_per_mm2']/max(b[n]['v2_before_length_per_mm2'],1e-8) for n in names],'s--',color='#a34936',label='Retained actual length fraction');right.set_ylim(0,1.1)
    axes[0].set_ylabel('Geometry frequency ratio');fig.suptitle('Dense / open / dense within each form; existing mist acts after placement')
    fig.legend(handles=[Line2D([],[],color='#235b8c',marker='o',label='Effective phase frequency / v1'),Line2D([],[],color='#a34936',marker='s',ls='--',label='Sampled retained A length / candidate A length')],loc='lower center',ncol=2,fontsize=9)
    fig.tight_layout(rect=(0,.12,1,.94));save(fig,out/'local_cadence.png')
    return [r['label'] for r in chosen]


def probe_diagrams(fixed,mass,examples,groups,out):
    """Actual vector/vertical-probe intersections; no opacity-based density."""
    records=[]
    for mid in examples:
        mask=mass['labels']==mid;t=mass['t'];candidates=[]
        for x in range(mask.shape[1]):
            ids=np.flatnonzero(mask[:,x]);parts=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
            for ys in parts:
                if len(ys)>=30 and t[ys,x].min()<.2 and t[ys,x].max()>.8:candidates.append((len(ys),x,ys))
        if not candidates:continue
        _,x,ys=max(candidates,key=lambda a:(a[0],-abs(a[1]-np.mean(np.where(mask)[1]))));xp=x+.5;y0,y1=int(ys[0]),int(ys[-1]+1)
        fig,axes=plt.subplots(1,4,figsize=(9,5),sharey=True);hits={}
        for ax,(name,strokes) in zip(axes,groups.items()):
            values=[]
            for s in strokes:
                p=np.asarray(s['xy_mm']);a,b=p[:-1],p[1:];dx=b[:,0]-a[:,0]
                ii=np.flatnonzero((np.minimum(a[:,0],b[:,0])<=xp)&(np.maximum(a[:,0],b[:,0])>xp)&(abs(dx)>1e-8))
                for i in ii:
                    y=a[i,1]+(xp-a[i,0])/dx[i]*(b[i,1]-a[i,1])
                    if y0<=y<y1 and mask[int(y),x]:values.append(float(y))
            values=np.sort(values);hits[name]=values.tolist()
            ax.hlines(values,.15,.85,lw=.8,color='black');ax.set(xlim=(0,1),ylim=(y1,y0));ax.set_xticks([]);ax.set_title(name,fontsize=9);ax.grid(axis='y',alpha=.2)
        axes[0].set_ylabel('Actual screen y (mm)')
        fig.suptitle(f'Form {mid}, x={xp:g} mm | equal stroke width, alpha 1; exact path intersections')
        fig.tight_layout();save(fig,out/f'form_{mid}_spacing_probe.png')
        records.append({'label':mid,'x_mm':xp,'y_range_mm':[y0,y1],'actual_crossings_y_mm':hits})
    return records


def run(master,veg,config_path,output,repo_root=None,prepared=None):
    cp=Path(config_path);root=Path(repo_root) if repo_root else cp.resolve().parents[2];c=json.loads(cp.read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    for p,h in c['locked_source_sha256'].items():assert sha256_file(root/p)==h,p
    selection=json.loads((root/c['selection']).read_text())
    if prepared is None:
        print('Reconstruct exact frozen F2-C',flush=True);fixed=load_selected_scene(master,veg,root,selection)
        fixed['_grammar_safe']=distance_transform_edt((fixed['retention']>1e-8)&fixed['base']['occupied']);fixed['_grammar_xyz']=np.nan_to_num(fixed['base']['xyz'])
    else:fixed=prepared
    parent=read_vectors(root/c['baseline_vectors'])['strokes'];old_c=json.loads((root/c['baseline_config']).read_text());mist_c=json.loads((root/c['mist_config']).read_text())
    before_hash=hashlib.sha256(fixed['retention'].tobytes()).hexdigest();profile=density_profile(fixed,old_c)
    print('Infer source-connected forms and redistribute row phase',flush=True);mass=mass_coordinates(fixed,parent,c);fields=phase_redistribution(fixed,mass,profile,c)
    assert fields['phase_derivative_nonpositive_pixels']==0
    a,raw,selection_record=generate_a(fixed,fields,parent,c,mist_c)
    baseline_a=[s for s in parent if s['layer']=='A'];raw0=foreground_a(a_proposals(fixed,profile,old_c),fixed,.72)
    updated=[{**s,'draw_order':i} for i,s in enumerate(s for k in ['C','A','B','V','D'] for s in (a if k=='A' else [s for s in parent if s['layer']==k]))]
    validate(updated,fixed);assert len(updated)==len({s['id'] for s in updated})
    for k in ['B','C','D','V']:assert layer_digest(updated,k)==layer_digest(parent,k)
    provenance={'study':c['study'],'parent_commit':c['parent_commit'],'seed':c['seed'],'config_sha256':sha256_file(cp),
        'input_sha256':selection['input_sha256'],'retention_sha256':before_hash,'baseline_vectors_sha256':sha256_file(root/c['baseline_vectors']),
        'implementation_sha256':{p:sha256_file(root/p) for p in ['src/datascape/strokes/mass_density.py','src/datascape/rendering/mass_density_study.py']},
        'composition':'Unchanged F2-C, 70/30 foreground, original DEM, current mist and vegetation',
        'diagnostic_styles':'Opaque role colors and width normalization exist only in diagnostic renders; not in production vector data'}
    publish_vectors(out/'v2_strokes.json.gz',updated,provenance);updated=read_vectors(out/'v2_strokes.json.gz')['strokes']
    for name,ss in [('baseline',parent),('v2',updated)]:
        print('Render '+name,flush=True);render(ss,out/f'{name}_production.png',c)
        physical_pair(out/f'{name}_production.png',out/f'{name}_physical.png')
        readable(ss,out/f'{name}_layers.png');readable(ss,out/f'{name}_A_only.png','A')
        for role,bounds in c['detail_crops_mm'].items():
            pixels=(1100,round(1100*(bounds[3]-bounds[1])/(bounds[2]-bounds[0])))
            render(ss,out/f'{name}_{role}_production.png',c,bounds=tuple(bounds),pixels=pixels)
            readable(ss,out/f'{name}_{role}_layers.png',bounds=tuple(bounds),pixels=pixels)
            readable(ss,out/f'{name}_{role}_A_only.png','A',tuple(bounds),pixels)
    readable([s for s in parent if s['layer']=='C'],out/'C_only_readable.png','C')
    for name,ss in [('baseline',raw0),('v2',raw)]:
        vv=finalize([s['xy_mm'] for s in ss],name+'-A-unattenuated',.32,{'layer':'A','preview_opacity':.82})
        publish_vectors(out/f'{name}_A_candidates.json.gz',vv,{**provenance,'diagnostic_only':True,'note':'Unattenuated proposals, not a whitespace-safe production drawing'})
        readable(vv,out/f'{name}_A_before_mist.png','A',(0,205,600,565),(1500,900))
    compare({'v1 baseline':out/'baseline_production.png','v2 local rhythm':out/'v2_production.png'},out/'production_comparison.png','Same production alpha / B C D V / foreground A')
    compare({'A gray / B purple / C blue / D red':out/'v2_layers.png','Frozen C only, opaque diagnostic':out/'C_only_readable.png'},out/'C_readability.png','Diagnostic C: 0.60 mm / alpha 1; production C: 0.16 mm / unchanged alpha. Same paths.')
    compare({'v1 A':out/'baseline_A_only.png','v2 A':out/'v2_A_only.png'},out/'A_density_comparison.png','Actual opaque A centerlines / equal diagnostic width / same omission field')
    compare({'v1 before mist':out/'baseline_A_before_mist.png','v2 before mist':out/'v2_A_before_mist.png'},out/'before_mist_comparison.png','Spacing rhythm exists before the unchanged mist transfer',(0,205,600,565))
    bounds=tuple(c['detail_crops_mm']['mountain'])
    compare({'v1 A':out/'baseline_mountain_A_only.png','v2 A':out/'v2_mountain_A_only.png'},out/'mountain_A_comparison.png','Mountain-relative spacing / opaque normalized-width paths',bounds)
    records=mass_metrics(fixed,mass,fields,baseline_a,a,raw0,raw);field_diagnostics(fixed,mass,fields,out);examples=cadence_diagnostic(fixed,mass,fields,records,out)
    probes=probe_diagrams(fixed,mass,examples,{'v1 before mist':raw0,'v2 before mist':raw,'v1 after mist':baseline_a,'v2 after mist':a},out)
    # Four independent layer panels make C readable without production alpha.
    fig,axes=plt.subplots(1,4,figsize=(13,6))
    for ax,k in zip(axes,['A','B','C','D']):
        p=out/f'layer_{k}_readable.png';readable([s for s in updated if s['layer']==k],p)
        ax.imshow(Image.open(p));ax.set_title(k+' / '+{'A':'body','B':'structure','C':'grain','D':'skeleton'}[k]);ax.axis('off')
    fig.suptitle('Opaque diagnostic layers; actual production styles remain unchanged');fig.tight_layout();save(fig,out/'separate_layers.png')
    write_svg(updated,out/'v2_production.svg',c,'composite')
    assert before_hash==hashlib.sha256(fixed['retention'].tobytes()).hexdigest()
    record={'study':c['study'],'provenance':provenance,'config':c,'masses':mass['masses'],'phase_integration':fields['integration'],'local_band_metrics':records,
        'highlighted_forms':examples,'spacing_probes':probes,'selection':selection_record,'metrics':{'baseline':metrics(parent,fixed['base']),'v2':metrics(updated,fixed['base'])},
        'screen_A_spacing':{'baseline':crossing_spacing(parent,fixed['base']),'v2':crossing_spacing(updated,fixed['base'])},
        'overlap':{'baseline':overlap(parent),'v2':overlap(updated)},
        'invariants':{'B_C_D_V_identical_except_draw_index':True,'foreground_A_inherited_exactly':True,'retention_float64_unchanged':True,'bottom_2mm_empty':True,
            'terrain_zero_cores_empty':True,'nonpositive_phase_derivative_pixels':0,'no_new_objects_colors_or_Gcode':True},
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__}}
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
