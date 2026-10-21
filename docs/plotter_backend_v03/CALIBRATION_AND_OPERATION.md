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
| PURGE | Nominal center X840 Y137.5 and area 70x70 mm; confirm actual G54 center, contact volume and surface Z. Default is one centered vertical gentle contact/dwell/retract, without XY wipe or rubbing. Optional material_overrides can calibrate ink/color/slot compression and dwell. |

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
   Spring G-code is written. D is preferred with two shared jobs; A retains four
   separate panel jobs. Review the selected IDs and remaining blockers.
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
7. **Painting stage:** confirm all pre-run conditions, authorize/export the chosen
   job, verify the delivered files and then start it. D uses `SHARED_INK`, followed
   by manual review/drying/preparation and `SHARED_COLOR`. A uses `P1_INK`,
   `P1_COLOR`, `P2_INK`, `P2_COLOR`, re-establishing the same paper origin for P2.
   Each program automatically loads/reloads, draws, parks at the validated target
   and terminates with M2. Standard programs contain no M0.

Before EACH job, complete `authorization.pre_run_confirmations[job_id]`:
`coordinates_and_start_verified`, `paper_and_clearance_verified`,
`tool_and_controller_state_verified`, `brush_clean_and_prepared`, and
`materials_and_clean_water_prepared` must be true. Color also requires
`ink_dry_and_registration_verified`; D requires
`continuous_substrate_or_tested_seam_verified`. These are explicit operator
records, not automatic sensing. Air requires the first three common checks.
Stage/profile/plan/job-bound authorization and measured evidence remain mandatory.
Reconfirm conditions immediately before sending; an old record does not observe
current controller or paper state. There is no startup pause to correct mistakes.

For D, set `machine.substrate_assembly`: `continuous_sheet` or `adjacent_panels`.
The adjacent-sheet choice additionally requires a current `continuous_seam`
physical contact/clearance evidence record. Test edge alignment, flatness, fixture
and brush passage before enabling unsplit contact across X=300. No seam lift or
stroke split is synthesized. B/C remain planning-only.

Between separate ink and color executions, manually clean/inspect the brush,
replace water, replenish palette materials, confirm drying, registration and G54.
The color job begins from that prepared state: it loads its first pigment without
an additional initial wash or inspection pause. Automatic full washing, centered
PURGE absorption, controlled rewet and loading remain BETWEEN different colors.

Initial distances are **ink 1,000 mm and color 800 mm**, independently configurable.
A later color trial can use 1,000 mm. Only actual XY drawing since the most recent
active-material load accumulates. Load, wash, material change and restart reset
it. Finish a whole original source unit before reloading and report overrun;
never split a source or wash merely to reload the same material.

`manual_refill_every_loads` and `water_change_every_washes` default to `null`, so
routine work never waits for manual refilling. Prepare enough pigment and cleaning
water before starting each job. Any safely arranged replenishment is external;
there is no sensing, depletion model or adaptive dipping. Positive integer values
explicitly enable optional park/M0 checks after the specified completed operations,
without adding a first-load/startup pause. Their exact reasons/counts appear in
export metrics and independent read-back. `end_cleanup` defaults to false; true
adds automatic final washing before parking, with no mandatory final M0.

Semi-sized Xuan paper is initially edge fixed; inspect any dampened/stretch-then-
dry preparation for flatness. Washing does not dry the paper. No automatic
buckling detection exists. After jogging, offsets/tool changes, reset or a partly
printed stroke, abort and regenerate a reviewed complete-source suffix. Reconfirm
the prepared brush/state before restart; partly printed sources repeat from their
beginning, so review possible overpainting first.

Explicit calibration programs retain inspection stops: startup (1), before/after
each station test (2 per role), before each brush line (1 per line), and final
recording (1). Thus M0 count is `2 + 2*station_roles + brush_lines`; the one-station,
one-line test has 5 M0, with all reasons recorded. These are manual calibration
programs, not the zero-M0 standard ink/color printing jobs.

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
choice and focused exporter extension; current A split and continuous D jobs are complete.
None of these optional extensions is a prerequisite for calibrated A/D printing.
