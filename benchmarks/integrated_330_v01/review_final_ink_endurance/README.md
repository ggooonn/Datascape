# Final ink endurance: independent 1200mm and1500mm tests

Each complete AIR/INK job starts independently immediately after manual homing,
G54 X0 Y900 Z35, and ends X800 Y800 Z35/M2, M0=0. No homing/offset write is
embedded. Each has ONE automatic fresh WELL_2 load, NO in-test reload, washing,
purge or palette visit. This intentional depletion-test override does not change
Spring ink1200/color800 reload thresholds. Old40-stroke and endurance baselines
are retained unchanged.

A1200:12 straight100mm strokes, drawing-only XY=1200mm.
B1500:15 straight100mm strokes, drawing-only XY=1500mm.
Depths repeat[-1,-2,-3,-4,-5,-6,-7] in the same order. B first12 source IDs,
XY, direction, depth, speed and sequence equal A; the last three extend the test.
Stroke centers: X20->120 for rows1..8 atY20,60,...300; X190->290 for later rows.
All paths fit the existing paper region10..320.40mm row spacing/70mm column gap
are layout choices, not measured wet-mark-width certificates. CSV schedules give
exact numbering/depth/cumulative distance. No non-drawing XY/Z travel is counted.
No Spring artwork/Pressure Intent or brush-response curve is regenerated.

Updated BOTH stone profiles: original immersion/agitation/slope -> ONE pressed
20mm Y+ wipe at7.5 -> vertical controlled release9 -> vertical lift20 -> controlled
XY to measured lip815/458 (ink) or815/298 (water) at20/F1500 -> X795/F1500 ->
vertical35/F7000. No Z35->20 round trip or redundant lip descent. The local
connection is distinct from cross-region travel at35. Lip displacement/feed,
local connection height/feed and final retract remain separately configurable.
The new connection/feed is operator-requested, not a fabricated physical pass.
Water uses the same grammar/configuration, but these INK-only tests visit only
WELL_2. Official station contact-volume and full-tool path/authorization checks
still apply; nominal review records do not certify the local XY corridor.

Dry/used-brush travel requests15000 from the FIRST departure block, keeping the
existing controlled F3000 arrival zone (nominal35mm for station/park arrival,
scaled for short routes). No initial F3000 departure segment for these states.
Collinear departure/main blocks can share F15000; no dwell or exact-stop mode
is introduced. Actual acceleration/attained speed remain governed by FluidNC
lookahead and unchanged axis limits. Short moves need not attain full speed.
Wet main12000 with its existing slow departure/arrival remains unchanged.
Drawing6000, noncontactZ7000, pressure/contact/release limit2000, paper hover15,
local hover off, transfer35, Y900/X860 YAML and Spring Z-8 candidate preserved.
The complete YAML is byte-identical to the prior final-lip candidate, never
installed/read back by this software. Existing fixedY0/stations remain unchanged.

AIR projects exactly the same XY/source/visit route: paper simulation15 and all
station handling35. It does not test actual liquid/stone/lip contact. INK uses
real commanded contact depths. All files contain real numeric G-code for review;
file generation, offline checks and physical execution authorization stay distinct.
No installed configuration, stopping, full-tool clearance or new physical pass
is invented. No hardware I/O, PR merge or final Spring production export occurs.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.final_ink_endurance --output NEW_DIR
Verify: append --verify using an existing package. Optional --machine and
--provenance bind/check recovered canonical Spring inputs without exporting it.
Next after operator results: select/calibrate brush, then existing full Spring
AIR and separate SHARED_INK/SHARED_COLOR export workflow. No further benchmark
study is planned.
