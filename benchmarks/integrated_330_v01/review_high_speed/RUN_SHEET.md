# High-speed commissioning run sheet (review programs)

No new candidate has been installed or physically passed. These numeric files
are review artifacts, not formal machine-authorized exports. Existing stopping,
clearance, measured-profile/evidence and stage-authorization gates stay intact.

1. Save the actual controller YAML. Manually install config.X860.high_speed.candidate.yaml,
   restart and read back X/Y20000, acceleration1500, X travel860 and unchanged Z/
   homing/motors. Confirm configuration hash and successful home. Do not infer
   installation from the filename or change work offsets. The historical YAML
   comments are preserved; the exact four-line-value diff is authoritative.
2. Required start EACH execution: after homing, G54 X0 Y898 Z35, zero G54/G92/TLO
   as previously established; verify current state. Ending park is800/800/35/M2.
   Rehome before the next file; do not silently start from the previous park.
3. Existing independent E-stop installation is not established (recorded absent).
   Confirm usable stop response and accessible independent drive/power stopping
   before extended high-speed travel. A software Feed Hold is not an independent
   collision stop. At a physically checked Z35 corridor, first check short dry
   X and especially Y-negative motions at reduced speed, then the requested
   higher candidate; record missed steps, vibration/noise, hold/reset response
   and post-stop coordinates. No successful stop behavior is assumed here.
4. Use WET12000 AIR first: no paper/liquid/cloth contact; paper simulation15,
   all station operations35. Confirm all six visits, F15000 long return/main,
   last35mm capped3000 BEFORE vertical descent, Z35 lift before station XY,
   holder/fixture/brush clearance, UGS TCP continuity and final park. Short moves
   may never attain commanded main speed. Do not increase feed override.
5. Only after review/current physical authorization, WATER_ONLY, then INK_GOUACHE
   with the same40-depth series. Water-only: water in WELL_2 and A2, clean water
   WELL_1. Pigment: ink WELL_2, prepared gouache A2, clean water WELL_1. Contents
   differ; numeric commands are identical. No automatic stop is inserted: abort
   for dragging, unsafe compression, splash, loss of steps or poor recovery.
6. The optional WET15000 set is a separate comparison AFTER wet12000 behavior
   is acceptable. Wet15 has modest modeled time benefit; it is not the initial
   approved wet speed. Global XY1500 acceleration also affects low-speed station
   motions: confirm X±10/F1500 agitation and two-pass wiping remain gentle.
7. Endurance AIR previews the separate18-line path and actual reload visit.
   Endurance INK uses Z-2, F6000: lines1..15 each80mm, cumulative80..1200mm;
   automatic same-ink reload before16, no washing, then lines16..18 in another
   column. Record width/continuity/pigment at800/1000/1120/1200 and first marks
   after reload, saturation trails and actual reload transfer. Prior800mm result
   is not1200mm evidence. No extrapolated successful delivery is recorded.

M0=0 in every file. Stations: initial WELL_2 -> WELL_2 reload -> WELL_1 wash ->
PURGE -> A2 load -> A2 reload. Endurance: WELL_2 load -> WELL_2 reload only.
Ink2s/water5s; ±10mm agitation1500; controlled immersion/withdrawal1000,
shallow approach750/wipe1000, pressedZ7.5 for20mm twice, vertical release/lift
before X-10; no lip contact. Purge840/137.5/Z1.5/4s single vertical dab. A2 dip5,
radius5, current dwell/feed unchanged. Nominal surfaces remain nominal.

After results: select brush, confirm response/motion/material outcomes, measure
WELL_1/WELL_2 lip XYZ, contact feed/relative travel and safe retract separately,
then implement/validate the explicit lip operation and authorize final Spring.
The generic existing backend supports the candidate's opt-in travel policy;
this Work exports no final Spring production program. The old baseline Spring
wrapper remains baseline-specific; do not let it silently substitute old speeds.
