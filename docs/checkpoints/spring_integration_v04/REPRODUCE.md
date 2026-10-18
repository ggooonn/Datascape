# Reproduce the preserved Spring v04 state

Run from repository root on the checkpoint artifact commit pinned in the PR.
Use a new branch and new output directory. Never generate into the tracked
checkpoint or overwrite earlier experimental output directories.

## Install

For the recorded review environment:

```bash
python -m pip install -r docs/checkpoints/spring_integration_v04/requirements-review.txt
python -m pip install --no-deps -e .
```

The saved renderer imports the inherited scene modules, so GIS dependencies are
still imported even though replay does not read TIFFs. Font used for the sheets:
`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. Package versions are display
reproducibility conditions, not brush/ink/pigment calibration.

## 1. Replay saved vectors, without TIFFs or private references

```bash
python -m datascape.rendering.spring_checkpoint \
  --output outputs/spring-v04-replay-new
```

This verifies retained artifact, original implementation and locked source hashes;
reconstructs terrain, B and C in their exact original order; and renders A,
B/C restrained and diagnostic, color-only diagnostic and optional centerline SVGs.
It writes `replay_validation.json` and compares the regenerated C diagnostic and
color-only pixels to their immutable archived originals. Existing nonempty output
directories are refused. Raster envelopes are uncalibrated width-intent previews;
SVGs contain open mean-width centerlines. Full profiles remain in JSON.

Exact ordered concatenation:

- terrain = A + C
- B = terrain + rock_soil + thin
- C = terrain + rock_soil + gestures + trunk

No source generation or placement decision runs in replay. The original four
full comparison sheets are stored directly. Original sheet 02 requires private
references; the tracked macro map is an exact crop `[16, 88, 1000, 803]` of its
nonplotting first panel, with no change to scene geometry.

## 2. Full geometry, masks and source-field regeneration

This is optional and **was not rerun for the preservation-only checkpoint**.
The original v04 generation evidence is retained in `artifacts/record.json`.
Supply the original files separately; no TIFF or float64 cache is in Git:

| Input | SHA-256 |
| --- | --- |
| SeoulNorth_v02_MASTER_30m.tif | `837f4b6b2e01e3b97b05db3e62fbd0869ce052ba4c18cc47a99d97873317f0fb` |
| SeoulNorth_v02_VEG_10m.tif | `ac7f2d96af327f7b1ab07da14e379d0466500799420066484b29b45fbd5b47d5` |

The original five private image filenames and hashes are in the v04 config.
They are only needed to rebuild reference sheet 02, not to make placement/color
choices; reference-to-rule interpretation is explicitly stored in the config.
Restore them from the preserved private package's `private_references` folder.

```bash
# Restore exactly the tracked v03 control; refuses different existing files.
python -m datascape.rendering.spring_checkpoint --restore-controls
python -m datascape.rendering.spring_macro_study \
  --master /path/to/SeoulNorth_v02_MASTER_30m.tif \
  --veg /path/to/SeoulNorth_v02_VEG_10m.tif \
  --references /path/to/private_references \
  --config configs/scenes/seoul_spring_macro_v04.json \
  --output outputs/spring-v04-regenerated-new
```

The old v04 study runner is preserved byte-for-byte, including its dependency on
`outputs/spring-diverse-vector-v03` and the private-reference diagnostic. It does
not require v02 output archives to generate v04. The restored v02/v03 source
entry points are historical/reusable code; their entire old output collections
are intentionally not duplicated in this checkpoint.

## Tests

```bash
python -m pytest tests/test_spring_checkpoint.py \
  tests/test_spring_macro_v04.py tests/test_spring_diverse_v03.py \
  tests/test_spring_cluster_v02.py tests/test_spring_integration.py \
  tests/test_tree_final_scale_unit.py tests/test_tree_catalog_acceptance_unit.py \
  tests/test_rock_ground_v05.py tests/test_rock_ground_consolidation.py \
  tests/test_rock_ground_patch_controls.py -q
```

The checkpoint test checks saved catalog/baseline integrity, canonical legacy-V
absence, complete current-owner inventory, exact composite counts and geometry
against actual source-arc records. Technical success is not artistic acceptance.
