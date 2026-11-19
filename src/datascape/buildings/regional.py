"""Pair optional regional evidence to Overture by polygon overlap."""

from collections import Counter
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from pyproj import Transformer
import shapely
from shapely.strtree import STRtree


def source_id(value):
    """Text is preserved verbatim; integers remain exact, floats are rejected."""
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise ValueError(f"Regional ID must be a nonempty string or exact integer: {value!r}")


def numeric(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def floor_count(value):
    number = numeric(value)
    return int(number) if number is not None and number.is_integer() else None


def korean_family(code, name):
    """Grouping for this study while retaining unmodified Korean use fields."""
    label = str(name or "")
    prefix = str(code or "")[:2]
    if "아파트" in label:
        return "apartment"
    if prefix == "01" or label in {"단독주택", "다가구주택", "다중주택"}:
        return "small_residential"
    if prefix == "02" or "공동주택" in label or label in {"다세대주택", "연립주택"}:
        return "other_residential"
    if prefix in {"03", "04"} or "근린생활시설" in label:
        return "neighborhood_facility"
    if prefix == "07" or "판매시설" in label:
        return "retail_facility"
    return "other" if code or name else None


def read_regional(path, spec, bounds, metric_crs):
    """Read a configured local vector. Registration and API keys are external."""
    columns = spec["fields"]
    field_names = sorted(set(columns.values()))
    if path.suffix == ".parquet":
        table = pq.read_table(path, columns=[*field_names, "geometry"])
        source_crs = spec["crs"]
        total = table.num_rows
        provider_fields = pq.read_schema(path).names
    else:
        import pyogrio

        options = {key: spec[key] for key in ("layer", "encoding") if spec.get(key)}
        info = pyogrio.read_info(path, **options)
        source_crs, total = info["crs"], info["features"]
        provider_fields = info["fields"].tolist()
        if not source_crs:
            raise ValueError("The regional vector must declare its source CRS.")
        # Bound the read without altering any returned source feature.
        source_bounds = Transformer.from_crs("OGC:CRS84", source_crs, always_xy=True).transform_bounds(*bounds)
        use_fid = info["fid_column"] in field_names
        user_columns = [name for name in field_names if name != info["fid_column"]]
        metadata, table = pyogrio.read_arrow(path, columns=user_columns, bbox=source_bounds,
                                             return_fids=use_fid, **options)
        geometry_name = metadata.get("geometry_name") or "wkb_geometry"
        table = table.rename_columns(["geometry" if name == geometry_name else name for name in table.column_names])
    missing = set(field_names) - set(table.column_names)
    if missing:
        raise ValueError(f"Configured fields are missing: {', '.join(sorted(missing))}")
    rows = table.to_pylist()
    original = shapely.from_wkb([row["geometry"] for row in rows], on_invalid="ignore")
    valid = shapely.is_valid(original) & np.isin(shapely.get_type_id(original), [3, 6])
    valid &= ~shapely.is_empty(original)
    search = Transformer.from_crs("OGC:CRS84", source_crs, always_xy=True)
    target = shapely.segmentize(shapely.box(*bounds), .004)
    target = shapely.transform(target, search.transform, interleaved=False)
    keep = valid & shapely.intersects(original, target)
    transform = Transformer.from_crs(source_crs, metric_crs, always_xy=True)
    local = shapely.transform(original[keep], transform.transform, interleaved=False)
    records = []
    for i in np.flatnonzero(keep):
        row = rows[i]
        mapped = {key: row[column] for key, column in columns.items()}
        mapped["id"] = source_id(mapped["id"])
        if "parcel_id" in mapped and mapped["parcel_id"] not in (None, ""):
            mapped["parcel_id"] = source_id(mapped["parcel_id"])
        records.append(mapped)
    order = sorted(range(len(records)), key=lambda i: records[i]["id"])
    return [records[i] for i in order], local[order], {
        "filename": Path(path).name, "source_crs": source_crs, "source_total_rows": total,
        "read_rows": len(rows), "invalid_nonpolygon_rows_read": int((~valid).sum()),
        "intersecting_valid_rows": len(records), "used_fields": field_names,
        "provider_attribute_fields": provider_fields,
    }


def match_polygons(footprints, regional, config):
    """Accept reciprocal, isolated, strong shape overlap. Retain all candidates."""
    n = len(footprints)
    findings = [{"status": "unmatched", "region_index": None, "candidates": []} for _ in range(n)]
    if not n or not len(regional):
        return findings
    regional = np.asarray(regional, dtype=object)
    footprints = np.asarray(footprints, dtype=object)
    left, right = STRtree(regional).query(footprints, predicate="intersects")
    a = shapely.area(footprints[left])
    b = shapely.area(regional[right])
    common = shapely.area(shapely.intersection(footprints[left], regional[right]))
    eligible = (common >= config["minimum_overlap_m2"]) & (common / np.minimum(a, b) >= config["min_smaller_share"])
    reciprocal = [[] for _ in regional]
    for i in np.flatnonzero(eligible):
        p, q = int(left[i]), int(right[i])
        evidence = {
            "region_index": q, "iou": float(common[i] / (a[i] + b[i] - common[i])),
            "overture_share": float(common[i] / a[i]), "regional_share": float(common[i] / b[i]),
            "intersection_m2": float(common[i]),
        }
        findings[p]["candidates"].append(evidence)
        reciprocal[q].append((p, evidence))
    for p, finding in enumerate(findings):
        candidates = finding["candidates"]
        if not candidates:
            continue
        candidates.sort(key=lambda item: (-item["iou"], item["region_index"]))
        top = candidates[0]
        q = top["region_index"]
        competing_left = [e for e in candidates[1:] if e["overture_share"] >= config["split_share"]]
        competing_right = [e for index, e in reciprocal[q]
                           if index != p and e["regional_share"] >= config["split_share"]]
        rival = max((e["iou"] for i, e in reciprocal[q] if i != p), default=0)
        left_gap = top["iou"] - (candidates[1]["iou"] if len(candidates) > 1 else 0)
        if competing_left or competing_right:
            finding["status"] = ("many_to_many" if competing_left and competing_right else
                                 "one_to_many" if competing_left else "many_to_one")
        elif (top["iou"] >= config["min_iou"]
              and min(top["overture_share"], top["regional_share"]) >= config["min_reciprocal_share"]
              and min(left_gap, top["iou"] - rival) >= config["min_iou_gap"]):
            finding.update(status="high_confidence", region_index=q)
        else:
            finding["status"] = "ambiguous"
    return findings


def choose_height(row, regional, authoritative, rates):
    """Keep both sources and choose an H1/H2 value using explicit evidence."""
    native_height = numeric(row.get("height"))
    native_floors = floor_count(row.get("num_floors"))
    official_height = numeric(regional.get("height_m")) if authoritative else None
    official_floors = floor_count(regional.get("floors")) if authoritative else None
    foreign = row.get("class")
    region_family = korean_family(regional.get("use_code"), regional.get("use_name")) if authoritative else None
    key = region_family or ("apartment" if foreign == "apartments" else
                            "small_residential" if foreign in {"house", "detached"} else
                            "retail_facility" if foreign == "retail" else
                            "commercial" if row.get("subtype") == "commercial" else
                            "other_residential" if row.get("subtype") == "residential" else "other")
    floors = official_floors or native_floors
    conflict = bool(native_height and official_height and
                    abs(native_height - official_height) > max(3, .20 * native_height))
    prefer_official = official_height is not None and not (conflict and native_height)
    h1 = official_height if prefer_official else native_height
    blocked = bool(row.get("is_underground") or
                   (row.get("min_floor") and row.get("min_height") is None))
    estimated = h1 is None and floors is not None and not row.get("min_height") and not blocked
    rate = rates.get(key, rates["other"])
    return {
        "native_height_m": native_height, "native_floors": native_floors,
        "official_height_m": official_height, "official_floors": official_floors,
        "height_conflict": conflict,
        "floor_conflict": bool(native_floors and official_floors and official_floors != native_floors),
        "regional_family": region_family, "study_family": key,
        "h0_m": None if blocked else native_height,
        "h1_m": None if blocked else h1,
        "h1_source": None if h1 is None or blocked else ("regional_official" if prefer_official else "overture"),
        "h2_m": floors * rate[1] if estimated else None,
        "h2_range_m": [floors * rate[0], floors * rate[2]] if estimated else None,
        "h2_floor_source": ("regional_official_floors" if official_floors else "overture_floors") if estimated else None,
        "missing_or_ambiguous_height": blocked or (h1 is None and not estimated),
    }


def audit_evidence(records):
    counts = {}
    for row in records:
        group = row["native_class"] or "<null>"
        subset = counts.setdefault(group, Counter())
        subset.update({
            "rows": 1, "native_height": int(row["h0_m"] is not None),
            "preferred_source_height": int(row["h1_m"] is not None),
            "official_positive_height": int(row["official_height_m"] is not None),
            "height_conflicts": int(row["height_conflict"]),
            "native_floors": int(row["native_floors"] is not None),
            "official_floors": int(row["official_floors"] is not None),
            "estimated_height": int(row["h2_m"] is not None),
            "missing_or_ambiguous_height": int(row["missing_or_ambiguous_height"]),
            "native_use": int(bool(row["native_class"] or row["native_subtype"])),
            "official_use": int(bool(row["official_use"] or row["official_use_code"])),
        })
    return counts
