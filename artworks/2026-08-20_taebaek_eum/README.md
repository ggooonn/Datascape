# Taebaek (Eum)

- Physical work completed: 2026-08-20 (reported by the owner).
- Code label: V31.
- Code layout: 8 columns × 6 rows (48 panels).
- Marks: vertical strokes, two silver passes, three gold passes, and an optional normal map.

## Files

- [Original notebook](original/datascape_0820_Taebaek.ipynb): original bytes and saved outputs.
- [Code-cell extraction](original/source.py): an unchanged extraction for review, not a replacement for the notebook.
- [Source manifest and checksums](source_manifest.json).

Inputs: `Taebaek_DEM.tif` and optional `Taebaek_Normal.png`. The normal-map generation method remains unconfirmed.

The mapping between original datasets and final production files, physical materials, hardware conditions, and dependency versions still needs documentation. Saved notebook outputs are historical execution records, not proof of a current successful reproduction.

Code layout: 330 × 330 mm panels, 20 mm horizontal gaps, and 10 mm vertical gaps; total 2780 × 2030 mm.

## Historical Sources

The historical script writes files and G-code at the top level. Do not import it into the shared engine. Negative X/Z values, motion rates, dipping, and washing settings belong to the original machine. Keep new experiments separate.
