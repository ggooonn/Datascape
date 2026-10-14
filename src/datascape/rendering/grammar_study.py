"""Isolated D, mist and vegetation grammar comparisons on frozen F2-C."""
from pathlib import Path
from copy import deepcopy
import argparse,json,io,platform
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from datascape.data.quality import sha256_file
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,resample,sample
from datascape.strokes.hierarchy import total_length
from datascape.strokes.generators import terrain_derivatives,taebaek_rows
from datascape.strokes.grammar import build_connected_d,transfer_mist
from datascape.vegetation.grammar import redesign
from datascape.rendering.hierarchy_study import publish_png,publish_vectors,comparison
from datascape.rendering.composition_study import save_figure
from datascape.rendering.ground_study import make_camera


def render(strokes,path,color_vegetation=True,black=False,bounds=(0,0,600,900),pixels=(1200,1800)):
    lines=[];widths=[];colors=[];x0,y0,x1,y1=bounds;pw,ph=pixels
    for s in strokes:
        p=np.asarray(s['xy_mm']);n=len(p);width=np.asarray(s.get('width_profile_mm',[s['width_mm']]*n))
        opacity=np.asarray(s.get('opacity_profile',[s.get('preview_opacity',1)]*n))
        color='#197568' if color_vegetation and s['layer']=='V' else 'black'
        if black:opacity=np.ones(n)
        if 'width_profile_mm' in s or 'opacity_profile' in s:
            for i in range(n-1):
                lines.append(p[i:i+2]);widths.append((width[i]+width[i+1])/2);colors.append(matplotlib.colors.to_rgba(color,float((opacity[i]+opacity[i+1])/2)))
        else:lines.append(p);widths.append(s['width_mm']);colors.append(matplotlib.colors.to_rgba(color,float(opacity[0])))
    fig=plt.figure(figsize=(pw/150,ph/150),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    ax.add_collection(LineCollection(lines,linewidths=np.array(widths)*pw/(x1-x0)*72/150,colors=colors,capstyle='round',joinstyle='round'))
    buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=150,facecolor='white');plt.close(fig);publish_png(buffer.getvalue(),path)


def svg(strokes,path,color_vegetation=False,panel=None):
    size=300 if panel else 600;shift=300 if panel==2 else 0
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}mm" height="900mm" viewBox="0 0 {size} 900">','<rect width="100%" height="100%" fill="white"/>','<g fill="none" stroke-linecap="round" stroke-linejoin="round">']
    for s in strokes:
        if panel and s['panel']!=panel:continue
        p=np.array(s['xy_mm']);p[:,0]-=shift;n=len(p)
        widths=s.get('width_profile_mm',[s['width_mm']]*n);opacity=s.get('opacity_profile',[s.get('preview_opacity',1)]*n)
        color='#197568' if color_vegetation and s['layer']=='V' else 'black'
        for i in range(n-1):
            xy=' '.join(f'{x:g},{y:g}' for x,y in p[i:i+2]);w=(widths[i]+widths[i+1])/2;a=(opacity[i]+opacity[i+1])/2
            lines.append(f'<polyline id="{s["id"]}-{i}" stroke="{color}" stroke-width="{w:.6g}" stroke-opacity="{a:.6g}" points="{xy}"/>')
    Path(path).write_text('\n'.join(lines+['</g>','</svg>'])+'\n')


def ordered(*groups):
    return [{**s,'draw_order':i} for i,s in enumerate(s for group in groups for s in group)]


def describe(strokes):
    lengths=[float(np.linalg.norm(np.diff(s['xy_mm'],axis=0),axis=1).sum()) for s in strokes]
    return {'vectors':len(strokes),'length_mm':sum(lengths),'path_length_p10_p50_p90_mm':np.percentile(lengths,[10,50,90]).tolist() if lengths else []}


def validate(strokes,fixed):
    for s in strokes:
        p=resample(s['xy_mm'],.18);width=max(s.get('width_profile_mm',[s['width_mm']]))
        assert np.isfinite(p).all()
        assert p[:,1].max()+width/2<898,'Boundary footprint violation'
        if s['layer']!='V':assert np.min(sample(fixed['_grammar_safe'],p,order=0))>width/2+.02,'Terrain core violation'
        for key in ['width_profile_mm','opacity_profile']:
            if key in s:assert len(s[key])==len(s['xy_mm']) and min(s[key])>=0
        if 'opacity_profile' in s:assert max(s['opacity_profile'])<=1


def panel_gap(source,path):
    with Image.open(source) as im:a=np.asarray(im.convert('RGB'));h,w=a.shape[:2]
    buffer=io.BytesIO();Image.fromarray(np.concatenate([a[:,:w//2],np.full((h,80,3),225,np.uint8),a[:,w//2:]],axis=1)).save(buffer,format='PNG');publish_png(buffer.getvalue(),path)


def run(master,veg,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2];c=json.loads(config_path.read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    for path,digest in c['locked_source_sha256'].items():assert sha256_file(root/path)==digest,path
    selection=json.loads((root/c['selection']).read_text());print('Reconstruct frozen F2-C',flush=True)
    fixed=load_selected_scene(master,veg,root,selection);fixed['_grammar_safe']=distance_transform_edt((fixed['retention']>1e-8)&fixed['base']['occupied']);fixed['_grammar_xyz']=np.nan_to_num(fixed['base']['xyz'])
    old=read_vectors(root/c['hierarchy_pool'])['strokes'];layers={k:[s for s in old if s['layer']==k] for k in ['A','B','C','D','V']}
    hc=json.loads((root/c['hierarchy_config']).read_text());derivative=terrain_derivatives(master,fixed['base'],hc['derivatives'])
    import rasterio
    sc=fixed['scene']
    with rasterio.open(master) as ds:camera,_=make_camera(ds,sc['primary_eye_xy_m'],sc['look_target_xy_m'],sc['eye_clearance_m'],sc['pitch_deg'],sc['vertical_fov_deg'],sc['near_m'])
    print('Connect supported D paths',flush=True)
    d1,d2,drecord=build_connected_d(fixed,derivative,camera.azimuth_deg,hc,layers['D'],layers['A']+layers['B']+layers['C']+layers['V'],c)
    print('Regenerate unchanged A proposal grammar, vary only mist transfer',flush=True)
    vc=json.loads((root/c['vector_config']).read_text());raw=taebaek_rows(fixed['base'],vc['taebaek'])
    # Raw A proposals share the old grammar/camera; no old soft fade is reused.
    from datascape.strokes.vector import finalize
    a_raw=finalize(raw,'A-raw',hc['styles']['A']['width_mm'],{'layer':'A','preview_opacity':hc['styles']['A']['density_preview_opacity'],
        'expression':{'intensity':hc['styles']['A']['intensity'],'pressure_calibrated':False}})
    mist={mode:transfer_mist(a_raw,fixed,mode,c) for mode in ['binary','density','combined']}
    print('Redesign vegetation at archived roots',flush=True);new_veg,vrecord=redesign(fixed,c)
    sets={
        'D0_current':ordered(layers['C'],layers['A'],layers['B'],layers['V'],layers['D']),
        'D1_connected':ordered(layers['C'],layers['A'],layers['B'],layers['V'],d1),
        'D2_envelope':ordered(layers['C'],layers['A'],layers['B'],layers['V'],d2),
        'M0_binary':mist['binary'],'M1_density':mist['density'],'M2_combined':mist['combined'],
        'V0_current':ordered(layers['C'],layers['A'],layers['B'],layers['V'],layers['D']),
        'V1_near':ordered(layers['C'],layers['A'],layers['B'],[s for s in new_veg if s['vegetation_role']=='near'],layers['D']),
        'V2_near_middle':ordered(layers['C'],layers['A'],layers['B'],[s for s in new_veg if s['vegetation_role']!='far'],layers['D']),
        'V3_all_depths':ordered(layers['C'],layers['A'],layers['B'],new_veg,layers['D']),
        'proposed':ordered(layers['C'],mist['combined'],layers['B'],new_veg,d2)}
    provenance={'study':c['study'],'config_sha256':sha256_file(config_path),'input_sha256':selection['input_sha256'],'seed':c['seed'],'parent_commit':c['parent_commit'],
        'composition':'Unchanged F2-C / 70-30 / same scalar fields','vegetation_color':'Development diagnostic only; palette unchanged'}
    # One pool retains each isolated experiment; the proposed drawing is standalone.
    for name,strokes in sets.items():
        print('Render '+name,flush=True);validate(strokes,fixed)
        render(strokes,out/f'{name}.png')
    publish_vectors(out/'proposed_strokes.json.gz',sets['proposed'],provenance)
    proposed=read_vectors(out/'proposed_strokes.json.gz')['strokes'];render(proposed,out/'proposed.png')
    render(new_veg,out/'vegetation_only.png')
    for name,items in [('old',layers['V']),('new',new_veg)]:
        render(items,out/f'vegetation_hero_{name}.png',bounds=(390,450,560,650),pixels=(900,1060))
    render(proposed,out/'proposed_monochrome.png',color_vegetation=False)
    for panel in [1,2]:svg(proposed,out/f'proposed_panel_{panel}.svg',panel=panel)
    svg(proposed,out/'proposed.svg');svg(proposed,out/'proposed_development.svg',color_vegetation=True)
    panel_gap(out/'proposed.png',out/'proposed_physical.png')
    for prefix,names,title in [('D',['D0_current','D1_connected','D2_envelope'],'D: current / connected / connected + central envelope'),('M',['M0_binary','M1_density','M2_combined'],'Mist transfer only | same raw A proposals and fixed scalar field'),('V',['V0_current','V1_near','V2_near_middle','V3_all_depths'],'Vegetation grammar only | fixed terrain, teal = development overlay')]:
        comparison({name:out/f'{name}.png' for name in names},out/f'{prefix}_comparison.png',title)
    fig,axes=plt.subplots(3,3,figsize=(13,9))
    for row,(role,bounds) in enumerate(c['mist_crops_mm'].items()):
        for col,name in enumerate(['M0_binary','M1_density','M2_combined']):
            path=out/f'M_{role}_{col}.png';render(sets[name],path,bounds=tuple(bounds),pixels=(900,500))
            axes[row,col].imshow(Image.open(path));axes[row,col].axis('off');axes[row,col].set_title(role+' | '+name)
    fig.suptitle('Same source-depth omission, different vector transfer');fig.tight_layout();save_figure(fig,out/'mist_depth_details.png')
    for prefix,names,bounds,title in [('D',['D0_current','D1_connected','D2_envelope'],c['D_detail_mm'],'Continuous skeleton / internal breathing'),('V',['V0_current','V1_near','V2_near_middle','V3_all_depths'],c['vegetation_detail_mm'],'Same measured roots / redesigned branch and canopy grammar')]:
        fig,axes=plt.subplots(1,len(names),figsize=(4*len(names),5))
        for ax,name in zip(np.atleast_1d(axes),names):
            path=out/f'{name}_detail.png';render(sets[name],path,bounds=tuple(bounds),pixels=(800,900));ax.imshow(Image.open(path));ax.axis('off');ax.set_title(name)
        fig.suptitle(title);fig.tight_layout();save_figure(fig,out/f'{prefix}_details.png')
    # Diagnose the existing depth fields; no new field is authored or exported.
    fig,axes=plt.subplots(1,4,figsize=(13,6))
    for ax,(name,array) in zip(axes,[('Near omission',fixed['old']['near']),('Middle omission',fixed['old']['middle']),('Far omission',fixed['refined']['far']),('Selected C retention',fixed['retention'])]):
        ax.imshow(np.where(fixed['base']['occupied'],array,np.nan),vmin=0,vmax=1,cmap='viridis');ax.set_title(name);ax.axis('off')
    fig.suptitle('Read-only diagnostics | unchanged terrain/depth-defined fields');fig.tight_layout();save_figure(fig,out/'fixed_mist_fields.png')
    record={'study':c['study'],'config':c,'provenance':provenance,'D_connection':drecord,
        'D_metrics':{'current':describe(layers['D']),'connected':describe(d1),'envelope':describe(d2)},
        'mist_metrics':{k:describe(v) for k,v in mist.items()},'vegetation':vrecord,
        'vegetation_metrics':{k:describe([s for s in new_veg if s['vegetation_role']==k]) for k in ['near','middle','far']},
        'proposed_metrics':describe(proposed),'D_proposed_length_fraction':total_length(d2)/total_length(proposed),
        'invariants':{'selected_C_pixels_and_archive_identical':True,'locked_sources_unchanged':all(sha256_file(root/p)==h for p,h in c['locked_source_sha256'].items()),
            'raw_inputs_unchanged':all(sha256_file(p)==selection['input_sha256'][k] for p,k in [(master,'master'),(veg,'vegetation')]),'terrain_zero_core_violations':0,'bottom_2mm_empty':True},
        'comparison_isolation':{'D':'Old A/B/C/V fixed; only D changes','M':'Identical unattenuated A proposal family; B/C/D/V hidden to isolate the transfer','V':'Old A/B/C/D fixed; vegetation alone changes'},
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__}}
    # Store experiment vectors for exact re-rendering, not only the chosen result.
    for name in ['D1_connected','D2_envelope','M0_binary','M1_density','M2_combined','V3_all_depths']:
        publish_vectors(out/f'{name}.json.gz',sets[name],provenance)
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'D':record['D_metrics'],'connections':drecord,'mist':record['mist_metrics'],'vegetation':record['vegetation_metrics'],'D_fraction':record['D_proposed_length_fraction']},indent=2),flush=True)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
