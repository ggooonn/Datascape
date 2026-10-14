"""Final small F2 composition study; previous artifacts remain immutable."""
from pathlib import Path
import argparse,json
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.data.quality import sha256_file
from datascape.rendering.painterly_layers import load_features,panel_figure
from datascape.rendering.composition_study import save_array,save_figure
from datascape.rendering.multidepth_whitespace import save_fields,save_json,field_figure
from datascape.composition.multidepth import source_features,build_reserves,omission_retention
from datascape.composition.refinement import refine_reserves,representative_trees,boundary_retention
from datascape.vegetation.multidepth import render_marks


def combine(terrain,marks):
    return 1-(1-terrain)*(1-marks)


def run(master_path,veg_path,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2]
    config=json.loads(config_path.read_text());old_config_path=root/config['source_config'];old=json.loads(old_config_path.read_text())
    scene_path=root/old['source_composition'];scene=json.loads(scene_path.read_text())
    source_layer=root/old['source_layer_config'];layer=json.loads(source_layer.read_text())
    previous=root/config['previous_results'];output=Path(output);output.mkdir(parents=True,exist_ok=True)
    previous_hashes={}
    for folder in [previous,root/old['previous_results']]:
        for path in folder.iterdir():
            if path.is_file() and '.writing.' not in path.name:previous_hashes[path.relative_to(root).as_posix()]=sha256_file(path)
    terrain,base,ndvi,counts,source=load_features(master_path,veg_path,scene,layer)
    w,h=scene['raster_pixels'];shade=terrain['shade'];occupied=base['occupied'];raw=np.clip(1-shade,0,1)
    with Image.open(root/layer['baseline_image']) as im:archived=np.asarray(im)
    assert np.array_equal(np.round(shade*255).astype(np.uint8),archived),'F2 geometry/baseline changed.'
    f=source_features(master_path,base,{**old['terrain'],'seed':old['seed']});old_reserves=build_reserves(base,f,old)
    marks=json.loads((previous/'marks.json').read_text())['marks']
    old_marks,_,_=render_marks(marks,base,old_reserves,old['vegetation'])
    old_ink=combine(raw*old_reserves['terrain_retention'],old_marks)
    with Image.open(previous/'depth_vegetation_continuous.png') as im:archived_E=np.asarray(im)
    assert np.array_equal(np.round((1-old_ink)*255).astype(np.uint8),archived_E),'v0.2 E did not reproduce.'
    r=refine_reserves(base,old_reserves,marks,config,old)
    small_ink,_,small_depth=render_marks(marks,base,r,old['vegetation'])
    representatives=representative_trees(marks,base,r,config['representative_trees'],config['seed'])
    rep_ink,_,rep_depth=render_marks(representatives,base,r,old['vegetation'])
    mark_C=combine(small_ink,rep_ink);terrain_B=raw*r['terrain_retention']
    ink_B=combine(terrain_B,small_ink);ink_C=combine(terrain_B,mark_C)
    images={'A':archived_E.astype(float)/255,'B':1-ink_B,'C':1-ink_C}
    legacy_r={**r,'local_core_retention':r['legacy_local_retention'],'terrain_retention':r['legacy_terrain_retention']}
    legacy_marks,_,_=render_marks(marks,base,legacy_r,old['vegetation']);legacy_ink=combine(raw*r['legacy_terrain_retention'],legacy_marks)
    for name,image in images.items():
        save_array(image,output/f'{name}_continuous.png')
        save_array(image[:,:w//2],output/f'{name}_panel_1.png');save_array(image[:,w//2:],output/f'{name}_panel_2.png')
        gap=np.full((h,round(40*w/600)),.85)
        save_array(np.concatenate([image[:,:w//2],gap,image[:,w//2:]],axis=1),output/f'{name}_physical_pair.png')
    save_array(1-legacy_ink,output/'subtractive_near_continuous.png')
    panel_figure({'A: preserved v0.2 E':images['A'],'B: selective terrain + small marks':images['B'],'C: representative canopy scale':images['C']},output/'ABC_comparison.png','Fixed F2 | final composition refinement v0.3')
    panel_figure({'v0.2: original near terrain':images['A'],'v0.3: boundary + old near method':1-legacy_ink,'v0.3: selective positive forms':images['B']},output/'near_comparison.png','Foreground comparison | new far/boundary identical in the right two views')
    old_far=omission_retention(old_reserves['far'],old['local']['soft_strength'],old['local']['core_threshold'],True)
    isolated_old_far_ink=raw*r['near_middle_retention']*old_far*r['global_retention']
    panel_figure({'Original far component':1-isolated_old_far_ink,'Refined far component':1-terrain_B},output/'far_comparison.png','Far-foot transition | near/middle/global settings identical')
    field_figure([('Unconditional boundary retention',r['boundary_retention']),('Irregular bottom retention',r['irregular_retention']),('DEM-selected positive forms',r['positive_forms']),('Small-root support',r['root_support']),('Refined far omission',r['far']),('Final terrain retention',r['terrain_retention'])],output/'fields.png','Separate boundary, transition, positive forms and far refinement',columns=3)
    yy,xx=np.mgrid[:h,:w];y=(yy+.5)*900/h
    fig,axs=plt.subplots(2,2,figsize=(12,8))
    axs[0,0].plot(np.arange(w)*600/w,old_ink[-1],label='A v0.2',color='#6b7c8a');axs[0,0].plot(np.arange(w)*600/w,ink_B[-1],label='B',lw=2);axs[0,0].plot(np.arange(w)*600/w,ink_C[-1],label='C',ls='--')
    axs[0,0].set(title='Final-row ink coverage',xlabel='Painted X (mm)',ylabel='Ink contribution');axs[0,0].legend()
    for col in [int(w*.15),int(w*.47),int(w*.83)]:axs[0,1].plot(y[:,col],r['terrain_retention'][:,col],label=f'x={col*600/w:.0f} mm')
    axs[0,1].set(title='Different lower transitions',xlabel='Painted Y (mm)',ylabel='Terrain retention',xlim=(765,900));axs[0,1].legend()
    axs[1,0].imshow(images['C'][round(.75*h):],cmap='gray',vmin=0,vmax=1,extent=[0,600,900,675]);axs[1,0].axhline(900-config['boundary']['hard_bottom_guard_mm'],color='#aa7046',lw=.6)
    axs[1,0].set(title='Forms fade before the frame edge',xlabel='Painted X (mm)',ylabel='Painted Y (mm)')
    lower=np.s_[round(.85*h):,:];variance=np.std(r['irregular_retention'][lower],axis=1)
    axs[1,1].plot(y[round(.85*h):,0],variance);axs[1,1].set(title='Across-width variation above the boundary',xlabel='Painted Y (mm)',ylabel='Std. dev. of irregular retention')
    fig.tight_layout();save_figure(fig,output/'boundary_diagnostics.png')
    # Root-depth survival is evaluated by the unchanged v0.2 compositor.
    if rep_depth['foreground_crossing_examples']:
        example=rep_depth['foreground_crossing_examples'][0];x0,y0,x1,y1=example['bounds_pixel_xy'];window=np.s_[max(0,y0-15):min(h,y1+15),max(0,x0-15):min(w,x1+15)]
        fig,axs=plt.subplots(1,2,figsize=(10,6))
        for ax,label,image in zip(axs,['Small vegetation baseline B','Added representative canopy C'],[images['B'],images['C']]):
            ax.imshow(image[window],cmap='gray',vmin=0,vmax=1);ax.set_title(label,fontsize=11);ax.axis('off')
        fig.suptitle(f'Representative foreground over deeper omission | root q={example["root_forward_depth_m"]:.0f} m');fig.tight_layout();save_figure(fig,output/'representative_depth.png')
    far_zone=occupied&(old_reserves['depth_roles']['far']>.25)&(f['silhouette']<.1)
    near_zone=occupied&(old_reserves['depth_roles']['near']>.7)
    mid_unchanged=np.array_equal(r['middle'],old_reserves['middle']);near_unchanged=np.array_equal(r['near'],old_reserves['near'])
    metrics={'F2_baseline_pixels_identical':True,'v02_E_pixels_identical':True,'old_near_field_identical':near_unchanged,'old_middle_field_identical':mid_unchanged,
        'final_row_max_terrain_ink_B_C':[float(terrain_B[-1].max())]*2,'final_row_max_vegetation_ink_B_C':[float(small_ink[-1].max()),float(mark_C[-1].max())],
        'final_row_max_total_ink_B_C':[float(ink_B[-1].max()),float(ink_C[-1].max())],
        'continuous_boundary_at_y900':float(boundary_retention(900,**config['boundary'])),
        'irregular_bottom_extent_min_max_mm':[float(r['bottom_extent_mm'][occupied].min()),float(r['bottom_extent_mm'][occupied].max())],
        'lower_transition_mean_across_width_std':float(variance.mean()),'positive_form_count':len(r['positive_records']),
        'near_mean_terrain_ink_v02_v03':[float((raw*old_reserves['terrain_retention'])[near_zone].mean()),float(terrain_B[near_zone].mean())],
        'far_terrain_pixels_ink_below003_v02_v03':[int(((raw*old_reserves['terrain_retention']<.03)&far_zone).sum()),int(((terrain_B<.03)&far_zone).sum())],
        'far_core_pixels_v02_v03':[int(((old_reserves['local_core_retention']==0)&far_zone).sum()),int(((r['far_core_gate']==1)&far_zone).sum())],
        'near_small_marks_preserved':sum(m['kind']=='near' for m in marks),'middle_marks_preserved':sum(m['kind']=='middle' for m in marks),'far_marks_preserved':sum(m['kind']=='far' for m in marks),
        'representative_tree_count':len(representatives),'representative_heights_mm':[m['height_mm'] for m in representatives],
        'small_mark_depth_metrics':small_depth,'representative_depth_metrics':rep_depth,
        'full_width_top_open_fraction_B_C':[float(np.min(np.where(ink>.015,yy,h))/h) for ink in [ink_B,ink_C]],
        'previous_artifacts_unchanged':all(sha256_file(root/name)==value for name,value in previous_hashes.items())}
    archive={name:r[name].astype(np.float16) for name in ['boundary_retention','irregular_retention','bottom_transition','positive_forms','positive','root_support','far','far_retention','local_core_retention','global_retention','terrain_retention','legacy_terrain_retention']}
    archive.update({'occupied':occupied,'boundary_core':r['boundary_retention']==0,'local_far_core':r['far_core_gate']==1})
    save_fields(archive,output/'fields.npz')
    save_json({'interpretation':'Paper-scale symbolic representatives, not measured tree heights or machine-ready strokes. Small/middle/far geometry is reused from v0.2.',
        'small_mark_source':str(Path(config['previous_results'])/'marks.json'),'representatives':representatives},output/'representative_trees.json')
    for key,path in [('master',master_path),('vegetation',veg_path)]:source[key]['unchanged_after']=sha256_file(path)==source[key]['sha256']
    record={'study':config['study'],'base_pr_head':config['base_pr_head'],'config':config,'config_sha256':sha256_file(config_path),
        'fixed_F2_config_sha256':sha256_file(scene_path),'v02_config_sha256':sha256_file(old_config_path),'inputs':source,'metrics':metrics,
        'previous_artifact_sha256':previous_hashes,'positive_forms':r['positive_records'],'representative_source_roots':[{'id':m['id'],'source_xyz_m':m['source_xyz_m'],'parent_small_mark_id':m['parent_small_mark_id']} for m in representatives],
        'field_archive_sha256':sha256_file(output/'fields.npz'),'seed_streams':{'native_features':'Unchanged v0.2 seed/401','small_grammar':'Reused v0.2 source marks','representative_geometry':603},
        'boundary_contract':'Y increases downward in painted mm. Every contribution is multiplied by boundary_retention; y >= 898 mm is zero in this config, including y = 900 mm. No form/root/depth exception.',
        'future_vector_color_contract':'Clip/split vector segments at the configured hard boundary; sample the same continuous retention for density/layer inclusion. Apply the final boundary gate to every color/ink contribution. No G-code or color engine is implemented.',
        'panel_rule':{'continuous_mm':[600,900],'panels_mm':[[300,900],[300,900]],'physical_gap_mm':40},
        'archive_note':'Scalar diagnostic fields float16; categorical boundary/far cores bool. Original raw source XYZ/depth stay in unchanged v0.1 fields.npz.',
        'limitations':['Representative heights are image-space choices, not DEM-measured trees.','Positive forms are terrain selections; no observed rock/path/tree inventory is inferred.','Shade/coverage is a composition proxy; final vector strokes and pigment calibration remain separate.']}
    save_json(record,output/'record.json');print(json.dumps(metrics,indent=2))
    return {'images':images,'base':base,'reserves':r,'record':record,'representatives':representatives,'ink_B':ink_B,'ink_C':ink_C,'small_marks':marks,'terrain_ink':terrain_B,'vegetation_B':small_ink,'vegetation_C':mark_C}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
