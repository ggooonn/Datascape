"""Extract complete Overture records for a pinned release and geographic window."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.request import urlopen

import duckdb
import pyarrow.parquet as pq


def intersecting_shards(index, kind, bounds):
    west, south, east, north = bounds
    return sorted(
        row["assets"]["aws"]["href"]
        for row in index
        if row["collection"] == kind
        and row["bbox"]["xmin"] <= east
        and row["bbox"]["xmax"] >= west
        and row["bbox"]["ymin"] <= north
        and row["bbox"]["ymax"] >= south
    )


def acquire(config, output):
    bounds = config["overture_bbox_wsen"]
    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Use a non-wrapping WGS84 bounding box in W,S,E,N order.")
    release = config["overture_release"]
    index_url = f"https://stac.overturemaps.org/{release}/collections.parquet"
    with urlopen(index_url, timeout=60) as response:
        index_bytes = response.read()
    index = pq.read_table(BytesIO(index_bytes)).to_pylist()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "release": release, "bounds_wsen": bounds, "source_crs": "OGC:CRS84",
        "index": index_url, "index_sha256": sha256(index_bytes).hexdigest(),
        "selection": "Inclusive bbox intersection. Audit further intersects source polygons.",
        "collections": {},
    }
    with duckdb.connect(config={"threads": 4}) as db:
        db.execute("INSTALL httpfs; LOAD httpfs")
        # Read geometry bytes without GeoParquet-to-DuckDB geometry conversion.
        db.execute("SET enable_geoparquet_conversion = false")
        for kind in ("building", "building_part"):
            urls = intersecting_shards(index, kind, bounds)
            if not urls:
                raise ValueError(f"STAC selected no shards for {kind}.")
            query = db.execute(
                """
                SELECT * FROM read_parquet(?)
                WHERE bbox.xmin <= ? AND bbox.xmax >= ?
                  AND bbox.ymin <= ? AND bbox.ymax >= ?
                ORDER BY id
                """,
                [urls, east, west, north, south],
            )
            table = query.to_arrow_table()
            path = output / f"{kind}.parquet"
            pq.write_table(table, path.with_suffix(".tmp"))
            path.with_suffix(".tmp").replace(path)
            manifest["collections"][kind] = {
                "shards": urls, "rows": table.num_rows, "schema": str(table.schema),
                "extract_sha256": sha256(path.read_bytes()).hexdigest(),
            }
    (output / "acquisition.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    acquire(json.loads(args.config.read_text()), args.output)


if __name__ == "__main__":
    main()
