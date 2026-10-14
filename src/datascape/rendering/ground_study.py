"""Reproduce F1/F2 composition checks without modifying previous results."""
import argparse
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import matplotlib.patheffects as effects
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform
from PIL import Image

from datascape.data.quality import read_valid_band,sha256_file
from datascape.projection.ground import GroundCamera,GroundComposite
from datascape.projection.composition import insert_panel_gap
from datascape.terrain.candidates import load_grid
from datascape.rendering.ground_composition import render
from datascape.rendering.composition_study import save_array,save_figure


def load_scene(ds,bounds):
    grid=load_grid(ds,bounds)
    window=from_bounds(*grid.bounds_m,transform=ds.transform).round_offsets().round_lengths()
    slope=read_valid_band(ds,2).filled(np.nan)[window.toslices()]
    return grid,slope


def make_camera(ds,xy,target,clearance,pitch,fov,near):
    row,col=ds.index(*xy)
    height=float(read_valid_band(ds,1)[row,col])
    if not np.isfinite(height):raise ValueError('Eye site has no valid source DEM.')
    azimuth=float(np.rad2deg(np.arctan2(target[0]-xy[0],target[1]-xy[1]))%360)
    camera=GroundCamera((xy[0],xy[1],height+clearance),azimuth,pitch,fov,near)
    lon,lat=transform(ds.crs,'EPSG:4326',[xy[0]],[xy[1]])
    return camera,{'eye_xy_utm_m':list(xy),'eye_lon_lat_wgs84':[lon[0],lat[0]],
                   'source_dem_at_eye_m':height,'eye_clearance_above_dem_m':clearance,
                   'exported_slope_at_eye_deg':float(read_valid_band(ds,2)[row,col]),
                   'camera':camera.record()}


def mapping_checks(result,projection,width,height,physical):
    xyz=result['xyz']
    ids=np.unique(result['faces'])
    sample=xyz[ids]
    pixel,depth=projection.project(sample,width,height)
    if physical:
        focal=height/(2*np.tan(np.deg2rad(projection.vertical_fov_deg)/2))
        determinant=focal*focal/(depth*depth)
        eye,basis=projection.frame()
        local=np.column_stack([(pixel[:,0]-width/2)*depth/focal,
                               -(pixel[:,1]-height/2)*depth/focal,depth])
        inverse=local@basis+eye
        formula='Physical pinhole: determinant = focal_px^2 / forward_depth_m^2; positive for depth>near.'
    else:
        determinant=projection.volume_determinant(sample,width,height)
        inverse=projection.unproject(pixel,depth,width,height)
        formula='Composite: determinant = W*H*k(q)/(1000*(near_width+width_growth*q)); positive for q>near. Known q uniquely recovers source r and z.'
    # Check the local numerical derivative away from the near boundary too.
    interior=sample[depth>3][::4]
    derivatives=[]
    for axis in range(3):
        delta=np.zeros(3);delta[axis]=.1
        p,z=projection.project(interior+delta,width,height)
        m,d=projection.project(interior-delta,width,height)
        derivatives.append((np.column_stack([p,z])-np.column_stack([m,d]))/.2)
    numeric=np.linalg.det(np.stack(derivatives,axis=2))
    return {'mapped_vertex_samples':len(sample),'analytic_volume_formula':formula,
            'nonfinite_analytic_samples':int((~np.isfinite(determinant)).sum()),
            'nonpositive_analytic_samples':int((determinant<=0).sum()),
            'minimum_analytic_volume_determinant':float(np.min(determinant)),
            'inverse_roundtrip_max_error_m':float(np.max(np.abs(inverse-sample))),
            'numeric_samples':len(interior),'numeric_step_m':.1,
            'nonfinite_numeric_samples':int((~np.isfinite(numeric)).sum()),
            'nonpositive_numeric_samples':int((numeric<=0).sum()),
            'interpretation':'3D mapping with known depth is locally orientation preserving and has an explicit inverse in the stated front domain. Terrain overlap in 2D remains legitimate occlusion.'}


def draw_source_map(full_dem,bounds,window_bounds,searches,eye_xy,target_xy,path):
    """Keep source outlines readable over both low and high grayscale terrain."""
    fig,ax=plt.subplots(figsize=(9,8))
    ax.imshow(full_dem,cmap='gray_r',vmin=0,vmax=850,extent=(bounds[0],bounds[2],bounds[1],bounds[3]))
    halo=[effects.withStroke(linewidth=3,foreground='white')]
    for rect,style,label in [([318120,4167770,325320,4174970],'--','Previous B1'),([320820,4165370,326820,4171370],':','Previous C1'),(window_bounds,'-','F1/F2 native source window')]:
        w,s,e,n=rect;patch=Rectangle((w,s),e-w,n-s,fill=False,edgecolor='black',linestyle=style,lw=1.5,label=label)
        patch.set_path_effects(halo);ax.add_patch(patch)
    for index,s in enumerate(searches):
        x,y=s['eye_xy_utm_m'];line=ax.plot(x,y,'kx',ms=6)[0];line.set_path_effects(halo)
        ax.text(x+120,y+100,f'S{index+1}',fontsize=9,color='black',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none','pad':1})
    ax.plot(*eye_xy,'ko',ms=6,label='Selected eye S3')[0].set_path_effects(halo)
    ax.plot(*target_xy,'^',markerfacecolor='white',markeredgecolor='black',ms=7,label='Look reference, source high vertex')
    arrow=ax.annotate('',xy=target_xy,xytext=eye_xy,arrowprops={'arrowstyle':'->','color':'black'})
    arrow.arrow_patch.set_path_effects(halo)
    ax.legend(loc='lower left',fontsize=9,facecolor='white',framealpha=.95);ax.ticklabel_format(style='plain',useOffset=False)
    ax.set_xlabel('UTM easting (m)');ax.set_ylabel('UTM northing (m)');ax.set_title('Actual source positions | No tile relocation',fontsize=16,fontweight='bold')
    save_figure(fig,path)


def run(master_path,config_path,output,previous_directory):
    config=json.loads(Path(config_path).read_text());output=Path(output);output.mkdir(parents=True,exist_ok=True)
    width,height=config['raster_pixels'];before_hash=sha256_file(master_path)
    with rasterio.open(master_path) as ds:
        if str(ds.crs)!='EPSG:32652' or ds.res!=(30.,30.) or ds.descriptions[0]!='DEM':raise ValueError('Expected the validated MASTER DEM.')
        grid,slope=load_scene(ds,config['primary_bounds_m'])
        camera,site=make_camera(ds,config['primary_eye_xy_m'],config['look_target_xy_m'],config['eye_clearance_m'],config['pitch_deg'],config['vertical_fov_deg'],config['near_m'])
        search_grid,search_slope=load_scene(ds,config['search']['bounds_m'])
        searches=[]
        fig,axes=plt.subplots(2,3,figsize=(12,11))
        for index,(ax,xy) in enumerate(zip(axes.ravel(),config['search']['eye_sites_m'])):
            c,s=make_camera(ds,xy,config['look_target_xy_m'],config['eye_clearance_m'],config['search']['pitch_deg'],config['search']['vertical_fov_deg'],config['near_m'])
            w,h=config['search']['raster_pixels'];view=render(search_grid,c,w,h,search_slope,config['search']['mesh_stride'],True,config['depth_edges_m'])
            ax.imshow(view['shade'],cmap='gray',vmin=0,vmax=1);ax.axis('off')
            ax.set_title(f"S{index+1} | {xy[0]}, {xy[1]}\nDEM {s['source_dem_at_eye_m']:.1f} m / az {c.azimuth_deg:.1f} deg",fontsize=10)
            searches.append({'site_id':f'S{index+1}',**s,'metrics':view['metrics']})
        fig.suptitle('Low-DEM eye sites | 2 m clearance / 1 deg upward / 48 deg FOV',fontsize=16,fontweight='bold')
        fig.text(.5,.02,'60 m search mesh | candidate places are not verified paths or accessible ground',ha='center',fontsize=10)
        save_figure(fig,output/'view_search.png')
        full_dem=read_valid_band(ds,1).filled(np.nan);bounds=list(ds.bounds)
    raw_copy=grid.elevation_m.copy()
    composite=GroundComposite(camera,site['source_dem_at_eye_m'],**config['composite'])
    results={'F1':render(grid,camera,width,height,slope,config['mesh_stride'],True,config['depth_edges_m']),
             'F2':render(grid,composite,width,height,slope,config['mesh_stride'],False,config['depth_edges_m'])}
    for name,result in results.items():
        save_array(result['shade'],output/f'{name}_continuous.png')
        save_array(result['shade'][:,:width//2],output/f'{name}_panel_1.png')
        save_array(result['shade'][:,width//2:],output/f'{name}_panel_2.png')
    fig,axes=plt.subplots(2,3,figsize=(12,12))
    for row,(name,result) in enumerate(results.items()):
        for ax,key,label in zip(axes[row],['shade','silhouette','depth'],['Shading','Silhouette','Source-depth bands']):
            ax.imshow(result[key],cmap='gray',vmin=0,vmax=1,extent=(0,600,900,0))
            ax.axvline(300,color='.5',linestyle=':',lw=.6);ax.set_title(f'{name} | {label}')
            ax.set_xticks([0,300,600]);ax.set_yticks([0,300,600,900])
    fig.suptitle('Spring ground composition | Same contiguous source scene',fontsize=18,fontweight='bold')
    fig.text(.5,.015,'F1 raw-meter perspective / F2 recorded artistic mapping | near <=600 m / middle <=2200 m / far >2200 m',ha='center',fontsize=10)
    save_figure(fig,output/'F1_F2_comparison.png')
    previous_directory=Path(previous_directory)
    fig,axes=plt.subplots(1,4,figsize=(14,7))
    previous_hashes={}
    for ax,name in zip(axes,['P2','P3','F1','F2']):
        if name in ['P2','P3']:
            path=previous_directory/f'{name}_continuous.png'
            with Image.open(path) as im:image=np.asarray(im)/255
            previous_hashes[name]=sha256_file(path)
        else:image=results[name]['shade']
        ax.imshow(image,cmap='gray',vmin=0,vmax=1,extent=(0,600,900,0));ax.set_title(f'{name} | '+('Preserved mountain-mass view' if name in ['P2','P3'] else 'Low-ground scene'),fontsize=11)
        ax.axvline(300,color='.5',linestyle=':',lw=.6);ax.set_xticks([0,300,600]);ax.set_yticks([0,300,600,900])
    fig.suptitle('Composition alternatives | Preserved P2/P3 + new F1/F2',fontsize=17,fontweight='bold')
    fig.text(.5,.025,'P2/P3 have their original viewpoint; F1/F2 share a new low-DEM eye. This compares composition families, not one-variable projection changes.',ha='center',fontsize=9)
    save_figure(fig,output/'composition_shortlist.png')
    fig,axes=plt.subplots(1,2,figsize=(8,7))
    for ax,(name,result) in zip(axes,results.items()):
        ax.imshow(insert_panel_gap(result['shade'],round(width*config['physical_gap_mm']/600)),cmap='gray',vmin=0,vmax=1,extent=(0,640,900,0))
        ax.set_title(f'{name} | 300 + 40 + 300 mm');ax.axis('off')
    fig.suptitle('Physical pair | Continuous content split without pixel loss',fontsize=16,fontweight='bold')
    save_figure(fig,output/'physical_pair.png')
    draw_source_map(full_dem,bounds,grid.bounds_m,searches,config['primary_eye_xy_m'],config['look_target_xy_m'],output/'source_map.png')
    checks={'F1':mapping_checks(results['F1'],camera,width,height,True),
            'F2':mapping_checks(results['F2'],composite,width,height,False)}
    if not np.array_equal(raw_copy,grid.elevation_m,equal_nan=True) or before_hash!=sha256_file(master_path):raise AssertionError('Source DEM changed.')
    for name,h in previous_hashes.items():
        if sha256_file(previous_directory/f'{name}_continuous.png')!=h:raise AssertionError('Previous result changed.')
    record={'study':config['study'],'base_pr_head':config['base_pr_head'],'config':config,
            'input':{'filename':Path(master_path).name,'sha256':before_hash,'crs':'EPSG:32652','native_resolution_m':[30,30]},
            'source_window_bounds_m':list(grid.bounds_m),'selected_site':site,'F2_mapping':composite.record(),
            'source_relocation':'None; contiguous native source surface, no terrain tiles, no synthetic ground or objects',
            'source_preserved':True,'input_hash_unchanged':True,'preserved_result_sha256':previous_hashes,
            'search_results':searches,'results':{k:v['metrics'] for k,v in results.items()},'mapping_checks':checks,
            'lighting':'Fixed NW at 45 degrees on raw-world normals; same for F1/F2; no cast shadows',
            'software':{'python':platform.python_version(),'numpy':np.__version__,'rasterio':rasterio.__version__,'matplotlib':matplotlib.__version__}}
    (output/'study.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--previous-directory',required=True)
    a=p.parse_args();run(a.master,a.config,a.output,a.previous_directory)


if __name__=='__main__':main()
