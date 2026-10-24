# Final measured lip-stripping benchmark

Three complete numeric review files share the original 40-stroke plan, explicit
constant-Z -1..-10 trials, exact material visit sequence, and accepted high-speed
profile. Existing old candidates are preserved. No hardware I/O or official
machine-authorization bypass occurs. Review generation is requested; physical
clearance/installation/new-sequence success is not fabricated.

For each ink/water visit: immersion/X agitation -> original slope -> ONE pressed
20mm Y+ wipe at Z7.5 -> vertical release Z9 -> vertical lift Z35 -> XY815/458
(ink) or815/298 (water) at Z35/F3000 -> vertical Z20/F1000 -> X795/F300
(relative X-20) -> vertical Z35/F7000. Both measured starts are operator-confirmed.
No second wipe or X-10 re-entry remains. Lip coordinates are independent of
slope and shallow-surface models. Displacement, feed/cap, start and retract are
separate profile fields. The shared production emitter validates the grammar;
official station validation additionally requires the calibrated contact volume
and all existing full-tool path, evidence and stage authorization checks.

Matched AIR retains every XY path and station visit, with all station handling
at Z35 and paper simulation at Z15; it does NOT descend to the lip at Z20.
WATER_ONLY/INK_GOUACHE numeric bodies are identical, differing only in contents.
Start after manual home: G54 X0 Y900 Z35; zero G54/G92/TLO expected. End:
X800 Y800 Z35/M2, M0=0. No homing/offset-setting commands embedded.

Dry/depleted15000, wet12000 (separate optional15000 profile), drawing6000,
noncontactZ7000, pressure/contact/release2000, paper15/localoff, station35,
ink1200/color800 reload candidates remain unchanged. Other station feeds,
dwells, purge1.5/4s, palette5/radius5, twelve Spring colors/Z-8 remain unchanged.

YAML: motion/motor/homing scalar values equal the previous completed Y900
candidate. Only descriptive name and obsolete comments change. It remains a
separate candidate, NOT installed/read back here. Physical lowerY0 and all
station/paper work coordinates remain unchanged; no global+2 translation.
Expected home MPos=WPos0/900/35; actual configuration/home/range/stopping and
full-tool clearance verification remain physical execution prerequisites.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.final_lip --output NEW_DIR
Verify: same command with existing output and --verify. Optional canonical
--machine /path/spring.machine.json --provenance /path/spring.provenance.json.
After operator feedback: select/calibrate brush, then existing Spring AIR and
separate SHARED_INK/SHARED_COLOR export workflow. No production Spring files
are exported before those results/physical profiles/authorization exist.
