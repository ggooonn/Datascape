# Datascape tree catalog v10 — consolidated review

**Tree grammar: provisionally accepted. Artistic occlusion: unresolved.**
This is the catalog-only consolidation for a Draft PR. It does not integrate
trees into the spring scene, approve wet-brush execution or start rock grammar.

## Review set

| Asset | Purpose |
| --- | --- |
| [00_overview.png](00_overview.png) | P/B/U/W: individual trees, three-tree overlaps and eight-tree serial groups |
| [02_controls.png](02_controls.png) | P/B at 95/130 mm: v09, touches only, unit count only, length only and combined |
| [05_occlusion.png](05_occlusion.png) | Unmasked / excessive full-support / selective vector clipping, with limitations below |
| [06_A4.svg](06_A4.svg) | Native 210 x 297 mm P130/B95/H22 coupon; print at 100% and check the 10 mm ruler |
| [scale_metrics.csv](scale_metrics.csv) | Actual counts, physical bounds and length quantiles for all 80 scale-control states |

Only three PNGs and one distinct SVG are published. The complete eight-sheet
review, vector archives and historical v02–v10 experiments remain locally
preserved; no history was deleted. Exact complete-v10 filenames, byte sizes and
SHA-256 hashes are in [reference_manifest.json](reference_manifest.json).
Those externally held review archives are not GitHub release assets or a
runtime dependency. The artist can supply the full package; the CLI below
reproduces the final review from this branch without it.

## Accepted grammar and entry points

| Form | Role / spring setting | Limits |
| --- | --- | --- |
| P | Emphasized/exposed tree; `profile='refined'` | Provisional structural reference; root attachment unresolved |
| B | General clustered spring tree; `profile='refined'` | Strongest default canopy mass; preserve controlled directional repetition |
| U | Small subordinate multi-stem mass; `profile='v09'` | Prefer H22–45; larger examples are diagnostic, not a second hero tree |
| W | Hanging secondary architecture; `profile='refined'` | Experimental B-carrier form; repeated roof motif, three-ray candidate ceiling, no calibrated damage/season policy |

Use `vegetation.tree_final_scale.make_tree` and `vector_records` for accepted
objects; use `tree_spatial_groups.members/project` for the preserved **local**
group fixtures. These are not DEM placement functions. `spring_profiles` in
the single config records the recommended selection, including the lighter U.
The direct generator also exposes comparison profiles; their availability does
not make every diagnostic output a recommended scene object.

```python
from datascape.vegetation.tree_final_scale import make_tree, FoliageControls
from datascape.vegetation.tree_form_calibration import GrowthControls

tree = make_tree('B', height=95, seed=20261017,
                 controls=FoliageControls(touches='scale', unit_count_scale=1,
                                           length_variation=.12, length_growth=True),
                 growth_controls=GrowthControls(stem_ratio=1, vigor=1))
understory = make_tree('U', height=45, profile='v09')
```

V02 directional fan candidates, dense/light/open/remnant pad ownership and
articulated unequal growth episodes remain. No new foliage generator is added.
`posture` is upright/stooped/redirected/seeded auto; `stem_ratio` is .7–1.3
(routine .85–1.15), `vigor` is 0–1.5. Existing broken-top, bent, suppressed,
dead-limb and damaged-crown operators remain; W rejects uncalibrated damage.
Bend amount and branch irregularity are not independent continuous sliders.

## Scale-dependent foliage

Keep the three controls distinct: touches within a unit, number of whole units,
and correlated stroke-length hierarchy. Recommended `unit_count_scale` is 1;
the x1.35 count experiment is not a default. At H22 the default delegates
exactly to v09. H45 adds selected touches only; H95/130 favor more 2–4-touch
units without filling sparse/open pads. Requested 3–5-touch richness is capped
by existing rays and physical clearance; canonical final states contain no
five-touch units. W retains its three-ray source ceiling.

Length variation is bounded at 0–.15, default .12, using correlated unit/edge
and ray hierarchy rather than independent per-stroke randomness. Nonlinear
growth factors are 1/1/1.04/1.07 at H22/45/95/130. Whole-unit rotation stays
within the inherited +/-8 degrees. Bodies and crown supports do not change.

| Actual source leaf paths | v09 H95 → v10 H95 | v09 H130 → v10 H130 |
| --- | ---: | ---: |
| P | 62 → 78 | 85 → 116 |
| B | 85 → 115 | 122 → 167 |

The .8 mm brush footprint, .5 mm inter-unit free gap and 2.8 mm source-length
floor are **assumptions**, not measured wet-media limits. Intra-unit joins may
merge. Nominal `width_mm` / width profiles remain separate uncalibrated intent.
Legacy tree overlap can generate shorter final fragments; it is not a hardware
filter. Nominal height is not actual ink height: P H130's centerline bounds are
about 117.8 x 137.8 mm. See the CSV before choosing scene dimensions.

## What is consolidated, and why the old module names remain

Ten unchanged runtime modules form the actual dependency closure:
`tree_catalog`, `tree_growth`, `tree_pattern`, `tree_rhythm`, `tree_plot_scale`,
`tree_group_review`, `tree_form_calibration`, `tree_final_scale`,
`tree_spatial_groups`, and the isolated `tree_occlusion_proof`.
The apparently historical modules still supply shared marks, segment geometry,
V02 candidates, pad ownership, safe contours, scale selection and exports.
Their bytes match the accepted v10 checkpoint; removing them or renaming the
whole chain would turn consolidation into an unrequested algorithm rewrite.
Use the final entry point above, not the old experimental canopy entry points.

The rejected v04 `tree_hybrid` engine, v02–v09 study renderers/configs, obsolete
growth/hybrid comparison tests, intermediate previews, all full-state archives,
duplicated reports and caches are **not copied into this branch**. Reusable
plotting functions are extracted into one small `tree_review_support` module.
[DECISIONS.md](DECISIONS.md) preserves the important visual decisions.

## Occlusion and the next Work

The selective proof leaves too much strong terrain inside the canopy. It is
technical evidence of vector splitting, **not artistic masking acceptance or
F2 integration**. Keep stronger trunk/major-branch exclusion, broader occupied
canopy cores, gradual transition release, sparse edges and selected root support
open. Separate object-relative depth, physical footprint, true occlusion,
pictorial omission, optional pressure effects and later pigment intent.

- [Implementation audit and proof limits](OCCLUSION_AUDIT.md)
- [Shared proposed object contract](../../design/object_occlusion_contract_v01.md)
- [Rock & Ground Work, including open pictorial corridors](../../experiments/rock_soil_catalog_handoff_v01/README.md)

Rock/soil grammar may proceed independently. Actual reciprocal masks, scene
placement, roots/ground acceptance, final fragments and physical tests follow
only after that grammar's provisional acceptance. No water/path generator is
required to establish a valley opening or a possible passage.

## Dependencies, reproduction and review status

This branch is stacked directly on **PR #16**,
`feat/spring-provisional-baseline-025` at
`1834cbe8161cf49d3bc5deac5e4af404f8bbdd09`. PR #17 remains a separate
foreground diagnosis, not a code dependency or an adopted scene change.
No existing base file, original artwork, baseline vector, F2 camera, A-density,
mist/whitespace rule, palette or hardware configuration is modified.

Install the repository's `research` and `dev` extras. The actual review runtime
uses Python, NumPy, SciPy, Matplotlib, Pillow and Shapely. It needs no GeoTIFFs
or network connection; no hardware commands are emitted.

```bash
PYTHONPATH=src python -W error::RuntimeWarning -m datascape.rendering.tree_final_scale_study --output outputs/tree-catalog-v10
PYTHONPATH=src python -W error::RuntimeWarning -m unittest discover -s tests -p 'test_tree*_unit.py'
PYTHONPATH=src python -W error::RuntimeWarning -m pytest -q
```

`outputs/` is already ignored by the base repository. The CLI recreates eight
PNG/SVG sheets, 96 review states with separate wash intent and the synthetic
terrain/mask records there. These generated files need not be committed.
Retained regression tests cover active dependencies; one new golden test checks
all 16 v10 size/form vector signatures against the frozen manifest. Validation
results and an exact changed-file inventory are recorded in `VALIDATION.md`.
This Draft PR must not be merged without a separate instruction.
