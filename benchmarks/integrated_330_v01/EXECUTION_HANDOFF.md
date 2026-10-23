# One 330-mm benchmark, Air then Paint, then Spring

Base PR29: `e3e51bfa22cca615d29c39f9a960f38d4a193da3`.
Local predecessor: `445c24717156513e5134f5acf6733b94f812f59a`.
The current selected request is `execution_mode: continuous_40`. Earlier
inspection-based requests remain backward compatible; they are not the selected
production-equivalent benchmark. No hardware movement or Spring changes.

## One source, two execution modes

`benchmark_columns` binds forty 45-mm strokes into the same plan SHA256 for both
jobs. Four columns use X20..65 / X100..145 / X180..225 / X260..305. Ten rows at
Y30+27*i (i=0..9). Ink uses depths -1..-10 then -10..-1; A2 repeats the sequence.
Normal hover10, local hover disabled, and exactly one final park.

Both modes use the same operation loop and XY grammar: WELL_2 load, ten ink
strokes, WELL_2 reload, ten ink strokes, WELL_1 wash with Y+ withdrawal, A2 load,
ten color strokes, A2 reload, ten color strokes, park. Same-material reloads
never wash. Forty source IDs, stroke directions, vertices and visit order match.
No legacy stability rectangle or extra pressure/hover strokes are added to Air.

| Motion | Proposed benchmark feed (mm/min) |
|---|---:|
| Ordinary dry XY | 8000 |
| Stroke XY, ink and A2 | 5000 |
| Wet-loaded main XY | 8000 |
| Wet departure / arrival | 3000 / 3000, existing 5-mm edges |
| Non-contact Z / paper approach | 3000 |
| Pressure Z velocity cap | 2000 |
| Paper compression / release | Existing Spring candidates, separately configured (2000 / 2000) |
| Station contact / immersion | Independent station profile; never inherited from high-speed paper motion |

All are candidates requiring the relevant pre-run physical validation, not
attained speeds or hardware approvals. The installed accelerations are unchanged.
Brush knot mapping and Spring Pressure Intent are unchanged.

`BENCHMARK_330_AIR.gcode`: paper XY paths at Z10; station XY grammar simulated
between verified Z35 approach and Z32 lower plane. No contact, no liquid/floor-Z
or pressure-curve dependencies, zero M0. It still requires the actual well deep/
shallow XY and A2 pattern geometry, plus complete station and transfer corridors.
Registered well regions are NOT automatically the contact endpoints. The same
palette XY helper drives wet loading and dry simulation.

`BENCHMARK_330_PAINT.gcode`: same source and route, actual independently measured
contact Z and loading primitives, zero M0. No routine depth/reload inspections
or repeated parking. Both start after rehoming at **X0 Y898 Z35**, zero G54/G92/
TLO, and end **X800 Y800 Z32, M2**. No offset writes or automatic homing.

## Preconditions are before execution

A missing independent physical E-stop and unresolved Y-negative vibration remain
real limitations. Neither file may be exported until USB-independent physical
power-stop behavior, motion limits, positive clearance and explicit Air job
approval are recorded. Verify Feed Hold/reset response and short directional
speed tests before long F8000 motion; GUI stop and USB disconnect are not an
independent stop. No actual Air outcome has been supplied.

Air also needs actual deep/shallow XY for WELL_1/2 and approved A2 loading radius/
pattern (liquid/contact Z remains unnecessary), inspected Z32..35 station routes
and paper Z10 corridors. Confirmed station registration is retained: water
X840/Y220..285, ink X840/Y370..435, A2 X824.5/Y554.5.

Before uninterrupted Paint: actual successful paired Air result, measured well
floor endpoints/liquid/contact volumes, A2 floor/liquid/dip/bottom clearance,
wet/contact acceleration limits and controller junction deviation, stage-specific
pre-run authorization, and scoped evidence `station_contacts`, `wet_motion`,
`continuous_benchmark_contact`. The latter must explicitly record actual -9 and
-10 tests in `tested_depths_mm`; historical -8 experience is insufficient. A
measured geometric envelope must include -10. Both stones must rise toward Y+.
The operator confirms brush preparation and supplies before the job starts.

Nominal A2 bed-relative floor2 plus fill5 gives liquid7. Only with paper height
h=1 above bed does this imply nominal G54 floor1/liquid6. These approximate
references are not promoted to measured contact values. Normal pressure mapping
and no-overshoot/domain rules remain unchanged.

## Export and verification

Generate input JSON only (not previews or blocked export attempts):

```bash
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.handoff \
  --seed-profile /path/to/measured-inputs.json --output /new/inputs
```

After real physical evidence and authorization exist, use the existing
`integrated --kind air|paint --plan ... --profile ... --authorization ... --output ...`
and `verify --output ...` workflow. Authorization binds the exact plan, profile,
stage and new job name. No zero-M0 bypass is available through the legacy
calibration path: the new read-back exception requires scoped continuous-contact,
station and wet-motion evidence, with full build validation preceding export.

Tests independently compare the complete XY route, all forty strokes, visits,
feeds, source IDs and zero M0. Temporary synthetic exports exercise both actual
serializers/read-back/SHA256 and reject rehashed altered G-code. They are never
physical evidence or deliverable machine programs. Measured wet Z updates do
not erase actual Air history; XY/loading-pattern or dry-policy changes do.

After physical feedback, apply validated motion/material/brush profiles and use
the existing full Spring Air -> SHARED_INK/SHARED_COLOR workflow. Preserve
normal Z10, F2-C, geometry, Pressure Intent, source direction and S3a order. No
new artistic or speed-comparison study is required. Existing Draft PRs remain
unmerged; remote publication is not retried without authorization.
