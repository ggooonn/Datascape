# Shared object occlusion contract — proposed v0.1

Status: **requirements recorded; implementation and pictorial acceptance pending**.
Review date: 2026-10-17. Source checkpoint: tree catalog v10, commit
`04bbc9364ef534037a55b2c64856ea9f0a07f972`.
This is a locally retained archival checkpoint, not a published GitHub
dependency. The consolidated review manifest pins the retained runtime bytes.

The artist accepts the v10 tree grammar as provisionally complete. This does
**not** accept the v10 selective masking proof as a finished pictorial solution.
It leaves too many strong background terrain strokes inside the canopy. Neither
uncontrolled crossings nor full canopy-support blank silhouettes are acceptable.
This document records a future shared contract; it does not implement a solver,
change a generator, or approve numerical mask settings.

Historical evidence remains unchanged:

- [v10 implementation audit](../catalogs/tree_v10/OCCLUSION_AUDIT.md)
- [v10 catalog decisions](../catalogs/tree_v10/README.md)
- [Next rock/soil catalog handoff](../experiments/rock_soil_catalog_handoff_v01/README.md)

## 1. Required regional behavior

All exclusions apply only where the receiving stroke is behind the **visible**
occluder. A nearer rock or terrain surface can instead hide tree ink. Region
strength never overrides this depth condition or the locked global reserves.

| Semantic region | Required vector behavior | Limits / open decisions |
| --- | --- | --- |
| Visible trunk / major branches | Strong exclusion through the body interior and its footprint-safe boundary; preserve body continuity | Use both stroke footprints and edge tolerance, not contour centerline intersection alone. Respect paired-to-single body transitions. |
| Canopy core | Substantial suppression over locally occupied grouped-pad masses, extending beyond exact leaf-touch footprints | v10's per-touch buffers and occasional per-unit hulls are insufficient. Use local occupancy and pad density; do not fill every pad or bridge deliberate large gaps. Influence reach and strength remain artistically unaccepted. |
| Canopy transition | Permit terrain to enter, then progressively reduce it through selective omission, shortening and controlled release | Use coherent path intervals and end release; avoid binary pad-edge cutoffs, comb-like fragments and broad empty silhouettes. Transition width, rhythm and surviving paths require comparison. |
| Outer canopy / sparse foliage | Retain more background structure and the V02 directional foliage pattern | Sparse or omitted pads must not inherit a dense core solely from their support polygon. No automatic opaque halo. |
| Roots / ground contact | Preserve explicitly selected supporting rock/ground strokes and contact cues | A blanket root collar is not attachment. Supporting strokes must agree with depth and cannot silently cross an opaque trunk body. |
| Visible foreground rock mass | Strong exclusion behind the visible opaque mass, with physical edge safety | Opacity is a semantic property of the mass, not a filled rendering or a requirement to plot its interior. Exposed and broken surfaces are not automatically opaque objects. |

Tree and rock adapters supply these regions to one consumer. Their geometry
need not be identical: a tree core is occupancy-dependent, whereas a foreground
rock body may provide a continuous opaque area. Soil texture usually supplies
surface marks and replacement/reinforcement intent, not a canopy-like occluder.

## 2. Shared exchange records

The following fields define proposed responsibilities, **not an implemented
Python API or validated serialization schema**. Polygon envelopes / influence
supports are nonplotter geometry; the ink records remain open vector paths.

| Record | Required information |
| --- | --- |
| Object identity | Stable `object_id`, catalog/version, structural form, geometry revision, seed and component IDs; object class tree / opaque rock mass / exposed bedrock / soil-ground interface |
| Terrain-relative depth | Terrain sample/surface reference, coordinate system, local source forward-depth provider, terrain-relative offset and uncertainty; mapped surface-ownership reference where applicable |
| Visible geometry | Visible component/ink fragments, resolved body boundary, canopy unit and pad ownership/occupancy, explicit omitted sectors, root/contact components, visibility revision |
| Stroke identity | Stable `stroke_id`, `source_stroke_id`, owning object or terrain layer, original arc-length coordinates, current surviving source intervals, geometry revision |
| Physical envelope | Physical mm units, assumed/measured footprint model for both occluder and receiving stroke, width/calibration revision, registration and edge safety margins; do not buffer a footprint twice |
| Region policy | Region ID and semantic role, hard-exclusion geometry, core influence support, transition support, sparse/open exclusions, influence bounds, omission/shortening/release policy and priority |
| Contact protection | Explicit supporting stroke IDs **and source intervals**, contact point/surface/depth, protected extent and reason; ambiguity/conflict status |
| Pictorial choice | Explicit per-object/group role or override, its bounded local scope, suppression/release intent, seed/policy revision and review status; independent of tree family |
| Texture relationship | `replace`, `reinforce` or `independent` role, referenced A/C source IDs/intervals, surface ownership and duplicate-coverage policy; unresolved references are reported, not guessed |
| Open corridor relationship | Stable corridor/reserve ID, bounded support or opening, terrain/depth relation, evidence/uncertainty and allowed edge/contact intervals; keep this pictorial space-preservation reason separate from physical depth occlusion |
| Result / audit | Kept/deleted source intervals and reasons, deterministic fragment IDs, effective local depth decisions, shortened/dropped lengths, minimum-length failures and unresolved conflicts |

Catalog fixtures may use a declared synthetic depth provider. They must never
silently convert screen mm into geographic depth or claim DEM attachment.
Unknown depth remains unknown; integration cannot certify occlusion using
whole-object draw order or an unqualified constant root depth. Preserve F2
mapped-depth ownership separately from the source forward-distance basis.

Footprint sources must state whether an envelope describes a body boundary,
ink centerline, or already-buffered ink. In a constant-width illustration,
clearance between ink centerlines includes half of each footprint plus the
additional edge margin. Variable wet footprints need a calibrated envelope;
the v10 0.8/0.6 mm widths, 0.15 mm margin and 2.8 mm fragment minimum remain
synthetic assumptions, not inherited production defaults.

## 3. Geometry influence versus pictorial choice

Canopy occupancy should come from visible retained foliage, grouped-pad
organization, known open sectors and local physical coverage. Touch count alone
is not sufficient: overlapping touches, different lengths and scale can produce
different occupied areas. Normalize any occupancy estimate to a declared local
support area and report its kernel/reach in physical units.

A proposed influence field may combine occupied units into a stronger local
core and a limited shoulder. Its value controls **vector decisions**, not raster
alpha. It must not grow through deliberate pad omissions merely because two
canopies' convex hulls overlap. The best support radius, connection limits and
core/transition thresholds remain experiments, not fixed requirements here.

Keep a separate pictorial policy over this geometry:

- Selected foreground / important trees may suppress surrounding background
  more strongly and release it into local whitespace or the existing mist.
- Small middle-ground groups may preserve more background terrain continuity.
- These are explicit composition choices for an object/group, not automatic
  deductions from P/B/U/W, canopy size, depth or density alone.
- Additional local pictorial omission must have a bounded scope and its own
  provenance. It is not a change to global F2 mist, whitespace or retention;
  it cannot restore ink inside an existing global reserve.

Policy values and presets are intentionally unspecified until reviewed.
Core suppression must be stronger than the v10 technical proof in relevant
cases, but no uniform deletion percentage or opaque-pad rule is approved.

Open pictorial corridors are additional bounded space-preservation intent,
not occluding solid objects or evidence of a stream/path. Object placement and
soil/A/C replacement proposals must respect their openings and declared edge
exceptions. Never fill a reserved opening merely to satisfy a local density
budget. This remains separate from, and cannot alter, locked global F2 reserves.

## 4. Proposed deterministic vector processing

1. Read the unchanged scene depth/ownership and locked global reserves. Keep
   accepted terrain and object sources immutable; use derived review outputs.
2. Resolve visible portions of trees, rocks and terrain by local depth. Handle
   partial component visibility and uncertainty, not only far-to-near sorting.
3. Derive exclusion/influence regions from visible portions only. Hidden rear
   objects must not independently erase foreground terrain or create white holes.
4. Evaluate hard exclusions, occupancy-dependent core suppression and bounded
   transition release on original stroke arc coordinates. Apply the explicit
   pictorial policy without modifying the shared mist/retention fields.
5. Preserve compatible supporting-ground intervals. If protection conflicts
   with an opaque body, keep only the depth-valid outside/contact portions or
   report the conflict. A truly nearer support can occlude tree ink instead;
   a preservation tag does not override physical depth.
6. Convert the decisions to actual kept intervals. Prefer coherent end
   shortening or omission of a low-priority run over repeated tiny gaps.
   A transition field alone is not a plotting result.
7. Apply calibrated minimum run and gap rules after all clipping and again
   after simplification/rounding. Drop, retract or report unsuitable fragments;
   never reconnect across a hard exclusion or protected global reserve to meet
   a minimum length. Avoid repeated clipping of already clipped fragments.
8. Export separate terrain ink, object ink, optional material-expression intent
   and pigment/wash support. Record the full lineage and unresolved decisions.

Stable decisions must use source identity, original arc coordinates, a fixed
seed and versioned policy, rather than input list order or generated fragment
indices. Combining multiple occluders must use a stable policy/interval union,
so a different object traversal order does not reroll omissions or multiply
fragmentation. Cache by geometry, visibility, depth, footprint and policy
revisions; changing posture, damage or canopy occupancy invalidates the cache.

Preserve original proposal IDs through the existing mist transfer. New downstream
fragment IDs must never be fed back to reroll its identity-keyed decisions.
Interpolate inherited width/pressure intent along original source arcs when
splitting; copied arrays with obsolete vertex counts are not valid profiles.

## 5. Separate vector omission and material treatment

The base result is a deterministic binary vector plan: keep, shorten or delete.
Optional later pressure/ink/color treatment is a separate calibrated layer on
the surviving paths. Neither a low digital opacity nor a thin nominal preview
profile is evidence that a brush can fade the same way. Wash halos do not define
opaque cores and must not repair inadequate structural occlusion by assumption.

The production sequence terrain ink → vegetation/object ink → pigment/wash
requires the terrain ink plan to be finalized before its first plotted mark.
Later object ink cannot remove earlier ink. Drying, pigment-over-ink behavior,
paper absorption, wet edge spread and registration remain physical tests.

## 6. Open requirements and completion gates

| ID | Unresolved requirement | Next evidence / gate |
| --- | --- | --- |
| OCC-01 | Inner-canopy terrain remains too strong in v10 | Compare occupancy/pad-core influence against v10 and full-support controls; accept black-vector core readability without blank silhouettes |
| OCC-02 | Transition release rhythm and fragmentation | Matched synthetic crossings; inspect entry, shortening, end release, retained terrain continuity and final short fragments |
| OCC-03 | Root-to-ground/rock attachment and selected ground visibility | Catalog contact examples first; final acceptance only against actual support surfaces, depth and unchanged scene mist |
| OCC-04 | Shared tree/rock depth and visible-object masks | One common exchange contract; later scene resolver must handle nearer terrain, partial objects and overlapping crowns/masses |
| OCC-05 | A/C replacement versus reinforcement | Explicit source ownership/intervals and duplicate-coverage checks; no edits to the accepted baseline |
| OCC-06 | Object/group pictorial exceptions | Review explicit foreground-emphasis and middle-group policies; demonstrate unchanged global reserves |
| OCC-07 | Brush footprint, minimum paths and material sequencing | Physical calibration before plotting approval; source path counts or PNG appearance cannot close this requirement |
| OCC-08 | Open pictorial corridors and evidence limits | Preserve openings through object/texture proposals; test negative space and minimal boundaries first, without inferring water or footpaths from DEM valleys |

Rock/soil **grammar** may proceed before these are resolved. Its provisional
acceptance requires reusable object strokes and declared interaction intent,
not a completed scene solver. Full reciprocal masking, placement, selected
ground support and physical validation belong to the later scene-integration
gate after rock/soil grammar acceptance. No item above is marked solved here.
