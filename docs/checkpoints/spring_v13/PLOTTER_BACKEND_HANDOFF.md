# Load Spring v13 in the separate Plotter Backend Work

Start the hardware Work on PR #23 `feat/plotter-backend-v01-offline`, pinned
contract commit `a2c3967b9d79030810f297cf5e1f5df079519aa3`. Keep this Spring
checkpoint in a separate checkout. Do not merge its visual dependency stack just
to load JSON. Do not change PR #23 from the Spring Work.

1. Fetch/checkout this checkpoint branch in a second repository directory.
2. In that Spring directory, run the export and verify commands in REPRODUCE.md
   with an explicit offline placeholder, producing `/tmp/spring_v13.machine.json`
   and `/tmp/spring_v13.metadata.json.gz`.
3. Run the actual unmodified Backend contract check from the Spring checkout:

```sh
PYTHONPATH=src python -m datascape.spring_checkpoint backend-check \
  --machine /tmp/spring_v13.machine.json \
  --backend-directory /absolute/BackendCheckout/src/datascape/gcode
```

This calls PR23's load_strokes and schedule functions only. Expected result:
14,951 strokes loaded; identical scheduled ID order; no G-code produced.

4. In the Backend checkout, load and inspect the same ordinary JSON directly:

```sh
PYTHONPATH=src python - <<'PY'
from datascape.gcode.io import load_strokes
from datascape.gcode.scheduling import schedule
s = load_strokes('/tmp/spring_v13.machine.json')
assert len(s) == 14951
assert [x.stroke_id for x in schedule(s)] == [x.stroke_id for x in s]
assert sum(x.medium == 'ink' for x in s) == 3345
assert sum(x.medium == 'color' for x in s) == 11606
print('Spring v13 contract loaded; no machine code generated')
PY
```

The committed machine file is gzip compressed; PR23's current loader expects
ordinary UTF-8 JSON. Use the adapter above or standard gzip decompression, not
load_strokes on the .gz file. Carry the metadata file with the JSON.

## What is ready

The full continuous 600x900 mm geometry is ready for **offline G-code/backend
development**: source IDs, exact vertex order, colors, layers, conservative order
constraints, original available pressure and explicit unresolved-pressure flags.
No nonplotting guides or diagnostic boundaries occur in the machine dataset.

## What is not physically approved

Only 675 paths have original normalized pressure intent. The other 14,276 use an
explicit offline-only 0.5 placeholder. Those values are not measured force,
original intent, brush compression, calibrated Z, dilution or pigment load.
Canonical rich data still distinguishes absent pressure from known intent.
PR23's own implicit 0.5 default is never relied on in this export.

All 675 known pressure profiles also need brush-specific physical calibration.
Width profiles, material-specific behavior and 4,572 expressive-width strokes
are retained in artistic data, not fully expressed by v0.1. Two sub-mm short
polylines are flagged; no dot/dwell/point-contact implementation is invented.
Do not infer execution readiness from contract acceptance or preview equality.

Backend remains responsible for panel choices (2x300x900 or future 600x900), seam
ownership, artwork-to-machine transforms, origins/registration, safe Z, feed,
pressure mapping, reload/wash sequencing and physical dry runs. Do not add the
40 mm exhibition gap to the artwork. This Spring Work generates no executable
production G-code and changes no FluidNC YAML or calibration.
