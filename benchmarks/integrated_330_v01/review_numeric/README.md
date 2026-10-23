# Numeric G-code review package

These are actual G1/G4/M2 files with zero M0, NOT commented previews. They are
operator-requested offline review files, NOT authorized or physically validated.
Do not stream them as machine-approved programs. Official export gates remain
unchanged; no passed evidence, free-space box or calibrated contact volume was
created to produce these files.

Both modes use the same 40 strokes, XY route and material visit order. Start
after homing at G54 X0 Y898 Z35; final X800 Y800 Z32 and M2. Dry/wet-main XY8000,
stroke XY5000, noncontact Z3000, pressure-Z cap2000. Paper compression/release
use separate Spring candidates2000/2000; station contact60, dwell1s, dip2mm,
palette radius1mm/one circle are independent provisional review settings.

Air: paper Z10, station XY simulated at Z32 with Z35 approach. Paint: actual
numeric requested depths -1..-10 and -10..-1, automatic ink/water/A2 operations.
Calculated well deep Y = registered lower Y+10, shallow Y = lower Y+55. These
are REVIEW placements using the historical 45-mm slope, not measured endpoints.
Latest nominal well floor bed+5 overrides the earlier bed+6 reference. At nominal
paper bed+1, selected well liquid Z9 gives dipZ7; A2 liquidZ6 gives dipZ4. See
nominal_assumptions.json for every calculated contact coordinate and uncertainty.

Offline checks cover exact read-back, full configured axis-reference segment
envelope, per-axis feed/Z limits, 40 strokes, visit order, M0=0 and final M2.
They do NOT verify mounted-tool clearance, actual collision freedom, liquid
levels, high-speed dynamics, stopping or -9/-10 brush response. No controller
runtime estimate is represented as measured time.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.numeric_review --output NEW_DIR
Verify: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.numeric_review --output DIR --verify

Machine-authorized Air still needs independent physical stopping and Y-negative
motion verification, full paper/station/transfer tool clearance and explicit
stage authorization. Authorized Paint additionally needs actual Air outcome,
measured station contacts/floor gaps, -9/-10 checks, wet/contact dynamics and
pre-run approval. Established nominal fill levels are not requested again.
After results: calibrate existing profiles, full Spring Air, SHARED_INK/COLOR;
preserve Spring artwork, Pressure Intent and S3a.
