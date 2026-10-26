# Summer P3/P4 scene development v01

A provisional Summer scene generated from the existing Seoul DEM and Summer NDVI, with unchanged reusable terrain, Tree v10 and Rock & Ground v05 modules. This work adds a seasonal framework, three new camera comparisons, a soft skyline-continuity review, actual independent Summer vectors and intent previews. Composition, placement, color and concentration remain open to artistic review.

The downloadable package includes a self-contained `Review.html` and the selected Summer diagnostic NPZ. Git keeps the source, canonical vector data, compressed `.svg.gz` centerlines (decompress first) and review PNGs; the large optional diagnostic archives and embedded HTML are distributed in the downloadable package. Start with `Review.html`, `summer_full.png`, `summer_physical_pair.png`, `transition_P1_P4.png`, `skyline_candidates_P1_P4.png` and `viewpoint_candidates.png`. `layers.png` and `color_studies.png` isolate the final vector layers and virtual color hypotheses.

- Artistic base: PR25, `checkpoint/spring-v13-pressure-intent-v01` at `d30ac7be302e1cbfcd2cf66de9087e35ea091b6c`. This contains the reusable catalogs and exact Spring review snapshot. It avoids copying an unrelated machine-backend tree or replacing artistic modules in PR34.
- Physical status reference: PR34, `9665b92a7ab78ce44a135c191eb6c259a3cb03f6`; no production backend, G-code, new Spring source or physical width model is created here.
- New branch: `feat/summer-scene-development-v01`. All inherited tracked files are preserved. Existing PRs remain unmodified and unmerged.
- New C1-related eye: UTM (327105, 4170785), looking toward (323820, 4168370), EPSG:32652. This is an authored viewpoint on the measured DEM, not a verified accessible human viewpoint. Source terrain is never moved or resculpted.

Read [seasonal framework](SEASONAL_FRAMEWORK.md) and [handoff](HANDOFF.md) before selecting the next iteration.

## Reproduction

Python 3.11+ with numpy, scipy, matplotlib, rasterio, shapely, contourpy, osqp, pillow, PyYAML and pytest. Exact local package versions are recorded in `verification.json`. From this checkout:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/summer_scene_v01/viewpoints.py \
  --master /path/SeoulNorth_v02_MASTER_30m.tif
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/summer_scene_v01/generate.py \
  --master /path/SeoulNorth_v02_MASTER_30m.tif \
  --vegetation /path/SeoulNorth_v02_VEG_10m.tif
PYTHONPATH=src python studies/summer_scene_v01/verify.py
PYTHONPATH=src python -m pytest -q tests/test_summer_scene_v01.py
```

The generator verifies both source TIFF SHA256s before use. Reuse existing TIFFs, not a new extraction. The optional `--cache /private/temp.pkl` is an ephemeral same-run speedup; omit it for independent regeneration. Do not use cache files from others. New output directories must first receive the candidate scene JSONs through the viewpoints command. No notebook state is needed.

## Vector contract

- Canonical full geometry: `summer_ink.json.gz` and `summer_color_intent.json.gz`, 600 × 900 mm, top-down XY, polylines, variable design width/opacity/expression intent profiles and source lineage. These profiles are artistic, not calibrated physical pressure.
- `P3.vectors.json.gz`, `P4.vectors.json.gz`: exact X=300 clipping of final canonical geometry, local 0–300 mm X, unchanged Y, original source ID and source-arc ranges. Gaps exist only in installation previews.
- SVGs contain mean-profile-width **open centerlines** for review. Complete vertex profiles live in JSON. SVG preview opacity does not describe pigment layering. They are not controller programs.
- `authoring_sources.json.gz` and `visibility_ledger.json.gz`: pre-occlusion sources and exact retained intervals; no raster eraser. `placement.json` records authored groups, support sites and measured triangle ownership where available. Mid/far roots explicitly use interpolated raster evidence, not exact branch 3D.
- `summer_fields.npz`: reduced-precision diagnostics; regenerate from TIFFs/config for full precision. Candidate surface NPZs are similarly diagnostic.
- `stroke_statistics.json`: original authoring and visible stroke counts/lengths, short-path bins, panel fragments, dense areas and **contact-distance-only** workload. It is not an execution-time prediction.

## Implemented grammar and limits

A reuses local mountain/foreground targets and the accepted monotone QP machinery, with new Summer source fields, mountain strength 0.70 and foreground strength 0.25. B selects existing source-structure accents; C uses the existing depth-direction family at a review spacing; D uses the existing sparse one-sided structural selection with a central strength envelope. D is not a full skyline outline. New masks are recomputed for the new view using inherited 70/30 near-retention principles; no Spring field is edited.

Near P/B/U trees regenerate from v10 with smooth vigor, unit-budget and carrier controls. Rocks regenerate v05 connected multi-mass supports and shared-parent ground patches. Mid/far V uses the existing reduced growth-graph M2/F2 implementation with linked independent foliage passages. B surface micro texture is disabled. No Spring object distribution is reused.

Visibility uses inherited depth-aware reciprocal terrain/object clipping, strong structural bodies and partial occupied-canopy suppression. Nominal design widths and 1 mm raster decisions have the inherited 2.5D limitations; this is not measured wet-brush occlusion. Middle vegetation uses its own reduced graphs and does not gain new 3D volumetric masks in this version. Color passages are independent lobe/branch structures, not per-ink-stroke duplicates. Virtual display groups do not allocate any of the 20 physical pigment slots.

Provisional color studies share identical canonical geometry. Light/dark ink ratios are not fixed, and Spring's approximately 70/30 concentration allocation is not inherited as a Summer execution rule.
