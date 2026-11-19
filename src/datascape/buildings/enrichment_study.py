"""Compare registry and floor evidence with the locked Seoul P3 baseline."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json

import numpy as np
from PIL import Image
import pyarrow as pa
import pyarrow.parquet as pq
from pyproj import Transformer
import shapely

from datascape.data.quality import sha256_file

from .ground import register_terrain, sample
from .massing import Mass
from .projection import composite, create_mapping, object_tile, project_masses, terrain_layers
from .regional import audit_evidence, choose_height, match_polygons, read_regional
from .source import distribution, read_source
from .study import save_json
from .visuals import scene_image
from .enrichment_visuals import charts, footprint_examples


def locked_baseline(root, inputs, checkpoint, terrain_paths):
    config = json.loads((root / "docs/experiments/buildings_work01/seoul_north.json").read_text())
    path = root / "docs/experiments/buildings_work01/validation.json"
    hashes = json.loads(path.read_text())["byte_identical_outputs"]
    references = ["viewpoint_comparison.png", "selected_geometry_visibility.png", "view_A.json",
                  "view_B.json", "view_C.json", "ground_samples.parquet"]
    if any(sha256_file(checkpoint / name) != hashes[name] for name in references):
        raise ValueError("Work 01 comparison files do not match the locked checkpoint.")
    acquisition = json.loads((inputs / "acquisition.json").read_text())
    if (config["overture_release"] != acquisition["release"] or
        config["overture_bbox_wsen"] != acquisition["bounds_wsen"] or
        sha256_file(inputs / "building.parquet") != acquisition["collections"]["building"]["extract_sha256"]):
        raise ValueError("The Overture extract does not match Work 01.")
    ground_report = json.loads((checkpoint / "height_ground_audit.json").read_text())
    expected = [item["sha256"] for item in ground_report["inputs"]["fabdem_dtm"]]
    if [sha256_file(path) for path in terrain_paths] != expected:
        raise ValueError("Use the original FABDEM tiles in the Work 01 order.")
    return config, {name: hashes[name] for name in references}


def build_evidence(buildings, registry, regional_shapes, authoritative, settings):
    matches = match_polygons(buildings.footprints, regional_shapes, settings["overlap"])
    # A provider ID shared by multiple polygons cannot be treated as a building-level key.
    duplicate_ids = {key for key, count in Counter(row["id"] for row in registry).items() if count > 1}
    covered = set()
    rows = []
    for row, link in zip(buildings.records, matches):
        index = link["region_index"]
        accepted = index is not None and registry[index]["id"] not in duplicate_ids
        region = registry[index] if accepted else {}
        native = choose_height(row, region, accepted and authoritative, settings["floor_rate_m"])
        if accepted:
            covered.add(index)
        rows.append({
            "id": row["id"], "native_class": row["class"], "native_subtype": row["subtype"],
            "match_status": "duplicate_regional_id" if index is not None and not accepted else link["status"],
            "matched_region_id": region.get("id"),
            "official_use": region.get("use_name") if authoritative else None,
            "official_use_code": region.get("use_code") if authoritative else None,
            "reference_archetype": region.get("archetype") if not authoritative else None,
            "official_parcel_id": region.get("parcel_id") if authoritative else None,
            "source_use_agreement": use_agreement(row, native["regional_family"]),
            "regional_attributes": region if accepted else None,
            **native,
            "candidate_overlaps": [
                {**candidate, "region_id": registry[candidate["region_index"]]["id"]}
                for candidate in link["candidates"]
            ],
        })
    return rows, {"regional_rows_in_high_confidence_matches": len(covered),
                  "regional_rows_without_high_confidence_match": len(registry) - len(covered)}


def use_agreement(row, regional):
    if not regional or not row.get("subtype"):
        return None
    native = row["subtype"]
    if regional in {"apartment", "other_residential", "small_residential"}:
        return "compatible_broad_use" if native == "residential" else "check_broad_use"
    if regional == "retail_facility":
        return "compatible_broad_use" if native == "commercial" else "check_broad_use"
    return "different_taxonomy"


def masses_by_scenario(buildings, evidence, ground_m):
    native, supported, floor = [], [], []
    for row, geom, entry, z in zip(buildings.records, buildings.footprints, evidence, ground_m):
        if not np.isfinite(z):
            continue
        args = (row["id"], geom, float(z), row["min_height"] or 0.0)
        tail = (row["class"], row["subtype"])
        if entry["h0_m"] is not None:
            native.append(Mass(*args, entry["h0_m"], "overture_height_field", *tail))
        if entry["h1_m"] is not None:
            kind = "overture_height_field" if entry["h1_source"] == "overture" else "regional_official_height"
            supported.append(Mass(*args, entry["h1_m"], kind, *tail))
        if entry["h2_m"] is not None:
            floor.append(Mass(*args, entry["h2_m"], entry["h2_floor_source"], *tail))
    return native, supported, floor


def crop_view(reference, width, center_y):
    """Use a uniform crop of the projected frame, with an identical source camera."""
    factor = reference["mapping"]["p3_width_scale_m"] / width
    source = reference["mapping"]
    mapping = {**source, "p3_width_scale_m": width,
               "p3_relief_fraction_per_km": source["p3_relief_fraction_per_km"] * factor,
               "p3_bottom_fraction": .5 + (source["p3_bottom_fraction"] - center_y) * factor,
               "p3_depth_rise_fraction": reference["p3_depth_rise_fraction"] * factor}
    return {**reference, "id": f"A1-{width}", "mapping": mapping}


def choose_near_site(masses, terrain, local, geographic, box, scene, spring, px):
    geom = np.asarray([m.footprint for m in masses], dtype=object)
    centers = shapely.get_coordinates(shapely.point_on_surface(geom))
    lon, lat = geographic.transform(*centers.T)
    inside = (lon >= box[0]) & (lon <= box[2]) & (lat >= box[1]) & (lat <= box[3])
    if not inside.any():
        raise ValueError("The A2 search window contains no height-bearing building.")
    queries = np.unique(np.round(centers[inside] / 65) * 65, axis=0)
    use = np.array([m.native_class or "" for m in masses])
    building_height = np.array([m.height_m for m in masses])
    small = (shapely.area(geom) <= 240) & (building_height <= 17)
    house = np.isin(use, ["house", "detached"]) & small
    commercial = np.isin(use, ["commercial", "retail", "office"]) & (building_height <= 22)
    xyz = np.column_stack([centers, np.array([m.base_m for m in masses]) + building_height / 2])
    slopes = np.column_stack([sample(terrain, queries + offset) for offset in
                              ((-75, 0), (75, 0), (0, -75), (0, 75))])
    scores = []
    views = []
    for point, change in zip(queries, np.ptp(slopes, axis=1)):
        target = list(geographic.transform(*point))
        view = {"id": "A2", "name": "Mixed foothill types", "target_lon_lat": target, "bearing_deg": 123,
                "depth_anchors_m": [-460, 3250],
                "mapping": {"p3_width_scale_m": 820, "p3_relief_fraction_per_km": 1.55,
                            "p3_bottom_fraction": .92, "p3_depth_rise_fraction": 1.20}}
        mapping = create_mapping(view, local, sample(terrain, point[None, :])[0], scene, spring)
        projected, _, fraction, _ = mapping.project(xyz, "P3", *px)
        # Give the center-screen foreground priority before raster occlusion is tested.
        in_frame = ((projected >= np.asarray(px) * .075) & (projected <= np.asarray(px) * .925)).all(axis=1)
        front = in_frame & (fraction >= 0) & (fraction < .43)
        apt = np.count_nonzero(front & (use == "apartments"))
        low = np.count_nonzero(front & small)
        known = np.count_nonzero(front & house)
        shops = np.count_nonzero(front & commercial)
        score = (min(apt, 5) * 3 + min(low, 12) + min(known, 5) * 10
                 + min(shops, 5) * 3 + min(float(change), 22) * .65)
        scores.append((score, int(apt), int(low), int(known), int(shops), float(change)))
        views.append(view)
    chosen = max(range(len(scores)), key=lambda i: scores[i][0])
    _, apt, low, known, shops, slope = scores[chosen]
    return views[chosen], {
        "window_wsen": box, "grid_points_compared": len(queries),
        "native_apartments_before_occlusion": apt,
        "small_plan_low_height_candidates_before_occlusion": low,
        "native_house_detached_before_occlusion": known,
        "native_commercial_retail_office_le22m_before_occlusion": shops,
        "dtm_relief_across_150m_m": slope,
    }


def measures(modeled, ownership, rows, px, mm, cutoffs, evidence):
    width, height = px
    sx, sy = mm[0] / width, mm[1] / height
    by_id = {p.mass.id: i for i, p in enumerate(modeled)}
    data = []
    for row in rows:
        i = by_id[row["id"]]
        item = modeled[i]
        entry = evidence[row["id"]]
        tile = object_tile(item, width, height)
        if tile is None:
            continue
        window, (tone, _, _, _) = tile
        mask = ownership[window] == i
        y, x = np.where(mask)
        # Work 01 surfaces have roof .92, underside .55 and walls in [.62,.81].
        facade = mask & (tone >= .61) & (tone <= .82)
        fy, fx = np.where(facade)
        visible_width = (np.ptp(x) + 1) * sx if len(x) else 0.0
        visible_height = (np.ptp(y) + 1) * sy if len(y) else 0.0
        facade_width = (np.ptp(fx) + 1) * sx if len(fx) else 0.0
        facade_height = (np.ptp(fy) + 1) * sy if len(fy) else 0.0
        level = "below_silhouette"
        for name, (w, h) in cutoffs.items():
            dims = ((facade_width, facade_height) if name == "surface_stroke_candidate" else
                    (visible_width, visible_height))
            if dims[0] >= w and dims[1] >= h:
                level = name
        isolated = row["isolated_px"]
        data.append({
            **row, "study_family": entry["study_family"], "official_use": entry["official_use"],
            "model_height_m": item.mass.height_m,
            "visible_width_mm": float(visible_width), "visible_height_mm": float(visible_height),
            "visible_area_mm2": int(mask.sum()) * sx * sy,
            "visible_facade_area_mm2": int(facade.sum()) * sx * sy,
            "visible_facade_width_mm": float(facade_width), "visible_facade_height_mm": float(facade_height),
            "percent_hidden_by_terrain": 100 * row["terrain_blocked_px"] / max(isolated, 1),
            "percent_hidden_by_buildings": 100 * row["building_blocked_px"] / max(isolated, 1),
            "readability": level,
            "bbox_px_xyxy": [int(x.min() + window[1].start), int(y.min() + window[0].start),
                             int(x.max() + window[1].start + 1), int(y.max() + window[0].start + 1)] if len(x) else None,
        })
    return data


def summarize(rows, land, owner):
    visible = [row for row in rows if row["visible_px"]]
    groups = defaultdict(list)
    for row in visible:
        groups[row["band"]].append(row)
        groups[f"{row['band']}/{row['study_family']}"].append(row)
    return {
        "visible": len(visible),
        "estimated_visible": sum(row["height_kind"].endswith("_floors") for row in visible),
        "official_height_visible": sum(row["height_kind"] == "regional_official_height" for row in visible),
        "all_visible_by_native_class": dict(Counter(row["class"] or "<null>" for row in visible)),
        "visible_by_study_family": dict(Counter(row["study_family"] for row in visible)),
        "urban_owned_frame_fraction": float(np.count_nonzero(owner >= 0) / owner.size),
        "terrain_covered_px": int(((owner >= 0) & (land[2] >= 0)).sum()),
        "unowned_frame_fraction": float(np.count_nonzero(owner < 0) / owner.size),
        "terrain_blocked_px": sum(row["terrain_blocked_px"] for row in rows),
        "building_blocked_px": sum(row["building_blocked_px"] for row in rows),
        "visible_facades": {key: {
            "visible": len(group),
            "readability": dict(Counter(row["readability"] for row in group)),
            **{field: distribution([r[field] for r in group]) for field in
               ("visible_width_mm", "visible_height_mm", "visible_area_mm2", "visible_facade_area_mm2",
                "percent_hidden_by_terrain", "percent_hidden_by_buildings")},
        } for key, group in groups.items()},
    }


def run(args):
    root = Path(__file__).resolve().parents[3]
    config, references = locked_baseline(root, args.extract, args.checkpoint, args.dtm)
    settings = json.loads(args.config.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    bounds, crs = config["overture_bbox_wsen"], config["metric_crs"]
    px, mm = config["screen_px"], config["diagnostic_sheet_mm"]
    source = read_source(args.extract / "building.parquet", bounds, crs)
    source.records = [row for row, ok in zip(source.records, source.eligible) if ok]
    source.footprints = source.footprints[source.eligible]
    registry, regional_shapes, provider, authoritative = [], np.array([], dtype=object), None, False
    if args.regional:
        spec = json.loads(args.provider.read_text())
        registry, regional_shapes, provider = read_regional(args.regional, spec, bounds, crs)
        provider.update(source=spec["source"], license=spec["license"], version=spec["version"],
                        sha256=sha256_file(args.regional), authoritative=spec["authoritative"])
        if spec.get("sha256") and spec["sha256"] != provider["sha256"]:
            raise ValueError("The regional file hash does not match its source manifest.")
        authoritative = spec["authoritative"]
    print(f"Matching {len(source.records):,} Overture footprints with {len(registry):,} regional polygons", flush=True)
    rows, reciprocal = build_evidence(source, registry, regional_shapes, authoritative, settings)
    linked = {row["id"]: row for row in rows}
    pq.write_table(pa.Table.from_pylist(rows), args.output / "building_height_evidence.parquet", compression="zstd")
    official_eligible = any(row["official_height_m"] is not None for row in rows)
    best_overlaps = np.array([row["candidate_overlaps"][0]["iou"] for row in rows
                              if row["candidate_overlaps"]], dtype=float)
    high_overlaps = np.array([row["candidate_overlaps"][0]["iou"] for row in rows
                              if row["match_status"] == "high_confidence"], dtype=float)
    audit = {
        "overture_rows": len(rows), "regional": provider,
        "h1_status": ("available" if official_eligible else "no_accepted_official_height" if authoritative
                      else "official_records_unavailable"),
        "matching_basis": "shape intersection only; source address or parcel identifiers do not occur on both sides",
        "match_counts": dict(Counter(row["match_status"] for row in rows)), **reciprocal,
        "best_candidate_iou": distribution(best_overlaps),
        "high_confidence_iou": distribution(high_overlaps),
        "categories": audit_evidence(rows), "reference_hashes_verified": references,
        "official_use_review": dict(Counter(row["source_use_agreement"] for row in rows
                                            if row["source_use_agreement"])),
        "height_policy": settings["floor_rate_m"], "thresholds": settings["overlap"],
    }
    save_json(args.output / "acquisition_matching_audit.json", audit)
    if registry:
        footprint_examples(source, registry, regional_shapes, rows, authoritative, args.output)
    del regional_shapes, registry
    terrain = register_terrain(args.dtm, config["datascape_roi_wsen"], crs, config["terrain_grid_m"])
    positions = shapely.get_coordinates(shapely.point_on_surface(source.footprints))
    ground_m = sample(terrain, positions)
    native, supported, floor = masses_by_scenario(source, rows, ground_m)
    source_supported = supported if authoritative else native
    diagnostic = source_supported + floor
    scene = json.loads((root / "configs/scenes/seoul_projection_composition_v01.json").read_text())
    spring = json.loads((root / "configs/scenes/seoul_spring_production_v01.json").read_text())
    local = Transformer.from_crs("OGC:CRS84", crs, always_xy=True)
    geographic = Transformer.from_crs(crs, "OGC:CRS84", always_xy=True)
    baseline = next(view for view in config["views"] if view["id"] == "A")
    view_geo = {}
    def view_model(view):
        place = np.asarray([local.transform(*view["target_lon_lat"])])
        mapping = create_mapping(view, local, sample(terrain, place)[0], scene, spring)
        land = terrain_layers(terrain.grid, mapping, *px, stride=1)
        view_geo[view["id"]] = {"config": view, "mapping": mapping.record()}
        return mapping, land
    results = {}
    def render(key, mapping, land, masses):
        selected = [p for p in project_masses(masses, mapping, *px) if p.band != "far"]
        owner, tones, occlusion = composite(selected, land, *px)
        sizes = measures(selected, owner, occlusion, px, mm, settings["readability_mm"], linked)
        stats = summarize(sizes, land, owner)
        raster = scene_image(land, owner, tones, selected)
        official_indexes = [i for i, item in enumerate(selected) if item.mass.height_kind == "regional_official_height"]
        if official_indexes:
            mask = np.isin(owner, official_indexes)
            raster[mask] = np.array([.16, .32, .52]) * tones[mask, None] + .20
        Image.fromarray(np.uint8(np.rint(raster * 255))).save(args.output / f"{key}.png")
        pq.write_table(pa.Table.from_pylist(sizes), args.output / f"{key}_readability.parquet")
        results[key] = {"image": raster, "rows": sizes, "stats": stats}
        print(key, stats["visible"], "visible", flush=True)
    mapping, land = view_model(baseline)
    render("A0_H0", mapping, land, native)
    if official_eligible:
        render("A0_H1", mapping, land, supported)
    render("A0_H2", mapping, land, diagnostic)
    reference_counts = {"near": 111, "middle": 299}
    for band, count in reference_counts.items():
        if results["A0_H0"]["stats"]["visible_facades"][band]["visible"] != count:
            raise RuntimeError("A0 native-height count changed from Work 01.")
    ref_visibility = pq.read_table(args.checkpoint / "view_A_visibility.parquet").to_pylist()
    cols = ("id", "band", "visible_px", "isolated_px", "terrain_blocked_px", "building_blocked_px")
    signature = lambda records: sorted(tuple(row[key] for key in cols) for row in records)
    if signature(ref_visibility) != signature(results["A0_H0"]["rows"]):
        raise RuntimeError("A0 native-height visibility changed from Work 01.")
    for width in settings["view_a1_width_m"]:
        reference = {**baseline, "p3_depth_rise_fraction": mapping.base.p3_depth_rise_fraction}
        view = crop_view(reference, width, settings["view_a1_center_y_fraction"])
        render(view["id"], *view_model(view), diagnostic)
    a2, selection = choose_near_site(diagnostic, terrain, local, geographic,
                                     settings["view_a2_search_wsen"], scene, spring, px)
    render("A2", *view_model(a2), diagnostic)
    save_json(args.output / "composition_audit.json", {
        "locked_A0_exact_per_object_occlusion": True, "a2_selection": selection, "views": view_geo,
        "screen_px": px, "artwork_mm": mm, "readability_thresholds_mm": settings["readability_mm"],
        "scenes": {key: value["stats"] for key, value in results.items()},
    })
    charts(results, audit["h1_status"], args.output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--extract", required=True, type=Path)
    p.add_argument("--checkpoint", required=True, type=Path)
    p.add_argument("--dtm", required=True, type=Path, nargs="+")
    p.add_argument("--regional", type=Path)
    p.add_argument("--provider", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if bool(args.regional) != bool(args.provider):
        p.error("Provide both the regional file and its provider configuration.")
    run(args)


if __name__ == "__main__":
    main()
