# Executed results — software only, no hardware execution

## Complete and exercised

- Exact v02 S3a reference recovered from the previous package; all 175 retained
  package manifest files matched. No repeated S0/S1/S3b/S4 or artistic study.
- Accepted PR25 adapter reused from its pinned checkout. Full bound payload and
  provenance validated: **14,951 original strokes / 240,974 pressure samples**.
- A preparation/read-back: **15,001 fragments / 241,074 clipped pressure samples**;
  every written original-segment interpolation, source direction/ID/material/lock,
  G54 work transform and complete segment partition checked.
- Four separate A jobs: P1 ink **1,494**, P1 color **5,684**, P2 ink **1,851**,
  P2 color **5,972** fragments. Source sequence records remain immutable.
- Full-plan canonical digest:
  `c9380e0b7c3967d1a8622dfa83974a568e2d1b2a67987dba479f348a66d9e074`.
  Complete geometry-bearing plan regenerates; the compact committed manifest
  binds every source/fragment/job to point/pressure/location/span/work hashes.
- **54 tests passed**, including **35 new v0.3 tests** and 19 existing regressions.
  The old optional full-scene unittest was skipped (no environment variables);
  the complete scene was instead exercised by the separate full preparation and
  actual exported-plan read-back above. No skipped test is called a pass.
- Measured-stage authorization, no-contact air export, separate small calibration
  export, measured-stage painting serialization, delivered-file read-back,
  atomic failure, source/pressure mutation rejection, current-material reset,
  source-boundary reload/overrun, resume, collision-path, stage/profile/plan binding,
  acceleration/rate constraints and arbitrary multi-knot mapping are tested with
  explicitly invented fixtures. No measured machine profile is shipped.
- Representative fixture jobs exercise the real serializer; retained `.example.txt`
  files comment every line. They are neither actual Spring jobs nor safe machine
  settings. Real Spring sidecar-bound paths reject synthetic fixture serialization.

The full preparation, actual JSON read-back, accepted-family audit and compressed
output took **19.12 seconds**, peak child RSS **736.55 MiB**, on Python 3.12.14 in
this run. It is a software observation, not a controller throughput or painting
speed prediction. No executable real Spring job was created.

## Actual pressure distribution and calibration implication

The accepted sidecar's explicit family labels were checked against every bound
ID/sample. Selected distributions below use original vertices, not clipped seam
samples; complete 15-family values are in
`review/pressure_distribution_by_accepted_family.json`.

| Medium / accepted family | Samples | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Ink A | 43,938 | 0.387 | 0.540 | 0.605 |
| Ink B | 1,839 | 0.392 | 0.542 | 0.625 |
| Ink D | 1,545 | 0.614 | 0.812 | 0.930 |
| Ink rock | 3,209 | 0.619 | 0.642 | 0.745 |
| Ink trunk | 3,248 | 0.440 | 0.580 | 0.684 |
| Ink branch-foliage | 4,610 | 0.251 | 0.382 | 0.471 |
| Color A-color | 64,374 | 0.266 | 0.423 | 0.492 |
| Color rock | 2,783 | 0.568 | 0.643 | 0.717 |
| Color mid-far-vegetation | 90,285 | 0.220 | 0.291 | 0.407 |

These data support testing a gentle low-intent region, expressive ordinary A
response and a separately observed stronger D/rock response. They do not determine
physical depths. Preserve .4 and .6 as provisional comparison markers; measure
low vegetation around .27–.35, ordinary ink A around .49–.58 and ink D around
.67–.87 before choosing finer knot positions. The accepted largest intent .93
need not use the maximum physical compression. A multi-knot curve can separate
these responses without changing any original pressure. Final Z knots await
width/continuity/recovery measurements on the intended mounted paper.

## Missing measurements that currently block real output

The shipped profile is deliberately `unverified`. Missing items include:

1. Actual installed firmware/config hash, usable XYZ envelope, machine/frame
   offset, starting position, rates/acceleration/steps/junction behavior, mounted
   brush/assembly and substrate identities.
2. Measured paper surface/contact/test Z range, approach/hover, wet motion limits,
   free-space/keepout volumes, station/global clearance and the exact park path.
3. Relevant water/ink/sponge/pigment station G54 contact geometry, reference levels,
   immersion and floor gaps, motion feeds/dwells/loading trajectories, and physical
   cleaning/reload tests.
4. Relevant measured multi-knot brush/media profiles and knot observations.
5. Current scoped hardware-test evidence and explicit separate authorization for
   air, calibration or painting. No authorization is manufactured by this Work.

Therefore no runnable first Spring ink or color file is available yet. The
exporter functionality is present; these are measured inputs and hardware gates,
not a request to redevelop the pipeline. Ink-only export does not require unused
color response profiles; color commissioning can follow ink independently.

## Hardware tests still required

Confirm directions/limits/homing/E-stop and the actual installed configuration;
verify G54 and expected MPos/WPos; inspect mounted paper/fixtures/head/holder and
entire no-contact/park paths; run separately authorized no-contact air checks;
measure small safe station and brush tests; verify ink/color contamination,
loading/recovery/overrun, relevant microsegments, actual mark widths and paper
flatness/registration. Washing does not satisfy the manual drying checkpoint.

Neither +10/+32 nor the intended X800 Y900 Z32 target is marked physically safe.
No -12 compression, nominal bed offset or liquid-depth default is approved.
Manual liquid maintenance is implemented; automatic sensing/adaptive dipping is
absent by design. No live controller connection, homing, YAML change or movement
occurs in this Work.

## Version boundary

Geometry, multi-knot depths/positions, media/substrate context, measured feeds,
hover/clearance/park, physical pigment order and existing station primitive
parameters are editable configuration in **v0.3**. The normal next action is
calibration and a controlled first use of this implementation, not a new v0.4.

Only newly requested capabilities absent from this architecture require code
work: e.g. sensors/feedback, incompatible kinematics/dialect, a different station
primitive, evidence-driven slope-continuous interpolation, or a separately chosen
shared continuous B/C output policy. The initial A split-job workflow does not
need those extensions.
