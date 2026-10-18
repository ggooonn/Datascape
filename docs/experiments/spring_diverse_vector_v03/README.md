# Spring v03: diverse integration and separate A/C color carriers

This is a local, bounded diagnostic study, based on local v02 commit
`9d733d8348ae47023ae8041b55424ef708cb368e`. No publication or merge is authorized.
The v02 source, configuration and outputs are the fixed control.

## Locked inputs and boundary

The original 600 x 900 mm F2-C composition, camera/projection/DEM, A .25
foreground baseline, B/D behavior, 70/30 retention and mist fields are unchanged.
Canonical A/B/C/D/V arrays remain immutable. All 5,200 legacy V placements are
excluded from the derived scene. New objects call Tree Catalog v10 and Rock &
Ground v05 without changing those modules. Local clipping creates new visible
fragments linked to exact source arc intervals; it does not rewrite terrain.

## Diagnosis of v02

- Six sites use the same member list and obligatory rock/Soil companions.
  Counts change, but the tree/rock hierarchy repeats.
- The last site is near source q 2.18 km. Mountain shoulders beyond it receive
  little catalog content; source-forward depth and geographic evidence are
  different from a placement prescription.
- Terrain wash generation loops over C supports only. There is no A carrier.
- C availability, stochastic selection, a .36 far-density multiplier, one or
  two passes, short accents and clipped support all reduce visible color.
  Display alpha .28 to .12 further weakens inspection, but is not the only cause.
- Object wash is a globally oriented row field clipped to occupancy. It does
  not use actual branch, leaf-ray or fracture carrier directions.
- A missing near-left serial root support occurs where original A has no
  surviving ground and the inherited Soil does not reach the exposed root.

## Historical Geumgangsan audit

Read, do not import/execute or modify:
`artworks/2026-03-17_geumgang/original/source.py`, preserved V39.10 notebook cells.
The existing source manifest considers its final-production identity provisional.

Lines 214-239 sample light ink from `curr_y = 0`, adaptive terrain-height gaps,
and a noise-dependent rugged y. Lines 241-276 sample color independently from
`curr_y = 5`, a different row-gap formula, depth-weighted discrete color choices,
and noise-based contact omission. Both use the same accordion x projection.
The color y uses DEM without the light-ink rugged-y noise term.

This supports independent terrain-informed color sampling and phase differences.
It is not a reusable, bounded local xy-displacement function. Unseeded random
calls, synthetic DEM fallback, missing historical raw data and hardware contact
values prevent a faithful finished-artwork reproduction. The v03 method below
is a documented derivative, not a claim of exact restoration. No historical
projection, horizon reset, brush Z, station or G-code settings are imported.

## New integration modules

`integration/diverse_scene.py` builds 14 authored relationships: a foreground
primary grove, a separate dominant connected rock exposure with rear vegetation,
rock-only groups, vegetation-only groups, a mixed contact group, two extended
middle belts and three selected distant canopy aggregates. Entire categories
may be absent. Individual native dimensions, uneven offsets, vigor/stem/posture
and root-centered rigid poses replace the repeated member template.

Source-q contacts and actual A/F2 support sections inform attachment. Locations,
relationships and apparent growth are pictorial interpretation; NDVI is not a
species map, and a catalog rock is not surveyed geology. At v10's native 20-mm
height floor, distance representation selects exact canopy marks and omits
most individual body detail. It does not scale complete glyphs smaller or
artificially enlarge a distant icon. This floor remains a limitation.

Reciprocal tree/rock ordering uses actual source q, plus explicit local ranks
only inside the existing 25-m uncertainty band. Strong body/occupied-core
suppression and selective soft transitions are retained. Local exposed roots
without nearby ground receive a native Soil repair; concealed roots/aggregate
crowns do not automatically trigger it. Raster support-relative 2.5D decisions
are not certified volumetric branch/overhang geometry.

`integration/diverse_color.py` separates:

1. Visible A references, independently selected episodes, local tangent/normal
   displacement bounded by nearby A spacing and a 9-degree displacement-derivative
   bound. Original ink and its identity are not moved. Color has its own IDs,
   stored carrier geometry, visible-source references and arc clipping.
2. Original C supports with independently selected offset passes, plus an
   extended field interpolating eight nearby C/B tangents. Undirected line-field
   interpolation and integration inertia avoid nearest-neighbor corners. Physical
   path selection decreases continuously with actual source q.
3. Material paths following retained foliage rays and actual branch origins,
   rock bedding/fracture/spall carriers, and broader shared Soil host flow.
   No canopy, rock or ground support polygon is painted.
4. The unchanged 12-active-slot palette, material priors and source-q palette
   modulation. A perceived transition uses discrete slots, not new hex values.

Controls live in `configs/scenes/seoul_spring_diverse_v03.json`. Case 1 fixes one
ink vector set. Cases 2 and 3 use it exactly; they also share the exact A/C colors.
Only material color layering differs. A coincident A control is shown in crops,
not as an additional full-scene experiment. Diagnostic visibility multiplies
existing color alpha by 2.8 (cap .83); restrained display retains v02 alpha policy.
No density, path, slot or width changes between these display modes.

## Reproduce

The original TIFFs are required and verified by the unchanged F2 loader:

```bash
python -m pip install -e '.[research,dev]' pillow affine
python -m datascape.rendering.spring_diverse_study \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --config configs/scenes/seoul_spring_diverse_v03.json \
  --output outputs/spring-diverse-vector-v03
pytest tests/test_spring_diverse_v03.py tests/test_spring_cluster_v02.py \
  tests/test_spring_integration.py tests/test_tree_final_scale_unit.py \
  tests/test_tree_catalog_acceptance_unit.py tests/test_rock_ground_v05.py \
  tests/test_rock_ground_consolidation.py tests/test_rock_ground_patch_controls.py
```

The fixed v02 control outputs must be present at
`outputs/spring-cluster-vector-v02`; regenerate them with the v02 entry point
and the same TIFFs if necessary. Results default to a new output directory.

The five sheets show full matched compositions, actual A/C crops, six actual
composition roles, material/depth views, and contact/mask/whitespace diagnostics.
JSON stores full carrier geometry/profiles/source arcs; SVG has independent A,
C and material groups with slot/source attributes. CSV reports actual discrete
palette use and physical placements.

Coverage is final centerline length split at actual source-q bands (near <1 km,
middle 1-2.2 km, far >=2.2 km). A path crossing a band counts in each. The common
comparison denominator is the unchanged one-mm occupied F2 terrain, retention
>.23, excluding global reserves and authored protected corridors. Only actual
terrain-color length inside this common domain is used for normalized control
comparison. Material paths have separate statistics; their canopy length is
not presented as painted terrain area. New object exclusions also define a
stricter v03 generation domain. These are reproducible centerline/raster proxies,
not wet coverage, measured pigment consumption, dilution or dry saturation.

Review stops at Spring visual integration. No rivers/roads, calligraphy, other
seasons, hardware settings, production G-code or pigment calibration are added.

## Bounded review result

The final comparison contains 79 authored trees, 22 rock exposures/stones and
17 Soil objects (including 10 selective exposed-root repairs). There are 14
unequal relationship groups, not 14 copies of one mixed cluster. All 79 root
sites pass the 7-mm/2-mm-nearby-ground centerline proxy; this does not certify
artistic attachment. Legacy V is absent and sampled terrain/color has no hard
body intrusion after clipping.

Case 2 has 4,753 color paths / 81.28 m. Case 3 has 5,014 / 84.04 m, comprising
23.32 m of displaced A, 53.07 m of C-guided terrain and 7.65 m of material
supports. Both use the same ink and A/C vectors. The v02 control has 1,384 color
paths / 21.82 m. Under the common terrain-domain measure, near/middle/far
terrain-color density changes from .058/.035/.011 to .246/.248/.191 mm/mm2.
These are centerline proxies, not opacity or physical wet coverage.

The visible A-to-color sampled median centerline separation is .63 mm; 90.7%
of the color samples are more than .25 mm from an A centerline, versus 0% for
the coincident control. The sampled nearest-line method has .2-mm A and .3-mm
color discretization; it is not a brush-edge or pigment-clearance guarantee.

The most convincing changes are the asymmetric grove, the separate rock-led
foreground relationship, branch-directed foliage color and the two middle
belts. The central-left C curves still dominate some terrain passages, small
rock contours remain heavy, and far canopy aggregates are understated. Actual
C1/C2 use is about 42.0%, below the 50% baseline target; A3/A5 together reach
about 41.6%, so the cooler/gray family remains overrepresented. Case 3 is a
provisional visual-review candidate, not a final accepted or production scene.
