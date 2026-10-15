"""Color-ready density, visible terminal D and intrinsic internal B on F2-C."""
from pathlib import Path
import argparse,json,io,hashlib,platform
from copy import deepcopy
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from datascape.data.quality import sha256_file
from datascape.projection.ground import GroundComposite
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,sample,resample
from datascape.strokes.generators import terrain_derivatives,structure_lines
from datascape.strokes.hierarchy import total_length
from datascape.strokes.color_ready import density_presets,visible_supports,terminal_d,mist_context,internal_b,boundary_relation
from datascape.vegetation.object_prototypes import generate
from datascape.rendering.grammar_study import ordered,panel_gap,validate,describe
from datascape.rendering.hierarchy_study import publish_png,publish_vectors,comparison,metrics
from datascape.rendering.ground_study import make_camera

COLORS={'A':'#62676e','B':'#9b59b6','C':'#4591bc','D':'#d54335','V':'#14866d','R':'#bd792c'}


def styled_segments(strokes,mode,config):
    """Geometry and width are invariant; only simulated alpha/color changes."""
    lines=[];widths=[];colors=[]
    for s in strokes:
        p=np.array(s['xy_mm']);n=len(p);w=np.asarray(s.get('width_profile_mm',[s['width_mm']]*n))
        original=np.asarray(s.get('opacity_profile',[s.get('preview_opacity',1)]*n))
        layer='R' if s.get('procedural_object')=='rock' else s['layer']
        if mode=='black':opacity=np.ones(n);color='black'
        elif mode=='layers':opacity=np.maximum(.25,original);color=COLORS[layer]
        elif mode=='vegetation':opacity=np.maximum(.25,original) if s['layer']=='V' else original*.35;color=COLORS[layer] if s['layer']=='V' else 'black'
        else:
            base=max(s.get('preview_opacity',1),1e-8)
            opacity=np.clip(original/base,0,1)*config['preview_opacity'][s['layer']];color='black'
        if 'width_profile_mm' in s or 'opacity_profile' in s:
            for i in range(n-1):
                lines.append(p[i:i+2]);widths.append(float((w[i]+w[i+1])/2));colors.append(matplotlib.colors.to_rgba(color,float((opacity[i]+opacity[i+1])/2)))
        else:lines.append(p);widths.append(float(w[0]));colors.append(matplotlib.colors.to_rgba(color,float(opacity[0])))
    return lines,np.array(widths),colors


def render(strokes,path,config,mode='composite',bounds=(0,0,600,900),pixels=(1200,1800)):
    pw,ph=pixels;x0,y0,x1,y1=bounds;fig=plt.figure(figsize=(pw/150,ph/150),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    lines,widths,colors=styled_segments(strokes,mode,config)
    ax.add_collection(LineCollection(lines,linewidths=widths*pw/(x1-x0)*72/150,colors=colors,capstyle='round',joinstyle='round'))
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150,facecolor='white');plt.close(fig);publish_png(buf.getvalue(),path)


def write_svg(strokes,path,config,mode='composite',panel=None):
    """Store canonical path vertices once and reuse them for profile intervals."""
    width=300 if panel else 600;shift=300 if panel==2 else 0
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="900mm" viewBox="0 0 {width} 900">','<rect width="100%" height="100%" fill="white"/>','<g fill="none" stroke-linecap="round" stroke-linejoin="round">']
    for s in strokes:
        if panel and s['panel']!=panel:continue
        pp,ww,cc=styled_segments([s],mode,config)
        for i,(p,w,c) in enumerate(zip(pp,ww,cc)):
            p=np.array(p);p[:,0]-=shift;color=matplotlib.colors.to_hex(c[:3]);xy=' '.join(f'{x:g},{y:g}' for x,y in p)
            lines.append(f'<polyline id="{s["id"]}-{i}" points="{xy}" stroke="{color}" stroke-width="{w:.6g}" stroke-opacity="{c[3]:.6g}"/>')
    Path(path).write_text('\n'.join(lines+['</g>','</svg>'])+'\n')


def overlap(strokes):
    """Sampled convergence diagnostic, including legitimate transverse crossings."""
    cells={};points=[];owners=[]
    for i,s in enumerate(strokes):
        if s['layer']=='V':continue
        p=resample(s['xy_mm'],.7)
        for key in set(map(tuple,np.floor(p).astype(int))):cells.setdefault(key,set()).add(i)
        q=resample(s['xy_mm'],2);points.extend(q);owners.extend([i]*len(q))
    vals=np.array([len(v) for v in cells.values()]);spacing=[]
    if points:
        p=np.array(points);owners=np.array(owners);idx=np.arange(0,len(p),max(1,len(p)//6000));dist,ids=cKDTree(p).query(p[idx],k=min(40,len(p)))
        for j,d,ii in zip(idx,dist,ids):
            mask=owners[ii]!=owners[j]
            if mask.any():spacing.append(float(d[mask].min()))
    return {'occupied_one_mm_cells':len(cells),'multiple_path_cell_fraction':float(np.mean(vals>1)) if len(vals) else 0,
            'maximum_paths_per_cell':int(vals.max()) if len(vals) else 0,'sampled_other_path_spacing_mm_p10_p50_p90':np.percentile(spacing,[10,50,90]).tolist() if spacing else [],
            'interpretation':'Sampled screen centerlines; crossings and panel-seam neighbors count, not an exact collision proof.'}


def edge_diagnostic(raw,selected,fields,fixed,out):
    fig,axes=plt.subplots(1,2,figsize=(10,8))
    for ax in axes:
        ax.set(xlim=(0,600),ylim=(650,180),aspect='equal');ax.set_xlabel('mm');ax.set_ylabel('mm')
        ax.imshow(np.where(fixed['base']['occupied'],.96,1),cmap='gray',vmin=0,vmax=1,extent=[0,600,900,0])
    for kind,p in raw:axes[0].plot(p[:,0],p[:,1],lw=.5,color={'skyline':'#348fc0','occlusion':'#51b39c','visible_crest':'#b383c4','rock_edge_proxy':'#c09950'}[kind],alpha=.8)
    axes[0].set_title('Read-only projected visible-edge supports')
    for kind,p in raw:axes[1].plot(p[:,0],p[:,1],lw=.35,color='#bac8cd',alpha=.6)
    for i,s in enumerate(selected):
        p=np.array(s['xy_mm']);axes[1].plot(p[:,0],p[:,1],lw=1.4,color=COLORS['D']);mid=p[len(p)//2];axes[1].text(*mid,str(i+1),fontsize=7)
    axes[1].set_title('Selected connected D / parent continuity')
    fig.suptitle('D is generated from F2 visibility, not the user annotation or mist contours');fig.tight_layout();buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150);plt.close(fig);publish_png(buf.getvalue(),out/'D_edge_diagnostic.png')


def compare_crops(images,path,title,bounds):
    x0,y0,x1,y1=bounds;fig,axes=plt.subplots(1,len(images),figsize=(4*len(images),4*(y1-y0)/(x1-x0)+1.0))
    for ax,(label,p) in zip(np.atleast_1d(axes),images.items()):
        ax.imshow(Image.open(p),extent=[x0,x1,y1,y0]);ax.set_title(label,fontsize=10);ax.set_xlabel('mm')
    fig.suptitle(title);fig.tight_layout();buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150);plt.close(fig);publish_png(buf.getvalue(),path)


def run(master,veg,config_path,output,repo_root=None):
    cp=Path(config_path);root=Path(repo_root) if repo_root else cp.resolve().parents[2];c=json.loads(cp.read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    for p,h in c['locked_source_sha256'].items():assert sha256_file(root/p)==h,p
    print('Verify unchanged F2-C',flush=True);selection=json.loads((root/c['selection']).read_text());fixed=load_selected_scene(master,veg,root,selection)
    fixed['_grammar_safe']=distance_transform_edt((fixed['retention']>1e-8)&fixed['base']['occupied']);fixed['_grammar_xyz']=np.nan_to_num(fixed['base']['xyz'])
    parent=read_vectors(root/c['current_vectors'])['strokes'];pc=json.loads((root/c['parent_config']).read_text());hc=json.loads((root/pc['hierarchy_config']).read_text());vc=json.loads((root/pc['vector_config']).read_text())
    derivative=terrain_derivatives(master,fixed['base'],hc['derivatives'])
    import rasterio
    sc=fixed['scene']
    with rasterio.open(master) as ds:camera,site=make_camera(ds,sc['primary_eye_xy_m'],sc['look_target_xy_m'],sc['eye_clearance_m'],sc['pitch_deg'],sc['vertical_fov_deg'],sc['near_m'])
    projection=GroundComposite(camera,site['source_dem_at_eye_m'],**sc['composite'])
    print('Nested physical density presets',flush=True);presets,density_record=density_presets(parent,fixed,root,c,pc,hc)
    sets={}
    for name,layers in presets.items():sets['density_'+name]=ordered(*(layers[k] for k in ['C','A','B','V','D']))
    color=presets['color_ready'];body=color['C']+color['A']+color['B']+color['V']
    print('Visible render-space D',flush=True);raw,edge_fields,edge_record=visible_supports(fixed,derivative,projection,c)
    d1,d1record=terminal_d(raw,edge_fields,fixed,color['A'],body,c,False);d2,d2record=terminal_d(raw,edge_fields,fixed,color['A'],body,c,True)
    sets['D_current']=sets['density_color_ready'];sets['D_screen']=ordered(color['C'],color['A'],color['B'],color['V'],d1);sets['D_connected']=ordered(color['C'],color['A'],color['B'],color['V'],d2)
    print('Unmasked intrinsic B and inward/orientation retreat',flush=True)
    raw_b,source_counts=structure_lines(fixed['base'],derivative,vc['structure'],camera.azimuth_deg);context=mist_context(fixed,color['A'],c)
    b2,b_record=internal_b(raw_b,fixed,derivative,color['A'],c,context)
    sets['B_old']=sets['D_connected'];sets['B_internal']=ordered(color['C'],color['A'],b2,color['V'],d2)
    print('Independent limited hero/rock prototype',flush=True);vegetation,rocks,obj_record=generate(fixed,color['V'],derivative,c,projection)
    # The primary choice does not depend on adopting the separate object prototype.
    sets['recommended']=sets['B_internal'];sets['object_prototype']=ordered(color['C'],color['A'],b2,vegetation,rocks,d2)
    provenance={'study':c['study'],'config_sha256':sha256_file(cp),'parent_commit':c['parent_commit'],'input_sha256':selection['input_sha256'],'seed':c['seed'],
                'frozen_selection_sha256':sha256_file(root/c['selection']),'opacity_interpretation':'Display simulation only; not dried ink or calibrated pressure','composition':'F2-C camera/projection/70-30/fields unchanged'}
    provenance['implementation_sha256']={p:sha256_file(root/p) for p in ['src/datascape/strokes/color_ready.py','src/datascape/rendering/color_ready_study.py','src/datascape/vegetation/object_prototypes.py']}
    for name,strokes in sets.items():
        print('Render '+name,flush=True);validate(strokes,fixed)
        for s in strokes:
            samples=s.get('expression',{}).get('intensity_samples')
            if samples is not None:assert len(samples)==len(s['xy_mm']) and np.isfinite(samples).all()
        publish_vectors(out/f'{name}.json.gz',strokes,provenance)
        # Every final image reads the saved canonical vector records.
        sets[name]=read_vectors(out/f'{name}.json.gz')['strokes'];render(sets[name],out/f'{name}_composite.png',c)
    for name in ['density_current','density_ink_dominant','density_color_ready','recommended']:
        render(sets[name],out/f'{name}_black.png',c,'black')
    render(sets['recommended'],out/'recommended_layers.png',c,'layers');render(sets['object_prototype'],out/'object_prototype_colored.png',c,'vegetation')
    for name in ['recommended','object_prototype']:
        panel_gap(out/f'{name}_composite.png',out/f'{name}_physical.png')
    for mode in ['black','composite']:write_svg(sets['recommended'],out/f'recommended_{mode}.svg',c,mode)
    for panel in [1,2]:write_svg(sets['recommended'],out/f'recommended_panel_{panel}.svg',c,'composite',panel)
    comparison({name:out/f'density_{name}_black.png' for name in ['current','ink_dominant','color_ready']},out/'density_comparison.png','Actual opaque paths | only A/C geometry density changes')
    comparison({'Actual paths':out/'recommended_black.png','Transparency-aware':out/'recommended_composite.png','Layer diagnostic':out/'recommended_layers.png'},out/'preview_modes.png','Same canonical vectors / same width profiles / display alpha separated')
    comparison({name:out/f'D_{name}_composite.png' for name in ['current','screen','connected']},out/'D_comparison.png','Same color-ready A/B/C/V | only D placement and breathing change')
    comparison({'Old B':out/'B_old_composite.png','Internal B':out/'B_internal_composite.png'},out/'B_comparison.png','Same color-ready A/C/D/V | intrinsic B candidates, mist retreat after extraction')
    edge_diagnostic(raw,d2,edge_fields,fixed,out)
    for name in ['density_current','density_ink_dominant','density_color_ready','D_current','D_screen','D_connected','B_old','B_internal','recommended','object_prototype']:
        for role,bounds in c['detail_crops_mm'].items():
            render(sets[name],out/f'{name}_{role}.png',c,'vegetation' if name=='object_prototype' else 'composite',tuple(bounds),(900,600))
    for group,names,role,title in [('density',['density_current','density_ink_dominant','density_color_ready'],'foreground','Actual foreground geometry | A/C density only'),('D',['D_current','D_screen','D_connected'],'ridge','Visible terminal edge placement and path breathing'),('B',['B_old','B_internal'],'middle','B inside surviving A; avoid parallel mist outlines')]:
        compare_crops({name:out/f'{name}_{role}.png' for name in names},out/f'{group}_detail_comparison.png',title,c['detail_crops_mm'][role])
    old_icon=read_vectors(root/pc['hierarchy_pool'])['strokes'];old_icon=[s for s in old_icon if s['layer']=='V']
    vegetation_sets={'old_icons':old_icon,'current':color['V'],'prototype':vegetation+rocks}
    for name,vs in vegetation_sets.items():render(vs,out/f'vegetation_{name}.png',c,'layers',tuple(c['object_crop_mm']),(900,1000))
    compare_crops({name:out/f'vegetation_{name}.png' for name in vegetation_sets},out/'vegetation_comparison.png','Objects only / existing root sites / prototype is separate',c['object_crop_mm'])
    layer_fig,axes=plt.subplots(1,5,figsize=(15,7))
    for ax,k in zip(axes,['A','B','C','D','V']):
        path=out/f'layer_{k}.png';render([s for s in sets['recommended'] if s['layer']==k],path,c,'layers');ax.imshow(Image.open(path));ax.set_title(k);ax.axis('off')
    layer_fig.suptitle('Diagnostic colors only / intended artwork preview remains black');layer_fig.tight_layout();buf=io.BytesIO();layer_fig.savefig(buf,format='png',dpi=150);plt.close(layer_fig);publish_png(buf.getvalue(),out/'layer_diagnostics.png')
    bm={name:boundary_relation(ss,context,fixed,c) for name,ss in [('old',color['B']),('internal',b2)]}
    record={'study':c['study'],'provenance':provenance,'config':c,'density_changes':density_record,'metrics':{name:metrics(ss,fixed['base']) for name,ss in sets.items()},
            'D':{'candidate_extraction':edge_record,'screen':d1record,'connected':d2record,'path_metrics':{name:describe(s) for name,s in [('current',color['D']),('screen',d1),('connected',d2)]},
                 'annotation_not_used_as_generation_input':True,'source_surface_edges_first':True},
            'B':{'source_counts':source_counts,'selection':b_record,'boundary_relation':bm},'objects':obj_record,
            'overlap':{k:overlap(sets[k]) for k in ['density_current','density_color_ready','density_ink_dominant','recommended']},
            'invariants':{'selected_C_image_exact':True,'retention_archive_exact':True,'input_hashes_match':True,'terrain_zero_core_violations':0,'nominal_bottom_2mm_empty':True,
                          'density_only_B_D_V_identical':all(presets[k][j]==presets['current'][j] for k in ['color_ready','ink_dominant'] for j in ['B','D','V']),
                          'same_dataset_for_black_and_transparency':True,'no_final_color_or_Gcode':True},
            'versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__}}
    assert record['metrics']['recommended']['D_all_length_fraction']<=.06
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'density':density_record,'D':record['D'],'B':bm,'invariants':record['invariants']},indent=2),flush=True)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
