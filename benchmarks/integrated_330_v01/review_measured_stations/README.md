# Measured XY benchmark / Spring motion handoff

Numeric G1/G4/M2 offline reviews, not machine authorization. Same forty original
45mm strokes, four columns, original depth order and visits. Drawing6000,
dry12000, wet-main9000 (departure/arrival3000 over5mm retained), noncontactZ6000,
contact/release/pressureZ2000. Paper hover10/local disabled. Consecutive paper
strokes remain at10; station/cross-region access35. Home start0/898/35,
park800/800/35/M2, M0=0. No artwork, pressure or S3a changes.

The operator reports prior stable Air/water-only streaming via UGS TCP and
large-brush strokes to -10. X860, X840+/-15 agitation, radius5 palette/holder
space and extended shallow XY sections are now operator-confirmed, not treated
as arbitrary unmeasured XY expansion. New feeds/material response remain candidates.

Installed YAML still records X850. config.X860.candidate.yaml changes ONLY
axes.x.max_travel_mm to860; original installed bytes/hash and homing/pull-offs
remain unchanged. Runtime installation/readback is pending. Reviews reach855;
they FAIL the recorded850 bound and pass the proposed860 bound with5mm axis
headroom. Right palette radius5 reaches852, with8mm axis headroom. These margins
are axis-reference distances, not invented measured tool-volume certificates.
soft_limits is absent in the original YAML (v4.1.1 source default false); this
patch does not change its state or claim runtime enforcement.

Ink dip8/dwell2s, water dip7/dwell5s, agitation825->855->840, then Y+ slope
withdrawal to the existing shallow reference. Immersion/agitation/withdrawal1000,
palette1000, purge750, approach6000; separately capped, no legacyF60 clamp.
Palette floor1/liquid6/dip4 still nominal, radius5/one24-segment circle/dwell1s.
Purge840/137.5 to0.5, single vertical dab/dwell4s/no rubbing.

Solid wiping is modeled SEPARATELY: ink445->455, water295->305; two passes,
second X830, lifted return toward slope middle402.5/252.5. Actual surface_z,
gentle compression_mm and reentry_lift_mm are missing for EACH well. No old
slope line is extrapolated. Production rejects these nulls before motion.
ALL three review files include this XY at Z35 ONLY. The two Paint files have
real loading/washing/purge/palette and forty paper strokes, but DO NOT perform
the requested solid squeezing/wiping yet: incomplete contact benchmarks, NOT
run-ready final Paint files. WATER_ONLY and INK_GOUACHE numeric commands match.
Once those inputs are supplied, regenerate actual contact through the shared
production primitive and obtain scoped physical authorization; do not edit G-code.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR
Verify: same command with --verify. Checks include regenerated IR, actual numeric
read-back, both controller bounds, axis/Z feeds, 40 strokes, paired XY, dwell,
M0=0/M2 and SHA256. No physical sweep, stopping or speed test is manufactured.
See spring_pipeline.py for the same-profile, canonical-input, gated Spring
Air/SHARED_INK/SHARED_COLOR path; normal paper links10, global transfers35.
