"""Render geography and mapped-surface review sheets for the building pilot."""

import json

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "datascape-buildings-work01"
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import shapely

from .massing import polygons
from .projection import composite, project_masses


PAPER = "#f6f3eb"
INK = "#232e29"
SUBTLE = "#52615a"
PALETTE = np.array([[.16, .35, .31], [.36, .52, .44], [.59, .58, .46], [.65, .40, .24]])
CREDIT = ("Overture Maps Buildings / ODbL · © OpenStreetMap contributors and Overture source providers · "
          "https://docs.overturemaps.org/attribution/ · https://opendatacommons.org/licenses/odbl/1-0/")
TERRAIN_CREDIT = ("Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH "
                  "2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved")
FABDEM_CREDIT = "FABDEM v1.2 / University of Bristol, Hawker & Neal · non-commercial research terrain"


def page(width, height, title, subtitle, dtm=True):
    fig = plt.figure(figsize=(width, height), facecolor=PAPER)
    fig.text(.045, .966, title, size=24, color=INK, weight="bold", va="top")
    fig.text(.045, .927, subtitle, size=10, color=SUBTLE, va="top")
    for i, credit in enumerate([CREDIT, TERRAIN_CREDIT, *([FABDEM_CREDIT] if dtm else [])]):
        fig.text(.045, .012 + (.008 * i), credit, size=6, color=SUBTLE)
    return fig


def scene_image(terrain, owner, tones, projected):
    shade, fraction, ground_owner, _ = terrain
    base = np.array([.30, .36, .31])
    paper = np.array([.968, .956, .923])
    color = paper - (1 - shade[:, :, None]) * (paper - base)
    active = owner >= 0
    if active.any():
        labels = np.array([3 if item.mass.height_kind != "overture_height_field" else
                           ("near", "middle", "far").index(item.band) for item in projected])
        indexes = owner[active]
        color[active] = PALETTE[labels[indexes]] * tones[active, None] + (.20 + .10 * tones[active, None])
        boundary = np.zeros(active.shape, dtype=bool)
        boundary[1:] |= owner[1:] != owner[:-1]
        boundary[:, 1:] |= owner[:, 1:] != owner[:, :-1]
        color[active & boundary] *= .78
    color[ground_owner < 0] = np.where(active[ground_owner < 0, None],
                                       color[ground_owner < 0], paper)
    return np.clip(color, 0, 1)


def local_plan(ax, buildings, primary, mapping):
    x, y = mapping.base.target_raw_xyz_m[:2]
    span = 1200
    grid = primary.grid
    select_x = abs(grid.x_m[0] - x) < span + 30
    select_y = abs(grid.y_m[:, 0] - y) < span + 30
    window = np.ix_(select_y, select_x)
    ax.contour(grid.x_m[window], grid.y_m[window], grid.elevation_m[window],
               levels=np.arange(25, 850, 25), colors="#a9ae9c", linewidths=.42)
    region = shapely.box(x - span, y - span, x + span, y + span)
    valid = buildings.eligible & shapely.intersects(buildings.footprints, region)
    layers = {"other": [], "apartments": [], "house": [], "commercial": [], "retail": []}
    for i in np.flatnonzero(valid):
        row = buildings.records[i]
        family = row["class"] if row["class"] in layers else "other"
        for poly in polygons(buildings.footprints[i]):
            layers[family].extend([np.asarray(ring.coords) for ring in (poly.exterior, *poly.interiors)])
    for key, color in zip(layers, ("#9eaaa0", "#204f4b", "#6a713e", "#a16642", "#a16642")):
        ax.add_collection(LineCollection(layers[key], colors=color, linewidths=.36 if key == "other" else .58))
    bearing = np.deg2rad(mapping.base.camera.azimuth_deg)
    dx, dy = np.array([np.sin(bearing), np.cos(bearing)]) * 370
    ax.annotate("", xy=(x + dx, y + dy), xytext=(x - dx * .25, y - dy * .25),
                arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 1.6})
    ax.plot(x, y, "o", color=INK, markersize=3)
    ax.plot([x - 1040, x - 540], [y - 1040] * 2, color=INK, lw=1.35)
    ax.text(x - 790, y - 995, "500 m", color=INK, ha="center", size=6)
    ax.text(x + 1050, y + 950, "N", color=INK, ha="center", size=8, weight="bold")
    ax.set(xlim=(x - span, x + span), ylim=(y - span, y + span), aspect="equal", facecolor=PAPER)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#c9cec3")


def comparison_chart(screens, buildings, primary, selected_id, output):
    names = "A / Hongje     B / Jeongneung     C / Suyu"
    fig = page(13.4, 22.0, "Datascape / Buildings 01",
               f"Seoul North · {names} · Overture 2026-11-18.0 · Spring P3 mapping",
               dtm=any(item["stats"]["terrain_kind"] == "fabdem_dtm_proxy" for item in screens))
    fig.text(.046, .869, "Source footprint plans · 25 m contours", color=SUBTLE, size=9)
    fig.text(.327, .869, "Projected source-height masses · near and middle distance", color=SUBTLE, size=9)
    for i, screen in enumerate(screens):
        y = .630 - i * .267
        ax = fig.add_axes([.045, y, .236, .214])
        local_plan(ax, buildings, primary, screen["mapping"])
        ax.set_anchor("N")
        ax = fig.add_axes([.326, y - .009, .624, .231])
        ax.imshow(screen["image"], extent=(0, 440, 300, 0))
        ax.set_anchor("N")
        ax.axis("off")
        view, stats = screen["view"], screen["stats"]
        near = stats["classified_views"]["near"]["objects_visible"]
        middle = stats["classified_views"]["middle"]["objects_visible"]
        selected = " / Selected" if view["id"] == selected_id else ""
        label = f"{view['id']}   {view['name']}{selected}"
        fig.text(.045, y - .019, label, size=13, color=INK, weight="bold")
        fig.text(.326, y - .021, f"{near:,} near  /  {middle:,} middle visible", size=9, color=SUBTLE)
    fig.text(.045, .053, "Plan colors  ·  teal apartments  /  olive house  /  ochre commercial & retail  /  grey other and unclassified",
             color=SUBTLE, size=8)
    fig.savefig(output / "viewpoint_comparison.png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    chosen = next(screen for screen in screens if screen["view"]["id"] == selected_id)
    fig = page(11, 11, f"{chosen['view']['name']} / Source plan",
               "Native Overture footprint or roofprint · 25 m contours · projected metric coordinates",
               dtm=chosen["stats"]["terrain_kind"] == "fabdem_dtm_proxy")
    ax = fig.add_axes([.075, .08, .85, .80])
    local_plan(ax, buildings, primary, chosen["mapping"])
    fig.savefig(output / "selected_source_plan.svg", facecolor=fig.get_facecolor(), metadata={"Date": None})
    plt.close(fig)


def detail_chart(screen, grounds, output):
    stats = screen["stats"]
    fig = page(13.4, 17.3, f"{screen['view']['name']} / Geometry and visibility",
               "Source-height baseline, two controlled display comparisons, and ground-elevation sensitivity",
               dtm=stats["terrain_kind"] == "fabdem_dtm_proxy")
    image = screen["image"]
    land = scene_image(screen["land"], np.full(image.shape[:2], -1), None, [])
    panes = [
        ("Terrain only", land),
        ("Source-height masses / far omitted", image),
        ("Far layer enabled / same source heights", screen["with_far_image"]),
        ("Floor-derived scenario / 3 m per floor (ochre)", screen["with_estimates_image"]),
    ]
    for i, (label, raster) in enumerate(panes):
        ax = fig.add_axes([.045 + .466 * (i % 2), .653 - .267 * (i // 2), .444, .235])
        ax.imshow(raster)
        ax.set_anchor("N")
        ax.axis("off")
        ax.set_title(label, loc="left", fontsize=11, color=INK)
    left = fig.add_axes([.070, .115, .383, .182], facecolor=PAPER)
    right = fig.add_axes([.533, .115, .383, .182], facecolor=PAPER)
    dtm = grounds["dtm_m"]
    for key, tint, label in [("raw_dsm_m", "#9c633a", "Raw DSM minus DTM"),
                             ("dsm_proxy_m", "#37645b", "Footprint-free DSM proxy minus DTM")]:
        diff = grounds[key] - dtm
        left.hist(diff[np.isfinite(diff)], bins=np.r_[np.arange(-24, 25, 2)], histtype="step", lw=2,
                  color=tint, label=label)
    left.set(xlabel="Ground difference (m), display clipped to ±24 m", ylabel="Height-bearing records")
    left.legend(frameon=False, fontsize=8)
    relief = grounds["dtm_footprint_vertex_relief_m"]
    right.hist(relief[np.isfinite(relief)], bins=np.arange(0, 30, 1), color="#527064")
    right.set(xlabel="DTM relief between footprint vertices (m), displayed to 29 m", ylabel="Height-bearing records")
    for axis in (left, right):
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(colors=SUBTLE, labelsize=8)
    caption = f"{stats['terrain_pixels_hidden_by_buildings']:,} terrain pixels covered · " \
              f"{stats['far_owner_pixels_if_enabled']:,} pixels owned by far buildings when enabled · " \
              f"{stats['floor_height_scenario_visible']:,} floor-derived buildings visible in the comparison"
    fig.text(.045, .065, caption, color=SUBTLE, size=9)
    fig.savefig(output / "selected_geometry_visibility.png", dpi=155, facecolor=fig.get_facecolor())
    plt.close(fig)


def part_chart(parent, children, mapping, plan_overlap, lonlat, output):
    width, height = 700, 460
    empty = (np.ones((height, width)), np.zeros((height, width)),
             np.full((height, width), -1), np.full((height, width), np.inf))
    alternatives = []
    fig = page(12, 7.5, "Building parts / Source relationship",
               "An actual Seoul North parent and its height-bearing linked parts, isolated from unrelated buildings",
               dtm=parent.ground_kind == "fabdem_dtm_proxy")
    for i, (label, masses) in enumerate([("Parent prism", [parent]), ("Linked prisms / depth composite", children)]):
        projected = project_masses(masses, mapping, width, height)
        owner, tones, rows = composite(projected, empty, width, height)
        ax = fig.add_axes([.048 + .465 * i, .16, .435, .68])
        ax.imshow(scene_image(empty, owner, tones, projected))
        ax.axis("off")
        ax.set_title(label, loc="left", color=INK, size=12)
        alternatives.append({"representation": label, "objects": rows})
    fig.text(.046, .123, f"{len(children)} height-bearing parts · {plan_overlap} positive-area overlaps in plan · Parent ID {parent.id}",
             size=9, color=SUBTLE)
    fig.savefig(output / "building_parts.svg", facecolor=fig.get_facecolor(), metadata={"Date": None})
    plt.close(fig)
    record = {"parent_id": parent.id, "parent_center_lon_lat": list(lonlat), "eligible_parts": len(children),
              "part_plan_overlap_pairs": plan_overlap, "alternatives": alternatives}
    (output / "building_parts.json").write_text(json.dumps(record, indent=2) + "\n")
