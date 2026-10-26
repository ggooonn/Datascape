"""New Summer cameras on the original DEM; Spring is read only."""
from pathlib import Path
from copy import deepcopy
import argparse, io, json, hashlib
import numpy as np
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.rendering.ground_study import load_scene, make_camera
from datascape.projection.ground import GroundComposite
from datascape.rendering.ground_composition import render
from datascape.composition.fields import mapped_source_coordinates

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/experiments/summer_scene_v01'

def spring_fields():
    path=ROOT/'artworks/spring_v13/source'
    manifest=json.loads((path/'fields_manifest.json').read_text())
    parts=[]
    for entry in manifest['parts']:
        raw=(path/entry['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Spring field part mismatch')
        parts.append(raw)
    raw=b''.join(parts)
    if hashlib.sha256(raw).hexdigest()!=manifest['file_sha256']:raise ValueError('Spring fields mismatch')
    return dict(np.load(io.BytesIO(raw)))

def skyline(occupied):
    valid=occupied.any(axis=0)
    y=np.argmax(occupied,axis=0).astype(float)+.5
    y[~valid]=np.nan
    return y*900/occupied.shape[0]

def boundary(a,b):
    # Least-squares 35 mm end-window directions, measured before any display gap.
    def slope(y,side):
        values=y[-35:] if side=='right' else y[:35]
        good=np.isfinite(values)
        return float(np.polyfit(np.arange(len(values))[good],values[good],1)[0]) if good.sum()>2 else None
    return dict(height_step_mm=float(b[0]-a[-1]),left_slope_dy_dx=slope(a,'right'),right_slope_dy_dx=slope(b,'left'))

def run(master,out=OUT):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    base=json.loads((ROOT/'configs/scenes/seoul_ground_composition_v01.json').read_text())
    reference=spring_fields();print('Verified frozen Spring fields',flush=True)
    occ=reference['f_occupied']
    if occ is None:raise ValueError('Spring occupancy missing')
    spring=skyline(occ)
    recipes=[('A_south',[325605,4166585],[320520,4168070],'A1 southern/core approach'),
             ('B_northwest',[319605,4171385],[321720,4171370],'B1 broad ridge/valley from northwest'),
             ('C_east',[327105,4170785],[323820,4168370],'C1 eastern lowland transition')]
    records=[]
    with rasterio.open(master) as ds:
        for name,eye,target,reason in recipes:
            scene=deepcopy(base);scene.update(primary_eye_xy_m=eye,look_target_xy_m=target,
                primary_bounds_m=[315000,4162500,330000,4175700],raster_pixels=[600,900],mesh_stride=1)
            scene['composite'].update(near_width_m=650.,width_growth=.85,depth_scale_m=1500.,
                depth_rise=.76,height_coefficients_per_km=[.14,.25,.38])
            camera,site=make_camera(ds,eye,target,2,0,36,1)
            grid,slope=load_scene(ds,scene['primary_bounds_m']);projection=GroundComposite(camera,site['source_dem_at_eye_m'],**scene['composite'])
            terrain=render(grid,projection,600,900,slope,stride=1,physical=False,depth_edges_m=scene['depth_edges_m'])
            xyz,occupied=mapped_source_coordinates(terrain);line=skyline(occupied)
            plt.imsave(out/f'{name}_surface.png',terrain['shade'],cmap='gray',vmin=0,vmax=1)
            np.savez_compressed(out/f'{name}_surface.npz',xyz=xyz,occupied=occupied,skyline=line)
            (out/f'{name}_scene.json').write_text(json.dumps(scene,indent=2)+'\n')
            records.append(dict(id=name,regional_basis=reason,camera=site,scene=scene,
                metrics=terrain['metrics'],P2_P3=boundary(spring,line),skyline_mm=line.tolist()))
            print(name,records[-1]['P2_P3'],flush=True)
    fig,axes=plt.subplots(1,3,figsize=(12,7))
    for ax,r in zip(axes,records):
        ax.imshow(plt.imread(out/f'{r["id"]}_surface.png'),extent=[0,600,900,0]);ax.axvline(300,c='#b9976b',ls='--',lw=.7)
        ax.set_title(r['regional_basis'],fontsize=10);ax.set_xlabel('Continuous painted X (mm)')
    axes[0].set_ylabel('Top-down Y (mm)');fig.suptitle('Summer candidate surfaces | same projection principles, new cameras');fig.tight_layout();fig.savefig(out/'viewpoint_candidates.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(13,9),sharex=True,sharey=True)
    for ax,r in zip(axes,records):
        y=np.array(r['skyline_mm']);x=np.arange(600)+.5
        ax.plot(x[:300],spring[:300],c='#806e57',lw=1.3);ax.plot(x[300:]+40,spring[300:],c='#806e57',lw=1.3)
        ax.plot(x[:300]+680,y[:300],c='#264f4a',lw=1.3);ax.plot(x[300:]+720,y[300:],c='#264f4a',lw=1.3)
        for lo,hi in [(300,340),(640,680),(980,1020)]:ax.axvspan(lo,hi,color='#dddcd7')
        ax.set_title(f'{r["id"]} | P2-P3 height step {r["P2_P3"]["height_step_mm"]:+.1f} mm',loc='left',fontsize=10)
        ax.set_ylim(680,50);ax.set_xlim(0,1320);ax.grid(axis='y',alpha=.15)
    axes[-1].set_xticks([150,490,830,1170],['P1 / Spring','P2 / Spring','P3 / Summer','P4 / Summer'])
    fig.suptitle('P1-P4 skyline comparison | 40 mm gaps; actual heights; no alignment warp')
    fig.tight_layout();fig.savefig(out/'skyline_candidates_P1_P4.png',dpi=160);plt.close(fig)
    record=dict(candidates=records,spring_skyline_mm=spring.tolist(),spring_fields_sha256='712ea50d328ea4956b387aee43e185dd19628748b55210efafdcf7968f79a233',
        policy='Provisional visual relationship only; no Spring edit, translation, silhouette fitting, or geographic connection assertion')
    (out/'viewpoint_review.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--master',required=True);p.add_argument('--output',type=Path,default=OUT);a=p.parse_args();run(a.master,a.output)
