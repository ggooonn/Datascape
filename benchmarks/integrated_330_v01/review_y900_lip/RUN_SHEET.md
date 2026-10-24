# Y900 / unchanged Y0 operator sequence

This upper-only hardware extension does not move the original Y0 stopper,
fixed stations or paper coordinates. Keep existing G54 registration and all
station Y values. No global+2 translation or G54+2 correction is proposed.
The geometry report is preserved; new configuration/home/range read-back is
still pending. These numeric programs are REVIEW files, not authorized exports.

1. Back up the ACTUAL active YAML. Manually install the new complete candidate,
   reboot and home. Capture the active file/hash and actual Y mpos900/travel900,
   XY20000/1500, X860 and unchanged Z/homing/pins/steps/pull-offs. The retained
   historical name/comments are not proof of the active configuration. Do not
   follow the old commented G10 example.
2. Capture $I, $G, $#, ? and UGS machine/work displays. Expected post-home MPos
   AND WPos:0/900/35; established G54/G92/TLO remain0, but inspect actual values.
   Never set an offset merely to make an unexpected display look correct.
3. At established no-contactZ35, verify the SAME lower-Y0 mechanical reference
   with controlled manual motion (do not drive into the stopper), and the fixed
   A2 center824.5/554.5 plus paper registration. Check usable0..900/end margins,
   including safe upper pull-off/homing. If old Y0 or a fixed reference disagrees,
   diagnose configuration/homing/pull-off/offsets before proceeding. Do not remap
   all stations or insert+2 to conceal the discrepancy. Complete only the new
   read-back/range fields in reconciliation.TO_COMPLETE.json; already reported
   physical geometry is not requested again.
4. Confirm actual stopping response/full-tool corridors; the previous absent
   independent E-stop is not presumed fixed. Run FRAME_AIR (entirely35) only
   when its actual start/offset/setup conditions match. It visits the A2 reference
   and a paper outline, not a hard stop or automatic limit probe. Observe motion,
   physical registration, streaming and final800/800/35/M2.
5. LIP_APPROACH_AIR visits ink458±10 then water298±10 in the unchanged-Y0 frame.
   Candidate X815 is approached from840 atZ35/F500. It never descends to20.
   Inspect brush AND holder/stone-edge clearance. Air clearance at35 does not
   establish contact at20, a contact stroke length or a safe release trajectory.
6. ONE_WIPE_330_AIR matches all40 original paths and material visits with station
   motions at35 and paper at15. WATER_ONLY then INK_GOUACHE are actual one-wipe
   material reviews: water at WELL_2/A2 for the first; ink WELL_2/gouache A2 for
   the second, clean water WELL_1. Numeric bodies are identical. The existing
   forty constant-depth trials still include-10: use the previously checked
   brush/mount, not an untested newly selected small brush. No routineM0.
7. Each stone visit now performs ONE20mm pressedY+ wipe at7.5, controlled vertical
   release9 then lift35 before lateral motion. No second X-10/re-entry pass and
   no lip contact is added. This incomplete dewatering candidate cannot prove
   lip-stripping performance. Other accepted feeds/dwells/purge/palette remain.
8. For each well separately report actual contact-start XYZ in this unchanged-Y0
   G54 frame, confirmed X-negative displacement/end, contact feed, release path,
   safe retract and mounted-holder clearance, plus specific trial approval. X815/
   Z20 is only a candidate, not a measurement. Prior relative-20 is historical;
   actual displacement stays null. Proposed first test300mm/min/-1mm is disabled,
   adjustable and unapproved. The existing production lip-enable guard stays
   closed; no contact program is generated from the proposed region alone.

Rehome before EVERY file: expected start0/900/35, end800/800/35/M2. Old Y898 files
remain reproducible references; do not silently reuse their old start assumption.
Motion: dry15000/wet12000 (optional profile15000), draw6000, Z7000, pressure/contact/
release2000, hover15/localoff, transfer35; ink1200/color800. No installed setting,
Spring source/pressure/S3a/color or authorized production G-code is changed.

Geometry: ink wipe445..465 overlaps lip448..468 but X840/Z7.5 is distinct from
candidate815/Z20. Water wipe295..315 ends7mm beyond lip288..308; reach center298
only AFTER release/lift35 (Y reposition-17). Never drag pressed toward the lip.

After Y900/reference/lip-clearance results: complete the separately gated contact
trial using real measurements, then small/medium brush selection and pressure
calibration, then final Spring preparation through existing physical gates.
