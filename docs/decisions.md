# Decisions

## 2026-10-14 — Repository Structure

- Starting main commit: `4e27f59805a79b3147f287f9d503adbf9bda7d14`.
- Adopted the `data/` package namespace, `tool_coordinates.yaml`, `configs/rendering/`, and three experiment notebook names selected by the owner.
- Replaced the root README with a minimal introduction; the previous version remains in Git history.
- Used the supplied Geumgang rendering (`output.png`) as the temporary cover.
- Preserved the bytes of the initial Python/GEE files and uploaded historical notebooks. Code-cell extractions are review copies identified in their manifests, not replacements for notebooks.
- Archived three completed works independently. Links between original datasets and final production files still need confirmation.
- Added package scaffolding; shared algorithms and production G-code remain future work.
- Preserved FluidNC values and recorded the validation status of examples, tool coordinates, and substrate colors.
- Keep raw GeoTIFFs, bulk G-code, caches, and device secrets outside tracked files.
- Review changes through branches and PRs; the owner decides when to merge.

## 2026-10-14 — PR #1 Merged

- PR #1 merged at 2026-10-13 20:03:38 UTC; main commit: `832d7b5639598d0ca1bdf7d51e50ec4c3f85ffaa`.
- The Taebaek (Yang) notebook was excluded from the remote commit because of the connector request limit. Its code extraction and checksum manifest are present. This does not establish that a recoverable local notebook is currently available.

## 2026-10-14 — Public Documentation in English

- Use concise English for maintained public text, new code comments/docstrings, commits, and PR descriptions.
- Keep historical sources and preserved hardware configurations unchanged.
- Keep the root README minimal and put detailed records in the existing documentation folders.
- Separate language maintenance from algorithm development. See the [development guide](project.md#public-language-policy).
