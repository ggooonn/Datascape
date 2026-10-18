# Datascape Plotter Backend v0.1 — Offline Prototype

## Status and safety boundary

**Review-only. Not physically validated. Do not send generated previews to FluidNC.**

This PR replaces the placeholder src/datascape/gcode package with a machine-independent JSON input contract, exact segment-level panel clipping, deterministic constrained stroke scheduling, preview 3D brush trajectories, and SVG/commented-G-code outputs. The Spring composition and hardware YAML are untouched.

## Input contract

- Schema: datascape.machine_vectors.v0.1
- Continuous artwork coordinates: 600 x 900 mm (no 40 mm exhibition gap)
- Panel P1: artwork X 0..300 mm; P2: X 300..600 mm; both Y 0..900 mm
- Stroke fields: stroke_id, points (x, y, normalized pressure 0..1), medium, layer, color_slot, order_group, sequence, reorderable, reversible
- Stroke IDs are retained via source_id after clipping and deterministic fragment IDs
- Stroke paths must be polylines with at least two points. Spline tessellation and dot primitives are separate future work.
- The same source dataset feeds SVG and commented G-code previews.

Coordinates remain in CONTINUOUS ARTWORK coordinates in v0.1. This is NOT a machine coordinate transform, G54 work offset, or panel-local registration.

**Seam policy pending:** a path exactly along X=300 appears in BOTH panels until the painting team selects an explicit seam-ownership rule.

## Scheduling

Locked order_group and sequence precedence is preserved. Within same medium/color/layer/group/sequence, only consecutive strokes that explicitly set reorderable=true can be reordered by a deterministic nearest-neighbor Euclidean-distance heuristic. Path reversal requires reversible=true. No global optimality or actual minimum-time claim: speed, acceleration, washing/reload, wet-on-wet constraints and stations are unmodeled.

## Preview Z semantics

- Work Z0: first brush contact with mounted paper (target coordinate convention, not yet physically established)
- Positive Work Z: lift above paper; preview hover +5 mm
- Negative Work Z: commanded compression; NOT measured physical force
- Illustrative mapping: normalized intent 1.0 -> Work Z -12 mm, linearly

These are **preview values only**, not approved machine motion. An empirically calibrated brush-specific mapping is mandatory before runnable G-code.

Flat-bed assumption: no X/Y-dependent surface-height compensation in scope.

## Output / local checks

Python 3.10+, no external package requirements.

Run from repository root:

    PYTHONPATH=src python -m datascape.gcode examples/sample_machine_vectors.json /tmp/datascape_preview
    PYTHONPATH=src python -m unittest discover -s tests -p 'test_gcode_backend.py' -v

Each panel/medium produces a centerline SVG and a .preview.gcode.txt with all machine motion lines commented out. Outputs are not suitable for machine execution.

## Explicit non-goals

- No FluidNC connection, homing, G54 commands, calibrated MPos or machine movement.
- No station travel/dipping/washing/sponge purge/manual palette refill.
- No paper tilt compensation; no validated pressure or stroke-width transfer.
- No real restart/resume/checkpoint.
- No full Spring artwork export and no real-time or global time optimization.

## Physical prerequisites for next phase

1. Verify controller MKS DLC32 V2.2 pin wiring, FluidNC firmware, X left/Y rear/Z upper limit switches, correct motor signs, homing and emergency-stop behavior.
2. Confirm actual Z usable span (nominal 50 mm is a configuration value) and post-home location/pulloff; confirm safe XY and work coordinate registration for both panels.
3. Measure palette rim at nominal 27 mm, inkstone at nominal 15 mm, sponge <=20 mm, plus mounts/obstacles/brush clearance. Stations are bed-mounted; **historical negative dip Z does not apply**.
4. Define independently calibrated Work Z0, paper hover clearance, global over-station clearance, drawing compression envelope (target -12 mm, unverified), and station-specific load/wipe heights.
5. Nominal 32 mm setup drop and -12 mm drawing target are design candidates, NOT approved execution commands. For full clearance and -15 mm compression goals, revisit travel budget and available margins.
6. Calibrate brush width against commanded Z, speed, load, and pigment viscosity. Distinguish XY centerline from physical brush footprint.
7. Implement separate brush reload and manual palette refill. Gouache is pre-diluted and stored in squeeze bottles; palette wells are replenished as needed, not kept full.
8. Preserve order and source IDs across Spring exports. Record calibration artifacts, config checksum, dry-run results, and safe-stop recovery before any executable command generation.

## Legacy notebook provenance

Reviewed historical source notebooks: datascape_0317test.ipynb, datascape_0815_Taebaek.ipynb, datascape_0820_Taebaek.ipynb. Ideas reused: ink/color separation, XY/Z brush trajectories, panel handling, constrained ordering and refill/wash state planning. Their historical machine coordinates and negative dip Z are not carried into executable output.
