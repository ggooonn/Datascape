# Reproduction and validation

Run from the pressure checkpoint repository root, with frozen Spring v13 files inherited from `67ba146b1213644d40bc9dabed9d52024d2bbe58`. The generator accepts that commit or a descendant, but verifies every baseline manifest entry before and after generation. No source vectors are regenerated or edited.

## Standard-library binding checks

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_spring_pressure_intent.py' -v
# Frozen-baseline regression tests additionally require pytest==8.3.5:
PYTHONPATH=src python -m pytest tests/test_spring_v13_checkpoint_export.py -q
PYTHONPATH=src python -O -m datascape.spring_pressure_intent
```

The adapter's critical checks use explicit exceptions and remain enabled under `python -O`. The study generator and its legacy binder use assertions and must run without optimization.

## Byte-for-byte full regeneration

Use Python **3.12.14** and the exact versions in `studies/spring_pressure_full_v01/requirements.txt` (numpy 2.3.5, scipy 1.17.0, matplotlib 3.10.8, Pillow 12.3.0). Install in a separate environment. Use fresh output directories; neither command overwrites source or the accepted sidecar:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/spring_pressure_full_v01/full_pressure.py generate --output /absolute/repro-a
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/spring_pressure_full_v01/full_pressure.py generate --output /absolute/repro-b
cmp artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz /absolute/repro-a/spring_v13.pressure_intent_v01.json.gz
cmp /absolute/repro-a/spring_v13.pressure_intent_v01.json.gz /absolute/repro-b/spring_v13.pressure_intent_v01.json.gz
sha256sum /absolute/repro-a/spring_v13.pressure_intent_v01.json.gz
```

Expected SHA-256: `0b8d59b7ca9268c70378b7a78df3f8825763b2b43e5667785459b2838d2b0b4e`. Deterministic gzip uses mtime=0. Pinned interpreter/library versions matter for exact compressed bytes and numerical reproduction. The committed acceptance manifest binds the original config bytes; do not rewrite config formatting or the generation-time status to record acceptance.

Generation also reproduces per-vertex modifier decomposition, family statistics, historical comparisons, context audit and source-preservation validation. All 675 counterfactual tests remove historical pressure from the input record and verify identical newly calculated values. Optional diagnostic review (large outputs remain local):

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/spring_pressure_full_v01/full_pressure.py review --output /absolute/repro-a --reproduction /absolute/repro-b
python studies/spring_pressure_full_v01/test_bindings.py --snapshot artworks/spring_v13 --pressure /absolute/repro-a/spring_v13.pressure_intent_v01.json.gz
```

## Executed checkpoint checks

The compact `artworks/spring_v13_pressure_intent_v01/checkpoint_validation.json` records actual executed results. Validation covers:

- 14,951 unique profiles and 240,974 finite normalized values, exact family ranges and canonical sidecar hash.
- Every rich source record, XY and vertex order, width/expression hash, medium/slot, layer, order group, sequence and direction lock.
- Complete replacement of 14,276 placeholder profiles / 231,999 values and 675 experimental profiles / 8,975 values. No fallback or missing pressure is accepted.
- New in-memory allocation and equality of all nonpressure machine fields; frozen source files remain exact.
- Mutation rejection for missing/duplicate/reordered IDs, vertex counts, source/width hashes, changed XY, wrong ordering/material/provenance, missing/invalid pressure, NaN and bool values; file checksum corruption is rejected before binding.
- The actual PR #23 loader/models/scheduler are exercised read-only, with all 240,974 loaded pressures compared to the canonical sidecar. No Backend CLI, physical mapping or G-code generation is invoked.

The only generator packaging change is accepting a Git descendant of the pinned baseline instead of requiring HEAD itself to equal the pin. The artistic engine, config and accepted sidecar bytes remain identical to the reviewed implementation. The legacy study binder is preserved; the new offline adapter adds fail-closed file checks without changing pressure calculations.
