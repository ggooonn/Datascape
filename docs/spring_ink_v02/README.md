# Spring P2 ink refinement v02 / dual-brush offline review

Based on PR35 c2464d65e2b2203f2e4b5912377eb33097987dbc. No inherited files,
canonical geometry, source pressure, widths, projection, mist or catalogs changed.
Spring INK only. No controller operation, YAML change or merge.

## Physical feedback and conditioning

Operator reports substantially better small-Baegunmo P2, stable800mm/20 contacts
AFTER proper initial wetting, useful two-ink interaction and successful A terrain.
No measured width, exact runtime or fine-brush calibration is supplied.

Before EACH independent program: recover homing/registration, retain P2 global
X300–600; start G54(0,900,35). Manually wet/condition the installed brush, absorb
excess water consistently, load/test the selected initial light ink off-artwork,
and confirm stable delivery before releasing the initial M0. The program's first
automatic load refreshes this prepared brush; it does not replace conditioning.
No automatic conditioning contact is invented and no repeated in-job M0 occurs.
Each program ends with full retained cleanup and park(800,800,35)/M2. Do not chain
from an unknown state. Do not execute A and B on the same artwork unintentionally.

## Execution content and actual files

A SMALL_ONLY and B BAEGUNMO_MAIN contain the same1007 main strokes. A deliberately
defers202 necessary fine details to future color; B FINE_DETAIL executes these
202 after manual brush exchange.642 further sources defer to color in both.
No source is canonically deleted; zero qualify for the conservative redundant-
noise omission rule in this P2. All1851 original P2 sources have an ID-linked
record with family/depth/role, length, density proxy, source/width/pressure hash,
original and proposed concentration, classification and reason. Centers-within2mm
counts are density proxies, not measured wet-brush overlap or legibility.

Preserve all A source concentrations and accepted A relative execution order.
Retain principal A/B/D and major rock structures. Nonstructural far foliage and
short pads defer to pigment; selected subordinate branches/growth/rock details
use fine brush. Far growth/distant rock darkening is restrained. Near rock70%
dark is a source-count ranking candidate, not a global target or measured tone.
Actual by-family/depth/count/length allocations are in the generated report.

Protected DAG edges are projected THROUGH deferred nodes rather than discarded.
89 P2 fine candidates conflict with later main successors: subordinate details
are explicitly deferred; structural trunks remain main. This deliberate content
adjustment permits B1→B2 without overriding precedence or repeated tool changes.
Remaining fine→main edges:0. The original footprint DAG remains an authored-width
proxy, not a complete calibrated wet-media occlusion model. No new path joins.
Configuration/generator supports --panel P1 or P1P2 for later propagation; optional
panel programs were not exported here so P2 remains the review focus.

## Scheduling and runtime

Dependency-ready same-concentration work is drained before switching;10 contacts
is a soft useful-batch preference, never an order override. Every shorter forced
batch and reason is logged.800mm OR20 actual engagements still triggers same-ink
reloads without wash; actual concentration changes retain wash→PURGE→rewet→load.
Both ink concentrations occur in both B stages. Budgets reset per brush program.

Reference minutes: PR35 P2 93.655 (116 loads,22 switches); A58.884 (67loads,
12switches); B1 same58.884; B2 approx9.23 (12loads,2switches). B total68.11min;
manual exchange/conditioning overhead separately assumed5min, not measured.
Same revised selection/allocation in original restricted order takes87.333min,
106loads/59switches; this control separates selection/allocation from scheduling.
Full programmed handling/cleanup/dwell included. Inherited accelerations,
ASSUMED JD0.01/full lookahead; no feed increase, no measured physical runtime.
Generated runtime tables include drawing, engagement, station handling/transfer,
non-drawing travel, full wash visits and material loading. All6 programs have AIR
counterparts atZ35, sameXY, no contact. Previews use original authored widths;
they do not simulate physical brush width, pigment concentration or diffusion.

## Fine brush is NOT calibrated

The fine profile intentionally does NOT reuse Baegunmo Z10/10.2mm compression.
Purely provisional OFFLINE numbers: touch12, approach17, hover22; artistic
pressure/compression knots0:0,.2:.1,.4:.25,.6:.45,.8:.7,.93:.9,1:1mm. These are
illustrative coefficients, not measurements or recommended contact depths.
No change to canonical artistic pressure. Station contact levels are retained
only as unverified fine-brush review candidates, including inkstone/sponge/water.

Before any fine contact: measure installed first-touch and tool XY tip offset;
re-register the fine tip without changing artwork coordinates; determine safe
compression and monotonic pressure response, dry/wet mark width, endpoint taper,
20-contact/800mm delivery, water immersion/holder clearance and well/sponge/lip
contact. Replace provisional profile values and regenerate/reverify before use.
Run AIR after confirming elevated swept clearances. No calibrated Z is claimed.
Small brush keeps confirmed10/15/20 and original mapping (up to10.2mm/Z-0.2);
its safe ceiling and new-container swept clearance still require evaluation.
M0 is a manual review stop, NOT a safety interlock. No job is machine-authorized.

## Future color handoff

color_handoff.json.gz retains XY, IDs, family, owner, depth, intended role and
reason. Fine detail entries defer ONLY in A; B already draws them and must not
silently duplicate them as future color. Color-only642 entries apply to both.
Future base / structural-grouping / foreground-accent layers remain undecided.
Avoid strong physical D4 in Spring/Summer provisionally. No color palette change
or color G-code is included. Later color work must explicitly select its ink
variant and preserve its underlying ink print registration.

## Reproduce

Use the Python dependencies from docs/spring_physical_ink_v01/README.md.

```sh
PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 python -m benchmarks.integrated_330_v01.spring_ink_v02 --context /absolute/context --output /absolute/new-review
PYTHONPATH=src:. python -m pytest tests/test_gcode*.py -q
```

Outputs require new directories. Canonical source recovered only from pinned Git
objects/hashes. Original pressure samples are emitted unchanged and in original
vertex order. All physical mappings are separate execution profiles. Committed
.gcode.gz files are lossless complete numeric programs; decompress before review.
The downloadable package also includes plain G-code and numeric IR.
