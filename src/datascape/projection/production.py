"""Foreground continuation and mapped-depth visibility for the spring pair.

The previous Composition remains the shared source of P2 camera blending and
P3 width/relief parameters. These additions do not alter archived study results.
"""
from dataclasses import dataclass, replace

import numpy as np

from datascape.projection.composition import Composition, depth_weights


def continued_power(depth, power, epsilon):
    """C1 extension of a normalized softened power to negative source depths.

    The derivative is finite at zero; terrain nearer than the old ROI does not
    collapse onto a clamped-depth shelf. f(0)=0 and f(1)=1.
    """
    if not 0 < power <= 1 or epsilon <= 0:
        raise ValueError("Use 0 < power <= 1 and a positive softening distance.")
    depth = np.asarray(depth, dtype=float)
    denominator = (1 + epsilon) ** power - epsilon ** power
    positive = ((np.maximum(depth, 0) + epsilon) ** power - epsilon ** power) / denominator
    slope = power * epsilon ** (power - 1) / denominator
    return np.where(depth < 0, slope * depth, positive)


@dataclass(frozen=True)
class ProductionMapping:
    """Metric source terrain and separate display-space coordinates/depth."""
    base: Composition
    p3_depth_softening: float = 0.05

    def source_fraction(self, xyz):
        bearing = np.deg2rad(self.base.camera.azimuth_deg)
        look = np.array([np.sin(bearing), np.cos(bearing)])
        metric = (np.asarray(xyz)[:, :2] - self.base.target_raw_xyz_m[:2]) @ look
        lo, hi = self.base.depth_extent_m
        return (metric - lo) / (hi - lo)

    def project(self, xyz, method, width, height):
        """Return mapped XY/depth, fixed-anchor source fraction, and P0 depth.

        P2 uses the same smooth weights for screen position and virtual depth.
        P3 uses positive horizontal distance from the base eye as virtual depth.
        Both define a mapped 3D mesh whose triangles are composited in screen
        space with affine depth interpolation. No single physical camera is
        claimed for either mapping.
        """
        xyz = np.asarray(xyz, dtype=float)
        d = self.source_fraction(xyz)
        if method == "P2":
            pixel, source_depth, _ = self.base.project(xyz, method, width, height)
            depths = []
            for angle in self.base.p2_elevations_deg:
                camera = replace(self.base.camera, elevation_deg=angle)
                _, depth = camera.project(xyz, self.base.target_raw_xyz_m, width, height)
                depths.append(depth)
            mapped_depth = np.sum(np.column_stack(depths) * depth_weights(d, self.base.transition_fraction), axis=1)
        elif method == "P3":
            _, source_depth = self.base.camera.project(xyz, self.base.target_raw_xyz_m, width, height)
            bearing = np.deg2rad(self.base.camera.azimuth_deg)
            right = np.array([np.cos(bearing), -np.sin(bearing)])
            target = self.base.target_raw_xyz_m
            lateral = (xyz[:, :2] - target[:2]) @ right
            rise = continued_power(d, self.base.p3_depth_power, self.p3_depth_softening) * self.base.p3_depth_rise_fraction
            relief = (xyz[:, 2] - target[2]) / 1000 * self.base.p3_relief_fraction_per_km
            pixel = np.column_stack([width / 2 + lateral / self.base.p3_width_scale_m * width,
                                     (self.base.p3_bottom_fraction - rise - relief) * height])
            pixel[:, 0] += width * self.base.horizontal_shift_fraction
            lo, hi = self.base.depth_extent_m
            mapped_depth = self.base.camera.distance_m + lo + d * (hi - lo)
        else:
            raise ValueError("The production study supports P2 and P3.")
        return pixel, mapped_depth, d, source_depth

    def record(self):
        return {"base_composition": self.base.record(),
                "p3_depth_softening": self.p3_depth_softening,
                "depth_anchors": "Fixed to the previous B1 ROI; foreground extension does not renormalize them",
                "p3_continuation": "Normalized softened power for d>=0; tangent continuation for d<0",
                "visibility": "Mapped virtual depth; affine interpolation over final screen triangles",
                "height_preservation": "Source DEM samples unchanged; display transforms stored separately"}


def mapping_jacobians(mapping, xyz, method, width, height, step_m=1.0):
    """Finite-difference 3D mapped-volume and constant-height plane checks.

    A terrain triangle reversing in 2D can be ordinary occlusion. The 3D
    determinant tests local inversion of the mapping itself instead. Sampling
    is explicit and does not constitute a global injectivity proof.
    """
    xyz = np.asarray(xyz, dtype=float)
    derivatives = []
    for axis in range(3):
        delta = np.zeros(3)
        delta[axis] = step_m
        plus = mapping.project(xyz + delta, method, width, height)
        minus = mapping.project(xyz - delta, method, width, height)
        a = np.column_stack([plus[0], plus[1]])
        b = np.column_stack([minus[0], minus[1]])
        derivatives.append((a - b) / (2 * step_m))
    jacobian = np.stack(derivatives, axis=2)
    volume = np.linalg.det(jacobian)
    plane = np.linalg.det(jacobian[:, :2, :2])
    return volume, plane
