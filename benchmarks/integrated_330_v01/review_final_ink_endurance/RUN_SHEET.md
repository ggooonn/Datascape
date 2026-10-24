# Final ink endurance run sheet

These are complete numeric review programs, not a fabricated machine-authorized
export. Preserve established machine checks/stopping procedure. Confirm actual
active Y900 configuration/home/offsets and mounted-tool local lip corridor before
physical execution; no hardware settings are changed by the files.

1. Select A1200 or B1500. Rehome BEFORE EACH separate AIR or INK program: expected
   MPos=G54 WPos X0 Y900 Z35 with established zero G54/G92/TLO. The prior park is
   not a valid substitute for the documented start. Finish is X800 Y800 Z35/M2.
2. Use the matching AIR file first. Paper XY simulation stays at15; all station
   handling stays35. AIR cannot establish contact or material-delivery quality.
3. Prepare WELL_2 ink at its established reference level. INK automatically loads
   once, including the local20/F1500 lip routine; it does not reload even when
   crossing1200mm. Each test starts with a fresh load. No manual mid-test refill
   of the brush or routine M0. Keep substrate/media comparable between A and B.
4. Follow the CSV: every line is100mm, depths repeat1..7mm compression. A ends
   after stroke12/1200mm; B after stroke15/1500mm. B first12 match A exactly.
   Record width, density, continuity/gaps, fading/depletion, puddling and brush
   recovery by stroke/depth/cumulative distance, plus lip droplet removal.
5. Dry/used travel commands15000 immediately then controlled3000 arrival; wet
   main12000, drawing6000, noncontactZ7000, paper contact/release cap2000.
   Stop by the established available control if motion/contact/streaming is
   abnormal; inspect position before resuming. M0=0 means no automatic pauses.
6. Send both results and brush selection/calibration. This completes benchmarks;
   next is full Spring AIR -> SHARED_INK -> SHARED_COLOR using validated settings.
