# Reproduce the frozen Spring v13 checkpoint

Run from the checkpoint repository root. Core export uses Python standard
library only. Scene replay and artistic previews need the pinned
`requirements-review.txt` alongside this document.

## Lossless deterministic machine export

```sh
PYTHONPATH=src python -m datascape.spring_checkpoint export \
  --output /tmp/spring_v13.machine.json \
  --metadata /tmp/spring_v13.metadata.json.gz \
  --offline-only --unresolved-pressure 0.5
PYTHONPATH=src python -m datascape.spring_checkpoint verify \
  --machine /tmp/spring_v13.machine.json \
  --metadata /tmp/spring_v13.metadata.json.gz
```

Compare the ordinary JSON bytes with the decompressed committed machine file.
The metadata must be byte-identical to the committed metadata. All XY, IDs,
slots, layers, order and 675 original pressure profiles must match canonical data.
The explicit 0.5 value is an offline placeholder for missing intent, not original
or calibrated pressure. Omitting the explicit policy makes export fail closed.

## SVG and raster previews derived from exported XY

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m datascape.spring_checkpoint preview \
  --machine /tmp/spring_v13.machine.json --output /tmp/spring_v13_previews
```

This produces ink.svg, color.svg, combined.svg and corresponding PNGs. SVGs are
600x900 mm; PNGs are 1200x1800. Use `--compress-svg` for the exact committed
review/*.svg.gz format. Their profiled ink segments and color width envelopes
are display constructs, not extra plot paths. Never parse these SVG envelopes
as machine geometry. XY comes only from machine_vectors; width/alpha/palette
comes from the hash-locked rich artistic records. Placeholder pressure does not
control display width. The combined PNG RGBA data must equal review/approved.png.

## Re-run the recorded source operation, without resampling the scene

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python -m datascape.spring_checkpoint replay \
  --output /tmp/spring_v13_replay
```

Use a fresh output directory. This reconstructs exact v12 control files from a
single compact control archive, verifies and joins numeric F2 chunks, and reruns
only the deterministic recorded left-foreground operation with seed 2026101913.
It does not regenerate the mountains, mist, right anchor or unrelated vegetation.
Both resulting final visible gzip JSONs must have the approved canonical hashes.

Frozen pre-clipping authoring records and clipping/omission decisions remain
distinct from the final visible snapshot and from the machine file. No private
GeoTIFFs, reference images, pickles or full comparison archives are required.
Field chunks are exact portable replay inputs, split only for repository upload
limits; their original combined checksum is source/fields_manifest.json.

## Tests

```sh
PYTHONPATH=src python -m pytest -q tests/test_spring_v13_checkpoint_export.py
```

Backend compatibility is separately tested against PR #23's exact loader,
models and scheduler. See PLOTTER_BACKEND_HANDOFF.md. Do not run a G-code CLI as
part of these checkpoint tests.
