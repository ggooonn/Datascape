# Spring v13 Pressure Intent v01 checkpoint

The user provisionally accepted this complete dataset as the artistic pressure-intent baseline for **offline Plotter Backend development**. No coefficients, pressure samples, family ranges, or pictorial rules were adjusted during checkpoint preparation. All 14,951 strokes / 240,974 values are newly computed, including the 675 historical experiments. No profile may fall back to those experiments or to the old offline 0.5 placeholder.

This is stacked on PR #24's head `checkpoint/spring-v13-interim-v01`, pinned at `67ba146b1213644d40bc9dabed9d52024d2bbe58`. PR #24's frozen files and PR #23's independent Backend branch are unchanged. No merge is authorized. The recovered approved PNG's visual identity was independently verified by the user; identity with the lost historical v13 vector source remains unproven.

## Canonical files

- `artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz`: accepted ID-linked pressure sidecar. Contains no replacement XY or width geometry.
- `artworks/spring_v13_pressure_intent_v01/acceptance.json`: acceptance, counts and hash bindings. The sidecar's generation-time candidate status and the config's provisional wording are intentionally preserved byte-for-byte; this record documents subsequent acceptance.
- `studies/spring_pressure_full_v01/engine.py`, `config.json`, `full_pressure.py`: accepted painterly rules, coefficients and deterministic full generator. `reference_samples.json.gz` supports optional matched diagnostic regeneration, not pressure generation.
- `src/datascape/spring_pressure_intent.py`: strict source/sidecar validation and offline all-profile adapter (standard library only).
- `tests/test_spring_pressure_intent.py`: real-data positive and corruption/mutation tests. Existing `studies/spring_pressure_full_v01/test_bindings.py` retains the study's original binder tests.
- Compact family distributions, context audit, estimated D cohorts, historical comparison summary and saturation analysis are beside the sidecar. Large HTML, ZIP, images, per-vertex decomposition and redundant derived machine JSON are intentionally not committed; they are reproducible and the reviewed diagnostic package is preserved separately.

SHA-256 of the accepted gzip bytes:

```
0b8d59b7ca9268c70378b7a78df3f8825763b2b43e5667785459b2838d2b0b4e
```

Canonical JSON payload hash (sorted keys, compact separators, no trailing newline): `55b1f933e66a8a2e3bac2a6b143766b0739ae41d6e1fac4d780023920eb44b5d`.

## Pressure semantics

Values are normalized artistic intent, **not** measured force, calibrated pigment density, physical stroke width, or Z. Width contributes bounded relative within-stroke variation; it is never min-max mapped to 0–1. Historical pressure and display alpha are not model inputs. D uses source-world terrain estimates and depth-gated support cohorts; foliage crowding reduces individual pressure. The numerical range is 0.22–0.93; no stroke is forced to 0 or 1.

The original v13 preview remains independent of pressure diagnostics. There is no artistic scene regeneration, coordinate transformation, panel split, 40 mm gap, physical mapping, washing/dipping routine, or G-code in this checkpoint.

See [reproduction and validation](REPRODUCE.md), [known limitations](KNOWN_LIMITATIONS.md), and the [exact Backend start procedure](PLOTTER_BACKEND_HANDOFF.md).
