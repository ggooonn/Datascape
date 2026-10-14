# Selected spring composition C: baseline review

## GitHub state observed before stroke development

PR #6 was already merged at **2026-10-14 15:14:13 UTC / 2026-10-15 00:14:13 KST** when this work inspected GitHub. No merge was performed by this work.

- Main/merge commit: `e4934547f5b901a2fc736baf876cddc9c3af6be7`.
- Reviewed PR head: `659653320afeaf99ca3df47a487993a57f20bcfe`.
- The 241 file blobs on main match that PR head exactly.
- PR #6 changed 141 files, all additions. None is under original artwork sources, palette settings or hardware settings.
- GitHub reported no check runs and no commit status entries. This is not described as passing GitHub CI. Local baseline tests: 60 passed; expanded stroke tests: 68 passed.

## Reproducible selected baseline

The selected scene is the foreground-continuity **C**, 70% existing near retention +30% selective retention. The existing F2 scene and v0.1/v0.2/v0.3/v0.4 configs and results remain unchanged. Its final grayscale image reproduces pixel for pixel, and recomputed float64 retention quantizes exactly to the archived C array. The original F2 terrain-only image also reproduces exactly.

The new selection lock records SHA-256 values for both original TIFFs, the five configuration files, selected image/retention/run record, archived small and representative mark geometry, initial visible-XYZ archive, historical Taebaek source, palette and tool coordinates. Full-precision fields are recomputed; float16 archives are not treated as final stroke-sampling precision.

The new stroke work starts from this main commit on a separate branch/PR. No main or PR #6 ref update is needed or performed. All existing remote blobs are retained by a base-tree overlay; the 197 existing files present in the working copy are independently hash-checked before and after development. Large originals absent from that working copy are preserved by their remote blob identities.

The selected baseline is complete for this first stroke comparison. Hardware output still needs a calibrated backend and physical brush/paper tests; that is separate from composition reproducibility.
