# Rock & Ground v05 — consolidated provisional catalog

**Pictorial grammar provisionally accepted. Scene integration and physical plotting remain unresolved.**
This branch is stacked on Tree Catalog v10 / PR #18 at
`f858e7816822c539944c8244677c29a7dd39fc0a`, which is stacked on the unchanged
PR #16 spring baseline. PR #17 remains a separate, unadopted foreground review.
No parent branch, scene asset, shared occlusion contract or tree module is edited.

## Compact review

| Native vector master | Review purpose | Physical sheet size |
| --- | --- | --- |
| [01_structure.svg](01_structure.svg) | Matched v04 control / accepted feature-linked short strokes, same B support and macro field | 420 x 297 mm |
| [02_scale_catalog.svg](02_scale_catalog.svg) | Eleven independently generated XS–XL specimens; B2/B3/B4; optional A | 594 x 594 mm |
| [03_material_layers.svg](03_material_layers.svg) | A, color-oriented C, rock, Soil, protected supports and nonplotting wash intent; matched Soil treatment | 594 x 420 mm |
| [04_overview.svg](04_overview.svg) | Local B assembly, ink-only / conceptual color / ownership, optional A and unchanged v10 trees | 594 x 420 mm |
| [scale_metrics.csv](scale_metrics.csv) | Actual object bounds, path counts, ink length and length/area; no wet coverage claim | mm |

SVGs are black-vector masters with separate diagnostic categories. Print at 100%
and verify the 10 mm ruler. Browser zoom does not establish physical brush feasibility.
Only these four complementary native SVGs are published, without PNG duplicates.
Additional feature/C-contact diagnostics and 11 native object crops regenerate locally.

## Accepted controls and entry points

| Level | Implementation / configuration | Continuous controls | Discrete choices |
| --- | --- | --- | --- |
| Shared mass / planes | `ground.structure_v02.scaffold`, `structural_mass`, `StructuralField`; low-level `ground.grammar` | width, height, anchor, burial, slope, field orientation, spacing, bow, local deviation | compact / angular / bedrock; layered / jointed / rounded treatments |
| Physical object detail | `ground.structural_detail_v05.base_mass`, `feature_detail`, `PhysicalDetailPolicy` | physical exposure thresholds, short-stroke limits, bounded feature spacing/overlap parameters | physical gates select sparse macro, meso and selected micro; XS–XL are review bins, not species |
| Connected B composition | `ground.structural_detail_v05.formation`, `FormationControls` | dominance .6–.8, overlap .1–.4, burial 0–.35, dimensions, orientation and local deviation | 2 / 3 / 4 major exposures, unequal depth ranks |
| Optional A condition | one `base_mass(..., form='bedrock')` plus `feature_detail` | same mass/plane controls; not a fixed outline | optional coherent finite exposure, not the default group |
| Stroke rhythm | `ground.refinement_v03.rhythm` | bounded strength and inherited gaps | prefer `interruption`; rare optional offset/overlap; omission is distinct from fracture and visibility |
| Patch ownership | `ground.patch_system_v04.PatchSpec`, `PatchControls`, `patch_system` | area, aspect, irregularity, position/contact offset, rotation, family phase, merge gap, minimum separation | none / separate / satellites / connected / shared / discontinuous; specs determine patch count; density tiers 0/1 |
| Patch ink / pigment intent | `PatchControls`, `ground.material_review_v05.ground_gradient` | ink spacing, coherence, edge dissolution, contact reach; pigment fraction | optional pigment support, separate from plotted ink and from C |
| Local interaction | `ground.interaction.plan`, `Region`, `Corridor`, `replacement_intervals` | original source-arc intervals, rank, declared footprint and edge margins | replace / restrained reinforce / independent; finite synthetic ranks only |
| Material review | `ground.material_review_v05.tag`, `appearance`, `angle_audit` | source-preserving derived review metadata | ink / C-only / sources / color-ready; C stays geometrically distinct |

`configs/catalogs/rock_ground_v05.json` holds the native-mm catalog specimens,
B controls, seed and physical detail gates. Authored historical controls and local
contact fixtures stay fixed in the renderer, rather than becoming a new catalog.
Nine accepted `ground` modules retain the exact v05 source bytes. Their inherited
low-level helpers remain available; obsolete study runners are not shipped.
`rendering/rock_ground_review_controls.py` exists only to regenerate the matched
v04 comparison, and is not the accepted detail or object-generation entry point.

```python
from datascape.ground.structural_detail_v05 import (
    base_mass, formation, FormationControls, feature_detail,
)
from datascape.ground.patch_system_v04 import PatchSpec, PatchControls, patch_system

masses = formation('new-object/group', FormationControls(
    width_mm=190, height_mm=65, major_count=3, dominance=.72, overlap=.26))
objects = [feature_detail(m)[0] for m in masses]
small = feature_detail(base_mass('new-object/stone', 18, 12, 'compact', 'rounded'))[0]
# Supply an explicitly identified monotone support path; this is not DEM placement.
# ground = patch_system('new-object/soil', host_record,
#     [PatchSpec('contact', x_mm=80, host_offset_mm=2, area_mm2=650)], PatchControls())
```

B is the preferred general foreground/middle-ground organization. A remains an
optional exposed-bedrock condition. Neither is one immutable silhouette: change
construction parameters, not a finished-path scale transform. A finite synthetic
body marked opaque is not proof that a real exposed terrain surface is opaque.
Small stones use physical simplification and do not inherit scaled micro hatching.

## Reproduce and validate

```bash
python -m pip install -e '.[research,dev]' cairosvg
python -m datascape.rendering.rock_ground_catalog \
  --config configs/catalogs/rock_ground_v05.json \
  --output outputs/rock-ground-v05-review
python -m pytest tests/test_rock_ground_catalog.py tests/test_rock_ground_v05.py \
  tests/test_rock_ground_patch_controls.py tests/test_rock_ground_consolidation.py -q
```

The runner creates four main sheets, two supplements, 11 native crops,
`vectors.json.gz` (original and final records), `audit.json`, `record.json` and
`supports.geojson`. All support/ownership/wash/feature polygons are nonplotting local
millimeters, not geographic coordinates. `record.json` retains the historical
review-status text inside reproducible output; this document records the later
provisional artistic acceptance. Acceptance does not lock integration or materials.

The matched structure comparison retains macro geometry while reducing 80 paths /
2489.262 mm to 67 / 2067.442 mm. Short groups follow existing carriers/junctions or
an explicitly selected carrier-side release; no independent oval hatch lattice.
C separation removes 57.103 mm from the example's 1430.045 mm ink-only review,
about 4% extra black length if C were included. It does not explain all A/Soil
regularity or solve C/material intersections. An isolated C0 contact proposal is
an optional diagnostic, not a default edit to canonical C.

Physical assumptions: rock screening .60 mm, contour .65, ground .60, tree .80;
minimum final centerline 2.8 mm. Overlap screening and path counts are not measured
ink accumulation, pressure, wash or production certification.

## Decisions and next Work

- [Decision history and final artistic feedback](DECISIONS.md)
- [Spring Scene Integration handoff: exact sources, missing inputs and OCC gates](SPRING_INTEGRATION_HANDOFF.md)
- [Validation and publication inventory](VALIDATION.md)
- [Archived output signatures and exact runtime/vector goldens](reference_manifest.json)
- [Unchanged shared proposed occlusion contract](../../design/object_occlusion_contract_v01.md)

No full spring preview is generated by this consolidation. Local v01–v05 branches,
complete SVG/PNG/HTML/ZIP/vector/support archives and research documents remain
untouched. They are excluded from this PR, not deleted. Do not merge this Draft PR.
