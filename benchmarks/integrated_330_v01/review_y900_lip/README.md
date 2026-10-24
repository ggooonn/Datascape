# Y900 reconciliation / one-wipe and lip-clearance review

No installed YAML is changed. Current two-pass/high-speed/Y898 files and Spring
v13/F2-C, artistic pressure, S3a, twelve colors and the Z-8 response stay intact.
New files are real numeric G1/G4/M2 REVIEW programs, not physical authorization.

The operator clarifies that PHYSICAL Y0 HAS NOT MOVED: the same mechanical
stopper establishes the lower reference; only the upper assembly was extended
from898 to900. Existing wells, palettes, purge and paper Y coordinates remain
unchanged. This supersedes a home-label-only/+2-offset scenario. NO+2 G54 offset,
station translation or retained898 new-frame alternative is proposed/exported.

The complete separate YAML changes ONLY Y homing mpos898->900 and max_travel
898->900, plus warning comments. X860, XY20000/1500, Z and all homing cycles,
directions/pins/steps/pull-offs/settings are preserved. Nominal Y bounds are
0..900. The physical upper modification is operator-reported; installation,
actual home/read-back and usable-range/end-margin tests remain unperformed.
Existing YAML name/comments are archival, not proof of active settings; do not
follow their obsolete G10 example. Installed YAML is never overwritten here.

Changing the assigned home label does not move fixed stations or automatically
set G54. In the same direction/scale, deltaM at a fixed physical point equals
delta home-label (2mm) minus physical post-home displacement. With G92/TLO0,
W=M-O54. In the reported upper-extension case the physical post-home point also
moves+2 while Y0 stays fixed, so fixed-reference deltaM is expected0 and old
G54 registration stays valid. Confirm with actual controller/home/reference
read-back; do not convert the geometry report into fabricated passing evidence.

| Verification | Expected result | If it disagrees |
|---|---|---|
| Existing mechanical Y0 | MPos/WPos Y0 | stop and inspect reference/config/offset |
| New post-home | MPos=WPos0/900/35 with existing zero offsets | inspect actual config/homing/pull-off/offsets |
| Fixed A2 center | X824.5/Y554.5 unchanged at safe Z35 | investigate; do not automatically translate |

G92 and tool offsets must be inspected, not assumed absent after reboot. If a
fixture moved independently, a common translation cannot fix it. Preserve
canonical artwork; registration correction belongs in measured G54/execution
mapping, never a rewrite of original artistic XY or pressure. A label-only+2
delta would be a different physical scenario; here it is a diagnostic mismatch,
not permission to set G54+2. No automatic coordinate correction is implemented.

One UNCHANGED_Y0 set is delivered. Expected post-home MPos AND WPos are0/900/35;
G54/G92/TLO remain the previously established zero values, subject to inspection.
All station/paper work coordinates and park800/800/35 remain unchanged. Complete
the actual read-back template after manual verification; --record rejects a+2
offset/reference mismatch rather than silently adopting it. Operator-reported
geometry is already recorded; only new installation/read-back/range evidence
remains blank. Record-derived profiles remain nominal, not contact-certified.

Programs: FRAME_AIR (A2 reference + paper outline entirely35), LIP_APPROACH_AIR
(both candidate regions, entirely35), and matched ONE_WIPE_330_AIR, WATER_ONLY,
INK_GOUACHE. All start0/900/35 and park800/800/35/M2. All M0=0; no homing, G10,
G92, probing or offset writes. FRAME_AIR avoids automatic end-limit/stopper tests;
the actual0 and900 margins are manually inspected, not claimed proved by it.

The same40 original depth strokes/order/feeds are preserved. The one-pass
material routine is deep immersion/agitation -> original Y+ withdrawal -> ONE
pressed20mm Y+ wipe at7.5 -> vertical controlled release9 -> vertical lift35.
Lip approach/contact steps are skipped until verified/authorized. This is a
replacement for two-pass wiping, not two passes plus a lip step. Matched Air
raises station motions to35 and paper drawing to15. Water/pigment numeric
commands are identical; prepare contents appropriately. Existing motion remains
dry15000/wet12000 (separate profile15000), draw6000, Z7000/contact2000, hover15,
localoff, transfer35; ink1200/color800 and material feeds/dwells unchanged.

Lip records keep the UNCHANGED Y0 coordinates: inkX815/Y458±10/Z20 and
waterX815/Y298±10/Z20. These are operator-proposed regions, not measured brush
contact. Z20 is NOT a contact measurement or a safe
approach boundary. No generated Air file descends there. Clearance-only X840
to815 is -25mm atZ35/F500, not a measured contact stroke or absolute negativeX.
The historical relative-20 proposal is recorded separately. Proposed first
contact feed300 and relative-1mm are adjustable unapproved suggestions only;
actual contact XYZ, X displacement, feed, release/retract and holder clearance
remain null/unconfirmed. The existing production lip-enable guard stays closed.
No unverified low-speed or high-speed lip-contact G-code is emitted.

Wipe inkY445..465 overlaps lipY448..468 by17mm; its end465 lies in that Y region.
WaterY295..315 overlaps288..308 by13mm, but its end315 lies7mm beyond the region.
Both require release/lift35 before any return toward the lip. X840/Z7.5 wiping
and X815/Z20 candidate lip geometry are distinct; Y overlap proves neither a
shared surface nor contact/holder clearance. Do not extrapolate slope or flatZ9.

Minimal operator sequence: back up actual config; manually select/install/reboot;
home; capture startup active YAML/actual scalar read-back, $I, $G, $# and ?.
Inspect MPos/WPos, G54/G92/TLO. Confirm unchanged mechanical Y0 with a slow
manual/no-contact check without driving into a hard stop. At verified Z35,
slowly approach the SAME fixed A2 reference and check Y554.5, plus existing
paper registration. Verify actual usable0..900/end clearances, then rehome and
capture MPos/WPos0/900/35. If offset/reference/range disagrees, stop and diagnose
the homing/configuration/offset source; do not set G54+2 or remap stations to
hide it. Confirm stopping and exact full-tool corridors
before running a selected review. Prior E-stop absence is not silently resolved.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.y900_lip --output NEW_DIR
Verify: append --verify with existing output. Optional --record
actual.json, --machine BOUND/spring.machine.json --provenance BOUND/spring.provenance.json.
Record-derived profiles remain nominal reviews; operator read-back is not a
measured contact-volume certificate or stage authorization. Existing official
machine/evidence/collision/physical-export gates remain untouched.
