# Next Stroke Experiment and Seasonal Layer Design

This is a design note, not an implemented stroke or color system. The current PR ends at a measured, continuous spring composition. Keep [P2 as the primary and P3 as the comparison](README.md); reuse the existing modules rather than rebuilding the terrain engine.

## Three Machine-Drawing Languages

Use the same finalized terrain mapping, canvas dimensions and visibility surface for all three experiments. Compare black ink first, with similar total path length or covered area and recorded density controls. The aim is continuous curves, repetition, density/direction changes and layered paths that suit a plotter, rather than reproducing a named historical texture stroke.

| Language | Proposed generation | What to compare |
| --- | --- | --- |
| Taebaek horizontal curves | Sample repeated geographic terrain transects; project them through the chosen P2/P3 mapping. Retain the archived 0815 language of long row curves and variable spacing. | Continuity, regular repetition, density increasing with terrain complexity, and whether valley/peak structure remains legible. |
| Structural lines | Extract ridge/valley candidates from valid source terrain at declared physical scales; keep important projected silhouettes and selected terrain transects. | A sparse spatial skeleton, clear gaps between masses, and connections from foreground through the valley to the main mountain. |
| Direction-field curves | Build an unoriented terrain direction field from source gradients/structure, blend a controllable horizontal preference, and trace long curves. Preserve sign continuity when integrating the field. | Continuous path length, direction changes, layered rhythm, and where aligned lines reveal or obscure relief. |

The field is a proposed machine-drawing control, not a claim about the correct traditional brush direction. Handle near-flat terrain and unstable directions explicitly. Keep density, line width and expressive intensity separate; do not use dense line counts as a substitute for calibrated pressure.

The [0815 analysis](../seoul_viewpoints_v01/taebaek_analysis.md) remains the verified source reference. Its Horizon Mask was evaluated before later distortions and included two compositional resets. Its third spline coordinate represented machine pressure/Z rather than terrain elevation. Preserve the archive and adapt the curve principle; do not run or import its embedded hardware commands.

## Shared Vector Record

Proposed fields, to be refined when the first stroke comparison is implemented:

| Field | Meaning |
| --- | --- |
| `stroke_id`, `scene_id`, `language`, `region_id` | Stable identity and provenance. |
| `source_xyz_utm_m` | Optional source terrain anchors with original elevations; never hardware Z. |
| `xy_canvas_mm` | Final continuous 600 x 900 mm polyline after projection, smoothing, visibility splitting and clipping. |
| `expressive_intensity`, `preview_width_mm` | Dimensionless intensity and digital display width, separately recorded. |
| `layer_id`, `draw_order`, `palette_slot`, `reversal_allowed` | Explicit scheduling and pigment/tool identity. Use ink initially; color slots are optional. |
| `source_hashes`, `mapping_config`, `seed_keys` | Reproducibility of terrain, projection and randomness. |
| `panel_segments` | Exact clipped 300 x 900 mm segments derived from the continuous path, with source stroke identity retained. |

Generate/smooth paths, then test them against the **same final mapped depth surface** used by the terrain preview. Split hidden intervals after smoothing; test spline overshoot and source-data support. For a curve anchored on a mesh triangle, use its mapped-triangle interpolation rule rather than mixing the old pre-warp mask with new screen positions. Physical gap insertion is for display only. A crossing line ends on the right edge of panel 1 and resumes at the left edge of panel 2; neither backend draws through the 40 mm gap.

Use exact segment intersections with panel boundaries, including outside-to-outside crossings. Finalize the shared vector record once. The digital stroke renderer and later G-code backend read identical geometry and order; the renderer does not silently regenerate randomness. Keep tool coordinates, dipping/washing and pressure-to-machine-Z conversion in a separately calibrated backend. These data structures and algorithms are proposals in this PR, not exported paths.

## Twenty-Color Seasonal Distribution

Keep [palette_20.yaml](../../../configs/palettes/palette_20.yaml) byte-identical. Its 20 assigned slots A1-D5 are available in every season; unassigned swaps are not silently introduced. The YAML explicitly describes display colors rather than measured dry pigments.

Compute color features in source geographic space **before projection**:

- Raw height/slope and a mask-aware Macro DEM at a declared metric smoothing scale. Preserve the raw DEM separately and record the chosen scale; do not inherit the archived image-pixel kernel as a physical terrain scale.
- Season-specific NDVI and valid observation counts. Mark low-support samples explicitly and use a documented fallback; do not treat missing NDVI as measured zero vegetation.
- Region IDs and spatially correlated density controls so repeated paths share coherent areas. Density and pigment selection remain independent controls.

The validated 30 m and 10 m exports have different bounds and vertical grid offsets. When using VEG, sample/reproject by CRS and transforms onto the required support; never pair DEM and VEG by array indices. Do not infer 10 m terrain detail from a 30 m DEM.

A proposed probability model is a normalized score per slot combining a seasonal bias, terrain/Macro DEM terms, valid NDVI terms and a seeded spatial field. Retain a small configurable probability floor for all assigned slots, and record the full 20-slot weights. Dominant colors emerge from relative occurrence, regional concentration and layer order, not a season-specific reduced palette.

| Season | Initial dominant-bias hypothesis | Other slots |
| --- | --- | --- |
| Spring | C1/C2 with D1 and A3 support | All 20 remain available; use sparse contrasting accents. |
| Summer | C3/C4/C5 with B2 support | Vary local density and depth of layering rather than using green alone. |
| Autumn | D2/D3/D4/D5 with selected green remnants | Preserve cooler passages and occasional accents. |
| Winter | A2/A3 with B2/B3 support | Allow restrained warm/green occurrences; do not force a monochrome season. |

These are starting hypotheses for visual review, not calibrated paint recipes or implemented defaults. Do not assign display alpha as a measured pigment transparency. Each actual pigment, dilution, substrate and drying condition needs its own observed behavior; no slot is assumed to layer transparently.

Separate broad light layers, regional passages, structural ink and accents in an explicit draw schedule. Several colors may overlap the same region. Record per-layer density, intended preview opacity, selected slot and order; test alternate orders using the same geometric strokes. Actual opacity, dilution and physical Z are calibration results, not inferred from a hex code or preview alpha.

## Controlled Randomness and Physical Calibration

Use one recorded base seed and stable derived keys for geometry, spatial density, pigment choice and layer accents. Derive keys from stable stroke/region IDs with a specified digest, not Python's process-dependent `hash()`. Store realized selections and order as well as seeds, so adding a renderer or rearranging files does not reroll the painting. A color change must not alter stroke geometry unless that is an explicit experiment.

Calibrate on the actual spring paper with single-pigment swatches and selected ordered overlaps; retain dilution, intensity/pressure setting, drying conditions and scans/photos. Later seasons require their own substrate checks. These measurements inform the preview and the backend separately. No machine motion, dipping, washing or palette modification is authorized or executed by this study.

## Immediate Next Step

After reviewing the completed spatial comparison, start a small black-ink test in P2 with horizontal curves, structural lines and direction-field curves. Reuse the source transects/anchors, seeds and density controls for P3, then finalize its own projected paths. Each mapping has a distinct vector record; within that record the digital and machine backends share identical geometry. Select useful line behavior before adding color. This staging prioritizes a spring pair that can be produced while keeping the modules reusable for all eight panels.
