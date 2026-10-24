# Integrated 330 mm physical benchmark v01

## Current large-Baegunmo Spring integration

Current complete review programs with terminal water washing and sponge purge
are under [review_spring_end_cleanup](review_spring_end_cleanup/README.md).
Standalone cleanup files start at the previous completed job's park800/800/35,
not post-home. Running streams are unchanged. The frozen1100/700 painting prefix
is preserved; terminal cleaning is appended after its park and before M2.

The final physical benchmark is operator-reported completed. The current Spring
profile and full AIR/INK/COLOR review files are under
[review_spring_reload_1100_700](review_spring_reload_1100_700/HANDOFF.md).
Current reloads are ink1100/color700, requested after initial AIR feedback.
The previous1500/1000 files and optional2000 profile remain preserved under
[review_spring_large_baegunmo](review_spring_large_baegunmo/HANDOFF.md). Paper
first-touch10 + relative hover10 = absolute20; approach+5 =15.
The0..12mm compression candidate is separate from the
historical Z-8 curve. Stations/YAML/G54 and all canonical artwork remain unchanged.
The entries below are preserved chronological benchmarks, not current Spring
operation settings. See the current handoff for full files, observations and
remaining distinction between offline review and formal machine authorization.

## Previous paper-reference correction / preserved benchmark

Use [review_paper_reference_1500](review_paper_reference_1500/README.md) and its
`profile.paper_touch10.ink1500.json` for the current handoff: first-touch is
approximately G54Z10, paper-only compression formula is Z=first-touch−compression,
and preferred Spring reloads are ink1500/color800mm. The final test repeats all
15 physical depths twice:30×50mm=1500mm, single automatic ink load/no reload.
Prior negative-Z benchmark files below are HISTORICAL, not1..7mm tests under
the corrected mounting/reference. Do not run them with their former labels.
All absolute station Z/YAML/G54 coordinates remain unchanged. Final Spring
pressure normalization is pending physical results; the Z−8 curve is only a
historical/provisional reference. `spring_handoff.json` identifies this current
profile; `spring_pipeline` accepts its corrected reference/motion/reload policy.
The older workflow below is retained for reproducibility, not current operation.

The operator workflow now has **two principal jobs**, `BENCHMARK_AIR.gcode` and
`BENCHMARK_PAINT.gcode`. PR28's original plans remain immutable source components,
not thirteen separate operator sessions. Base: PR28
`29fccadc9a270afe65d46c7e8711c5c2ec0d8ea8`; Backend v0.3 and Local Hover are reused.
No Spring artwork, pressure samples, S3a order, controller settings or prior PRs
are modified. No device I/O is implemented or performed.

## Current physical record

`design.py` preserves the operator's actual Idle transcript: FluidNC v4.1.1,
MPos and G54 WPos `(0,898,35)`, G54/G92/TLO zero, repeated homing/directions/limits
working. `config.installed.yaml` is the supplied installed file, SHA256
`884fb232dfbe9f5396155f5ad90c231458913a29aaa723e415ba5a4ee2ed3280`.
It replaces the old `config(2).yaml` as the input for this workflow. The legacy
V2.1 board label is retained for the reported V2.2 hardware. Nothing is written
to FluidNC, and YAML comments are not interpreted as motion instructions.

The configured axis-reference box is X0..850 / Y0..898 / Z-11..35. It is recorded
as configured/reported travel, not invented swept free space. The checked paper
and park interference reports are retained. The independent manual-review
A_SHORT numerical check is **not** recorded as an authorized backend Air result.
Only explicit reported controller/G54 and normal-hover/park preflight facts are
bound into evidence; no emergency-stop, Z5 trial or actual Air outcome is invented.

## Two jobs

| Motion | Initial candidate mm/min |
|---|---:|
| Air XY / Air paper-path simulation | **5000** |
| Ordinary dry XY travel | **5000** |
| Painting contact XY | **600** |
| Wet XY departure / main / arrival | 300 / 600 / 300 |
| General Z / paper approach | 300 / 300 |
| Paper contact / release | 60 / 60 |
| Pressure-driven Z cap | 120 |

F5000 is an explicit Air/dry-only field; it cannot become the painting feed by
selecting the integrated workflow. The installed accelerations remain
1200/1200/1000 mm/s²; slow feed does not change them. Wet/contact trial limits
still need an approved profile. Z5 is the proposed approach boundary and local
hover, pending the integrated Air inspection/result. No faster-contact trial is
silently added.

**Air:** reuse A_STABILITY's four rectangles and two 301-vertex stream sweeps,
then simulate B_DEPTH_1/2/3, C_LOW, D_HOVER and short color marks without contact.
Z10 is normal; eligible D_HOVER links stay at Z5 without a rebound to Z10.
Station transfers use Z32; final park is X800 Y800 Z32, M2. First XY transfer
stays at the actual initial Z35. Default Air has **zero M0**.

The Air profile starts at `(0,898,35)`. The separate paint profile expects the
Air final park `(800,800,32)`, conditional on actual arrival and fresh pre-run
verification; there is no redundant automatic homing between jobs. These
expected positions are not auto-confirmed current positions.

Only `air_station_roles` explicitly selected in both plan and profile may be
visited. Each requires G54 center, scoped `air_station_ROLE` evidence and complete
full-tool path validation. Unknown station XY/corridors are omitted from the
executable scope and retained as unresolved offline station references. The
default selection is empty; this does not claim that station Air trials passed.
An independently verified cloth Air approach may be selected while cloth
contact remains disabled; its unmeasured compression does not block Air.

**Paint:** load ink WELL_2; -1/-2/-3 mm lines; C_LOW; Z10 versus Z5 groups; wash
WELL_1 with controlled sloped withdrawal; optional cloth; one representative C1
gouache load/short -1 mm mark; park and M2. C2 is an optional second color, with
another wash before loading. Existing palette-loading and station primitives,
floor-gap checks, measured contact envelopes and synchronized XYZ are reused.

Default paint has **10 intentional M0s**, in order: startup; first ink immersion;
ink/first -1 contact; inspect -1 before -2; inspect -2 before -3; inspect -3 before
C_LOW; inspect pressure before Z10; inspect Z10 before Z5; first water immersion;
first color dip. Cloth adds an inspection before each cloth contact. Two colors
without cloth have 12 M0s; two colors with cloth have 14. No final cleanup or
final M0 is forced. A failed observation means abort, not automatic continuation.

The -1/-2/-3 observations are reviewed at unconditional M0s within this job before
C_LOW and hover tests. This replaces the standalone plans' prior-paper-contact
dependency **only inside this fixed ordered renderer**; no evidence is persisted
or production local hover enabled. Standalone calibration prerequisites remain.
Actual backend Air evidence is still required before paint export.

## Well and color inputs

WELL_1 is water, historical X840/Y220..285; WELL_2 is ink, X840/Y370..435.
The historic midpoint is a reference, never a fabricated deep/shallow point.
Supplied bed levels are liquid 10..11, deep floor 6, shallow floor 10 mm. With
only the prior approximate 1 mm paper elevation, nominal G54 values would be
liquid 9..10, floors 5/9, first 2 mm dip 7..8; these are **not entered as measured
G54 contact values**. Exact G54 deep/shallow XYZ and actual liquid level remain
null. The existing two-point withdrawal enforces positive floor gap throughout.
Initial well immersion is 2 mm; 3 mm needs a later reviewed expansion.

Conservative trial candidates are contact feed60, dwell1s, gap1 and exit2 mm,
one wash pass, and 5 mm wet departure/arrival. They are labelled unapproved
configuration choices, not measurements. Confirm them with actual well geometry
and initial motion authorization. Contact volumes and color levels/loading
geometry are not guessed. C1's historic `(824.5,721.5)` and optional C2's
`(824.5,754.5)` still need G54 registration. Cloth is disabled by default, so
missing cloth height/compression does not block either default job.

The mixing reference is approximately 50 mL water + six small palette-knife
scoops of gouache; pigment mass/concentration is unmeasured.

## Safety and reproducibility

Air no longer requires unused pressure/contact/wet fields or junction deviation.
Axis caps, offsets, homing/stop evidence, paper clearance, complete swept paths,
park and hash-bound stage authorization remain required. An unknown junction
deviation produces an unavailable timing estimate, never a fabricated model.
Wet/contact stages retain their acceleration and calibration checks.

Air-result evidence is tied to hardware, controller/axis configuration, G54 and
dry policy. Adding later wet parameters or a separately verified subsequent job
start does not require repeating a passed Air trial. Current start, obstacle and
full swept-path checks remain mandatory for every new job.

Axis-reference bounds are not eroded by the tool radius, which would wrongly
reject a real homed reference point on its axis limit. Obstacle expansion and
full-tool corridor checks remain. Legacy tool-envelope bounds retain erosion.
As an alternative to measured full-tool free-space boxes, an operator may
inspect the **exact G54 segments** in `AIR_FULL_TOOL_SEGMENTS.TO_CONFIRM.json`.
Only after inspection may they become `machine.validated_free_segments` with
current `swept_clearance` evidence. This route uses axis-reference bounds and an
explicit inspected empty keepout list; it never certifies surrounding space or
accepts an off-path segment. If obstacles are modelled, a measured tool margin
is still required. No segments are automatically marked inspected.

Generate offline reviews (requires repository dependencies and PyYAML):

```bash
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.run --output /new/review
```

The generated actual-profile export attempts must fail without partial output.
The previews are entirely comments, preserve unresolved station operations and
are checked with PR28 `write_review`/`verify_review`. A SHA256 manifest covers all
review files. These checks are not physical evidence or executable read-back.

After actual profile/evidence and **separate job authorization** are supplied:

```bash
PYTHONPATH=src python -m datascape.gcode.production integrated \
  --kind air --plan integrated.plan.json --profile profile.measured.json \
  --authorization BENCHMARK_AIR.authorized.json --output /new/air-export
PYTHONPATH=src python -m datascape.gcode.production verify --output /new/air-export
```

Use `--kind paint` with separate calibration-stage authorization for
`BENCHMARK_PAINT`, after actual Air results and all selected contact parameters
are supplied. Export/verification reuse the existing atomic writer, serializer,
dialect/XYZ/feed checks, SHA256 and authorization. Delivered verification also
regenerates the complete IR from the authorized plan and detects rehashed
trajectory changes or unmanifested `.nc`/`.gcode` files.

After one consolidated physical-results review: calibrate brush, washing, color
loading and hover; then full Spring Air -> SHARED_INK / SHARED_COLOR through the
existing v0.3 exporter. No new artwork or scheduling study is needed.
