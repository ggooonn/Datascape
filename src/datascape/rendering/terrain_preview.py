"""Occluded monochrome terrain previews from a sampled DEM mesh."""
import numpy as np


def mesh(grid,stride=2):
    """Sample existing elevations; no interpolation, normalization or smoothing."""
    if stride<1:raise ValueError("Mesh stride must be positive.")
    z=grid.elevation_m[::stride,::stride]
    valid=grid.valid[::stride,::stride]
    xyz=np.column_stack([grid.x_m[::stride,::stride].ravel(),grid.y_m[::stride,::stride].ravel(),z.ravel()])
    h,w=z.shape;indices=np.arange(h*w).reshape(h,w)
    a,b,c,d=indices[:-1,:-1].ravel(),indices[:-1,1:].ravel(),indices[1:,:-1].ravel(),indices[1:,1:].ravel()
    faces=np.concatenate([np.column_stack([a,b,c]),np.column_stack([b,d,c])])
    faces=faces[valid.ravel()[faces].all(axis=1)]
    return xyz,faces,indices


def rasterize_triangles(pixel,depth,faces,gray,width,height,near_m=1.0):
    """Perspective-correct reciprocal-depth z-buffer, with flat face shading.

    Faces crossing the near plane are discarded in this diagnostic viewer.
    Cameras are placed outside the ROI; discarded faces are counted by caller.
    """
    inverse=np.zeros((height,width),dtype=np.float64)
    image=np.ones((height,width),dtype=np.float32)
    for face,tone in zip(faces,gray):
        p=pixel[face];z=depth[face]
        if (z<=near_m).any() or not np.isfinite(p).all():continue
        xmin=max(0,int(np.floor(p[:,0].min())));xmax=min(width-1,int(np.ceil(p[:,0].max())))
        ymin=max(0,int(np.floor(p[:,1].min())));ymax=min(height-1,int(np.ceil(p[:,1].max())))
        if xmax<xmin or ymax<ymin:continue
        xx,yy=np.meshgrid(np.arange(xmin,xmax+1)+.5,np.arange(ymin,ymax+1)+.5)
        denom=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
        if abs(denom)<1e-10:continue
        b0=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/denom
        b1=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/denom
        b2=1-b0-b1
        iz=b0/z[0]+b1/z[1]+b2/z[2]
        region=inverse[ymin:ymax+1,xmin:xmax+1]
        wins=(b0>=-1e-8)&(b1>=-1e-8)&(b2>=-1e-8)&(iz>region)
        region[wins]=iz[wins]
        image[ymin:ymax+1,xmin:xmax+1][wins]=tone
    return image,inverse


def wire_image(pixel,depth,indices,inverse,grid_step=3):
    """Draw only visible sampled mesh rows/columns; these are not brush strokes."""
    height,width=inverse.shape;image=np.ones((height,width),dtype=np.float32)
    lines=[row for row in indices[::grid_step]]+[col for col in indices[:,::grid_step].T]
    for line in lines:
        for a,b in zip(line[:-1],line[1:]):
            p,q=pixel[a],pixel[b]
            if not np.isfinite([p,q]).all() or min(depth[a],depth[b])<=1:continue
            count=int(np.ceil(np.abs(q-p).max()))+1
            if count>4*(width+height):continue
            t=np.linspace(0,1,max(2,count));xy=p[None,:]*(1-t[:,None])+q[None,:]*t[:,None]
            ix=np.floor(xy[:,0]).astype(int);iy=np.floor(xy[:,1]).astype(int)
            inside=(ix>=0)&(ix<width)&(iy>=0)&(iy<height)
            ix,iy,t=ix[inside],iy[inside],t[inside]
            iz=(1-t)/depth[a]+t/depth[b]
            # Small pixel/depth tolerance for rasterized edges, not hidden-line transparency.
            visible=(inverse[iy,ix]>0)&(iz>=inverse[iy,ix]*.997)
            image[iy[visible],ix[visible]]=.18
    return image


def render_terrain(grid,camera,target,width=1200,height=675,stride=2,wire=True):
    xyz,faces,indices=mesh(grid,stride)
    pixel,depth=camera.project(xyz,target,width,height)
    display=xyz.copy();display[:,2]*=camera.vertical_exaggeration
    triangles=display[faces]
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normals[normals[:,2]<0]*=-1
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    # Fixed northwest light, 45-degree altitude; no cast-shadow simulation.
    light=np.array([-.5,.5,np.sqrt(.5)])
    lambert=np.maximum(normals@light,0)
    face_depth=depth[faces].mean(axis=1)
    distance_tone=np.clip((face_depth-camera.distance_m)/(camera.distance_m),0,1)*.15
    gray=np.clip(.20+.55*lambert+distance_tone,.15,.92)
    shade,inverse=rasterize_triangles(pixel,depth,faces,gray,width,height,camera.near_m)
    silhouette=np.where(inverse>0,.14,1).astype(np.float32)
    wireframe=wire_image(pixel,depth,indices,inverse) if wire else None
    # A finite terrain patch is not a full geographic horizon. Distinguish
    # uncovered ground below its lower edge from white sky above its skyline.
    occupied=inverse>0
    rows=np.arange(height)[:,None]
    last=np.max(np.where(occupied,rows,-1),axis=0)
    outside_ground=(rows>last[None,:])&(last[None,:]>=0)
    yy,xx=np.mgrid[:height,:width]
    hatch=np.where((xx+yy)%12<2,.84,.96).astype(np.float32)
    shade[outside_ground]=hatch[outside_ground]
    silhouette[outside_ground]=hatch[outside_ground]
    if wireframe is not None:wireframe[outside_ground]=hatch[outside_ground]
    return {"shade":shade,"silhouette":silhouette,"wire":wireframe,
            "occupied":occupied,
            "metadata":{"mesh_stride":stride,"mesh_spacing_m":float(grid.native_resolution_m[0]*stride),
                        "vertices":len(xyz),"triangles":len(faces),
                        "near_plane_discarded_triangles":int((depth[faces]<=camera.near_m).any(axis=1).sum()),
                        "visible_pixel_fraction":float(occupied.mean()),
                        "outside_roi_ground_pixel_fraction":float(outside_ground.mean())}}


def panel_pair(image,gap_mm=40,panel_mm=300,height_mm=900):
    """Center-crop to 640:900 and blank the real 40 mm screen gap.

    The gap removes that portion of the continuous view; painted areas are not
    stretched to replace it. Central image crop preserves vertical FOV.
    """
    width_mm=2*panel_mm+gap_mm
    crop_width=int(round(image.shape[0]*width_mm/height_mm))
    if crop_width>image.shape[1]:raise ValueError("Source image is too narrow for pair crop.")
    left=(image.shape[1]-crop_width)//2
    crop=image[:,left:left+crop_width].copy()
    g0=int(round(crop_width*panel_mm/width_mm))
    g1=int(round(crop_width*(panel_mm+gap_mm)/width_mm))
    crop[:,g0:g1]=1
    return crop
