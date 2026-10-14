"""Low eye-height perspective and a contiguous terrain composite mapping."""
from dataclasses import dataclass, asdict

import numpy as np

from datascape.projection.composition import smoothstep


@dataclass(frozen=True)
class GroundCamera:
    """Raw-meter camera; positive pitch looks upward, azimuth clockwise from N.

    Eye Z is the source DEM sample plus a stated clearance. This is not proof
    of an accessible ground location: the 30 m surface cannot identify paths,
    water, buildings, vegetation or actual human-scale footing.
    """
    eye_xyz_m: tuple
    azimuth_deg: float
    pitch_deg: float = 1.0
    vertical_fov_deg: float = 48.0
    near_m: float = 1.0

    def __post_init__(self):
        if not -89 < self.pitch_deg < 89 or not 0 < self.vertical_fov_deg < 170 or self.near_m <= 0:
            raise ValueError("Use a finite sight pitch, valid field of view and positive near plane.")
        if len(self.eye_xyz_m) != 3 or not np.isfinite(self.eye_xyz_m).all():
            raise ValueError("Eye position must contain three finite raw-meter coordinates.")

    def frame(self):
        az, pitch = np.deg2rad([self.azimuth_deg, self.pitch_deg])
        forward = np.array([np.sin(az)*np.cos(pitch), np.cos(az)*np.cos(pitch), np.sin(pitch)])
        right = np.array([np.cos(az), -np.sin(az), 0.0])
        up = np.cross(right, forward)
        return np.asarray(self.eye_xyz_m), np.stack([right, up, forward])

    def project(self, xyz, width, height):
        eye, basis = self.frame()
        local = (np.asarray(xyz) - eye) @ basis.T
        depth = local[:, 2]
        focal = height/(2*np.tan(np.deg2rad(self.vertical_fov_deg)/2))
        safe = np.where(depth>=self.near_m, depth, np.nan)
        return np.column_stack([width/2+focal*local[:,0]/safe,
                                height/2-focal*local[:,1]/safe]), depth

    def horizontal_coordinates(self, xyz):
        az = np.deg2rad(self.azimuth_deg)
        delta = np.asarray(xyz)[:,:2] - np.asarray(self.eye_xyz_m)[:2]
        return delta @ np.array([np.cos(az), -np.sin(az)]), delta @ np.array([np.sin(az), np.cos(az)])

    def record(self):
        return {**asdict(self),"pitch_convention":"Positive upward, unlike the earlier downward camera elevation",
                "vertical_exaggeration":1.0,"projection":"Physical pinhole in raw DEM meters"}


@dataclass(frozen=True)
class GroundComposite:
    """P2-style smooth depth bands and P3-style upward unfolding on one scene.

    No source tile relocation or height replacement. Width expands with depth,
    near height remains restrained, and far terrain gains display relief.
    This is an artistic mapped surface, not a physical camera.
    """
    camera: GroundCamera
    ground_reference_m: float
    near_width_m: float = 600.0
    width_growth: float = 0.8
    bottom_fraction: float = 1.02
    depth_rise: float = 0.72
    depth_scale_m: float = 1400.0
    near_middle_transition_m: tuple = (400.0, 1000.0)
    middle_far_transition_m: tuple = (1800.0, 3200.0)
    height_coefficients_per_km: tuple = (0.12, 0.22, 0.32)

    def __post_init__(self):
        a0,a1=self.near_middle_transition_m
        b0,b1=self.middle_far_transition_m
        if not 0 <= a0 < a1 <= b0 < b1 or self.near_width_m <= 0 or self.width_growth < 0 or self.depth_scale_m <= 0:
            raise ValueError("Use ordered transitions, positive near width/depth scale and nonnegative width growth.")
        if len(self.height_coefficients_per_km)!=3 or min(self.height_coefficients_per_km)<=0:
            raise ValueError("All three relief coefficients must be positive.")

    def weights(self, q):
        a0,a1 = self.near_middle_transition_m
        b0,b1 = self.middle_far_transition_m
        a = smoothstep((q-a0)/(a1-a0))
        b = smoothstep((q-b0)/(b1-b0))
        return np.column_stack([1-a,a-b,b])

    def project(self, xyz, width, height):
        xyz = np.asarray(xyz)
        lateral,q = self.camera.horizontal_coordinates(xyz)
        span = self.near_width_m+self.width_growth*q
        safe = np.where(span>0,span,np.nan)
        k = self.weights(q) @ np.array(self.height_coefficients_per_km)
        rise = self.depth_rise*q/(q+self.depth_scale_m)
        relief = k*(xyz[:,2]-self.ground_reference_m)/1000
        pixel = np.column_stack([width/2+width*lateral/safe,
                                 height*(self.bottom_fraction-rise-relief)])
        return pixel,q

    def record(self):
        result=asdict(self)
        result["camera"]=self.camera.record()
        result["projection"]="Depth-banded contiguous composite; virtual depth = horizontal q; affine triangle interpolation"
        result["relation_to_P2_P3"]="Reuse P2 smooth depth-weighting and P3 upward depth/relief principles; these are new recorded rules, not unchanged old cameras"
        result["source_relocation"]="None; one contiguous source surface and shared source eye/azimuth with F1"
        return result

    def unproject(self,pixel,q,width,height):
        """Invert mapped XYZ when its virtual depth is known; no terrain lookup."""
        pixel=np.asarray(pixel);q=np.asarray(q)
        span=self.near_width_m+self.width_growth*q
        lateral=(pixel[:,0]/width-.5)*span
        rise=self.depth_rise*q/(q+self.depth_scale_m)
        k=self.weights(q)@np.array(self.height_coefficients_per_km)
        z=self.ground_reference_m+1000*(self.bottom_fraction-rise-pixel[:,1]/height)/k
        az=np.deg2rad(self.camera.azimuth_deg)
        xy=np.asarray(self.camera.eye_xyz_m)[:2]+lateral[:,None]*np.array([np.cos(az),-np.sin(az)])+q[:,None]*np.array([np.sin(az),np.cos(az)])
        return np.column_stack([xy,z])

    def volume_determinant(self,xyz,width,height):
        """Exact positive mapped-volume Jacobian for the front domain q>0."""
        _,q=self.camera.horizontal_coordinates(xyz)
        span=self.near_width_m+self.width_growth*q
        k=self.weights(q)@np.array(self.height_coefficients_per_km)
        return width*height*k/(1000*span)
