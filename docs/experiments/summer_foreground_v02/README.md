# Summer v02 / foreground checkpoint

A distinct provisional refinement of PR36 at `f2d03a592aec0e43368557391696f3b4c940db69`. The C_east camera, skyline, source depth and existing omission fields remain fixed. Complete original middle/far terrain and vegetation records are retained exactly; domain-crossing terrain is clipped at source-forward 1600 m without shifting geometry. Approved Spring and all inherited files remain read only.

## Review

Start with `full.png`, `physical_pair.png`, `foreground_before_after.png`, `foreground_crops.png`, `ground_spacing_diagnostics.png`, and `layers.png`. P3/P4 each occupy 300 × 900 mm; the original continuous composition is 600 × 900 mm. The installation adds a 40 mm display gap without stretching the painting.

A-ground organization uses actual source-XYZ mound/ridge support patches shared with unequal tree/rock groups. Near row phase reuses the accepted monotone solver; a new connected occurrence policy opens valleys and passages while retaining supported ground masses. A-specific support priority raises survival around those masses, preserving every exact zero omission core and the two-mm bottom guard. The canonical mist/whitespace fields and other layers are not globally edited. This priority is a new foreground policy, not a claim that the previous A attenuation is unchanged.

Tree v10 P/B/U and Rock & Ground v05 internals are reused at native requested sizes. Changes concern group placement, growth controls, dominance, source-supported roots, shared rock supports, burial and reciprocal 2.5D visibility. W remains experimental and unused. Existing middle/far vegetation survives outside the near domain; far-only provisional B micro texture is disabled. Larger native trees increase path count, which must be considered separately from A length reduction.

`foreground_diagnostics.json` reports actual A intersections at vertical probes and 1 mm centerline-cell occupancy. Dense/open categories come from the shared source-ground field, not arbitrary horizontal stripes. Large open gaps and empty probe intervals must not be described as a calibrated brush-spacing guarantee. The localized crops and coverage results are necessary alongside spacing ratios. All lengths and contacts describe vectors, never physical runtime.

## Canonical data

- `ink.json.gz`, `color_intent.json.gz`: full canonical centerlines and artistic profiles.
- `P3.vectors.json.gz`, `P4.vectors.json.gz`: lossless physical-panel clipping, with continuous offsets and source arcs.
- `authoring_sources.json.gz`: new authoring plus the preserved ancestor sources needed for exact lineage. Statistical authoring counts use only active source cohorts, not every archived ancestor.
- `visibility_ledger.json.gz`: final-pass exact original-arc intervals. `ground_selection_ledger.json.gz` separately records the intermediate A organization.
- `config.json`, `placement.json`, `generation.json`, `verification.json`: selected contacts, settings, solver checks, preserved-record identities and independent readback.
- Open SVG centerlines use mean artistic profiles; full variable profiles are in JSON. Git stores losslessly compressed `.svg.gz`; the review package includes ordinary SVGs.

## Reproduce

Use the verified existing MASTER/VEG TIFFs; their hashes are enforced. From this repository checkout:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/seasonal_screen_v01/summer_v02.py \
  --master /path/SeoulNorth_v02_MASTER_30m.tif \
  --vegetation /path/SeoulNorth_v02_VEG_10m.tif \
  --baseline-fields studies/seasonal_screen_v01/reference_phase.npz
```

The compact reference contains only the unchanged float32 phase array from the preserved Summer v01 diagnostic archive; original and array hashes are in `reference_phase.json`. A private same-run `--field-cache` is optional; omit it for independent source reconstruction. The checkpoint adds no changed DEM or new source extraction.

For previews, call `season_previews` from `diagnostics.py`; `summer_comparison` additionally needs the optional same-run field cache. `verify.py` reads delivered vectors, source arcs, panel profiles and inherited Git blob hashes. New tests are in `tests/test_seasonal_screen_v01.py`.

## Remaining review

The retained middle-distance horizontal transition, foreground ground-to-rock contact, degree of canopy connection, occasional small soil fragments and virtual color territory remain provisional. Nominal masks retain inherited one-mm / upright-2.5D limitations. Width, pigment, pressure-to-Z, reload policy and drying are uncalibrated. No production G-code is generated and no PR is merged.
