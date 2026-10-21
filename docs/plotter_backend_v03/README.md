# Plotter Backend v0.3 — calibrated S3a printing pipeline

Based exactly on Backend PR #26 `7047db4d45ba0c3ca950002fe2d43c061699c627`.
This is an implemented offline G-code exporter, not a controller connection.
The preferred first physical workflow is Layout D: `SHARED_INK` and
`SHARED_COLOR` over the continuous 600x900-mm composition. Layout A retains
`P1_INK`, `P1_COLOR`, `P2_INK`, `P2_COLOR`, mounting each 300x900-mm panel
independently at the same G54 paper origin. Actual Spring machine jobs remain
blocked by missing measurements and stage authorization. Earlier PR #23-#26,
artwork and accepted pressure remain unchanged; no installed FluidNC
configuration, homing setting or work offset is changed.

## Start here

- [Reproduce and export](REPRODUCE.md)
- [Measurements, calibration and operating procedure](CALIBRATION_AND_OPERATION.md)
- [Controller behavior and implementation contract](ARCHITECTURE.md)
- [Executed software results and remaining limits](RESULTS.md)
- [Unmeasured reusable profile](../../config/plotter_v03/profile.unmeasured.json)
- [Stage authorization template](../../config/plotter_v03/authorization.template.json)
- [Small calibration request template](../../config/plotter_v03/calibration_plan.template.json)
- [Synthetic ink example](review/P1_INK.synthetic.example.txt) and
  [synthetic color example](review/P1_COLOR.synthetic.example.txt), all lines
  commented; invented test fixture, never a machine setup.

## Implemented behavior

`src/datascape/gcode/production/` is additive. The v0.2 Level-1 preview API and
its explicit output restrictions are unchanged. Production reuses its immutable
`Stroke`, accepted adapter/binder, original-segment clipping, `Layout`, `Fragment`,
`WorkToMachine`, `MotionSettings`, `stroke_events`, and `BrushCalibration`.

The exact previous S3a permutation was recovered and verified from the v02 ZIP.
`config/plotter_v03/spring_s3a_order.json` binds that permutation to the accepted
machine payload, pressure sidecar and ordered IDs. A hard-coded sequence digest
also rejects reference tampering. This is an experimental **execution** policy;
canonical `sequence`, geometry, directions, widths, colors and pressure stay
locked. The previous 15,220 inferred-dependency violations remain disclosed; no
new artistic protection or sequencing study is performed.

Default slot order is C1, D1, A2, D2, C2, A4, A3, A5, C3, D4, C4, D5. Each used
slot occurs in one batch per color job. Within-color routing retains the previous
S3a directed optimization, with no stroke reversal. A later measured physical
pigment order can be supplied through `material.color_order`: it must contain
exactly the twelve used IDs, changes only batch order, and creates a different
plan hash requiring explicit review/authorization. It does not regenerate art.

The exporter plans actual G54 drawing, station operations, lifts, approaches,
release, clear travel, washing, loading, dwells and final park. Standard jobs
have **zero M0** commands. Pre-run checks are recorded before execution.
It uses feed-controlled G1 XYZ lines, G4 and M2. M0 is reserved for explicit
calibration tests or optional operator-enabled periodic checks. It never issues G10, G92,
G53, homing, configuration writes, spindle commands or per-move acceleration
settings. It selects G54 without setting it. Operator verification must occur
BEFORE starting the program; G-code alone cannot query or conditionally verify offsets.

All jobs must pass their stage gate, current calibration evidence, whole-segment
machine-envelope/keepout/free-corridor checks, brush domain/context checks,
axis-rate constraints, IR/G-code read-back and exact source-sample checks.
All selected files are staged and atomically installed together. Failure leaves
no final partial job directory. Existing output directories are rejected.

## Readiness levels

| Level | Output | Required gate |
| --- | --- | --- |
| Offline preparation | Full plan, pressure/fragment/source validation and blocker report; no executable Spring file | Exact pinned inputs and S3a reference |
| Synthetic fixture | Comment-only examples exercising the real serializer | Synthetic fixture status; real Spring sidecar-bound paths rejected |
| Air | No-contact `.nc`, all work Z at or above measured paper hover; no dipping/loading/washing | Measured machine/frame/motion/clearance evidence and explicit air authorization |
| Calibration | Small requested station or constant-Z brush test `.nc`; no automatic Spring pressure replacement | Passed air gate, measured safe contact volumes, explicit test depths/parameters and separate calibration authorization |
| Painting | Separate ink/color `.nc` with measured pressure mapping and material handling | Relevant measured brush/station profiles, physical test evidence and explicit painting authorization |

`readiness` checks structure and evidence; it never grants authorization or
certifies hardware safety. All pass records are operator evidence, not sensed
state. Export remains offline; manual sending is outside this Work.

## A/D physical workflows and automatic material handling

D uses one full-width path per original stroke: X=300 is not a clipping boundary.
It supports a continuous 600x900-mm sheet or two tightly adjacent 300x900-mm sheets.
Set `machine.substrate_assembly` to `continuous_sheet` or `adjacent_panels`. The
latter requires current `continuous_seam` physical contact/clearance evidence;
no gap, seam lift, reload or artificial interruption is inserted. The complete
Spring D plan and read-back retain 14,951 strokes / 240,974 original samples.

A remains available with four independently registered panel/medium jobs. B/C
remain existing planning alternatives; physical B/C serialization stays blocked.
No additional B/C printing policy or geometry change is introduced.

Default reloads are **ink 1,000 mm / color 800 mm**, independently configurable.
Color can later be raised to 1,000 mm through its profile. Same-material reloads
are automatic at the next intact source boundary without washing. Different
colors automatically wash -> centered PURGE contact -> controlled rewet -> load.
Periodic manual refill/water-change intervals default to `null` (disabled).
The operator prepares adequate supplies, a clean brush and water before each job.
Color starts from that confirmed prepared state, without redundant initial wash.
End cleanup defaults to false; jobs park and terminate with M2, without M0.

[Current A/D counts and conditional cost recalculation](RESULTS.md) distinguish
exact material counts from unverified station/time assumptions. All stage,
calibration and collision gates remain active; no real Spring G-code is emitted
with missing calibration or pre-run authorization.
