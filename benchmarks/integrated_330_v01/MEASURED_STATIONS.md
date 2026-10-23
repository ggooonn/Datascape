# Final physical feedback: hover15 and Spring handoff

Base Draft PR31: `f6aca60a24499036c4e17de994abde63c9189839`.
Both prior Paint benchmarks ran successfully over UGS TCP per the operator:
higher feeds, Z35, station visits and palette loading worked; vibration/noise
acceptable. Reported defects: saturated brush trails at hover10, weak water
removal, excessive purge compression and a request for less palette immersion.
These observations are retained; they do not certify the NEW refinements.

## Focused changes

| Item | Previous | Final trial |
|---|---:|---:|
| Paper hover | 10 | 15 |
| Noncontact Z / paper and station approach | 6000 | 7000 mm/min |
| Pressed shallow pass | 10mm | 20mm |
| Ink pass / optional endpoint | 445..455 | 445..465 /475 |
| Water pass / optional endpoint | 295..305 | 295..315 /325 |
| Purge target / dwell | 0.5 /4s | 1.5 /4s |
| Palette dip / immersion | 4 /2mm | 5 /1mm |

Ordinary12000, wet-main9000, draw6000, paper contact/release/pressureZ2000,
local hover off, station/cross-region35, home start0/898/35, park800/800/35/M2,
forty original benchmark strokes, M0=0 unchanged. Paper links remain15 rather
than35. Existing wet departure/arrival3000 over5mm and independent station
feeds retained: immersion/agitation/slope/palette1000, shallow/purge contact750,
shallow wiping1000 and lifted re-entry3000. Ink dwell2s, water5s, X+/-15,
purge center840/137.5 and radius5 palette pattern are unchanged.

Wiping remains contact7.5 from assumed flat surface9/compression1.5. Both
passes now actually move Y+20mm WHILE PRESSED. They do not merely extend the
lifted approach. First passX840, controlled vertical release to9, vertical
lift to17.5 BEFORE X-10, lifted return via middle402.5/252.5, second passX830,
release and retract35. Endpoints and depth remain configurable; alternatives
475/325 are not defaults. More distance does not prove adequate surface contact:
insufficient real contact/force remains separate, so compression is NOT deepened.
The added endpoint reach and flat surface remain final-trial assumptions.

Purge target1.5 equals nominal surface1.5: zero nominal compression, not an
invented positive compression. Alternate1.0 remains configurable; no automatic
fallback. Negative compression fails. All12 Spring slots retain centers/order
and use the corrected common liquid6/dip5 model where geometry is equivalent;
no per-slot measured liquid level is fabricated.

X860 YAML is unchanged, SHA256
64325aac547971245ae73c1be4c640ec69f233ca92127d5deaeff0423eabb937.
Actual installation/config readback/homing status is STILL unreported. Successful
benchmark travel is not a substitute for readback. Candidate860 bounds pass;
recorded850 conflict is explicitly retained. Other YAML settings are untouched.

## Actual files and checks

Three complete numeric REVIEW files in review_measured_stations/ retain the
same40/visits/XY pairing, real Paint contacts and no M0. Air uses paper15 and
station35, no contact. Water/pigment numeric commands match. Verification covers
actual15/7000, pressed lengths/heights, lift-before-X, purge/palette targets,
axis bounds/feed caps, actual read-back, regenerated IR, SHA256 and park/M2.
144 software tests passed, INCLUDING the recovered full-scene conditional test;
no skip remains. Fifteen focused station/handoff tests cover these corrections
and gated .gcode extension export. No new physical test is marked passed.

Reproduce/verify with the existing measured_stations --output NEW_DIR / --verify
commands; PYTHONPATH=src:. All earlier source plan geometry stays frozen.

## Full Spring recovery and time impact

The pinned PR25 adapter and essential frozen binding resources were recovered.
recover_spring.py verifies source bytes, calls the ORIGINAL apply_profiles
without generating pressure, then requires existing canonical machine/provenance
SHA256s. Full LayoutD preparation/readback is NOW rebuilt:14951 unsplit strokes,
240974 accepted samples,50 continuous X300 crossings, unchanged plan hash
8b4804f561f0eaab28753ae1790ce3b0f5b9ab8ba9a4a2ffe1e4daecbe2596bd.
Original F2-C/v13, source direction, Pressure Intent, S3a and Spring12 are locked.
Unused terrain/render archives are not claimed verified; exact canonical output
checksums and every bound vertex/pressure are verified. Inputs and full plan are
included in the delivery package so subsequent Work need not recover them again.

Full synchronized trajectories use the SAME production renderer/material state
machine with an explicitly offline envelope-only sink; no fake collision boxes.
Pressure-driven XYZ axis rates remain limited. Compare the same final station
policy with three hover/Z combinations; no artistic or routing optimization:

| Job | Z10/F6000 commanded | Z15/F7000 commanded | Increase | Z15/F7000 acceleration reference |
|---|---:|---:|---:|---:|
| SHARED_INK | 190.67min | 194.33min | 3.66min | 214.95min |
| SHARED_COLOR | 298.58min | 311.86min | 13.28min | 371.32min |

Hover-only atF6000 adds5.44min ink/19.13min color; F7000 recovers some commanded
time. Acceleration reference uses recorded YAML1200/1200/1000 and ASSUMED
junction0.01; no attained/runtime guarantee. Compared with Z10 reference it
adds5.99min ink/21.33min color. Synthetic100 acceleration comparison is included
in JSON, not applied to the controller. Existing depleted-return F600 remains
included unchanged, not silently optimized. Color commanded categories:
drawing16.12, paper engagement118.89, other travel39.02, station transfer122.24,
handling15.60 minutes. The color4–5h target is not guaranteed: this model is about
5h12 commanded /6h11 acceleration-reference. No speed increase is proposed.
See review/spring_hover15_runtime.json for all categories/scenarios/assumptions.

## Production handoff, no benchmark redesign

spring_pipeline expects hover15/noncontact7000 and this unchanged motion policy.
Modes prepare -> air -> ink -> color reuse canonical binding, existing S3a and
formal export/verification. Authorized export now supports .gcode with the
extension recorded and hash-verified (legacy default .nc remains compatible).
No placeholder or preview is offered as an authorized Spring program.

After final refinement confirmation and actual X860 readback, complete the
existing measured-profile/scoped safety records and stage authorization from
real evidence, then export Spring Air and SHARED_INK.gcode/SHARED_COLOR.gcode.
A330mm test does not by itself certify the entire600x900 substrate/corridor or
resolve prior stopping limitations. Those official gates are retained, not
invented as passed. This revision does not repeatedly attempt blocked exports
or claim that final refinements/production are already authorized. No merges
or hardware operation; next Work consumes the physical results, not a new study.
