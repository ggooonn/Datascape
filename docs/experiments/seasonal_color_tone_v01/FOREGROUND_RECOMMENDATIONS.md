# Limited foreground differentiation using existing libraries

These are concrete proposals for a later geometry Work. None has been generated or applied here. Retain seasonal cameras, middle/far contours, panel footprints and the useful existing support groups; intervene in one dominant/subordinate grouping at a time.

## Summer — proposed, not applied

**Vegetation:** Make B the continuous overhanging bank body and U a low connected underlayer; retain P as a counter-accent rather than repeating three upright groups.

**Rock:** Replace one upright jointed plinth with lower compact/rounded base_mass and partly buried layered bedrock; keep B-type supporting masses unequal.

**Ground:** Use a low shared bank and connected color support, retaining the diagonal passage rather than a separate pedestal below every tree.

Existing controls: `tree_final_scale.make_tree(form="B", architecture="terminal-droop") for one supported bank member`; `P/B/U posture, stem_ratio and vigor; keep U small/light`.

Entry points: `datascape.vegetation.tree_final_scale.make_tree`, `datascape.ground.structural_detail_v05.base_mass(form="compact", regime="rounded")`.

## Autumn — proposed, not applied

**Vegetation:** Break one B crown episode with dead-limb or damaged-crown; retain unequal P/B remnants and reduce the repeated center-relay silhouette.

**Rock:** Expose angular/layered ledges and fewer unequal blocks, rather than only enlarging the same jointed-parent/layered-front B recipe.

**Ground:** Use broken bedding/contact cues and an asymmetric terrace; separate dry exposed ground from retreating canopy color.

Existing controls: `accent="dead-limb" or "damaged-crown" on selected P/B/U members`; `Unequal vigor and stem_ratio; no new botanical family`.

Entry points: `datascape.vegetation.tree_final_scale.make_tree`, `datascape.ground.structural_detail_v05.base_mass(form="angular", regime="layered")`.

## Winter — proposed, not applied

**Vegetation:** Keep one P shelter and an incomplete B skeleton, using broken-top or suppressed accents selectively; make the small P8 remnant subordinate to its long rest.

**Rock:** Use one coherent A-style bedrock mass plus a few subordinate stones instead of three similar B plinth formations.

**Ground:** Expose a broad structural plane and isolated contacts. Preserve P8 terrain, skyline and gentle ending.

Existing controls: `accent="broken-top" or "suppressed" only on selected members`; `Retain pine foliage; do not make every tree uniformly bare`.

Entry points: `datascape.vegetation.tree_final_scale.make_tree`, `datascape.ground.structural_detail_v05.base_mass(form="bedrock", regime="jointed")`.

## Library bounds and review sequence

Use Tree v10 accepted P/B/U anatomy. W remains experimental; no W promotion or generation is included. Existing accents include bent, broken-top, suppressed, dead-limb and damaged-crown. `terminal-droop` is an existing architecture option, not a new species. Use posture, vigor and stem ratio to vary the group; the foliage unit-count control supports 1.0–1.5 rather than arbitrary reduction, so reduction should use supported vigor/architecture and scene omission. Do not treat every Autumn or Winter member identically.

Rock v05 `base_mass` already supports compact/angular/bedrock and layered/jointed/rounded regimes. Its bounded multi-mass `FormationControls` support unequal dominance, overlap, burial and orientation. For existing B formations, keep dominance 0.6–0.8, overlap 0.1–0.4 and burial 0–0.35. A coherent A-style rock means a scene arrangement around a supported bedrock parent; it is not a new generator mode.

For the next geometry review, change one Summer bank grouping, one Autumn retreat/ledge episode, and one Winter shelter/plane episode, then compare their shared ground, burial, overlap and foreground silhouette at full pair scale. Avoid replacing every group. Color territories should bind the resulting forms, not hide unresolved ground contact.

Sources: `docs/catalog/tree_v10/{README.md,DECISIONS.md}`, `docs/catalog/rock_v05/{README.md,DECISIONS.md}`, `src/datascape/vegetation/tree_final_scale.py`, `src/datascape/ground/structural_detail_v05.py`, and `studies/seasonal_composition_v03/recipes.py` at the pinned PR38 commit.
