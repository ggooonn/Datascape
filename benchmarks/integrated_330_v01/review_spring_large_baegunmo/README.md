# Spring integration / large Baegunmo physical benchmark

Operator reports the final1..15mm benchmark completed: corrected first-touch10,
clear width differences, splitting beginning around12mm,1500mm ink workable with
gradual fading, lip/wash/recovery/Y900 working. No exact widths or streamed-file/
active-YAML hash were supplied. Observations are preserved separately from formal
machine/profile evidence; prior source/G-code artifacts remain unchanged.

Paper: per-brush first-touch10, relative hover10→absolute20, approach+5→15.
F7000 applies to noncontact Z; contact/compression/release useF2000. Stations,
lip, washing, palette, purge and global35 are ABSOLUTE and never shifted.
Ink1500 default/optional2000, color1000. Reload at the next original-stroke
boundary only; same material never washes. Color changes retain the existing
wash/purge/rewet routine. Dry/used15000 with controlled arrival3000, wet12000,
draw6000, normal20/localoff, start0/900/35, park800/800/35/M2, routineM0=0.

New USER-SPECIFIED candidate compression knots (pressure,mm):
0:0,.2:1,.4:3.5,.6:5.8,.8:8.2,.93:10.2,1:12.
Absolute paper Z=10−compression. Actual Spring pressure<=.93 therefore maps
<=10.2mm, not automatically to12mm. Ink/color curves and first-touch remain
independent. The old Z-8 response is saved as history, not silently reused.
New knot widths/complete Spring physical behavior remain unmeasured; curve and
color calibration are not misrepresented as fully machine-authorized.

SHARED_INK_REVIEW.gcode and SHARED_COLOR_REVIEW.gcode are separate complete
executions, EACH expected to start after manual homing at0/900/35. Manual brush/
water/palette/drying/registration review occurs BETWEEN them. No startup wash
or M0 is added to the prepared color job; automatic washing between colors stays.
SPRING_AIR_REVIEW.gcode is ONE full-scene no-contact simulation of the same ink
then color order and material itinerary, including simulated ink→color wash.
Paper motions project to20/station operations35; it does not prove contact.
It is not a single continuous pigment production program.

All are numeric OFFLINE REVIEW files, NOT completed machine authorization.
No fabricated measured volumes, exact widths, passed stopping/full-scene swept
clearance or installed-YAML hash is supplied. Existing formal export gates stay.
14951 original strokes/240974 pressures/50 continuous X300 crossings, F2-C/v13,
XY/direction/S3a/twelve colors and canonical plan hash remain unchanged.
Only physical execution mapping/material parameters change. No artwork generated.

Visual overview uses original canonical colors/opacity/XY. Canonical-width view
and explicitly labeled unmeasured compression-width proxy are separate. No ink
diffusion or pigmentation is claimed physically simulated. Full PNGs/crops and
HTML are included. Runtime uses actual candidate limits with assumedJD0.01/full
lookahead; separate synthetic100 acceleration reference, never promised duration.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_large_baegunmo --output NEW_DIR --machine BOUND/spring.machine.json --provenance BOUND/spring.provenance.json --rich RECOVERED/artworks/spring_v13 --sidecar RECOVERED/artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz
Complete G-code is also losslessly gzip-compressed for repository publication;
SHA256 records identify uncompressed commands. Extract before inspection/use.
