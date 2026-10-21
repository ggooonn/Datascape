# Implementation and controller contract

## Modules

| Module | Responsibility |
| --- | --- |
| `production.sequence` | Verify exact recovered S3a permutation; apply explicit optional physical pigment order; separate source-bound jobs; complete source-unit restart suffixes; serialized-plan and family-distribution audit |
| `production.profiles` | Reusable JSON profiles; installed machine/brush/substrate context; staged blockers; scoped evidence; stage/profile/plan/job-bound operator authorization |
| `production.trajectory` | Original v0.2 brush events into XYZ IR; active-material loading state; measured station paths; global clearance; feed/acceleration checks and time categories |
| `production.exporter` | Narrow FluidNC dialect; separate files; atomic installation; independent G-code/IR/source-sample read-back; hash manifest; small calibration exporter |
| `production.__main__` | `prepare`, `readiness`, `export`, `calibration`, `verify`; no device I/O |

The prepared manifest includes all clipped points, pressure values, original
source locations/spans, source IDs/sequence/order locks, sidecar SHA, panel/setup
membership, G54 coordinates, layout/registration and source aggregate hash.
No vector schema migration, pressure defaults, artistic resampling, simplification,
merging, reversal or reconnection of gaps is used.

D uses a single FULL substrate primitive with no X=300 clipping or seam events.
Every original stroke and pressure vertex is retained; serialized-plan and full
trajectory audits check all 50 Spring crossing sources. Two adjacent substrates
require a current physical continuous-seam contact test in addition to the usual
calibration gates. A source is atomic for material services and restart within its job. Shared
B/C IR keeps original fragment arc traversal, including P2-first crossings.
Separate A panel jobs necessarily separate 50 source paths across sessions; 25
start in P2 in original traversal. This temporal limitation is reported, not
claimed preserved across a P1-first paper replacement.

## FluidNC planning

Primary sources reviewed on 2026-10-21:

- [FluidNC Planner.cpp](https://github.com/bdring/FluidNC/blob/main/FluidNC/src/Planner.cpp)
- [FluidNC GCode.cpp](https://github.com/bdring/FluidNC/blob/main/FluidNC/src/GCode.cpp)

The planner projects axis rate and acceleration maxima onto each Cartesian block,
limits junction entry speed, and performs forward/backward lookahead. A G1 feed
is the synchronized 3D path speed, not an independent Z or XY command. M0 pauses
program flow; G4 performs a dwell. The code does not assume G61 guarantees exact
stops or use a per-line acceleration command. Source review of upstream `main`
does not identify the installed firmware; its exact version/config must be
recorded and checked on the actual MKS DLC32 V2.2 installation.

For each generated segment, software limits F to the projected measured axis
rates and, during pressure variation/drawing, the separate pressure-Z rate cap.
It records each axis velocity and projected acceleration. The installed global
XY acceleration must not exceed the brush's measured wet-travel acceleration
limit; global Z acceleration must not exceed the measured contact limit.
Violations block export. The operator must adjust/revalidate controller settings
outside this program if necessary; no automatic acceleration/YAML changes occur.

Wet-loaded XY travels include configurable slow departure/arrival lengths and
feed caps. Intermediate XY points are inserted only in lifted travel. Drawing
vertices and pressure are never inserted or removed. `partially_depleted` means
accumulated loading distance exceeded its experimental threshold, not physically
dry. XYZ pressure changes remain on the original synchronized G1 segments;
rapid changes reduce commanded feed rather than rewriting intent.

Requested drawing feed is a 3D feed ceiling. When Z changes, resulting XY speed
can be below 5,000 mm/min even before acceleration and junction limits. Candidate
3,000/5,000/6,000 drawing and 12,000/15,000 ordinary travel comparisons are profile
edits; they do not need another software version. Maximum commanded rates are
not evidence of attained short-segment speed. Sub-step motion and brush recovery
require representative physical tests; finite machine steps cannot reproduce
mathematically infinitesimal vector intervals exactly. Every original sample
still appears in the IR and serialized command sequence, to 9 decimal places.

## Pressure interpretation

The v0.2 `BrushCalibration.z_for()` multi-knot piecewise-linear map is reused.
Any number of increasing intent knots is allowed. Work-Z is nonpositive and
nonincreasing with intent. Domain underflow/overflow fails; no clamping,
extrapolation, hidden fallback or automatic endpoint-to-maximum compression.
Mapping is applied at the original accepted pressure vertices; each G1 line
interpolates XYZ between those endpoints. No intermediate artistic samples or
new drawing vertices are invented. Physical tests must check this sampled
response, especially when a segment spans a calibration knot.
Profiles match mounted brush, hardware assembly, medium, substrate and measured
surface-above-bed height. Each selected physical knot depth needs recorded width,
continuity/loading observations. Per-slot brush/media profiles may override the
medium profile where separate physical measurements justify them.

A monotonic slope-continuous option, such as PCHIP, is a focused future extension
only if piecewise-linear physical tests show unreliable pressure response. Its
contract would retain the same knots/intent, prohibit overshoot or sign reversal,
reject extrapolation, preserve XY samples and enforce the same XYZ/Z dynamic
limits. `interpolation: pchip` currently fails explicitly. No assumed cubic
function is selected as the physical curve, and no new v0.4 Work is prescribed.

## Spatial checks and time accounting

Every complete straight segment is transformed by the measured G54-to-machine
translation and checked against usable machine limits with a tool-envelope
margin. Keepout boxes are expanded by that margin. The complete segment must be
covered by the union of `validated_free_boxes`; checking endpoints alone is
insufficient. These G54 boxes are **measured swept-tool-safe reference-position
volumes**, already accounting for holder/head/brush/fixture geometry. They are
not inferred from nominal machine travel. No automatic obstacle/paper sensor is
assumed. Verify all contact regions, wet brush overhang and mounting edges.

Station transfers raise vertically to station clearance before XY movement;
paper hover is used only after arrival above the drawing area. Parking uses the
exact configured target; unreachable/blocked paths fail without substitution.
An optional air station tour (`motion.air_station_roles`) visits measured station
XY at global clearance, without descending into a station or using liquid data.

Metrics separate original XY drawing distance, synchronized 3D drawing distance,
non-drawing 3D travel, station access AND return transfers, station operation distance and commanded-feed
time by action. An additional rest-to-rest-per-segment time model uses measured
axis acceleration. Neither model reproduces all FluidNC lookahead/step quantization
or proves physical duration. Manual interventions and drying remain null. Station
travel becomes spatially accounted for only in measured or explicitly synthetic
trajectories; the synthetic examples are not Spring time estimates.

## Interruption and delivered-file checks

Standard A/D ink/color programs have no routine M0. Operator confirmations are
recorded in the job-bound authorization BEFORE execution: coordinate/start state,
controller/tool state, paper/clearance, prepared clean brush and adequate supplies;
color also confirms ink drying/registration, and D confirms a continuous substrate
or tested seam. Export fails if confirmations are absent. No runtime G-code can
query/conditionally compare offsets; the operator must check them before starting.

Manual refill/water-change pauses are disabled by `null` intervals, while positive
integers explicitly opt in after completed operations. End cleanup is optional;
standard completion parks and ends with M2. All actual pause counts and reasons
are derived from IR and checked against G-code. Small explicit calibration tests
retain their intentional startup/inspection/recording pauses.

After an interruption that invalidates state, abort and re-establish registration;
never resume at an arbitrary G-code line. `--resume-after` regenerates a complete-
source suffix with a fresh initial load and pre-run confirmations, changing the
plan hash/authorization. The operator prepares a clean brush before restart;
there is no redundant forced initial color wash. Ink remains ink-only and color
color-only.

`verify` rechecks all delivered file hashes, the dialect, coordinates, complete
segments and each artistic sample against the saved plan. Use it after transfer
before manual sending. Hash/evidence records are integrity/audit controls, not
cryptographic certification of an operator's physical measurements.
