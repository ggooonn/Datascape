# Seasonal composition v03

Additive development from PR37 at `a6ce842cfb894ce35e15332f3b6c6154254708ec`. All inherited files stay unchanged. The new flow policy, scene recipes, generators, reviews and verifier are isolated here.

Summer retains C_east and starts with the existing middle/far mountain structure. Three asymmetric release hypotheses are compared as source-field studies. A broad authored gaze prior is refined by measured valley/ridge evidence. Only a depth-local part of the omission field changes; global top/bottom reserves remain binding. Near Tree v10 and Rock & Ground v05 groups regenerate natively at larger requested sizes with actual shared terrain contacts.

Autumn uses the recorded A_south view; Winter uses B_northwest. These are existing, distinct source views, not a new viewpoint search. Their foliage budgets, retained pine cohorts, rock exposure, unequal groups and open territories differ structurally. Colors remain virtual hypotheses and no printing plan or G-code is produced.

## Reproduce

Use Python 3.11+ with numpy, scipy, matplotlib, rasterio, shapely, contourpy, osqp, pillow, PyYAML and pytest. Read the exact package versions in the final verification report. Reuse the original MASTER/VEG TIFFs; their SHA256s are enforced. No new extraction or notebook state is needed.

Run each command from the complete repository checkout. `--cache-dir` may point to a new empty private directory; source fields and previsibility stages are then rebuilt independently. Existing stage caches are input/code bound and must not be mixed across implementation changes.

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/seasonal_composition_v03/scenes.py summer \
  --master /path/SeoulNorth_v02_MASTER_30m.tif \
  --vegetation /path/SeoulNorth_v02_VEG_10m.tif --cache-dir /private/empty-study-cache
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/seasonal_composition_v03/scenes.py autumn \
  --master /path/SeoulNorth_v02_MASTER_30m.tif \
  --vegetation /path/SeoulNorth_v02_VEG_10m.tif --cache-dir /private/empty-study-cache
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/seasonal_composition_v03/scenes.py winter \
  --master /path/SeoulNorth_v02_MASTER_30m.tif \
  --vegetation /path/SeoulNorth_v02_VEG_10m.tif --cache-dir /private/empty-study-cache
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/seasonal_composition_v03/screen.py
PYTHONPATH=src python -m pytest -q tests/test_seasonal_composition_v03.py
```

`recipes.py` holds explicit requested compositions; each output includes requested_config.json before support snapping, final config.json after snapping, unchanged scene.json, placement/source/visibility ledgers, actual vectors and reviews. Canonical JSON includes full variable artistic width/opacity/expression profiles. SVGs are mean-width open centerlines; Git stores `.svg.gz`, and downloadable packages include ordinary SVG copies. Reduced fields.npz archives support offline review and are not full-precision generation inputs.

Every delivered row has `scene_season`. Native catalog `season` metadata records its Spring grammar ancestry and is made explicit as `catalog_reference_season`; it is not the generated scene's season. Seasonal vigor and structural placement are controlled by the actual scene configuration.

Middle/far contour drawing appears relatively stable. Foreground is less physically verified and may need a different brush strategy. This is a production consideration, not an automatic canonical geometry change. All technical and artistic results remain provisional until visual/physical review; do not merge a PR without explicit authorization.
