# Spring P2 selective A-layer brush hierarchy v01

Pinned PR41:172601cbe9e19d013d159b9dc9cd64b985c1ae1f. All inherited files stay
unchanged. Review only; no merge, controller operation, color G-code, palette
change, YAML, station coordinates, feed policy or acceleration change.

## Recommended candidate B

Transfer12 LIGHT A sources from main to fine, in3 locally crowded MIDDLE-distance
ground groups. Main997→985; fine212→224. Only12 of704 P2 A sources move (1.7%);
all dark A sources and long principal mass strokes remain broad-brush. No uniform
thinning, alternating-brush parity, geometry edits or new contours. All1209
intended ink sources,32403 pressure vertices and642 color deferrals remain.
Actual reassigned IDs, per-source evidence and every rejection are supplied.
Near regions are studied but not forced into B: sufficiently crowded near A
candidates still have essential main successors. B is a bounded proof of the
role, not a claim to resolve all physically merged areas in Spring.

## What PR41 actually rejected

PR41's120 reviewed A candidates encountered more than an occlusion barrier:
(1) its generation added a consecutive global A chain, and (2) its selector also
contained explicit blanket A-family retention after the descendant check.
Historical reasons and code locations are in historical_A_rejection_audit.json.
The new selector replaces that blanket rule with spatial/context evidence.

The original6834 protected edges are ALL retained, including actual authored
footprint overlaps,0.5mm proximity guard, owner-local and parent-contour order.
Of703 added global A-chain pairs,325 are released ONLY when absent from that
original DAG, different parent contours and separated beyond the0.5mm authored-
footprint guard. Every pair has IDs, measured footprint gap and retain/release
reason. This is evidence about execution constraints, not permission to remove
artistically protected overlap. All projected predecessor paths through deferred
sources remain. Fine B has no main successors under this retained graph.
The discarded chronological pairs are independent inter-contour scheduling
preferences; changed wet-media timing still requires physical observation.

## Spatial diagnostics and limits

Use9 interior arclength samples per A source and nearest other-parent contours
within8mm, same depth band and within20% preserved forward depth. These are XY
spacing measurements, not screen-Y elevation assumptions. Crowded means at least
2 neighboring contours and median spacing in the lower40% of that depth band,
subject to a5mm cap. Main long strokes/dark concentration are protected; select
at most24 sources/8 per70mm local group/3 groups. This spatial selection admits
12 sources with median spacings approximately0.58–2.19mm in3 middle groups.
No selected source or local spacing is geometrically moved.

Physical Baegunmo width is UNMEASURED. The operator reported merging but supplied
no calibrated mark-width samples. Diagnostics include1/2/3/4/5mm width sensitivity
fractions, not invented measured width. Full and local previews use authored
widths with a clearly unmeasured0.45 fine display factor. Additional2mm-main/
0.5mm-fine A-only constant-width sensitivity crops deliberately magnify the
hypothesis; they are NOT physical predictions or pressure/ink changes. Density
histograms remain identical because XY is frozen. Real layered SVGs and exact
source-role/pressure/width hashes are included.

## A/B/C comparison and manual sequence

A: PR41 allocation,2 programs. Its fine program is REGENERATED with the newly
required450mm/10 policy; do not confuse its timing with historical800mm/20.
B:12 selected middle A transfers,2 programs,985 main→224 fine. Preferred.
C: B plus1 explicitly blocked near A source,3 programs:981 main→225 fine→3 main.
All essential dependencies are preserved. Returning/re-registering the main brush
for3 final sources is operationally weak for just1 extra8.87mm near contour.
C has complete optional numeric files and AIR, but is not recommended by default.
No localized pressure change is needed or adopted.

A separate counterfactual retaining the full artificial global A chain would
require22 alternating programs for the B allocation. This is NOT C, not an
essential occlusion requirement, and not a proposed workflow. The exact
role-switch stage lower bound and witness are documented. Actual C needs3
programs under the evidenced retained graph. Its visual differs from B only at
the extra near A line; stage chronology is not physically simulated by the image.

Use each complete matched set independently. Do not mix A-main/B-fine or B-main/
C-fine; that would duplicate/miss reassigned lines. Existing PR41 prints already
contain these broad strokes. Fine overprinting cannot erase them; compare on a
fresh registered P2 panel. P2 always stays G54 GLOBAL X300–600.

## Reloads and modeled times

Small Baegunmo800mm OR20 actual engagements; fine450mm OR10, independently per
brush program and concentration. Reset distance AND contact count on load;
same-ink replenishment never washes. Actual light/dark changes retain existing
wash/PURGE/rewet/load. Never interrupt original source continuity; threshold
overruns are explicit. Stage counts/loads/reasons/station visits and complete
XYZ/feed/dwell/pressure IR are supplied.400/500mm fine sensitivities retain the
same23 B-fine loads here: contact-count dominates, not measured ink capacity.

| Candidate | Main/fine sources | Modeled minutes | Manual exchanges |
| --- | --- | ---: | ---: |
| A with fine450/10 | 997/212 | 71.198 | 1 |
| B preferred | 985/224 | 71.065 | 1 |
| C near extension | 981/225/3 | 70.679 | 2 |

C's numerical route happens to be slightly faster after dependency-safe
rescheduling; the extra exchange dominates practical uncertainty. Assume5min
PER manual exchange/conditioning/registration only for comparison: A76.198,
B76.065,C80.679min. These are assumptions, not measured delays. All programmed
station handling, transfer, engagement and terminal cleanup are included in
modeled time; manual M0/conditioning/drying/controller effects are not measured.
PR41 historical total68.191min used fine800/20 and is preserved separately.
The more conservative fine450/10 adds loading time, not artistic strokes.

## Physical boundary

All numerical files are OFFLINE REVIEW ONLY. Small brush retains confirmed
first-touch10/approach15/hover20, no additional3mm backing offset, pressure
response unchanged up to10.2mm compression/Z-0.2. Safe measured ceiling remains
uncertified. Fine retains the explicitly PROVISIONAL PR39/41 contact12/approach17/
hover22 and max1mm curve. Those values are NOT measurements or recommended Z.
Before any fine contact measure actual first touch, monotonic safe compression
and mark-width/taper, wet ink retention under450/10, tip XY registration after
exchange, paper registration, well/water/PURGE/lip/holder and connecting swept
clearance. Replace provisional profile and regenerate/reverify. For C, reinstall
and re-register the small brush before stage3; do not assume remounting repeats
Z10 or XY exactly. No G54 shift is emitted automatically.

Each file requires a known registered start0/900/35 and ends800/800/35/M2. Manually
wet, absorb excess water, load/test ink and confirm stable delivery before its
initial M0; same-ink reloads are not initial conditioning. One M0 per independent
program, not repeated in-job pauses and NOT a safety interlock. AIR is allZ35
with matched XY, not a physical collision certificate. No contact executed here.

## Reproduce / validate

Use PR39's Python dependencies and fresh absolute output directories:

```sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_a_hierarchy --context /absolute/context --output /absolute/review-a
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_a_hierarchy --context /absolute/context --output /absolute/review-b
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_a_hierarchy --verify --context /absolute/context --output /absolute/review-a --independent /absolute/review-b
PYTHONPATH=src:. python -m pytest tests/test_gcode*.py -q
```

253 tests pass;2 inherited conditional fixture tests skipped. All14 numerical
programs (A4/B4/C6) are parsed against full IR, axis/feed bounds, unchanged source
XY/pressure/direction/width hashes, exact stage set completeness/disjointness,
retained dependencies, material counters/limits, AIR Z35 and terminal park.
Compressed programs are lossless complete G-code; decompress before inspection.
No Spring color execution begins. Color handoff preserves642 deferred sources;
A reassignment is INK, not extra color. Later color work must use the reviewed
ink candidate plus PR40 seasonal framework. PR40 is not imported or modified.
