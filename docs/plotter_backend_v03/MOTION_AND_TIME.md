# Focused motion policy and conditional A/D times

This update follows PR #27 commit `e424782585818de7c9b98fa6a4af196da9aff198`.
D is the first-trial layout; A remains an alternative. No S3a order, artwork,
accepted pressure, knots, station primitive, reload rule or physical gate changes.
No hardware or real-Spring G-code is executed/serialized.

## Speeds and entry/release behavior

All values are unapproved physical-test candidates (mm/min).

| Motion | Previous cost fixture | Candidate |
| --- | ---: | ---: |
| Draw / ordinary XY / general Z | 5,000 / 12,000 / 6,000 | unchanged |
| Non-contact paper approach | 120, shared with contact | 5,000, separate |
| Initial contact and first compression | 120 | up to 2,000 |
| Pressure-driven Z limit | 600 | up to 2,000 |
| Release to Z0 and no-contact boundary | 120 to Z0, then fast lift | up to 2,000 through boundary, then fast lift |
| Wet departure / main / arrival | 1,000 / 9,000 / 1,000 | 3,000 / 9,000 / 3,000 |
| Stone/palette/PURGE contact | station feed, capped at 120 in fixture | unchanged and independent |

`paper_approach_mm` remains a measured boundary above first-contact Z0; the
scenario uses fictional +1 mm, +10-mm hover and 10-mm wet departure/arrival.
Lengths and both edge feeds are independently configurable. Short travel scales
end distances to fit. Original draw vertices and pressure samples are unchanged.
Approach, contact, first compression, pressure-driven drawing, slow release to
Z0/boundary and fast retraction are separate motions. Profile/evidence and
authorization hashes must be renewed after relevant motion changes.

## Six jobs — hours, conditional scenario only

The following commanded-feed categories are disjoint. Station = transfer plus
contact/loading/wash/dwell/retraction; separate components are in the JSON.
Acceleration column uses the **unverified DEV YAML** assumptions below.

| Job | Draw | Paper approach/contact/release/retract | Other XY/Z travel | Station | Feed total | Acceleration model |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SHARED_COLOR | 0.321 | 0.864 | 0.789 | 1.197 | 3.171 | 3.946 |
| SHARED_INK | 0.294 | 0.256 | 0.587 | 0.806 | 1.943 | 2.212 |
| P1_COLOR | 0.155 | 0.423 | 0.393 | 0.764 | 1.735 | 2.116 |
| P1_INK | 0.141 | 0.114 | 0.228 | 0.413 | 0.897 | 1.018 |
| P2_COLOR | 0.167 | 0.444 | 0.411 | 0.801 | 1.824 | 2.225 |
| P2_INK | 0.153 | 0.141 | 0.267 | 0.458 | 1.019 | 1.167 |

Previous D commanded-feed totals were 7.228 h ink / 20.726 h color; new totals
are 1.943 / 3.171 h. A totals change from 28.397 h to 5.475 h across four jobs.
These improvements remove the coupled 120-mm/min approach and slow wet edges;
they are not measured physical speedups.

## Acceleration assumptions and 4–5-hour target

FluidNC projects axis constraints, limits corner speed by junction deviation and
uses reverse/forward lookahead. The new model integrates acceleration/deceleration
and cruise per block instead of instantaneously changing velocity at feed boundaries.
It follows the reviewed [upstream Planner.cpp](https://github.com/bdring/FluidNC/blob/main/FluidNC/src/Planner.cpp)
constraints; it is not an emulator of the unidentified installed firmware.

| Assumption | Inherited slow fixture | Unverified DEV YAML comparison |
| --- | --- | --- |
| XYZ max rates, mm/min | 15,000 / 15,000 / 6,000 | 15,000 / 15,000 / 8,000 |
| XYZ acceleration, mm/s² | 100 / 100 / 20 | 1,200 / 1,200 / 1,000 |
| Junction deviation | synthetic 0.01 mm | same synthetic 0.01; absent from YAML |
| D ink acceleration model | 5.732 h | 2.212 h |
| D color acceleration model | 13.943 h | 3.946 h |
| D color stop-each-segment sensitivity | 23.841 h | 5.961 h |

The DEV file is explicitly UNVERIFIED, describes a different board revision from
previous hardware notes, and does not establish installed settings or wet-brush
approval. Its accelerations exceed the current synthetic brush limits: using
them for comparison does not make that profile exportable. All stone Z, brush
compression (synthetic 0–1 mm), contact/dwell and station registration remain
fictional. Deeper measured knots can also reduce synchronized draw speed.

The full-lookahead estimate assumes uninterrupted streaming. Finite controller
buffer occupancy, serial/CPU stalls, step rounding, firmware differences, manual
preparation/drying and actual brush recovery are not simulated. Neither this nor
the stop-each-segment model is a verified bound or physical printing time.

**The 4–5-hour D color target is conditionally plausible, not established.** With
DEV assumptions its dominant modeled times are paper engagement 1.312 h, station
handling 0.923 h, other XY/Z travel 0.905 h, drawing 0.515 h and station transfer
0.291 h. At inherited slow acceleration, paper engagement alone takes 8.645 h;
higher programmed feeds cannot overcome that acceleration limit.

## Requested speed comparisons — D color

Entries are DEV-assumption acceleration-model hours with preferred wet travel.
Pressure-driven drawing Z stays capped at 2,000; the contact candidate also sets
initial compression and controlled release. Every combination for all six jobs
and both dynamics cases is retained in `review/motion_comparison.json`.

| Approach mm/min | Contact/release 1,000 | 1,500 | 2,000 |
| --- | ---: | ---: | ---: |
| 3000 | 4.328 | 4.166 | 4.086 |
| 5000 | 4.198 | 4.031 | 3.946 |
| 6000 | 4.192 | 4.024 | 3.937 |

At 20-mm/s² synthetic Z acceleration, all nine combinations yield about
13.943 h: the short moves cannot reach even the lowest requested feed. Raising
approach from 5,000 to 6,000 saves only about 0.009 h with DEV dynamics; contact
quality and recovery therefore govern the final setting.

| Wet departure/main/arrival | Feed total h | Slow-fixture acceleration h | DEV acceleration h |
| --- | ---: | ---: | ---: |
| 1,000 / 9,000 / 1,000 | 4.615 | 14.762 | 5.334 |
| 3,000 / 9,000 / 3,000 | 3.171 | 13.943 | 3.946 |
| 5,000 capped throughout | 3.055 | 14.046 | 3.882 |

The flat 5,000 policy is only about four minutes faster than the preferred
3,000-edge policy in the DEV model, while allowing faster departure/arrival.
At low acceleration it is slightly slower despite its lower commanded-feed
subtotal. The preferred candidate remains 3,000 → 9,000 → 3,000 pending tests.

## Software verification and commissioning boundary

74 tests passed; one legacy conditional test skipped. Added analytical timing,
collinear/reversal/corner/dwell, independent feed/short-wet-travel, pressure cap,
read-back tampering, missing field and stale-evidence regressions. Full A/D plan
write/read-back and every trajectory pressure sample were independently checked:
D retains 14,951 unsplit paths / 240,974 samples and all 50 cross-X300 sources;
A retains its prior exact plan hash. Reloads (A ink/color 84/108; D 83/114),
washes, centered PURGE, station transfer geometry, zero routine M0 and final
park are unchanged. Synthetic serialization tests retain final M2.

Actual installed rate/acceleration/junction settings, a collision-safe approach
boundary and recovered brush clearance, calibrated compression knots, station
contact settings, safe wet edge lengths and brush acceleration limits still
require measurement. Validate air/park, short contact/release/recovery and wet
loading/cleaning, then representative dense microsegments and the D seam (if
using adjacent sheets) before authorizing production. Existing gates continue
to block unmeasured Spring output. These are v0.3 commissioning/configuration
inputs; no v0.4 work or automatic controller configuration is introduced.
