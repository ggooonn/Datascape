"""Audit catalog preservation, patch geometry and aligned vector exports."""
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .atlas_v08 import INDEX
from .catalog_v02 import compact
from .catalog_v08 import aligned_svgs, generate
from .geometry import ROOT
from .ground_attachment_v07 import G, TerrainFrame
from .sheets_v07 import GROUND_ROLES, SITE_BOX, matched_site
from .sheets_v08 import assemble
from .terrain_v03 import terrain_fixture


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def frozen_inputs():
    manifest = json.loads((ROOT / "baseline/V07_MANIFEST_SHA256.json").read_text())
    retained = [k for k in manifest if k == "requirements.txt" or
                k.startswith(("catalog/", "config/", "baseline/"))]
    # Historical Korean reports accompany the distribution, separately from the public checkout.
    required = [k for k in retained if not k.endswith("_KO.md")]
    retained = required + [k for k in retained if k.endswith("_KO.md") and (ROOT / k).is_file()]
    assert all(digest(ROOT / k) == manifest[k] for k in retained)
    source = ROOT.parent / "Datascape_Procedural_Catalog_Refinement_v07"
    if source.is_dir():
        assert all(digest(source / k) == sha for k, sha in manifest.items())
    return len(retained), len(manifest) if source.is_dir() else 0


def ground_metrics(card, frame, reference=None):
    paths = [p for p in card.paths if p.role in GROUND_ROLES]
    model = card.meta["ground"]
    contacts = {contact["key"]: contact for contact in model["contacts"]}
    bodies = {rock["id"]: Polygon(rock["outline"]) for rock in card.meta["rocks"]}
    solid = unary_union(list(bodies.values()))
    max_slope = 0.0
    penetration = 0.0
    painted = set()
    for contact in contacts.values():
        x, y = contact["xy"]
        east, depth, elevation = contact["xyz"]
        assert np.allclose((x, y), frame.project_xy(east, depth)) and np.isclose(elevation, depth - y)
        if contact["kind"] == "rock":
            assert bodies[contact["owner"]].boundary.distance(Point(x, y)) < 1e-6
    for path in paths:
        anchors = [contacts[key] for key in path.features["anchors"]]
        assert all(contact["visible"] for contact in anchors), path.id
        painted.update(path.features["anchors"])
        assert path.pigment in G["colors"][anchors[0]["kind"]]
        assert path.medium == path.phase == "COLOR"
        dx, dy = np.diff(path.xy, axis=0).T
        assert np.all(dx > 0)
        max_slope = max(max_slope, float(np.max(np.abs(np.rad2deg(np.arctan2(dy, dx))))))
        penetration = max(penetration, LineString(path.xy).intersection(solid).length)
        max_stretch = model.get("stretch", 1.0)
        assert G["min_path_mm"] - 1e-8 <= path.length <= 30.1 * max_stretch
    assert max_slope <= G["max_tangent_deg"] + 1e-6
    assert penetration < 1e-6
    assert all(c["key"] in painted for c in contacts.values() if c["kind"] == "root" and c["visible"])
    total = sum(p.length for p in paths)
    result = dict(strokes=len(paths), length_mm=round(total, 2), mean_mm=round(total / len(paths), 4),
                  max_mm=round(max(p.length for p in paths), 3), maximum_slope_deg=round(max_slope, 3),
                  max_rock_penetration_mm=round(penetration, 6), visible_contacts=len(painted),
                  hidden_contacts=sum(not c["visible"] for c in contacts.values()),
                  secondary_strokes=sum(p.features.get("secondary", False) for p in paths))
    if reference:
        result["count_ratio"] = round(len(paths) / reference["strokes"], 4)
        result["mean_ratio"] = round(result["mean_mm"] / reference["mean_mm"], 4)
        assert 1.20 <= result["mean_ratio"] <= 1.35
        assert result["count_ratio"] <= model["density_cap"]
    return result


def verify_site(sheet):
    base, light, checkpoint = sheet.cards
    frame = TerrainFrame.from_lines(terrain_fixture("site/ground", SITE_BOX, 376), SITE_BOX)
    _, frozen, old_patches, *_ = matched_site(frame)
    assert base.paths == frozen + old_patches
    source = ROOT.parent / "Datascape_Procedural_Catalog_Refinement_v07/vectors/01_COMPARISON__02.json.gz"
    if source.is_file():
        current = ROOT / "vectors/01_GROUND__01.json.gz"
        saved = json.loads(gzip.decompress(source.read_bytes()))
        assert json.loads(gzip.decompress(current.read_bytes()))["strokes"] == saved["strokes"]
    for variant in (light, checkpoint):
        assert [p for p in variant.paths if p.role not in GROUND_ROLES] == frozen
        assert variant.meta["ground"]["contacts"] == base.meta["ground"]["contacts"]
    reference = ground_metrics(base, frame)
    return len(frozen), {
        "v07": reference,
        "light": ground_metrics(light, frame, reference),
        "checkpoint": ground_metrics(checkpoint, frame, reference),
    }


def verify_composition(card, metrics):
    key = card.key
    preset = card.meta["preset"]
    box = (8, 79, 249, 139)
    terrain = terrain_fixture(f"combinations/{key}/terrain", box, preset["seed"])
    frame = TerrainFrame.from_lines(terrain, box)
    ground = ground_metrics(card, frame)
    assert 0 < ground["strokes"] <= 2 * card.meta["ground"]["baseline_count"]
    count = Counter("COLOR" if p.medium == "COLOR" else "INK" for p in card.paths)
    canvas = []
    with TemporaryDirectory() as d:
        folder = Path(d)
        aligned_svgs(folder, key, card.paths)
        for layer, expected in (("INK", count["INK"]), ("COLOR", count["COLOR"]), ("COMBINED", sum(count.values()))):
            name = f"{key}_{layer}.svg"
            path = ROOT / "compositions" / name
            assert path.read_bytes() == (folder / name).read_bytes()
            doc = ElementTree.parse(path).getroot()
            canvas.append(doc.attrib["viewBox"])
            assert len(doc.findall("{http://www.w3.org/2000/svg}polyline")) == expected
    assert len(set(canvas)) == 1
    rocks = card.meta["rocks"]
    return {
        "key": key, "seed": preset["seed"], "rock_family": preset["family"],
        "rock_arrangement": preset["arrangement"], "rocks": len(rocks),
        "specimens": len(preset["plants"]), "ink_paths": count["INK"], "color_paths": count["COLOR"],
        "all_path_mm": metrics["mm"], "short_paths_under_6mm": metrics["short_under_6mm"],
        "turn_p95_deg": metrics["turn_p95_deg"], "ground": ground,
    }


def compare_regenerated_exports():
    with TemporaryDirectory() as d:
        folder = Path(d)
        generate(folder, no_png=True)
        files = sorted(p for p in folder.rglob("*") if p.is_file())
        assert all(p.read_bytes() == (ROOT / p.relative_to(folder)).read_bytes() for p in files)
        return len(files)


def verify():
    retained, local_v07 = frozen_inputs()
    sheets = assemble()
    frozen, ground = verify_site(sheets[0])
    metrics = {row["key"]: row for row in json.loads((ROOT / "audit/metrics.json").read_text())}
    compositions = [verify_composition(c, metrics[c.key]) for sheet in sheets[1:] for c in sheet.cards]
    assert len({c["seed"] for c in compositions}) == len(compositions) == 4
    atlas = [ROOT / "atlas" / f"v{v:02}_{key}.svg" for _, v, key, _ in INDEX]
    assert all(p.is_file() and ElementTree.parse(p).getroot().tag.endswith("svg") for p in atlas)
    assert not any(p.suffix.lower() in {".nc", ".tap", ".ngc", ".gcode"} for p in ROOT.rglob("*"))
    for sheet in sheets:
        for card in sheet.cards:
            assert len(card.paths) == len({p.id for p in card.paths})
    data = dict(frozen_v07_source_files=retained, historical_v07_files_verified=local_v07,
                unchanged_nonground_paths=frozen, atlas_sheets=len(atlas), new_sheets=len(sheets),
                regenerated_exports_byte_identical=compare_regenerated_exports(),
                ground_patch_comparison=ground, combinations=compositions)
    (ROOT / "audit/verification.json").write_bytes(compact(data))
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    verify()
