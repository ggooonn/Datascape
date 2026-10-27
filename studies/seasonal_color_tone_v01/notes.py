"""Human review and execution handoff for the provisional display framework."""
from model import *
import html

def textfile(name,content):
    p=OUT/name;t=p.with_name(p.name+'.pending');t.write_text(content.strip()+'\n');t.replace(p)

def write_notes(c,evidence,proposals,transitions):
    table='\n'.join('| '+ ' | '.join([p['id'],p['stage'],p['base'],p['structural']+' / '+p['mineral'],p['accent'], '/'.join(str(round(v*100)) for v in p['ink_mix_target'])])+' |' for p in c['panels'])
    transition_text='\n'.join(f"- **{t['from']} → {t['to']}:** {t['logic']}" for t in transitions)
    textfile('FRAMEWORK.md',f'''# Seasonal color and tone framework v01

Status: provisional artistic intent. Baseline: PR38, `{c['baseline_commit']}`. All canonical geometry, widths, pressure/expression and opacity profiles remain unchanged. Spring receives style references only; no supplemental Spring paths are created.

Three roles organize the whole screen: **base** supplies pale underlying terrain/ground climate; **structural** binds vegetation and mineral bodies; **accent** identifies a few exposed or protruding episodes. The mineral companion belongs to the structural role, not a fourth role. Paper remains an active spatial component; the base is not an all-over wash.

| Panel | Direction | Base | Structure: vegetation / mineral | Accent | Light / middle / dark target % |
| --- | --- | --- | --- | --- | --- |
{table}

The hex values are display anchors, not pigment identities. Smoothstep interpolation in OKLab runs between panel centers across all seven boundaries, in the 2400 mm continuous painted coordinate. Seven 40 mm display gaps are excluded from color evaluation. This links neighboring color families without forcing skyline alignment. A continuous role function does not promise continuous painted coverage where a scene leaves paper open.

Spring opens in pale yellow-green, celadon and light mineral support. Summer becomes fuller through cool vegetation bodies, mineral blue-gray and warm apertures, rather than turning all terrain green. Autumn changes the structural family toward straw/copper and then dry mauve-gray; its unequal retreat needs a future foreground adjustment. Winter concentrates on cold mineral planes and a reduced color emphasis, preserving a small warm remnant and the gentle P8 ending.

## Seven transitions

{transition_text}

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
''')
    counts='\n'.join(f"| {s.title()} | {evidence[s]['ink_paths']} | {evidence[s]['color_paths']} | {evidence[s]['native_tree_owners']} | {evidence[s]['tree_accents']} |" for s in ORDER)
    textfile('DISTINCTIVENESS_REVIEW.md',f'''# Seasonal identity review

## Main finding

Spring → Summer is legible through an established open Spring and denser Summer ground. From P3 through P7, similarity is strongest in the tightly folded contour vocabulary and the repeated supported-tree/plinth arrangement, not in an identical skyline. P8's gentler terrain and open ending already help; preserve them.

| Season | Ink paths | Existing color paths | Tree v10 owners | Native tree accents |
| --- | ---: | ---: | ---: | --- |
{counts}

`baseline_audit.json` records the exact source counts and rock regimes. New-season trees use accepted P/B/U forms with the same `none` accent family; Summer, Autumn and Winter rock paths remain predominantly jointed or layered, with no classified rounded regime. The current B formation recipe repeatedly combines jointed parent/rear/shoulder and a layered front member. Changing size, member count and omission has not changed that underlying morphology enough.

## Where the sequence converges

- **P2 → P3:** Spring's open distribution gives way to a humid, dense bank. Keep the receiving passage light; do not rely on a dark brown edge to announce Summer.
- **P3–P4:** The diagonal release is useful, but foreground needles and jointed plinths can read as separate stacked display marks. Stronger color grouping improves hierarchy while the spatial-grouping issue remains.
- **P4 → P5:** This is the most important differentiation task. Autumn's baseline has fewer color paths, but all 1,029 belong to one canopy-edge group. Its mountains and supporting formations still feel related to Summer. A warm palette is useful evidence, not a sufficient new seasonal identity.
- **P5 → P6:** Keep Autumn asymmetric. Retreat one crown episode, expose a dry ledge and reduce the repeating center relay rather than applying uniform foliage thinning.
- **P6 → P7:** Winter has only 325 existing color paths, all in the distance group. Reduction already exists numerically, yet the recurring tree/plinth scaffold and folded contour character remain visible. Selective exposed branches, one coherent rock plane and ground contacts would differentiate it more than more recoloring.
- **P7 → P8:** Preserve the lowering, gentler finish. Avoid making the last foreground remnant as visually heavy as the opening winter shelter.

## Evidence and limits

Existing Summer/Autumn/Winter cameras use different eye positions and directions within the same DEM window (15 × 13.2 km). `source_view_evidence.png` plots the saved cameras; no new viewpoint search was performed. They also share the depth-unfolding map and A/B/C/D language. Similar mountain character does not mean copied skyline geometry. `mountain_character_evidence.json` reports simple silhouette range and adjacent-height metrics; it does not measure artistic distinctiveness.

`foreground_scaffold_review.png` shows the repeated left/relay/right support positions. This is the clearest limited intervention point. Middle/far contours can remain shared while changing local ink emphasis and color territories. No silhouette or approved Spring geometry is edited in this Work.

For skyline continuity, retain natural within-pair projection. Across seasonal boundaries, use related height, slope, directional flow and negative space provisionally. The existing P2→P3 skyline reference remains authoritative; color transition is not a license to align or distort those ridges. PR38 reports top-down skyline steps of −18 mm (P2→P3), +116 mm (P4→P5), and +33 mm (P6→P7); do not infer geographic continuity from these screen relationships.
''')
    body=[]
    for season,p in proposals.items():
        body.append(f"## {season.title()} — proposed, not applied\n\n**Vegetation:** {p['vegetation']}\n\n**Rock:** {p['rocks']}\n\n**Ground:** {p['ground']}\n\nExisting controls: "+'; '.join('`'+x+'`' for x in p['existing_controls'])+'.\n\nEntry points: '+', '.join('`'+x+'`' for x in p['library_entrypoints'])+'.')
    textfile('FOREGROUND_RECOMMENDATIONS.md','''# Limited foreground differentiation using existing libraries

These are concrete proposals for a later geometry Work. None has been generated or applied here. Retain seasonal cameras, middle/far contours, panel footprints and the useful existing support groups; intervene in one dominant/subordinate grouping at a time.

'''+ '\n\n'.join(body)+'''

## Library bounds and review sequence

Use Tree v10 accepted P/B/U anatomy. W remains experimental; no W promotion or generation is included. Existing accents include bent, broken-top, suppressed, dead-limb and damaged-crown. `terminal-droop` is an existing architecture option, not a new species. Use posture, vigor and stem ratio to vary the group; the foliage unit-count control supports 1.0–1.5 rather than arbitrary reduction, so reduction should use supported vigor/architecture and scene omission. Do not treat every Autumn or Winter member identically.

Rock v05 `base_mass` already supports compact/angular/bedrock and layered/jointed/rounded regimes. Its bounded multi-mass `FormationControls` support unequal dominance, overlap, burial and orientation. For existing B formations, keep dominance 0.6–0.8, overlap 0.1–0.4 and burial 0–0.35. A coherent A-style rock means a scene arrangement around a supported bedrock parent; it is not a new generator mode.

For the next geometry review, change one Summer bank grouping, one Autumn retreat/ledge episode, and one Winter shelter/plane episode, then compare their shared ground, burial, overlap and foreground silhouette at full pair scale. Avoid replacing every group. Color territories should bind the resulting forms, not hide unresolved ground contact.

Sources: `docs/catalog/tree_v10/{README.md,DECISIONS.md}`, `docs/catalog/rock_v05/{README.md,DECISIONS.md}`, `src/datascape/vegetation/tree_final_scale.py`, `src/datascape/ground/structural_detail_v05.py`, and `studies/seasonal_composition_v03/recipes.py` at the pinned PR38 commit.
''')
    textfile('SPRING_P2_HANDOFF.md',f'''# Later Spring / P2 color execution handoff

1. Review `P1_P8_theme.png`, `P1_P8_ink_led.png`, `P2.png`, `P2_D4_comparison.png` and `FRAMEWORK.md`. Choose Spring color strength, the pale mineral replacement and the intended P2→P3 receiving passage artistically before execution.
2. Use frozen Spring source files `artworks/spring_v13/visible_ink.json.gz`, `visible_color.json.gz`, and `palette.json` at `{c['baseline_commit']}`. Canonical Spring geometry, expressive envelopes and pressure intent are authoritative. No new Spring color guides are supplied.
3. `spring/P2_style_handoff.json.gz` lists existing source IDs intersecting P2 and provisional styles. It contains **no geometry or machine material mapping**. P2's continuous X offset is 300 mm. Use the established source-arc panel-clipping contract later; an intersecting source ID is not a panel contact count.
4. Review the primary D4-free virtual replacement first. Compare small physical coupons of candidate A4/A2/A5 and, if useful, restrained D1. The low-D4 image is only an alpha comparison; derive actual strength from physical tests, not 0.18 as a dilution or Z formula. Confirm paper and drying behavior independently.
5. Once pigment choices are accepted, derive an explicit physical slot/dose strategy in a separate execution Work. Respect canonical source IDs, source arcs, effective pressure and boundary behavior. No production color G-code is supplied or authorized by this study.

Middle/far contour drawing appears relatively stable. Foreground is less physically verified: thick foliage and rock grouping may require different brush strategies, contact/spacing and local handling from middle/far contours. That is a production consideration, not a reason to change canonical geometry here. The common-white and candidate-material previews are not wet-print proofs.

## Restart files

- `configs/experiments/seasonal_color_tone_v01.json`: panel anchors, role/display gains, tone targets, seven transition narratives and D4 policy.
- `studies/seasonal_color_tone_v01/generate.py`: reproducible study entry point.
- `spring/style_intent.json.gz`: full source-ID style sidecar; physical schedule remains null.
- `spring/P2_style_handoff.json.gz`: focused P2 source references, execution-ready false.
- `baseline_audit.json`, `panel_intent_statistics.json`, `verification.json`: source evidence, measured display-path statistics and verification.

Outstanding decisions: stronger theme versus ink-led option; acceptable remaining seasonal similarity; future foreground interventions; Autumn copper saturation; Winter reduction and P8 balance; final physical substrate, pigments and brush behavior. These remain artistic/physical acceptance decisions.
''')
    textfile('README.md',f'''# Datascape — Seasonal Color Framework & Tone Review v01

Open **[Review.html](Review.html)** after extracting the complete package. The study continues PR38 at `{c['baseline_commit']}`. It adds display studies and source-ID sidecars while preserving every baseline file. It does not redesign scenes or produce G-code.

## Review first

1. [Eight-panel stronger theme](P1_P8_theme.png), [ink-led option](P1_P8_ink_led.png), [matched-renderer before/after](P1_P8_before_after.png).
2. [Role and tone framework](framework_ribbon.png), [ink only](P1_P8_ink_tone.png), [color only](P1_P8_color_only.png).
3. [P2 D4 options](P2_D4_comparison.png), [foreground scaffold evidence](foreground_scaffold_review.png), [existing source views](source_view_evidence.png).
4. `P1.png` through `P8.png`; each season folder also contains pair, separated ink/color, control, quieter and provisional material-context images.

Read [FRAMEWORK.md](FRAMEWORK.md), [DISTINCTIVENESS_REVIEW.md](DISTINCTIVENESS_REVIEW.md), [FOREGROUND_RECOMMENDATIONS.md](FOREGROUND_RECOMMENDATIONS.md) and [SPRING_P2_HANDOFF.md](SPRING_P2_HANDOFF.md).

## Completion versus acceptance

**Technically completed:** all eight display-intent studies, continuous three-role palette, seven transition rules, tone cohorts, D4 comparison, source audits, source-ID sidecars, read-only identity review and P2 handoff. All canonical scenes and approved Spring geometry remain frozen. Supplemental color-territory guides after Spring are review-only exact source subarcs, not production color geometry.

**Provisional:** color anchors, display gains, ink-tone targets, unmeasured material backgrounds, artistic seasonal distinctiveness and the proposed foreground adjustments. No physical pigment schedule, concentration, calibrated dose, production path assignment or G-code is delivered. Foreground form changes are **proposed, not applied**.

## Reproduce

In the full repository checked out at the study commit, install `numpy scipy matplotlib pillow shapely pytest`. Run:

```bash
OPENBLAS_NUM_THREADS=1 python3 studies/seasonal_color_tone_v01/generate.py
python3 -m pytest -q tests/test_seasonal_color_tone_v01.py
python3 studies/seasonal_color_tone_v01/verify.py
```

For one season use `--scene spring|summer|autumn|winter`; after all four use `--finalize`. Source vectors and saved depth fields come from PR38, not from a regenerated DEM or new viewpoint search. `reproducibility_manifest.json` pins all used inputs, including config, camera/placement, depth fields, palette, skyline and archived reference. `verification.json` records independent checks. PNG bytes may vary with renderer/font versions; style and guide JSON are deterministic. The extracted review package is self-contained for visual review; full regeneration additionally requires the pinned repository inputs.

Canonical input paths: `artworks/spring_v13/visible_{{ink,color}}.json.gz` and `docs/experiments/{{summer_composition_v03,autumn_composition_v01,winter_composition_v01}}/{{ink,color_intent}}.json.gz`. The new output folder contains style references, not replacements for those canonical vectors.

All public documentation, comments and commit messages are English. No earlier PR is merged or changed by this additive study.
''')

def write_html(c):
    images=[('P1_P8_theme.png','Stronger seasonal theme'),('P1_P8_ink_led.png','Ink-led option / 0.65 display color gain'),('P1_P8_before_after.png','Matched-renderer control and theme'),('framework_ribbon.png','Three roles and artistic tone targets'),('P2_D4_comparison.png','P2 D4 / replacement / low display option'),('P1_P8_color_only.png','Color intent alone'),('P1_P8_ink_tone.png','Ink-tone intent alone'),('P1_P8_candidate_substrate.png','Unmeasured material-context candidates'),('foreground_scaffold_review.png','Repeated foreground support scaffold'),('source_view_evidence.png','Existing PR38 views / no viewpoint exploration'),('PR38_archived_reference.png','Archived PR38 reference')]
    figures=''.join(f'<figure><h2>{html.escape(title)}</h2><a href="{file}"><img loading="lazy" src="{file}" alt="{html.escape(title)}"></a><figcaption>{file} · open image for full resolution</figcaption></figure>' for file,title in images)
    panels=''.join(f'<a href="P{i}.png"><img loading="lazy" src="P{i}.png" alt="P{i}"><span>P{i}</span></a>' for i in range(1,9))
    pairs=''.join(f'<li>{s.title()}: <a href="{s}/theme.png">theme</a> · <a href="{s}/baseline_control.png">control</a> · <a href="{s}/color_only.png">color</a> · <a href="{s}/ink_tone.png">ink tone</a> · <a href="{s}/statistics.json">statistics</a></li>' for s in ORDER)
    docs=''.join(f'<li><a href="{f}">{f}</a></li>' for f in ['FRAMEWORK.md','DISTINCTIVENESS_REVIEW.md','FOREGROUND_RECOMMENDATIONS.md','SPRING_P2_HANDOFF.md','README.md','verification.json','reproducibility_manifest.json','panel_intent_statistics.json','transitions.json'])
    textfile('Review.html',f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Datascape / Seasonal Color and Tone v01</title>
<style>body{{margin:0;background:#eeeae1;color:#283b35;font:16px/1.6 system-ui,sans-serif}}header,main{{max-width:1600px;margin:auto;padding:26px}}h1{{font-size:clamp(28px,3vw,48px);line-height:1.15}}small,figcaption{{color:#626b61}}a{{color:#2d6858}}figure{{margin:35px 0;padding:18px;background:#fffdfa;border:1px solid #d5d7cb}}figure img{{width:100%;height:auto}}.panels{{display:grid;grid-template-columns:repeat(8,1fr);gap:8px}}.panels img{{width:100%}}.panels span{{display:block;text-align:center}}.note{{padding:18px;background:#e0e7db;border-left:4px solid #5c8067}}@media(max-width:700px){{.panels{{grid-template-columns:repeat(4,1fr)}}header,main{{padding:14px}}}}</style>
<header><small>DATASCAPE / ARTISTIC REVIEW / v01</small><h1>Seasonal color framework<br>and tone across P1–P8</h1><p>Fresh Spring → humid mineral Summer → straw/copper Autumn → cold, paper-rich Winter.</p><p class="note">Provisional color and tone intent. Canonical geometry and pressure profiles remain frozen. Foreground redesign is proposed, not applied. Supplemental color guides after Spring are review-only. No physical pigment recipe or production G-code.</p><p>Baseline: PR38 / <code>{c['baseline_commit']}</code>. Primary comparison uses common white. Tap any image for full resolution.</p></header>
<main><h2>Individual panels</h2><div class="panels">{panels}</div><h2>Read and continue</h2><ul>{docs}</ul><h2>Pair details</h2><ul>{pairs}</ul>{figures}<p>Local, self-contained review; no external scripts or image dependencies. Technical verification does not imply artistic acceptance or wet-print calibration.</p></main></html>''')
