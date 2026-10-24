# Final1500mm ink test: corrected paper first-touch

Use ONLY the new PAPER_Z10_COMP1_15 files for this reference. Prior negative-Z
files were based on first-touch0 and no longer describe their labeled physical
compressions. Reference10 is operator-reported approximate, brush-specific.

1. Each separate AIR or INK file requires manual rehome/start G54X0Y900Z35,
   established zero G54/G92/TLO; endX800Y800Z35/M2. Do not shift G54 or stations.
   Preserve existing controller/configuration/clearance/stopping checks. No
   installation or new physical pass is asserted by these review files.
2. Run matched AIR as appropriate: paper15/stations35. It has no contact and
   cannot establish physical compression, brush response or the local lip fit.
3. Prepare WELL_2 ink at its established reference. INK loads once automatically
   with the accepted local20/F1500 lip routine, then draws without reloading.
4. Follow stroke_schedule.csv: early15 lines at1..15mm compression/750mm, then
   late15 equivalent lines/750mm. Each50mm/F6000; physical1->Z9,7->Z3,15->Z-5.
   Paper fast motion stops15; initial contact10, compression and release use2000.
5. Record widths, density, continuity, depletion, pooling/paper condition and
   brush recovery for each paired early/late depth. Compare equivalent depths,
   not a shallow early mark against a deep late mark. M0=0: use the established
   stop control if contact, communication or mechanics is abnormal; inspect
   actual position before resuming. No automatic mid-test reload or inspection.
6. Send results and brush selection. Final Spring pressure distribution remains
   undecided; Z-8 is history only. Select the physical curve from these results,
   then existing Spring AIR -> SHARED_INK -> SHARED_COLOR export. No new hardware
   commissioning or artwork/composition study is planned.
