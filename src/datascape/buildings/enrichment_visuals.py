"""Aligned comparison plates and measurable architectural crops."""

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from .massing import polygons
from .visuals import CREDIT, FABDEM_CREDIT, TERRAIN_CREDIT


PAPER = "#f6f3eb"
INK = "#26382f"
REF_CREDIT = "Building polygons: Seo, B., Park, S. J. & Park, J. (2026) / Zenodo 21881381 / CC BY 4.0, when using the research reference."


def page(width, height, title, description, terrain=True):
    fig = plt.figure(figsize=(width, height), facecolor=PAPER)
    fig.text(.045, .97, title, color=INK, size=21, weight="bold", va="top")
    fig.text(.045, .925, description, color=INK, size=9, va="top")
    credits = [CREDIT, TERRAIN_CREDIT, FABDEM_CREDIT] if terrain else [CREDIT]
    for i, line in enumerate(credits):
        fig.text(.045, .017 + .012*i, line, color=INK, size=6)
    return fig


def raster_plot(ax, result, name):
    ax.axis("off")
    ax.set_title(name, loc="left", color=INK, size=12)
    ax.imshow(result["image"])
    stats = result["stats"]
    ax.text(0, -.035,
            f"{stats['visible']:,} visible / {stats['estimated_visible']:,} estimates / "
            f"{stats['urban_owned_frame_fraction']:.1%} of frame owned by buildings",
            transform=ax.transAxes, color=INK, fontsize=8, va="top")


def charts(results, h1_status, output):
    fig = page(15, 6.1, "Datascape Buildings 01B / Fixed View A0",
               "Same terrain, P3 projection and 440 × 300 mm scale. Green is Overture height. Ochre is estimated from floors.")
    grid = fig.add_gridspec(1, 3, left=.045, right=.96, bottom=.155, top=.85, wspace=.075)
    for i, (key, name) in enumerate([("A0_H0", "H0 / native Overture"),
                                     ("A0_H1", "H1 / official registry"),
                                     ("A0_H2", "H2 / additional floor estimates")]):
        ax = fig.add_subplot(grid[0, i])
        if key in results:
            raster_plot(ax, results[key], name)
        else:
            ax.set_facecolor("#e9e7dc")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_color("#cdcec0")
            ax.set_title(name, loc="left", color=INK, size=12)
            notice = ("Official building file unavailable" if h1_status == "official_records_unavailable"
                      else "No accepted regional height")
            ax.text(.5, .59, notice, ha="center", transform=ax.transAxes,
                    size=11, weight="bold", color=INK)
            ax.text(.5, .43, "The public reference supplies footprint evidence.", ha="center",
                    transform=ax.transAxes, size=8, color=INK)
    fig.savefig(output / "01_fixed_view.png", dpi=155)
    plt.close(fig)

    fig = page(12.2, 10.3, "Architectural scale / P3 frame comparison",
               "Identical height policy across frames. A1 crops the mapped view. A2 tests a smaller foothill neighborhood.")
    grid = fig.add_gridspec(2, 2, left=.045, right=.96, bottom=.085, top=.86, hspace=.20, wspace=.09)
    candidates = ["A0_H2", *[key for key in results if key.startswith("A1-")], "A2"]
    labels = {"A0_H2": "A0 / width 3,300 m", "A1-2200": "A1 / width 2,200 m",
              "A1-1650": "A1 / width 1,650 m", "A2": "A2 / local type study, width 820 m"}
    for i, key in enumerate(candidates):
        raster_plot(fig.add_subplot(grid[i // 2, i % 2]), results[key], labels.get(key, key))
    fig.savefig(output / "02_scale_review.png", dpi=155)
    plt.close(fig)

    near = results["A2"]
    fig = page(12.2, 6.4, "Readability on the 440 × 300 mm sheet",
               "Each outline is a size probe. Measurements use final visible pixels. Expanded previews retain the reported original size.")
    grid = fig.add_gridspec(1, 3, left=.045, right=.96, bottom=.17, top=.84, wspace=.12)
    selections = [("apartments", "Apartment"), ("house", "House"), ("commercial", "Commercial")]
    for i, (kind, title) in enumerate(selections):
        accepted = {"house", "detached"} if kind == "house" else {kind}
        options = [row for row in near["rows"] if row["bbox_px_xyxy"] and row["class"] in accepted]
        if kind == "commercial":
            low = [row for row in options if row["model_height_m"] <= 22]
            options = low or options
        ax = fig.add_subplot(grid[0, i])
        ax.axis("off")
        if not options:
            ax.text(.5, .50, "No visible native class in A2", color=INK, ha="center", transform=ax.transAxes)
            ax.set_title(title, loc="left", color=INK, size=11)
            continue
        row = max(options, key=lambda item: item["visible_facade_area_mm2"])
        x, y, right, bottom = row["bbox_px_xyxy"]
        center_x = (x + right) // 2
        center_y = (y + bottom) // 2
        radius = max(35, (max(right-x, bottom-y) + 28) // 2)
        ax.imshow(near["image"])
        ax.set(xlim=(center_x-radius, center_x+radius), ylim=(center_y+radius, center_y-radius))
        ax.add_patch(Rectangle((x, y), right-x, bottom-y, fill=False, color="#b05f34", linewidth=1.0))
        ax.set_title(title, loc="left", color=INK, size=11)
        ax.text(0, -.08, f"{row['visible_width_mm']:.1f} × {row['visible_height_mm']:.1f} mm visible\n"
                f"Facade {row['visible_facade_area_mm2']:.1f} mm² · "
                f"{'floor estimate' if row['height_kind'].endswith('_floors') else 'source height'}",
                transform=ax.transAxes, color=INK, size=8, va="top")
    fig.savefig(output / "03_readability_crops.png", dpi=155)
    plt.close(fig)


def footprint_examples(source, registry, shapes, rows, authoritative, output):
    attribution = (REF_CREDIT if not authoritative else
                   "Regional source attribution and license are recorded in acquisition_matching_audit.json.")
    fig = page(12, 6.8, "Regional match examples / Source polygons",
               "Green is the original Overture footprint. Ochre shows candidate regional polygons.", terrain=False)
    fig.text(.045, .038, attribution, color=INK, size=7)
    grid = fig.add_gridspec(2, 4, left=.06, right=.95, bottom=.13, top=.85, hspace=.38, wspace=.25)
    examples = []
    for kind, title in [("apartments", "Apartment"), ("detached", "Detached"), ("house", "House"),
                        ("commercial", "Commercial"), ("retail", "Retail")]:
        options = [(i, row) for i, row in enumerate(rows) if row["native_class"] == kind and
                   row["match_status"] == "high_confidence"]
        if options:
            index, row = max(options, key=lambda item: (item[1]["official_height_m"] is not None,
                                                        item[1]["native_height_m"] is not None,
                                                        item[1]["candidate_overlaps"][0]["iou"]))
            examples.append((index, row, title))
    for status in ("ambiguous", "one_to_many", "many_to_one"):
        option = next(((i, row, status.replace("_", " ").title())
                       for i, row in enumerate(rows) if row["match_status"] == status), None)
        if option:
            examples.append(option)
    from .study import save_json
    details = []
    for j in range(8):
        ax = fig.add_subplot(grid[j//4, j%4])
        ax.axis("off")
        if j >= len(examples):
            continue
        index, row, title = examples[j]
        candidates = row["candidate_overlaps"]
        for shape, color in [(source.footprints[index], "#315851"),
                             *[(shapes[item["region_index"]], "#b17c4a") for item in candidates]]:
            for polygon in polygons(shape):
                for ring in (polygon.exterior, *polygon.interiors):
                    ax.plot(*np.asarray(ring.coords).T, color=color, lw=1.25)
        ax.set_aspect("equal")
        ax.set_title(title, color=INK, fontsize=9)
        native = f"{row['native_height_m']:g} m" if row["native_height_m"] is not None else "missing"
        region = f"{row['official_height_m']:g} m" if row["official_height_m"] is not None else "unavailable"
        ax.text(.5, -.025, f"IoU {candidates[0]['iou']:.2f}\n"
                 f"Native {native} · Official {region}",
                 transform=ax.transAxes, color=INK, size=7, ha="center", va="top")
        details.append({**row, "title": title})
    save_json(output / "footprint_examples.json", details)
    fig.savefig(output / "04_match_examples.png", dpi=155)
    plt.close(fig)
