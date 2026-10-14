"""Combine existing near-retention rules; no new field or projection model."""
from pathlib import Path
import argparse,json
import numpy as np
from PIL import Image
from scipy.ndimage import label
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.data.quality import sha256_file
from datascape.rendering.painterly_layers import load_features,panel_figure
from datascape.rendering.composition_study import save_array,save_figure
from datascape.rendering.multidepth_whitespace import save_fields,save_json
from datascape.rendering.composition_refinement import combine
from datascape.composition.multidepth import source_features,build_reserves
from datascape.composition.refinement import refine_reserves,boundary_retention
from datascape.vegetation.multidepth import render_marks


def blend_existing_and_selective(existing,selective,existing_weight):
    """A convex combination of two existing local retentions, before globals."""
    if not 0<=existing_weight<=1:raise ValueError('Existing near weight must be between zero and one.')
    existing=np.asarray(existing);selective=np.asarray(selective)
    if existing.shape!=selective.shape:raise ValueError('Retention snapshots must share a shape.')
    mixed=existing_weight*existing+(1-existing_weight)*selective
    # Preserve common regions bit for bit, including unchanged far retention.
    return np.where(existing==selective,existing,mixed)


def connectivity_metrics(ink,near_zone,threshold,minimum_pixels):
    """A thresholded preview diagnostic, not geographic access/connectivity."""
    labels,count=label(near_zone&(ink>threshold),structure=np.ones((3,3)))
    sizes=np.bincount(labels.ravel())[1:]
    return {'components_at_least_minimum_pixels':int((sizes>=minimum_pixels).sum()),
        'largest_component_fraction_of_retained_near_pixels':float(sizes.max()/max(sizes.sum(),1)) if count else 0,
        'retained_near_pixel_fraction':float((near_zone&(ink>threshold)).sum()/max(near_zone.sum(),1))}


def root_ground_support(terrain_ink,marks,radius_mm):
    """Measure the same existing root sites in every variant; never place roots."""
    h,w=terrain_ink.shape;radius=max(1,round(radius_mm*w/600));values=[];seen=set()
    for mark in marks:
        if mark['kind']!='near':continue
        key=tuple(mark['root_pixel_xy'])
        if key in seen:continue
        seen.add(key)
        x,y=mark['root_pixel_xy'];row=int(y);col=int(x)
        # A small patch just below the root, where ground contact is read.
        window=terrain_ink[max(0,row):min(h,row+radius+1),max(0,col-radius):min(w,col+radius+1)]
        if window.size:values.append(float(window.mean()))
    return {'sites':len(values),'mean_terrain_ink_below_root':float(np.mean(values)) if values else 0,
            'p10_p50_p90_terrain_ink_below_root':np.percentile(values,[10,50,90]).tolist() if values else []}


def physical_comparison(pairs,path):
    fig,axes=plt.subplots(1,3,figsize=(13,6.8))
    for ax,(name,array) in zip(axes,pairs.items()):
        ax.imshow(array,cmap='gray',vmin=0,vmax=1,extent=[0,640,900,0]);ax.set_title(name,fontsize=11)
        ax.set_xlabel('Installed width (mm)');ax.set_xticks([0,300,340,640])
        ax.tick_params(axis='x',labelrotation=45,labelsize=9)
    axes[0].set_ylabel('Painted height (mm)');fig.suptitle('Same painting split into 300 mm panels | 40 mm physical gap',fontsize=13)
    fig.tight_layout();save_figure(fig,path)


def run(master_path,veg_path,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2]
    config=json.loads(config_path.read_text());v03_path=root/config['source_config'];v03=json.loads(v03_path.read_text())
    v02_path=root/v03['source_config'];v02=json.loads(v02_path.read_text())
    scene_path=root/v02['source_composition'];scene=json.loads(scene_path.read_text());layer=json.loads((root/v02['source_layer_config']).read_text())
    previous=root/config['previous_results'];output=Path(output);output.mkdir(parents=True,exist_ok=True)
    old_hashes={}
    for folder in [previous,root/v03['previous_results'],root/v02['previous_results']]:
        for p in folder.iterdir():
            if p.is_file() and '.writing.' not in p.name:old_hashes[p.relative_to(root).as_posix()]=sha256_file(p)
    terrain,base,_,_,source=load_features(master_path,veg_path,scene,layer)
    raw=1-terrain['shade'];occupied=base['occupied'];w,h=scene['raster_pixels']
    with Image.open(root/layer['baseline_image']) as im:baseline=np.asarray(im)
    assert np.array_equal(np.round(terrain['shade']*255).astype(np.uint8),baseline),'F2 baseline changed.'
    features=source_features(master_path,base,{**v02['terrain'],'seed':v02['seed']})
    old=build_reserves(base,features,v02)
    small=json.loads((root/v03['previous_results']/'marks.json').read_text())['marks']
    r=refine_reserves(base,old,small,v03,v02)
    reps=json.loads((previous/'representative_trees.json').read_text())['representatives']
    small_ink,_,small_depth=render_marks(small,base,r,v02['vegetation'])
    rep_ink,_,rep_depth=render_marks(reps,base,r,v02['vegetation'])
    vegetation=combine(small_ink,rep_ink)
    local={'A':r['local_core_retention'],'B':r['legacy_local_retention']}
    local['C']=blend_existing_and_selective(local['B'],local['A'],config['existing_near_weight'])
    retention={name:value*r['global_retention'] for name,value in local.items()}
    terrain_inks={name:raw*value for name,value in retention.items()}
    final_inks={name:combine(value,vegetation) for name,value in terrain_inks.items()}
    images={name:1-value for name,value in final_inks.items()}
    with Image.open(previous/'C_continuous.png') as im:archived=np.asarray(im)
    assert np.array_equal(np.round(images['A']*255).astype(np.uint8),archived),'v0.3 C did not reproduce.'
    common_depth=occupied&(old['depth_roles']['near']==0)
    outside_near_max=float(np.max(np.abs(retention['B'][common_depth]-retention['A'][common_depth])))
    assert outside_near_max==0,'A/B differ outside the existing near role.'
    assert np.array_equal(retention['C'][common_depth],retention['A'][common_depth]),'C changes the common non-near retention.'
    for name in images:
        assert np.all(terrain_inks[name][-2:]==0) and np.all(final_inks[name][-2:]==0)
        save_array(images[name],output/f'{name}_continuous.png')
        save_array(images[name][:,:w//2],output/f'{name}_panel_1.png');save_array(images[name][:,w//2:],output/f'{name}_panel_2.png')
    assert np.all(vegetation[-2:]==0)
    pairs={name:np.concatenate([image[:,:w//2],np.full((h,round(40*w/600)),.85),image[:,w//2:]],axis=1) for name,image in images.items()}
    for name,image in pairs.items():save_array(image,output/f'{name}_physical_pair.png')
    ew=config['existing_near_weight']
    labels={'A':'A: v0.3 C / selective','B':'B: existing near method','C':f'C: {ew:.0%} existing + {1-ew:.0%} selective'}
    panel_figure({labels[name]:images[name] for name in images},output/'ABC_comparison.png','Fixed F2 | only foreground terrain retention changes')
    physical_comparison({labels[name]:pairs[name] for name in pairs},output/'physical_comparison.png')
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    for ax,name in zip(axes,images):
        ax.imshow(images[name][round(.63*h):],cmap='gray',vmin=0,vmax=1,extent=[0,600,900,.63*900]);ax.set_title(labels[name],fontsize=10)
        ax.set_xlabel('Painted X (mm)')
    axes[0].set_ylabel('Painted Y (mm)');fig.suptitle('Same root sites and canopies | foreground ground continuity',fontsize=13);fig.tight_layout();save_figure(fig,output/'foreground_detail.png')
    near=occupied&(old['depth_roles']['near']>.7);dc=config['diagnostics']
    metrics={}
    for name in images:
        metrics[name]={'mean_near_terrain_ink':float(terrain_inks[name][near].mean()),
            'last_two_rows_max_terrain_ink':float(terrain_inks[name][-2:].max()),'last_two_rows_max_vegetation_ink':float(vegetation[-2:].max()),
            'last_two_rows_max_final_ink':float(final_inks[name][-2:].max()),
            'root_ground_support':root_ground_support(terrain_inks[name],small+reps,dc['root_neighborhood_radius_mm']),
            'connectivity':connectivity_metrics(terrain_inks[name],near,dc['connected_terrain_ink_threshold'],dc['minimum_component_pixels'])}
    fig,axs=plt.subplots(2,2,figsize=(12,7))
    names=list(images);means=[metrics[k]['mean_near_terrain_ink'] for k in names];support=[metrics[k]['root_ground_support']['mean_terrain_ink_below_root'] for k in names]
    axs[0,0].bar(names,means,color=['#a8b1b4','#677c8a','#9a6e44']);axs[0,0].set(title='Near terrain contribution',ylabel='Mean ink proxy')
    axs[0,1].bar(names,support,color=['#a8b1b4','#677c8a','#9a6e44']);axs[0,1].set(title='Same root sites: ground directly below',ylabel='Mean terrain ink proxy')
    row_profile=np.arange(h)*900/h
    for name in names:
        axs[1,0].plot(row_profile,terrain_inks[name].mean(axis=1),label=name)
        axs[1,1].plot(np.arange(w)*600/w,final_inks[name][-1],label=name)
    axs[1,0].set(title='Terrain fades toward the bottom',xlabel='Painted Y (mm)',ylabel='Across-width mean ink',xlim=(650,900));axs[1,0].legend()
    axs[1,1].set(title='Exact-zero final boundary: every variant',xlabel='Painted X (mm)',ylabel='Final-row ink',ylim=(-.01,.01));axs[1,1].legend()
    fig.tight_layout();save_figure(fig,output/'diagnostics.png')
    archive={f'terrain_retention_{name}':value.astype(np.float16) for name,value in retention.items()}
    archive.update({'global_boundary_core':r['boundary_retention']==0,'occupied':occupied})
    save_fields(archive,output/'retention_snapshots.npz')
    for key,path in [('master',master_path),('vegetation',veg_path)]:source[key]['unchanged_after']=sha256_file(path)==source[key]['sha256']
    record={'study':config['study'],'base_pr_head':config['base_pr_head'],'config':config,'config_sha256':sha256_file(config_path),
        'v03_config_sha256':sha256_file(v03_path),'v02_config_sha256':sha256_file(v02_path),'F2_config_sha256':sha256_file(scene_path),
        'source_inputs':source,'previous_artifact_sha256':old_hashes,'metrics':metrics,
        'invariants':{'F2_baseline_pixels_identical':True,'A_v03_C_pixels_identical':True,'vegetation_coverage_identical_A_B_C':True,
            'v03_far_retention_unchanged':True,'v03_global_retention_unchanged':True,'outside_near_max_retention_difference':outside_near_max,
            'boundary_y900':float(boundary_retention(900,**v03['boundary'])),
            'previous_artifacts_unchanged':all(sha256_file(root/path)==value for path,value in old_hashes.items())},
        'combination':f'R_local_C = {ew:.2f} R_local_existing + {1-ew:.2f} R_local_selective; multiply the unchanged global retention once. No image/DEM/projection warp.',
        'vegetation':'Exact shared v0.3 C coverage, including all 42 near/105 middle/65 far small marks and 3 representatives. No re-placement, re-sizing or new randomness.',
        'source_small_marks':str(Path(v03['previous_results'])/'marks.json'),'source_representatives':str(Path(config['previous_results'])/'representative_trees.json'),
        'snapshot_archive_sha256':sha256_file(output/'retention_snapshots.npz'),
        'snapshot_note':'Derived combinations of existing retention arrays; float16 diagnostics, boolean boundary mask. Recompute in float64 for final stroke sampling.',
        'panel_rule':{'continuous_mm':[600,900],'panels_mm':[[300,900],[300,900]],'physical_gap_mm':40},
        'next_stage':'After visual choice, freeze the selected terrain retention plus the common v0.3 vegetation/boundary snapshot for actual vector-stroke comparisons.',
        'diagnostic_limit':'Thresholded image components and root-patch ink are visual proxies, not geographic landform/accessibility claims.'}
    save_json(record,output/'record.json');print(json.dumps({'metrics':metrics,'invariants':record['invariants']},indent=2))
    return {'images':images,'terrain_inks':terrain_inks,'final_inks':final_inks,'shared_vegetation_ink':vegetation,'retention':retention,'record':record}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
