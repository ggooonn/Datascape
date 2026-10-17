# Consolidation validation and inventory

All results below were executed in this consolidation Work, after extracting the
standalone renderer and adding the native-mm configuration. No F2 scene was run.

## Executed checks

- `PYTHONPATH=src python -m pytest -q`: **233 passed, 16 subtests passed**, 179.87 s.
  Includes all 198 inherited scene/tree tests, 16 source/interaction tests, nine v05
  invariant tests, six patch-control cases and four consolidation/golden tests.
- Focused interaction/v05 run before the final two test files: **25 passed**, 6.31 s.
- Standalone catalog generation ran before and after config extraction. All 18 final
  states and 19 original source groups match the accepted v05 archive exactly,
  including IDs, geometry, profiles and material metadata. A second complete `build`
  matches sources, finals, audits, canonical fixtures and catalog data deterministically.
- Six native SVGs, six PNGs, 11 native specimen crops, compressed vector archive,
  audit JSON and support GeoJSON match the accepted output bytes. All record values
  match except the expected implementation-file hashes after renderer extraction.
- Four retained SVGs parse, have exact physical-mm dimensions and contain the 10 mm
  ruler; corresponding PNGs decode. All relative links in added catalog docs resolve.
- Nine accepted ground modules match their original SHA-256 hashes byte-for-byte.
  Every original Tree v10/spring/contract tree entry remains unchanged in the Git
  consolidation tree; only the added paths in this catalog are published.

Machine-readable evidence: [regeneration_check.json](regeneration_check.json),
[reference_manifest.json](reference_manifest.json), [scale_metrics.csv](scale_metrics.csv).
The original source goldens were computed from the preserved v05 archive, not from
this consolidation's generated results. Exact state signatures are asserted in tests.

## Published material

- Nine accepted ground runtime modules; original versioned filenames retained to
  avoid opaque renames and preserve source lineage.
- One final catalog renderer, two small fixture/plot adapters and one explicitly
  comparison-only v04 control module. No v01–v04 study runner is required or shipped.
- One catalog configuration, four relevant test files, concise catalog/decision/
  handoff/validation documents, input inventory, vector/runtime/archive signatures,
  regeneration evidence and physical metrics.
- Four complementary native SVG masters. No duplicated PNG/HTML/ZIP, full vector
  archive, patch chain, cache, reference painting or external GeoTIFF is published.

## Excluded but preserved

The original local v01–v05 branches and full research sources/docs remain intact.
Complete comparison outputs, both diagnostic supplements, 11 specimen crops, vector
and support archives, PNGs, Korean HTML reviews, source ZIPs and incremental patches
are preserved locally. The reference manifest records archive signatures; they are
not required at runtime and are not claimed to be GitHub release assets.
Discarded mound/default Soil, four-block large-mass and window-hatching experiments
are not restored as accepted generation defaults. A small old hatching control is
retained only to reproduce the selected matched review sheet.

## Limits carried forward

No GeoTIFF or authoritative float64 F2 ownership cache was available here. The
baseline gzip identity and its expected digest were obtained from the inherited Git
tree and pinned record; its binary bytes were not independently verified locally.
No full composition, terrain attachment, reciprocal masking, canopy-core artistic
acceptance, brush calibration or pigment behavior is claimed by these tests.

The isolated C0 polygon-clearance proposal is preserved as a non-default diagnostic.
The earlier source-arc endpoint precision issue remains open; the common consumer
and proposed OCC contract are not modified. The default retains prior C geometry.
