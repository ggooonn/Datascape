# Taebaek (Yang) Source Analysis and Future Module Boundaries

## Verified Source

The attached `datascape_0815_Taebaek(1).ipynb` is 35,391,440 bytes; its SHA-256 matches the existing artwork manifest:

`0ebd5e95ae309edf88b6cd1857e12510d5c6e657c1e22d3a604400e7f0b49a77`

It contains one code cell (499 displayed lines). Its parsed Python AST matches the [archived code extraction](../../../artworks/2026-08-15_taebaek_yang/original/source.py). The attachment establishes the notebook's availability in this conversation; it has not been added to GitHub by this PR. Original code and outputs remain unchanged. Matching the archive does not independently establish the exact historical production run or environment.

## Actual Generation Structure

| Stage | Historical behavior | Consequence for the new work |
| --- | --- | --- |
| Loading | Resize each band to 2000 × 1500; replace all negative values with zero; any exception returns a zero array. | Reuse the new explicit finite-mask loader. Do not hide failures or remove valid negatives. |
| Height shaping | Normalize DEM by its maximum, raise it to 1.3, then multiply by a y-dependent 200/450/550 scale. | This is expressive screen-height shaping, not a metric camera projection. Keep raw terrain and transformations separate. |
| Horizontal mapping | Extend the canvas by 400 mm on both sides; add sinusoidal sway and row-dependent stretch. | Retain as an optional historical stroke transform after selecting a geographic view. |
| Y mapping | Accumulate row pitches, map them to 1550 mm, and add shaped terrain height. | Creates a depth-like drawing arrangement; not a calibrated perspective camera. |
| Horizon Mask | Scan rows forward, compare each screen-height column against a running maximum, and lower the horizon by 150 at 30%/70% of rows. | The two resets are deliberate compositional openings, not physically derived occlusion. The mask is computed before later sway/high-frequency Y changes, so it is not an exact screen-space z-buffer. |
| Ink curves | Sample horizontal rows, vary spacing with row roughness, build visible point runs, and break paths using a Z threshold. | Preserve the horizontal curve principle; do not copy the old row or camera assumptions into the selected view. |
| Pressure | Combine normalized altitude 70% and array-index slope 30%, then add noise and map to negative machine Z. | Expressive intensity must be separated from calibrated hardware Z. |
| Spline | CubicSpline independently interpolates X/Y/Z using uniformly spaced parameters; adjacent XY points below 0.1 mm are filtered. | Here, the third value is machine Z/pressure, not DEM elevation. Review overshoot, parameterization, and post-spline bounds. |
| Vegetation inputs | Aspect and NDVI are loaded but not used by the subsequent path logic. | Seasonal vegetation requires new explicit data connections after terrain selection. |
| Panel clipping | Keep interior sample points and split runs when points fall outside. | Boundary intersections and outside-to-outside crossings are lost; use exact segment clipping later. |
| Digital rendering | Matplotlib LineCollection uses the sliced XY paths, fixed per-layer width/opacity, and visual z-order. | The preview does not simulate each Z pressure value; visual z-order can differ from G-code layer order. |
| G-code | Iterate panel/layer paths with embedded old station coordinates, dipping, washing, and negative Z. | Preserve this archive. Build a separate calibrated backend later; do not execute it on the new plotter. |

Random generation uses both `random` and `numpy.random` without a recorded seed. The macro DEM color logic mixes row position and smoothed height, rather than measured seasonal NDVI. Output-directory V203 and preview/G-code V202 labels differ and should remain historical facts.

## Proposed Production Boundaries — Not Implemented Here

| Module | Input | Output / responsibility |
| --- | --- | --- |
| Terrain and projection | Valid geographic grid + scene/camera settings | Terrain features and a chosen view; retain physical units and transformation provenance. |
| Stroke generation | Chosen view + texture rules + seed | A finalized vector stroke set in panel/canvas millimeters, independent of machine coordinates. |
| Digital stroke renderer | Finalized stroke set + preview style | Images from the same path geometry/order used for production. Preview opacity/line width stay separate from physical pigment or Z. |
| Plotter backend | The identical finalized stroke set + calibrated machine/tool map | Coordinate conversion, pressure-to-Z mapping, validated tool motions, and G-code. |

A future stroke record should retain ID, scene/panel IDs, XY polyline, dimensionless expressive intensity along the path, palette/tool identity, draw order, direction-reversal permission, and input/scene/seed provenance. Do not store old negative machine Z as intrinsic terrain geometry. Use exact panel clipping before finalizing the shared paths; both output backends read the same finalized set. This is a design direction, not a committed production schema or implementation.

The current shaded DEM/mesh viewer is a **diagnostic terrain renderer**, not the future vector stroke renderer. Its mesh edges, shading, and ROI hatching are not plotter instructions.

The existing 20-slot palette and FluidNC coordinates were read only. They are not inputs to this monochrome exploration. Do not couple machine dip/wash/Z settings to camera exploration. See the unchanged [palette](../../../configs/palettes/palette_20.yaml) and [tool coordinates](../../../hardware/fluidnc/tool_coordinates.yaml).
