# Hanji C numeric offline review

**These files contain real G1/G4/M2 commands. They are not machine-authorized programs.**
The named scenario is nominal offset0, artwork XY at0/0, fixed G54 hover35. These are explicit review coordinates, not measured mounting values. Do not strip the review status or assume flat first-touch10 is included.

Default contact:3mm additional compression from local first touch; full1s dwell at depth; reload before point21 after20 contacts. Eight-color Hanji extension and right-first bottom-up serpentine are preserved.

Start for each independent job is G54 X0 Y900 Z35; end X800 Y800 Z35/M2. No homing/offset writes or routine M0. Stations and terminal cleanup reuse PR32. Terminal water3×10s/three agitation cycles, sponge2×4s, no final rewet.

Ten main jobs are alternatives: one full global job OR the nine local panel jobs. P04 benchmark uses hanji_panel_04_local.gcode. The additional C4_first40 overlaps40 points of that890-point job; do not execute both unchanged on the same artwork. No completion is inferred. The P04 AIR plans47 loads but consumes/completes zero actual contacts.

| Job | Dots | Colors | Loads | Same-color refill | Changes | Modeled min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hanji_panel_04_C4_first40 | 40 | 1 | 2 | 1 | 0 | 3.61 |
| hanji_panel_04_local_AIR | 890 | 6 | 47 | 41 | 5 | 16.79 |
| hanji_full_600x600 | 6200 | 8 | 313 | 305 | 7 | 318.00 |
| hanji_panel_01_local | 306 | 6 | 19 | 13 | 5 | 20.10 |
| hanji_panel_02_local | 32 | 3 | 4 | 1 | 2 | 4.90 |
| hanji_panel_03_local | 278 | 4 | 17 | 13 | 3 | 17.80 |
| hanji_panel_04_local | 890 | 6 | 47 | 41 | 5 | 50.70 |
| hanji_panel_05_local | 908 | 5 | 48 | 43 | 4 | 50.05 |
| hanji_panel_06_local | 903 | 7 | 49 | 42 | 6 | 51.89 |
| hanji_panel_07_local | 970 | 8 | 52 | 44 | 7 | 56.06 |
| hanji_panel_08_local | 927 | 7 | 49 | 42 | 6 | 52.99 |
| hanji_panel_09_local | 986 | 8 | 53 | 45 | 7 | 57.11 |

Timing uses the shared full-lookahead/JD0.01 model and configuration-reference XYZ acceleration1500/1500/1000mm/s². Junction deviation is assumed; streaming, finite buffers, step rounding, brush response and dry-mark size are not physically verified.

Open Hanji_C_Review.html for artwork, first40 numbered refill boundary, machine XZ/YZ, heights, offset/hover table, counters and time breakdown. Detailed dot IDs/coordinates/Z/counters are in each mapping CSV. Missing actual first-touch fields remain blank.

Reproduce: PYTHONPATH=src:. python -m projects.hanji_relief --output NEW_DIR
Verify: PYTHONPATH=src:. python -m projects.hanji_relief --verify DIR
Confirmed same-condition paint completion: add --completed-record RECORD.json to generate a separate remaining job. AIR/planned completion is rejected. No arbitrary-line restart.

The source CSV/GH code and previous Spring/backend files are unchanged. No mesh/STL or additional ink pass is generated.
