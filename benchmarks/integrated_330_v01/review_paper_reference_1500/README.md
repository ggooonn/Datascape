# Corrected paper first-touch and final1500mm ink test

IMPORTANT: the operator now reports actual first-touch at approximately G54Z+10,
not0. Old negative-Z benchmark files are historical/superseded for this mounting:
Z-1..-7 meant approximately11..17mm compression. Do not reuse those old files as
1..7mm tests under the corrected reference. They remain reproducible for audit.

Paper formula: commanded_Z=brush_first_touch_Z-compression_mm.
At first-touch10: compression1->Z9,7->Z3,15->Z-5.
The reusable brush field paper_first_touch_z_mm is independent for ink/color/slot.
Existing pressure knots remain SIGNED COMPRESSION OFFSETS: z_for returns that
historical relative value; work_z_for adds only the brush's paper reference.
Paper contact/release use that reference. Absolute stations, machine bounds,
YAML, G54, bed/substrate registration and station/lip/palette/washing Z NEVER
receive this paper-only offset.

Fast noncontact paper approach stops at the existing hoverZ15 (5mm above the
reported first-touch); no new lower fast-approach boundary is assumed measured.
Z15->10 initial contact, compression, return to10 and release10->15 all useF2000.
F7000 is restricted to the noncontact region15 and above. Readback separately
checks every paper segment and prevents fast Z crossing/occupying the actual
contact plane. Station motions crossing the numericZ10 elsewhere are not paper
contact and keep their existing independent feeds/absolute coordinates.

One final test:30 straight50mm strokes=1500mm drawing-onlyXY. Depths1..15mm
repeat in early750mm and late750mm; every depth appears twice at equal length,
direction and F6000. Three columns X20->70,130->180,240->290. Early rowY20..140,
lateY180..300,30mm spacing. Paired depths shareX and differY+160. The centerlines
fit the existing paper region10..320; wet-mark width/overlap is not certified.
One automatic WELL_2 load with accepted immersion/agitation/slope/single20mm
wipe/local20 lip connection/X815->795 atF1500/retract35. No reload within the
test, wash, purge or color visit. Every file independently starts after home at
X0Y900Z35 and finishes800/800/35/M2. M0=0. No homing/offset commands embedded.
Matched AIR retains all XY/source/visits, paper15/stations35, with no contact.

Preferred subsequent Spring ink reload is now1500mm; color remains800mm.
All other accepted motion/station/controller settings are unchanged. Complete
Y900 YAML bytes equal the previous candidate; installation/readback is not
claimed. Files are real numeric review G-code, not manufactured execution
authorization, brush-response measurement or swept-tool clearance evidence.

SPRING PRESSURE IS NOT FINAL: the relative Z-8 curve is kept ONLY as a historical/
provisional reference. The profile explicitly marks final Spring response NOT
selected; the official painting gate rejects that pending state. No3..15mm or
other new normalization is chosen. After results, select brush/usable compression
and knot response from physical width/continuity/recovery/loading observations,
then apply first-touch to its absolute paper G-code. Every artistic pressure,
source XY/direction/S3a/color and canonical plan binding stays immutable.
No final Spring production files are generated in this update.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.paper_reference_1500 --output NEW_DIR
Verify: append --verify for an existing package. Optional --machine/--provenance
perform canonical Spring dependency readback without producing Spring G-code.
