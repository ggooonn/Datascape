# PR42 B fine-brush target Z10 / provisional5.5mm profile revision

Pinned PR42 cf010e6f41de36baee83ed7a04cacbc3f0931e23. Separate revision only;
keep Draft and do not merge. All inherited files remain unchanged. No controller
operation, color G-code, composition/catalog/geometry/pressure-intent change,
YAML, G54, station coordinate or global feed-policy change.

## What is preserved and what changes

B-MAIN985 and B-FINE224 sources, original vertex order, source IDs,3481 fine
artistic pressure samples, concentrations, protected source order and exact
material schedule are preserved. B-MAIN INK and AIR are copied BYTE-FOR-BYTE,
with their original filenames/headers. Do not regenerate or remount the main
brush differently just for this revision.

Fine paper target is touch10/approach15/hover20 with ZERO added mounting or3mm
substrate offset. This is an operator mounting TARGET, not measured fine-brush
first touch. Fine station contacts stay in absolute G54; no−2mm station shift.
The new physical response changes only paper XYZ Z mapping, necessary synchronized
feed limiting and derived runtime. XY itineraries and command sequence remain
identical; station XYZ/feeds/dwells are exactly unchanged. No feed is increased.
Fine450mm OR10 actual engagements and small800mm OR20 remain independent per
program/concentration, both counters reset on load. Same-ink replenishment has
no added wash. Fine23 loads (16 light/7 dark),20 same-ink replenishments,2 actual
concentration switches and3 terminal water-wash visits remain identical.

## Mapping: profile ceiling versus actual dataset use

Preserve PR42 fine curve shape (historical1mm ceiling), multiply compression
ordinates by5.5. Sensitivity profiles multiply by5 or6. Monotonic and gradually
stronger with artistic pressure; no per-dataset renormalization, extrapolation,
pressure clamp or modified artistic values. Every candidate uses LESS intended
compression than the small Baegunmo at the same artistic pressure. This is not
calibrated force, width, darkness or proof of physical safety.

| Artistic pressure | Fine5.5 compression | Absolute paper Z |
| --- | ---: | ---: |
| 0 | 0 | 10 |
| .20 | .550 | 9.450 |
| .40 | 1.375 | 8.625 |
| .60 | 2.475 | 7.525 |
| .80 | 3.850 | 6.150 |
| .93 | 4.950 | 5.050 |
| 1 | 5.500 | 4.500 |

Actual B fine artistic pressure is .27–.7368563078158471, not0–1. Therefore:

| Profile ceiling at pressure1 | Actual compression range | Actual paper Z range | Fine modeled minutes |
| --- | --- | --- | ---: |
| 5mm | .7625–3.105352 | 6.894648–9.2375 | 13.451 |
| 5.5mm selected | .83875–3.415887 | 6.584113–9.16125 | 13.485 |
| 6mm | .915–3.726422 | 6.273578–9.085 | 13.518 |

The full5.5 candidate does NOT force any stroke to5.5mm. The progressive test can
reach that ceiling only after individual operator checks. Static test success is
not approval of every dynamic pressure transition. Main modeled time57.895min
unchanged; selected combined71.380min vs PR42 B71.065min. These retain reference
acceleration and ASSUMED JD0.01/full lookahead, exclude manual gate/conditioning/
registration/drying delays, and are not observed physical times.

## Complete ordinary G-code

Recommended numerical comparison pair:

1. SPRING_P2_INK_B_SELECTIVE_A_MAIN_REVIEW.gcode (unchanged PR42).
2. SPRING_P2_INK_B_FINE_Z10_C5P5_REVIEW.gcode (new profile candidate).

Each has matching AIR. C5P0/C6P0 are separate alternative FULL fine programs, not
additional passes; never run sensitivity programs successively on the same art
unless deliberately testing overprint. Use only the matching B main/fine set,
not other A/C variant stages. Exact source/material/station audits and mapping
ranges accompany the files. Repository copies are lossless .gcode.gz; decompress
before review. The package also includes ordinary G-code and full fine IR.

Every full job independently assumes known G54 start(0,900,35), ends park
(800,800,35)/M2; no homing or offset write. P2 stays globalX300–600. Before each
installed brush program, manually condition (wet, absorb excess, load/test ink)
and verify stable initial delivery/registration. Full INK has ONE initial M0,
not repeated in-job review stops and NOT a safety interlock. AIR allZ35 retains
XY but is not an elevated swept-clearance certificate.

## Progressive paper contact test (sacrificial sheet only)

Use FINE_PROGRESSIVE_CONTACT_UP_TO_5P5_REVIEW.gcode AFTER verifying target first
touch10 and the test area/holder clearance. Matching AIR is supplied. Separate
optional6P0 test extends the same progression to6mm, not an approved safe limit.
Use disposable paper, NEVER the actual Spring composition for these test marks.
The20mm horizontal lines occupy globalX340–360, Y700–796 for5.5 (toY804 for6),
within the same P2 frame. Placement map and per-level JSON label every mark.
Start/reference and park conventions match the full files.

13 compression levels:.25,.5,.75,1,1.5,2,2.5,3,3.5,4,4.5,5,5.5mm. One initial
mount/conditioning stop plus one M0 before EACH level (14 total). Inspect the
previous mark and assess the next depth; abort rather than continue when bowing,
splitting, paper damage, abnormal resistance or holder clearance is unsuitable.
No automatic progression after M0 is assumed safe. Do not blindly resume all
stops. Optional6mm program has14 levels/15 stops and minZ4;5.5 has minZ4.5.

Calibration ONLY uses deliberately slow contact/compression/release Z300mm/min
and drawing600mm/min; noncontact travel retains the existing policy. These slow
feeds are NOT changes to the full painting jobs, which retain production motion
policy. After safe depth checks, separately evaluate representative strokes at
full-job speed and material delivery before considering full contact execution.

To avoid touching unverified fine-brush stations during PAPER calibration, this
test has NO automatic dip/water/wipe/lip/PURGE routine. Manually condition/load
LIGHT ink initially and replenish the SAME ink before level11 (after10 contacts,
200mm) at its labeled pause. No wash is required for same-ink replenishment.
The test logs manual reload counters; the full job's normal automatic routines
remain unchanged. Manually clean the brush after the paper-only test. The6mm
alternative restarts at shallow depth on a fresh sacrificial area; it is not an
extension to stream automatically from the previous park.

## Station-depth review and required physical checks

Full fine program total numerical bounds:X0–850,Y45–900,Z1.5–35. The minimum1.5
is PURGE, NOT paper compression. Station audit proves every station target,
feed, dwell, XY path and order matches PR42 despite the changed paper reference.

| Location | Retained nominal commands | Checks before fine operation |
| --- | --- | --- |
| WELL_1 light ink center840/252.5 | dipping targets includeZ7,7.5,9,11,17.5; approach12; lip20 | actual fluid level, bottom/rim, brush/holder immersion and withdrawal |
| WELL_2 dark ink center840/402.5 | targets includeZ7.5,8,9,11,17.5; approach12; lip20 | same checks, keep concentrations distinct |
| Shallow wipe | surface9,1.5mm nominal compression →Z7.5; existing XY unchanged | fine tip/holder compliance, ledge and lip geometry |
| New water840/45 | selected immersion20, vertical release22, approach/withdraw25; lip790/45/25→775/45/25 | liquid/bottom/holder clearance and connecting swept paths |
| PURGE840/137.5 | contact1.5, approach/release3.5 | cloth surface height, compression and available compliance |
| All station transfers | globalZ35 | full mounted-tool envelope, fixtures and registration |

Do NOT derive any of these values from paper touch10 or add/subtract2mm. Their
fine-brush suitability is unverified even when the previous brush worked.
The encoded station trial coordinates are preserved, not re-certified.
The paper-to-global35 departure lift now starts at paper hover20 rather than22;
that changed vertical paper leg also requires swept-clearance review. This does
not shift the station contact targets or fixed station paths.

Contact-ready status remains FALSE. Physically confirm actual fine touch10 and
paper flatness, safe compression/mark-width/taper, tip XY registration,450/10
ink retention and all station checks. Replace/regenerate this provisional curve
if observations disagree; do not silently clamp pressures or shift stations.
No physical pass/fail result is fabricated. Small brush contact reference and
pressure mapping stay frozen; its previously unmeasured safe ceiling is not
newly certified by this Work.

## Reproduce / verify

Use the same Python dependencies as PR42. From the repository root:

```sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_fine_profile --context /absolute/context --output /absolute/review-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_fine_profile --context /absolute/context --output /absolute/review-b
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_fine_profile --verify --context /absolute/context --output /absolute/review-a --independent /absolute/review-b
PYTHONPATH=src:. python -m pytest tests/test_gcode*.py -q
```

Fresh outputs required. Original PR42 fine IR is deterministically reconstructed
and proved BYTE-IDENTICAL to the pinned full G-code BEFORE retargeting. Exact
material manifests, command order, XY, source IDs/pressure/width hashes remain.
All12 output programs receive complete numerical readback or exact pinned-byte
verification. No artwork regeneration, palette change or color G-code.

Validation at this checkpoint:259 tests passed;2 inherited conditional fixture
tests skipped. Independent regeneration matches every manifest-covered file
byte-for-byte. Main remains pinned PR42 bytes, not a visual approximation.
