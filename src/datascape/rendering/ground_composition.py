"""Ground-anchored terrain studies using existing mesh and raster utilities."""
from pathlib import Path
import json
import numpy as np

from datascape.rendering.terrain_preview import mesh
from datascape.rendering.composition_study import rasterize,save_figure,save_array
from datascape.rendering.spring_production import rasterize_mapped


def clip_near_plane(xyz,faces,depth,near_m):
    """Clip triangles to a linear camera/q plane without fabricating terrain.

    Added vertices are intersections on original triangle edges; they are
    geometry interpolation, not new measured DEM samples.
    """
    xyz=np.asarray(xyz)
    inside=depth[faces]>=near_m
    kept=faces[inside.all(axis=1)]
    ids=np.flatnonzero(inside.all(axis=1)).tolist()
    appended=[];extra_faces=[]
    crossings=np.flatnonzero(inside.any(axis=1)&~inside.all(axis=1))
    for face_id in crossings:
        face=faces[face_id];polygon=[]
        for a,b in zip(face,np.roll(face,-1)):
            da,db=depth[a],depth[b]
            if da>=near_m:polygon.append(int(a))
            if (da>=near_m)!=(db>=near_m):
                fraction=(near_m-da)/(db-da)
                point=xyz[a]+fraction*(xyz[b]-xyz[a])
                polygon.append(len(xyz)+len(appended));appended.append(point)
        for i in range(1,len(polygon)-1):
            extra_faces.append([polygon[0],polygon[i],polygon[i+1]]);ids.append(int(face_id))
    result_xyz=np.concatenate([xyz,np.asarray(appended).reshape(-1,3)]) if appended else xyz.copy()
    result_faces=np.concatenate([kept,np.asarray(extra_faces,dtype=int).reshape(-1,3)])
    return result_xyz,result_faces,np.asarray(ids),{"near_plane_m":near_m,"crossing_source_triangles":len(crossings),"edge_intersection_vertices":len(appended),"behind_plane_source_triangles":int((~inside.any(axis=1)).sum())}


def render(grid,projection,width,height,slope_grid,stride=1,physical=True,depth_edges_m=(600,2200)):
    """Return shades, silhouettes, source-depth bands and raw-surface metrics."""
    original,source_faces,_=mesh(grid,stride)
    _,depth=projection.project(original,width,height)
    near=max(getattr(projection,'near_m',1.0),1.0)+.0001
    xyz,faces,source_ids,clipping=clip_near_plane(original,source_faces,depth,near)
    pixel,depth=projection.project(xyz,width,height)
    finite=np.isfinite(pixel[faces]).all(axis=(1,2))
    p=np.where(np.isfinite(pixel[faces]),pixel[faces],0)
    lower,upper=p.min(axis=1),p.max(axis=1)
    frame=finite&(upper[:,0]>=0)&(upper[:,1]>=0)&(lower[:,0]<width)&(lower[:,1]<height)
    faces,source_ids=faces[frame],source_ids[frame]
    tri=xyz[faces]
    normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals[normals[:,2]<0]*=-1
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    camera=projection if physical else projection.camera
    _,q=camera.horizontal_coordinates(xyz)
    # Encode two exact distance breaks into three monotone source-depth bands.
    a,b=depth_edges_m
    fraction=np.interp(q,[0,a,b,10000],[0,1/3,2/3,1])
    tones=np.clip(.16+.58*np.maximum(normals@np.array([-.5,.5,np.sqrt(.5)]),0)+.12*np.clip(q[faces].mean(axis=1)/6000,0,1),.12,.90)
    if physical:
        shade,visible,owners=rasterize(pixel,depth,fraction,faces,tones,width,height)
    else:
        shade,visible,owners,_=rasterize_mapped(pixel,depth,fraction,faces,tones,width,height)
    occupied=owners>=0;yy,xx=np.mgrid[:height,:width]
    first=np.min(np.where(occupied,yy,height),axis=0)
    missing=(~occupied)&(yy>=first)
    hatch=np.where((xx+yy)%14<2,.84,.97)
    band=np.clip((np.nan_to_num(visible,nan=0)*3).astype(int),0,2)
    depth_image=np.where(occupied,np.array([.18,.48,.78])[band],1)
    silhouette=np.where(occupied,.14,1).astype(np.float32)
    for image in [shade,depth_image,silhouette]:image[missing]=hatch[missing]
    # Visible face means are native surface statistics, not street/rock labels.
    original_slope=slope_grid[::stride,::stride].ravel()
    face_height=original[source_faces[source_ids],2].mean(axis=1)
    face_slope=original_slope[source_faces[source_ids]].mean(axis=1)
    owner_safe=np.maximum(owners,0)
    visible_z=np.where(occupied,face_height[owner_safe],np.nan)
    visible_slope=np.where(occupied,face_slope[owner_safe],np.nan)
    lower_zone=occupied&(yy>=height*2/3)
    gentle=lower_zone&(visible_z<120)&(visible_slope<=10)
    bands=[]
    for i,label in enumerate(['foreground','middle_ground','background']):
        mask=occupied&(band==i)
        bands.append({'label':label,'visible_terrain_fraction':float(mask.sum()/max(1,occupied.sum())),
                      'centroid_y_fraction':float(yy[mask].mean()/height) if mask.any() else None})
    metrics={'mesh_stride':stride,'native_spacing_m':grid.native_resolution_m[0]*stride,
             'source_triangles':len(source_faces),'raster_candidate_triangles':len(faces),
             'terrain_frame_fraction':float(occupied.mean()),'uncovered_ground_fraction':float(missing.mean()),
             'bottom_edge_coverage_fraction':float(occupied[-1].mean()),
             'bottom_300mm_coverage_fraction':float(occupied[round(height*2/3):].mean()),
             'bottom_300mm_low_gentle_visible_fraction':float(gentle.sum()/max(1,lower_zone.sum())),
             'bottom_300mm_source_elevation_p10_p50_p90_m':np.percentile(visible_z[lower_zone],[10,50,90]).tolist() if lower_zone.any() else [],
             'bottom_300mm_source_slope_p50_p90_deg':np.percentile(visible_slope[lower_zone],[50,90]).tolist() if lower_zone.any() else [],
             'bottom_300mm_original_triangle_count':int(np.unique(source_ids[owners[lower_zone]]).size),
             'source_statistic_rule':'Visible original triangle means; low/gentle = elevation<120 m and exported SLOPE<=10 deg. This does not establish accessibility.',
             'depth_edges_m':list(depth_edges_m),'depth_bands':bands,'near_clipping':clipping}
    return {'shade':shade,'silhouette':silhouette,'depth':depth_image,'occupied':occupied,'owners':owners,
            'metrics':metrics,'xyz':xyz,'faces':faces,'pixel':pixel,'source_ids':source_ids}
