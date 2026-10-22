# Operator sequence — not an execution authorization

Before any `.nc` is exported: confirm actual installed YAML/firmware, G54/MPos/WPos
and zero G92/tool offset, 100% override, current start, axis/brush limits, paper
registration and swept-tool corridors including the entire park path. Home/offset
setup is manual in CONTROL. The profile expects WPos (0,898,35); after each job
parks at (800,800,32), manually re-establish and verify the next job's recorded
start. Never start the next file from the previous park without a matching profile.

| Order | Plan | Candidate geometry | Intentional M0 |
| --- | --- | --- | ---: |
| 1 | A_SHORT | One 300x300 square at XY15..315, Z>=10; park | 0 |
| 2 | A_STABILITY | Four squares + two 301-point sweeps; short streaming check | 0 |
| optional | A_STATION_OPTIONAL | Measured centers only, verified global clearance | 0 |
| 3 | B_DEPTH_1 | Manually inked 60-mm line, Z-1, 600 mm/min | 3 |
| 4 | B_DEPTH_2 | Fresh recorded load, 60-mm line Z-2 only after -1 review | 3 |
| 5 | B_DEPTH_3 | 60-mm line Z-3 only after -2 review and range approval | 3 |
| 6 | C_LOW | 120-mm sample ramp .2/.35/.45/.35/.2; peak ~2.96-mm compression | 3 |
| later | C_EXTENDED_LATER | 180-mm .2/.4/.6/.8/.93/.6/.2; reaches -8.8, NOT initial -3 envelope | 3 |
| 7 | D_HOVER | Two groups of three 20-mm strokes: +10 vs +5, gaps 5/10 mm | 4 |
| 8 | E_INK | WELL_2 only, 2-mm immersion candidate, measured diagonal exit | 4 |
| 9 | E_WATER | WELL_1 one operation, measured diagonal exit | 4 |
| optional | E_CLOTH_OPTIONAL | Secured cloth, actual surface minus 0.5-mm candidate, one dab | 4 |
| 10 | E_INK_REAPPLY | Ink load then 60-mm line; only after ink/water trial evidence | 5 |

The core M0 locations are startup; before/after each station; before each line or
pressure test or hover group; and final recording. `Builder.pause` parks first
except the initial startup pause. Inspect at those stops; no pauses occur between
strokes within a hover group. No production evidence is automatically granted.
A successful -1-mm line does not approve -2/-3 or a -10-mm maximum.

For every B/C/D line: record actual depth/feed, line length, width at start/middle/
end, continuity/gaps, ink transfer/distribution, substrate indentation/fiber lift/
tearing or pooling, brush recovery/lag and loading/water recipe. Compare fresh
loading consistently; inspect paper before moving to the next depth. During D,
observe/measure wet-bristle clearance after release at +5 along the whole short
link. Abort on any drag, hair snag, liquid trail, unusual bending or collision.

For E: record actual liquid Z just before testing, deep/shallow XYZ, minimum floor
gap along withdrawal, exit height and feed/dwell/contact volume. Nominal bed liquid
10..11 minus nominal paper height 1 suggests work Z9..10, not a measured Z plane.
At 2-mm immersion the nominal deep-floor gap is 2..3 mm; at 3 mm it is 1..2 mm.
The two-point floor model assumes a linear slope between its references. Confirm points on the actual 45-mm slope; do not treat the combined 45-mm slope plus 60-mm flat as one 105-mm linear slope. Validate the whole floor clearance if the path includes the flat. Do not scrape/press the stone; no 4.5..5-mm immersion default. Cloth is optional
and does not block A or manually loaded B/C/D. Re-folding cloth requires remeasurement.
Palette use is deferred; X847 + radius7 reaches X854 before any tool margin.

For A: record elapsed time, alarms/disconnects, reference XY/Z before/after and
repeatability error with measurement method. The preview's candidate feed-only
A_SHORT/A_STABILITY durations are approximately 3.8/11.3 min, not controller time
or long-duration reliability. A port change and one successful short test do not
approve several hours of streaming. On disconnect/position uncertainty: stop/abort
using the established controller safety procedure, rehome/re-register as appropriate,
inspect partial marks and reapprove a complete test. Never resume an arbitrary line.

Keep `observations.TO_FILL.json` as the raw record. Only the operator can report
actual pass/fail and approve adding current scoped evidence. Before later full
Spring printing, verify measured curve/brush/media, station operations, +5 recovery,
streaming, actual park/corridors, and all production gates. No existing PR is merged.
