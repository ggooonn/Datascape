"""Reproducible global/local reserve ablations on the unchanged F2 mapping."""
from pathlib import Path
import argparse,json,os
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.data.quality import sha256_file
from datascape.rendering.painterly_layers import load_features,panel_figure
from datascape.rendering.composition_study import save_array,save_figure
from datascape.composition.multidepth import source_features,build_reserves
from datascape.vegetation.multidepth import vegetation_fields,place_marks,render_marks


def save_fields(archive,path):
    """Publish only a fully decoded, flushed field archive."""
    path=Path(path);temp=path.with_suffix('.writing.npz')
    with temp.open('wb') as stream:
        np.savez_compressed(stream,**archive);stream.flush();os.fsync(stream.fileno())
    with np.load(temp,allow_pickle=False) as loaded:
        if set(loaded.files)!=set(archive):raise AssertionError('Incomplete field archive.')
        for name,value in archive.items():
            if not np.array_equal(loaded[name],value,equal_nan=True):raise AssertionError('Field archive verification failed: '+name)
    temp.replace(path)


def save_json(value,path):
    """Flush and validate structured results before publishing."""
    path=Path(path);temp=path.with_suffix('.writing.json')
    data=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with temp.open('w') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    if json.loads(temp.read_text())!=json.loads(data):raise AssertionError('Structured result verification failed.')
    temp.replace(path)


def field_figure(items,path,title,occupied=None,columns=3,horizon=None):
    rows=int(np.ceil(len(items)/columns));fig,axes=plt.subplots(rows,columns,figsize=(4*columns,5.6*rows),squeeze=False)
    for ax,(label,values) in zip(axes.flat,items):
        value=np.where(occupied,values,np.nan) if occupied is not None else values
        im=ax.imshow(value,cmap='viridis',vmin=0,vmax=1,extent=[0,600,900,0]);ax.set_title(label,fontsize=10)
        ax.axvline(300,color='white',lw=.5,ls=':');fig.colorbar(im,ax=ax,fraction=.035,pad=.025)
        if horizon is not None:ax.plot((np.arange(len(horizon))+.5)*600/len(horizon),horizon,color='black',lw=.7)
    for ax in list(axes.flat)[len(items):]:ax.axis('off')
    fig.suptitle(title,fontsize=13);fig.tight_layout();save_figure(fig,path)


def run(master_path,veg_path,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2]
    config=json.loads(config_path.read_text());source_config_path=root/config['source_layer_config']
    old_config=json.loads(source_config_path.read_text());scene_path=root/config['source_composition'];scene=json.loads(scene_path.read_text())
    previous=root/config['previous_results'];output=Path(output);output.mkdir(parents=True,exist_ok=True)
    old_hashes={p.name:sha256_file(p) for p in previous.iterdir() if p.is_file()}
    terrain,base,ndvi,counts,source=load_features(master_path,veg_path,scene,old_config)
    w,h=scene['raster_pixels'];shade=terrain['shade'];occupied=base['occupied'];raw_ink=np.clip(1-shade,0,1)
    with Image.open(previous/'A_continuous.png') as im:archived_A=np.asarray(im)
    assert np.array_equal(np.round(shade*255).astype(np.uint8),archived_A),'F2 baseline changed.'
    tc={**config['terrain'],'seed':config['seed']};features=source_features(master_path,base,tc)
    reserves=build_reserves(base,features,config)
    vegetation=vegetation_fields(base,ndvi,counts,reserves,config['vegetation'])
    marks=place_marks(base,vegetation,reserves,config['vegetation'],config['seed'])
    mark_ink,kind_ink,depth_metrics=render_marks(marks,base,reserves,config['vegetation'])
    local_ink=raw_ink*reserves['local_core_retention'];terrain_ink=raw_ink*reserves['terrain_retention']
    soft_ink=raw_ink*reserves['terrain_soft_retention']
    final_ink=1-(1-terrain_ink)*(1-mark_ink)
    images={'local_only':1-local_ink,'global_local':1-terrain_ink,'soft_only':1-soft_ink,'depth_vegetation':1-final_ink}
    for name,image in images.items():save_array(image,output/f'{name}_continuous.png')
    final=images['depth_vegetation'];gap=np.full((h,round(40*w/600)),.85)
    save_array(np.concatenate([final[:,:w//2],gap,final[:,w//2:]],axis=1),output/'physical_pair.png')
    save_array(final[:,:w//2],output/'panel_1.png');save_array(final[:,w//2:],output/'panel_2.png')
    with Image.open(previous/'C_continuous.png') as im:previous_C=np.asarray(im,dtype=float)/255
    panel_figure({'C v0.1: previous reserve':previous_C,'D: global + local omission':images['global_local'],'E: depth-specific vegetation':final},output/'comparison.png','Fixed F2 | multi-depth omission and breathing space')
    panel_figure({'F2: terrain baseline':shade,'Local omission only':images['local_only'],'Global + local omission':images['global_local']},output/'ablation.png','Separate global composition from local terrain omission')
    panel_figure({'Soft density fading only':images['soft_only'],'Fading + exact-zero cores':images['global_local']},output/'gradation.png','Local transition comparison | global layout identical')
    horizon=np.min(np.where(occupied,np.indices((h,w))[0],h),axis=0)*900/h
    field_figure([('Global top envelope',reserves['global_top']),('Global bottom envelope',reserves['global_bottom']),('Terrain legibility anchors',reserves['anchors']),('Global retention',reserves['global_retention'])],output/'global_envelope.png','Global reserves | top 10-20%, bottom 5-15%; black line = unchanged skyline',columns=4,horizon=horizon)
    field_figure([('Near omission: ground fragments',reserves['near']),('Middle omission: valleys / overlap',reserves['middle']),('Far omission: ridge feet',reserves['far']),('Combined local omission',reserves['local']),('Local ink retention',reserves['local_core_retention']),('Global + local ink retention',reserves['terrain_retention'])],output/'local_fields.png','Local rules use source depth, relative height, valleys and occlusion',occupied)
    field_figure([('Native small-valley proxy',features['valley_small']),('Native broad-valley proxy',features['valley_large']),('Far side of depth discontinuity',features['behind_edge']),('Main ridge protection',features['ridge']),('Upper silhouette protection',features['silhouette']),('Native correlated irregularity',features['noise'])],output/'terrain_features.png','Evidence / protection / declared seeded irregularity',occupied)
    # Normalize each role separately for legibility; counts and values are recorded.
    vitems=[]
    for kind in ['near','middle','far']:
        value=vegetation['before'][kind];scale=max(value.max(),1e-9)
        vitems.append((f'{kind.title()} density (own max)',value/scale))
    field_figure(vitems,output/'vegetation_fields.png','NDVI + terrain + composition; distinct source-distance roles',occupied)
    panel_figure({'Near: trunks / branching / crowns':1-kind_ink['near'],'Middle: clusters / short repeats':1-kind_ink['middle'],'Far: sparse leaves / dashes':1-kind_ink['far']},output/'vegetation_grammar.png','Different mark grammars; each glyph uses its root depth')
    if depth_metrics['foreground_crossing_examples']:
        example=depth_metrics['foreground_crossing_examples'][0];x0,y0,x1,y1=example['bounds_pixel_xy']
        x0=max(0,x0-20);x1=min(w,x1+20);y0=max(0,y0-20);y1=min(h,y1+20);window=np.s_[y0:y1,x0:x1]
        blind=1-(1-terrain_ink)*(1-mark_ink*reserves['local_core_retention'])
        fig,axs=plt.subplots(1,3,figsize=(12,4.8))
        for ax,label,image in zip(axs,['Terrain / background only','Blind background masking (incorrect)','Root-depth compositing'],[images['global_local'],1-blind,final]):
            ax.imshow(image[window],cmap='gray',vmin=0,vmax=1,extent=[x0*600/w,x1*600/w,y1*900/h,y0*900/h]);ax.set_title(label,fontsize=10)
        fig.suptitle(f'Foreground mark over deeper omission | root distance {example["root_forward_depth_m"]:.0f} m',fontsize=12)
        fig.tight_layout();save_figure(fig,output/'depth_compositing.png')
    yy,xx=np.mgrid[:h,:w];first=np.min(np.where(occupied,yy,h),axis=0)
    fig,axes=plt.subplots(2,2,figsize=(12,7))
    axes[0,0].plot((np.arange(w)+.5)*600/w,first*900/h,color='black');axes[0,0].axhspan(90,180,color='#8fbfc3',alpha=.3)
    axes[0,0].set(title='Unchanged skyline vs top target',xlabel='Painted width (mm)',ylabel='First terrain row (mm)');axes[0,0].invert_yaxis()
    for panel,color,start,end in [('Left','#485e8f',0,w//2),('Right','#a96a3e',w//2,w)]:
        ratio=(terrain_ink[:,start:end]<.015).mean(axis=1);axes[0,1].plot(ratio,np.arange(h)*900/h,color=color,label=panel)
    axes[0,1].axhspan(765,855,color='#8fbfc3',alpha=.3);axes[0,1].set(title='Panel-wise open space profile',xlabel='Paper / almost no terrain ink fraction',ylabel='Height (mm)');axes[0,1].invert_yaxis();axes[0,1].legend()
    for col in [int(w*.2),int(w*.48),int(w*.82)]:axes[1,0].plot(np.arange(h)*900/h,reserves['terrain_retention'][:,col],label=f'x={col*600/w:.0f} mm')
    axes[1,0].set(title='Continuous retention along three cuts',xlabel='Top-to-bottom height (mm)',ylabel='Terrain ink retention');axes[1,0].legend()
    bottom=(terrain_ink[-1]>.02).astype(float);axes[1,1].fill_between(np.arange(w)*600/w,0,bottom,color='#485e8f')
    axes[1,1].set(title='Discontinuous bottom contact',xlabel='Painted width (mm)',ylabel='Retained terrain ink > 0.02',ylim=(0,1.2))
    fig.tight_layout();save_figure(fig,output/'envelope_profiles.png')
    export_names=['near','middle','far','local','global_top','global_bottom','global','global_retention','terrain_retention','terrain_soft_retention','anchors']
    archive={name:reserves[name].astype(np.float16) for name in export_names}
    archive.update({'vegetation_'+name:vegetation['before'][name].astype(np.float16) for name in ['near','middle','far']})
    local_core=occupied&(reserves['local_core_retention']==0)
    global_core=occupied&(reserves['global_retention']==0)
    archive.update({'occupied':occupied,'local_terrain_core':local_core,'global_core':global_core})
    save_fields(archive,output/'fields.npz')
    save_json({'units':'Pixel XY, 1 pixel = 1 painted mm in this preview. Source XYZ is raw EPSG:32652 meters.',
        'model':'Three schematic grammars, constant root-forward-depth billboards, not actual trees or machine-ready strokes.','marks':marks},output/'marks.json')
    bottom_start=round(.85*h);transition=occupied&(yy>=bottom_start)
    metrics={'baseline_pixels_identical':True,'previous_artifacts_unchanged':all(sha256_file(previous/name)==digest for name,digest in old_hashes.items()),
        'top_full_width_blank_fraction':float(first.min()/h),'top_first_terrain_p10_p50_p90_fraction':np.percentile(first/h,[10,50,90]).tolist(),
        'top_target_intersects_terrain':reserves['top_target_intersects_terrain'],
        'bottom_edge_terrain_contact_fraction_gt002':float((terrain_ink[-1]>.02).mean()),
        'bottom_edge_left_right_contact_fraction_gt002':[float((terrain_ink[-1,:w//2]>.02).mean()),float((terrain_ink[-1,w//2:]>.02).mean())],
        'bottom_15pct_terrain_ink_retained_fraction':float(terrain_ink[transition].sum()/raw_ink[transition].sum()),
        'local_field_max':{k:float(reserves[k].max()) for k in ['near','middle','far']},
        'local_field_gt05_terrain_fraction':{k:float(((reserves[k]>.5)&occupied).sum()/occupied.sum()) for k in ['near','middle','far']},
        'local_exact_zero_terrain_pixels':int(local_core.sum()),'global_exact_zero_terrain_pixels':int(global_core.sum()),
        'terrain_max_ink_in_local_core':float(terrain_ink[local_core].max()) if local_core.any() else 0,
        'final_max_ink_in_global_core':float(final_ink[global_core].max()) if global_core.any() else 0,
        'mark_count':{k:sum(x['kind']==k for x in marks) for k in ['near','middle','far']},**depth_metrics,
        'mean_terrain_ink_before':float(raw_ink[occupied].mean()),'mean_terrain_ink_after':float(terrain_ink[occupied].mean()),
        'final_full_width_top_open_fraction':float(np.min(np.where(final_ink>.015,yy,h))/h),
        'panel_sky_open_fraction':[float((~occupied[:,:w//2]).mean()),float((~occupied[:,w//2:]).mean())]}
    source['master']['unchanged_after']=sha256_file(master_path)==source['master']['sha256'];source['vegetation']['unchanged_after']=sha256_file(veg_path)==source['vegetation']['sha256']
    record={'study':config['study'],'base_pr_head':config['base_pr_head'],'config':config,'config_sha256':sha256_file(config_path),
        'fixed_F2_config_sha256':sha256_file(scene_path),'previous_layer_config_sha256':sha256_file(source_config_path),
        'previous_artifact_sha256':old_hashes,'source_inputs':source,'metrics':metrics,'anchor_patches':reserves['anchor_records'],
        'field_archive_sha256':sha256_file(output/'fields.npz'),
        'original_source_coordinate_archive':str(Path(config['previous_results'])/'fields.npz'),
        'seed_streams':{'native_irregularity':401,'placement_per_depth_role':501,'geometry_per_depth_role':502},
        'panel_rule':{'continuous_mm':[600,900],'panels_mm':[[300,900],[300,900]],'physical_gap_mm':40},
        'field_archive_note':'Scalar masks stored float16 (typically <0.0005 absolute quantization); exact-zero masks stored bool. Original source XYZ/depth remain in the unchanged v0.1 archive.',
        'depth_compositing':'Each symbolic glyph holds its source root forward depth. Local omission fades only matching depths; substantially nearer terrain occludes the glyph. Global layout reserves apply at all depths.',
        'limitations':['Top breathing space is already larger than the 10-20% target; fixed F2 cannot reduce it without adding content or changing placement.','Terrain/valley/ridge proxies and screen anchors do not establish actual rocks, paths, trees or weather.','Digital coverage fading is an omission proxy, not a calibrated brush/pigment model.']}
    save_json(record,output/'record.json');print(json.dumps(metrics,indent=2))
    return {'images':images,'base':base,'reserves':reserves,'vegetation':vegetation,'marks':marks,'record':record,'terrain_ink':terrain_ink,'mark_ink':mark_ink}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('master');parser.add_argument('veg');parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
