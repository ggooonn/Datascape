"""Experimental screen-space translations of an unchanged metric DEM mesh.

P2 and P3 are artistic mappings, not physical cameras or implementations of
historical painting theory. Visibility always uses the P0 source-camera depth.
"""
from dataclasses import asdict, dataclass, replace

import numpy as np

from datascape.projection.camera import Camera


def smoothstep(value):
    """C1-continuous transition with zero derivative at both endpoints."""
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def depth_weights(depth_fraction, transition=0.12):
    """Blend three thirds of the horizontal ROI depth, without hard seams."""
    if not 0 < transition < 1 / 3:
        raise ValueError("Transition must be between zero and one third.")
    d = np.asarray(depth_fraction)
    a = smoothstep((d - (1 / 3 - transition / 2)) / transition)
    b = smoothstep((d - (2 / 3 - transition / 2)) / transition)
    return np.column_stack([1 - a, a - b, b])


@dataclass(frozen=True)
class Composition:
    """All transformations are display-only; elevations remain in meters."""
    camera: Camera
    target_raw_xyz_m: tuple
    depth_extent_m: tuple
    horizontal_shift_fraction: float = 0.0
    transition_fraction: float = 0.12
    p1_height_multipliers: tuple = (1.15, 1.24, 1.08)
    p1_vertical_warp: float = 1.08
    p2_elevations_deg: tuple = (8.0, 12.0, 16.0)
    p2_vertical_offsets: tuple = (0.10, -0.01, -0.12)
    p3_width_scale_m: float = 5200.0
    p3_bottom_fraction: float = 1.04
    p3_depth_rise_fraction: float = 0.95
    p3_relief_fraction_per_km: float = 0.45
    p3_depth_power: float = 0.85

    def depth_fraction(self, xyz):
        """Normalized horizontal look-axis distance, independent of raw Z."""
        bearing = np.deg2rad(self.camera.azimuth_deg)
        look = np.array([np.sin(bearing), np.cos(bearing)])
        metric = (np.asarray(xyz)[:, :2] - self.target_raw_xyz_m[:2]) @ look
        lo, hi = self.depth_extent_m
        if hi <= lo:
            raise ValueError("Depth extent must have positive length.")
        return np.clip((metric - lo) / (hi - lo), 0, 1)

    def project(self, xyz, method, width, height):
        """Return screen pixels, common visibility depth, and depth fraction.

        Nonphysical mappings retain P0 depth for overlap ordering. This is a
        declared compositing rule, not a multi-view physical z-buffer.
        """
        xyz = np.asarray(xyz, dtype=float)
        target = self.target_raw_xyz_m
        base, source_depth = self.camera.project(xyz, target, width, height)
        d = self.depth_fraction(xyz)
        weights = depth_weights(d, self.transition_fraction)
        if method == "P0":
            pixel = base.copy()
        elif method == "P1":
            eye, basis = self.camera.frame(target)
            display = xyz.copy()
            multiplier = weights @ np.array(self.p1_height_multipliers)
            # Exaggerate relief around the common target height, keeping eye fixed.
            display[:, 2] = (target[2] + (xyz[:, 2] - target[2]) * multiplier) * self.camera.vertical_exaggeration
            local = (display - eye) @ basis.T
            focal = height / (2 * np.tan(np.deg2rad(self.camera.vertical_fov_deg) / 2))
            safe = np.where(local[:, 2] > self.camera.near_m, local[:, 2], np.nan)
            pixel = np.column_stack([width / 2 + focal * local[:, 0] / safe,
                                     height / 2 - focal * local[:, 1] / safe])
            pixel[:, 1] = height / 2 + (pixel[:, 1] - height / 2) * self.p1_vertical_warp
        elif method == "P2":
            views = []
            for angle, offset in zip(self.p2_elevations_deg, self.p2_vertical_offsets):
                camera = replace(self.camera, elevation_deg=angle)
                view, _ = camera.project(xyz, target, width, height)
                view[:, 1] += offset * height
                views.append(view)
            pixel = np.sum(np.stack(views, axis=1) * weights[:, :, None], axis=1)
        elif method == "P3":
            bearing = np.deg2rad(self.camera.azimuth_deg)
            right = np.array([np.cos(bearing), -np.sin(bearing)])
            lateral = (xyz[:, :2] - target[:2]) @ right
            # Orthographic width; depth moves upward, raw relief stays local.
            rise = d ** self.p3_depth_power * self.p3_depth_rise_fraction
            relief = (xyz[:, 2] - target[2]) / 1000 * self.p3_relief_fraction_per_km
            pixel = np.column_stack([width / 2 + lateral / self.p3_width_scale_m * width,
                                     (self.p3_bottom_fraction - rise - relief) * height])
        else:
            raise ValueError(f"Unknown projection method: {method}")
        pixel[:, 0] += width * self.horizontal_shift_fraction
        return pixel, source_depth, d

    def record(self):
        result = asdict(self)
        result["camera"] = self.camera.record(self.target_raw_xyz_m)
        result["visibility_rule"] = "P0 forward depth for all methods; reciprocal-depth screen-triangle interpolation"
        result["depth_rule"] = "Three equal horizontal look-axis thirds of the native ROI, with smooth blending"
        result["height_rule"] = "Display mapping only; source DEM samples remain unchanged"
        return result


def insert_panel_gap(image, gap_pixels):
    """Separate two equal halves without dropping or rescaling painted pixels."""
    if image.shape[1] % 2 or gap_pixels < 0 or int(gap_pixels) != gap_pixels:
        raise ValueError("An even content width and nonnegative integer gap are required.")
    center = image.shape[1] // 2
    gap = np.ones((image.shape[0], int(gap_pixels), *image.shape[2:]), dtype=image.dtype)
    return np.concatenate([image[:, :center], gap, image[:, center:]], axis=1)
