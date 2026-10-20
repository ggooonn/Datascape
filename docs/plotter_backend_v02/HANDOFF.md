# Brush calibration and future Air Run handoff

## Current executable boundary

Only Level 1 is implemented. `require_output_level(2)` and `(3)` raise.
There is no serial/HTTP controller client, live command path, executable exporter,
station-contact trajectory implementation or automatic homing/config write.
Commented review files are not machine jobs. The legacy v0.1 CLI remains a
comment-only prototype and is not the v0.2 production pipeline.

Pressure is accepted artistic intent. All physical Z, brush width, wetting,
gouache darkness/viscosity, speed response, clearances and usable Z remain to be
measured. Future configuration changes must not overwrite original pressure.

## Brush profile and experiments

`BrushCalibration` separates brush ID/family/type/dimensions/mounting,
medium/substrate/surface height, hardware/date, observations and nonlinear
pressure→work-Z knots. Each observation records tested Z, measured width,
feedrate, water/pigment loading, continuity, quality and notes. A measured profile
requires observations, date and surface height, increasing intent knots and
nonincreasing nonpositive compression. Unsupported pressure fails; no domain
clamping/extrapolation or universal percentage mapping.

The supplied `SYNTHETIC-NOT-A-BRUSH` profile is only a display scale. Its
compression and hover/approach values are neither recommendations nor safe limits.
`calibrated_z_mm` and `machine_xyz` remain null throughout the actual Spring run.
A future measured profile can supply calibrated work-Z interpretation offline;
this alone never authorizes physical output or establishes a machine envelope.

The generated benchmark sheet includes constant-depth straight lines and curves,
a gradual ramp, artistic entry/exit taper, alternating changes, 0.1/0.5/2-mm short
paths, a long continuous path, repeated feedrates, ink/color comparisons and
low/ordinary/high loading conditions. Physical first-contact and release motions
remain separate from the benchmark's artistic endpoint pressure. Constant-depth
patterns retain pressure samples rather than overwriting them.

Use the recording template to measure actual visible continuity at low intent
around 0.22, ordinary behavior at 0.4–0.6 and stronger marks at 0.8–0.93. Establish
brush- and medium-specific curves within measured safe Z, never map 0.93 directly
to -12 mm. Preserve the known family-clipping/flatness limitations for review.

## Stations and interruptions

`StationConfiguration` requires measured G54 coordinates/clearance plus explicit
well roles before treating station data as measured. Even such a record cannot
produce contact motion in this Work. The old unverified YAML is reference only.
No station coordinates are consumed by the Spring simulation.

Current logical sequence candidate for a material/color change:
wash → sponge wipe → controlled rewet → load. Initial loading follows a manual
brush-condition check. Same-color replenishment is a separate event. Physical
agitation, dipping depths, water transfer, wipe pressure and contamination effects
are unresolved. Distance thresholds are assumptions (ink1,200/color600 mm) and
are deferred to the next intact fragment; they never break an accepted stroke.

Automatic brush replenishment is separate from manually refilling gouache wells
from pre-diluted bottles. Optional load-count refill pauses are synthetic, not a
well-volume model. Real well depletion and station travel cannot be estimated
without measurements. Simulated brush state tracks material, accumulated drawing
distance and uncertain water/pigment condition; a simulated interruption discards
loaded-state confidence and requires resume preparation and manual condition
inspection/reloading. This is not a physically verified restart procedure.

The source order causes thousands of material changes. See RESULTS before
adopting a wash-after-every-change policy. Any grouping of colors, reordering,
path reversal or new multi-brush strategy requires separate artistic review;
v0.2 does not enable such optimization.

## Measurements before future work

1. Complete assembly; measure actual X/Y/Z usable travel and end margins with
   installed head/brush, substrate and stations. Approximately 50 mm Z is provisional.
2. Validate each limit switch, motor direction, reliable homing, stopping distance,
   E-stop and recovery. Archive the actual installed, corrected V2.2 configuration.
   Keep old GitHub YAML separate. Do not auto-increase homing seek speeds.
3. Establish physical panel front-left registration and G54 X/Y. Record actual
   G54-to-machine offset and bounds; machine home is not work zero. Measure
   repeatability across paper replacements, shared seam and fixtures.
4. With a mounted aligned brush, establish actual first-contact G54 Z0 on the
   drawing surface. Measure compression, paper hover, obstacle/global clearance,
   station heights/contents and required travel budget with margins. Container
   height alone is insufficient to infer dip depth. Avoid unmeasured -12 mm motion.
5. Measure brush/medium/substrate-specific response over the benchmark conditions,
   including fragile tiny/short strokes and high-frequency pressure alternation.
   Record feed, water/pigment load, width and continuity. Review contact/release.
6. Measure shared-layout head/fixture clearance, right-hand station access and
   travel over the physical gap. Nominal paper fit within 900×960 is not validation.
7. Define verified safe pause, park and restart, material-state loss, paper wetness,
   partial-stroke recovery and manual palette-refill behavior.

## Future Level 2: no-brush air run

Architecture is reserved, not enabled. Requires explicit user authorization,
verified homing/limits/E-stop, measured machine/work bounds, user-set G54 and safe
positive clearance with no surface/station contact. A virtual air-run work Z0
must be tagged `virtual_air_run_zero`, not mistaken for `brush_first_contact_zero`.
Keep the two origins and calibrations distinct. No station dipping or mounted
brush is permitted in the initial future air-run scope.

## Future Level 3: calibrated painting

Requires brush-contact origin, verified pressure mapping/context, measured station
coordinates/heights and obstacles, bounds/clearance, physical benchmarks, safe
restart and explicit user approval. Only a separate future Work may add executable
output after these conditions are established. No part of this handoff authorizes
a machine movement now.
