"""Fixed F2 A/B/C study with georeferenced vegetation and omission fields."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.data.quality import read_valid_band,sha256_file
from datascape.projection.ground import GroundComposite
from datascape.rendering.ground_study import load_scene,make_camera
from datascape.rendering.ground_composition import render
from datascape.rendering.composition_study import save_array,save_figure
from datascape.composition.fields import mapped_source_coordinates,sample_window_band,sample_finite,smooth_supported,build_fields
from datascape.vegetation.painterly import place_plants,plant_coverage,combine_ink


def dataset_record(ds,path):
    return {'filename':Path(path).name,'sha256':sha256_file(path),'crs':str(ds.crs),
            'resolution_m':list(ds.res),'bounds_m':list(ds.bounds),'shape':list(ds.shape),
            'transform':list(ds.transform)[:6],'bands':list(ds.descriptions),'nodata':ds.nodata}


def load_features(master,veg,scene,config):
    """Use native transforms; interpolate circular aspect as sine/cosine."""
    with rasterio.open(master) as ds:
        grid,slope_native=load_scene(ds,scene['primary_bounds_m'])
        camera,site=make_camera(ds,scene['primary_eye_xy_m'],scene['look_target_xy_m'],scene['eye_clearance_m'],scene['pitch_deg'],scene['vertical_fov_deg'],scene['near_m'])
        projection=GroundComposite(camera,site['source_dem_at_eye_m'],**scene['composite'])
        w,h=scene['raster_pixels']
        terrain=render(grid,projection,w,h,slope_native,stride=scene['mesh_stride'],physical=False,depth_edges_m=scene['depth_edges_m'])
        xyz,valid=mapped_source_coordinates(terrain)
        slope,_=sample_window_band(ds,ds.descriptions.index('SLOPE')+1,grid.bounds_m,xyz)
        window=from_bounds(*grid.bounds_m,transform=ds.transform).round_offsets().round_lengths()
        transform=ds.window_transform(window)
        aspect_native=read_valid_band(ds,ds.descriptions.index('ASPECT')+1)[window.toslices()].filled(np.nan)
        ss,_=sample_finite(np.sin(np.deg2rad(aspect_native)),transform,xyz[:,:,0],xyz[:,:,1])
        cc,_=sample_finite(np.cos(np.deg2rad(aspect_native)),transform,xyz[:,:,0],xyz[:,:,1])
        aspect=np.rad2deg(np.arctan2(ss,cc))%360
        # Smooth a padded/full raw DEM for features only; no surface changes.
        dem=read_valid_band(ds,ds.descriptions.index('DEM')+1).filled(np.nan)
        macro=smooth_supported(dem,np.isfinite(dem),config['macro_scale_m']/ds.res[0])
        macro_screen,_=sample_finite(macro,ds.transform,xyz[:,:,0],xyz[:,:,1])
        master_record=dataset_record(ds,master)
    ndvi={};counts={};supports={}
    with rasterio.open(veg) as ds:
        if str(ds.crs)!=master_record['crs']:raise ValueError('Reproject VEG explicitly before this study; CRS mismatch.')
        for season in ['SPRING','SUMMER','AUTUMN','WINTER']:
            ndvi[season],supports[season]=sample_window_band(ds,ds.descriptions.index('NDVI_'+season)+1,grid.bounds_m,xyz)
            counts[season],_=sample_window_band(ds,ds.descriptions.index('N_'+season)+1,grid.bounds_m,xyz)
            good=np.isfinite(ndvi[season]) & (ndvi[season]>=-1)&(ndvi[season]<=1)&np.isfinite(counts[season])&(counts[season]>=0)
            ndvi[season]=np.where(good,ndvi[season],np.nan)
            counts[season]=np.where(good,counts[season],np.nan)
        veg_record=dataset_record(ds,veg)
    fields=build_fields(terrain,grid,slope,aspect,macro_screen,ndvi,counts,camera,config)
    return terrain,fields,ndvi,counts,{'master':master_record,'vegetation':veg_record,'site':site}


def panel_figure(images,path,title):
    fig,axes=plt.subplots(1,len(images),figsize=(4.2*len(images),6.6))
    for ax,(label,image) in zip(np.atleast_1d(axes),images.items()):
        ax.imshow(image,cmap='gray',vmin=0,vmax=1,extent=[0,600,900,0]);ax.axvline(300,color='#aa7046',lw=.65,ls='--')
        ax.set_title(label,fontsize=11);ax.set_xlabel('Continuous painted width (mm)');ax.set_yticks([0,300,600,900])
    axes=np.atleast_1d(axes);axes[0].set_ylabel('Top-to-bottom height (mm)')
    fig.suptitle(title,fontsize=14);fig.tight_layout();save_figure(fig,path)


def run(master_path,veg_path,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2]
    config=json.loads(config_path.read_text());scene_path=root/config['source_composition']
    scene=json.loads(scene_path.read_text());output=Path(output);output.mkdir(parents=True,exist_ok=True)
    terrain,f,ndvi,counts,source=load_features(master_path,veg_path,scene,config)
    w,h=scene['raster_pixels'];baseline=root/config['baseline_image']
    with Image.open(baseline) as im:archived=np.array(im)
    quantized=np.round(np.clip(terrain['shade'],0,1)*255).astype(np.uint8)
    if not np.array_equal(quantized,archived):raise AssertionError('Fixed F2 baseline does not match the archived pixels.')
    plants=place_plants(f,config)
    pb=plant_coverage(plants,w,h,config['plants']['line_width_mm'],'B')
    pc=plant_coverage(plants,w,h,config['plants']['line_width_mm'],'C')
    images=combine_ink(terrain['shade'],pb,pc,f)
    for name in ['A','B','C']:
        image=images[name];save_array(image,output/f'{name}_continuous.png')
        save_array(image[:,:w//2],output/f'{name}_panel_1.png');save_array(image[:,w//2:],output/f'{name}_panel_2.png')
        gap=round(40*w/600);physical=np.concatenate([image[:,:w//2],np.full((h,gap),.85),image[:,w//2:]],axis=1)
        save_array(physical,output/f'{name}_physical_pair.png')
    panel_figure({'A: fixed F2 terrain':images['A'],'B: foreground vegetation':images['B'],'C: vegetation + omission':images['C']},output/'ABC_comparison.png','F2 painterly layer study | 600 x 900 mm continuous painting')
    fig,axs=plt.subplots(2,3,figsize=(12,11))
    field_items=[('Valley proxy (macro DEM - raw Z)','valley'),('Mist / omission field M','mist'),('Whitespace field W','whitespace'),('Vegetation before omission V_B','vegetation_before'),('Vegetation after omission V_C','vegetation_after'),('Terrain retention R_T','terrain_retention')]
    for ax,(label,key) in zip(axs.flat,field_items):
        value=np.where(f['occupied'],f[key],np.nan);maximum=max(.001,float(np.nanmax(value))) if key.startswith('vegetation_') else 1
        im=ax.imshow(value,cmap='viridis',vmin=0,vmax=maximum,extent=[0,600,900,0]);ax.set_title(label,fontsize=10);ax.axvline(300,color='white',lw=.5,ls=':');fig.colorbar(im,ax=ax,fraction=.035,pad=.025)
    fig.suptitle('Explicit fields | bright = stronger; vegetation panels share a scale',fontsize=13)
    # Use the same color scale for the before/after pair.
    vmax=max(.001,float(f['vegetation_before'].max()))
    for ax in [axs[1,0],axs[1,1]]:ax.images[0].set_clim(0,vmax)
    fig.tight_layout();save_figure(fig,output/'fields.png')
    fig,axs=plt.subplots(1,3,figsize=(12,6))
    for ax,title,value,cmap,limits in zip(axs,['Spring NDVI (native 10 m sampling)','Effective spring observations','Zero ink reserve / gradual attenuation'],[f['current_ndvi'],f['current_observations'],np.where(f['reserve'],1,1-f['terrain_retention'])],['YlGn','magma','gray'],[(-.1,.7),(0,40),(0,1)]):
        im=ax.imshow(np.where(f['occupied'],value,np.nan),cmap=cmap,vmin=limits[0],vmax=limits[1],extent=[0,600,900,0]);ax.set_title(title,fontsize=10);fig.colorbar(im,ax=ax,fraction=.035,pad=.03)
    fig.tight_layout();save_figure(fig,output/'data_and_omission.png')
    arrays={key:np.asarray(f[key],dtype=np.float32) for key in ['mist','whitespace','terrain_retention','vegetation_before','vegetation_after','vegetation_retention','depth_m','current_ndvi','current_observations','xyz']}
    arrays.update({key:f[key] for key in ['occupied','reserve','evidence_valid']})
    np.savez_compressed(output/'fields.npz',**arrays)
    (output/'plants.json').write_text(json.dumps({'units':'pixel coordinates; 1 pixel = 1 mm at this preview resolution','interpretation':'Schematic seeded branching marks; not observed trees, species or machine-ready strokes.','plants':plants},indent=2,allow_nan=False)+'\n')
    occupied=f['occupied'];lower=occupied & (np.indices((h,w))[0]>=2*h/3)
    metrics={'baseline_pixels_identical':True,'plants_B':len(plants),'plants_C':sum(p['keep_C'] for p in plants),
        'occupied_pixels':int(occupied.sum()),'hard_reserve_pixels':int(f['reserve'].sum()),
        'hard_reserve_terrain_fraction':float(f['reserve'].sum()/occupied.sum()),
        'reserve_max_ink_C':float(np.max(1-images['C'][f['reserve']])) if f['reserve'].any() else 0,
        'mist_gt_05_terrain_fraction':float(((f['mist']>.5)&occupied).sum()/occupied.sum()),
        'vegetation_positive_pixels_before':int((f['vegetation_before']>0).sum()),
        'vegetation_mass_retained_fraction':float(f['vegetation_after'].sum()/max(f['vegetation_before'].sum(),1e-9)),
        'lower_300mm_spring_ndvi_p10_p50_p90':np.nanpercentile(f['current_ndvi'][lower],[10,50,90]).tolist(),
        'lower_300mm_spring_effective_observations_p10_p50_p90':np.nanpercentile(f['current_observations'][lower],[10,50,90]).tolist(),
        'season_valid_occupied_fraction':{s:float((np.isfinite(ndvi[s])&occupied).sum()/occupied.sum()) for s in ndvi},
        'mean_terrain_ink_A':float((1-images['A'][occupied]).mean()),'mean_total_ink_B':float((1-images['B'][occupied]).mean()),'mean_total_ink_C':float((1-images['C'][occupied]).mean())}
    source['master']['unchanged_after']=sha256_file(master_path)==source['master']['sha256']
    source['vegetation']['unchanged_after']=sha256_file(veg_path)==source['vegetation']['sha256']
    record={'study':config['study'],'base_pr_head':'0d4b7a34103beff67eb561f0095800abb6c3a707','config':config,'config_sha256':sha256_file(config_path),
        'fixed_F2_config_sha256':sha256_file(scene_path),'baseline_png_sha256':sha256_file(baseline),'inputs':source,'metrics':metrics,
        'field_archive_sha256':sha256_file(output/'fields.npz'),
        'sampling':'Visible mapped triangle barycentric XYZ; affine native-center bilinear VEG and slope; circular aspect. Require >=0.999 finite support. Interpolated N is effective support, not a native integer count.',
        'macro_dem':'Mask-aware Gaussian sigma 300 m on raw master grid; feature only, no geometry smoothing.',
        'seed_streams':{'screen_density_noise':101,'root_placement_and_C_thinning':202,'branching_geometry':303},
        'panel_rule':{'continuous_mm':[600,900],'panels_mm':[[300,900],[300,900]],'physical_gap_mm':40,'physical_pair_mm':[640,900]},
        'limitations':['NDVI is a vegetation proxy; no species, tree, path, building or meteorology inventory.','Density attenuation is a digital ink coverage proxy; no pigment or brush calibration.','Masks are applied only to visible terrain and foreground marks; no hidden terrain is invented.']}
    (output/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps(metrics,indent=2))
    return {'images':images,'fields':f,'plants':plants,'record':record}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('master');parser.add_argument('veg');parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.master,args.veg,args.config,args.output)

if __name__=='__main__':main()
