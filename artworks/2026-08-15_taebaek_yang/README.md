# Taebaek (Yang)

- Physical work completed: 2026-08-15 (reported by the owner).
- Code labels: output directory V203; preview/G-code V202.
- Code layout: 8 columns × 6 rows (48 panels).
- Marks: ink and ten pigment layers, horizontal curves, and macro-DEM color selection.

## Files

- Original notebook: `original/datascape_0815_Taebaek.ipynb` is **not present in this repository**. The 35,391,440-byte upload was deferred because of the connector request limit. Current local recoverability has not been verified.
- [Code-cell extraction](original/source.py): an unchanged extraction for review, not a replacement for the notebook.
- [Source manifest and checksums](source_manifest.json).

Inputs: `Taebaek_DEM.tif`, `Taebaek_Aspect.tif`, and `Taebaek_NDVI.tif`. Aspect and NDVI are loaded but not used in subsequent path generation.

The mapping between original datasets and final production files, physical materials, hardware conditions, and dependency versions still needs documentation. Saved notebook outputs are historical execution records, not proof of a current successful reproduction.

Code layout: 330 × 330 mm panels, 20 mm horizontal gaps, and 10 mm vertical gaps; total 2780 × 2030 mm.

## Historical Sources

The historical script writes files and G-code at the top level. Do not import it into the shared engine. Negative X/Z values, motion rates, dipping, and washing settings belong to the original machine. Keep new experiments separate.
