"""Diagnose and compare A-row breathing on the locked F2-C spring scene."""
from pathlib import Path
import argparse
import io
import json
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

from datascape.data.quality import sha256_file
from datascape.rendering.grammar_study import validate
from datascape.rendering.hierarchy_study import publish_png, publish_vectors, metrics
from datascape.strokes.density_rhythm import density_profile, layer_digest
from datascape.strokes.density_rhythm import a_proposals, foreground_a
from datascape.strokes.mass_density import (
    generate_a, mass_coordinates, phase_redistribution,
)
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.spacing_schedule import (
    explicit_screen_spacing_phase, explicit_source_spacing_phase,
    phase_ablation,
)
from datascape.strokes.vector import read_vectors, resample, sample


BANDS = {
    "crest": (0.00, 0.18),
    "shoulder": (0.25, 0.45),
    "descending": (0.55, 0.75),
    "foot": (0.85, 1.01),
}
METHODS = ["baseline", "v2", "A_topology_05", "B_screen", "B_source"]


def _total_length(strokes):
    return float(sum(np.linalg.norm(np.diff(s["xy_mm"], axis=0), axis=1).sum() for s in strokes))


def _compose(parent, a):
    groups = {k: (a if k == "A" else [s for s in parent if s["layer"] == k])
              for k in ["C", "A", "B", "V", "D"]}
    return [{**s, "draw_order": i}
            for i, s in enumerate(s for k in ["C", "A", "B", "V", "D"] for s in groups[k])]


def _render(strokes, output, bounds=(0, 0, 600, 900), pixels=(1200, 1800),
            mode="production"):
    x0, y0, x1, y1 = bounds
    pw, ph = pixels
    fig = plt.figure(figsize=(pw / 150, ph / 150), dpi=150, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(x0, x1), ylim=(y1, y0))
    ax.axis("off")
    colors = {"A": "#62676e", "B": "#9b59b6", "C": "#4591bc", "D": "#d54335", "V": "#14866d"}
    lines, widths, rgba = [], [], []
    for s in strokes:
        layer = s["layer"]
        if mode == "A_only" and layer != "A":
            continue
        p = np.asarray(s["xy_mm"], dtype=float)
        wp = np.asarray(s.get("width_profile_mm", [s["width_mm"]] * len(p)), dtype=float)
        op = np.asarray(s.get("opacity_profile", [s.get("preview_opacity", 1)] * len(p)), dtype=float)
        if mode in {"A_only", "black"}:
            color, op = "black", np.ones(len(p))
        elif mode == "layers":
            color, op = colors[layer], np.ones(len(p))
        else:
            color = "black"
        for i in range(len(p) - 1):
            lines.append(p[i:i + 2])
            widths.append(.32 if mode == "A_only" else (wp[i] + wp[i + 1]) / 2)
            alpha = 1.0 if mode in {"A_only", "black", "layers"} else (op[i] + op[i + 1]) / 2
            rgba.append(matplotlib.colors.to_rgba(color, float(alpha)))
    ax.add_collection(LineCollection(
        lines, linewidths=np.asarray(widths) * pw / (x1 - x0) * 72 / 150,
        colors=rgba, capstyle="round", joinstyle="round"))
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, facecolor="white")
    plt.close(fig)
    publish_png(buffer.getvalue(), output)


def _physical_pair(source, output):
    image = Image.open(source).convert("RGB")
    width, height = image.size
    canvas = Image.new("RGB", (width + round(width * 40 / 600), height), "#dddddd")
    canvas.paste(image.crop((0, 0, width // 2, height)), (0, 0))
    gap = round(width * 40 / 600)
    canvas.paste(image.crop((width // 2, 0, width, height)), (width // 2 + gap, 0))
    canvas.save(output)


def _crossings(strokes, x_mm, bounds):
    y0, y1 = bounds
    found = []
    for s in strokes:
        p = np.asarray(s["xy_mm"], dtype=float)
        a, b = p[:-1], p[1:]
        dx = b[:, 0] - a[:, 0]
        idx = np.flatnonzero((np.minimum(a[:, 0], b[:, 0]) <= x_mm) &
                             (np.maximum(a[:, 0], b[:, 0]) > x_mm) &
                             (np.abs(dx) > 1e-9))
        for i in idx:
            y = a[i, 1] + (x_mm - a[i, 0]) / dx[i] * (b[i, 1] - a[i, 1])
            if y0 <= y < y1:
                found.append(float(y))
    found.sort()
    unique = []
    for y in found:
        if not unique or y - unique[-1] > .08:
            unique.append(y)
    return np.asarray(unique)


def _band_spacing(strokes, mass, label, x_mm, y_bounds):
    ys = _crossings(strokes, x_mm, y_bounds)
    labels, t = mass["labels"], mass["t"]
    rows = []
    for y0, y1 in zip(ys[:-1], ys[1:]):
        ym = (y0 + y1) / 2
        ix, iy = int(np.clip(x_mm, 0, labels.shape[1] - 1)), int(np.clip(ym, 0, labels.shape[0] - 1))
        if labels[iy, ix] != label:
            continue
        tv = float(t[iy, ix])
        band = next((name for name, (lo, hi) in BANDS.items() if lo <= tv < hi), None)
        if band:
            rows.append((band, float(y1 - y0)))
    result = {name: {"n": 0, "median_mm": None, "p10_mm": None, "p90_mm": None}
              for name in BANDS}
    for name in BANDS:
        values = np.array([gap for band, gap in rows if band == name], dtype=float)
        if len(values):
            result[name] = {"n": int(len(values)), "median_mm": float(np.median(values)),
                            "p10_mm": float(np.percentile(values, 10)),
                            "p90_mm": float(np.percentile(values, 90))}
    crest = result["crest"]["median_mm"]
    open_gap = result["shoulder"]["median_mm"]
    descent = result["descending"]["median_mm"]
    dense = [x for x in [crest, descent] if x is not None]
    result["crest_to_open_ratio"] = float(open_gap / crest) if open_gap and crest else None
    result["open_to_descending_ratio"] = float(open_gap / descent) if open_gap and descent else None
    result["open_to_dense_mean_ratio"] = float(open_gap / np.mean(dense)) if open_gap and dense else None
    result["crossings"] = int(len(ys))
    return result


def _diagnostic_spacing_image(out, mass, chosen, forms):
    fig, axes = plt.subplots(len(forms), len(chosen), figsize=(3.0 * len(chosen), 3.8 * len(forms)), sharey="row")
    axes = np.asarray(axes).reshape(len(forms), len(chosen))
    for row, (label, probe_x, y_bounds) in enumerate(forms):
        for col, method in enumerate(chosen):
            ax = axes[row, col]
            values = _crossings(chosen[method]["candidate"], probe_x, y_bounds)
            ax.hlines(values, .18, .82, color="black", lw=.8)
            ax.set(xlim=(0, 1), ylim=(y_bounds[1], y_bounds[0]))
            ax.set_xticks([])
            ax.grid(axis="y", color="#999999", alpha=.22, linewidth=.5)
            measure = _band_spacing(chosen[method]["candidate"], mass, label, probe_x, y_bounds)
            def mm(name):
                value = measure[name]["median_mm"]
                return "—" if value is None else f"{value:.2f}"
            ratio = measure["open_to_dense_mean_ratio"]
            ratio_text = "—" if ratio is None else f"{ratio:.2f}×"
            ax.set_title(method.replace("_", " ") +
                         f"\nC {mm('crest')} · O {mm('shoulder')} · D {mm('descending')} mm\nOpen/dense {ratio_text}", fontsize=8)
            if col == 0:
                ax.set_ylabel(f"Form {label} · y (mm)")
        axes[row, 0].set_xlabel(f"x = {probe_x:.1f} mm")
    fig.suptitle("Same mountain profile · opaque 0.32 mm A centerlines · adjacent crossing gaps in mm", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(out / "spacing_probes.png", dpi=170, facecolor="white")
    plt.close(fig)


def _draw_ablation_table(fixed, mass, fields):
    labels = [5, 9]
    rows = []
    for method, field in fields.items():
        safe = field.get("safe", mass["labels"] > 0)
        ratios = {}
        for mid in labels:
            m = (mass["labels"] == mid) & safe
            ratios[str(mid)] = {}
            for band, (lo, hi) in BANDS.items():
                pick = m & (mass["t"] >= lo) & (mass["t"] < hi)
                ratios[str(mid)][band] = float(np.median(field["directional_phase_ratio"][pick])) if pick.any() else None
        rows.append({"method": method, "local_field_medians": ratios,
                     "topology_gain": {str(x["label"]): x.get("topology_gain", 1.0)
                                       for x in field.get("integration", [])}})
    return rows


def run(master, veg, config_path, output, repo_root=None):
    config_path = Path(config_path)
    root = Path(repo_root) if repo_root else config_path.resolve().parents[2]
    cfg = json.loads(config_path.read_text())
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    for path, digest in cfg["locked_source_sha256"].items():
        if sha256_file(root / path) != digest:
            raise ValueError(f"Locked file changed: {path}")
    selection = json.loads((root / cfg["selection"]).read_text())
    fixed = load_selected_scene(master, veg, root, selection)
    fixed["_grammar_safe"] = distance_transform_edt((fixed["retention"] > 1e-8) & fixed["base"]["occupied"])
    fixed["_grammar_xyz"] = np.nan_to_num(fixed["base"]["xyz"])
    parent = read_vectors(root / cfg["baseline_vectors"])["strokes"]
    v2_cfg = json.loads((root / cfg["v2_config"]).read_text())
    baseline_cfg = json.loads((root / cfg["baseline_config"]).read_text())
    mist_cfg = json.loads((root / cfg["mist_config"]).read_text())
    base_profile = density_profile(fixed, baseline_cfg)
    masses = mass_coordinates(fixed, parent, v2_cfg)

    print("Replay PR #12 mountain-relative A phase", flush=True)
    v2_fields = phase_redistribution(fixed, masses, base_profile, v2_cfg)
    fields = {"v2": v2_fields}
    ablations = [
        ("endpoint_global", {"endpoint": "global"}),
        ("no_boundary_feather", {"boundary_feather_mm": 0}),
        ("no_phase_smoothing", {"smoothing_mm": 0}),
        ("max_displacement_16mm", {"maximum_displacement": 16}),
        ("topology_floor_10pct", {"minimum_derivative_ratio": .10}),
        ("topology_floor_05pct", {"minimum_derivative_ratio": .05}),
    ]
    ablation_records = []
    for name, kwargs in ablations:
        print("One-factor ablation: " + name, flush=True)
        value = phase_ablation(fixed, masses, base_profile, v2_cfg, **kwargs)
        fields[name] = value
        ablation_records.append({"method": name, "changed_constraint": kwargs,
                                 "phase_derivative_nonpositive_pixels": value["phase_derivative_nonpositive_pixels"],
                                 "integration": value["integration"]})

    baseline_candidate = foreground_a(a_proposals(fixed, base_profile, baseline_cfg), fixed, .72)
    print("Compare explicit screen-space and source-space schedules", flush=True)
    screen = explicit_screen_spacing_phase(fixed, masses, base_profile, v2_cfg)
    source = explicit_source_spacing_phase(fixed, masses, base_profile, v2_cfg,
                                           minimum_derivative_ratio=.05)
    fields["B_screen"] = screen
    fields["B_source"] = source
    fields["A_topology_05"] = fields["topology_floor_05pct"]

    raw_by_method, after_by_method, field_records = {}, {}, {}
    for method in METHODS:
        field = None if method == "baseline" else fields[method]
        if method == "baseline":
            after = [s for s in parent if s["layer"] == "A"]
            candidate = baseline_candidate
            generation = {"baseline_A_paths": len(after), "baseline_A_length_mm": _total_length(after)}
        else:
            after, raw_mountain, selection_record = generate_a(fixed, field, parent, v2_cfg, mist_cfg)
            candidate = raw_mountain
            generation = {**selection_record, "candidate_paths_before_mist": len(candidate),
                          "candidate_length_mm": _total_length(candidate),
                          "final_A_length_mm": _total_length(after)}
        raw_by_method[method] = candidate
        after_by_method[method] = after
        field_records[method] = generation

    chosen_forms = [(5, 442.5, (317, 455)), (9, 586.5, (350, 533))]
    measures = {"forms": [], "methods": {}}
    for method in METHODS:
        measures["methods"][method] = {"A_paths_after_mist": len(after_by_method[method]),
            "A_length_after_mist_mm": _total_length(after_by_method[method]),
            "A_candidate_paths_before_mist": len(raw_by_method[method]),
            "A_candidate_length_before_mist_mm": _total_length(raw_by_method[method]),
            "forms": {}}
        for label, probe_x, yb in chosen_forms:
            measures["methods"][method]["forms"][str(label)] = {
                "probe_x_mm": probe_x, "y_bounds_mm": list(yb),
                "candidate": _band_spacing(raw_by_method[method], masses, label, probe_x, yb),
                "after_mist": _band_spacing(after_by_method[method], masses, label, probe_x, yb),
            }
    for label, probe_x, yb in chosen_forms:
        region = {}
        item = next(x for x in masses["masses"] if x["label"] == label)
        x0, _, x1, _ = item["bounds_mm"]
        xs = np.linspace(x0 + .15 * (x1 - x0), x1 - .15 * (x1 - x0), 9)
        for method in METHODS:
            gaps = {b: [] for b in BANDS}
            for x in xs:
                values = _band_spacing(after_by_method[method], masses, label, float(x),
                                       (int(item["bounds_mm"][1]), int(item["bounds_mm"][3])))
                for band in BANDS:
                    n = values[band]["n"]
                    if n:
                        ys = _crossings(after_by_method[method], float(x),
                                        (int(item["bounds_mm"][1]), int(item["bounds_mm"][3])))
                        # Rebuild exact gap lists for the nine-column region from the same field.
                        for y0, y1 in zip(ys[:-1], ys[1:]):
                            iy, ix = int((y0 + y1) / 2), int(np.clip(x, 0, 599))
                            if masses["labels"][iy, ix] != label:
                                continue
                            tmid = masses["t"][iy, ix]
                            if BANDS[band][0] <= tmid < BANDS[band][1]:
                                gaps[band].append(float(y1 - y0))
            med = {k: float(np.median(v)) if v else None for k, v in gaps.items()}
            contrast = min([med[k] for k in ["crest", "descending"] if med[k] is not None], default=None)
            dense = [med[k] for k in ["crest", "descending"] if med[k] is not None]
            region[method] = {"nine_probe_band_medians_mm": med,
                              "open_to_dense_mean_ratio": float(med["shoulder"] / np.mean(dense))
                              if dense and med["shoulder"] else None,
                              "gap_counts": {k: len(v) for k, v in gaps.items()}}
        measures["forms"].append({"label": label, "bounds_mm": item["bounds_mm"],
                                   "nine_probe_region": region})

    # Frozen production-style full compositions: the only changed layer is A.
    full_sets = {method: _compose(parent, after_by_method[method]) for method in METHODS}
    for method, strokes in full_sets.items():
        validate(strokes, fixed)
        for layer in ["B", "C", "D", "V"]:
            if layer_digest(strokes, layer) != layer_digest(parent, layer):
                raise AssertionError(f"Frozen {layer} geometry changed in {method}")
    full = out / "full"
    local = out / "local"
    full.mkdir(exist_ok=True)
    local.mkdir(exist_ok=True)
    for method in ["baseline", "v2", "A_topology_05"]:
        _render(full_sets[method], full / f"{method}_production.png", mode="production")
        _physical_pair(full / f"{method}_production.png", full / f"{method}_physical.png")
        _render(full_sets[method], full / f"{method}_black.png", mode="black")
    # Shared full-width comparison and physical pair are the review-facing images.
    fig, axes = plt.subplots(1, 3, figsize=(12, 6.5))
    for ax, method in zip(axes, ["baseline", "v2", "A_topology_05"]):
        ax.imshow(Image.open(full / f"{method}_production.png"))
        ax.axis("off")
        ax.set_title({"baseline": "PR #11 baseline", "v2": "PR #12 v2", "A_topology_05": "v3 · topology floor 0.05"}[method])
    fig.suptitle("Locked F2-C · same B/C/D/V, mist, retention and production styling")
    fig.tight_layout()
    fig.savefig(full / "full_comparison.png", dpi=150, facecolor="white")
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 6.5))
    for ax, method in zip(axes, ["baseline", "v2", "A_topology_05"]):
        ax.imshow(Image.open(full / f"{method}_physical.png"))
        ax.axis("off")
        ax.set_title({"baseline": "PR #11 baseline", "v2": "PR #12 v2", "A_topology_05": "v3 · topology floor 0.05"}[method])
    fig.suptitle("300 mm + 40 mm physical gap + 300 mm")
    fig.tight_layout()
    fig.savefig(full / "physical_comparison.png", dpi=150, facecolor="white")
    plt.close(fig)

    # Proof crops use constant-width, opaque A centerlines before and after unchanged mist.
    form_records = []
    for label, probe_x, yb in chosen_forms:
        mass_record = next(x for x in masses["masses"] if x["label"] == label)
        x0, _, x1, y1 = mass_record["bounds_mm"]
        x0 = max(0, int(x0 - 8)); x1 = min(600, int(x1 + 8))
        y0 = max(0, int(yb[0] - 12)); y1 = min(900, int(yb[1] + 12))
        bounds = (x0, y0, x1, y1)
        fig, axes = plt.subplots(2, 3, figsize=(11, 7))
        for row, stage in enumerate(["candidate", "after mist"]):
            for col, method in enumerate(["baseline", "v2", "A_topology_05"]):
                ax = axes[row, col]
                paths = raw_by_method[method] if stage == "candidate" else after_by_method[method]
                selected = [s for s in paths if s["layer"] == "A"]
                # Baseline vectors are already post-mist; label the stage accurately.
                _plot_axes(ax, selected, bounds, .32)
                ax.set_title(("Candidate / " if stage == "candidate" else "After mist / ") + method.replace("_", " "), fontsize=9)
        fig.suptitle(f"Analysis form {label} · same source catchment · x={probe_x:g} mm probe")
        fig.tight_layout()
        fig.savefig(local / f"form_{label}_vectors.png", dpi=160, facecolor="white")
        plt.close(fig)
        # Store a single-probe summary for the report.
        form_records.append({"label": label, "bounds_mm": mass_record["bounds_mm"],
                             "probe_x_mm": probe_x, "probe_y_bounds_mm": list(yb)})
    _diagnostic_spacing_image(local, masses,
                              {m: {"candidate": raw_by_method[m]} for m in METHODS},
                              chosen_forms)
    # Layer diagnostic: B/C/D/V are the exact same saved records in every column.
    fig, axes = plt.subplots(1, 3, figsize=(12, 6.5))
    for ax, method in zip(axes, ["baseline", "v2", "A_topology_05"]):
        _plot_axes(ax, full_sets[method], (0, 0, 600, 900), None, layers=True)
        ax.axis("off")
        ax.set_title(method.replace("_", " "))
    fig.suptitle("Diagnostic layer colors · only A geometry changes")
    fig.tight_layout()
    fig.savefig(out / "layer_diagnostic.png", dpi=150, facecolor="white")
    plt.close(fig)

    # Publish the v3 canonical actual vector data and unattenuated A candidates.
    provenance = {"study": cfg["study"], "seed": cfg["seed"],
                  "composition": "Locked F2-C; original DEM, 70/30 foreground retention, current whitespace and mist transfer",
                  "method": "A phase redistribution with minimum directional derivative ratio 0.05",
                  "parent_pr12_commit": cfg["parent_commit"],
                  "baseline_vector_sha256": sha256_file(root / cfg["baseline_vectors"]),
                  "note": "Experimental candidate; PR #11 blended_color_ready remains the approved baseline."}
    publish_vectors(out / "v3_A_candidates_before_mist.json.gz", raw_by_method["A_topology_05"],
                    {**provenance, "diagnostic_only": True})
    publish_vectors(out / "v3_full_strokes_after_mist.json.gz", full_sets["A_topology_05"], provenance)

    ablation_summary = _draw_ablation_table(fixed, masses, fields)
    explicit_schedule_records = {}
    for name, value in [("B_screen", screen), ("B_source", source)]:
        explicit_schedule_records[name] = {
            "phase_derivative_nonpositive_pixels_after_guard": value["phase_derivative_nonpositive_pixels"],
            "phase_derivative_nonpositive_pixels_before_guard": value["unlimited_phase_derivative_nonpositive_pixels"],
            "schedule_positions": value["schedule_positions"],
            "spacing_multipliers": value["schedule_multipliers"],
            "integration": value["integration"],
        }
    density = {"study": cfg["study"], "source_hashes": {p: sha256_file(root / p) for p in cfg["locked_source_sha256"]},
               "inputs": selection["input_sha256"], "seed": cfg["seed"],
               "phase_ablation": ablation_records, "phase_local_band_medians": ablation_summary,
               "explicit_schedule_diagnostics": explicit_schedule_records,
               "methods": field_records, "spacing": measures, "selected_forms": form_records,
               "metrics": {k: metrics(v, fixed["base"]) for k, v in full_sets.items()},
               "invariants": {"locked_F2_C": True, "DEM_and_projection_unchanged": True,
                   "B_C_D_V_identical": True, "foreground_retention_read_only": True,
                   "foreground_A_inherited": True, "mist_transfer_unchanged": True,
                   "nonpositive_phase_derivative_pixels": {k: v["phase_derivative_nonpositive_pixels"]
                       for k, v in fields.items()}, "no_full_composition_regeneration_of_other_layers": True},
               "versions": {"python": platform.python_version(), "numpy": np.__version__,
                            "matplotlib": matplotlib.__version__}}
    (out / "record.json").write_text(json.dumps(density, indent=2, allow_nan=False) + "\n")
    return density


def _plot_axes(ax, strokes, bounds, width, layers=False, panel_inches=3.3):
    x0, y0, x1, y1 = bounds
    colors = {"A": "#62676e", "B": "#9b59b6", "C": "#4591bc", "D": "#d54335", "V": "#14866d"}
    lines, widths, rgba = [], [], []
    for s in strokes:
        p = np.asarray(s["xy_mm"], dtype=float)
        wp = np.asarray(s.get("width_profile_mm", [s["width_mm"]] * len(p)), dtype=float)
        for a, b, wa, wb in zip(p[:-1], p[1:], wp[:-1], wp[1:]):
            lines.append([a, b])
            widths.append(width if width is not None else (wa + wb) / 2)
            rgba.append(matplotlib.colors.to_rgba(colors[s["layer"]] if layers else "black", 1.0))
    ax.set(xlim=(x0, x1), ylim=(y1, y0))
    ax.add_collection(LineCollection(lines, linewidths=np.asarray(widths) * panel_inches / (x1 - x0) * 72,
                                     colors=rgba, capstyle="round", joinstyle="round"))
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master")
    parser.add_argument("veg")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo-root")
    args = parser.parse_args()
    run(args.master, args.veg, args.config, args.output, args.repo_root)


if __name__ == "__main__":
    main()
