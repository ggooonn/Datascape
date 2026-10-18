# Spring clustered placement and vector wash v02 — local diagnostic

Local continuation of `f3a11745217a6ab976ac90819d5538462dae346b` / PR #20.
**No remote branch, PR update, publication or merge is authorized or performed.**
This is a scene-adjustment diagnostic, not production approval.

## Controlled comparisons

| Output | Placement | Color logic |
| --- | --- | --- |
| 01_clean | Six sparse serial clusters: 18 trees, 24 rock exposures/stones, 6 Soil systems | Restrained open-vector wash |
| 02_clustered | Six developed clusters: 31 trees, 36 rock exposures/stones, 6 Soil systems | Same restrained policy |
| 03_layered | Identical ink and placement to 02 | More carrier concentration and a second oblique cross-layer |

Original V placement: all **5,200** baseline V paths are excluded from each
derived scene, with explicit omission ledgers. No v01 placeholder or legacy
glyph is reused as new scene vegetation. The immutable original V dataset and
its visibility logic remain available. Original A/B/C/D/V sources, F2 camera,
DEM, 70/30 retention, mist framework, near-A .25 baseline, palette definitions,
Tree v10 and Rock & Ground v05 source files remain unchanged.

A remains structural ink. Existing C paths supply terrain color carriers; new
C-like carriers serve vegetation, rock and Soil independently of their ink.
There is no filled color region or background paint. The white display canvas
represents unfilled paper. Nonplotting ownership geometry only bounds paths;
it is never rendered as a flat pigment fill.

## Placement and interaction

The six authored sites form a foreground/middle/upper sequence on actual F2
support. Unequal native physical sizes range from 22 to 130 mm. A large anchor,
rear companion, smaller front support and serial/edge members create local
concentrations and releases, rather than a uniform random point distribution.
Major and subordinate rocks share formation parents, with regenerated smaller
stones rather than scaled copies of finished detail. All contacts retain exact
source-triangle/XYZ/q evidence; these are authored objects, not observed trees
or geological classifications.

Native tree catalog seeds have a directional bias; seed selection is not claimed
to reverse it. Complete tree geometry and mask metadata receive a bounded rigid
root-centered placement rotation (at most 25 degrees) toward a left/right/vertical
axis target. Intrinsic path lengths and catalog anatomy are preserved before the
existing vector serialization; original native catalog signatures are recorded
separately from posed vectors. No per-leaf or skeleton redesign is performed.

Occupied-core occlusion remains preferred: opaque bodies exclude background,
retained-ink occupancy builds stronger local cores, transitions make coherent
interval cuts and outer foliage retains more terrain. Visible-object masks are
rebuilt after object visibility, not painted as white silhouettes. Local group
contact ordering resolves selected ties. Upright 2.5D tree/rock depth remains a
bounded diagnostic; it is not a branch/overhang volume reconstruction.

A v01 integration-specific Soil failure is corrected: ground texture now samples
actual visible F2 surface depth at XY, rather than inheriting an upright root
sheet. The accepted patch generator and v05 contact gradient remain unchanged.
Root contacts and the nearest real C tangent influence local Soil flow. Only
surviving Soil ink gets a narrow duplicate-clearance strip; an entire ownership
patch no longer erases A/C while most of its Soil strokes are hidden.

## Vector wash and palette

Every color item is an open centerline path with palette slot, source lineage,
object family, depth proxy, width/alpha profiles and channel metadata. A second
pass crosses the first by 37 degrees. Stronger areas emerge from more vectors
and overlap, not from increasing an opaque area fill. Ink is drawn first and
remains visible through/between low-opacity color vectors. SVG/PNG color display
uses one continuous stroke per carrier at its mean width/alpha, preventing
artificial alpha accumulation at stored segment joints. Detailed profiles remain
in the vector records for later backend decisions, without a calibration claim.

The unchanged `configs/palettes/palette_20.yaml` supplies every hex value. Twelve
slots are active; all 20 assigned stations remain defined. Proposed percentages
are approximate **final color-centerline length**, not pigment volume or measured
coverage. Object priors are blended with the global Spring target, then modified
continuously by source forward distance.

| Role | Slots | Target share |
| --- | --- | ---: |
| Primary Spring | C1 28%, C2 22% | 50% |
| Support | A5 10%, A3 10%, A4 6%, D1 7% | 33% |
| Secondary greens | C3 6%, C4 4% | 10% |
| Limited accents | D4 3%, D5 2%, B2 1%, B4 1% | 7% |

Vegetation favors C1/C2 with A5 and limited deeper green; rock favors A3/A4/A5
with short earth/blue accents; Soil favors A4/D1 with restrained earth. Terrain
carriers bridge these roles. A1/A2/B1/B3/B5/C5/D2/D3 are inactive in this pass.
Accents are bounded to short carrier episodes rather than broad purple/earth
crown areas. Realized slot/type/depth proportions are reported in `record.json`.

Source q from 250 to 2,550 m continuously reduces carrier density 1 to .36,
base width 1.70 to .85 mm and display alpha .28 to .12; cool A3/A5 weights rise
while stronger green/warm roles recede. Taper and terrain role reduce realized
mean widths further. Alpha expresses a display intention, not calibrated dilution.
The equal-physical-size depth crop sheet shows actual near/middle/upper locations.

## Findings and remaining decisions

Cluster relations and size hierarchy are clearer after complete legacy removal.
The two main root/rock assemblies read as local groups, with smaller serial
support toward their edges. Soil survives as roughly .9 m of structural ink,
rather than the few residual paths in v01. A 7 mm root-neighborhood audit finds
supporting ground for 30 of 31 developed trees; the near-left serial-edge contact
remains unresolved. This is a geometric support check, not artistic attachment
certification.

03 demonstrates the requested overlap/concentration direction more clearly;
02 provides the quieter comparison. Some canopy color rows still read as parallel
hatching. Rock contours remain heavy relative to terrain, and the repeated cluster
template can read as six islands. These are explicit next review points, not
reasons to reopen the locked camera or globally densify A. A5 is more frequent
and C3/D5 less frequent than the proposed target; review realized ratios before
forcing a quota. Limited cool distant color is intentional, but its strength
remains a pictorial choice.

## Reproduce from the pinned parent

The package includes a patch containing only new source/config/tests/docs against
the pinned parent, not the existing repository or external TIFFs. Apply on a separate
local checkout. Do not merge or publish the accepted parent PRs to reproduce.

```bash
git switch -c work/spring-cluster-vector-wash-v02 f3a11745217a6ab976ac90819d5538462dae346b
git apply /path/to/source.patch
python -m pip install -e '.[research,dev]' pillow affine
python -m datascape.rendering.spring_cluster_study \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --config configs/scenes/seoul_spring_clusters_v02.json \
  --output outputs/spring-cluster-vector-v02
python -m datascape.integration.cluster_validation \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --output outputs/spring-cluster-vector-v02
python -m pytest tests/test_spring_cluster_v02.py tests/test_spring_integration.py \
  tests/test_tree_catalog_acceptance_unit.py tests/test_tree_final_scale_unit.py \
  tests/test_rock_ground_v05.py tests/test_rock_ground_patch_controls.py \
  tests/test_rock_ground_consolidation.py -q
```

MASTER SHA-256:
`837f4b6b2e01e3b97b05db3e62fbd0869ce052ba4c18cc47a99d97873317f0fb`.
VEG SHA-256:
`ac7f2d96af327f7b1ab07da14e379d0466500799420066484b29b45fbd5b47d5`.
Canonical vector gzip SHA-256:
`22bace23f0ae34f69873a282fec15c25a431d0e998216d995b1ab14c3f85fab3`.
No approximate field cache is required or distributed. The exact existing loader
checks input hashes, the F2 image and float64 70/30 retention reproduction.

The result folder includes 3 scene PNGs, ink/color-only views, equal-scale depth
crops, a 640 x 900 mm pair display with a 40 mm gap inserted only for viewing,
open-vector SVGs, visible vectors, all new sources, omission ledgers, exact sites,
configuration, actual palette metrics and validation evidence. The continuous
600 x 900 mm coordinate frame and x=300 split remain unchanged.

Validation: 43 tests and 16 accepted-tree reference subtests passed. The v02 tests
were rechecked after the continuous-color display correction. Real-scene checks
confirm source-arc geometry, profile alignment, ledger length conservation, complete
legacy exclusion, original source-field hashes, 2.8 mm new path minimums, and equal
ink/color geometry and palette after reversed cluster traversal. SVGs contain open
strokes only. No machine YAML, G-code, pressure or pigment calibration is produced.
