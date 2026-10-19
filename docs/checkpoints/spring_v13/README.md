# Spring v13 interim production-development vector baseline

The user approved `v13_recovered_candidate` on 2026-10-20 as the first vector
baseline for initial plotter development. **No further artistic refinement.**
This is an interim development checkpoint, not physical artwork completion,
calibrated brush pressure or approval of executable machine G-code.

The user independently compared the recovered PNG with
`image(20261019-044435).png`: both 1200x1800 RGBA arrays are identical. This export
also reproduces the approved recovered PNG exactly from exported XY and retained
artistic display metadata. **Visual identity is verified; exact identity with
the lost historical v13 vector source remains unproven.** See approval.json.

## Canonical data and distinct representations

| Representation | Repository path | Meaning |
| --- | --- | --- |
| Final visible ink | `artworks/spring_v13/visible_ink.json.gz` | 3,345 complete rich records, exact approved bytes |
| Final visible color | `artworks/spring_v13/visible_color.json.gz` | 11,606 complete rich records, exact approved bytes |
| Editable/replay sources | `artworks/spring_v13/source/` | Frozen v12 replay control, authoring records, decisions, exact numeric F2 fields and original configs |
| Machine contract | `artworks/spring_v13/machine/spring_v13.offline.machine_vectors.json.gz` | All 14,951 paths, explicit offline placeholder for unresolved pressure |
| Machine/artistic linkage | `artworks/spring_v13/machine/metadata.json.gz` | Per-ID source record, role, channel, pressure provenance and width flags |
| Approved image and SVGs | `artworks/spring_v13/review/` | Nonplotting review only; profiled ink/color/combined SVGs are gzip compressed |

XY is continuous **600x900 mm**, top-left artwork origin with Y downward, exactly
as the approved source. No panel split, 40 mm exhibition gap or machine offset.
No IDs, vertices, slots or pressure samples are regenerated during export.

Source generation-time status labels remain byte-preserved historical metadata.
The current approval is approval.json; those old labels do not withdraw approval.
The recovered source/config code is retained unchanged; only new checkpoint and
export code is added. Historical v09-v13 comparisons remain in the preserved Work
and Library archives, not duplicated as large HTML/PDF/ZIP archives in Git.

## Pressure and brush information

- 675 color paths / 8,975 points retain original normalized pressure intent.
- 3,345 ink plus 10,931 color paths lack original normalized pressure: 14,276
  paths / 231,999 points. The offline machine file explicitly uses **0.5**, never
  the PR23 loader's implicit default. Metadata labels every affected ID.
- The adapter fails unless both `--offline-only` and an explicit
  `--unresolved-pressure` value are supplied. Rich canonical records keep the
  original absence. No width/alpha-to-pressure or pigment conversion is made.
- All 11,606 color and 2,725 ink paths retain width profiles in rich records.
  These profiles are not a calibrated brush/Z transfer function. The contract
  cannot carry full widths, alpha, material behavior, wash/reload, dwell or wet
  timing; those remain in the rich data or explicitly unresolved.
- No single-point or zero-length primitive occurs. Two positive-length
  polylines shorter than 1 mm and 4,572 expressive-width color paths are flagged
  per ID. They are preserved, not converted to dots or dropped. Physical fidelity
  of tiny marks and broad brush strokes remains a Backend/calibration task.

## Conservative ordering

Original vertex direction is locked. Every stroke sets `reorderable=false` and
`reversible=false`. The original full array order is preserved as sequence, with
ink and the original A/C/rock_soil/gestures/trunk/RSU color phases as order_group.
This preserves existing drawing/visibility precedence; it does not certify the
physical wet sequence, station changes or painting time. No optimizer runs here.

## Reproduction and separate Backend Work

See [REPRODUCE.md](REPRODUCE.md), [VALIDATION.md](VALIDATION.md) and the exact
[Plotter Backend handoff](PLOTTER_BACKEND_HANDOFF.md).
PR dependency remains #16 -> #18 -> #19 -> #20 -> #21 -> #22 -> this checkpoint.
PR #23 stays independent and unmodified. Base is `feat/mid-far-vegetation-consolidated`
at `1c798a7fd8becdf530b338260447e20e36f6b31d`, not the Backend branch or main.
No parent PR is merged or rewritten. Keep this checkpoint as a Draft.
