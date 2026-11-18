"""Geometry quality, native attributes and measurements in the pilot extract."""

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
import pyarrow.parquet as pq
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import box
from shapely.strtree import STRtree


ROOF_FIELDS = ("roof_shape", "roof_height", "roof_direction", "roof_orientation",
               "roof_material", "roof_color")


@dataclass
class Source:
    records: list
    footprints: np.ndarray
    eligible: np.ndarray
    bbox_rows: int


def read_source(path, bounds, metric_crs):
    crs = CRS.from_user_input(metric_crs)
    if not crs.is_projected or any(axis.unit_conversion_factor != 1 for axis in crs.axis_info):
        raise ValueError("Use a projected CRS with metric axes.")
    local = Transformer.from_crs("OGC:CRS84", crs, always_xy=True)
    records = pq.read_table(path).to_pylist()
    geographic = shapely.from_wkb([row["geometry"] for row in records], on_invalid="ignore")
    valid = shapely.is_valid(geographic) & np.isin(shapely.get_type_id(geographic), [3, 6])
    valid &= ~shapely.is_empty(geographic)
    # Invalid bbox hits stay in the audit as spatially unresolved.
    keep = ~valid
    keep[valid] = shapely.intersects(geographic[valid], box(*bounds))
    metric = shapely.transform(geographic[keep], local.transform, interleaved=False)
    eligible = valid[keep] & shapely.is_valid(metric) & (shapely.area(metric) > 0)
    return Source([row for row, include in zip(records, keep) if include], metric, eligible, len(records))


def positive(value):
    return value is not None and np.isfinite(value) and value > 0


def morphology(footprints):
    area = shapely.area(footprints)
    perimeter = shapely.length(footprints)
    rects = shapely.get_coordinates(shapely.minimum_rotated_rectangle(footprints)).reshape(-1, 5, 2)
    edges = np.diff(rects, axis=1)
    lengths = np.linalg.norm(edges, axis=2)
    longest = edges[np.arange(len(edges)), lengths.argmax(axis=1)]
    return {
        "footprint_area_m2": area,
        "compactness_4pi_area_over_perimeter2": 4 * np.pi * area / perimeter**2,
        "elongation_min_rectangle": lengths.max(axis=1) / lengths.min(axis=1),
        "long_axis_bearing_deg_mod180": np.degrees(np.arctan2(longest[:, 0], longest[:, 1])) % 180,
    }


def distribution(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return {
        "count": len(values),
        "p05_p50_p95": np.percentile(values, [5, 50, 95]).tolist() if values.size else None,
    }


def overlap_audit(footprints):
    footprints = np.asarray(footprints, dtype=object)
    tree = STRtree(footprints)
    first, second = tree.query(footprints, predicate="intersects")
    keep = first < second
    first, second = first[keep], second[keep]
    a, b = footprints[first], footprints[second]
    shared = shapely.area(shapely.intersection(a, b))
    area_a, area_b = shapely.area(a), shapely.area(b)
    return {
        "positive_area_pairs_gt_0_01_m2": int(np.count_nonzero(shared > .01)),
        "near_duplicate_candidate_pairs_iou_ge_0_90": int(np.count_nonzero(shared / (area_a + area_b - shared) >= .90)),
        "topologically_equal_pairs": int(np.count_nonzero(shapely.equals(a, b))),
    }


def collection_audit(source, detailed=False):
    rows = source.records
    valid_rows = [row for row, valid in zip(rows, source.eligible) if valid]
    fields = ("class", "subtype", "height", "num_floors", "min_height", "min_floor",
              "has_parts", "building_id", "names", "sources", *ROOF_FIELDS)
    schema_fields = set(rows[0]) if rows else set()
    classified = sum(bool(row.get("class") or row.get("subtype")) for row in rows)
    height = [row["height"] for row in rows if positive(row.get("height"))]
    floors = [row["num_floors"] for row in rows if positive(row.get("num_floors"))]
    source_counts = Counter()
    property_counts = Counter()
    evidence_by_class = defaultdict(Counter)
    evidence_by_provider = defaultdict(Counter)
    for row in rows:
        entries = row.get("sources") or []
        providers = {entry["dataset"] for entry in entries if entry.get("dataset")}
        source_counts.update(providers)
        evidence = {
            "records": 1, "positive_height": int(positive(row.get("height"))),
            "positive_floors": int(positive(row.get("num_floors"))),
        }
        evidence_by_class[row.get("class") or "<null>"].update(evidence)
        for provider in providers:
            evidence_by_provider[provider].update(evidence)
        property_counts.update({(s["property"], s["dataset"]) for s in entries
                                if s.get("property") and s.get("dataset")})
    result = {
        "bbox_prefilter_rows": source.bbox_rows,
        "geographic_rows_including_unresolved": len(rows),
        "invalid_or_nonpolygon_bbox_hits_unresolved": len(rows) - len(valid_rows),
        "valid_intersecting_polygon_rows": len(valid_rows),
        "multipolygons": int(np.count_nonzero(shapely.get_type_id(source.footprints[source.eligible]) == 6)),
        "extra_rows_with_repeated_id": len(rows) - len({row["id"] for row in rows}),
        "coverage_non_null": {field: sum(row.get(field) is not None for row in rows)
                              for field in fields if field in schema_fields},
        "any_native_classification": classified,
        "missing_both_classification_fields": len(rows) - classified,
        "any_roof_metadata": sum(any(row.get(field) is not None for field in ROOF_FIELDS) for row in rows),
        "source_dataset_records": dict(source_counts),
        "height_floor_by_source_dataset": {key: dict(value) for key, value in sorted(evidence_by_provider.items())},
        "height_floor_by_native_class": {key: dict(value) for key, value in sorted(evidence_by_class.items())}
        if "class" in schema_fields else None,
        "source_attribute_dataset_records": [
            {"property": prop, "dataset": dataset, "row_count": count}
            for (prop, dataset), count in sorted(property_counts.items())
        ],
        "positive_source_height_m": distribution(height),
        "positive_source_floors": distribution(floors),
        "floor_count_with_no_valid_height": sum(positive(row.get("num_floors")) and
                                               not positive(row.get("height")) for row in rows),
    }
    for field in ("class", "subtype", "roof_shape"):
        if field in schema_fields:
            result[field] = dict(Counter(row[field] for row in rows if row[field] is not None))
    if detailed:
        footprints = source.footprints[source.eligible]
        result["geometry_overlap"] = overlap_audit(footprints)
        result["morphology"] = {key: distribution(values) for key, values in morphology(footprints).items()}
    return result


def part_audit(buildings, parts):
    parents = {row["id"]: footprint for i, (row, footprint) in
               enumerate(zip(buildings.records, buildings.footprints)) if buildings.eligible[i]}
    groups = defaultdict(list)
    for row, geom, ok in zip(parts.records, parts.footprints, parts.eligible):
        if ok and row["building_id"] in parents:
            groups[row["building_id"]].append((row, geom))
    intersections = 0
    vertical_pairs = 0
    outside = 0
    for parent, members in groups.items():
        for i, (row, footprint) in enumerate(members):
            outside += footprint.difference(parents[parent]).area > max(.5, .01 * footprint.area)
            for other, other_geom in members[:i]:
                if footprint.intersection(other_geom).area <= .01:
                    continue
                intersections += 1
                if positive(row["height"]) and positive(other["height"]):
                    bottom, other_bottom = row["min_height"] or 0, other["min_height"] or 0
                    vertical_pairs += min(bottom + row["height"], other_bottom + other["height"]) > max(bottom, other_bottom)
    expected = {row["id"] for row in buildings.records if row.get("has_parts") is True}
    return {
        "parents_source_has_parts": len(expected),
        "parents_with_matched_part": len(groups),
        "has_parts_without_matched_part": len(expected - groups.keys()),
        "part_rows_with_parent_unresolved_in_extract": sum(row["building_id"] not in parents for row in parts.records),
        "valid_linked_part_rows": sum(map(len, groups.values())),
        "parts_outside_parent_more_than_0_5m2_and_1pct": outside,
        "same_parent_parts_positive_plan_overlap_pairs": intersections,
        "same_parent_parts_overlap_with_positive_vertical_interval_pairs": vertical_pairs,
    }
