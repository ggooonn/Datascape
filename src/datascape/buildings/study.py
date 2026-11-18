"""Run the reproducible Seoul North audit, geometry and projection study."""

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
import pyarrow as pa
import pyarrow.parquet as pq
import shapely

from datascape.data.quality import sha256_file

from .ground import GroundModel, register_terrain, sample
from .massing import Mass, height_policy, make_masses
from .projection import composite, create_mapping, project_masses, terrain_layers
from .source import collection_audit, distribution, morphology, part_audit, read_source
from .visuals import comparison_chart, detail_chart, part_chart, scene_image


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def summary(rows):
    return {
        band: {
            "surface_rasterized": sum(row["isolated_px"] > 0 for row in rows if row["band"] == band),
            "objects_visible": sum(row["visible_px"] > 0 for row in rows if row["band"] == band),
            "objects_full_terrain_hide": sum(row["terrain_blocked_px"] > 0 and row["visible_px"] == 0 and
                                             row["building_blocked_px"] == 0 for row in rows if row["band"] == band),
            "visible_classes": dict(Counter(row["class"] or "no_class" for row in rows
                                          if row["band"] == band and row["visible_px"] > 0)),
            **{key: sum(row[key] for row in rows if row["band"] == band)
               for key in ("isolated_px", "visible_px", "terrain_blocked_px", "building_blocked_px")},
        } for band in ("near", "middle", "far")
    }


def positive_part_overlap_case(parts, masses):
    parent_by_id = {mass.id: mass for mass in masses if mass.height_kind == "overture_height_field"}
    groups = {}
    for row, geom, eligible in zip(parts.records, parts.footprints, parts.eligible):
        height = height_policy(row)
        parent_id = row["building_id"]
        if eligible and height is not None and parent_id in parent_by_id:
            parent = parent_by_id[parent_id]
            groups.setdefault(parent_id, []).append(
                Mass(row["id"], geom, parent.base_m, row["min_height"] or 0.0, *height,
                     parent_id=parent_id, ground_kind=parent.ground_kind)
            )
    ranked = []
    for parent, members in groups.items():
        count = sum(a.footprint.intersection(b.footprint).area > .01
                    for i, a in enumerate(members) for b in members[:i])
        if count:
            ranked.append((count, len(members), parent))
    if not ranked:
        return None
    count, _, parent_id = max(ranked)
    parent = parent_by_id[parent_id]
    width = max(parent.footprint.bounds[2] - parent.footprint.bounds[0],
                parent.footprint.bounds[3] - parent.footprint.bounds[1], 80)
    return parent, groups[parent_id], float(width), count


def grouping_audit(buildings):
    from scipy.spatial import cKDTree

    selection = [i for i, row in enumerate(buildings.records) if buildings.eligible[i]
                 and row.get("class") == "apartments"]
    geom = buildings.footprints[selection]
    measures = morphology(geom)
    coordinates = shapely.get_coordinates(shapely.centroid(geom))
    tree = cKDTree(coordinates)
    area = measures["footprint_area_m2"]
    bearing = measures["long_axis_bearing_deg_mod180"]
    elongation = measures["elongation_min_rectangle"]
    pairs = []
    for a, b in sorted(tree.query_pairs(95)):
        angle = abs(bearing[a] - bearing[b])
        if min(angle, 180 - angle) <= 12 and .65 < area[a] / area[b] < 1 / .65 and min(elongation[a], elongation[b]) >= 1.6:
            pairs.append([buildings.records[selection[a]]["id"], buildings.records[selection[b]]["id"]])
    eligible = np.flatnonzero(buildings.eligible)
    valid_geom = buildings.footprints[eligible]
    small = valid_geom[(shapely.area(valid_geom) >= 20) & (shapely.area(valid_geom) <= 180)]
    points = shapely.get_coordinates(shapely.centroid(small))
    small_tree = cKDTree(points)
    neighbors = small_tree.query_ball_point(points, r=35, return_length=True) - 1
    return {
        "apartment_alignment": {
            "native_class": "apartments", "candidate_pairs": len(pairs), "example_ids": pairs[:8],
            "rule": "Within 95 m; elongation >= 1.6; axial difference <= 12 deg; areas within a 0.65 ratio.",
        },
        "small_footprint_density": {
            "footprints_20_to_180_m2": len(small),
            "with_five_or_more_other_small_footprints_within_35m": int((neighbors >= 5).sum()),
            "interpretation": "Plan-based morphology; height, building use and ownership are independent.",
        },
    }


def run(config_path, input_path, dsm_paths, dtm_paths, output):
    config = json.loads(config_path.read_text())
    root = Path(__file__).resolve().parents[3]
    scene = json.loads((root / "configs/scenes/seoul_projection_composition_v01.json").read_text())
    spring = json.loads((root / "configs/scenes/seoul_spring_production_v01.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    bounds = config["overture_bbox_wsen"]
    crs, step = config["metric_crs"], config["terrain_grid_m"]
    local = Transformer.from_crs("OGC:CRS84", crs, always_xy=True)
    geographic = Transformer.from_crs(crs, "OGC:CRS84", always_xy=True)
    acquisition = json.loads((input_path / "acquisition.json").read_text())
    if acquisition["release"] != config["overture_release"] or acquisition["bounds_wsen"] != bounds:
        raise ValueError("Acquisition metadata does not match the study bounds and release.")
    for kind in ("building", "building_part"):
        if sha256_file(input_path / f"{kind}.parquet") != acquisition["collections"][kind]["extract_sha256"]:
            raise ValueError(f"{kind} extract does not match its manifest.")
    buildings = read_source(input_path / "building.parquet", bounds, crs)
    parts = read_source(input_path / "building_part.parquet", bounds, crs)
    print(f"Read {len(buildings.records):,} buildings and {len(parts.records):,} parts", flush=True)
    audit = {"acquisition": acquisition, "buildings": collection_audit(buildings, detailed=True),
             "building_parts": collection_audit(parts), "part_relationships": part_audit(buildings, parts),
             "grouping": grouping_audit(buildings)}
    save_json(output / "data_audit.json", audit)
    dsm = register_terrain(dsm_paths, config["datascape_roi_wsen"], crs, step)
    dtm = register_terrain(dtm_paths, config["datascape_roi_wsen"], crs, step) if dtm_paths else None
    support_coverage = shapely.transform(shapely.box(*bounds), local.transform, interleaved=False)
    ground = GroundModel(dsm, dtm, buildings.footprints[buildings.eligible], support_coverage)
    masses, source_rows, heights = make_masses(buildings, ground)
    primary = dtm if dtm is not None else dsm
    base_by_id = {mass.id: mass for mass in masses}
    geometry_rows, ground_rows = [], []
    measures = morphology([geom for _, geom, _ in source_rows])
    for i, (row, geom, height) in enumerate(source_rows):
        mass = base_by_id.get(row["id"])
        samples = {
            key: float(value[i]) if np.isfinite(value[i]) else None
            for key, value in heights.items() if key != "xy"
        }
        geometry_rows.append({
            "id": row["id"], "footprint_local_wkb": geom.wkb,
            "class": row["class"], "subtype": row["subtype"], "bottom_offset_m": row["min_height"] or 0.0,
            "height_m": height[0], "height_kind": height[1],
            **{key: float(values[i]) for key, values in measures.items()},
        })
        ground_rows.append({
            "id": row["id"], "base_m": mass.base_m if mass else None,
            "ground_kind": mass.ground_kind if mass else None, **samples,
        })
    pq.write_table(pa.Table.from_pylist(geometry_rows), output / "height_geometry.parquet", compression="zstd")
    pq.write_table(pa.Table.from_pylist(ground_rows), output / "ground_samples.parquet", compression="zstd")
    height_audit = {
        "modeled": dict(Counter(mass.height_kind for mass in masses)),
        "modeled_ground": dict(Counter(mass.ground_kind for mass in masses)),
        "eligible_height_rows_without_ground": len(source_rows) - len(masses),
        "dsm_raw_minus_dtm_m": distribution(heights["raw_dsm_m"] - heights["dtm_m"]),
        "dsm_ground_proxy_minus_dtm_m": distribution(heights["dsm_proxy_m"] - heights["dtm_m"]),
        "dsm_ground_proxy_fit_residual_median_abs_m": distribution(heights["dsm_proxy_residual_median_abs_m"]),
        "dtm_footprint_vertex_relief_m": distribution(heights["dtm_footprint_vertex_relief_m"]),
        "dtm_footprint_vertex_relief_over_5m": int((heights["dtm_footprint_vertex_relief_m"] > 5).sum()),
        "terrain_valid_fraction": float(primary.grid.valid.mean()),
        "metric_crs": crs, "metric_bounds": list(primary.grid.bounds_m),
        "vertical_datum": config["terrain_crs_vertical_datum"],
        "inputs": {
            kind: [{"name": path.name, "sha256": sha256_file(path)} for path in paths]
            for kind, paths in [("copernicus_dsm", dsm_paths), ("fabdem_dtm", dtm_paths)]
        },
    }
    save_json(output / "height_ground_audit.json", height_audit)
    print(f"Based {len(masses):,} masses", flush=True)
    screens = []
    width, height = config["screen_px"]
    measured = [mass for mass in masses if mass.height_kind == "overture_height_field"]
    for view in config["views"]:
        xy = np.asarray([local.transform(*view["target_lon_lat"])])
        target_z = sample(primary, xy)[0]
        if not np.isfinite(target_z):
            raise ValueError(f"No terrain sample at view {view['id']} anchor.")
        mapping = create_mapping(view, local, target_z, scene, spring)
        land = terrain_layers(primary.grid, mapping, width, height, stride=1)
        projected = project_masses(measured, mapping, width, height)
        foreground = [item for item in projected if item.band != "far"]
        far = [item for item in projected if item.band == "far"]
        owner, tones, rows = composite(foreground, land, width, height)
        all_owner, all_tones, rows_all = composite(projected, land, width, height)
        stats = summary(rows)
        relief = primary.grid.elevation_m[primary.grid.valid]
        metric = {
            "view": view, "mapping": mapping.record(),
            "terrain_kind": "fabdem_dtm_proxy" if dtm is not None else "raw_copernicus_dsm",
            "classified_views": stats, "with_far_items": summary(rows_all),
            "far_candidates_outside_display_policy": len(far),
            "far_owner_pixels_if_enabled": sum(row["visible_px"] for row in rows_all if row["band"] == "far"),
            "terrain_frame_pixels": int((land[2] >= 0).sum()),
            "terrain_pixels_hidden_by_buildings": int(((land[2] >= 0) & (owner >= 0)).sum()),
            "terrain_25m_contour_band_pixels_hidden_by_buildings": int(
                ((np.abs((land[1] + 12.5) % 25 - 12.5) < 2.5) & (land[2] >= 0) & (owner >= 0)).sum()),
            "terrain_grid_elevation_range_m": [float(relief.min()), float(relief.max())],
            "virtual_eye_lon_lat": list(geographic.transform(*mapping.base.camera.frame(
                mapping.base.target_raw_xyz_m)[0][:2])),
        }
        print(f"View {view['id']} {view['name']}: "
              f"{stats['near']['objects_visible']} near / {stats['middle']['objects_visible']} middle", flush=True)
        save_json(output / f"view_{view['id']}.json", metric)
        pq.write_table(pa.Table.from_pylist(rows), output / f"view_{view['id']}_visibility.parquet")
        screens.append({
            "view": view, "stats": metric, "mapping": mapping, "land": land,
            "image": scene_image(land, owner, tones, foreground),
            "with_far_image": scene_image(land, all_owner, all_tones, projected),
        })
    selected = next(screen for screen in screens if screen["view"]["id"] == config["selected_view_id"])
    selected_view = selected["view"]
    diagnostic = [mass for mass in masses if mass.height_kind != "overture_height_field"]
    overlay = [p for p in project_masses(measured + diagnostic, selected["mapping"], width, height)
               if p.band != "far"]
    estimate_owner, estimate_tone, estimate_rows = composite(overlay, selected["land"], width, height)
    selected["with_estimates_image"] = scene_image(selected["land"], estimate_owner, estimate_tone, overlay)
    selected["stats"]["floor_height_scenario_visible"] = sum(
        row["visible_px"] > 0 for row in estimate_rows if row["height_kind"] != "overture_height_field")
    save_json(output / f"view_{selected_view['id']}.json", selected["stats"])
    comparison_chart(screens, buildings, primary, selected_view["id"], output)
    detail_chart(selected, heights, output)
    case = positive_part_overlap_case(parts, masses)
    if case is not None:
        parent, children, span, plan_overlap = case
        target = parent.footprint.representative_point()
        lonlat = geographic.transform(target.x, target.y)
        part_view = {"target_lon_lat": lonlat, "bearing_deg": 312, "depth_anchors_m": [-span, 2.2 * span],
                     "mapping": {"p3_width_scale_m": span * 1.8, "p3_bottom_fraction": .87,
                                 "p3_depth_rise_fraction": .90, "p3_relief_fraction_per_km": 730 / span}}
        mapping = create_mapping(part_view, local, parent.base_m, scene, spring)
        part_chart(parent, children, mapping, plan_overlap, lonlat, output)
    save_json(output / "projection_summary.json", {"views": [s["stats"] for s in screens],
                                                  "selected_view": selected_view["id"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--extract", required=True, type=Path)
    parser.add_argument("--dsm", nargs="+", required=True, type=Path)
    parser.add_argument("--dtm", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.config, args.extract, args.dsm, args.dtm, args.output)


if __name__ == "__main__":
    main()
