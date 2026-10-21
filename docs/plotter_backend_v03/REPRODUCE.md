# Reproduce, commission and export

Use Python 3.10+ (executed with Python 3.12.14); standard library only. From this
Backend checkout, retain PR #25 in a separate detached checkout at
`d30ac7be302e1cbfcd2cf66de9087e35ea091b6c`. The accepted PR #24 Spring input is
`67ba146b1213644d40bc9dabed9d52024d2bbe58`, already frozen inside the pressure
checkpoint. Do not run a scene generator or pressure synthesis script.

## Software tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_gcode*.py' -v
python -m compileall -q src/datascape/gcode/production
```

The legacy full-scene conditional unittest is skipped without its environment
variables. The complete scene is separately verified by `prepare` below, including
read-back of every actual written source fragment/sample. Do not count that skip
as a hardware pass.

## Accepted binding

Run PR25's existing adapter, producing new files outside the source directories:

```sh
PYTHONPATH=src python - <<'PY'
from datascape.gcode.binding import bind_with_accepted_adapter
bind_with_accepted_adapter('/absolute/Pressure',
                          '/absolute/offline/spring.machine.json',
                          '/absolute/offline/spring.provenance.json',
                          '/absolute/Backend/src/datascape/gcode')
PY
```

The adapter checks source bytes and every accepted pressure value. No output
file may already exist. Backend binding rejects substituted payload/provenance.

## Full-scene offline preparation

```sh
PYTHONPATH=src python -m datascape.gcode.production prepare \
  --machine /absolute/offline/spring.machine.json \
  --provenance /absolute/offline/spring.provenance.json \
  --s3a-order config/plotter_v03/spring_s3a_order.json \
  --pressure-sidecar /absolute/Pressure/artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz \
  --profile config/plotter_v03/profile.unmeasured.json \
  --layout D \
  --output /absolute/offline/spring-v03-prepared
```

Writes deterministic full `plan.json.gz`, validation/readiness `summary.json`,
layer and accepted-family pressure distributions and hashes. It does not write
executable Spring G-code. It verifies 14,951 sources, 240,974 accepted samples,
14,951 unsplit D paths and 240,974 samples (A: 15,001 fragments / 241,074
samples), including exact original
segment/fraction pressure interpolation and G54 work transformation. The compact
committed execution manifest records the exact source/fragment/job IDs and hashes
of all point/pressure/location/span/work-coordinate payloads. Recreate the complete
15-MB compressed plan with this command; do not duplicate frozen artwork in git.

`--registration` accepts a JSON list of existing `Registration` fields (`panel`,
`x_mm`, `y_mm`, `rotation_deg`). D is the production CLI default; A and B/C planning remain available.
C uses explicit `--gap-mm`; no exhibition gap is inferred. Nondefault registration
or physical color order changes the prepared plan hash and requires review.

## Readiness report

```sh
PYTHONPATH=src python -m datascape.gcode.production readiness \
  --profile /absolute/local/measured-profile.json \
  --stage painting --layout D --media ink
```

For color readiness include `--media color --slots C1 D1 A2 D2 C2 A4 A3 A5 C3 D4 C4 D5`.
For the shipped unmeasured profile, exit status 2 and an explicit blocker list are
expected. A passing report is not authorization. Follow CALIBRATION_AND_OPERATION
for measured records, scoped evidence and authorizations.

## Authorized no-contact or painting export

After the relevant measurements/tests and separate explicit authorization:

```sh
PYTHONPATH=src python -m datascape.gcode.production export \
  --machine /absolute/offline/spring.machine.json \
  --provenance /absolute/offline/spring.provenance.json \
  --s3a-order config/plotter_v03/spring_s3a_order.json \
  --profile /absolute/local/measured-profile.json \
  --stage air \
  --authorization /absolute/local/air-authorization.json \
  --jobs SHARED_INK \
  --output /absolute/jobs/shared-ink-air
```

Use `--stage painting` only after its own current evidence and matching painting
authorization. D uses separate `SHARED_INK`/`SHARED_COLOR`; use `--layout A` for
`P1_INK`, `P1_COLOR`, `P2_INK`, `P2_COLOR`. Select one
job at a time if paper registration or profiles differ. A profile must not claim
contact calibration just because its machine/air stage passed. Changing knots,
feeds, registration or selection never silently reuses old authorization.

Files include selected `.nc` jobs, per-job `.trajectory.json.gz`, complete
`plan.json.gz`, exact profile/authorization, source-bound restart lists, estimates,
read-back report and `MANIFEST_SHA256.json`. The final directory must be new.
No serial, network or OpenBuilds sending is performed by the exporter.

## Explicit small calibration export

```sh
PYTHONPATH=src python -m datascape.gcode.production calibration \
  --profile /absolute/local/measured-base-test-profile.json \
  --plan /absolute/local/small-calibration-plan.json \
  --authorization /absolute/local/calibration-authorization.json \
  --output /absolute/jobs/small-calibration
```

It can test measured station volumes with explicitly selected candidate operation
parameters, or isolated constant-Z brush lines inside the measured test range.
No measured response curve is required to measure that response in the first
place. A measured base/frame, passed air evidence and explicit calibration-stage
authorization are still required. Missing test depths fail; none default to -12.

## Transfer checks and safe restart

```sh
PYTHONPATH=src python -m datascape.gcode.production verify \
  --output /absolute/jobs/shared-ink-air
```

Run after copying files, before manual sending. An altered or unmanifested `.nc`
file, source sample change, unexpected dialect, invalid path or coordinate/feed
mismatch fails verification.

For an interrupted job, supply a JSON mapping such as
`{"P1_INK":"<last completely printed ORIGINAL source ID>"}` to `prepare` and
`export` through `--resume-after`. The new suffix starts from the measured initial
position, repeats pre-run confirmation/load, and has a new plan hash. Do not
skip an unfinished source, manually edit `.nc`, concatenate panel/medium files,
or resume at an arbitrary line after state loss.


## Focused reload and cost recalculation

```sh
PYTHONPATH=src python -m datascape.gcode.production.costs \
  --machine /absolute/offline/spring.machine.json \
  --provenance /absolute/offline/spring.provenance.json \
  --s3a-order config/plotter_v03/spring_s3a_order.json \
  --scenario config/plotter_v03/cost_scenario.synthetic.json \
  --output /absolute/offline/A-D-costs
```

This runs the current automatic 1,000-mm ink / 800-mm color policy on the fixed
S3a order, validates written A/D plans and every trajectory pressure sample, and
reports reloads, station transfer and time models. It is not a scheduling search.
The scenario intentionally uses nominal unverified station XY and invented Z,
curve, feed/contact/dwell/dynamic assumptions. It writes no G-code or physical
trajectory files. Physical station travel and total duration remain null; the
reported numerical scenario is not measured calibration. See RESULTS.md.
