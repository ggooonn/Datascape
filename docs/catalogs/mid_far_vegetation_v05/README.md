# Mid/Far Vegetation v05 — provisional closure

This closes the existing Mid/Far Work for a separate Spring integration Work.
It does not begin scene integration, large-forest refinement or production.
The revised [decisions](DECISIONS.md) and
[integration policy](../../../configs/vegetation/mid_far_integration_handoff_v05.json)
supersede earlier recommendations, including the private v05 suggestion to
continue with C. Historical A/B/C labels never imply current acceptance.

| Result | Current role |
| --- | --- |
| R / radial crowns | Primary reusable mid/far vocabulary |
| S / shared canopy surfaces | Primary reusable mid/far vocabulary |
| U / jointed leaders | Primary reusable mid/far vocabulary |
| v05 B / surface micro texture | Far-only optional provisional candidate; disabled by default |
| v05 A / forest field, C / combination | Deferred; not accepted for general use |

The R/S/U vocabulary is reusable; saved placement, mass continuity, scales and
the full Spring scene are not approved by that statement. Select a family for
a passage rather than stacking all three over identical supports by default.

## B: ink and color together

B must be developed as a coherent far-vegetation layer with linked ink and
color behavior. Shared passage/support identity, source-depth profiles, terrain
flow, density rhythm, open intervals and mist transitions should relate the
passes. This need not mean duplicate ink/color centerlines or a mark-for-mark
pair, and does not prescribe uncalibrated station order or wet-on-wet timing.

The v05 micro evidence already has palette-colored marks. The sparse ink in
the v05 B scene belongs to its shared medium groves; it is **not a linked ink
pass for the micro layer**. That linkage is not implemented here. No isolated
black-only B layer, disconnected color overlay or middle-distance B solution
is recommended. The small selection adapter fails closed for B until the next
Work implements and reviews the required relationship.

## Compact review evidence

| Version | Selected evidence | Reason retained |
| --- | --- | --- |
| v01 | [Mist geometry](evidence/v01_mist_geometry.png) | Geometric selection and omission, rather than alpha alone |
| v02 | [Ink / color](evidence/v02_ink_color.png) | Growth scaffolds and separate structural/material roles |
| v03 | [Family comparison](evidence/v03_families.png) | R/S/U distinction and historical development |
| v04 | [Construction](evidence/v04_construction.png), [occupation](evidence/v04_occupation.png), [color](evidence/v04_plant_color.png), [palette](evidence/v04_palette.png) | Primary vocabulary, territorial/cluster controls, original material slots |
| v05 | [Scene comparison](evidence/v05_scene_deferred_AC.png), [scale comparison](evidence/v05_scales_deferred_AC.png) | B candidate and deferred A/C limitations, including the historical middle B trial |

The v05 sheets retain their original middle-distance B trial as historical
evidence only. It is excluded from the recommendation. No additional visual
refinement was performed for closure. The six native SVGs in `native/` are
replays of the exact retained v04 middle/far R/S/U vectors, without the terrain
context, at artwork millimeters. Case A means the historical middle crop;
case C means the historical far crop. These crop IDs differ from v05 A/B/C.

## Reuse and reproduction

Five runtime modules retain original source bytes. One catalog CLI and a small
extracted review-helper module replace six whole-study renderers. Five small
historical configs remain for runtime/test provenance; their old output paths
are not required by this CLI. All required inputs are tracked here or inherited
from the Spring checkpoint; no private `outputs/` restore is needed.

```bash
python -m pip install -e '.[research,dev]' Pillow reportlab pypdf
PYTHONPATH=src python -m datascape.rendering.mid_far_catalog --output outputs/mid-far-replay-new
PYTHONPATH=src python -m pytest -q
```

Use an empty new output directory. The default CLI writes six primary SVGs,
primary raw/visible vectors, and **far-only historical color micro evidence**.
It does not enable B in Spring or create the missing linked ink pass.
For exact historical A/B/C reproduction only, add `--include-deferred-v05`.
That explicit history option retains old middle micro trials and A/C; it is not
the recommended integration plan. Compare replay digests with
`reference_vectors.json` and read [validation](VALIDATION.md).

Original study branches and complete private v01-v05 reviews remain preserved.
`archive_manifest.json` records original source/output signatures. Repeated
panel renders, private reference paintings, pending files, HTML/PDF/ZIP/bundle
duplicates, large vector archives and obsolete study runners are not included
in this PR. Historical source commit hashes are provenance, not claimed remote
branches. This is a bounded consolidated snapshot above the checkpoint.

Read [Spring handoff](SPRING_INTEGRATION_HANDOFF.md) before starting the next Work.
