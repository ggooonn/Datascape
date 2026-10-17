# Terrain–vegetation visibility audit

Scope: source inspection plus one synthetic vector proof. The accepted F2-C
scene, PR #16 baseline, A density, A/B/C/D/V vectors, retention and mist rules
are unchanged. No full scene was reconstructed. This is not an integration PR.

## Existing directions and exact owners

| Concern | Existing modules / functions | Actual support and limits |
| --- | --- | --- |
| Terrain self-occlusion | `rendering/ground_composition.py::render`, `rendering/spring_production.py::rasterize_mapped` | The selected nonphysical F2 surface uses final mapped triangles and affine mapped-depth ownership. This is a surface raster ownership calculation, not vegetation masking. The physical branch instead uses `composition_study.py::rasterize` and reciprocal depth. Do not substitute its rule into F2. |
| Visible source coordinates | `composition/fields.py::mapped_source_coordinates`, `rendering/painterly_layers.py::load_features` | Recover visible original triangle XYZ by the same final screen triangle ownership. `build_fields` obtains source forward distance from those XYZ. Mapped visibility depth and source forward distance are distinct quantities. |
| Terrain stroke continuity | `strokes/generators.py::continuity_mask`, `valid_runs`; `strokes/grammar.py::hard_clip` | Reject hidden/discontinuous surface bridges using occupied pixels, source XY jumps, safe distances and boundaries. This is not a full analytic triangle-line visibility solver. It does not know new catalog trees. |
| Painterly omission / whitespace | `composition/multidepth.py::build_reserves`, `omission_retention`; `composition/refinement.py::refine_reserves`; `strokes/scene.py::load_selected_scene` | Local source-depth omissions and global reserves remain distinct. The selected scene blends legacy and selective local retention at 70/30, then applies global retention. Existing positive forms/root-support fields refer to archived scene marks; they are not attachment solutions for new trees. |
| Actual terrain path omission | `strokes/grammar.py::transfer_mist`, `strokes/density_rhythm.py::transfer`; `strokes/vector.py::omit_path`, `split_at_gate` | Retention becomes real shortened/split/dropped paths, plus uncalibrated width/opacity/intensity profiles. Transparent raster alpha alone is not the exported physical omission. Identity-keyed phases matter. |
| Vegetation hidden by nearer terrain | `vegetation/multidepth.py::object_retention`, `render_marks`; `vegetation/grammar.py::redesign` | A scene glyph has one source root forward depth. Nearer terrain can hide it, global reserves always apply, and local omission is matched by source depth. `redesign` converts the probability field to actual clipped V paths. This is the older scene V grammar, not P/B/U/W integration. It is not per-branch 3D visibility. |
| Terrain hidden by foreground vegetation | No reciprocal catalog-tree consumer in the accepted terrain generators / baseline path | **Not connected.** Scene vector composition and draw order overlay V but do not subtract terrain paths behind the new catalog objects. The fixed A/B/C/D/V exports are reused by `rendering/spring_baseline.py::run`; no call imports this new catalog there. |
| Tree-to-tree / crown-to-crown | `vegetation/tree_catalog.py::foreground_gate`, `overlap`; `rendering/tree_final_scale_study.py::_run` | Actual far-to-near vector splitting exists in catalog fixtures. The canopy gate uses a fixed seasonal fraction of each lobe (spring core scale 0.5236), irrespective of retained unit omissions. Trunks use a 0.40 mm distance ribbon around contour centerlines, not a full body with both stroke footprints. Minimum output fragments are 1.2 mm. This is a diagnostic, not production occlusion or a spacing guarantee. |
| Local group depth | `vegetation/tree_spatial_groups.py::members`, `project` | Hand-authored roles plus local 2.5D root offsets, unequal sizes and far-to-near sorting. Not DEM attachment, F2 placement or scene-depth sampling. |
| Wash / pigment | `vegetation/tree_catalog.py::halo_outline`, `wash_metadata`; `coloring/__init__.py` | Separate halo support and preview-color intent only. `coloring` remains a reserved namespace. These polygons are not opaque terrain masks, water transport, calibrated pigment paths or validated layer scheduling. `strokes/color_ready.py` concerns ink support/profile studies, not a working canopy-wash engine. |

The retained runtime hashes and accepted vector signatures are in
`reference_manifest.json`. The historical complete audit, including function
line locations, remains in the locally preserved v10 package. This compact
review does not ship that duplicated audit archive.

## Missing reciprocal interface

The future scene stage needs a shared **visibility contract**, rather than a
new tree generator or a global white silhouette:

1. Object identity, source root XYZ, the existing source forward-depth basis,
   visible ink fragments and body geometry after nearer-terrain/tree clipping.
   A provider must evaluate which terrain segments are truly behind each visible
   part; constant root depth is only a limited fallback for small glyphs.
2. Separate strong body envelopes, occupied canopy-unit support and optional
   selected dense-core support. Export pad occupancy, deliberate omissions,
   leaf unit IDs and open gaps. A wash halo must never supply this exclusion.
3. Per-material footprint envelope, both terrain and vegetation widths,
   registration/edge tolerance, root/supporting-ground protection and minimum
   executable fragment length. Uncalibrated nominal width profiles are not
   sufficient. An exposed root needs a chosen ground relationship.
4. A vector clip operation returning source-parent IDs, original arc intervals,
   local depth decisions, removed lengths and preserved/interpolated pressure
   or width metadata. Split before plotting. Reapply/recheck final physical
   guards after simplification and rounding.

Proposed order: resolve visible trees against the existing terrain depth and
global reserves; resolve ordered tree overlap; build masks only from visible
vegetation; split **farther** terrain segments; validate root contact and selected
ground strokes; export separate terrain and vegetation ink plans. Preserve
original terrain proposal IDs through existing mist transfer; fragment IDs are
new downstream identities, never inputs used to reroll mist. Cache masks by
full geometry, visibility and physical settings, not seed alone.

This must respect the current retention field. True depth occlusion, intentional
pictorial omission, and material footprint clearance must remain separate reasons
in provenance. A tree cannot override a global layout reserve merely because it
is nearer. The new interface has not been added to `spring_baseline.run`.

## Isolated vector proof — implemented only in this experiment

`vegetation/tree_occlusion_proof.py` implements `masks`, `clip_vectors` and
`synthetic_probes`. `rendering/tree_final_scale_study.py::run` exercises them.

- `masks` reconstructs actual paired body sides and their physical collapse
  from `tree_plot_scale.safe_contours`; it fills the visible trunk/major-arm
  interior and includes structural stroke footprints. It does not use the older
  uncollapsed envelope to invent a wide body at a single-line tail.
- Canopy support follows actual retained ink. Only compact dense **units** bridge
  their own inter-ray gaps. No polygon joins different units across an empty pad.
  Omitted / bare foliage therefore cannot generate opaque canopy holes.
- Buffers assume vegetation width 0.8 mm, terrain width 0.6 mm and 0.15 mm
  additional edge tolerance. The terrain-centerline exclusion includes the
  half terrain footprint as well as the tree ink footprint or body. These
  are design assumptions, not brush measurements or absorption margins.
- A small root collar preserves surrounding probes outside the strong body.
  It does not erase the body itself, and does not choose convincing supporting
  terrain. It is a bookkeeping demonstration, **not solved ground attachment**.
- `LineString.difference` produces real clipped polylines. Parts below 2.8 mm
  are dropped and accounted for. Original direction, source IDs and depth stay
  available. The proof preserves nearer/supporting-depth probes. All ordinary
  rulers are farther than one constant-depth B tree; the special near-depth
  ruler remains visible through it to demonstrate the opposite applicability.
  A real scene must clip tree ink behind that nearer object too; this proof
  intentionally does not implement the complete reciprocal visibility solver.

`05_occlusion` compares unmasked, excessive full-support and selective results.
The rulers are synthetic geometry, not a new terrain/rock/soil grammar. Gray
terrain and black trees are diagnostic colors; vector layer archives are
separate. There is no white paint, eraser polygon or raster-alpha masking.
Mask polygons are explicitly nonplotter intent in `proof.masks.geojson`.

## Failure cases and acceptance requirements

| Case | Risk | Required later check |
| --- | --- | --- |
| Sparse or omitted canopy | Legacy lobe cores erase strokes despite absent leaves; full silhouettes make white holes | Use retained unit support; compare occupied units, gaps and actual overlap at calibrated width. Selective ink-only masks may conversely reveal too much terrain inside a crown; tune only occupied dense areas. |
| Narrow or exposed trunk | Contour-only distance ribbons leave terrain through the body, or overwide masks white-out collapsed tails | Body interior plus actual paired-to-single transition; both footprints and measured tolerance. |
| Exposed roots / misty ground | A collar preserves arbitrary lines, while a broad erase makes a floating tree | Choose supporting terrain segments and contact depth explicitly. Retain selected adjacent ground mass; inspect contact under unchanged mist. Root-to-ground attachment remains unresolved. |
| Overlapping trees | A hidden rear crown still erases terrain; clipping makes tiny dangling rays and lost stems | Build reciprocal masks from final visible object parts, preserve strong body continuity, measure all-tree spacing and recheck minimum lengths. Legacy catalog overlap is not accepted as this solution. |
| Depth discontinuity | One root depth places a tall crown incorrectly; geometry depth and source distance are mixed | Use the exact F2 ownership/source mapping and an explicit local comparison basis. Do not alter the camera or retention to hide mistakes. |
| Wider wet footprint | Digital .8 mm gaps survive but real strokes merge | Material coupon, registration margin, direction/speed/pressure variation and final brush-width sensitivity checks. |

## Painting sequence and physical questions

Keep four data products: terrain ink vectors; vegetation ink vectors; later
wash/pigment support; measured brush/material execution settings. The intended
sequence terrain ink → vegetation ink → pigment/wash can work only if the
terrain ink plan is already clipped before the first stroke is executed.
Rendering the trees later cannot remove previously deposited terrain ink.

No wet-medium behavior was measured here. Test required drying intervals and
whether later pigment lifts or redistributes the chosen ink; edge registration
after paper wetting; width variation with load, direction and pressure; absorption,
feathering and multiple-pass accumulation on the actual paper. Preview alpha
does not specify achievable pigment strength. Wash boundaries need separate
material calibration and must not be assumed to repair weak black geometry.

## Acceptance handoff

The tree grammar is provisionally accepted. This proof is not artistically
final: strong terrain lines still survive inside the canopy. The controlling
next requirements are [the shared regional contract](../../design/object_occlusion_contract_v01.md)
and [Rock & Ground Work handoff](../../experiments/rock_soil_catalog_handoff_v01/README.md).
