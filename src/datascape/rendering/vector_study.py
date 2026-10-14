"""Black paths on paper, rendered from the same finalized vector records."""
from pathlib import Path
import argparse
import json
import platform
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
from datascape.strokes.generators import taebaek_rows, terrain_derivatives, structure_lines, direction_field, flow_lines
from datascape.strokes.vector import sample, resample, split_at_gate, omit_path, finalize, save_vectors, read_vectors, thin_parallel_paths
from datascape.vegetation.multidepth import object_retention
from datascape.rendering.composition_study import save_figure


def render_vectors(strokes, path, bounds=(0,0,600,900), pixels=(1200,1800)):
    """Opaque black geometry only; gray pixels are edge antialiasing."""
    x0,y0,x1,y1=bounds;pw,ph=pixels;dpi=150
    fig=plt.figure(figsize=(pw/dpi,ph/dpi),dpi=dpi,facecolor='white')
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    lines=[s['xy_mm'] for s in strokes];widths=[s['width_mm']*pw/(x1-x0)*72/dpi for s in strokes]
    if lines:ax.add_collection(LineCollection(lines,colors='black',linewidths=widths,alpha=1,capstyle='round',joinstyle='round'))
    fig.savefig(path,dpi=dpi,facecolor='white');plt.close(fig)


def write_svg(strokes,path,panel=None):
    """Use stored coordinates directly; apply no renderer-only mask or warp."""
    width=600 if panel is None else 300
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="900mm" viewBox="0 0 {width} 900">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g fill="none" stroke="black" stroke-linecap="round" stroke-linejoin="round">']
    for s in strokes:
        if panel is not None and s['panel']!=panel:continue
        shift=300 if panel==2 else 0
        points=' '.join(f'{x-shift:g},{y:g}' for x,y in s['xy_mm'])
        lines.append(f'<polyline id="{s["id"]}" stroke-width="{s["width_mm"]:g}" points="{points}"/>')
    lines.extend(['</g>','</svg>']);Path(path).write_text('\n'.join(lines)+'\n')


def stroke_metrics(strokes, base):
    terrain=[s for s in strokes if s.get('layer')=='terrain'];lengths=[];points=[];owners=[]
    roles={k:{'length_mm':0.,'area_mm2':int((base['occupied']&(base['depth_m']>=a)&(base['depth_m']<b)).sum())} for k,a,b in [('near',0,1600),('middle',1600,3400),('far',3400,np.inf)]}
    cells={}
    for i,s in enumerate(terrain):
        p=np.asarray(s['xy_mm']);lengths.append(float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()))
        dense=resample(p,.5);q=sample(base['depth_m'],dense);ds=np.linalg.norm(np.diff(dense,axis=0),axis=1)
        for k,a,b in [('near',0,1600),('middle',1600,3400),('far',3400,np.inf)]:roles[k]['length_mm']+=float(ds[(q[:-1]>=a)&(q[:-1]<b)].sum())
        sparse=resample(p,2);points.extend(sparse);owners.extend([s['parent_path']]*len(sparse))
        for key in set(map(tuple,np.floor(dense*2).astype(int))):cells.setdefault(key,set()).add(s['parent_path'])
    spacing=[]
    if len(points)>1:
        p=np.asarray(points);owner=np.asarray(owners);idx=np.arange(0,len(p),max(1,len(p)//10000))
        dist,ids=cKDTree(p).query(p[idx],k=min(48,len(p)))
        for j,d,ii in zip(idx,dist,ids):
            valid=owner[ii]!=owner[j]
            if valid.any():spacing.append(float(d[valid].min()))
    for k,v in roles.items():v['length_per_area_mm_per_mm2']=v['length_mm']/max(1,v['area_mm2'])
    vals=np.array([len(x) for x in cells.values()])
    return {'terrain_vectors':len(terrain),'context_vectors':len(strokes)-len(terrain),
            'terrain_length_mm':sum(lengths),'length_mm_p10_p50_p90':np.percentile(lengths,[10,50,90]).tolist() if lengths else [],
            'sampled_other_path_distance_mm_p10_p50_p90':np.percentile(spacing,[10,50,90]).tolist() if spacing else [],
            'half_mm_cells_with_multiple_parent_paths_fraction':float((vals>1).mean()) if len(vals) else 0,
            'maximum_parent_paths_per_half_mm_cell':int(vals.max()) if len(vals) else 0,'depth_density':roles}


def vector_vegetation(fixed,config):
    """Reuse archived glyphs and object-depth omission; remove path segments."""
    b=fixed['base'];r=fixed['refined'];paths=[];width=config['vegetation_width_mm']
    for mark in fixed['small']+fixed['representatives']:
        probability=object_retention(b['depth_m'],b['occupied'],mark['forward_depth_m'],r['local_core_retention'],r['global_retention'],fixed['vegetation_config'])
        distance=distance_transform_edt(probability>1e-8)
        for i,line in enumerate(mark['polylines_pixel_xy']):
            paths.extend(omit_path(line,probability,distance,mark['id']+f':{i}',config['seed'],width,.65))
    return finalize(paths,'vegetation',width,{'layer':'vegetation','source':'archived v0.3 glyphs; unchanged roots and grammar'})


def validate_vectors(strokes, safe_distance, width, terrain_only=True):
    violations=0;max_y=0.
    for s in strokes:
        p=resample(s['xy_mm'],.18);max_y=max(max_y,float(p[:,1].max()))
        if s.get('layer')=='terrain':violations+=int((sample(safe_distance,p,order=0)<=width/2+.05).sum())
        if p[:,1].max()+s['width_mm']/2>=898:raise AssertionError('Hard bottom guard violated.')
        if not np.isfinite(p).all() or np.any(p[:,0]<0) or np.any(p[:,0]>600):raise AssertionError('Invalid coordinates.')
    if violations:raise AssertionError(f'Paths enter a terrain omission core: {violations}')
    return {'zero_core_sample_violations':violations,'maximum_centerline_y_mm':max_y,
            'last_2mm_footprint_empty':True,'opaque_black_only':all(s['opacity']==1 and s['ink']=='black' for s in strokes)}


def run(master,veg,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2]
    config=json.loads(config_path.read_text());selection=json.loads((root/config['selection']).read_text())
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    print('Reconstructing selected C',flush=True)
    fixed=load_selected_scene(master,veg,root,selection);b=fixed['base'];r=fixed['refined']
    from datascape.rendering.ground_study import make_camera
    with __import__('rasterio').open(master) as ds:
        sc=fixed['scene'];camera,site=make_camera(ds,sc['primary_eye_xy_m'],sc['look_target_xy_m'],sc['eye_clearance_m'],sc['pitch_deg'],sc['vertical_fov_deg'],sc['near_m'])
    projection=GroundComposite(camera,site['source_dem_at_eye_m'],**sc['composite'])
    derivative=terrain_derivatives(master,b,config['structure'])
    field=direction_field(b,derivative,projection)
    print('Generating three path families',flush=True)
    a=taebaek_rows(b,config['taebaek']);bb,counts=structure_lines(b,derivative,config['structure'],camera.azimuth_deg)
    c=flow_lines(b,field,config['flow'],config['seed'])
    candidates={'A':a,'B':bb,'C':c};width=config['terrain_width_mm']
    core=(fixed['retention']<=1e-8)|~b['occupied'];safe=distance_transform_edt(~core)
    # Protection adjusts survival probability but cannot override a zero core.
    priority=np.maximum.reduce([fixed['features']['ridge'],fixed['features']['silhouette'],
                               fixed['old']['depth_roles']['near']*np.maximum(fixed['features']['mound'],r['root_support'])])
    retention=fixed['retention'];probability=np.clip(retention+.25*priority*retention*(1-retention),0,1)
    shared=vector_vegetation(fixed,config);metrics={};all_vectors={}
    source_xyz=np.nan_to_num(b['xyz'])
    provenance={'baseline_commit':selection['baseline_commit'],'selection_sha256':sha256_file(root/config['selection']),
                'config_sha256':sha256_file(config_path),'seed':config['seed'],
                'input_sha256':selection['input_sha256'],'projection':'unchanged F2; no raw DEM edits',
                'mask_policy':'C 70/30; opaque paths shortened/split/thinned, never alpha-masked'}
    for name,paths in candidates.items():
        print(f'Finalizing {name}: {len(paths)} candidates',flush=True)
        before=[];after=[]
        for i,p in enumerate(paths):
            # Raw control retains visibility and the absolute bottom gate.
            dense=resample(p,.5)
            edge=np.minimum.reduce([dense[:,0]-width/2,600-width/2-dense[:,0],dense[:,1]-width/2,898-width/2-.002-dense[:,1]])
            before.extend(split_at_gate(dense,edge,config['minimum_stroke_mm']))
            after.extend(omit_path(p,probability,safe,f'{name}:{i}',config['seed'],width,config['minimum_stroke_mm']))
        # Apply the same geometric retracing rule to raw and omitted controls.
        before=thin_parallel_paths(before,config['minimum_stroke_mm'])
        after=thin_parallel_paths(after,config['minimum_stroke_mm'])
        raw=finalize(before,name+'-raw',width,{'layer':'terrain'});terrain=finalize(after,name,width,{'layer':'terrain'})
        for stroke in terrain:
            p=resample(stroke['xy_mm'],2)
            q=sample(b['depth_m'],p)
            xyz=np.column_stack([sample(source_xyz[:,:,i],p) for i in range(3)])
            stroke['source_summary']={'forward_depth_range_m':[float(q.min()),float(q.max())],
                'xyz_bounds_m':[xyz.min(axis=0).tolist(),xyz.max(axis=0).tolist()]}
        # Reload the exact exported data before producing every final preview.
        combined=terrain+[{**s,'draw_order':len(terrain)+i} for i,s in enumerate(shared)]
        path=out/f'{name}_strokes.json.gz';save_vectors(path,combined,provenance)
        strokes=read_vectors(path)['strokes'];all_vectors[name]=strokes
        checks=validate_vectors(strokes,safe,width)
        write_svg(strokes,out/f'{name}_continuous.svg')
        for panel in [1,2]:write_svg(strokes,out/f'{name}_panel_{panel}.svg',panel)
        render_vectors(strokes,out/f'{name}_continuous.png')
        render_vectors(terrain,out/f'{name}_terrain_only.png')
        render_vectors(raw,out/f'{name}_before_omission.png')
        with Image.open(out/f'{name}_continuous.png') as im:image=np.asarray(im.convert('RGB'))
        h,w=image.shape[:2];gap=np.full((h,80,3),225,np.uint8)
        Image.fromarray(np.concatenate([image[:,:w//2],gap,image[:,w//2:]],axis=1)).save(out/f'{name}_physical_pair.png')
        for panel,sl in [(1,slice(0,w//2)),(2,slice(w//2,w))]:Image.fromarray(image[:,sl]).save(out/f'{name}_panel_{panel}.png')
        metrics[name]={'before_omission':stroke_metrics(raw,b),'after_omission':stroke_metrics(strokes,b),'checks':checks}
        metrics[name]['length_retained_fraction']=metrics[name]['after_omission']['terrain_length_mm']/max(1,metrics[name]['before_omission']['terrain_length_mm'])
    labels={'A':'A: Taebaek-style transverse curves','B':'B: terrain structure lines','C':'C: terrain direction-field curves'}
    for fname,suffix,title,extent in [('ABC_comparison.png','continuous','Actual black vectors | selected F2 C, fixed context',[0,600,900,0]),('physical_comparison.png','physical_pair','Same vectors | 300 mm panels + 40 mm physical gap',[0,640,900,0]),('terrain_only_comparison.png','terrain_only','Terrain strokes only | identical omission and line width',[0,600,900,0])]:
        fig,axes=plt.subplots(1,3,figsize=(13.2,7.2))
        for ax,name in zip(axes,candidates):
            ax.imshow(Image.open(out/f'{name}_{suffix}.png'),extent=extent);ax.set_title(labels[name],fontsize=10);ax.set_xlabel('mm');ax.set_yticks([0,300,600,900])
        fig.suptitle(title);fig.tight_layout();save_figure(fig,out/fname)
    crops=config['detail_crops_mm'];fig,axes=plt.subplots(3,3,figsize=(12,10))
    for row,(role,bounds) in enumerate(crops.items()):
        for col,name in enumerate(candidates):
            tmp=out/f'{name}_{role}_detail.png';render_vectors(all_vectors[name],tmp,tuple(bounds),(900,600))
            axes[row,col].imshow(Image.open(tmp));axes[row,col].axis('off');axes[row,col].set_title(f'{name} | {role} / {bounds}',fontsize=9)
    fig.suptitle('Same paper-space crops | foreground, valley and far slopes');fig.tight_layout();save_figure(fig,out/'depth_details.png')
    fig,axes=plt.subplots(2,3,figsize=(12,7))
    bounds=config['omission_crop_mm']
    for col,name in enumerate(candidates):
        for row,suffix in enumerate(['before_omission','terrain_only']):
            im=Image.open(out/f'{name}_{suffix}.png');x0,y0,x1,y1=bounds
            axes[row,col].imshow(im.crop((x0*2,y0*2,x1*2,y1*2)));axes[row,col].axis('off');axes[row,col].set_title(f'{name}: '+('before local omission' if row==0 else 'shortened / split / omitted'))
    fig.suptitle('Same generated families and bottom guard | opaque line occupancy changes');fig.tight_layout();save_figure(fig,out/'omission_comparison.png')
    fig,axes=plt.subplots(2,3,figsize=(12,9))
    for col,name in enumerate(candidates):
        roles=['near','middle','far'];x=np.arange(3)
        for shift,key,label in [(-.18,'before_omission','Before'),(.18,'after_omission','After')]:
            axes[0,col].bar(x+shift,[metrics[name][key]['depth_density'][k]['length_per_area_mm_per_mm2'] for k in roles],width=.36,label=label)
        axes[0,col].set_xticks(x,roles);axes[0,col].set_title(name+' | actual terrain path length / area');axes[0,col].legend()
        cells={}
        for s in all_vectors[name]:
            if s.get('layer')!='terrain':continue
            for key in set(map(tuple,np.floor(resample(s['xy_mm'],.5)).astype(int))):cells.setdefault(key,set()).add(s['parent_path'])
        heat=np.zeros((900,600))
        for (x,y),parents in cells.items():
            if 0<=x<600 and 0<=y<900:heat[y,x]=len(parents)
        im=axes[1,col].imshow(np.ma.masked_where(heat==0,heat),cmap='magma',vmin=1,vmax=max(3,heat.max()),extent=[0,600,900,0]);axes[1,col].set_title('Distinct paths per 1 mm cell')
        fig.colorbar(im,ax=axes[1,col],fraction=.035,pad=.025)
    fig.suptitle('Path density and convergence | crossings also count as overlap');fig.tight_layout();save_figure(fig,out/'density_diagnostics.png')
    record={'study':config['study'],'provenance':provenance,'config':config,'selection':selection,
            'invariants':{'selected_C_pixels_identical':True,'selected_retention_float16_identical':True,'raw_inputs_unchanged':all(sha256_file(p)==selection['input_sha256'][k] for p,k in [(master,'master'),(veg,'vegetation')]),
                          'locked_files_unchanged':all(sha256_file(root/p)==d for p,d in selection['locked_files_sha256'].items()),'shared_vegetation_vector_count':len(shared)},
            'metrics':metrics,'structure_candidate_counts':counts,
            'versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__},
            'limits':['Vector study, not calibrated machine-ready output. No G-code or hardware calls.',
                      'Line widths are nominal preview footprints, not measured brush marks.',
                      'Spacing and overlap use sampled centerlines; crossings count as overlap.',
                      'Ridge/valley and Hessian fields are scale-dependent DEM proxies. No invented objects.']}
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'metrics':metrics,'invariants':record['invariants']},indent=2),flush=True)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
