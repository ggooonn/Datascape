# Seasonal color and tone framework v01

Status: provisional artistic intent. Baseline: PR38, `6e331beb7e405cff55feb0ea9f3982808976f907`. All canonical geometry, widths, pressure/expression and opacity profiles remain unchanged. Spring receives style references only; no supplemental Spring paths are created.

Three roles organize the whole screen: **base** supplies pale underlying terrain/ground climate; **structural** binds vegetation and mineral bodies; **accent** identifies a few exposed or protruding episodes. The mineral companion belongs to the structural role, not a fourth role. Paper remains an active spatial component; the base is not an all-over wash.

| Panel | Direction | Base | Structure: vegetation / mineral | Accent | Light / middle / dark target % |
| --- | --- | --- | --- | --- | --- |
| P1 | fresh opening | #CCD3BA | #87A46D / #ADB49F | #D0C46B | 76/20/4 |
| P2 | celadon receiving groups | #BDCDB6 | #6D997A / #9FAE9F | #BEC873 | 69/24/7 |
| P3 | humid mineral and expanding green | #BBC9C3 | #427F70 / #8FA6A5 | #B6B36A | 61/29/10 |
| P4 | full cool masses with warm openings | #A9BDBD | #356A6B / #829B9F | #C3A261 | 53/33/14 |
| P5 | assertive straw and copper transition | #D3C1A1 | #A87A48 / #A38B70 | #CC7C3E | 56/30/14 |
| P6 | dry mineral and unequal retreat | #C4B6A7 | #8E6560 / #93847B | #B27B4D | 63/24/13 |
| P7 | cold planes and retained skeleton | #C3CBD0 | #748696 / #89939E | #AA9D82 | 74/18/8 |
| P8 | paper-rich gentle ending | #D9DCD9 | #949CA8 / #A7ADB4 | #B3AA98 | 84/12/4 |

The hex values are display anchors, not pigment identities. Smoothstep interpolation in OKLab runs between panel centers across all seven boundaries, in the 2400 mm continuous painted coordinate. Seven 40 mm display gaps are excluded from color evaluation. This links neighboring color families without forcing skyline alignment. A continuous role function does not promise continuous painted coverage where a scene leaves paper open.

Spring opens in pale yellow-green, celadon and light mineral support. Summer becomes fuller through cool vegetation bodies, mineral blue-gray and warm apertures, rather than turning all terrain green. Autumn changes the structural family toward straw/copper and then dry mauve-gray; its unequal retreat needs a future foreground adjustment. Winter concentrates on cold mineral planes and a reduced color emphasis, preserving a small warm remnant and the gentle P8 ending.

## Seven transitions

- **P1 → P2:** Fresh yellow-green edges consolidate into celadon groups; keep warm mineral support pale and let structural ink increase locally.
- **P2 → P3:** Carry celadon into humid blue-gray ground; deepen grouped vegetation while retaining a light receiving passage.
- **P3 → P4:** Increase cool grouped cores and mineral depth, with warm olive/amber openings rather than green over every terrain surface.
- **P4 → P5:** Use the existing amber opening as the hinge into straw/copper; make Autumn's structural color shift assertive, retaining cool mineral counterweights.
- **P5 → P6:** Copper peaks retreat into dry mauve/umber-neutral structure; break accent territories and expose more paper and rock.
- **P6 → P7:** Desaturate warm mineral remnants toward cold gray; shift emphasis from canopy color to selected trunks, joints and ground contacts.
- **P7 → P8:** Reduce colored path weight and dark-ink incidence while retaining a few warm remnants; preserve P8's gentle ending and long rest.

## Tone and the two review strengths

`P1_P8_theme.png` is the stronger color statement. `P1_P8_ink_led.png` uses 0.65 of its display color gain and the same ink-tone model. Compare both before choosing the strength. Ink-tone cohorts select existing source paths; their artistic target proportions are not physical dilution ratios. Structural edges, near mineral joints and trunk contours receive higher dark priority, while far terrain and dense foliage are biased lighter. Actual **length-weighted** light/middle/dark shares are recorded per panel in `panel_intent_statistics.json`; they need not equal the artistic selection targets.

Most contours remain in a shared Datascape language. Strength changes here are grayscale/alpha display intent only. Source pressure, width and expression are frozen. The renderer approximates source expressive envelopes with varying centerline widths; the matched-renderer control is the fair style comparison, while `PR38_archived_reference.png` is the historical raster reference.

## D4 and material awareness

The source Spring palette calls **D4 red earth / ochre** (`#A2432B`); **D5 is burnt umber** (`#4E3325`). The artist's observation that physical D4 dominates takes precedence over digital swatch appearance. The primary Spring/Summer framework assigns no physical D4. Spring's existing D4/D5 paths are retained and shown in pale role colors. Summer PR38 uses virtual color groups and has no assigned physical D4 station to remove.

`P2_D4_comparison.png` compares the same frozen source crop under existing color, primary replacement, and a D4 ×0.18 **display-alpha-only** option. This is not an eighteen-percent concentration, water ratio, pressure or Z recommendation. Candidate replacements for later coupons are A4 light warm/apricot gray, A2 light gray, A5 green-gray, and a restrained D1 adjustment if needed. Do not substitute dark D5 as a blanket solution. Autumn copper is also a virtual role color, not an instruction to fill D4.

The main comparison uses common white to isolate palette differences. `P1_P8_candidate_substrate.png` uses existing provisional material background colors only: these are unmeasured display contexts, not verified papers, calibrated absorption or a printing plan.

## What the color study adds

Existing source color paths receive style sidecars. Summer/Autumn/Winter also receive **review-only** pale terrain/mineral color-territory guides, following exact subarcs of existing visible A/rock ink sources near existing spatial groups. Their broader display envelopes are not canonical color geometry or executable brush paths. Spring receives zero guides. These guides make missing base/mineral roles visible without changing terrain or inventing a uniform wash band.

The selection is deterministic and spatially grouped. It is not a new plant/rock arrangement. Geometry-based foreground differentiation remains a recommendation for a later Work. Seasonal color gains, guide widths and alpha are display parameters with no automatic mapping to pigment quantities.
