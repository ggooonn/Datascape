# Final physical-feedback benchmark and Spring handoff

Actual numeric REVIEW commands, not authorized physical exports. Both previous
Paint variants at pinned f6aca60a were successfully run over UGS TCP according
to the operator: higher feeds, station visits, Z35 and palette loading worked;
vibration/noise acceptable. New refinements below remain awaiting confirmation.
No controller configuration readback or exact attained speed is inferred.

Same original40 strokes/depth order/visits. Ordinary12000, wet-main9000,
drawing6000, noncontact Z/approach7000, paper contact/release/pressureZ2000.
Normal paper hover15, local disabled; no per-strokeZ35 round trips. Station and
cross-region clearance35. Home start0/898/35; park800/800/35/M2; M0=0.
Existing wet departure/arrival3000 over5mm and separate station feeds retained.

Both shallow passes are now PRESSED20mm atZ7.5: ink445->465, water295->315.
Optional endpoints475/325 are configurable candidates, not defaults. Surface9
and compression1.5 stay operator assumptions; no blind slope extrapolation.
First pass X840, controlled release to9, vertical lift to17.5 BEFORE X-10,
lifted return via middleY402.5/252.5, second passX830, release and retract35.
Prior pressed passes were only10mm. Doubling distance does not prove actual
surface contact; insufficient contact/force remains a separate possible cause
of weak removal. Compression is not increased automatically.

Purge840/137.5, target1.5, dwell4s, one vertical dab, no rubbing. Nominal
surface1.5 implies ZERO nominal compression; target1.0 is an explicit alternate
if later selected, not automatic fallback. Negative compression is rejected.
All registered palettes keep radius5/feeds/centers; common equivalent geometry
uses liquid6 minus immersion1 -> dip5, instead of prior dip4. No new per-slot
measured liquid height is invented. Ink dwell2s, water5s unchanged.

X860 candidate YAML is byte-identical to pinned PR31 and changes only X max
travel versus recorded installed850. The operator's intended860 and physical
reach are retained; installation/readback/homing verification are STILL
unreported. Reviews reach855, pass candidate860 bounds and explicitly fail the
recorded850 bound. Formal profile/evidence/authorization gates stay intact.

Matched Air: paper strokes15 and station XY35, no paper/liquid/stone/cloth
contact. WATER_ONLY and INK_GOUACHE numeric commands match and include actual
wiping, purge and loading, not Z35-only Paint substitutes. Verification covers
regeneration, bounds/feeds, actual15/7000, pressed length/height, lift-before-X,
40 strokes, M0=0, finalpark/M2, read-back and SHA256.

Reproduce: PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.measured_stations --output NEW_DIR
Verify: same command with --verify. Original source-plan hover10/5 metadata is
retained provenance, not this version's execution height.

Canonical Spring inputs have now been recovered with the byte-verified PR25
adapter and exact existing machine/provenance SHA256s. Full LayoutD plan readback
preserves14951 unsplit sources/240974 pressure samples/50 continuous X300
crossings and S3a. spring_runtime.py compares hover10/Z6000, hover15/Z6000 and
hover15/Z7000 on FULL synchronized trajectories with existing material visits,
reloads and separate jobs. Estimates are not measured runtimes or safety tests.
After final refinement feedback, the same-profile spring_pipeline exports Air,
SHARED_INK and SHARED_COLOR through the official gates and verifier. No preview
files are substituted for requested authorized Spring executions.
