"""Metric pinhole cameras for diagnostic terrain views, not brush paths."""
from dataclasses import dataclass, asdict
import numpy as np


@dataclass(frozen=True)
class Camera:
    """Azimuth is the look bearing, clockwise from geographic north.

    Distance is horizontal eye-to-target distance. Elevation is the downward
    sight angle. Raw DEM meters are never replaced by exaggerated elevations.
    """
    azimuth_deg: float
    elevation_deg: float
    distance_m: float
    vertical_exaggeration: float = 1.8
    vertical_fov_deg: float = 22.0
    near_m: float = 1.0

    def __post_init__(self):
        if not 0 < self.elevation_deg < 89:
            raise ValueError("Elevation must be between 0 and 89 degrees.")
        if self.distance_m <= 0 or self.vertical_exaggeration <= 0 or self.near_m <= 0:
            raise ValueError("Distance, exaggeration and near plane must be positive.")
        if not 0 < self.vertical_fov_deg < 170:
            raise ValueError("Vertical field of view must be between 0 and 170 degrees.")

    def frame(self, target_xyz_m):
        target=np.asarray(target_xyz_m,dtype=float).copy()
        target[2]*=self.vertical_exaggeration
        bearing=np.deg2rad(self.azimuth_deg)
        look=np.array([np.sin(bearing),np.cos(bearing),0.0])
        eye=target-self.distance_m*look
        eye[2]+=self.distance_m*np.tan(np.deg2rad(self.elevation_deg))
        forward=target-eye;forward/=np.linalg.norm(forward)
        right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right)
        up=np.cross(right,forward)
        return eye,np.stack([right,up,forward])

    def project(self, xyz_m, target_xyz_m, width, height):
        """Return pixel XY and forward depth, without mutating world vertices."""
        eye,basis=self.frame(target_xyz_m)
        xyz=np.asarray(xyz_m,dtype=float).copy()
        xyz[:,2]*=self.vertical_exaggeration
        local=(xyz-eye)@basis.T
        depth=local[:,2]
        focal=height/(2*np.tan(np.deg2rad(self.vertical_fov_deg)/2))
        safe=np.where(depth>self.near_m,depth,np.nan)
        pixel=np.column_stack([width/2+focal*local[:,0]/safe,
                               height/2-focal*local[:,1]/safe])
        return pixel,depth

    def record(self,target_xyz_m):
        eye,_=self.frame(target_xyz_m)
        return {**asdict(self),"target_raw_xyz_m":list(map(float,target_xyz_m)),
                "eye_display_xyz_m":eye.tolist(),"projection":"perspective",
                "azimuth_convention":"Look bearing clockwise from north",
                "distance_convention":"Horizontal eye-to-target distance",
                "display_z_transform":"raw elevation meters * vertical_exaggeration"}
