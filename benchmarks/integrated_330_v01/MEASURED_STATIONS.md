# Final shallow-wiping trial and Spring handoff

Base: Draft PR31, `943d0b1e9d59f9e6978aec85589c986bd8f06c64`.
This is a focused parameter/transition correction. No hardware I/O, merges,
artwork generation, pressure changes, S3a or palette-order changes.

## Operator-selected trial parameters

Both wells: flat `surface_z=9.0`, `compression_mm=1.5`,
`reentry_lift_mm=10.0` FROM THE COMPRESSED CONTACT TARGET.
Contact=9-1.5=7.5; lifted re-entry=7.5+10=17.5 (not19).
The extended flatZ9 is an operator-selected assumption based on the existing
shallow endpoint reference. It is NOT a newly measured extended surface and
is not an extrapolation of the old liquid-slope line. Successful prior XYZ/-10
observations are retained separately; final wiping/material results are pending.

Ink: first pass X840 Y445->455; second X830 Y445->455, with lifted return
via X830 Y402.5. Water: first X840 Y295->305; second X830 Y295->305,
with lifted return via X830 Y252.5. Existing slope withdrawal ends at425/275.

Sequence: deep immersion/dwell, X825->855->840 agitation, rising Y+ slope
withdrawal, vertical lift to17.5, transfer to the separate flat section,
controlled descent to7.5, first Y+ wipe, controlled vertical release7.5->9,
vertical lift9->17.5, THEN X-10 and noncontact return/second approach at17.5,
controlled descent, second Y+ wipe, vertical release to9 and retract35 before
station transfer. No X step at compressed contact. Re-entry rise is10mm total.
The production primitive still requires calibrated contact/re-entry volumes;
REVIEW generation does not manufacture those volumes or passed evidence.

## Preserved motion and material policy

| Motion | mm/min |
|---|---:|
| Ordinary XY / wet main XY | 12000 / 9000 |
| Drawing / Air stroke simulation | 6000 |
| Noncontact Z / paper approach / station approach | 6000 |
| Paper contact / release / pressure-Z cap | 2000 |
| Immersion / agitation / slope withdrawal / palette | 1000 |
| Shallow contact and release / purge contact | 750 |
| Shallow wipe / lifted re-entry | 1000 / 3000 |

Wet departure/arrival retain F3000 over5mm. Paper linksZ10, local hover off;
station/cross-region accessZ35. Home start0/898/35, park800/800/35/M2, M0=0.
Ink dip8/dwell2s; water dip7/dwell5s; purge840/137.5/0.5/dwell4s, vertical
single dab. Palette radius5/dwell1s; existing nominal floor1/liquid6/dip4.
All20 registered centers and Spring12 slots/order are unchanged. Explicit
phase caps prevent an obsolete F60 clamp. New speeds/material behavior are
still trial candidates, not physically achieved speed claims.

## X860 configuration

The operator confirms860 as intended maximum and will install the EXISTING
`config.X860.candidate.yaml`. Its bytes/hash are unchanged from pinned PR31:
`64325aac547971245ae73c1be4c640ec69f233ca92127d5deaeff0423eabb937`.
Only axes.x.max_travel_mm differs from the recorded installed YAML (850->860).
Homing, pull-offs, pins, rates, acceleration, other axes and soft-limit enable
state are unchanged. Installation/readback and subsequent homing verification
remain pending. Formal profile target-config hash/install gates remain intact.

Reviews reachX855: candidate860 bounds pass, recorded installed850 bounds fail
explicitly. Right palette circles reach852. Margins are axis-reference headroom,
not manufactured measured swept-tool clearance certificates.

## Delivery and reproduction

`review_measured_stations/` has three actual numeric G1/G4/M2 REVIEW files.
Air keeps identical40/station XY at safe simulation planes10/35. BOTH Paint
variants now contain the actual intended two-pass contact at7.5 and lifted
re-entry17.5: no Z35-only substitution. WATER_ONLY and INK_GOUACHE have identical
numeric commands, different fill instructions. They are motion-complete reviews,
not officially authorized physical programs or claimed successful final trials.

```sh
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR --verify
PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_gcode*.py' -q
```

Checks cover shared source/40 strokes, paired XY/visits, independent phase/Z
feeds, both controller bounds, two contact passes per well visit, vertical
release/lift before X offset, no routineM0, finalpark/M2, regenerated IR,
actual numeric read-back and SHA256. Tests reject too-low re-entry, rehashed
G-code mutation and attempts to promote review profiles through official gates.

## Spring handoff

`spring_pipeline.py` continues to use this SAME profile with existing canonical
PR25-bound machine/provenance inputs and existing S3a planner/export/verifier.
Modes: prepare -> air -> ink -> color; exports need separate current profile/
stage authorization. Paper links10/global transfers35, ink reload1000/color800,
no routine refill/water-change M0, existing Spring12/order, no end cleanup.
Original source bytes, accepted pressure and protected painting order stay locked.
See `spring_handoff.json` for immutable records and current profile binding.
No full Spring rebuild/production export is claimed in this parameter revision.

Next: operator installs X860 and reports actual config/homing readback;
review final matched Air as required, water-only and ink/gouache outcomes;
apply only necessary measured brush/material refinements and scoped approvals;
then existing Spring Air -> SHARED_INK -> SHARED_COLOR. No new design study.
