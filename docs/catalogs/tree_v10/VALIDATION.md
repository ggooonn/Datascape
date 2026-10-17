# Consolidation validation and exact PR inventory

## Dependency and preservation

- Base: PR #16, `feat/spring-provisional-baseline-025`, commit
  `1834cbe8161cf49d3bc5deac5e4af404f8bbdd09`.
- PR #16 is open and depends on PR #15. PR #17 is a separate foreground
  review based on PR #16; it is not included or rewritten here. `main` is
  therefore not the correct direct base for this catalog-only diff.
- All **690** existing PR #16 files remain unchanged. Every PR change is an
  addition. Historical artwork, baseline, scene vectors, camera, A density,
  mist/whitespace, palette and hardware settings are untouched.
- All **10** retained tree runtime modules are byte-identical to accepted local
  v10 code, verified against `reference_manifest.json`.

Accepted baseline vector archive SHA-256:

`22bace23f0ae34f69873a282fec15c25a431d0e998216d995b1ab14c3f85fab3`

## Executed verification

```bash
PYTHONPATH=src python -W error::RuntimeWarning -m pytest -q
PYTHONPATH=src python -W error::RuntimeWarning -m datascape.rendering.tree_final_scale_study --output outputs/tree-catalog-v10
```

- **198 tests passed**, including **80 catalog tests** (79 retained active
  regressions + one new golden test) and the 118 existing repository tests.
  The golden test's **16 subtests passed**, one for each form/size reference.
- Recreated eight PNG/SVG sheets and 96 object/group review states, plus one
  separate vegetation archive for the isolated proof. All **97** gzip vector
  archives decoded; their actual stroke records exactly match the complete
  locally preserved v10 originals. Config/provenance differs intentionally to
  identify PR #16 as this clean branch's base.
- All eight PNGs decode and eight SVGs parse. The three retained PNGs are
  pixel-identical to the regenerated counterparts. Native A4 dimensions are
  210 x 297 mm. Translation-only physical coordinates are preserved.
- The published CSV uses LF line endings; all 80 records equal the regenerated
  metrics. Renderer extraction and CSV formatting do not alter object geometry.
- New source/config/docs are English. Python syntax, documentation links,
  whitespace and exact scope were checked. No machine commands or full scene
  generation were run.

Runtime: Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, Matplotlib 3.10.8,
Shapely 2.2.0, pytest 9.1.1. Validation required installing the declared research
and dev dependencies in the execution environment; no dependency/hardware
configuration files were changed. Geometry tests and assumed-width previews
are not wet-brush or pictorial masking approval.

## Exact changed-file scope — 34 additions

- 10 unchanged active tree/proof runtime modules.
- 2 renderer/helper modules, replacing dependencies on historical study runners.
- 9 test files: 8 relevant retained suites and 1 golden acceptance suite.
- 1 final review configuration.
- 12 documentation/review files: 6 Markdown documents, 1 manifest, 1 metrics CSV,
  3 PNGs and 1 distinct native-size SVG.

- `configs/experiments/tree_catalog_v10.json`
- `docs/catalogs/tree_v10/00_overview.png`
- `docs/catalogs/tree_v10/02_controls.png`
- `docs/catalogs/tree_v10/05_occlusion.png`
- `docs/catalogs/tree_v10/06_A4.svg`
- `docs/catalogs/tree_v10/DECISIONS.md`
- `docs/catalogs/tree_v10/OCCLUSION_AUDIT.md`
- `docs/catalogs/tree_v10/README.md`
- `docs/catalogs/tree_v10/VALIDATION.md`
- `docs/catalogs/tree_v10/reference_manifest.json`
- `docs/catalogs/tree_v10/scale_metrics.csv`
- `docs/design/object_occlusion_contract_v01.md`
- `docs/experiments/rock_soil_catalog_handoff_v01/README.md`
- `src/datascape/rendering/tree_final_scale_study.py`
- `src/datascape/rendering/tree_review_support.py`
- `src/datascape/vegetation/tree_catalog.py`
- `src/datascape/vegetation/tree_final_scale.py`
- `src/datascape/vegetation/tree_form_calibration.py`
- `src/datascape/vegetation/tree_group_review.py`
- `src/datascape/vegetation/tree_growth.py`
- `src/datascape/vegetation/tree_occlusion_proof.py`
- `src/datascape/vegetation/tree_pattern.py`
- `src/datascape/vegetation/tree_plot_scale.py`
- `src/datascape/vegetation/tree_rhythm.py`
- `src/datascape/vegetation/tree_spatial_groups.py`
- `tests/test_tree_catalog_acceptance_unit.py`
- `tests/test_tree_catalog_unit.py`
- `tests/test_tree_final_scale_unit.py`
- `tests/test_tree_form_calibration_unit.py`
- `tests/test_tree_group_review_unit.py`
- `tests/test_tree_occlusion_proof_unit.py`
- `tests/test_tree_pattern_unit.py`
- `tests/test_tree_plot_scale_unit.py`
- `tests/test_tree_rhythm_unit.py`

## Assets deliberately outside the PR

The original archival worktree and all local v02–v10 branches/results remain.
Excluded are the rejected hybrid engine, superseded comparison runners/configs
and growth/hybrid comparison suites; intermediate generated PNG/SVG collections;
all full-state vector/wash archives, the large proof GeoJSON and repeated record
JSON; full HTML/ZIP reviews; caches, temporary files and raw data. None were
removed to shrink this PR. Complete v10 package filenames, sizes and hashes are
listed in `reference_manifest.json`; those artist-held archives are not publicly
hosted by this PR. Fresh full outputs go to the already ignored `outputs/`.

## Open ownership

The Rock & Ground Work owns compact rock/bedrock/broken-surface and soil/slope/
mound grammar, root/support interfaces, A/C replace/reinforce/omit intent and
negative-space corridor studies. It may use isolated synthetic interactions.
Later scene integration owns actual placement, shared depth resolution, broader
canopy-core and gradual transition suppression, root grounding and final physical
fragments. Brush/material calibration remains later physical work. The synthetic
proof does not close any of those acceptance gates. No PR is merged here.
