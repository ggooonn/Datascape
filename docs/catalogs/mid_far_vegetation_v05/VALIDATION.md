# Consolidation validation

Final complete suite:

```bash
PYTHONPATH=src python -m pytest -q
```

**311 passed, 22 subtests passed in 178.13 seconds.** This includes inherited
terrain/data/vector, accepted Tree v10, Rock & Ground v05, Spring/checkpoint,
mid/far v01-v05 behavior and five new closure-policy cases. The policy tests
keep R/S/U as default, reject middle B, refuse unimplemented linked far B and
check read-only selection. Earlier behavior tests retain their bodies; only
review-helper imports are redirected to the extracted support module.

## Exact replay

- Six middle/far R/S/U cases reproduce **all raw and visible ink/color records**
  exactly from preserved v04, including IDs, geometry, palette, source-arc and
  source-q/width/opacity profiles. This is not just a pixel or count comparison.
- Explicit historical reproduction of v05 A/B/C matches every original record.
  Far-only micro evidence exactly matches the F subset of the preserved micro
  layer: 403 experimental point contacts and 47 compact continuous paths.
- Default replay repeated with identical bytes in all nine output files:
  six SVGs, primary vector archive, far-micro evidence archive and replay record.
- `reference_vectors.json` records case digests and inherited evidence hashes.
  `regeneration_check.json` records executed comparisons and consolidation scope.
- All six retained SVGs parse and keep native artwork millimeters. All nine
  selected PNGs decode and match their source archive hashes. Existing review
  images are copied, not artistically refined. SVGs use recorded mean display
  widths; full vector profiles survive in the replayed JSON and do not imply
  calibrated pressure or brush behavior.

## Conservation and boundaries

- All **850 inherited files/modes** from the #21 head remain unchanged.
- All five original grammar runtime modules remain byte-identical to the
  preserved study. The small review helpers are extracted without body changes.
- The support fixture retains only the exact A/C clustered records used by the
  replays. Unused control/territory lists remain in the preserved original
  archive. Original and retained-subset hashes are recorded separately.
- Nine selected v01-v05 evidence PNGs, six native SVGs, five historical configs,
  one recommended integration policy and six relevant test files are retained.
- Six obsolete whole-study renderers, historical full vector/support exports,
  repeated panels, source paintings, caches and HTML/PDF/ZIP/bundle duplicates
  are excluded. Original local branches and complete private reviews remain.
- Markdown relative links, Python/JSON parsing and staged whitespace checks are
  checked before publication. Publication additionally verifies all uploaded
  blob SHAs, the complete root tree and the new PR's base/head/draft state.

The exact API/local commit mapping is reported in the Draft PR; commit metadata
may change SHA while the complete root tree stays identical. Existing PR heads
are checked again after publication. No parent branch is changed or merged.

## Limits

No full Spring scene regeneration, original-TIFF/full-precision terrain rebuild,
new scene integration, machine configuration, material calibration or G-code.
Geometry replay does not resolve pictorial forest continuity, depth rhythm,
Spring color or linked B ink/color. Read `DECISIONS.md` and the integration
handoff; B remains an optional far-only candidate and A/C remain deferred.
