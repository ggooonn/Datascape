# Measured geometry correction and Spring handoff

Base: Draft PR30, `20a8070f66bcaea5adc38c67d2ef9dbb64ee9544`.
No hardware I/O, merge, Spring geometry/pressure/order modification.

| Motion | mm/min |
|---|---:|
| Ordinary XY | 12000 |
| Wet main XY | 9000 |
| Drawing / Air stroke simulation | 6000 |
| Noncontact Z / paper approach / station approach | 6000 |
| Paper contact / release / pressure-Z cap | 2000 |
| Immersion / X agitation / slope withdrawal / palette | 1000 |
| Shallow contact / purge contact | 750 |
| Shallow wiping / lifted re-entry | 1000 / 3000 |

Wet departure/arrival retain independent F3000 over5mm; no instantaneous speed
claim. Controller acceleration/homing/pull-offs stay unchanged. These new
feeds are candidates, not reported as physically achieved. Prior stable UGS TCP
Air/water-only motion and successful -10 brush strokes remain operator reports.

Paper-to-paper links use Z10; local hover is disabled. Station/cross-region
transfers use Z35, vertical lift -> XY -> vertical approach -> handling -> lift.
Start after homing X0 Y898 Z35, park X800 Y800 Z35/M2, M0=0.

Operator-measured XY is accepted: physical X860, X840+/-15 agitation,
radius5 palette/holder space, ink445..455 and water295..305 solid sections.
All20 registered palette centers and canonical Spring12/order are reused.
Do not re-request these measurements.

## Deliverable boundary

`review_measured_stations/` contains actual numeric Air/WATER_ONLY/INK_GOUACHE
reviews, shared40 source, IR, read-back, SHA256, same unified profile and X860
controller candidate. Paint variants have identical numeric commands and
different fill instructions. Ink dip8/dwell2s, water dip7/dwell5s, purge0.5/
dwell4s, A2 dip4/radius5/dwell1s. Liquid/floor references remain nominal.

The extended solid surface Z, safe compression and re-entry lift are NOT in the
records. Each well's `shallow_wipe.surface_z`, `.compression_mm` and
`.reentry_lift_mm` remains null. The new production routine is complete and
rejects missing values before movement; it never extrapolates the slope line.
It implements two solid passes, X-10 side-step and lifted return toward slope
middle. The delivered reviews explicitly substitute this unknown-contact
section with XY atZ35. Therefore they are incomplete contact benchmarks, not
final authorized squeezing/wiping programs. This is not an M0 inspection or
automatic contact assumption; headers/verification identify it explicitly.

The recorded installed YAML still says X850. The candidate changes only
`axes.x.max_travel_mm` to860; original YAML/hash remain intact. No homing or
soft-limit enable setting changes. Candidate installation and actual config
readback are still pending, not implied by physical reach to860. Reports pass
candidate860 bounds and explicitly FAIL installed850 bounds (max path855).
Rightmost palette circle reaches852. Axis headroom5/8mm is not invented tool
volume evidence. Formal profile readiness now checks target config installation
and hash agreement, preventing an offline-bounds-only promotion.

## Reproduction and validation

```sh
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR --verify
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_gcode*.py' -v
```

139 software tests: 138 pass, one pre-existing conditional full-scene skip.
Ten new tests exercise actual production wiping/F60 separation, matched numeric
reviews, original40 geometry, phase feeds/dwells, candidate-only bounds, scoped
XY evidence invalidation, tamper detection and Spring Z10 links. No physical
pass is manufactured. Runtime/clearance/contact authorization remain separate.

## Existing Spring pipeline, no fallback profile

Use `spring_pipeline.py` with the existing PR25-bound machine/provenance files,
this package's profile after measured calibration, and separate stage-specific
authorizations. The runner checks the unified motion policy, canonical12/order,
ink1000/color800 reload, zero routine refill/water pauses, no automatic end
cleanup, home start and normal hover10. It invokes the existing backend binder,
S3a planner, export and regeneration/read-back verifier. No generator is invoked.

```sh
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_pipeline \
  --mode prepare --machine /absolute/offline/spring.machine.json \
  --provenance /absolute/offline/spring.provenance.json \
  --profile /absolute/current/measured-profile.json --output /absolute/new/spring-plan
```

Then use `--mode air`, `--mode ink` and `--mode color`, each with the corresponding
`--authorization /absolute/current/STAGE-authorization.json` and a NEW output
directory. Air selects both shared jobs; ink/color select SHARED_INK/SHARED_COLOR
separately. Successful exports automatically invoke the existing verifier.
The core exporter writes `.nc`; preserve its filename/manifest instead of
renaming a verified job behind the manifest. `.gcode` extension alone never
confers machine authorization.

Existing committed full-scene readback (not rerun from missing source bytes in
this local checkpoint): 14,951 original unsplit D strokes, 240,974 accepted
samples, 50 X300-crossing strokes continuous; ink3345/color11606 source units.
The compact plan and canonical binding hashes remain unchanged. This revision
tests the actual runner/production primitives; it does not claim to have rebuilt
the full Spring plan or emitted Spring production files without their original
bound inputs and measured authorization. `spring_handoff.json` binds this new
profile to those existing immutable records. The next stage is configuration
completion and physical feedback, not backend redesign.

Remaining handoff: actual X860 config installation/readback; six solid-contact
values (surface/compression/re-entry lift perwell); reviewed revised Air/water/
pigment outcomes and scoped stage authorization; apply measured brush/material
results to existing multi-knot profiles and production palette fills. Established
controller/home/XY/fill references are retained, not requested again. Existing
stopping hardware limitations are not silently marked resolved.
