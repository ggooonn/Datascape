# Hanji bed10 / hover35 / 30-contact programs

Two operator-requested alternatives: full600x600 assembly OR physical P4 in local200x200 coordinates. These files contain actual motion commands. Generation is offline; no machine was connected or operated.

Place the artwork nominal outer lower-left at existing G54 X0 Y0. The full program uses global XY; P4 uses unchanged panel-local XY and full design Z. Do not shift G54 or station coordinates to reposition the artwork.

Operator-selected setup: model datum=bed; first bed touch G54 Z10; first touch=designZ+10; press=designZ+7;3mm compression, full1s at depth; hover35. Analytic design ceiling20 already includes Base2. Nominal full-scene gap5mm is explicitly accepted by the operator, replacing the earlier10mm criterion. No local correction map or new measurement is fabricated.

Each independent file starts at G54 X0Y900Z35 and ends at X800Y800Z35/M2. Same-color supply follows30completed contacts/retraction, before31/61/etc; color changes use the existing wash/purge/rewet/load and reset. No redundant load after a final color dot. Terminal PR32 cleanup occurs once. Station coordinates, rates, controller limits and G54-to-machine registration remain unchanged.

Use the spare P4 for the preliminary complete-panel test. The full program includes all890P4 dots; painting an original panel with P4 then running the unchanged full program on that same panel repeats those dots. No physical completion is inferred or recorded here.

| Program | Dots | Loads | Modeled minutes |
| --- | ---: | ---: | ---: |
| hanji_full_600x600_Z10_Z35_R30.gcode | 6200 | 209 | 279.52 |
| hanji_P4_local_Z10_Z35_R30.gcode | 890 | 32 | 44.53 |

Timing uses the existing Cartesian full-lookahead model, configured acceleration1500/1500/1000mm/s² and assumed JD0.01. It is not measured execution time. Dwell begins after the press move completes. Motion/hold/load/wash categories are included in time_breakdown.csv.

Physical panel labels are P1-P9 from front-view top-left to bottom-right. Original source IDs remain separate: P1/sourceP07, P2/sourceP08, P3/sourceP09, P4/sourceP04, P5/sourceP05, P6/sourceP06, P7/sourceP01, P8/sourceP02, P9/sourceP03. C2/C4 are color IDs. Preview diameter2.8mm is an unmeasured display assumption; SVG labels never paint.

Numeric verification re-creates the two plans, shared trajectory, final serialized moves/dwell, per-contact mapping and material schedule. Operator setup/acceptance is recorded separately from measured-profile evidence; existing official physical exporter gates remain unchanged. No homing, G92, controller/offset writes, routineM0, transmission, physical measurements or completion claims are added.

Backend base: spring/large-baegunmo-z10-hover20-v01 / eda6069b12c8785d458a0e8a567a9a86980bc394. Source CSV SHA256: bf9d2fa2b693f9ad1174c7126eaff6a1cd777babc78125c5cfe4f03cfc45be9a.

Reproduce: PYTHONPATH=src:. python -m projects.hanji_relief.run_export --output NEW_DIR
Verify: PYTHONPATH=src:. python -m projects.hanji_relief.run_export --verify DIR
