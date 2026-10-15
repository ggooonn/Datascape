# Geumgangsan spacing audit

Source: preserved [`original/source.py`](../../../artworks/2026-03-17_geumgang/original/source.py), Git blob `551dca8f7124e0fac3fbbd761babdcbdfe9eac81` at parent commit `c89a211aaea3a4d0884d47b0223cb8b1493a0eed`.
SHA-256: `fb6a5ae288097a82842e4e6eea159369a3463d174382c11837d6900f42e75108`.

This is V39.10 from `datascape_0317test.ipynb`. The source manifest says it is a verbatim concatenation of code cells, and that its identity as the final production file remains provisional. The findings below describe this preserved implementation, not an independently verified reconstruction of the finished artwork. The historical file was read, not imported or executed.

## What actually controls rhythm

| Mechanism | Evidence in preserved source | Actual effect |
| --- | --- | --- |
| Adaptive row step | Lines 220–239 | `h = clip((row_max_DEM - 0.1) / 0.8, 0, 1)`; `base_gap = 35 - 33*h**2`; light-ink row step is `max(1, base_gap*(1.5-mean(density_wave)*0.5))`. Taller row maxima produce denser source rows. The gap is in resized DEM row indices, not millimeters. |
| Depth-dependent screen pitch | Lines 47–52 and 169–175 | Cubic interpolation of A/B/C/D y-pitches, followed by a normalized cumulative sum, changes the mapping of rows onto the paper. Height scales also change with depth. This changes apparent spacing independently of row selection. |
| Accordion x shift | Lines 185–188 | `30*sin(2.5*pi*y_ratio)` shifts a whole row sideways. It is not a local spacing field. |
| `density_wave` | Lines 168, 196–218, 223–225, 264–267 | Cubic horizontal anchors `[1, .4, .2, 1, .6]` primarily alter pressure and color-path eligibility. Its mean in the row-step formula is constant across rows; it does not directly make transverse spacing vary with x. |
| Visibility and omission | Lines 177–183, 210–218, 233–235 | A horizon test, including explicit resets at 40% and 75% of depth, hides row portions. Valley/slope/noise can raise the historical Z value toward hover. These are separate causes of visible density variation. |
| Color row step | Lines 241–276 | Uses a different formula: `35-(35-2*m)*h**2`, then advances by `max(1.5,gap*m)`, with the same constant `m=1.5-mean(density_wave)*.5`. Depth weights choose one color per row; noise gates portions along it. |
| Simplification and spline | Lines 285–300 | Three-dimensional RDP and a cubic spline shape the path after selection. They do not define the adaptive row schedule. |

The characteristic rhythm therefore combines terrain-adaptive row sampling, depth mapping, lateral row shift, visibility and brush contact. It cannot accurately be attributed to a single sinusoidal density wave.

## Transfer to fixed F2-C

Only the terrain-responsive sampling principle is adapted. The existing F2 camera, nonlinear projection, terrain visibility, 70/30 foreground retention and all whitespace fields remain unchanged. No historical horizon resets, x shifts, y-pitch warps or hardware values are imported.

The new row signal uses visible source-depth neighborhoods: 50% local peak-height residual, 25% macro-relative relief, 15% ridge support and 10% slope. Each component is robustly normalized. The inverse-quadratic gap is given an explicit contrast exponent and a bounded global density gain. The gain is normalized with a screen-length proxy and expected retained coverage; this is one global scalar, not a local inverse-mist compensation.

Integrating `1 / pitch(q)` produces a strictly increasing row phase. Integer phase contours create actual transverse paths at irregular source-depth intervals. The DEM and projected surface are unchanged. The published mist transfer then cuts and removes actual path portions and assigns width/opacity profiles. No alpha field substitutes for geometry selection.

Historical raw inputs and dependency versions are incomplete. The code includes a synthetic DEM fallback and unseeded NumPy/Python random calls. This study does not claim to reproduce the original 0317 image. All new randomness is explicitly seeded.
