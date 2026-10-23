# Final station benchmark review

Real numeric G-code, not physically authorized. Prior Air/water-only motion and
-10 strokes succeeded via UGS TCP according to the operator. New station feeds,
agitation, purge and pigment response remain candidates. No repeated hardware
questions or new palette mapping study: all 20 centers are read from the existing
YAML; the existing 12 Spring slots/order are preserved.

Start X0 Y898 Z35 after homing; final X800 Y800 Z35/M2. Same forty strokes,
F5000 drawing, F8000 dry/wet-main XY, F3000 noncontact Z, F2000 pressure-Z cap,
hover10/local disabled, zero M0. Station access always retracts vertically to35
before XY, then approaches vertically. Air uses a noncontact Z32 simulation
plane after Z35 travel. WATER_ONLY and INK_GOUACHE executable commands match.

Approach F3000 to wellZ12/paletteZ8/clothZ3.5, immersion750, agitation500,
withdrawal1000, cloth500. Explicit phase caps replace the legacy F60 clamp for
these profiles; legacy profiles retain their old clamp. Ink dipZ8/dwell1.5s,
water dipZ7/dwell3s, one +/-0.5mm X agitation cycle, Y+ rising withdrawal. A2
dipZ4, radius1 circle, dwell1s. Purge one centered X840/Y137.5 dab toZ0.5,
dwell0.75s, controlled release; no rubbing. All new dimensions/feeds are explicit
nominal candidates, not precision measurements or certified stone interior fit.

X847 palette radius1 reachesX848, leaving2mm of axis-reference travel. That
number is NOT actual brush/holder clearance; full-tool fit and common A2 model
equivalence must be checked before production. No new collision-free volumes
or measured pressure curve are invented. See spring_palette_mapping.json.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.station_final --output NEW_DIR
Verify: same command with --verify. Checks: configured axis bounds, per-axis/Z
feeds, regenerated sequence/read-back/SHA256, forty strokes, M0=0, park/M2.
After water then pigment results, apply only necessary parameter refinements
to existing profiles; full Spring Air -> SHARED_INK / SHARED_COLOR, preserving
v13/F2-C/Pressure Intent/S3a. Official physical authorization gates stay intact.
