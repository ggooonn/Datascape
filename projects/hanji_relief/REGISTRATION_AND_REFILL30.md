# Bed registration, physical panel labels, and thirty-contact refill

## Current decision and preserved experiment

The operator completed the flat330mm C2 comparison and reported that3mm compression with1s full dwell at depth looked best. This is a qualitative preference on flat paper, not a measured diameter or proof of relief contact uniformity. The operator now requests refill every30completed paper contacts. No test of30-contact pigment endurance is claimed.

Current relief settings are3mm /1s /30contacts in `config/stipple.json`. Supply once at the start of each color, then reload the same color before31,61,... only when another point exists. Color changes wash/reset/load the new color instead of adding an old-color reload. Station contacts and travel do not count. Motion, pigment recipes, point order, source IDs, design heights and artwork remain unchanged.

The completed flat comparison under `benchmarks/flat_c2_330_v01/` remains20+20contacts and is preserved byte-for-byte. The previous20-contact relief review under `review/nominal_offset0/` is also preserved. The new30-contact review is `review/refill30_offset0/`; its mounting scenario remains explicit offset0, not the bed-touch10 candidate below.

## Physical panels and colors are separate identifiers

Use **P1-P9 for physical panels in front view**, top-left to bottom-right. Retain original source-panel identifiers as separate archival data. They must never be inferred from a short P label without its physical/source context.

| Front view | Left | Middle | Right |
| --- | --- | --- | --- |
| Top | P1 / source P07 | P2 / source P08 | P3 / source P09 |
| Middle | P4 / source P04 | P5 / source P05 | P6 / source P06 |
| Bottom | P7 / source P01 | P8 / source P02 | P9 / source P03 |

**C2 and C4 are COLOR IDs, not panel IDs.** `hanji_panel_04_C4_first40.gcode` means physical P4, color C4, first40points. `hanji_panel_04_local.gcode` means the complete890-point/six-color physical P4. Existing machine-readable filenames and immutable source IDs remain stable. New full-layout previews show `P1 / source P07`, etc.

## What bed touch at G54 Z10 means

The operator proposes mounting the brush so it nearly touches the bed at G54 Z10. If that bed is exactly the relief model's lower datum, its physical height is0mm while the controller still reads G54 Z10. These are different frames; no G92 or work-offset write is needed or added.

Let `B` be the measured G54 Z for first brush-tip touch at the installed model's design-height0 datum. With unchanged brush mounting:

`first_touch_G54_Z = B + z_design_mm + surface_delta_mm`

`press_G54_Z = first_touch_G54_Z - 3`

If `B=10` and local correction is0, the illustrative values are:

| Design height above installed model datum | First touch, G54 Z | Press by3mm, G54 Z |
| ---: | ---: | ---: |
| 0 | 10 | 7 |
| 10 | 20 | 17 |
| 20 | 30 | 27 |

The source20mm ceiling is measured from the source model datum and **already includes Base2mm**. Do not add another2mm. Actual dry hanji deviations remain separate; the user's expected1-2mm is not a measured correction.

Flat paper touch at10 and bare-bed touch at10 are not automatically identical: paper thickness, backing, fixtures and installation height change the datum. Likewise, nearly touching is a preliminary setup observation, not a recorded exact first-touch calibration. Record one actual first touch at a known design-height point on the mounted P4: `B = measured_touch - design_height - measured_local_delta`. Several points are needed to assess local variation. A flat comparison cannot establish this relief registration by itself.

`config/review.bed_touch10_candidate.json` records the conditional +10offset interpretation only. It is not measured registration, does not change the default scenario and has no generated run-approved program. Existing offset0 review G-code does **not** include this +10.

## The remaining Z35 clearance conflict

The unchanged configured upper G54 reference is35. At B10, the whole artwork's design ceiling20 gives highest nominal touch30, so fixed hover35 provides only5mm. The retained target is10mm; the nominal target would require hover40, outside the current35reference. No controller limit, G54, station height, brush mounting or clearance target is changed to conceal this gap.

Physical P4 has a17.262494mm sampled surface maximum at the original2mm sampling. With B10, that gives about7.74mm at hover35, also below10mm. This is a sample, not a certified maximum, and selected-dot maximum16.921111 is not a bound on the intervening surface. Fixtures, full brush/holder width and local dry-paper deviations still matter.

Before moving from a P4 test to full assembly, reconcile actual installation height and available physical travel/clearance. Lowering the mounted work can increase the physical gap if hardware permits; it requires a newly measured datum. Altering brush mounting also changes station contact geometry and requires separate reconciliation. Coordinate relabeling alone creates no gap. No equipment movement, homing, setting write or transmission is performed here.

## Reproduce and verify

```sh
PYTHONPATH=src:. python -m projects.hanji_relief --output NEW_REVIEW_DIR
PYTHONPATH=src:. python -m projects.hanji_relief --verify NEW_REVIEW_DIR
PYTHONPATH=src:. python -m unittest discover -s projects/hanji_relief/tests -v
PYTHONPATH=src:. python -m unittest discover -s projects/hanji_relief/benchmarks/flat_c2_330_v01/tests -v
```

Thirty-contact plans: P4 has890contacts/32loads/26same-color reloads/five color changes; full assembly has6200contacts/209loads/201same-color reloads/seven color changes. Numeric files are offline review artifacts. Original20-contact completion ledgers are not fabricated, and no flat test contacts are counted as artwork completion.

Source head before this update: `f6aa986bd9580f6bb4af67da663656b9a8e5d021`. Shared PR32 base remains `eda6069b12c8785d458a0e8a567a9a86980bc394`. All changes stay on `feat/hanji-relief-stipple-v01`/Draft PR33; no merge or force-push.
