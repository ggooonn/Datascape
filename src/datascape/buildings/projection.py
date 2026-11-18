"""Project building and terrain faces using the shared Spring mapped surface."""

from dataclasses import dataclass

import numpy as np
import shapely

from datascape.projection.camera import Camera
from datascape.projection.composition import Composition
from datascape.projection.production import ProductionMapping
from datascape.rendering.spring_production import rasterize_mapped
from datascape.rendering.terrain_preview import mesh

from .massing import prism


@dataclass
class Projected:
    mass: object
    pixel: np.ndarray
    depth: np.ndarray
    fraction: np.ndarray
    tones: np.ndarray
    band: str


def create_mapping(view, local, elevation, scene, spring):
    anchor = view["depth_anchors_m"]
    x, y = local.transform(*view["target_lon_lat"])
    camera = Camera(view["bearing_deg"], scene["camera"]["elevation_deg"],
                    -anchor[0] + 1200, scene["camera"]["vertical_exaggeration"],
                    scene["camera"]["vertical_fov_deg"])
    controls = {**scene["mapping"], **spring["mapping_overrides"], **view.get("mapping", {})}
    return ProductionMapping(Composition(camera, (x, y, float(elevation)), tuple(anchor), **controls),
                             spring["p3_depth_softening"])


def project_masses(masses, mapping, width, height):
    items = []
    for mass in masses:
        if not np.isfinite(mass.base_m):
            continue
        left, bottom, right, top = mass.footprint.bounds
        z = mass.base_m + mass.bottom_offset_m
        corners = np.array([[x, y, elev] for x in (left, right) for y in (bottom, top)
                            for elev in (z, z + mass.height_m)])
        coarse, depth, _, _ = mapping.project(corners, "P3", width, height)
        lower, upper = coarse.min(axis=0), coarse.max(axis=0)
        if depth.max() <= 1 or (upper < 0).any() or (lower >= [width, height]).any():
            continue
        center = mass.footprint.representative_point()
        fraction = mapping.source_fraction([[center.x, center.y, z]])[0]
        band = ("near", "middle", "far")[int(np.clip(np.floor(fraction * 3), 0, 2))]
        # Display scale/visibility screens reuse the mapped thirds, then a
        # projected area gate avoids drawing sub-pixel shapes.
        if np.prod(upper - lower) < (4 if band == "near" else 3):
            continue
        footprint = mass.footprint
        if band != "near":
            footprint = shapely.simplify(footprint, 1.2 if band == "middle" else 2.0,
                                         preserve_topology=True)
        vertices, tones = prism(mass, footprint)
        pixel, depth, fraction, _ = mapping.project(vertices, "P3", width, height)
        items.append(Projected(mass, pixel, depth, fraction, tones, band))
    return items


def terrain_layers(grid, mapping, width, height, stride):
    xyz, faces, _ = mesh(grid, stride)
    pixel, depth, fraction, _ = mapping.project(xyz, "P3", width, height)
    tri = xyz[faces]
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normal *= np.where(normal[:, 2:3] < 0, -1, 1)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-9)
    light = np.clip(normal @ np.array([-.52, -.2, .83]), 0, 1)
    face_fraction = fraction[faces].mean(axis=1)
    tones = .73 + .17 * light
    shade, visible_z, owner, buffer = rasterize_mapped(pixel, depth, xyz[:, 2], faces,
                                                      tones, width, height)
    occupied = owner >= 0
    masked_fraction = face_fraction[owner[occupied]]
    # Shade rises to paper value in the far distance. This is a display
    # envelope; the original surface and its depth remain available.
    fade = np.clip((masked_fraction - .53) / .57, 0, 1)
    fade = fade**2 * (3 - 2 * fade)
    contour_distance = abs((visible_z[occupied] + 12.5) % 25 - 12.5)
    contour = np.clip(1 - contour_distance / 2.5, 0, 1)
    shade[occupied] = 1 - (1 - fade) * (1 - shade[occupied] + .22 * contour)
    return shade, visible_z, owner, buffer


def object_tile(item, width, height):
    lower = np.floor(item.pixel.min(axis=0)).astype(int).clip(0, [width, height])
    upper = (np.ceil(item.pixel.max(axis=0)).astype(int) + 1).clip(0, [width, height])
    tile_width, tile_height = upper - lower
    if tile_width <= 0 or tile_height <= 0:
        return None
    faces = np.arange(len(item.pixel)).reshape(-1, 3)
    rendered = rasterize_mapped(item.pixel - lower, item.depth, item.fraction,
                                faces, item.tones, tile_width, tile_height)
    x, y = lower
    return (slice(y, y + tile_height), slice(x, x + tile_width)), rendered


def composite(items, terrain, width, height):
    nearest = np.full((height, width), np.inf)
    owner = np.full((height, width), -1, dtype=np.int32)
    tones = np.ones((height, width), dtype=float)
    tiles = []
    for index, item in enumerate(items):
        tile = object_tile(item, width, height)
        tiles.append(tile)
        if tile is None:
            continue
        window, (tone, _, _, depth) = tile
        wins = depth < nearest[window]
        nearest[window][wins] = depth[wins]
        owner[window][wins] = index
        tones[window][wins] = tone[wins]
    buildings_win = nearest < terrain[3]
    final_owner = np.where(buildings_win, owner, -1)
    rows = []
    for index, (item, tile) in enumerate(zip(items, tiles)):
        if tile is None:
            continue
        window, (_, _, _, depth) = tile
        isolated = np.isfinite(depth)
        won = isolated & (final_owner[window] == index)
        blocked_terrain = isolated & (terrain[3][window] <= depth) & ~won
        blocked_building = isolated & ~won & ~blocked_terrain
        rows.append({
            "id": item.mass.id, "parent_id": item.mass.parent_id, "band": item.band,
            "height_kind": item.mass.height_kind, "class": item.mass.native_class,
            "ground_kind": item.mass.ground_kind,
            "isolated_px": int(isolated.sum()), "visible_px": int(won.sum()),
            "terrain_blocked_px": int(blocked_terrain.sum()),
            "building_blocked_px": int(blocked_building.sum()),
        })
    return final_owner, tones, rows
