"""Terrain-registered building prisms and separate height evidence."""

from dataclasses import dataclass

import numpy as np
import shapely

from .source import positive


@dataclass
class Mass:
    id: str
    footprint: object
    base_m: float
    bottom_offset_m: float
    height_m: float
    height_kind: str
    native_class: str | None = None
    native_subtype: str | None = None
    parent_id: str | None = None
    ground_kind: str = "fabdem_dtm_proxy"


def height_policy(row, floor_estimates=False):
    if row.get("is_underground") or (row.get("min_floor") and row.get("min_height") is None):
        return None
    if positive(row.get("height")):
        return float(row["height"]), "overture_height_field"
    if floor_estimates and positive(row.get("num_floors")) and not row.get("min_height"):
        return float(row["num_floors"]) * 3.0, "floor_count_x_3m_diagnostic_estimate"
    return None


def make_masses(source, ground):
    rows = [(row, geom, height_policy(row, floor_estimates=True))
            for row, geom, eligible in zip(source.records, source.footprints, source.eligible) if eligible]
    rows = [(row, geom, height) for row, geom, height in rows if height is not None]
    diagnostics = ground.compare([geom for _, geom, _ in rows])
    masses = []
    for i, (row, geom, height) in enumerate(rows):
        dtm = diagnostics["dtm_m"][i]
        base = dtm if np.isfinite(dtm) else diagnostics["dsm_proxy_m"][i]
        if np.isfinite(base):
            masses.append(Mass(row["id"], geom, float(base), row["min_height"] or 0.0,
                               *height, row.get("class"), row.get("subtype"),
                               ground_kind="fabdem_dtm_proxy" if np.isfinite(dtm) else "footprint_free_dsm_plane"))
    return masses, rows, diagnostics


def polygons(footprint):
    return [footprint] if footprint.geom_type == "Polygon" else list(footprint.geoms)


def prism(mass, footprint=None):
    """Return flattened XYZ triangles and per-triangle diagnostic shade.

    Roof tessellation is constrained to the polygon, including interior rings.
    Perimeter walls share the same absolute elevation as the flat top and base.
    """
    footprint = mass.footprint if footprint is None else footprint
    bottom = mass.base_m + mass.bottom_offset_m
    top = bottom + mass.height_m
    data, tones = [], []
    for polygon in polygons(footprint):
        roof_xy = shapely.get_coordinates(shapely.constrained_delaunay_triangles(polygon))
        roof_xy = roof_xy.reshape(-1, 4, 2)[:, :3].reshape(-1, 2)
        data.extend(np.column_stack([roof_xy, np.full(len(roof_xy), top)]).reshape(-1, 3, 3))
        tones.extend([.92] * (len(roof_xy) // 3))
        if mass.bottom_offset_m:
            data.extend(np.column_stack([roof_xy, np.full(len(roof_xy), bottom)]).reshape(-1, 3, 3))
            tones.extend([.55] * (len(roof_xy) // 3))
        for ring in (polygon.exterior, *polygon.interiors):
            for a, b in zip(ring.coords[:-1], ring.coords[1:]):
                p, q, r, s = (*a, bottom), (*b, bottom), (*b, top), (*a, top)
                data.extend([(p, q, r), (p, r, s)])
                dx, dy = np.subtract(b, a)
                weight = .62 + .19 * abs(dy) / max(np.hypot(dx, dy), 1e-10)
                tones.extend([weight, weight])
    return np.asarray(data).reshape(-1, 3), np.asarray(tones)
