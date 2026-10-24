# Flat330mm C2 four-condition point benchmark

An additive comparison study inside the Hanji project, not a change to the relief artwork, C source, main3mm/1s/20-contact settings, Spring artwork or shared backend.

**Baseline inspected2026-10-25:** Draft PR33 head `b53719eaad224c9caba1c142c8ce519f6c2bd5f7`, based on still-unmerged Draft PR32 `eda6069b12c8785d458a0e8a567a9a86980bc394`. Both remained unchanged when this study began. Continue the existing `feat/hanji-relief-stipple-v01` branch and Draft PR33; do not merge or rewrite existing commits.

## Four conditions

| Front-view location | ID | Additional Z compression | Full dwell at depth | Integrated run rank |
| --- | --- | ---: | ---: | ---: |
| Upper right | Q1 | 4mm | 0.5s | 2 |
| Upper left | Q2 | 3mm | 0.5s | 1 |
| Lower left | Q3 | 3mm | 1s | 3 |
| Lower right | Q4 | 4mm | 1s | 4 |

C2 and the current large Baegunmo are held constant. Q3 is the current artwork baseline. Paper coordinates are lower-left0/0, upper-right330/330, X right/Y up. Quadrant centers are Q1(247.5,247.5), Q2(82.5,247.5), Q3(82.5,82.5), Q4(247.5,82.5). Paper mounting is a separate G54 XY translation; equipment stations never move with it.

## Same original40 points, translation only

The immutable PR33 `C_dots.csv` has390C2 points on physical panel4. Select the40nearest to local(100,100), using exact-decimal squared XY distance and `study_dot_id` tie-breaks. Their source bounds are X75.25…129.70/Y70.30…124.75: **54.45×54.45mm**. No125mm fitting fallback is needed. A deterministic source-anchor fallback is implemented only if that default patch would not fit; scaling is never allowed.

Center this exact bounding box in each quadrant using translation only. Do not scale, rotate, mirror, snap, homogenize spacing, generate new grid points or retain relief Z as contact geometry. All40source IDs, relative coordinates, pairwise displacements and the same relative execution order are preserved. Selection rule, source hash, IDs and bounds are recorded in `review/selected_source_patch.json`.

The first occupied Y row starts right-to-left, then occupied rows alternate X direction while Y increases. Translation does not change row grouping or direction. Same index1…40 always means the same original source point across all four conditions.

Source IDs are provenance; execution IDs use the separate `FLAT_C2_330_V01:Qn:S<study_dot_id>` namespace. Plan, mapping and observation records explicitly set `artwork_completion_eligible=false` and infer zero physically completed contacts. They cannot serve as a parent Hanji physical-completion record or exclude artwork dots.

## Flat Z reference and unchanged motion

`config.json` records the PR32 flat first-touch **G54 Z10** as a numeric review reference, not a fresh measurement of today's mounting. No later mounting/brush correction was supplied and both referenced heads are unchanged. Actual paper lower-left mounting XY and retained brush/paper first-touch still require confirmation. The default XY0/0 is an explicit nominal placement; no new hardware/station/firmware assumptions are requested.

`Z_press = Z_flat_first_touch − additional_compression`

Thus reference touch10 gives press7 for3mm and press6 for4mm, approach15, paper hover20, station/parking clearance35. Original varying `z_design_mm` is retained only in the mapping's `source_z_design_mm_REFERENCE_ONLY` field. It is never added to touch10. No normalized pressure curve is used.

Reuse PR33 `DotMaterials`, the existing PR32 `RuntimeBuilder`, independent station feed/geometry grammar, serializer, configured axis/Z velocity checks, timing and terminal-cleanup renderer through imports. A small flat-only point adapter emits fixed-XY approach → touch → press → G4 dwell → controlled release → hover. Full0.5/1s dwell remains after target arrival; descending/ascending time is extra. Source inspection already documented in PR33 confirms FluidNC v4.1.1 G4 Pseconds and planner synchronization before dwell.

Motion settings are identical across conditions: dry/used-return maximumF15000, wet travel maximumF12000 with inherited edge zones, noncontact ZF7000, paper contact/compression/releaseF2000. Station immersion/agitation/withdrawal/wipe/lip feeds remain unchanged. The current X0…860/Y0…900/Z−11…35 reference envelope is checked separately from unmeasured full-tool/fixture clearance. No homing, G92, offset/config writes or routineM0 are added.

## Preparation, refill and final cleanup

Every condition, **including the first**, executes the existing wash → absorbent water control → controlled rewet → initial C2 loading procedure. The same C2 absorbent policy is explicitly used even for a clean first brush. A used brush retains the contact-aware used return to the first water station; the paper contact budget is then cleared before freshly washed water/rewet travel so later preparations do not inherit20used contacts.

Each condition: initial supply,20contacts, same C2 reload **after20has completed/retracted and before21**, then20contacts. No wash accompanies that middle refill. No extra supply follows40. Next condition starts its own full preparation and resets to0. Station contacts and transit do not consume paper-dot contacts. Genuine drawing distance stays0; no fake distance or sensed-pigment estimate is introduced.

Integrated order is **Q2 → Q1 → Q3 → Q4**,160contacts, four initial preparations, four initial C2 supplies plus four middle supplies = **eight pigment supplies**. After the last condition, reach the inherited800/800/35park and append the PR32 FROM_PARK terminal IR once: water3visits×10s/three agitations each with existing withdrawal/wipe/lip; sponge2×4s; no final rewet/load; park/M2. Every standalone40-point program has its own start0/900/35, initial preparation, two supplies, one final cleanup and park/M2.

Integrated and individual files are alternative executions. Do not run them unchanged sequentially on the same marked paper. This study does not set a new C2 dilution, binder concentration, brush water state or pigment-consumption model. Record and hold those material conditions constant.

## Delivered files

[`review/`](review/) includes five actual numeric G1/G4/M2 programs, explicitly **offline reference review, not machine-authorized**:

| File stem | Contacts | C2 supplies | Independent modeled duration |
| --- | ---: | ---: | ---: |
| `FLAT_C2_330_ALL_Q2_Q1_Q3_Q4` | 160 | 8 | 10.45min |
| `FLAT_C2_330_Q1` | 40 | 2 | 3.62min |
| `FLAT_C2_330_Q2` | 40 | 2 | 3.62min |
| `FLAT_C2_330_Q3` | 40 | 2 | 3.98min |
| `FLAT_C2_330_Q4` | 40 | 2 | 3.99min |

Independent times each include their own final cleanup; the integrated time is not their sum because final cleanup occurs only once. The existing acceleration model uses configuration-reference1500/1500/1000mm/s2 and assumed JD0.01/full lookahead. Streaming, steps, wet marks and brush dynamics are not measured. At-depth dwell alone is120s integrated,20s for each0.5s condition,40s for each1s condition. `time_breakdown.csv` and `verification.json` separate noncontact XY/Z, controlled contact, depth dwell, preparation/supply/round-trip, middle refill/round-trip and terminal cleaning. Integrated condition allocations use the same continuous planner model without adding stops at quadrant boundaries.

- `flat_C2_layout.svg`: only160display marks and paper outline, no numbers.
- `flat_C2_numbered_guide.svg`: condition/run order,1…40, first point,20/21, lifted-route arrows, paper/central bounds.
- `flat_C2_numbered_guide_330mm.pdf`: one330×330mm print page. Print at100% for exact dimensions, or tile on a smaller printer. These are guide annotations, never painting strokes. The SVG has a2mm outer viewing margin while its paper outline remains330mm.
- `Flat_C2_Review.html`: self-contained front views, schedule, time breakdown and registration limits.
- Each `.mapping.csv`: experiment ID, original ID, condition/global order, original and translated XY, flat touch/press/dwell and refill counters.
- Each `.plan.json`, `.profile.json`, `.trajectory.json.gz`: full reproduction and independent numeric readback records.
- `observations_by_contact.csv`: matched original points for four conditions, including dry width/height, bleed, density, neighboring overlap, paper deformation and material/run notes.
- `observations_by_window.csv`: comparison windows1–5,16–20,21–25,36–40.

Display mark diameter2.8mm is explicitly unmeasured. Large-brush marks may be larger/overlap; no physical spread prediction or original-dot reduction is made. Compare corresponding point indices between conditions; differences among different positions within a patch are not proof of pigment depletion.

## Reproduction and validation

Python3.10+, repository imports and `reportlab` for the printable guide; no external image/browser dependency is needed. From the repository root:

```bash
PYTHONPATH=src:. python -m projects.hanji_relief.benchmarks.flat_c2_330_v01 --output NEW_DIR
PYTHONPATH=src:. python -m projects.hanji_relief.benchmarks.flat_c2_330_v01 --verify NEW_DIR
PYTHONPATH=src:. python -m unittest discover -s projects/hanji_relief/benchmarks/flat_c2_330_v01/tests -v
```

`--config PATH` accepts separately recorded mounting/reference values. Nonfinite/missing values and out-of-range motion fail rather than falling back to0. The four condition geometry/depth/dwell and20-contact comparison remain fixed. No existing output directory is overwritten. Five jobs regenerate from immutable source selection/config; hash checks plus numerical/trajectory/mapping/timing readback reject mutations. Existing official measured-profile, physical-clearance and authorization gates remain unchanged; the CLI exposes no device transport or physical export.

19new tests pass, including exact source translations, quadrant placement, bottom-up ordering,160/40contacts,0.5/1s/3/4mm readback, first preparation and matching fresh-wet preparation,8supplies,20→21 boundary/no middle wash/no refill after40, flat-Z-only commands, used brush at distance0, terminal cleanup once, fixed stations under a paper shift, finite/bounds checks and experiment/artwork completion isolation. Prior Hanji22tests pass; existing backend217tests run with215pass/two optional full-Spring-input/artifact skips. Old tracked files and the main artwork3mm/1s/20configuration are unchanged. No physical outcome is entered, no machine is connected/transmitted/operated, and no PR is merged.
