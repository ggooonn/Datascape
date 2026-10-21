# Calibration and operating procedure

## Measurements to enter before use

Copy `config/plotter_v03/profile.unmeasured.json` to a local machine/brush/media
profile. Candidate +10 paper hover, +32 station clearance and X800 Y900 Z32 park
are retained but are not approved as physically safe. The approximate 3-mm
paper-above-bed relationship and 50-mm Z capability are not measurement defaults.
No -3 bed plane, -12 compression, old negative station coordinates or current
installed YAML is inferred from historical files.

| Profile section | Required measurements / records |
| --- | --- |
| Machine | Actual FluidNC firmware and installed YAML SHA256; Cartesian kinematics; mounted brush and assembly identities; measured G54-to-MPos offset; expected initial WPos; usable XYZ bounds; axis rates, accelerations, steps/mm and junction deviation; swept-tool margin/free volumes/keepouts |
| Paper and travel | Actual paper surface above bed; first-contact work Z0; flatness and edge fixation; approach/hover/clearance; entire parking path and target reachability; wet departure/arrival distance/rate and allowable global acceleration |
| Brush response | Brush dimensions/mounting, medium and substrate; multi-knot intent/Z pairs; width, continuity, loading, feed, quality and recovery observations at selected physical depths; safe paper-contact Z range; pressure-Z speed limit |
| WELL_1 water / WELL_2 ink | G54 frame and contact volume; measured deep/shallow stone surface XYZ; maintained liquid reference Z; immersion, minimum stone gap, gradual exit height/feed/dwell; optional measured gentle agitation area; wash cycles and separate controlled-rewet immersion/dwell |
| Color slots | Used slot G54 XY, contact volume, manually maintained liquid Z, bottom Z/clearance, immersion, circle radius/revolutions/segments/feed/dwell/exit height; optional cross loading only after testing |
| PURGE | Replaceable absorbent geometry, surface Z, gentle compression/feed/dwell, optional contact repetition or short linear wipe; default has no circular rubbing |

`WELL_1=water`, `WELL_2=ink`, `PURGE=sponge/absorbent` are checked, not guessed.
The old station XY YAML remains reference-only with unknown coordinate frame.
Unused slots need no loading calibration to export a job that never uses them,
but all physical obstacles still belong in clearance measurements.

Profile status `measured` denotes a measured base machine/frame; individual
station and brush statuses remain unverified until their contact calibration is
completed. Ink-only painting checks the relevant ink profile/stations without
requiring unused color profiles. Separate profile copies may be retained per
brush, medium, paper setup and test condition.

## Stage evidence and authorization

Run `readiness` to obtain blockers and `preferred_evidence_scope_sha256` values.
After an actual test, append an operator record to `evidence`:

```json
{"check":"air_run","status":"passed","scope_sha256":"<reported scope hash>",
 "operator":"<name>","date":"<date>","method":"<what was measured/tested; result and retained record>"}
```

A record is current only for its dependency scope. Machine/frame checks bind
machine data; air/clearance/motion checks also bind motion and station geometry;
station/cleaning checks bind operation parameters; brush-response/contact checks
bind the curves and observations. Changing a knot invalidates brush evidence,
without automatically discarding unchanged machine/air measurements. Changing
geometry/offset/clearance invalidates the relevant broader scopes. A strict
whole-profile `calibration_sha256` evidence field is also accepted for compatibility.
No command automatically marks physical evidence passed.

Authorization is separate: fill the authorization template with the exact stage,
profile SHA256, plan SHA256, selected job IDs, operator/date and explicit approval.
The `plan_sha256` is printed by `prepare`; a calibration request uses its canonical
JSON digest. The profile hash is printed by `readiness`. Approval for air does
not approve calibration or painting. A profile/plan/job-set change requires a
new matching authorization. Keep registration/flatness checks current for each
installed paper; a historical pass is not a sensor reading.

## Commissioning without another backend rewrite

1. **Preparation only:** reproduce the accepted binding and S3a plan. No runnable
   Spring G-code is written. Review exact four job IDs and remaining blockers.
2. **Machine/frame/no-contact checks:** confirm actual configuration, homing,
   limits, E-stop, coordinate directions, available travel and measured collision
   volumes. Home outside this software, jog using OpenBuilds CONTROL, then set G54
   explicitly at the installed paper front-left and first brush contact. Archive
   `$#`, `$G` and status/WPos/MPos for operator comparison. Require zero G92/tool
   offsets and 100% feed override. No automatic macro or configuration change.
3. **Air stage:** explicitly authorize the selected no-contact job. All work Z
   stay at or above verified hover; no negative Z, dipping, washing or loading.
   Optional measured station XY can be toured at global clearance. Inspect the
   actual path, paper/fixture/head/holder clearances and park. Record the result.
4. **Small calibration stage:** use an explicit `calibration_plan` with selected
   station roles and/or a few `brush_lines` (`start_xy`, `end_xy`, `z_mm`,
   `feed_mm_min`). Target depths/volumes must be inside a measured test envelope.
   These isolated constant-Z tests do not change Spring Pressure Intent. Calibrate
   gradual stone withdrawal, palette loading and gentle absorbent contact. Measure
   width, continuity and recovery at small selected depths before selecting knots.
5. **Pressure profile selection:** retain thin low-intent marks, expressive middle
   behavior and optional stronger high-intent response only where physical tests
   support it. The actual family distribution is in the review JSON/table; sample
   A-family around its observed middle range and D/rock high range. The provisional
   .20/.40/.60/.93 regions are test organization, not fixed thresholds or depths.
   The largest Spring intent need not map to maximum compression. Record all
   chosen knots and matching observations. Do not infer -12 or -3 compression.
6. **Measured material tests:** test first post-load marks, contamination after
   ink/color and dark/light changes, loading distance/overrun and paper response.
   Water/animal glue/Marie's gouache recipe is a recorded test condition, not a
   firmware motion constraint. Liquid is manually restored to reference levels;
   there is no sensing or adaptive dipping.
7. **Painting stage:** authorize and export `P1_INK`, verify delivered files, then
   manually send only after checks. At start, M0 requires exact header offset and
   position confirmation. The job loads/reloads ink and parks. Review/dry manually.
   Authorize `P1_COLOR` separately; it requires paper/registration review, deep
   wash, absorbent contact, controlled rewet and manual contamination inspection
   before first pigment load. Later color changes repeat full washing; same-color
   replenishment only reloads. Repeat independently for P2 after registration.

Initial distances are color 1,000 mm and ink 2,000 mm, configurable. Only actual
XY drawing since the most recent active-material load accumulates. Load, wash,
material change and restart reset it. Finish a whole original source unit before
reloading; report overrun. Never split a canonical stroke to meet the threshold.
Manual palette refills and water changes are separate park/M0 checkpoints with
explicit intervals; no unlimited clean-water assumption or liquid volume model.

Semi-sized Xuan paper is initially edge fixed; any lightly dampened/stretch-then-
dry preparation must be inspected for flatness. Washing does not dry the paper.
At the final parked M0, acknowledge the review to finish M2 before starting another file; this acknowledgment adds no motion.
No automatic buckling detection exists. Do not resume after jogging, offset/tool
changes or reset; regenerate a reviewed complete-source suffix instead.

## What changes need code work?

Measured coordinates/depths, knot count/positions, substrate/brush/media records,
loading paths' existing parameters, feeds/hover/clearance/park, reload/checkpoint
intervals and physical pigment order are configuration/calibration work in v0.3.
No automatic v0.4 Work is required after a first test.

A new software feature would be needed for automatic liquid/warp sensing,
feedback pressure control, non-Cartesian kinematics, an installed controller with
an incompatible dialect/planner contract, a new station primitive absent from the
existing slope/circle/cross/absorbent options, or an evidence-driven PCHIP option.
A future shared continuous B/C job organization also needs an explicit policy
choice and focused exporter extension; current A split jobs are complete.
None of these optional extensions is a prerequisite for calibrated A printing.
