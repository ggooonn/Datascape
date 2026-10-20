# Exact offline Backend start procedure

Keep the Spring pressure checkpoint and Plotter Backend PR #23 in **separate checkouts**. Do not merge either PR. The pressure PR is stacked on PR #24's head, not on the Backend branch. Use the exact published pressure commit identified in the Draft PR/report; the frozen XY baseline is `67ba146b1213644d40bc9dabed9d52024d2bbe58`. The tested Backend source is `a2c3967b9d79030810f297cf5e1f5df079519aa3` from PR #23.

## 1. Bind before any panel clipping or scheduling

From the pressure checkout root, select **new** absolute output filenames outside frozen/checkpoint directories:

```sh
PYTHONPATH=src python -m datascape.spring_pressure_intent \
  --output /absolute/offline/spring_v13.pressure_v01.machine.json \
  --provenance /absolute/offline/spring_v13.pressure_v01.provenance.json \
  --backend-directory /absolute/BackendCheckout/src/datascape/gcode
```

Omit `--backend-directory` if the Backend checkout is not present yet. The command never creates G-code or uses the Backend CLI. It imports only the loader, models and scheduler for compatibility checks. PR #23's loader expects ordinary JSON; the derived output is intentionally uncompressed.

Default inputs:

1. Frozen machine vectors: `artworks/spring_v13/machine/spring_v13.offline.machine_vectors.json.gz`.
2. Frozen rich ink/color vectors and widths: `artworks/spring_v13/visible_ink.json.gz`, `visible_color.json.gz`; exact order in `ordering.json`.
3. Accepted pressure sidecar: `artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz`.
4. Acceptance/config/manifest checksums in the pressure checkpoint.

The loader checks all source manifest hashes, sidecar/config/payload hashes, unique IDs, sequence, per-ID XY and width/expression hashes, full source-record hashes, vertex counts, medium/color slot, layer and order/direction locks. Any mismatch raises; do not catch it to fall back to old values. The original frozen machine input is also checked against its original experimental/placeholder pressure, but those values are **never used as output intent**.

The adapter allocates a new machine object and replaces every per-point pressure from the sidecar. It changes no other machine field. Expected totals:

| Origin replaced | Strokes | Values |
| --- | ---: | ---: |
| Historical experimental | 675 | 8,975 |
| Explicit offline 0.5 placeholder | 14,276 | 231,999 |
| New artistic pressure | **14,951** | **240,974** |

Accepted gzip SHA-256: `0b8d59b7ca9268c70378b7a78df3f8825763b2b43e5667785459b2838d2b0b4e`.
Derived canonical machine payload SHA-256: `6586df2ea3c48ee45de7df10926a2845172f39203ec805f61724f0c7e504ff2b` (sorted compact JSON, no newline). Output files end with a newline; this payload hash differs from an ordinary file hash.

## 2. In-memory use and validation

```python
from datascape.spring_pressure_intent import load_accepted, check_backend
machine, provenance = load_accepted()
assert len(machine['strokes']) == 14951
assert provenance['pressure_values'] == 240974
assert provenance['fallback_permitted'] is False
# machine is a new object; frozen sources are unchanged.
# If loading the written file with PR23:
check_backend('/absolute/offline/spring_v13.pressure_v01.machine.json',
              '/absolute/BackendCheckout/src/datascape/gcode')
```

`check_backend` compares **every loaded pressure** against its sidecar value, and verifies scheduler ID order. PR #23's generic missing-pressure default must never be relied on. Treat absent sidecar profiles, pressures, vertex bindings or provenance as errors. A new artistic sample numerically equal to 0.5 remains a valid new sample; equality alone is not a provenance test.

## 3. Carry pressure provenance into Backend-derived data

Load and verify the unsplit 600 × 900 mm composition first. Keep both frozen inputs immutable and retain the separate binding provenance JSON, including the sidecar SHA, frozen machine SHA, original ID, sequence, source record/XY/width hashes and original vertex count.

Panel splitting belongs to Backend Work. For each derived fragment, keep:

- A unique fragment ID and `source_id` equal to the original canonical stroke ID (PR23's `origin_id` supports this), panel ID, original sequence/order group and locked direction.
- The accepted sidecar SHA and pressure origin `new_painterly_pressure_intent_v01`; attach the provenance by canonical source ID, not fragment-name parsing alone.
- For each new clipping/resampling vertex: original segment index and interpolation fraction `t` (or unambiguous original arc parameter), plus source arclength interval for the fragment. PR23 currently preserves `source_id` and interpolates pressure, but **does not persist these detailed parameter bindings**: Backend must add this companion record before relying on detailed traceability.

For a point within original segment i, use `p(t) = p[i] + t * (p[i+1] - p[i])`, with the same t used for XY. Do not renormalize pressure per panel, infer it again from width, revert to the old 675, insert default 0.5, or reverse paths. Retain entry/exit taper and short-stroke profiles. Interpolate only within the original segment; never bridge unrelated strokes or omitted/mist gaps. Validate all original values before interpolation; fragments will legitimately have different vertex counts afterward. Check interpolated pressure against the two bound source values, and maintain the source provenance record.

Coordinates remain continuous artwork millimeters. Backend may later support P1/P2 at X=300 or one 600 mm panel, origins and registration; the 40 mm exhibition gap is not an artwork coordinate offset. PR23's shared-seam ownership remains unresolved and must be handled there.

## Boundary

This dataset is ready as a **provisional artistic input for offline Backend development**. It is not physically calibrated or machine-ready. Preserve the documented clipping/flatness limitations; any future artistic revision needs review. Brush-specific width, pigment, wetting, feed, pressure-to-Z, compression limits, panel registration and safe execution remain Backend/calibration work. No calibrated Z, executable G-code, physical mapping or hardware routine is supplied here.
