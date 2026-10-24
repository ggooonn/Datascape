# Current Spring handoff after large-Baegunmo benchmark

Base PR31/e5e11ff4aa91eebc46eab44172b0da13ee03fd9c, preserved/unmerged.

Current profile: profile.spring.large_baegunmo.json. Ink1500(default)/2000(optional),
color1000. Large Baegunmo; first-touch10 independently configurable by medium/slot.
Relative paper hover10 -> absolute20; approach+5 ->15; global/stations35 absolute.
All station, lip, palette, washing/purge XYZ and Y900 YAML remain unchanged.

New compression knots:0:0,.2:1,.4:3.5,.6:5.8,.8:8.2,.93:10.2,1:12mm.
Paper Z=first-touch minus compression. Old Z-8 profile remains historical.
Actual accepted pressures0.22..0.93 map1.25..10.2mm, below the reported approximate
12mm splitting onset. This does not establish measured widths or all brush behavior.

Preserved operator observations: physical1..15mm test completed, clear width
differences, splitting around12,1500mm workable with late fading, lip/wash/recovery
and Y900 working. No exact widths or active-YAML/streamed-file hash invented.

Complete review programs: SPRING_AIR, SHARED_INK, SHARED_COLOR; each independently
starts0/900/35 and ends800/800/35/M2, M0=0. AIR is noncontact paper20/station35.
INK and COLOR remain separate, with manual cleaning/water/material/drying/G54
review between them. Preserve canonical14951 strokes/240974 pressures/50 continuous
X300 crossings, F2-C/v13/S3a/twelve colors and source directions.

Use RUNTIME.md for labeled modeled times and physical_benchmark_observations.json
for physical reports. Visual width proxy is not measured width/diffusion. The
profile remains nominal_review/unverified for the new curve; physical benchmark
observations do not silently satisfy formal full-scene profile/evidence/authorization
gates. No hardware operation occurred. Next is review/authorization of the prepared
Spring jobs using this profile and actual current evidence, not a new hardware or
artwork study. The existing spring_pipeline prepare/air/ink/color exporter is reused.

For Git transport the complete canonical-plan gzip is split into two parts;
spring_large_baegunmo --output THIS_DIRECTORY --verify joins them in memory.
The delivery ZIP contains the unsplit plan and ordinary G-code files.
