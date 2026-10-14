"""Reproducible B-V3 projection study; no brush paths or machine commands."""
import argparse
import json
import os
import platform
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from PIL import Image

from datascape.data.quality import sha256_file
from datascape.projection.camera import Camera
from datascape.projection.composition import Composition, insert_panel_gap
from datascape.rendering.terrain_preview import mesh
from datascape.terrain.candidates import load_grid


def rasterize(pixel, depth, fractions, faces, tones, width, height):
    """Rasterize mapped triangles with P0 reciprocal-depth overlap ordering.

    Source depth fraction is interpolated with the same reciprocal-depth
    weights. This is a diagnostic compositor for P1-P3, not ray tracing.
    """
    inverse = np.zeros((height, width))
    image = np.ones((height, width), dtype=np.float32)
    visible_depth = np.full((height, width), np.nan, dtype=np.float32)
    owners = np.full((height, width), -1, dtype=np.int32)
    for face_id, (face, tone) in enumerate(zip(faces, tones)):
        p, z = pixel[face], depth[face]
        if not np.isfinite(p).all() or (z <= 1).any():
            continue
        xmin = max(0, int(np.floor(p[:, 0].min())))
        xmax = min(width - 1, int(np.ceil(p[:, 0].max())))
        ymin = max(0, int(np.floor(p[:, 1].min())))
        ymax = min(height - 1, int(np.ceil(p[:, 1].max())))
        if xmax < xmin or ymax < ymin:
            continue
        xx, yy = np.meshgrid(np.arange(xmin, xmax + 1) + .5,
                             np.arange(ymin, ymax + 1) + .5)
        edge1, edge2 = p[1] - p[0], p[2] - p[0]
        denom = edge1[0] * edge2[1] - edge1[1] * edge2[0]
        if abs(denom) < 1e-9:
            continue
        b1 = ((xx - p[0, 0]) * (p[2, 1] - p[0, 1]) - (yy - p[0, 1]) * (p[2, 0] - p[0, 0])) / denom
        b2 = ((p[1, 0] - p[0, 0]) * (yy - p[0, 1]) - (p[1, 1] - p[0, 1]) * (xx - p[0, 0])) / denom
        b0 = 1 - b1 - b2
        iz = b0 / z[0] + b1 / z[1] + b2 / z[2]
        region = inverse[ymin:ymax + 1, xmin:xmax + 1]
        wins = (b0 >= -1e-8) & (b1 >= -1e-8) & (b2 >= -1e-8) & (iz > region)
        region[wins] = iz[wins]
        image[ymin:ymax + 1, xmin:xmax + 1][wins] = tone
        dd = (b0 * fractions[face[0]] / z[0] + b1 * fractions[face[1]] / z[1] + b2 * fractions[face[2]] / z[2]) / np.maximum(iz, 1e-12)
        visible_depth[ymin:ymax + 1, xmin:xmax + 1][wins] = dd[wins]
        owners[ymin:ymax + 1, xmin:xmax + 1][wins] = face_id
    return image, visible_depth, owners


def render(grid, composition, method, width, height, stride=2):
    xyz, faces, _ = mesh(grid, stride)
    pixel, depth, fraction = composition.project(xyz, method, width, height)
    triangles = xyz[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals[normals[:, 2] < 0] *= -1
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
    light = np.array([-.5, .5, np.sqrt(.5)])
    # The SAME raw-world face tones are used for every projection.
    tones = np.clip(.16 + .58 * np.maximum(normals @ light, 0) + .14 * fraction[faces].mean(axis=1), .12, .90)
    shade, visible, owners = rasterize(pixel, depth, fraction, faces, tones, width, height)
    occupied = owners >= 0
    bands = np.minimum((np.nan_to_num(visible, nan=0) * 3).astype(int), 2)
    diagnostic = np.where(occupied, np.array([.18, .48, .78])[bands], 1)
    silhouette = np.where(occupied, .14, 1).astype(np.float32)
    # Hatch the finite ROI's missing ground; it is not pictorial mist or sky.
    yy, xx = np.mgrid[:height, :width]
    bottom = np.max(np.where(occupied, yy, -1), axis=0)
    outside = (yy > bottom) & (bottom >= 0)
    hatch = np.where((xx + yy) % 14 < 2, .86, .97)
    for image in (shade, diagnostic, silhouette):
        image[outside] = hatch[outside]
    band_metrics = []
    for index, label in enumerate(("foreground", "middle_ground", "background")):
        mask = occupied & (bands == index)
        band_metrics.append({"label": label, "frame_fraction": float(mask.mean()),
                             "visible_terrain_fraction": float(mask.sum() / max(1, occupied.sum())),
                             "centroid_y_fraction": float(yy[mask].mean() / height) if mask.any() else None})
    # Orientation changes also occur at ordinary silhouettes. Report differences
    # from P0 rather than claiming every sign change is a projection defect.
    base, _, _ = composition.project(xyz, "P0", width, height)
    def signed_area(points):
        t = points[faces]
        a, b = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        return a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    area, base_area = signed_area(pixel), signed_area(base)
    sign_changed = area * base_area < 0
    vertex_inside = (pixel[:, 0] >= 0) & (pixel[:, 0] < width) & (pixel[:, 1] >= 0) & (pixel[:, 1] < height)
    return {"shade": shade, "depth": diagnostic, "silhouette": silhouette,
            "metrics": {"bands": band_metrics, "terrain_frame_fraction": float(occupied.mean()),
                        "white_above_or_beside_roi_fraction": float((~occupied & ~outside).mean()),
                        "missing_ground_frame_fraction": float(outside.mean()),
                        "vertices_in_frame_fraction": float(vertex_inside.mean()),
                        "near_plane_discarded_triangles": int((depth[faces] <= 1).any(axis=1).sum()),
                        "orientation_changed_vs_P0_fraction": float(sign_changed.mean()),
                        "orientation_changed_visible_triangle_fraction": float(sign_changed[np.unique(owners[occupied])].mean()) if occupied.any() else 0,
                        "mesh_stride": stride, "mesh_spacing_m": stride * grid.native_resolution_m[0]}}


def save_figure(fig, path):
    """Atomically publish a fully decoded PNG."""
    path = Path(path)
    temp = path.with_suffix(".writing.png")
    fig.savefig(temp, dpi=150, bbox_inches="tight", facecolor="#f7f6f2")
    plt.close(fig)
    with Image.open(temp) as check:
        check.load()
    with temp.open("rb") as stream:
        os.fsync(stream.fileno())
    temp.replace(path)


def save_array(image, path):
    path = Path(path)
    temp = path.with_suffix(".writing.png")
    Image.fromarray(np.round(np.clip(image, 0, 1) * 255).astype(np.uint8)).save(temp)
    with Image.open(temp) as check:
        check.load()
    temp.replace(path)


def run(master_path, config_path, output):
    """Generate comparisons and a complete source/configuration record."""
    config = json.loads(Path(config_path).read_text())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    input_hash_before = sha256_file(master_path)
    with rasterio.open(master_path) as ds:
        if str(ds.crs) != "EPSG:32652" or tuple(ds.res) != (30.0, 30.0):
            raise ValueError("This pinned scene requires the validated EPSG:32652 30 m MASTER.")
        grid = load_grid(ds, config["roi_bounds_m"])
        description = ds.descriptions[0]
        if description not in (None, "DEM"):
            raise ValueError("Expected DEM as MASTER band 1.")
    raw_before = grid.elevation_m.copy()
    camera = Camera(**config["camera"])
    xyz, _, _ = mesh(grid, 1)
    bearing = np.deg2rad(camera.azimuth_deg)
    distances = (xyz[:, :2] - config["target_raw_xyz_m"][:2]) @ np.array([np.sin(bearing), np.cos(bearing)])
    mapping = Composition(camera, tuple(config["target_raw_xyz_m"]),
                          (float(distances.min()), float(distances.max())), **config["mapping"])
    width, height = config["raster_pixels"]
    if width % 2 or width / height != 600 / 900:
        raise ValueError("Use an even raster width with the 600:900 continuous-pair ratio.")
    if config["painted_panel_mm"] != [300, 900] or config["panel_count"] != 2 or config["physical_gap_mm"] != 40:
        raise ValueError("This benchmark is fixed to two 300 x 900 mm panels with a 40 mm gap.")
    results = {method: render(grid, mapping, method, width, height, config["mesh_stride"]) for method in ("P0", "P1", "P2", "P3")}
    for method, result in results.items():
        save_array(result["shade"], output / f"{method}_continuous.png")
    titles = ("P0 | Perspective", "P1 | Relief + mild warp", "P2 | Blended multi-view", "P3 | Upward depth unfolding")
    for name, key in (("projection_comparison.png", "shade"), ("depth_comparison.png", "depth"), ("silhouette_comparison.png", "silhouette")):
        fig, axes = plt.subplots(1, 4, figsize=(14, 6.9))
        for ax, (method, result), title in zip(axes, results.items(), titles):
            ax.imshow(result[key], cmap="gray", vmin=0, vmax=1, extent=(0, 600, 900, 0))
            ax.set_title(title, fontsize=12)
            ax.axvline(300, color=".5", ls=":", lw=.6)
            ax.set_xticks([0, 300, 600]); ax.set_yticks([0, 300, 600, 900])
            ax.set_xlabel("Continuous painted width (mm)")
        axes[0].set_ylabel("Painted height (mm)")
        subtitle = "600 x 900 mm content | dotted line = panel split | hatch = ground outside finite ROI"
        if key == "depth":
            subtitle += "\nNear = dark / middle = gray / far = light; equal source-depth thirds"
        fig.suptitle("B-V3 adjusted | Spring pair | Projection study v0.1", fontsize=17, fontweight="bold")
        fig.text(.5, .025, subtitle, ha="center", fontsize=10)
        fig.subplots_adjust(bottom=.12, top=.89, wspace=.2)
        save_figure(fig, output / name)
    gap = round(width * config["physical_gap_mm"] / (2 * config["painted_panel_mm"][0]))
    fig, axes = plt.subplots(1, 4, figsize=(14, 7))
    for ax, (method, result), title in zip(axes, results.items(), titles):
        ax.imshow(insert_panel_gap(result["shade"], gap), cmap="gray", vmin=0, vmax=1, extent=(0, 640, 900, 0))
        ax.set_title(title, fontsize=12); ax.set_axis_off()
    fig.suptitle("Physical pair | 300 + 40 gap + 300 mm", fontsize=17, fontweight="bold")
    fig.text(.5, .03, "The gap is inserted after painting; every content pixel is preserved. Fold angles are not simulated.", ha="center", fontsize=10)
    save_figure(fig, output / "physical_pair.png")
    # This is only a sequencing scaffold, not eight independently developed panels.
    fig, axes = plt.subplots(1, 4, figsize=(14, 5))
    for ax, label in zip(axes, ("SPRING | study", "SUMMER | open", "AUTUMN | open", "WINTER | open")):
        if label.startswith("SPRING"):
            ax.imshow(insert_panel_gap(results["P2"]["shade"], gap), cmap="gray", vmin=0, vmax=1, extent=(0, 640, 900, 0))
        else:
            ax.set_facecolor("#efeeea")
            ax.text(320, 450, "Composition\nto be selected", ha="center", va="center", color=".5")
            ax.axvline(300, color="white", lw=10)
        ax.set_xlim(0, 640);ax.set_ylim(900, 0);ax.set_aspect("equal")
        ax.set_title(label, fontsize=11);ax.set_xticks([]);ax.set_yticks([])
    fig.suptitle("8-panel sequencing scaffold | 2400 mm content / 2680 mm nominal spread", fontsize=16, fontweight="bold")
    fig.text(.5, .02, "Only spring is studied. Carry the terrain exit height and empty-space rhythm into later pairs; no seasonal image is implied.", ha="center", fontsize=10)
    save_figure(fig, output / "sequence_scaffold.png")
    native = {method: render(grid, mapping, method, width, height, 1) for method in ("P2", "P3")}
    fig, axes = plt.subplots(2, 2, figsize=(8, 10))
    native_metrics = {}
    for row, method in enumerate(("P2", "P3")):
        for col, (result, label) in enumerate(((results[method], "60 m sampled"), (native[method], "30 m native"))):
            axes[row, col].imshow(result["shade"], cmap="gray", vmin=0, vmax=1)
            axes[row, col].set_title(f"{method} | {label}");axes[row, col].set_axis_off()
        native_metrics[method] = native[method]["metrics"]
    fig.suptitle("Sampling sensitivity | same projection and framing", fontsize=15, fontweight="bold")
    save_figure(fig, output / "native_sampling.png")
    if not np.array_equal(raw_before, grid.elevation_m, equal_nan=True):
        raise AssertionError("Source elevations changed.")
    input_hash_after = sha256_file(master_path)
    if input_hash_after != input_hash_before:
        raise AssertionError("Input GeoTIFF changed during the study.")
    record = {"study": config["study"], "base_main": config["base_main"],
              "input": {"filename": Path(master_path).name, "sha256": sha256_file(master_path),
                        "crs": "EPSG:32652", "dem_band": 1, "native_resolution_m": list(grid.native_resolution_m)},
              "configuration": config, "projection": mapping.record(),
              "roi_raw_dem_range_m": [float(np.nanmin(raw_before)), float(np.nanmax(raw_before))],
              "raw_dem_preserved": True, "input_hash_unchanged": True,
              "roi_bounds_m": list(grid.bounds_m), "roi_valid_fraction": float(grid.valid.mean()),
              "random_seed": None, "randomness": "None; deterministic geometry",
              "shading": "Raw-world normals, fixed NW light at 45 degrees, same depth tone in all methods; no cast shadows",
              "results": {key: value["metrics"] for key, value in results.items()},
              "native_sampling_results": native_metrics,
              "versions": {"python": platform.python_version(), "numpy": np.__version__, "rasterio": rasterio.__version__, "matplotlib": matplotlib.__version__}}
    (output / "study.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.master, args.config, args.output)


if __name__ == "__main__":
    main()
