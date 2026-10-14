"""Reproducible candidate and camera contact sheets; no stroke generation."""
import argparse
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
import json,platform,os
import numpy as np
import rasterio
from rasterio.warp import transform,transform_bounds
import yaml
from datascape.data.quality import sha256_file
from datascape.terrain.candidates import scan_rois,load_grid
from datascape.projection.camera import Camera
from datascape.rendering.terrain_preview import render_terrain,panel_pair


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family":"DejaVu Sans","figure.facecolor":"#f6f5f1"})
    return plt


def _finish(fig,path):
    # Publish complete files atomically so readers never see a partial PNG.
    temporary=path.with_name(path.stem+".writing.png")
    plt=_plt();fig.savefig(temporary,dpi=125,bbox_inches="tight");plt.close(fig)
    plt.imread(temporary)
    with temporary.open("rb") as stream:os.fsync(stream.fileno())
    temporary.replace(path)


def overview(dataset,selected,output):
    from matplotlib.patches import Rectangle
    from datascape.data.quality import read_valid_band
    plt=_plt();fig,axes=plt.subplots(1,2,figsize=(15,7),layout="constrained")
    extent=[dataset.bounds.left/1000,dataset.bounds.right/1000,dataset.bounds.bottom/1000,dataset.bounds.top/1000]
    colors={"A":"#ad4e33","B":"#266c9d","C":"#388864"}
    for ax,index,cmap,title in zip(axes,[1,4],["terrain","gray"],["Native 30 m surface elevation","Exported hillshade"]):
        image=ax.imshow(read_valid_band(dataset,index),extent=extent,origin="upper",cmap=cmap)
        for candidate in selected:
            w,s,e,n=candidate["bounds_utm_m"];key=candidate["type"]
            ax.add_patch(Rectangle((w/1000,s/1000),(e-w)/1000,(n-s)/1000,fill=False,edgecolor=colors[key],linewidth=2))
            ax.text(w/1000+.15,n/1000-.40,key+"1",color="white",weight="bold",fontsize=13,
                    bbox={"facecolor":colors[key],"edgecolor":"none","pad":3})
        ax.set_title(title,loc="left",fontsize=13)
        ax.set_xlabel("Easting (km)");ax.set_ylabel("Northing (km)")
        fig.colorbar(image,ax=ax,shrink=.8,label="m" if index==1 else "shade")
    fig.suptitle("Seoul North | Terrain candidate ROIs (EPSG:32652)",fontsize=19,weight="bold")
    _finish(fig,output/"candidate_rois.png")


def camera_sheet(key,frames,records,output):
    plt=_plt();fig=plt.figure(figsize=(16,13),layout="constrained")
    gs=fig.add_gridspec(3,4,width_ratios=[2.35,1,1,1])
    for row in range(3):
        frame=frames[row];rec=records[row]
        arrays=[frame["shade"],panel_pair(frame["shade"]),panel_pair(frame["silhouette"]),panel_pair(frame["wire"])]
        for col,(a,title) in enumerate(zip(arrays,["Panorama 16:9","Pair shade 640:900","Pair silhouette","Pair wireframe"])):
            ax=fig.add_subplot(gs[row,col]);ax.imshow(a,cmap="gray",vmin=0,vmax=1,interpolation="nearest")
            ax.set_xticks([]);ax.set_yticks([])
            if row==0:ax.set_title(title,fontsize=11)
            for spine in ax.spines.values():spine.set_color("#b8bcb5")
            if col==0:
                ax.set_xlabel(f"{rec['view_id']} | look {rec['azimuth_deg']:g} deg | elev {rec['elevation_deg']:g} deg\nD {rec['distance_m']/1000:.2f} km | VE {rec['vertical_exaggeration']:g}x | VFOV {rec['vertical_fov_deg']:g} deg",fontsize=11)
    fig.suptitle(f"Candidate {key}1 | Matched camera controls; lower hatching = ground outside ROI",fontsize=17,weight="bold")
    _finish(fig,output/f"candidate_{key}_views.png")


def control_sheet(all_frames,all_records,output):
    plt=_plt();fig,axes=plt.subplots(3,4,figsize=(12,14),layout="constrained")
    for row,key in enumerate("ABC"):
        indices=[0,3,4,5]
        for col,idx in enumerate(indices):
            rec=all_records[key][idx]
            axes[row,col].imshow(panel_pair(all_frames[key][idx]["shade"]),cmap="gray",vmin=0,vmax=1)
            axes[row,col].set_xticks([]);axes[row,col].set_yticks([])
            axes[row,col].set_title(f"{rec['view_id']}\nelev {rec['elevation_deg']:g} deg / D {rec['distance_m']/1000:.2f} km / VE {rec['vertical_exaggeration']:g}x",fontsize=9)
            if row==0:axes[row,col].set_xlabel(["Baseline","Elevation only","Distance only","Exaggeration only"][col],fontsize=10)
    fig.suptitle("One-variable camera controls | Same target and bearing within each row",fontsize=15,weight="bold")
    _finish(fig,output/"camera_controls.png")


def shortlist_sheet(all_frames,all_records,output,view_indices=None):
    if view_indices is None:view_indices={"A":0,"B":0,"C":0}
    plt=_plt();fig=plt.figure(figsize=(12,12),layout="constrained")
    gs=fig.add_gridspec(3,2,width_ratios=[2.5,1])
    for row,key in enumerate("ABC"):
        idx=view_indices[key];rec=all_records[key][idx];frame=all_frames[key][idx]
        for col,a in enumerate([frame["shade"],panel_pair(frame["shade"])]):
            ax=fig.add_subplot(gs[row,col]);ax.imshow(a,cmap="gray",vmin=0,vmax=1);ax.set_xticks([]);ax.set_yticks([])
            ax.set_title(f"{rec['view_id']} | "+("16:9 panorama" if col==0 else "640 x 900 mm pair"),loc="left",fontsize=12)
    fig.suptitle("Terrain shortlist for discussion | No final composition selected",fontsize=17,weight="bold")
    _finish(fig,output/"terrain_shortlist.png")


def run_exploration(master_path,config_path,output_dir,base_revision=None):
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    cfg=yaml.safe_load(Path(config_path).read_text())
    before=sha256_file(master_path)
    all_frames={};all_records={};candidates=[]
    with rasterio.open(master_path) as ds:
        if str(ds.crs)!=cfg["input_crs"]:raise ValueError("Unexpected DEM CRS.")
        ranks=scan_rois(ds,tuple(cfg["selection"]["spans_m"]),cfg["selection"]["scan_step_pixels"],cfg["selection"]["keep_per_type"])
        for key in "ABC":
            index=cfg["selection"]["selected_ranks"][key]
            candidate=dict(ranks[key][index]);candidate["candidate_id"]=key+"1";candidate["selection_rank"]=index+1
            grid=load_grid(ds,candidate["bounds_utm_m"])
            candidate["bounds_utm_m"]=list(grid.bounds_m)
            center=candidate["center_utm_m"]
            lon,lat=transform(ds.crs,"EPSG:4326",[center[0]],[center[1]])
            candidate["center_wgs84_lon_lat"]=[lon[0],lat[0]]
            candidate["bounds_wgs84_wsen"]=list(transform_bounds(ds.crs,"EPSG:4326",*grid.bounds_m))
            candidate["roi_size_m"]=[grid.bounds_m[2]-grid.bounds_m[0],grid.bounds_m[3]-grid.bounds_m[1]]
            candidate["name"]=None
            target=[*center,float(np.median(grid.elevation_m[grid.valid]))]
            settings=cfg["camera"]
            baseline=Camera(settings["bearings_deg"][key][0],settings["elevation_deg"],candidate["roi_size_m"][0]*settings["distance_to_roi_width_ratio"],settings["vertical_exaggeration"],settings["vertical_fov_deg"],settings["near_m"])
            cameras=[replace(baseline,azimuth_deg=b) for b in settings["bearings_deg"][key]]
            controls=settings["controls"]
            cameras += [replace(baseline,elevation_deg=controls["high_elevation_deg"]),replace(baseline,distance_m=baseline.distance_m*controls["far_distance_multiplier"]),replace(baseline,vertical_exaggeration=controls["unexaggerated_scale"])]
            frames=[];records=[]
            for i,camera in enumerate(cameras):
                print(f"Rendering {key}-V{i+1}: bearing={camera.azimuth_deg}, elevation={camera.elevation_deg}, distance={camera.distance_m}, VE={camera.vertical_exaggeration}",flush=True)
                frame=render_terrain(grid,camera,target,cfg["preview"]["width_px"],cfg["preview"]["height_px"],cfg["preview"]["mesh_stride"],wire=i<3)
                record={"view_id":f"{key}-V{i+1}","candidate_id":key+"1",**camera.record(target),**frame["metadata"]}
                occupancy=np.where(frame["occupied"],.14,1)
                record["pair_visible_fraction_excluding_gap"]=float((panel_pair(occupancy)<1).mean()*640/600)
                frames.append(frame);records.append(record)
            all_frames[key]=frames;all_records[key]=records;candidates.append(candidate)
            camera_sheet(key,frames,records,output)
        overview(ds,candidates,output)
        control_sheet(all_frames,all_records,output)
        shortlist_sheet(all_frames,all_records,output,cfg["preview"].get("shortlist_view_indices"))
        # Check one highly faceted candidate at native sampling as well.
        native_grid=load_grid(ds,candidates[0]["bounds_utm_m"])
        native_camera=Camera(**{k:all_records["A"][0][k] for k in ["azimuth_deg","elevation_deg","distance_m","vertical_exaggeration","vertical_fov_deg","near_m"]})
        native=render_terrain(native_grid,native_camera,all_records["A"][0]["target_raw_xyz_m"],cfg["preview"]["width_px"],cfg["preview"]["height_px"],stride=1,wire=False)
        plt=_plt();fig,axes=plt.subplots(1,2,figsize=(14,5),layout="constrained")
        for ax,a,title in zip(axes,[all_frames["A"][0]["shade"],native["shade"]],["A-V1 | 60 m sampled preview mesh","A-V1 | Native 30 m sampled mesh"]):
            ax.imshow(a,cmap="gray",vmin=0,vmax=1);ax.set_title(title,fontsize=12);ax.set_xticks([]);ax.set_yticks([])
        fig.suptitle("Sampling check | Same camera and exaggeration; no added terrain information",fontsize=15)
        _finish(fig,output/"native_sampling_check.png")
    report={"schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),
            "repository_base_revision":base_revision,"master_sha256":before,
            "configuration_sha256":sha256_file(config_path),"configuration":cfg,
            "source_modules_sha256":{str(p.relative_to(Path(__file__).parents[1])):sha256_file(p) for p in [Path(__file__),Path(__file__).with_name("terrain_preview.py"),Path(__file__).parents[1]/"projection/camera.py",Path(__file__).parents[1]/"terrain/candidates.py"]},
            "environment":{"python":platform.python_version(),"numpy":np.__version__,"rasterio":rasterio.__version__},
            "candidates":candidates,"ranked_windows":ranks,"views":[r for v in all_records.values() for r in v],
            "native_sampling_check":{"view_id":"A-V1","metadata":native["metadata"]},
            "source_dem_modified":False,"input_hash_unchanged":before==sha256_file(master_path),
            "limitations":["No verified place names, rock exposure, or urban land-use labels","Finite ROI edges are cropped mesh boundaries, not a full regional horizon","60 m mesh sampling for preview; original DEM remains 30 m","Diagnostic mesh edges are not brush strokes","No production paths or G-code generated"]}
    if not report["input_hash_unchanged"]:raise RuntimeError("Input bytes changed.")
    (output/"exploration.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--master",required=True,type=Path);p.add_argument("--config",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path);p.add_argument("--base-revision")
    a=p.parse_args();run_exploration(a.master,a.config,a.output,a.base_revision)


if __name__=="__main__":main()
