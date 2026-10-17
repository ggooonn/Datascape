# Spring Scene Integration Work — starting handoff

This is a handoff, not a scene integration implementation. Begin a **separate Work
and branch** from `feat/rock-ground-v05-consolidated`; use its published commit as the
pin. Preserve the stack: PR #16 → PR #18 → Rock & Ground v05. Do not start from main,
merge parent PRs, include PR #17 trials, or redesign either accepted catalog.

## First checkpoint and invariants

Compare (1) unchanged baseline, (2) restrained objects, (3) richer but selective
objects, on one real continuous **600 x 900 mm** drawing. Preserve the x=300 mm
physical panel division: two 300 x 900 panels; insert the physical 40 mm gap only
in the pair display, which is 640 x 900 mm. Never stretch the drawing or delete
40 mm of content to create the gap. No arbitrary scene rescaling or camera change.

Use existing A/B/C/D/V, mist/whitespace, 70/30 retention and foreground A strength
.25 unchanged as immutable source records. Keep a source-only baseline side by side
with any derived visible fragments. The first checkpoint is placement, scale,
visibility, grounding and balance; no foreground A-density solve, catalog redesign,
new color engine, stream/path generator or production G-code.

## Exact dependencies and entry points

| Dependency | Pin and entry | Purpose |
| --- | --- | --- |
| Canonical spring | PR #16 artifact/code `fdae976d3c3414f50c23054ad0f9cfa6e2945bca`; branch head/handoff `1834cbe8161cf49d3bc5deac5e4af404f8bbdd09` | Reuse `docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz`, `production.png`, `physical_pair.png`, `record.json` and its README; do not regenerate vectors for a simple overlay |
| Spring config | `configs/scenes/seoul_spring_provisional_baseline_v01.json` SHA-256 `e35f6156165b9588bd93ff11c98e87cc4a21e5b90225163bec3181b72f1e6e3c` | Exact .25 selection, underlying config locks and physical panel rule |
| Tree v10 | PR #18 `f858e7816822c539944c8244677c29a7dd39fc0a`; `vegetation.tree_final_scale.make_tree`, `vector_records`; `configs/experiments/tree_catalog_v10.json` | P/B refined, U v09 and small/light; W experimental. `tree_spatial_groups.members/project` provides local groups, not terrain attachment |
| Rock & Ground v05 | this branch; `ground.structural_detail_v05.base_mass`, `formation`, `feature_detail`; `configs/catalogs/rock_ground_v05.json` | Generate at physical mm sizes; B preferred; A optional; stable new object IDs |
| Ground ownership | `ground.patch_system_v04.patch_system`, `PatchSpec`, `PatchControls`, `host_function`; `material_review_v05.ground_gradient` | Explicit monotone support A-like curve, independent patch geometry/ink, pigment support separate; actual terrain-support adapter absent |
| Interaction proof | `ground.interaction.Region`, `Corridor`, `plan`, `replacement_intervals`, `duplicate_coverage`; `vegetation.tree_occlusion_proof.masks` | Simple planar constant-rank original-path processing only; not an F2 reciprocal resolver |
| Full-scene source loader | `strokes.scene.load_selected_scene(master, veg, root, selection)` with `configs/scenes/seoul_spring_selected_C.json` | Reconstruct unchanged float64 ownership/source/mist fields; validates pinned auxiliary assets |
| Geometry mapping | `rendering.painterly_layers.load_features`; `rendering.ground_composition.render(..., physical=False)`; `composition.fields.mapped_source_coordinates`, `build_fields` | Exact F2 mapped triangle ownership and original source XYZ; mapped depth and source forward distance are different |
| Full baseline reproducer | `rendering.spring_baseline.run`; `rendering.foreground_interpolation_study.prepare` | Expensive reproduction only if needed; no tuning. Prefer loading canonical vectors and separately restoring required fields |

Canonical vectors SHA-256:
`22bace23f0ae34f69873a282fec15c25a431d0e998216d995b1ab14c3f85fab3`.
Production PNG: `e7a850407c67ba0c65c34fe29c4ac760d03e4579ef3d8a4b7034bd5796cc47b1`.
Physical pair: `de13922b7082921e05dc52abde579e005c0d4157929e3e651fffa54723aefd2d`.
These are read from the pinned baseline record, not re-generated in this Work.

## Assets, availability and precision

`integration_inputs.json` inventories required inherited assets and their Git blob IDs,
expected hashes where available, and availability in this consolidation checkout.
A normal full checkout of this stack inherits those repository assets. Several are
not materialized in this session's sparse reconstruction; that is not evidence that
they are missing from GitHub. No baseline asset is deleted or republished here.
The connector exposes the baseline gzip blob identity but did not return its binary
content, so its byte digest was not independently rechecked locally in this Work.
The next Work must hydrate it through Git and verify it before use.

External hash-matched files are still required for actual terrain placement:

- `SeoulNorth_v02_MASTER_30m.tif`, SHA-256
  `837f4b6b2e01e3b97b05db3e62fbd0869ce052ba4c18cc47a99d97873317f0fb`.
- `SeoulNorth_v02_VEG_10m.tif`, SHA-256
  `ac7f2d96af327f7b1ab07da14e379d0466500799420066484b29b45fbd5b47d5`.

Neither GeoTIFF nor an authoritative float64 F2 ownership/source cache is available
locally in this Work. The inherited `fields.npz` and `retention_snapshots.npz` are
validation/diagnostic archives; the exact loader recomputes float64. Do not treat
rounded float32/float16 fields as authoritative local depth or reconstruct terrain
from a PNG. `prepare` also needs pinned candidate vectors and its config/hash chain.
All nested loader checks must be satisfied, including inherited source/artwork,
representative tree, marks, image, palette and hardware records, even though this
Work does not change or execute those hardware settings.

Available once the original sources and inherited files are present: mapped
triangle ownership, original source XYZ in EPSG:32652, occupied masks, source forward
distance, source slope/aspect, NDVI/observation support, local/global reserves and
retention. The canonical vector schema contains finalized drawing paths/profiles;
it is not a persisted per-object terrain attachment/depth field. Existing scene
small marks/representative roots describe the old V context, not new P/B/U roots.

Missing integration metadata/logic: explicit sampled supporting surface and source
triangle/contact intervals for every new root/rock/Soil patch; bounded local depth
variation across object height and surfaces; visible object parts; occupied canopy
core/transition policy; reciprocal terrain/object resolution; brush calibration;
independent broader color support specs. No invented geological coordinates or
"real" rock size may be inferred from catalog mm or visual plausibility.

## Reproducible start

```bash
git fetch origin feat/rock-ground-v05-consolidated
git switch -c feat/spring-scene-integration-v01 origin/feat/rock-ground-v05-consolidated
git rev-parse HEAD  # record and pin the published Rock & Ground commit
python -m pip install -e '.[research,dev]' cairosvg
python -m pytest tests/test_rock_ground_catalog.py tests/test_rock_ground_v05.py \
  tests/test_rock_ground_patch_controls.py tests/test_rock_ground_consolidation.py -q
python -m datascape.rendering.rock_ground_catalog \
  --config configs/catalogs/rock_ground_v05.json --output outputs/catalog-input-check
```

Before any scene rendering, load and verify the unchanged archive:

```python
from pathlib import Path
import hashlib
from datascape.strokes.vector import read_vectors
p = Path('docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest() == '22bace23f0ae34f69873a282fec15c25a431d0e998216d995b1ab14c3f85fab3'
scene = read_vectors(p)
assert scene['continuous_mm'] == [600, 900] and scene['panel_width_mm'] == 300
assert scene['physical_gap_mm'] == 40
source_records = scene['strokes']  # immutable original A/B/C/D/V
```

When exact fields are available, restore them without solving new A geometry:

```python
import json
from datascape.strokes.scene import load_selected_scene
root = Path('.').resolve()
selection = json.loads((root/'configs/scenes/seoul_spring_selected_C.json').read_text())
fixed = load_selected_scene('/path/to/SeoulNorth_v02_MASTER_30m.tif',
                            '/path/to/SeoulNorth_v02_VEG_10m.tif', root, selection)
# fixed['terrain']: mapped mesh/ownership; fixed['base']: source xyz/depth fields
# fixed['retention'], fixed['refined']: unchanged retention/reserve evidence
```

The above field recovery is a next-Work command, not an executed validation here.
If full baseline regeneration is necessary, use the unchanged documented CLI:

```bash
python -m datascape.rendering.spring_baseline \
  /path/to/SeoulNorth_v02_MASTER_30m.tif /path/to/SeoulNorth_v02_VEG_10m.tif \
  --config configs/scenes/seoul_spring_provisional_baseline_v01.json \
  --output outputs/spring-baseline-check
```

## Source identity, material separation and OCC carry-forward

Never pass canonical scene records blindly through the catalog `family()` helper:
it recognizes catalog `A-like`/`C-like` metadata, not every canonical scene schema.
A future scene adapter must retain original `layer`, ID, path, profiles and provenance,
add an explicit derived `source_family` from the original layer, and use a separate
namespace such as `spring-integration-v01/tree/...`, `/rock/...`, `/soil/...` for new
objects. Preserve original V even if new trees are nearby; report duplication before
proposing derived omissions. Store `origin_kind=baseline/new-catalog`, baseline SHA,
source object/component ID, original source arc and reason on derived results.
Do not normalize IDs before the locked ID-keyed mist transfer or feed downstream
fragment IDs back into that transfer. Do not recursively clip finalized fragments.

Keep A/rock/Soil/tree structural ink, C-oriented color vectors and nonplotting broader
pigment supports separate. Ink patches may share ground context with larger/offset
color supports but need independent future extent/density specs; current pigment
supports remain unchanged. A/D/V duplication is an audit, not permission to redesign
baseline source geometry. C still participates in geometric/footprint interaction.

The unchanged [shared contract](../../design/object_occlusion_contract_v01.md) remains
the controlling unresolved specification:

| Gate | Next evidence; not solved by the local catalog |
| --- | --- |
| OCC-01 | Occupancy-based canopy cores suppress strong inner terrain without full white crown silhouettes |
| OCC-02 | Graduated transition entry/release, coherent original-arc omissions and final short-fragment audit |
| OCC-03 | Explicit real supporting surfaces, roots/contact protection and rock burial under unchanged mist |
| OCC-04 | Reciprocal local depth, nearer terrain hides objects, visible occluders only, no rear-object white holes |
| OCC-05 | A/C replace/reinforce ownership plus A/D/V/object duplicate coverage and C/Soil intersections |
| OCC-06 | Explicit bounded pictorial foreground/middle choices; all global reserves unchanged |
| OCC-07 | Both footprints, minimum paths, source-arc endpoint precision and later physical ink/pigment tests |
| OCC-08 | Corridors and blank intervals protected through object, Soil and color-support placement; no path/stream inference |

The existing simple rank consumer does not supply a terrain-varying per-part depth
provider. Root collars and canopy-touch envelopes remain technical proofs only.
The v05 C0 proposal is not automatically adopted. The observed arc-substring endpoint
precision issue must be tested before integration; no shared fix is claimed here.

## Recommended first integration checks

1. Verify baseline/config hashes and independent A/B/C/D/V source digests before and
   after a baseline-only 600 x 900 render. Confirm both panel origins and the physical
   gap view; preserve the bottom 2 mm omission and original global reserves.
2. Predeclare a few foreground/middle support sites with source triangle/XYZ/depth,
   local surface tangent, uncertainty and stable IDs. If evidence is unavailable,
   label output **compositional mock-up**, not integrated F2 placement; report missing
   inputs instead of inventing terrain or attachment.
3. Compare no objects / restrained / richer arrangements with exactly the same
   original scene paths. Native-mm object sizes and placement/depth are the changing
   variables. New objects are distinguishable from existing V and terrain features.
4. Use matched crossing/contact crops to audit both directions of visibility,
   hidden rear masks, trunk/core/transition/sparse regions, selected root support,
   burial, corridors, A/D/V duplicate coverage, and C/Soil footprints.
5. Export separate immutable sources, derived visible intervals, object ink,
   color-oriented C, nonplotting pigment support and a per-source decision ledger.
   Check deterministic traversal, minimum length and source profiles after clipping.
6. Review balance and foreground density with the artist. Report remaining weak A
   masses; do not rerun the A-density solver to compensate for object placement.

Stop at that first diagnostic checkpoint for visual review. An overlay, a clean
PNG or this catalog's synthetic clipping cannot close reciprocal masking, artistic
root attachment or physical plotting feasibility.
