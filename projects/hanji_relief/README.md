# Hanji relief C — point-contact painting

This is an **independent raised hanji painting inspired by Ilwolobongdo**, sharing Datascape's plotter technology. It is not a modification of the Spring artwork or the Datascape landscape series. Printed supports and hanji application are complete; no new geometry, mesh or STL is generated.

The adapter implements constant **3.0mm additional Z compression from local first touch, a full1.00s dwell at depth, and same-color reload before contact31 after30 contacts**. The user preferred3mm/1s after the flat C2 comparison and subsequently requested30-contact refill. Dry-mark size and30-contact endurance on the relief are not measured. No normalized artistic pressure is used.

## Current operator-selected programs

The user confirms the bed/model datum, uses bed first-touch G54 Z10, and accepts5mm nominal relief clearance at fixed hover35. [Full assembly and physical P4 programs](runs/bed10_hover35_refill30_v01/) apply **first touch=designZ+10 / press=designZ+7**,3mm/1s/30contacts, with artwork nominal lower-left at existing G54 X0Y0. Station coordinates and controller/work-offset settings remain unchanged. P4 uses local XY and unchanged full-design Z. Use the spare P4 for the complete-panel trial; the full program includes all P4 points.

```sh
PYTHONPATH=src:. python -m projects.hanji_relief.run_export --output NEW_DIR
PYTHONPATH=src:. python -m projects.hanji_relief.run_export --verify NEW_DIR
```

The selected setup is recorded in `config/mounting.bed10_hover35.json`, separately from measured profiles. Numeric checks do not fabricate a local surface map, passed physical evidence or artwork completion. Two files are generated offline; the user operates the equipment independently.

## Backend dependency

- Base Draft PR: [#32](https://github.com/ggooonn/Datascape/pull/32), still open/unmerged when inspected on2026-10-25.
- Exact base SHA: `eda6069b12c8785d458a0e8a567a9a86980bc394`.
- Base branch: `spring/large-baegunmo-z10-hover20-v01`.
- Hanji branch: `feat/hanji-relief-stipple-v01`; the Hanji Draft PR targets the PR32 branch to show only this independent project.

The latest PR remained32 at inspection; no later PR was selected by number alone. No existing PR, Spring file, shared source, YAML or controller setting is modified. Shared code is imported from the repository rather than copied into this project.

Reuse is through production `Command`, `Profile`, motion/rate checks, serialization, atomic output, Cartesian timing, and PR32's `RuntimeBuilder` / `RuntimeMaterials` review sink plus `spring_end_cleanup.cleanup`. The sink is the existing **envelope-only numeric review route**; it does not fabricate physical evidence, measured free-space boxes or contact volumes. The shared official `Profile.require()` / `authorize()` / complete-path gates remain intact. `require_physical_export()` retains those gates and adds Hanji checks; the original CLI generates/verifies offline reviews; the separate `run_export` module generates the two operator-selected offline programs. Neither route operates equipment or fabricates measured evidence.

## Source and coordinate identity

`input/C_dots.csv` is the immutable6200-dot C artwork; physical P4 (archived source P04) contains890 dots and COLOR C4 contains253. This supersedes the older5826/849-point handoff. `study_dot_id`, colors, selected density, source/physical panels, global/local XY, design Z, ink-level comparison fields and historical2.8mm rendering diameter are preserved. `ink_level_id` creates no extra ink pass.

| Front view | Left | Center | Right |
| --- | --- | --- | --- |
| Top | P1 / source P07 | P2 / source P08 | P3 / source P09 |
| Middle | P4 / source P04 | P5 / source P05 | P6 / source P06 |
| Bottom | P7 / source P01 | P8 / source P02 | P9 / source P03 |

The full600×600 job uses global XY; the nine200×200 jobs use each panel's nominal outer lower-left. X right/Y up remains unchanged. No Y flip, mirroring, rotation, minimum-point XY origin, panel minimum-Z subtraction or extra Base2mm is applied.

`first_touch_Z = design_Z + hanji_surface_offset_z + local_surface_correction`

`press_Z = first_touch_Z − compression_depth_mm`

Mounting XY applies only to artwork points. Stations remain fixed G54 coordinates. The inherited measured/reference G54-to-machine translation is checked separately, not added twice to G-code coordinates. The GH height function is used only for nominal surface review and is unchanged. When needed, local panel XY maps back to its original global panel location before evaluating that function.

## Settings, ordering and material state

`config/stipple.json` is now the user-requested3mm/1s/30-contact configuration. Completed flat comparison files keep their original20-contact configuration. The previous relief20-contact delivery is retained unchanged under `review/nominal_offset0/`; the offset0 30-contact review is `review/refill30_offset0/`; current user-selected+10 programs are `runs/bed10_hover35_refill30_v01/`. See [registration and refill handoff](REGISTRATION_AND_REFILL30.md). Depth/dwell are constant across dots/colors and are not inferred from preview diameter or estimated1–2mm paper error.

Hanji's provisional eight-color extension is **C2 → A4 → A3 → D4 → C4 → B1 → C5 → B2**. It preserves the common Spring relative order but is not an official pre-existing eight-slot S3a order or a measured pigment-lightness order. Physical panel4 uses **C2 → A3 → D4 → C4 → B1 → C5**. Explicit color-to-station mapping uses the actual PR32 station entries, including B1/B2/C5. No color is omitted by filtering the twelve-slot Spring list.

Within each color: ascending occupied Y rows, first row right-to-left, then alternating X directions. Exact decimal CSV row positions are grouped without coordinate snapping. Left-first is configurable. Color changes restart from that color's lowest row. The full job does not traverse panels by physical number.

Every dot has independent fixed-XY approach, first contact,3mm compression, G4 dwell, controlled release, lift and completion events. No artificial short XY stroke, XY agitation or repeated dab is inserted.

`DotMaterials` keeps genuine drawing distance at0. Its explicit contact counter schedules same-color reload before31,61,… only when another dot exists. A color boundary replaces the old-color refill with wash/purge/rewet/new-color load. Contact-aware used-brush/pending-return state preserves PR32's used-return motion when distance is0. The state does not claim sensed pigment quantity. Station contact speeds, liquid geometry and wipe/lip routines retain their independent PR32 settings.

The terminal cleanup is appended **once after reaching PARK**, using the existing FROM_PARK IR contract: water3visits,10s/three agitation cycles each with existing withdrawal/shallow wipe/lip; sponge2contacts×4s; no final rewet/load; park800/800/35/M2. Each complete job independently expects start0/900/35. No routineM0, homing, G92 or setting writes are added.

## Numeric files and physical limits

[`review/refill30_offset0/`](review/refill30_offset0/) contains real G1/G4/M2 numeric files, not comment-only placeholders. They are **offline review artifacts, not machine-authorized or physically validated jobs**.

`config/mounting.unmeasured.json` retains unknown physical values as null. `config/review.nominal_offset0.json` is a separate explicit scenario: artwork XY0/0, surface offset0, no measured correction, fixed G54 hover35. It is not a claim that the object's back plane or brush first-touch is actually Z0. Never add the planar paper first-touch10 automatically or use the nominal file unchanged as a measured installation.

Ten main alternatives are `hanji_full_600x600.gcode` and `hanji_panel_01_local.gcode` through `hanji_panel_09_local.gcode`. The physical P4 full benchmark references the existing panel04 file, not a duplicated main job. Additional files:

- `hanji_panel_04_local_AIR.gcode`:890 planned points, simulated32-load/color-service XY at35; zero contact/dip/dwell, zero material-consumption/completion count. This is still an unapproved physical route.
- `hanji_panel_04_C4_first40.gcode`:first40 of the original253 C4 dots; initial supply plus one reload before31, none after40. The SVG labels1–40 and the30→31 boundary; observation CSV compares1–5,26–30,31–35,36–40.

The current axis reference is X0…860/Y0…900/Z−11…35 with separate station positions; the user's approximate800×900 painting workspace is not treated as the whole machine envelope. Artwork footprints fit the nominal scenario, while full brush/holder, fixture, station and transfer clearance still require actual review. Centerline envelope checks are not collision certification.

The unchanged height function has global design upper bound20, including Base2. The operator explicitly accepts5mm nominal clearance at hover35, replacing the earlier10mm criterion. At the selected+10 transform, the nominal highest first touch is30 and the gap is5mm. No limit, G54 or station position changes are used to create this gap. Panel4's dot maximum16.921111 is not used as a bound on the whole intervening surface. A separate2mm/90601-point nominal surface sample and its sampled panel maxima are delivered; sampled panel extrema are not certified continuous-surface suprema.

The operator-selected setup uses nominal outer-corner G54 XY0/0, bed first touch10 and fixed hover35 with accepted5mm nominal clearance. Actual local dry-surface deviations remain unmeasured rather than silently assigned a1-2mm correction. Brush mounting/station geometry and G54 remain unchanged by this update.

## Dwell semantics and timing

The shared serializer emits `G4 P1.000000000`. Source inspection of FluidNC **v4.1.1** confirms [GCode.cpp](https://github.com/bdring/FluidNC/blob/v4.1.1/FluidNC/src/GCode.cpp) multiplies P by1000 before calling `mc_dwell`; [MotionControl.cpp](https://github.com/bdring/FluidNC/blob/v4.1.1/FluidNC/src/MotionControl.cpp) synchronizes the planner before its millisecond dwell. Thus P1 is one second **after the preceding move completes**, not time spent during descent. This source version check is separate from proving the installed binary identity.

F7000 noncontact Z and F2000 controlled contact/compression/release are inherited/requested candidates.3mm at F2000 has0.09s constant-speed path time; finite acceleration and response mean it is not a measured3mm duration. Total physical contact exceeds the1s depth dwell.

The shared timing model uses configuration-reference XYZ acceleration1500/1500/1000mm/s², assumed JD0.01, full lookahead/continuous streaming. It reports noncontact XY/Z, controlled engagement, depth dwell, initial supply, same-color service/round-trip, color-change service/round-trip, terminal cleaning/park and stop-each-segment sensitivity. Finite streaming/buffers, step rounding, brush dynamics and actual point size are not verified. Current selected+10 program modeled totals are44.53min/P4 and279.52min/full, recorded in `runs/bed10_hover35_refill30_v01/verification.json`; previous offset0/30-contact review totals were3.61min/first40,47.17min/P4,297.84min/full; previous20-contact values were3.61min/first40,50.70min/P4,318.00min/full. Dwell alone is40s/890s/6200s. The30-contact full plan has209loads and seven color changes; physical P4 has32loads and five color changes.

## Reproduce and verify

From the repository root, Python3.10+; core generation needs only the standard library and the existing repository backend:

```bash
PYTHONPATH=src:. python -m projects.hanji_relief --output NEW_DIR
PYTHONPATH=src:. python -m projects.hanji_relief --verify NEW_DIR
PYTHONPATH=src:. python -m unittest discover -s projects/hanji_relief/tests -v
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_gcode*.py' -v
```

`--scenario PATH` selects an explicit numerical scenario, `--settings PATH` selects validated stipple settings. Existing output directories are never overwritten. All original numeric inputs are finite-checked; null/NaN/Inf are not silently replaced with0. Verification checks the complete manifest and regenerates all12 jobs from immutable source/settings/registration, including G-code, per-dot mappings, material schedule, saved trajectories and timing. A rehashed numeric mutation still fails regenerated readback. No official export or hardware transport is exposed by this CLI.

Open [`review/nominal_offset0/Hanji_C_Review.html`](review/nominal_offset0/Hanji_C_Review.html) for English repository review. A Korean user review is delivered separately. CSV/JSON records map source ID→execution sequence, source/physical panel, color, global/local/G54/machine XY, design/review first-touch/press Z, batch/contact number and service events. Actual measured first-touch fields remain blank.

## Confirmed continuation, not arbitrary-line resume

The first40 and full890 overlap. If they are actually accepted as completed on the same artwork/registration/conditions, supply a copy of `config/completion_record.template.json` with the true completion IDs and provenance. Its registration SHA256 binds the same scenario/mount/correction data. AIR or planned tests cannot complete dots; different conditions, IDs, duplicate IDs and registration changes are rejected. A recorded40-dot set yields850remaining dots in the original order, starting with a fresh load and independent start/finish. No850 file is pre-authorized or fabricated now.

```bash
PYTHONPATH=src:. python -m projects.hanji_relief \
  --scenario ACTUAL_RECORDED_SCENARIO.json \
  --completed-record CONFIRMED_COMPLETION.json --output NEW_REMAINING_REVIEW
```

The full global and individual-panel files are alternative workflows, not sequential programs. Do not run the full/full-panel files unchanged after accepted artwork test contacts.

## Verification and handoff

Latest operator-program verification:33Hanji tests and19flat tests pass. Both generated programs regenerate/read back with the selected+10 transform, fixed35hover and5mm accepted nominal gap. Existing immutable source, flat comparison, shared backend and historical review directories remain byte-identical. See `provenance/bed10_hover35/` for current evidence.

The original22 Hanji regression tests retain an explicit20-contact fixture; six additional tests cover the30-contact default,29/30/31/59/60/61 boundaries, color reset, unchanged coordinates/order, serialized30→31service and bed-touch10 registration. Original coverage: counter0/1/19/20/21/40/41, color-end multiples, bottom-up/left-right ordering, exact C/panel union, immutable source,3mm/1s explicit primitives, readback tampering, fixed stations under artwork movement, used-brush distance0, AIR separation, terminal cleanup once, finite values, registration/limits and confirmed850 continuation.

Existing backend regression discovery ran217 tests:215passed, two conditional full-Spring artifact/input tests skipped because their optional bound inputs were not supplied. Shared backend and Spring files are byte-unchanged. The12delivered jobs are independently regenerated/parsed and preserve configured bounds/feed limits, material events and park/M2. Neither physical readiness, actual streamed bytes, measured dot diameter,30-contact material endurance nor collision-free operation is inferred. No machine is connected, transmitted to or operated. All PRs remain unmerged.
