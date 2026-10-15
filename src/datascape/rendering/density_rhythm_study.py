"""Reproducible A-density study on locked F2-C, with frozen B/D/V vectors."""
from pathlib import Path
import argparse,json,io,hashlib,platform
import numpy as np
from scipy.ndimage import distance_transform_edt,gaussian_filter
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.data.quality import sha256_file
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,resample,sample,finalize
from datascape.strokes.generators import terrain_derivatives
from datascape.strokes.density_rhythm import build_sets,layer_digest
from datascape.rendering.grammar_study import validate
from datascape.rendering.hierarchy_study import publish_vectors,publish_png,metrics
from datascape.rendering.color_ready_study import render,write_svg,compare_crops,overlap
from datascape.rendering.ground_study import make_camera
from datascape.projection.ground import GroundComposite


def save_figure(fig,path):
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150);plt.close(fig);publish_png(buf.getvalue(),path)


def length_map(strokes,cell_mm=20):
    """Actual centerline length / paper area, independent of display alpha."""
    out=np.zeros((int(900/cell_mm),int(600/cell_mm)))
    for s in strokes:
        p=resample(s['xy_mm'],.5);mid=(p[:-1]+p[1:])/2;dl=np.linalg.norm(np.diff(p,axis=0),axis=1)
        ij=np.floor(mid/cell_mm).astype(int);x=np.clip(ij[:,0],0,out.shape[1]-1);y=np.clip(ij[:,1],0,out.shape[0]-1)
        np.add.at(out,(y,x),dl/cell_mm**2)
    return out


def crossing_spacing(strokes,base):
    """Vertical-probe A gaps in screen mm, not a pressure/opacity estimate.

    Compare distinct source-depth rows on the same surface. Omission gaps
    remain in the measurement; projected occlusion jumps are excluded.
    """
    gaps={'near':[],'middle':[],'far':[]}
    for x in np.arange(30,600,30)+.37:
        hits=[]
        for s in strokes:
            if s['layer']!='A':continue
            p=np.asarray(s['xy_mm']);a,b=p[:-1],p[1:];dx=b[:,0]-a[:,0]
            ids=np.flatnonzero((np.minimum(a[:,0],b[:,0])<=x)&(np.maximum(a[:,0],b[:,0])>x)&(np.abs(dx)>1e-8))
            for i in ids:hits.append(a[i,1]+(x-a[i,0])/dx[i]*(b[i,1]-a[i,1]))
        y=np.sort(hits)
        if len(y)<2:continue
        p=np.column_stack([np.full(len(y),x),y]);q=sample(base['depth_m'],p);dy=np.diff(y);dq=np.abs(np.diff(q))
        valid=(dy>.1)&(dy<30)&(dq>4)&(dq<150)
        qmid=(q[:-1]+q[1:])/2
        for k,lo,hi in [('near',0,1600),('middle',1600,3400),('far',3400,np.inf)]:gaps[k].extend(dy[valid&(qmid>=lo)&(qmid<hi)].tolist())
    return {k:{'samples':len(v),'p10_p50_p90_mm':np.percentile(v,[10,50,90]).tolist() if v else []} for k,v in gaps.items()}


def density_metrics(strokes,fixed,crops):
    layers={k:[s for s in strokes if s['layer']==k] for k in ['A','C']};result={}
    b=fixed['base'];roles={'near':b['occupied']&(b['depth_m']<1600),'middle':b['occupied']&(b['depth_m']>=1600)&(b['depth_m']<3400),'far':b['occupied']&(b['depth_m']>=3400)}
    for k,ss in layers.items():
        one=length_map(ss,1);result[k]={}
        for role,m in roles.items():result[k][role]={'source_visible_area_mm2':int(m.sum()),'path_length_mm':float(one[m].sum()),'length_per_visible_mm2':float(one[m].mean())}
        result[k]['screen_crops']={}
        for name,(x0,y0,x1,y1) in crops.items():
            a=one[y0:y1,x0:x1];result[k]['screen_crops'][name]={'length_mm':float(a.sum()),'length_per_paper_mm2':float(a.mean())}
    result['A_vertical_probe_spacing']=crossing_spacing(strokes,b)
    return result


def physical_pair(source,path):
    """Insert 40 physical mm at the actual render pixel/mm scale."""
    with Image.open(source) as im:a=np.asarray(im.convert('RGB'))
    gap=int(round(a.shape[1]*40/600));paper=np.full((a.shape[0],gap,3),225,np.uint8)
    buf=io.BytesIO();Image.fromarray(np.concatenate([a[:,:a.shape[1]//2],paper,a[:,a.shape[1]//2:]],1)).save(buf,format='PNG');publish_png(buf.getvalue(),path)


def compare(images,path,title,bounds=(0,0,600,900)):
    x0,y0,x1,y1=bounds;fig,axes=plt.subplots(1,len(images),figsize=(4*len(images),4*(y1-y0)/(x1-x0)+.9))
    for ax,(label,image) in zip(np.atleast_1d(axes),images.items()):
        ax.imshow(Image.open(image),extent=[x0,x1,y1,y0]);ax.set_title(label,fontsize=10);ax.set_xlabel('mm');ax.set_aspect('equal')
    fig.suptitle(title,fontsize=11);fig.tight_layout();save_figure(fig,path)


def diagnostic(profile,pre,post,fixed,out):
    raw_a=pre['A'];after=[s for s in post if s['layer']=='A'];before=length_map(raw_a);actual=length_map(after)
    rho=profile['density'];r=fixed['retention'];occ=fixed['base']['occupied']
    fig,axes=plt.subplots(2,3,figsize=(12,12))
    panels=[('A source-row density / 20m reference',np.where(occ,rho,np.nan),0,2.1),('Existing retention R (unchanged)',np.where(occ,r,np.nan),0,1),('Density x R (diagnostic target only)',np.where(occ,rho*r,np.nan),0,2.1),
        ('Actual A before mist: mm/mm2',before,0,.9),('Actual A after mist: mm/mm2',actual,0,.9),('Actual removed length / before',np.where(before>0,np.clip(1-actual/np.maximum(before,1e-9),0,1),np.nan),0,1)]
    for ax,(title,a,lo,hi) in zip(axes.ravel(),panels):
        im=ax.imshow(a,extent=[0,600,900,0],vmin=lo,vmax=hi,cmap='viridis');ax.set_title(title,fontsize=9);fig.colorbar(im,ax=ax,shrink=.65);ax.set_xlabel('mm')
    fig.suptitle('Geometry density and mist are separate | no shading enters final previews');fig.tight_layout();save_figure(fig,out/'density_mist_diagnostic.png')
    fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True)
    axes[0].plot(profile['q_m'],profile['peak_elevation_m']);axes[0].set_ylabel('Row p95 height (m)')
    axes[1].plot(profile['q_m'],profile['signal']);axes[1].set_ylabel('Terrain signal [0,1]')
    axes[2].plot(profile['q_m'],profile['pitch_m']);axes[2].axhline(20,color='gray',ls='--',label='Original regular source pitch');axes[2].set_ylabel('New source pitch (m)');axes[2].set_xlabel('Source forward depth (m)');axes[2].legend()
    fig.suptitle('Inverse-quadratic spacing follows local relief / ridge / slope; no random wave');fig.tight_layout();save_figure(fig,out/'source_spacing_profile.png')


def run(master,veg,config_path,output,repo_root=None,prepared=None):
    cp=Path(config_path);root=Path(repo_root) if repo_root else cp.resolve().parents[2];c=json.loads(cp.read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    for p,h in c['locked_source_sha256'].items():assert sha256_file(root/p)==h,p
    selection=json.loads((root/c['selection']).read_text());pc=json.loads((root/c['parent_config']).read_text())
    if prepared is None:
        print('Reproduce unchanged selected F2-C',flush=True);fixed=load_selected_scene(master,veg,root,selection)
        fixed['_grammar_safe']=distance_transform_edt((fixed['retention']>1e-8)&fixed['base']['occupied']);fixed['_grammar_xyz']=np.nan_to_num(fixed['base']['xyz'])
        derivative=terrain_derivatives(master,fixed['base'],{'derivative_sigma_m':60});sc=fixed['scene'];import rasterio
        with rasterio.open(master) as ds:camera,site=make_camera(ds,sc['primary_eye_xy_m'],sc['look_target_xy_m'],sc['eye_clearance_m'],sc['pitch_deg'],sc['vertical_fov_deg'],sc['near_m'])
        projection=GroundComposite(camera,site['source_dem_at_eye_m'],**sc['composite'])
    else:fixed,derivative,projection=(prepared[k] for k in ['fixed','derivative','projection'])
    parent=read_vectors(root/c['parent_vectors'])['strokes'];retention_hash=hashlib.sha256(fixed['retention'].tobytes()).hexdigest()
    print('Generate terrain-responsive A / depth-specific C',flush=True);sets,profile,generation,pre=build_sets(parent,fixed,derivative,projection,c,pc)
    provenance={'study':c['study'],'config_sha256':sha256_file(cp),'parent_commit':c['parent_commit'],'seed':c['seed'],'input_sha256':selection['input_sha256'],
        'selection_sha256':sha256_file(root/c['selection']),'retention_float64_sha256':retention_hash,
        'implementation_sha256':{p:sha256_file(root/p) for p in ['src/datascape/strokes/density_rhythm.py','src/datascape/rendering/density_rhythm_study.py']},
        'material_note':'C centerlines and material intent are separate; preview alpha is not physical dilution or calibrated pressure'}
    result={};densities={}
    for name,ss in sets.items():
        print('Render / measure '+name,flush=True);validate(ss,fixed)
        assert len({s['id'] for s in ss})==len(ss),'Duplicate global stroke identity'
        for k in ['B','D','V']:assert layer_digest(ss,k)==layer_digest(parent,k)
        publish_vectors(out/f'{name}.json.gz',ss,provenance);ss=read_vectors(out/f'{name}.json.gz')['strokes'];sets[name]=ss
        for mode in ['black','composite']:render(ss,out/f'{name}_{mode}.png',c,mode)
        physical_pair(out/f'{name}_composite.png',out/f'{name}_physical.png')
        for role,bounds in c['crops_mm'].items():
            x0,y0,x1,y1=bounds;render(ss,out/f'{name}_{role}.png',c,'composite',tuple(bounds),(1040,round(1040*(y1-y0)/(x1-x0))))
        if name!='ink_upper_reference':
            bounds=c['crops_mm']['foreground'];x0,y0,x1,y1=bounds
            for mode in ['black','layers']:
                render(ss,out/f'{name}_foreground_{mode}.png',c,mode,tuple(bounds),(1040,round(1040*(y1-y0)/(x1-x0))))
        result[name]=metrics(ss,fixed['base']);densities[name]=density_metrics(ss,fixed,c['crops_mm'])
    names=['baseline','A_dominant','C_dominant','blended_color_ready']
    compare({n:out/f'{n}_composite.png' for n in names},out/'grammar_comparison.png','Fixed F2-C / B D V | A-density and foreground A/C grammar')
    compare({n:out/f'{n}_foreground.png' for n in names},out/'foreground_comparison.png','Same ground, same whitespace, same vegetation | actual A/C paths',tuple(c['crops_mm']['foreground']))
    compare({n:out/f'{n}_foreground_black.png' for n in names},out/'foreground_black_comparison.png','Opaque vector close-up | opacity cannot hide the geometry',tuple(c['crops_mm']['foreground']))
    compare({n:out/f'{n}_foreground_layers.png' for n in names},out/'foreground_layers_comparison.png','Diagnostic layer colors | gray A, blue C, green existing V',tuple(c['crops_mm']['foreground']))
    compare({n:out/f'{n}_physical.png' for n in names},out/'physical_pair_comparison.png','300 + 300 mm content | 40 mm physical interval', (0,0,640,900))
    compare({n:out/f'{n}_composite.png' for n in ['baseline','blended_color_ready','ink_upper_reference']},out/'production_density_comparison.png','Baseline / color-ready recommendation / ink upper reference')
    compare({n:out/f'{n}_composite.png' for n in ['baseline','A_density_only']},out/'A_density_isolation.png','Only A changes | identical B/C/D/V and identical mist transfer')
    ss=sets['blended_color_ready'];render(ss,out/'recommended_layers.png',c,'layers')
    material_options={'geometry_file':'blended_color_ready.json.gz','C_geometry_ids':[s['id'] for s in ss if s['layer']=='C'],
        'options':{'light_ink':{'role':'Light directional ink support'},'color_support':{'role':'Future color-stroke geometry; no palette color assigned'},'ink_and_color':{'role':'Same centerline family available to both material passes'}},
        'note':'These are material intents, not extra paths or automatic duplicate passes. Physical order/dilution require a separate study.'}
    (out/'C_material_options.json').write_text(json.dumps(material_options,indent=2)+'\n')
    compare({'Opaque actual paths':out/'blended_color_ready_black.png','Display alpha':out/'blended_color_ready_composite.png','Layer diagnostic':out/'recommended_layers.png'},out/'preview_modes.png','Identical geometry and widths | D > B > A > C')
    # Store actual unattenuated proposals for an explicit pre/post comparison.
    raw=pre['blended_color_ready']['A'];raw_strokes=finalize([s['xy_mm'] for s in raw],'A-pre-mist',.32,{'layer':'A','preview_opacity':.82})
    publish_vectors(out/'A_before_mist.json.gz',raw_strokes,{**provenance,'diagnostic_only':True,'note':'Candidate geometry; not a production drawing or whitespace-safe output'})
    render(raw_strokes,out/'A_before_mist.png',c,'black');render([s for s in ss if s['layer']=='A'],out/'A_after_mist.png',c,'black')
    compare({'Actual A candidates':out/'A_before_mist.png','Actual retained / cut A':out/'A_after_mist.png'},out/'mist_vector_comparison.png','Unchanged R attenuates density / length / width / display alpha')
    diagnostic(profile,pre['blended_color_ready'],ss,fixed,out)
    for panel in [1,2]:write_svg(ss,out/f'recommended_panel_{panel}.svg',c,'composite',panel)
    write_svg(ss,out/'recommended_composite.svg',c,'composite')
    write_svg(ss,out/'recommended_black.svg',c,'black')
    assert retention_hash==hashlib.sha256(fixed['retention'].tobytes()).hexdigest()
    record={'study':c['study'],'config':c,'provenance':provenance,'generation':generation,'metrics':result,'local_density':densities,
        'overlap':{n:overlap(sets[n]) for n in ['baseline','blended_color_ready','ink_upper_reference']},
        'source_profile':{k:v.tolist() for k,v in profile.items() if v.ndim==1},
        'invariants':{'retention_float64_unchanged':True,'B_D_V_identical_except_absolute_draw_index':True,'bottom_2mm_empty':True,'terrain_zero_cores_empty':True,
            'original_A_preserved_as_baseline':True,'no_new_object_generator':True,'no_Gcode_or_hardware_action':True,'same_vectors_black_and_alpha':True},
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__}}
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
