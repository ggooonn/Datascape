"""Register tile elevations and compare DTM contacts with a DSM ground proxy."""

from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling, transform_bounds
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
import shapely

from datascape.data.quality import read_valid_band
from datascape.terrain.candidates import TerrainGrid


@dataclass
class RegisteredTerrain:
    grid: TerrainGrid
    transform: object


def register_terrain(paths, geographic_bounds, metric_crs, spacing):
    west, south, east, north = transform_bounds("OGC:CRS84", metric_crs, *geographic_bounds, densify_pts=21)
    west, south = np.floor(np.array([west, south]) / spacing) * spacing
    east, north = np.ceil(np.array([east, north]) / spacing) * spacing
    width, height = int((east - west) / spacing), int((north - south) / spacing)
    transform = from_origin(west, north, spacing, spacing)
    elevation = np.full((height, width), np.nan, dtype=np.float32)
    for path in paths:
        with rasterio.open(path) as source:
            tile = np.full_like(elevation, np.nan)
            reproject(read_valid_band(source, 1).astype("float32").filled(np.nan), tile,
                      src_transform=source.transform, src_crs=source.crs, src_nodata=np.nan,
                      dst_transform=transform, dst_crs=metric_crs, dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
        valid = np.isfinite(tile)
        elevation[valid] = tile[valid]
    row, col = np.indices(elevation.shape)
    x, y = transform * (col + .5, row + .5)
    grid = TerrainGrid(elevation, np.isfinite(elevation), x, y, (west, south, east, north),
                       (spacing, spacing))
    return RegisteredTerrain(grid, transform)


def sample(terrain, xy):
    col, row = ~terrain.transform * (xy[:, 0], xy[:, 1])
    return map_coordinates(terrain.grid.elevation_m, [row - .5, col - .5],
                           order=1, mode="constant", cval=np.nan)


class GroundModel:
    """DTM first. Fit an explicit DSM proxy only using footprint-free cells."""

    def __init__(self, dsm, dtm, valid_footprints, support_coverage):
        self.dsm = dsm
        self.dtm = dtm
        grid = dsm.grid
        urban = rasterize(((geom, 1) for geom in valid_footprints), out_shape=grid.valid.shape,
                          transform=dsm.transform, all_touched=True, dtype="uint8").astype(bool)
        within_extract = rasterize([(support_coverage, 1)], out_shape=grid.valid.shape,
                                   transform=dsm.transform, dtype="uint8").astype(bool)
        supported = grid.valid & within_extract & ~urban
        self.xy = np.column_stack([grid.x_m[supported], grid.y_m[supported]])
        self.z = grid.elevation_m[supported]
        if len(self.xy) < 12:
            raise ValueError("DSM ground proxy requires at least 12 footprint-free raster cells.")
        self.tree = cKDTree(self.xy)

    def compare(self, footprints):
        centers = shapely.get_coordinates(shapely.point_on_surface(footprints))
        raw_dsm = sample(self.dsm, centers)
        dtm_z = sample(self.dtm, centers) if self.dtm is not None else np.full(len(centers), np.nan)
        distances, neighbors = self.tree.query(centers, k=12, distance_upper_bound=180)
        valid = np.isfinite(distances)
        proxy = np.full(len(centers), np.nan)
        proxy_mad = np.full(len(centers), np.nan)
        for i in np.flatnonzero(valid.sum(axis=1) >= 6):
            indexes = neighbors[i, valid[i]]
            offset = self.xy[indexes] - centers[i]
            design = np.column_stack([np.ones(len(indexes)), offset / 90])
            weights = 1 / np.sqrt(np.maximum(distances[i, valid[i]], 30) / 30)
            result, _, rank, _ = np.linalg.lstsq(design * weights[:, None], self.z[indexes] * weights,
                                                 rcond=None)
            hull = shapely.multipoints(self.xy[indexes]).convex_hull
            if rank != 3 or not hull.covers(shapely.Point(centers[i])):
                continue
            proxy[i] = result[0]
            proxy_mad[i] = np.median(np.abs(self.z[indexes] - design @ result))
        # Flag contact uncertainty from local DTM footprint samples. A single
        # horizontal base is retained; the terrain can cover its upslope edge.
        spans = np.full(len(centers), np.nan)
        if self.dtm is not None:
            coords, indices = shapely.get_coordinates(footprints, return_index=True)
            heights = sample(self.dtm, coords)
            for i, group in enumerate(np.split(heights, np.flatnonzero(np.diff(indices)) + 1)):
                finite = group[np.isfinite(group)]
                if finite.size:
                    spans[i] = finite.max() - finite.min()
        return {
            "xy": centers, "dtm_m": dtm_z, "raw_dsm_m": raw_dsm,
            "dsm_proxy_m": proxy, "dsm_proxy_residual_median_abs_m": proxy_mad,
            "dsm_proxy_support_count_within_180m": valid.sum(axis=1),
            "nearest_footprint_free_cell_m": distances[:, 0],
            "dtm_footprint_vertex_relief_m": spans,
        }
