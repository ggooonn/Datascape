# Spring P2 selective fine terrain support v01

PR39 baseline38b32a68bb58c502c4e0fba60eccf9205ecbd4c5 is frozen. No inherited
files, composition, projection, canonical XY/pressure/widths, concentrations,
station coordinates, feed policies, accelerations or YAML are changed.

## Result and bounded recommendation

Recommend including a LIMITED terrain-support role alongside vegetation detail,
subject to visual approval and fine-brush physical calibration.10 original main
sources move to fine:7 Soil ground/contact/support lines and3 rock feature-
shoulder lines,5 near/5 middle. No far additions, generated paths, extra overprint
or duplicated sources. Main997/fine212 retains exactly1209 intended ink sources;
1851 original P2 records remain accounted for,642 still deferred to color,0 omitted.
The principal terrain/rock mass remains small Baegunmo.

Local comparisons show selected heavy contact bars become delicate articulation
in the illustrative width view, leaving main ground masses readable. The effect
is deliberately small, not a second terrain texture field. It may be lost if the
fine brush spreads or has inadequate ink delivery; this is not physically proven.
A slightly smaller main brush may eventually help compressed A passages, but no
brush-family study or pressure adjustment is performed here.

A-line candidates were REVIEWED, not silently ignored: the protected A sequence
requires later main A strokes. Reassigning them to a final fine stage would break
that order. They remain main; no duplicate A overlay is used to hide this conflict.
Full candidate decisions and count/spacing/owner caps are in terrain_selection_review.
Fine support is selected from terminal dependency nodes: eligible ground roles,
3–24mm length, at least12mm between centers, at most2 per owner/12 overall. Major
rock contours/joints are protected. This is role/context selection, not a global
minimum-length deletion. The inherited depth bands and footprint DAG remain
proxies, not an authoritative calibrated wet-brush occlusion field.

## Comparison and complete programs

Variant A means the PR39 DUAL-BRUSH control, not PR39's small-only alternative.
The package contains its main/fine INK/AIR programs byte-for-byte from the pinned
Git blobs. Variant B contains:

- SPRING_P2_INK_TERRAIN_MAIN_REVIEW (+AIR):997 main sources.
- SPRING_P2_INK_VEGETATION_TERRAIN_FINE_REVIEW (+AIR):202 original details +10 terrain.

The old fine category already includes some structural rock details as well as
vegetation; no claim that it was literally vegetation-only. Revised source roles
name that inherited category fine_vegetation_detail for comparison continuity;
its exact original family/grammar is preserved in every record.

Use a COMPLETE matched pair for A or B, not A-main followed by B-fine: the latter
would duplicate the10 transferred sources. Existing physical PR39 prints already
contain those lines in main brush; a fine overlay cannot undo their broad marks.
A fresh registered P2 print is needed to compare this reassignment physically.

Main stays an exact PR39 subsequence with only those10 sources removed. The fine
stage is dependency-safe scheduled with unchanged concentrations and800mm OR20
actual engagements.2848 projected protected edges verified, including the A
relative-order barrier and paths through deferred source nodes. No extra manual
brush stage or deliberate short-batch concentration override is introduced.

## Visual evidence and limitations

Full A/B authored-width PNGs and layered SVGs preserve actual original geometry.
A/B width-proxy views scale fine DISPLAY widths by0.45, explicitly UNMEASURED.
This coefficient never changes G-code, pressure intent, original widths or XY.
Do not infer fine-brush calibration or pigment dilution from display alpha.
The SVG terrain support is teal for diagnosis, not a requested pigment change.
Three local matched crops and support map show the selected locations. Since
geometry/source content is identical, authored-width views should remain nearly
identical; the hypothesis being tested is the physical line-weight hierarchy.

## Numeric execution and readiness

Variant A reference:main58.884min/fine9.230min, total68.113min.
Variant B:main58.640min/fine9.551min, total68.191min, approximately4.7seconds more.
Both revised stages retain main67/fine12 loads and12/2 concentration switches.
Manual exchange/conditioning time is additional;5min from PR39 is only an assumption.
Model uses unchanged acceleration reference and ASSUMED JD0.01/full lookahead.
No actual runtime or line-width measurement is fabricated.

Both stages independently require manual conditioning (wet, absorb excess water,
load/test ink, confirm stable delivery), homing and G54 registration. P2 stays
GLOBAL X300–600; no coordinate shift or exhibition gap. Start0/900/35, final
800/800/35/M2. Do not chain from an unknown machine state. AIR is allZ35 and
retains matching XY; actual elevated swept clearance still needs inspection.
Washing, PURGE, inkstone loading/lips and terminal cleanup are unchanged.

Small Baegunmo retains confirmed Z10/approach15/hover20, no extra3mm offset;
pressure response unchanged, max compression10.2mm/Z-0.2. Safe ceiling is not
certified. Fine retains PR39's UNCALIBRATED numerical-only touch12/approach17/
hover22/max1mm curve. These are NOT measured or recommended operating settings.
Before fine contact, measure tip XY registration, actual first touch, safe
compression curve, stroke width/taper and20-contact/800mm delivery, and verify
water/well/sponge/lip/holder and connecting clearance. Replace provisional
settings and regenerate/reverify before use. Each INK starts with one M0, not a
safety interlock or machine authorization. No contact was executed in this Work.

## Color handoff boundary

642 color-deferred IDs, XY, family, depth, source roles remain unchanged. The10
fine terrain IDs are INK, not new color obligations. Source manifest explicitly
separates main/fine inherited detail/fine terrain/color/omitted. Next color Work
must select the approved ink candidate and combine it with PR40's seasonal color
framework. PR40 was not imported, modified or treated as approval here. No Spring
color G-code, seasonal palette design or new D4 assignment is generated.

## Reproduce and verify

Use PR39's documented Python dependencies. From this repository root:

```sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_fine_terrain --context /absolute/context --output /absolute/review-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_fine_terrain --context /absolute/context --output /absolute/review-b
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_fine_terrain --verify --context /absolute/context --output /absolute/review-a --independent /absolute/review-b
PYTHONPATH=src:. python -m pytest tests/test_gcode*.py -q
```

New output directories required. All original1851 source/width/pressure hashes,
reassigned source set, stage disjointness, protected order, numerical XYZ/feed/
dwell/pressure vertices, material engagements, terminal park and AIR Z35 are
verified.247 tests pass,2 inherited conditional fixture tests skipped. Public
review stores lossless complete .gcode.gz; decompress before inspection. The
package also contains plain G-code, full IR and all local comparisons. Keep Draft;
do not merge. Formal machine authorization remains false.
