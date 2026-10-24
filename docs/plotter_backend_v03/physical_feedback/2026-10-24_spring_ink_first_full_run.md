# First complete Spring ink run — operator feedback, 2026-10-24

## Preserved checkpoint

Implementation baseline: Draft PR32, `f9ac4da7fca907ed2529f123fa792c61a869caed`, branch `spring/large-baegunmo-z10-hover20-v01`. Preserve all existing numeric G-code, profiles, pressure intent, artwork and Y900 YAML. This update records observations and follow-up candidates only; no execution, geometry, normalization, reload interval or machine configuration is changed.

## Operator observations

- The full ink run completed and the scene was successfully drawn.
- Physical lines are substantially wider than the intended/rendered appearance. Overlapping marks merge into black regions and obscure separation.
- This is a physical width/spacing issue to investigate, not a decision that the whole pictorial grammar should be redesigned.
- The operator accepts the X-positive toward X-negative drawing direction and the overall progression upward from Y0.
- Brush bending during X-negative drawing leaves a margin at the left edge even when the commanded endpoint reaches X0.
- The operator believes approximately2–3mm of negative-X mechanical allowance exists and proposes boundary overtravel to compensate. This is reported allowance, not a measured/authorized machine envelope.
- Ink delivery over1500mm and possibly2000mm appears feasible with the current brush. Small-brush capacity has not been established.
- A smaller brush with1500mm ink reload is a proposed next trial. It is not yet a selected/calibrated replacement profile.
- For many short paths, distance-only reloading can underrepresent depletion; the operator reports material shortage from the middle of the run onward in that condition. The exact material/file/portion was not specified.
- Ink elapsed time was approximately2hours, reported by the operator. Current1100mm configuration-reference estimate was116.66min before terminal cleaning. This is qualitative agreement, not a precisely timed120.000min measurement or refitted timing model.
- Terminal water washing/sponge purge has been implemented. Its physical success was not explicitly reported here.

No photograph, numerical stroke widths, brush-specific first-touch remeasurement, streamed-file SHA256 or exact timing log was supplied with this feedback. These omissions are not silently fabricated. Full color completion, terminal cleanup success and formal profile authorization are not inferred from ink completion.

## Physical width and preview follow-up

Previously delivered compression-width previews are explicitly unmeasured proxies. Do not use them as millimetre-accurate brush-footprint predictions. Compare a smaller brush at unchanged canonical spacing first, with its own paper first-touch reference and a small set of measured width/continuity samples. Preserve the current pressure values and geometry; decide any subsequent pressure mapping or spacing change from that comparison rather than changing several variables at once.

The existing1500/1000 historical profile and1100/700 selected profile remain preserved. Reusing a large-brush file unchanged with a smaller brush is not established: first-touch and compression response can differ. A future small-brush1500 candidate should inherit the accepted motion/station sequence and source order, with independently verified brush reference/mapping; color interval remains700 unless explicitly revised.

## Left-edge brush-deflection candidate — not implemented

Treat compensation as a separate plotter execution transform, not a global G54 shift or rewrite of canonical art. Candidate: selectively extend appropriate X-negative stroke endings that actually reach the left paper boundary, testing approximately2–3mm overrun. Do not extend every internal endpoint or reverse source directions.

The current profile uses zero G54 offset and an axis-reference envelope X0..860/Y0..900/Z−11..35. Current YAML has X homing mpos0, negative homing direction, max travel860 and a negative limit input. Thus X−2/−3 lies outside the current software envelope. Increasing max travel alone must not be presumed to authorize a negative lower bound. Physical clearance, limit-switch engagement, brush/holder swept path, actual FluidNC version/frame behaviour and matching backend bounds must agree before a numerical negative-X candidate is emitted. Do not disable limits or globally translate paper/stations to evade this.

FluidNC primary reference: https://wiki.fluidnc.com/en/support/machine_space_and_homing

## Short-stroke material budget candidate — not implemented

Keep the accepted distance-only scheduler as the historical baseline. Candidate: track cumulative drawing XY plus the number of paper contacts/completed original strokes since load; optionally track contact time if useful. Reload at the next original-stroke boundary when either budget is exhausted. Alternatively fit a calibrated effective-distance cost per contact after observing depletion. Do not invent contact-count thresholds or consumption constants.

Ink and each color retain independent budgets. Clear budgets on material load, retain existing same-color reload and color-change washing behaviour, and never insert a service mid-source or at a continuous X300 crossing.

## Next comparison, without reopening the artwork

1. Preserve this completed large-brush run and its source files as the physical checkpoint.
2. Verify the smaller brush's first-touch and physical stroke widths at selected compression values.
3. Compare unchanged scene crops with a proposed1500mm ink budget; decide spacing/pressure only after inspecting the marks.
4. Separately validate any left-edge overtravel and mixed distance/contact-count budget before generating a new complete review variant.

This record does not authorize machine operation or merge PR32. No new G-code/YAML is generated by this checkpoint.
