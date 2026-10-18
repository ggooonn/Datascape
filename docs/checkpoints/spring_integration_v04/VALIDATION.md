# Checkpoint validation

This preservation step does not change artistic generation. Recorded checks:

- Applied the preserved v04 source patch to PR #20 commit
  `f3a11745217a6ab976ac90819d5538462dae346b`; all original implementation hashes
  match the archived v04 manifest. The old local-only source commit is preserved
  as provenance, not advertised as remotely fetchable.
- **All 782 inherited repository files remain byte-identical**, covering the
  PR #16 baseline, Tree v10, Rock & Ground v05, source camera/mist logic,
  palette, hardware configuration and historical experiments. This PR adds files
  only. No old experiment or accepted source is deleted or rewritten.
- Replayed the saved v04 open-vector primitives with the pinned review packages.
  Recreated C integrated diagnostic and color-only diagnostic pixels match
  their archived originals exactly. `replay_validation.json` records results.
  Composite ordering/counts: terrain 2,309; B 3,650; C 3,094. Ink 3,067 paths.
- Ran the focused checkpoint/integration/catalog suite: **58 passed, 16 subtests
  passed in 73.72 seconds**. The added checkpoint check validates current-owner
  inventory, original-V absence, composite counts, fixed-source hashes and
  exact source-arc geometry against saved canonical/catalog sources.
- Identified all 119 temporary authored object sites: 79 trees, 22 rocks and
  18 Soil supports. Every saved v04 object owner resolves to this inventory;
  other owners are canonical A/B/D. Legacy canonical V is absent in this exact
  saved scene. This does not close the artistic temporary-placement audit.
- All retained PNGs fully decode; gzip archives fully decompress and parse as
  JSON. The original artifact bytes are preserved, including CSV CRLF endings.
  Public reference-map crop contains only the original nonplotting scene map;
  private reference thumbnails and originals remain outside the PR.
- Original v04 generation evidence is retained unchanged: source-field/palette
  hashes, source-arc conservation, sampled solid-body/absolute-omission/root
  checks, and paired-trunk footprint checks. **Full TIFF/F2 geometry regeneration
  was not rerun in this checkpoint step.** Replay uses saved decisions and does
  not independently recertify those original source-field calculations.

The v04 findings remain unapproved. Pixel identity, deterministic clipping and
zero recorded intrusions are not artistic acceptance, volumetric occlusion
certification, calibrated brush pressure, pigment dilution or production readiness.
