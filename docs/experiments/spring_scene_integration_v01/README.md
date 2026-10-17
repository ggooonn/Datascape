# Spring scene integration v01

First controlled scene diagnostic on the unchanged PR #16 F2-C / near A .25
source, using accepted Tree v10 and Rock & Ground v05. **Not ready for machine
YAML / G-code preparation.** The visible improvements do not establish finished
root attachment, a full 3D reciprocal resolver or physical plotting readiness.

Start: `6fcac2864e7b7fdd5ae626f8a8161c01e5c90994`,
`feat/rock-ground-v05-consolidated`. Integration branch:
`feat/spring-scene-integration-v01`. This is stacked work; do not merge PR #16,
#18, #19 or this checkpoint automatically. No existing catalog, scene source,
palette, hardware configuration or A-density implementation is changed.

## Review

- [A/B/C/D comparison](comparison.png): unchanged archived A; restrained B;
  richer C; spring color-ready D using C's identical visible vector geometry.
- [Matched structural-ink comparison](ink_comparison.png): A/B/C without C's
  color-support category. This additional control separates material display
  from object integration; archived A itself is not restyled or overwritten.
- [B structural ink](B_ink.png), [C structural ink](C_ink.png),
  [C spring color](C_color.png).
- [Foreground ink](C_foreground_ink.png) and [foreground color](C_foreground_color.png).
- [Actual-terrain canopy controls](canopy_controls.png): the same right-middle
  tree and original A paths, unmasked / v10 footprints / occupied-core proposal /
  excessive full-support control. These are vector deletions, not white polygons.
- [C / Soil / ownership](materials.png). The C-only display doubles diagnostic
  width and sets full preview opacity for inspection; source C is unchanged.
- [Detailed measured record](record.json), [validation](validation.json),
  [B sites](B_sites.json), [C sites](C_sites.json).

The continuous painting remains 600 x 900 mm. Source path x coordinates never
include the physical 40 mm gap. The reproducible full output includes a correctly
split 640 x 900 mm pair display. No content is deleted or stretched at x=300.

B has six new trees, two connected B rock groups (three major exposures each),
four regenerated subordinate stones and two Soil systems. C has ten trees,
four connected B groups (3/3/2/2 exposures), eight subordinate stones and four
Soil systems. Variants share IDs, seeds, geometry and policies for common objects.
No W experiment, optional large A mass or additional season is introduced.

## Findings

Occupied-core suppression improves the relevant canopy crossings over the v10
footprint proof while retaining substantially more A than the full-support
control. Sparse foliage and deliberate empty crown sectors do not automatically
own a filled silhouette. The central pictorial opening remains readable; its
bounded placement reserve is neither mapped water nor an inferred road.

Connected parent/child rock relations read more coherently than isolated symbols,
and the two large root/rock locations gain a definite contact. However, at the
selected physical sizes rock contours have much greater black weight than the
existing terrain. Some straight endings and sparse internal structural runs read
as pasted-on angular symbols. The catalog is preserved; this is an exposed scene
scale/material mismatch, not a claim that v05 grammar is finally integrated.

Several small trees lack strong retained A or new ground near the root. Additional
objects alone do not solve the foreground accordion rhythm. Local concentrations
improve near the two principal rock groups, but intervening terrain remains weak.
Do not increase global foreground A or rerun its solver to conceal this result.

Original V is immutable. Six / ten explicitly identified old root groups are
replaced only in the derived B / C result; every removed original interval is
recorded. Remaining V preserves the locked scene but visibly mixes the older
fine-stem grammar with the new catalog. Remaining V/tree footprint overlap is
reported rather than silently deleting the whole vegetation layer.

C remains useful as directional color support, not dominant black structure.
Soil remains local structural ground ink with separate ownership and nonplotting
pigment intent. Exact C/Soil and A/Soil assumed-footprint intersections are in the
record; absence of overlap under these widths is not a wet-material guarantee.
B directions and D's mountain accents remain legible; no new object occupies
those mountain accents in this selected placement.

## Color provenance and assumptions

The byte-identical `configs/palettes/palette_20.yaml` supplies all assigned hex
values. `configs/substrates/four_seasons.yaml` supplies spring paper `#F8F8F5`.
The original seasonal intent is in
`docs/experiments/spring_production_v01/stroke_and_color_design.md`: spring C1/C2
with D1/A3 support, all 20 slots available rather than a new seasonal palette.

Broad tree support uses C1 `#E1ECB8` for P/U and C2 `#98C245` for B; small Soil
pigment intent uses D1 `#F5D647`. Existing C geometry receives stable regional
slot assignments on 220 m source-UTM cells using the full recorded 20-slot bias;
A3 `#8E9FA9` is a cool support. These newly declared display weights are conservative
integration assumptions, not a previously accepted pigment distribution. C2's
broad display weight is lower than C1's. All alpha values are display-only.

Ink-only omits C from black display while retaining structural A/B/D/V and new
object/Soil ink. Scene comparison B/C keeps the inherited faint C display for
fair comparison with archived A. Color-ready changes only material display and
adds separately exported nonplotting wash intent. It does not simulate pigment
transport, opacity, dry colors, hardware calibration or an executable fill.

## Actual placement and bounded visibility

Original MASTER/VEG TIFFs are hash-validated by the unchanged selected-scene loader.
Its exact F2 source image, ownership and float64 70/30 retention checks pass.
The new contact adapter uses the final owning mapped triangle and barycentric
source XYZ in EPSG:32652. Existing tree roots reproduce their original forward
source coordinates; the objects are authored, not observations of actual trees
or rocks. Depth ownership in F2 projection remains distinct from source forward
meters.

A short A fragment is never extrapolated to manufacture a rock host. If a long
nearby original A arc is unavailable, the nonplotting host follows a section of
the visible source-q terrain surface. It is exported in the site metadata and
never inserted into baseline A. Soil patch ownership does not fill an open
corridor or an original hard reserve. Root/rock host offsets are reported.

Objects use an explicitly limited upright 2.5D sheet: exact contact q plus the
support triangle's lateral q derivative, bounded to +/-35 m. There is no invented
world-height conversion for a canopy or rock. A 25 m uncertainty band retains
unresolved cross-object contacts. Within a declared local group, tree-over-rock,
rock-over-Soil and inherited B mass ordinal ranks resolve contact ties; those
ordinal choices are not fabricated source meters. Real leaning branches,
overhangs and independently nearer surfaces remain unresolved.

Visible solid parts are resolved first, actual visible object ink rebuilds the
canopy occupancy, and original terrain is clipped once against those visible
parts. Hidden rear parts cannot independently create terrain holes. Occupancy
uses retained ink area on a one-mm field, Gaussian sigma 1.3-3.2 mm, absolute
core/transition thresholds, source-ID-keyed coherent interval decisions and real
vector shortening. It does not use a whole-crown hull or a wash mask.

Both footprints, a .15 mm edge allowance and an explicit 1 mm raster/decision
sampling guard enter exclusion. These conservative guards remain uncalibrated.
New paths below 2.8 mm after all catalog rounding/clipping are dropped; original
baseline short paths remain identified. Original arc endpoints are retained
without rounding them back into a cut. Width, opacity and intensity arrays are
interpolated to the final vertices. Source IDs and ancestor metadata survive;
no derived ID is fed back into the locked mist transfer.

## Reproduction

From the repository root, with the original hash-matched TIFFs:

```bash
python -m pip install -e '.[research,dev]' pillow affine
python -m datascape.rendering.spring_integration \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --config configs/scenes/seoul_spring_integration_v01.json \
  --output outputs/spring-integration-v01
python -m datascape.integration.validation \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --config configs/scenes/seoul_spring_integration_v01.json \
  --output outputs/spring-integration-v01
python -m pytest tests/test_spring_integration.py \
  tests/test_tree_catalog_acceptance_unit.py tests/test_tree_final_scale_unit.py \
  tests/test_rock_ground_v05.py tests/test_rock_ground_patch_controls.py \
  tests/test_rock_ground_consolidation.py -q
```

No authoritative float16/float32 diagnostic cache is substituted for source TIFFs.
The CLI restores exact fields; no private pickle cache is distributed or needed.
The full checkout of the pinned stack supplies inherited auxiliary assets. The
canonical source gzip SHA-256 is
`22bace23f0ae34f69873a282fec15c25a431d0e998216d995b1ab14c3f85fab3`.
The two TIFF hashes are pinned in the unchanged selected-scene configuration and
copied into `record.json`; they are external inputs, not committed here.

`B_vectors.json.gz` / `C_vectors.json.gz` contain visible structural and color
categories. The matching `*_sources_and_ledger.json.gz` files retain all new
sources, immutable baseline reference, original kept/removed intervals, reasons
and short-path losses. Wash GeoJSON and site metadata are nonplotting canvas-mm
supports, not geographical GeoJSON. The full local output also regenerates all
individual controls, full scenes, C-only / Soil-only images and physical pair.

## Next scene decisions

Review B as the lower-population starting point. Choose a small number of
foreground root/ground relationships, check remaining V ownership, then compare
rock/terrain visual weight at the same physical scale. Keep the large white
passages and the locked baseline. The richer C result is a diagnostic upper
population, not an accepted upgrade. All OCC-01 through OCC-08 remain explicit
review gates; physical validation cannot be inferred from this draft checkpoint.

The resolved Soil channel is especially weak: B retains only one path / 7.546 mm,
C three paths / 37.510 mm after contact/solid visibility. This explains why simply
adding Soil ownership does not reinforce the intended foreground masses. C/Soil
separation remains meaningful, but useful Soil coverage is not achieved. Local
support extent/contact decisions require the next visual pass; this checkpoint
does not quietly increase density to hide the loss.

Validation run: **36 tests passed, plus 16 accepted-tree reference subtests**.
The additional real-scene validator checks every exported vertex/profile and
original source-arc geometry, length conservation, canvas/bottom guards, final
new-path minimums and reversed object-construction traversal. Its separate
footprint probe uses the same original object sources and resolved masks at the
nominal widths and widths increased by .30 mm; it does not measure wet ink.
