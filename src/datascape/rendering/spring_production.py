"""Native-DEM foreground extension and mapped-space checks for two panels."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import numpy as np
import rasterio

from datascape.data.quality import read_valid_band, sha256_file
from datascape.projection.camera import Camera
from datascape.projection.composition import Composition, insert_panel_gap
from datascape.projection.production import ProductionMapping, mapping_jacobians
from datascape.rendering.composition_study import render as legacy_render, save_array, save_figure
from datascape.rendering.terrain_preview import mesh
from datascape.terrain.candidates import TerrainGrid, load_grid


def extended_grid(dataset, old_bounds, mapping, minimum_eye_distance_m):
    """Load available east/north source extent, then apply a separate view mask.

    NoData remains invalid. The horizontal eye-distance clip excludes terrain
    behind or too close to the virtual eye, not missing geographic data.
    """
    if minimum_eye_distance_m <= 0:
        raise ValueError("Minimum horizontal eye distance must be positive.")
    bounds = (old_bounds[0], old_bounds[1], dataset.bounds.right, dataset.bounds.top)
    source = load_grid(dataset, bounds)
    xyz = np.column_stack([source.x_m.ravel(), source.y_m.ravel(), source.elevation_m.ravel()])
    d = mapping.source_fraction(xyz).reshape(source.valid.shape)
    lo, hi = mapping.base.depth_extent_m
    eye_distance = mapping.base.camera.distance_m + lo + d * (hi - lo)
    view_valid = source.valid & (eye_distance >= minimum_eye_distance_m)
    view = TerrainGrid(source.elevation_m, view_valid, source.x_m, source.y_m,
                       source.bounds_m, source.native_resolution_m)
    return source, view, {"source_valid_fraction": float(source.valid.mean()),
                          "view_valid_fraction": float(view_valid.mean()),
                          "source_valid_pixels": int(source.valid.sum()),
                          "view_valid_pixels": int(view_valid.sum()),
                          "eye_distance_clip_pixels": int((source.valid & ~view_valid).sum()),
                          "expanded_bounds_m": list(source.bounds_m)}


def rasterize_mapped(pixel, depth, fractions, faces, tones, width, height):
    """Composite the final mapped triangles using affine virtual depth.

    Returns face ownership for subsequent diagnostics. Post-projection XY and
    depth define one common surface; hidden lines must use this same surface.
    """
    nearest = np.full((height, width), np.inf)
    image = np.ones((height, width), dtype=np.float32)
    visible = np.full((height, width), np.nan, dtype=np.float32)
    owner = np.full((height, width), -1, dtype=np.int32)
    p = pixel[faces]
    finite = np.isfinite(p).all(axis=(1, 2)) & np.isfinite(depth[faces]).all(axis=1) & (depth[faces] > 1).all(axis=1)
    safe_p = np.where(np.isfinite(p), p, 0)
    lo = safe_p.min(axis=1)
    hi = safe_p.max(axis=1)
    candidates = np.flatnonzero(finite & (hi[:, 0] >= 0) & (hi[:, 1] >= 0) & (lo[:, 0] < width) & (lo[:, 1] < height))
    for face_id in candidates:
        face = faces[face_id]
        p, z = pixel[face], depth[face]
        xmin = max(0, int(np.floor(p[:, 0].min())))
        xmax = min(width - 1, int(np.ceil(p[:, 0].max())))
        ymin = max(0, int(np.floor(p[:, 1].min())))
        ymax = min(height - 1, int(np.ceil(p[:, 1].max())))
        if xmax < xmin or ymax < ymin:
            continue
        edge1, edge2 = p[1] - p[0], p[2] - p[0]
        area = edge1[0] * edge2[1] - edge1[1] * edge2[0]
        if abs(area) < 1e-9:
            continue
        xx, yy = np.meshgrid(np.arange(xmin, xmax + 1) + .5, np.arange(ymin, ymax + 1) + .5)
        b1 = ((xx - p[0, 0]) * edge2[1] - (yy - p[0, 1]) * edge2[0]) / area
        b2 = (edge1[0] * (yy - p[0, 1]) - edge1[1] * (xx - p[0, 0])) / area
        b0 = 1 - b1 - b2
        display_depth = b0 * z[0] + b1 * z[1] + b2 * z[2]
        region = nearest[ymin:ymax + 1, xmin:xmax + 1]
        wins = (b0 >= -1e-8) & (b1 >= -1e-8) & (b2 >= -1e-8) & (display_depth < region)
        region[wins] = display_depth[wins]
        image[ymin:ymax + 1, xmin:xmax + 1][wins] = tones[face_id]
        dd = b0 * fractions[face[0]] + b1 * fractions[face[1]] + b2 * fractions[face[2]]
        visible[ymin:ymax + 1, xmin:xmax + 1][wins] = dd[wins]
        owner[ymin:ymax + 1, xmin:xmax + 1][wins] = face_id
    return image, visible, owner, nearest


def render_surface(grid, mapping, method, width, height, stride=1, source_visibility=False):
    """Shading and source-depth regions from the final mapped surface."""
    xyz, faces, _ = mesh(grid, stride)
    pixel, mapped_depth, fractions, source_depth = mapping.project(xyz, method, width, height)
    triangles = xyz[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals[normals[:, 2] < 0] *= -1
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
    tones = np.clip(.16 + .58 * np.maximum(normals @ np.array([-.5, .5, np.sqrt(.5)]), 0)
                    + .14 * np.clip(fractions[faces].mean(axis=1), 0, 1), .12, .90)
    depth = source_depth if source_visibility else mapped_depth
    shade, visible, owner, buffer = rasterize_mapped(pixel, depth, fractions, faces, tones, width, height)
    occupied = owner >= 0
    yy, xx = np.mgrid[:height, :width]
    first = np.min(np.where(occupied, yy, height), axis=0)
    missing_ground = (~occupied) & (yy >= first)
    interior_holes = (~occupied) & (yy > first) & (yy < np.max(np.where(occupied, yy, -1), axis=0))
    band = np.clip((np.nan_to_num(visible, nan=0) * 3).astype(int), 0, 2)
    depth_image = np.where(occupied, np.array([.18, .48, .78])[band], 1)
    hatch = np.where((xx + yy) % 14 < 2, .84, .97)
    shade[missing_ground] = hatch[missing_ground]
    depth_image[missing_ground] = hatch[missing_ground]
    metrics = {"mesh_stride": stride, "mesh_spacing_m": stride * grid.native_resolution_m[0],
               "triangles": len(faces), "terrain_frame_fraction": float(occupied.mean()),
               "uncovered_ground_fraction": float(missing_ground.mean()),
               "interior_uncovered_fraction": float(interior_holes.mean()),
               "bottom_edge_coverage_fraction": float(occupied[-1].mean()),
               "bottom_100mm_coverage_fraction": float(occupied[-round(height / 9):].mean()),
               "nonfinite_or_near_triangles": int((~np.isfinite(pixel[faces]).all(axis=(1, 2)) | (mapped_depth[faces] <= 1).any(axis=1)).sum()),
               "depth_bands": []}
    for index, label in enumerate(("foreground", "middle_ground", "background")):
        mask = occupied & (band == index)
        metrics["depth_bands"].append({"label": label,
            "visible_terrain_fraction": float(mask.sum() / max(occupied.sum(), 1)),
            "centroid_y_fraction": float(yy[mask].mean() / height) if mask.any() else None})
    return {"shade": shade, "depth": depth_image, "occupied": occupied, "owners": owner,
            "depth_buffer": buffer, "metrics": metrics, "pixel": pixel, "xyz": xyz, "faces": faces,
            "mapped_depth": mapped_depth, "source_depth": source_depth}


def fold_checks(grid, mapping, method, width, height):
    """Sample every native valid DEM vertex plus five constant-height slices."""
    xyz = np.column_stack([grid.x_m[grid.valid], grid.y_m[grid.valid], grid.elevation_m[grid.valid]])
    volume, _ = mapping_jacobians(mapping, xyz, method, width, height)
    # Perspective and both selected mappings have a positive volume orientation
    # with this east/north/up -> pixel-right/pixel-down/depth convention.
    result = {"finite_difference_step_m": 1.0, "native_vertex_samples": len(xyz),
              "nonfinite_volume_samples": int((~np.isfinite(volume)).sum()),
              "nonpositive_volume_samples": int((volume <= 0).sum()),
              "minimum_volume_determinant_px2_per_m2": float(np.nanmin(volume)),
              "constant_height_checks": []}
    for height_m in (0.0, 200.0, 400.0, 600.0, 850.0):
        flat = xyz[::4].copy()
        flat[:, 2] = height_m
        vol, plane = mapping_jacobians(mapping, flat, method, width, height)
        result["constant_height_checks"].append({"height_m": height_m, "samples": len(flat),
            "nonfinite_samples": int((~np.isfinite(vol) | ~np.isfinite(plane)).sum()),
            "nonpositive_volume_samples": int((vol <= 0).sum()),
            "nonnegative_plane_samples": int((plane >= 0).sum()),
            "minimum_volume_determinant": float(np.nanmin(vol)),
            "maximum_plane_determinant": float(np.nanmax(plane))})
    result["interpretation"] = "Local sampled mapping checks; terrain silhouettes/overlaps are distinct from warp inversions. Not a global injectivity proof."
    # Check the actual triangulated surface as thin 1 m vertical prisms too.
    # Three tetrahedra per triangle detect local mesh-volume inversion that a
    # screen-normal sign alone cannot distinguish from natural occlusion.
    vertices, faces, _ = mesh(grid, 1)
    lower, upper = vertices.copy(), vertices.copy()
    lower[:, 2] -= .5
    upper[:, 2] += .5
    mapped_layers = []
    for layer in (lower, upper):
        pixel, depth, _, _ = mapping.project(layer, method, width, height)
        mapped_layers.append(np.column_stack([pixel, depth]))
    raw_vertices = np.concatenate([lower, upper])
    mapped_vertices = np.concatenate(mapped_layers)
    a, b, c = faces.T
    d, e, f = a + len(vertices), b + len(vertices), c + len(vertices)
    tetrahedra = np.concatenate([np.column_stack([a,b,c,d]), np.column_stack([b,c,d,e]), np.column_stack([c,d,e,f])])
    def determinant(points):
        t = points[tetrahedra]
        return np.linalg.det(np.stack([t[:,1]-t[:,0],t[:,2]-t[:,0],t[:,3]-t[:,0]],axis=2))
    raw_det, mapped_det = determinant(raw_vertices), determinant(mapped_vertices)
    ratio = mapped_det / raw_det
    result["native_triangle_prisms"] = {"vertical_thickness_m":1.0,"tetrahedra":len(tetrahedra),
        "nonfinite_tetrahedra":int((~np.isfinite(ratio)).sum()),
        "nonpositive_orientation_ratio_tetrahedra":int((ratio<=0).sum()),
        "minimum_orientation_ratio":float(np.nanmin(ratio))}
    return result


def scene(source_scene, config):
    base_config = json.loads(Path(source_scene).read_text())
    camera = Camera(**{**base_config["camera"], **config["camera_overrides"]})
    mapping = Composition(camera, tuple(base_config["target_raw_xyz_m"]), tuple(config["source_depth_extent_m"]),
                          **{**base_config["mapping"], **config["mapping_overrides"]})
    return base_config, ProductionMapping(mapping, config["p3_depth_softening"])


def run(master_path, source_scene, config_path, output):
    """Render extended P2/P3 and preserve a complete reproducibility record."""
    config = json.loads(Path(config_path).read_text())
    base_config, mapping = scene(source_scene, config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    before_hash = sha256_file(master_path)
    width, height = config["raster_pixels"]
    if width % 2 or width / height != 2 / 3:
        raise ValueError("Use an even width and the 600:900 painted-content ratio.")
    with rasterio.open(master_path) as ds:
        if str(ds.crs) != "EPSG:32652" or tuple(ds.res) != (30.0, 30.0) or ds.descriptions[0] != "DEM":
            raise ValueError("Use the validated EPSG:32652, 30 m MASTER with DEM in band 1.")
        old_grid = load_grid(ds, base_config["roi_bounds_m"])
        source, grid, extension = extended_grid(ds, base_config["roi_bounds_m"], mapping, config["minimum_horizontal_eye_distance_m"])
        hillshade = read_valid_band(ds, 4).filled(np.nan)
        full_bounds = list(ds.bounds)
    raw_copy = source.elevation_m.copy()
    results = {method: render_surface(grid, mapping, method, width, height, config["mesh_stride"]) for method in ("P2", "P3")}
    previous_mapping = Composition(Camera(**base_config["camera"]),
        tuple(base_config["target_raw_xyz_m"]), tuple(config["source_depth_extent_m"]), **base_config["mapping"])
    old = {method: legacy_render(old_grid, previous_mapping, method, width, height, config["mesh_stride"]) for method in ("P2", "P3")}
    for method, result in results.items():
        save_array(result["shade"], output / f"{method}_continuous.png")
        save_array(result["shade"][:, :width // 2], output / f"{method}_panel_1.png")
        save_array(result["shade"][:, width // 2:], output / f"{method}_panel_2.png")
    fig, axes = plt.subplots(2, 2, figsize=(9, 12))
    for row, method in enumerate(("P2", "P3")):
        for col, (result, label) in enumerate(((old[method], "Previous finite ROI"), (results[method], "Extended native terrain"))):
            ax = axes[row, col]
            ax.imshow(result["shade"], cmap="gray", vmin=0, vmax=1, extent=(0, 600, 900, 0))
            ax.axvline(300, color=".5", ls=":", lw=.6)
            ax.set_title(f"{method} | {label}")
            ax.set_xticks([0, 300, 600]); ax.set_yticks([0, 300, 600, 900])
    fig.suptitle("Spring pair | Native foreground continuation", fontsize=17, fontweight="bold")
    fig.text(.5, .015, "Source DEM unchanged | fixed depth anchors | hatch = uncovered ground", ha="center", fontsize=10)
    save_figure(fig, output / "foreground_before_after.png")
    fig, axes = plt.subplots(1, 4, figsize=(14, 7))
    for ax, (method, key) in zip(axes, (("P2", "shade"), ("P2", "depth"), ("P3", "shade"), ("P3", "depth"))):
        ax.imshow(results[method][key], cmap="gray", vmin=0, vmax=1, extent=(0, 600, 900, 0))
        ax.axvline(300, color=".5", ls=":", lw=.6); ax.set_title(f"{method} | {'shading' if key=='shade' else 'source depth'}")
        ax.set_xticks([0, 300, 600]); ax.set_yticks([0, 300, 600, 900])
    fig.suptitle("Spring production composition | 600 x 900 mm continuous content", fontsize=17, fontweight="bold")
    fig.text(.5, .025, "Dark = foreground / gray = middle / light = background | same native source terrain and lighting", ha="center", fontsize=10)
    save_figure(fig, output / "spring_comparison.png")
    fig, axes = plt.subplots(1, 2, figsize=(8, 7))
    for ax, method in zip(axes, ("P2", "P3")):
        gap = round(width * config["physical_gap_mm"] / 600)
        ax.imshow(insert_panel_gap(results[method]["shade"], gap), cmap="gray", vmin=0, vmax=1, extent=(0, 640, 900, 0))
        ax.set_title(f"{method} | 300 + 40 + 300 mm")
        ax.set_axis_off()
    fig.suptitle("Physical panel pair | no painted content removed", fontsize=16, fontweight="bold")
    save_figure(fig, output / "physical_pair.png")
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.imshow(hillshade, cmap="gray", extent=(full_bounds[0], full_bounds[2], full_bounds[1], full_bounds[3]), vmin=0, vmax=255)
    for bounds, style, label in ((base_config["roi_bounds_m"], "--", "Previous B1 ROI"), (source.bounds_m, "-", "Expanded source bounds")):
        w,s,e,n = bounds
        ax.add_patch(Rectangle((w,s),e-w,n-s,fill=False,edgecolor="black",linestyle=style,linewidth=2,label=label))
    coverage = np.ma.masked_where(~grid.valid, np.ones(grid.valid.shape))
    ax.imshow(coverage, cmap="Greys", vmin=0, vmax=1, alpha=.18, extent=(grid.bounds_m[0],grid.bounds_m[2],grid.bounds_m[1],grid.bounds_m[3]))
    ax.contour(grid.x_m, grid.y_m, grid.valid.astype(float), levels=[.5], colors="black", linewidths=.9)
    eye,_ = mapping.base.camera.frame(mapping.base.target_raw_xyz_m)
    ax.plot(eye[0],eye[1],"kx",ms=10,label="Virtual eye (XY)")
    ax.plot(*mapping.base.target_raw_xyz_m[:2],"ko",ms=5,label="Aim")
    ax.annotate("", xy=mapping.base.target_raw_xyz_m[:2],xytext=eye[:2],arrowprops={"arrowstyle":"->","color":"black"})
    ax.set_xlabel("UTM easting (m)");ax.set_ylabel("UTM northing (m)")
    ax.ticklabel_format(style="plain",useOffset=False)
    handles,labels = ax.get_legend_handles_labels()
    handles.append(Line2D([0],[0],color="black",lw=.9,label="Source-valid + eye-distance mask"))
    ax.legend(handles=handles,loc="lower left",fontsize=9,facecolor="white",framealpha=.95)
    ax.set_title("Original MASTER coverage | source expansion + separate view mask",fontsize=15,fontweight="bold")
    save_figure(fig, output / "source_extension_map.png")
    folds = {method: fold_checks(grid, mapping, method, width, height) for method in results}
    visibility = {}
    for method, result in results.items():
        alternate = render_surface(grid, mapping, method, width, height, config["mesh_stride"], source_visibility=True)
        both = result["occupied"] & alternate["occupied"]
        difference = both & (result["owners"] != alternate["owners"])
        visibility[method] = {"same_screen_geometry": True, "source_depth_vs_mapped_depth_owner_difference_fraction": float(difference.sum()/max(both.sum(),1)),
                              "coverage_difference_pixels": int((result["occupied"] != alternate["occupied"]).sum()),
                              "comparison": "Same final mapped XY and affine interpolation; change only depth scalar. This is not the legacy reciprocal-depth compositor."}
    if not np.array_equal(raw_copy, source.elevation_m, equal_nan=True):
        raise AssertionError("Source terrain changed.")
    if before_hash != sha256_file(master_path):
        raise AssertionError("GeoTIFF changed.")
    record = {"study": config["study"],"base_main":config["base_main"],
              "input":{"filename":Path(master_path).name,"sha256":before_hash,"crs":"EPSG:32652","dem_band":1,"native_resolution_m":[30,30]},
              "config":config,"source_scene":base_config,"mapping":mapping.record(),"extension":extension,
              "raw_dem_preserved":True,"input_hash_unchanged":True,
              "results":{k:v["metrics"] for k,v in results.items()},
              "previous_roi_results":{k:v["metrics"] for k,v in old.items()},
              "mapping_checks":folds,"visibility_checks":visibility,
              "software":{"python":platform.python_version(),"numpy":np.__version__,"rasterio":rasterio.__version__,"matplotlib":matplotlib.__version__}}
    record["spatial_checks_pass"] = all(
        result["metrics"]["uncovered_ground_fraction"] == 0
        and result["metrics"]["bottom_edge_coverage_fraction"] == 1
        and result["metrics"]["nonfinite_or_near_triangles"] == 0
        and folds[method]["nonfinite_volume_samples"] == 0
        and folds[method]["nonpositive_volume_samples"] == 0
        and folds[method]["native_triangle_prisms"]["nonfinite_tetrahedra"] == 0
        and folds[method]["native_triangle_prisms"]["nonpositive_orientation_ratio_tetrahedra"] == 0
        for method,result in results.items())
    (output/"study.json").write_text(json.dumps(record,indent=2)+"\n")
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master",required=True)
    parser.add_argument("--source-scene",required=True)
    parser.add_argument("--config",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.master,args.source_scene,args.config,args.output)


if __name__ == "__main__":
    main()
