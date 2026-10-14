# Geumgang

- Physical work completed: 2026-03-17 (reported by the owner).
- Code label: V39.10.
- Code layout: 5 columns × 4 rows (20 panels).
- Marks: light ink, teal/ultramarine/navy, and horizontal curves.

## Files

- [Original notebook](original/datascape_0317test.ipynb): original bytes and saved outputs.
- [Code-cell extraction](original/source.py): an unchanged extraction for review, not a replacement for the notebook.
- [Source manifest and checksums](source_manifest.json).

Input: `Manmulsang_DEM.tif`. The historical loader falls back to synthetic terrain if loading fails.

The mapping between original datasets and final production files, physical materials, hardware conditions, and dependency versions still needs documentation. Saved notebook outputs are historical execution records, not proof of a current successful reproduction.

The [temporary cover rendering](../../assets/geumgang_render.png) is the supplied `output.png`. A physical photograph has not been added pending publication timing and usage rights.

Reported physical modules are 330 × 330 mm. The code uses a 325 mm panel variable, drawing coordinates of 5–330 mm, and 330 mm origin spacing. These are distinct measurements.

## Historical Sources

The historical script writes files and G-code at the top level. Do not import it into the shared engine. Negative X/Z values, motion rates, dipping, and washing settings belong to the original machine. Keep new experiments separate.
