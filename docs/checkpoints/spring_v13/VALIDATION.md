# Spring v13 checkpoint validation

Executed locally with Python 3.12.14 and the pinned review requirements. No
GitHub CI or physical validation is claimed. Compressed byte identity is tested
in this environment; compression headers may differ in other Python/zlib
versions without changing JSON numbers. Use the pinned runtime for byte hashes.

| Check | Result |
| --- | --- |
| Rich snapshot and approval PNG | Exact approved recovered file hashes |
| Historical original visual identity | User-verified exact 1200x1800 RGBA equality with image(20261019-044435).png |
| Lost historical vector identity | Unproven; no original v13 source claim |
| Ink / color paths | 3,345 / 11,606; 14,951 total |
| XY vertices | 240,974, all preserved exactly |
| IDs / geometry | Unique, finite, positive path length, within continuous 600x900 mm |
| Slots / layers / direction / order | Exact source assignments; INK or permitted A1-D5; no reversal/reordering |
| Original normalized pressure | 675 color paths / 8,975 points retained exactly |
| Missing original normalized pressure | 14,276 paths / 231,999 points explicitly marked; offline-only 0.5 placeholder |
| Repeated machine export | Identical JSON bytes and gzip metadata; no implicit Backend default |
| Recorded scene replay | Both approved rich vector gzip files byte-identical |
| PR23 loader and scheduler | 14,951 loaded, identical ordered IDs |
| Export-derived combined PNG | Exact RGBA equality with approved snapshot, zero differing pixels |
| SVG previews | Ink/color/combined profile-aware SVGs parse and retain native 600x900 mm size |
| Focused tests | 10 passed |
| Executable G-code / YAML changes | None |

Actual per-artifact hashes are in `artworks/spring_v13/MANIFEST_SHA256.json`.
The machine/source verification, pinned Backend module checksums and pixel
comparison are in validation.json. The source replay seed remains 2026101913.
Earlier independent recovery generation produced 21 byte-identical outputs;
its original result remains under source/recovery_validation.json.

Two positive-length sub-mm polylines and 4,572 expressive-width color records
remain present and flagged. No unsupported single-point/zero-length primitive
occurs. Full brush width, wet media, dwell and calibrated pressure are outside
the v0.1 contract; they are not silently approximated as calibrated execution.

Runtime/config source files copied from the recovered Work retain original
bytes. All 893 files inherited from PR #22 remain unchanged. Historical local
source SHAs are provenance, not promised remotely fetchable starting points.
Use the published checkpoint branch/commit supplied in the PR and final handoff.
