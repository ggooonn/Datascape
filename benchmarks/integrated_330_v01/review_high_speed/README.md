# High-speed commissioning candidate (PR31)

Numeric G1/G4/M2 offline REVIEW programs, not machine-authorized exports. No
configuration is installed and no new physical safety evidence is created.
The existing40-stroke baseline, Spring v13/F2-C, Pressure Intent/S3a,12 colors
and explicit Z-8 response remain unchanged. No final Spring G-code is exported.

The complete YAML differs from the prior X860 candidate at exactly four scalars:
XY rates15000->20000, XY accelerations1200->1500. X860 and all Z/homing/direction/
motor/pin/step/pull-off/controller settings stay byte-identical. Historical YAML
comments remain archival; consult the exact diff/controller record for intent.

Profile: dry15000, wet12000 (separate15000 variant), used-brush return15000,
draw6000, noncontactZ7000, pressure/contact/release2000, paper15/localoff,
station35, start0/898/35, park800/800/35/M2, ink1200/color800. Z-8 is Spring-only;
the40 explicit constant-Z trials still reach-10. Stations retain two pressed
20mm Y+ passes at7.5, reentry17.5 before X-10, purge1.5/dwell4s and palette5/
radius5. Ink2s/water5s. Agitation X±10 at1500; other contact feeds unchanged.

The SAME40 XY/depth/source/order plan has two separate wet-speed sets. Each has
matched AIR (station motion elevated35/paper15), WATER_ONLY and INK_GOUACHE.
Water/pigment numeric commands are identical; change the contents manually.
The scheduled reload after each10-line450mm column is preserved for baseline
comparison and is not evidence of1200mm endurance. Independent endurance uses
15x80mm at constantZ-2 (1200mm), actual automatic ink reload before line16, then
three80mm comparison marks in a separate column (1440mm total). Reported prior
ten80mm marks establish only~800mm, not success at1200mm. Previous ink1000
profile is preserved; color threshold stays800. No canonical stroke is split.

Station access is vertical to35, segmented straight XY, then vertical descent.
Final35mm XY is capped3000. Used-brush departure also35mm/3000. Wet-paper edges
retain5mm/3000, wet station arrival35mm/3000. Short paths shrink edge zones and
omit high-feed main; commands do not force attained speed. A15000->3000 ramp
at1500mm/s² needs20mm ideally. That deceleration begins BEFORE the final capped
zone; a35mm zone is not a physical safety certificate. Actual corner angles,
projected axis acceleration, forward/backward planning and dwell stops enter
the offline model. Adequate lookahead/streaming and assumedJD0.01 are explicit;
finite planner buffer, step rounding, TCP timing, feed override and wet dynamics
are not measured.30/35/40mm actual-route comparisons are recorded. FluidNC4.1.1
Planner.cpp source blob eb0b1b81953feece3d3888941b623784aba368b4 was inspected.

Both wells have separate disabled lip_stripping fields: measured_contact_xyz,
contact_feed_mm_min, relative_x_mm=-20 and safe_retract_z. Missing values stay
null. Enabling fails before any station motion; no lip contact implementation
or invented location is present. Future X-20 means measured contact X minus20,
never absolute machine X=-20. Future one-wipe/lip sequence is NOT active here.

Spring runtime uses the same Z-8 source/plan for A baseline1000-ink, B new1200,
C wet15000. Commanded feed, configuration-reference acceleration and synthetic
100mm/s² comparisons share assumedJD0.01. Categories are exclusive, with used-
brush return separated from other station transfers. Future lip time excluded;
physical times/attained feeds and new brush response are not claimed verified.

Reproduce (existing recovered bound inputs, no artwork regeneration):
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.high_speed --output NEW_DIR
Add --machine BOUND/spring.machine.json --provenance BOUND/spring.provenance.json
for the complete canonical Spring runtime comparison. Existing formal physical
profile, clearance, installed-config, stopping/evidence and authorization gates
remain intact. Review filenames are intentionally not authorized Spring jobs.
