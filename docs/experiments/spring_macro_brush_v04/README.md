# Spring v04: macro fields, selective A/D color and growth wash

Local diagnostic candidate for visual review only. No remote push, PR update,
merge, publication, hardware profile or G-code is included. The original F2-C
600 x 900 mm camera/DEM/mist arrays, A .25 baseline, B/D logic, Tree v10,
Rock & Ground v05 and the 20-slot HEX table remain byte-identical.

## Controlled comparisons

A uses one fixed ink set. B adds selective A/D terrain wash and geometric mist,
with the previous thin foliage method regenerated on this same ink. C keeps
exactly the same ink and terrain colors, replacing vegetation colors with
branch-supported growth gestures and longitudinal trunk paths. The v03 control
uses its original saved ink and vectors. Restrained/diagnostic modes differ only
in display alpha (x2.8, cap .83); they are not separate geometry experiments.
All 5,200 canonical legacy V records are excluded only from derived integration.

## Reference relationships translated into rules

- R1: Unequal dominant/subordinate groves become a left ascending macro field
  and a separate right rock-led counterflow. Member count, individual height,
  group extent and between-group links are separate controls.
- R2: Foreground rocks hide rear trunks while crowns emerge. The dominant native
  B formation is regenerated at 240 x 82 mm, with subordinate stones and rear
  tree ranks; actual visible vector arcs establish the relationship.
- R3: Two selected D mountain masses receive A-displaced color. D samples attach
  to occupied F2 contacts within 4.5 mm; a Gaussian field uses original source
  lateral/forward/elevation meters (sigma 125/185/72 m). It is not a screen halo.
- R4: Open intervals separate masses. Color mist changes actual carrier presence,
  unequal endpoint shortening and retention-contour clipping. Fully omitted
  retention <= .001 remains excluded. The canonical mist itself is unchanged.
- R5: Color follows actual leaf/branch supports and longitudinal paired trunk
  contours. Neither the reference silhouettes nor their brush textures are copied.

The five supplied reference images are private analytical inputs. They are not
added to the source repository. Historical Geumgangsan source is read-only;
its separate ink/color sampling supports a derivative design, not an exact
finished-artwork reconstruction or physical brush calibration.

## Scale, placement and visibility

There are still 79 trees and 22 rock masses/stones across 18 groups. Four small
relay groups redistribute existing members, preserving deliberate openings.
Maximum tree height remains 130 mm; no finished vector is scaled. The v10
acceptance specimens document 22/45/95/130 mm; the inherited native 20 mm floor
is below that specimen range and is explicitly a distant-representation limit.
The right dominant rock changes from 188 x 69 to 240 x 82 mm, within the approved
native catalog's tested 307 x 89 mm B scale. Tree/rock ordering and occupied-core
clipping use actual source q, with explicit rank only inside the inherited 25 m
uncertainty band. Root repair Soil stays selectively generated.

## Color and physical meaning

A remains the ink structure and supplies separate displaced terrain carriers.
Original C and its tangent field guide color flow. Foliage follows actual leaf
rays/branch paths, rocks follow bedding/fractures/spall, Soil follows host flow.
The active 12 slots and object-type priors remain fixed. Source-forward depth
modulates selection, discrete slot weights, intended width and display alpha.
No paper/background, canopy or terrain region is painted.

JSON stores open centerlines, profiles, source-q samples and complete raw ->
feathered -> visible arc provenance. Growth/trunk paths add explicit widening /
release width samples and normalized **uncalibrated** pressure intent. Raster
previews use continuous variable-width stroke footprints; these are appearance
previews, never plotter region fills. SVG exports open centerlines with mean
width, so they do not reproduce the JSON width envelopes or calibrated pressure.
No width-to-Z, pigment dilution, wet spread, paper or dry-opacity claim is made.

Length proportions are centerline statistics, not pigment consumption. D-focus
and adjacent-far comparisons share the same fixed > .23 retention domain;
actual generation uses > .08 with further local exclusions and geometric
feathering. A near/middle/far density sequence need not be monotone: the middle
C field remains locally dense, an unresolved pictorial issue.

## Reproduce

Apply `source.patch` from the review package to clean repository base
`f3a11745217a6ab976ac90819d5538462dae346b`. It includes restored v02/v03 additions
and v04 additions. Saved v03 outputs in the package are the fixed control.
The original TIFFs are required; hashes are in `record.json`. From repo root:

```bash
python -m pip install -e '.[research,dev]' pillow affine
# Copy the package control outputs to outputs/spring-diverse-vector-v03 first.
python -m datascape.rendering.spring_macro_study \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --references /path/to/private_references \
  --config configs/scenes/seoul_spring_macro_v04.json \
  --output outputs/spring-macro-brush-v04
pytest tests/test_spring_macro_v04.py tests/test_spring_diverse_v03.py \
  tests/test_spring_cluster_v02.py tests/test_spring_integration.py \
  tests/test_tree_final_scale_unit.py tests/test_tree_catalog_acceptance_unit.py \
  tests/test_rock_ground_v05.py tests/test_rock_ground_consolidation.py \
  tests/test_rock_ground_patch_controls.py
```

The report includes five sheets: full comparison; references/macro fields;
selective far A/D and mist; same-ink foliage/trunk comparisons; integrated
relationships. Exact source-arc, omitted-region, paired-support and fixed-input
checks accompany them. Remaining weaknesses include decorative parallel C
strokes, dense middle-field loops, heavy small-rock outlines and weak far canopy
aggregates. C is a provisional review candidate, not a replacement baseline.
