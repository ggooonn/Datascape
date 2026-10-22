# Hardware commissioning and 330x330 mm benchmark v01

**Current operator workflow:** the integrated successor on the dedicated branch
uses [two principal jobs](../integrated_330_v01/README.md), rather than thirteen
operator sessions. The plans below remain unchanged source components and
regression fixtures. The new record uses the supplied installed YAML and actual
FluidNC v4.1.1 query; historical unknowns below are not current facts.

Base Backend PR #27: `12b28bd5b7ad575b1438ed5af61618746c7effe9`.
Parent Local Hover study: `0eeff5d0d874b9b869c3f274d06bf524ac18282a`.
This independent branch changes neither existing Draft PR nor Spring artwork,
Pressure Intent, S3a order, homing, offsets, firmware or installed YAML.

The current deliverable is **offline preparation**, not approved machine output.
The user reports homing WPos `(0,898,35)` and first paper contact Z0. These do not
identify MPos or the saved G54 translation. Park is explicitly `(800,800,32)`.
The stored direction-corrected YAML still says X pull-off 2 mm, whereas the current
user report says approximately 5 mm; it is not asserted to be the installed file.
Actual YAML bytes and network/controller secrets stay out of git. `measurements.json`
records selected non-secret audit fields, the file hash, reports and assumptions.

## Focused backend additions

- `prepare --benchmark-plan` accepts independent 330-mm **G54 work XY** paths.
  Its adapter to the existing Layout is explicit and round-trip tested; these are
  not Spring paths or a 600x900-mm contact job. `export --stage air` uses the same
  profile/evidence, authorization, spatial checks, serializer and read-back gates.
  Contact/painting export of a benchmark Air manifest is rejected at both API/CLI.
- Calibration requests optionally add `pressure_lines` and `hover_groups`.
  Pressure samples use the existing multi-knot `BrushCalibration.z_for`, unchanged
  XY/sample order, synchronized XYZ and existing axis/pressure-Z feed caps.
  Requested depths must fit the measured `paper_contact_z_range`. Test drawing feeds are capped by both the requested feed and the profile draw limit; existing axis/Z caps remain active.
- Explicit hover calibration tests contain separate contact/release events and
  lifted links of at most 10 mm. The preceding stroke retracts only to the chosen
  height; the next begins there. Final strokes return to normal hover. These
  isolated trials do not require their own successful production clearance result
  in advance; they require prior contact observations, the existing air/base gates,
  measured whole-path corridors and separately bound calibration authorization.
  Production `local_hover_clearance` remains mandatory and is never auto-passed.
- `paper_region_xy` rejects contact samples outside the benchmark. Optional
  `requires_evidence` only adds prerequisites; C/D require prior `paper_contact`.
  Independent station trials can record `station_ink_trial`, `station_water_trial`
  or `cloth_purge_trial` with the existing evidence format. Their dependency scopes
  include machine, motion, station operation data and brush/media context.
- Calibration `verify` regenerates the authorized request and compares all IR,
  then rechecks G-code. Delivered-file verification also reruns readiness. Manual brush-test transfers and inspection parking use the existing wet-loaded
  departure/main/arrival policy; unknown wet edge lengths remain unresolved in previews. No
  safety gate is relaxed and no executable output is enabled by a preview sink.

## Prepare and inspect

Run from this checkout with Python 3.10+. The optional preparation YAML audit uses
PyYAML (the existing research extra); the core exporter uses the standard library.
Use a **new** output directory. Supplied/stored controller YAML is audit input only.

```sh
PYTHONPATH=src:. python -m benchmarks.commissioning_330_v01.run \
  --controller-yaml /absolute/config-copy.yaml --output /absolute/review-new

PYTHONPATH=src python -m datascape.gcode.production readiness \
  --profile /absolute/review-new/profile.provisional.json \
  --stage air --layout D --media ink
```

The script generates 13 independent plans and comment-only previews, blank
observations, blocked-export results and FALSE authorization templates. Actual
station geometry remains null. It does not fill fake offsets or free-space boxes
just to exercise a physical serializer. Preview numeric coordinates are test
candidates; unresolved boundaries/stations remain explicit. Every preview line
is commented; never remove the comments and stream it.

The report generator is optional and uses matplotlib for a precise layout figure.
A final offline package includes a SHA256 manifest. Verify it with:

```sh
PYTHONPATH=src:. python -m benchmarks.commissioning_330_v01.verify \
  --package /absolute/review-package
```

## After actual measurements and explicit authorization

Copy/fill the profile with measured machine/frame/motion/clearance data and retain
physical evidence using `readiness` scope hashes. Do not merely change `status`.
Keep current first-contact reference and nominal home WPos; no G10/G92/homing or
YAML writes are generated. Rebuild a plan/profile-bound authorization when either
changes. Each independently started job must start at its recorded WPos; returning
to that start after the preceding park is a manual, verified operation.

```sh
PYTHONPATH=src python -m datascape.gcode.production prepare \
  --benchmark-plan /absolute/review-new/plans/A_SHORT.json \
  --profile /absolute/measured-profile.json --output /absolute/air-prepared-new

PYTHONPATH=src python -m datascape.gcode.production export --stage air \
  --benchmark-plan /absolute/review-new/plans/A_SHORT.json \
  --profile /absolute/measured-profile.json \
  --authorization /absolute/approved-air.json --output /absolute/air-export-new

PYTHONPATH=src python -m datascape.gcode.production calibration \
  --plan /absolute/review-new/plans/B_DEPTH_1.json \
  --profile /absolute/measured-test-profile.json \
  --authorization /absolute/approved-contact.json --output /absolute/contact-new

PYTHONPATH=src python -m datascape.gcode.production verify --output /absolute/air-export-new
PYTHONPATH=src python -m datascape.gcode.production verify --output /absolute/contact-new
```

`readiness --stage calibration --slots ink` checks ink only; omit `--slots` for
manually loaded paper tests, or use `water`/`sponge` for isolated tests. The core
still requires all its original common motion fields even for Air Run. Unknown
approach boundary, wet edge lengths, state-specific acceleration limits and
station contact ceilings must not be disguised as approved measurements.

Station Air tours are opt-in: the request's roles must exactly match
`motion.air_station_roles`, and measured G54 `center_xy` and full swept clearance
are required. The default Air plans omit stations and perform no dipping/wash/PURGE.
Color stations are inactive. Cloth uses the existing absorbent primitive, one
vertical dab, but its folding/securement/surface and trial remain specific to cloth.

## Calibration request additions

`pressure_lines`: each item has `medium:"ink"`, `slot:"INK"`, positive
`feed_mm_min`, and `samples:[{"xy":[x,y],"pressure":p}, ...]` with >=2 distinct
consecutive XY points. There is no extrapolation or pressure replacement.
`hover_groups`: each has >=2 constant-depth `strokes` (existing brush-line fields),
`hover_mm` and `max_transition_mm` (positive, <=10). A lower-than-measured approach
boundary or an over-distance link fails. No source joining occurs.

`requires_evidence` may name `paper_contact`, `station_ink_trial`,
`station_water_trial`, `cloth_purge_trial`; these are additional current-profile
prerequisites. Existing evidence fields/operator/date/method apply unchanged.
M0 count is `2 + 2*station_roles + brush_lines + pressure_lines + hover_groups`.
All reasons are derived from IR and checked against delivered text. Standard
production Spring ink/color jobs retain their zero-routine-M0 behavior.

See [operator order and records](RUN_SHEET.md). This is normal v0.3 commissioning,
not a v0.4 architecture. Future Spring export uses its accepted source inputs and
S3a through the existing production workflow after calibration and authorization.
