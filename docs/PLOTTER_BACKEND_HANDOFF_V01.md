# Datascape Plotter Backend v0.1 — Work Handoff

## Intent

Continue hardware/plotter execution development independently of the ongoing Spring Scene Integration Work. Spring is NOT approved for production yet. Never modify Spring composition, camera/viewpoint, current stroke grammar or existing Spring Draft PRs from this branch. This branch targets main and remains an unmerged Draft PR until explicitly approved.

## Completed baseline

- Python package: src/datascape/gcode/
- Shared JSON contract: datascape.machine_vectors.v0.1
- Panel clipping: continuous 600x900 mm artwork to two 300x900 mm physical panel views
- Deterministic stroke segment and source ID tracking
- Constraint-aware conservative nearest-neighbor scheduling
- Preview-only XY/Z motion planning; normalized pressure intent maps linearly to an *illustrative* negative Z
- Non-executable commented G-code and centerline SVG previews
- Tests and synthetic sample in tests/test_gcode_backend.py and examples/sample_machine_vectors.json

Verify this state from the PR diff and run the tests before subsequent edits. Test the current source with PYTHONPATH=src.

## What is not complete

- No production G-code, no real machine coordinate transform, no G54 setup routine.
- No motor/limit/homing/stop validations; MKS DLC32 V2.2 vs development YAML V2.1 label is still unresolved electrically.
- No brush calibration, station dipping, washing, squeeze-bottle palette replenishment procedure, or safe restart.
- No spline tessellation, dot primitive, or production seam ownership.
- No globally shortest or minimum-time scheduling.

## Hardware constraints to retain

- X homes left, Y homes rear (+Y), Z homes at upper limit; current YAML uses X0, Y960, Z50 with 2 mm switch pulloff, all *unverified*.
- Nominal Z span 50 mm. The brush is physically clamped at a setup location so its tip nearly touches the paper, then G54 Work Z0 is set without changing machine reference.
- Paper local hover target +3..5 mm; strong brush compression target down to -12 mm for calibration only. Do not assert measured force from Z compression.
- Palette rim 27 mm, inkstone 15 mm, sponge planned <=20 mm, all on top of the drawing bed. Global travel height above these obstacles must be measured.
- Previous notebook dip depths were negative because old stations were BELOW the bed; they do not define this hardware.
- Proposed setup descent ~32 mm remains a candidate; +32 clearance and -12 compression require 44 mm of travel before margins. A 35 mm descent and -15 compression overrun the nominal 50 mm range after a 2 mm post-home pulloff.
- Palette: mainly diluted gouache in squeeze bottles; manually refill small portions to palette during/after painting, while automatic brush reload can follow path/distance triggers.
- Flat drawing surface: do not implement prior notebook Y-axis tilt compensation in this phase.

## Next task sequence (independent of Spring completion)

1. Review PR and improve safety tests/schema validation (explicit ordered ink/color phases, color slots, duplicate IDs, out-of-bounds, invalid numeric fields).
2. Define production-capable intermediate motion events independently of printer machine coordinates: lift/travel/contact/stroke, source ID, brush/color slot, water/dip/wipe, checkpoint, manual palette refill.
3. Create an offline simulated time/route evaluator with constraints; preserve painterly layer order and directional brush logic, avoid unsupported minimum-time claims.
4. After physical assembly: pin/limit/E-stop/homing checks followed by coordinate transforms and brush/surface/station measurements. Store dated calibration artifacts before permitting executable motion.
5. Develop brush calibration sheets (constant depth, entry/exit taper, variable Z) and ink/gouache/water/sponge station logic, including color contamination and safe restart.
6. Only after Spring approves a vector snapshot: create an exporter that satisfies the shared contract. Validate with test vectors first; do not generate full-scene production files without machine validation.

## Repository policy

English code/comments/docs/commits/PRs; Korean discussion and work reports. Do not merge any Draft PR without explicit user approval.
