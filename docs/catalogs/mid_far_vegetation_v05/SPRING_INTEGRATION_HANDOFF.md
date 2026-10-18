# Handoff to the next full Spring integration Work

## Start and dependencies

Start a **separate Work and branch from this consolidation PR's published head**,
not the original local-only study SHAs. Use the exact head SHA shown by the PR.

```bash
git fetch origin feat/mid-far-vegetation-consolidated
git switch -c work/spring-integration-next origin/feat/mid-far-vegetation-consolidated
git rev-parse HEAD
```

Dependency order remains #16 -> #18 -> #19 -> #20 -> #21 -> this PR. The base is
`checkpoint/spring-integration-v04` at
`b86a831eab9bfd78ce870c9ffb7e9a0ea65e44e7` (#21). Its last commit is a publication
note above the immutable `90bb2572a35731ccdb38ec332456f2f94ac76456` study start.
Keep the note and all 850 inherited file entries unchanged. #17 remains a
separate unadopted foreground diagnosis. No parent PR is rebased, retargeted,
closed, modified or merged for this consolidation.

## Read first

1. This catalog's `DECISIONS.md`, `VALIDATION.md` and `reference_vectors.json`.
2. `configs/vegetation/mid_far_integration_handoff_v05.json` — authoritative
   recommendation, distinct from historical experiment configs.
3. `docs/checkpoints/spring_integration_v04/PUBLISHED_START.md`, `HANDOFF.md`,
   `REPRODUCE.md`, and `placement_inventory.csv` — saved scene and 119 temporary
   authored sites, all still provisional.
4. Accepted Tree v10 and Rock & Ground v05 catalog handoffs, plus
   `docs/design/object_occlusion_contract_v01.md` — inherited unresolved contract.

## Locked and usable inputs

| Input | Repository path / status |
| --- | --- |
| F2-C / foreground A .25 baseline | `docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz`; unchanged |
| Current scene/control | `docs/checkpoints/spring_integration_v04/artifacts/` and `control_v03/`; saved-vector fixed comparison |
| Actual temporary owners | Checkpoint `placement_inventory.csv`, `artifacts/sites.json`, source/visibility ledgers |
| Primary R/S/U implementation | `src/datascape/vegetation/territorial_mid_far_v04.py`, inherited v01-v03 helpers; original runtime bytes |
| Matched replay contacts | This catalog's `fixtures/v04_supports.json`; authored raster-supported contacts, not measured stems |
| Historical far B | `scale_fields_v05.micro_field('F', ...)`; replay only, linkage unfinished |
| Terrain evidence | Existing `f2_painterly_layers_v01/fields.npz`, `f2_foreground_continuity_v04/retention_snapshots.npz`, `f2_painterly_composition_v03/fields.npz` under `docs/experiments/`; hashes in replay/reference records |

Keep the 600 x 900-mm composition, camera/DEM, two physical 300 x 900-mm panels,
foreground A .25, 70/30 retention, 2-mm bottom omission, accepted Tree v10 and
Rock & Ground v05, existing palette slots, source IDs and canonical A/B/C/D/V
semantics. A display copy may be tested later; no canonical terrain edit or
masking acceptance is implied here. Recommended terrain condition is overlay.

## Exact first steps in the next Work

1. Check out the published consolidation head; replay the saved Spring v04
   checkpoint using its `REPRODUCE.md`. Verify hashes and inspect existing
   middle/far crops and the temporary owner inventory before replacing anything.
2. Run the catalog CLI into a new output directory and the test suite. Compare
   six primary case digests and far micro evidence against `reference_vectors.json`.
   Treat the old contact positions as comparison fixtures, not accepted placement.
3. Use R/S/U as the default reusable mid/far vocabulary. Choose family roles
   and coherent supported passages; do not stack all three over the same roots
   or automatically import v05 A/C. Middle distance must not select B.
4. If studying optional B, restrict it explicitly to the far source-depth role.
   Develop linked structural ink and color at shared passage/support level,
   with related terrain direction, material density, openings and mist behavior.
   Inspect ink separately, color separately and combined. The current adapter
   refuses B because that implementation is missing. Shared linkage does not
   require a one-to-one duplicate mark pair, nor decide physical pass order.
5. Compare the unchanged full Spring scene with restrained and richer derived
   integration, at matched native crop scale and whole composition. Evaluate
   vegetation continuity, middle/far distinction, density/depth rhythm and full
   Spring color relationships. Carry the unresolved table in `DECISIONS.md`
   forward explicitly; saved-vector correctness does not resolve these choices.
6. Before making exact terrain attachment/occlusion claims, restore authoritative
   MASTER/VEG TIFFs and full-precision F2 fields/triangles as described by the
   checkpoint. Available evidence here is 1-mm float32 depth/XYZ and float16
   retention; only occupied-domain bytes match exactly. Label source-limited
   overlays honestly. Physically test tiny contacts and continuous color/ink
   passages before treating B as plotter-valid. Production G-code is a later
   separately authorized step, not part of this closure or replay.

This Work stops after consolidation, publication and reporting. It does not
start the next integration, redesign large forests, tune machine YAML, generate
production G-code or merge any PR. Broader unresolved Spring issues remain
visible rather than being silently declared solved.
