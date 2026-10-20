# Reproduce offline Backend v0.2

Python 3.10+ standard library; no plotting dependencies are required for pipeline
or HTML/SVG assets. Linux `resource` reports process RSS in the recorded run.
Use three separate checkouts. Commands below run from their indicated root and
write only new offline destinations. Never copy old YAML onto the controller.

## 1. Prepare source checkouts

```sh
git worktree add --detach /absolute/Pressure d30ac7be302e1cbfcd2cf66de9087e35ea091b6c
git worktree add --detach /absolute/Spring 67ba146b1213644d40bc9dabed9d52024d2bbe58
# Backend is this PR's branch, descended directly from PR23's pinned head.
```

The pressure checkout includes the frozen PR24 files, but a separate Spring
checkout makes inspection and immutability checks straightforward. Do not merge.

## 2. Use PR25's existing binding adapter

From `/absolute/Pressure`:

```sh
PYTHONPATH=src python -m datascape.spring_pressure_intent \
  --output /absolute/offline/spring_v13.pressure_v01.machine.json \
  --provenance /absolute/offline/spring_v13.pressure_v01.provenance.json \
  --backend-directory /absolute/Backend/src/datascape/gcode
```

Both JSON outputs must be fresh. The adapter validates canonical source hashes,
all original records and all accepted samples before writing. It checks the
actual Backend loader/scheduler without generating motion. No fallback is allowed.
`binding.bind_with_accepted_adapter(...)` is an optional Python wrapper around
this same command, not a second adapter.

## 3. Small deterministic development checks

From `/absolute/Backend`:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_gcode*.py' -v
PYTHONPATH=src python -m datascape.gcode.offline \
  --machine /absolute/offline/spring_v13.pressure_v01.machine.json \
  --provenance /absolute/offline/spring_v13.pressure_v01.provenance.json \
  --output /absolute/offline/subset-new --limit 32 \
  --synthetic-z-preview --compare-layouts
```

The full pinned test is explicitly skipped unless bound paths are set. Synthetic
geometry tests cover exact seam paths, crossing direction, disconnected returns,
sub-nanometer positive intervals, nonlinear pressure interpolation, layout gaps,
rotated/offset registration, constant/unresolved/variable depth, entry/release,
station sequence/reload/refill/restart, comment-only output and blocked Levels 2/3.

## 4. Full verification and output

```sh
PYTHONPATH=src \
DATASCAPE_BOUND_MACHINE=/absolute/offline/spring_v13.pressure_v01.machine.json \
DATASCAPE_BOUND_PROVENANCE=/absolute/offline/spring_v13.pressure_v01.provenance.json \
python -m unittest discover -s tests -p 'test_gcode*.py' -v

PYTHONPATH=src python -m datascape.gcode.offline \
  --machine /absolute/offline/spring_v13.pressure_v01.machine.json \
  --provenance /absolute/offline/spring_v13.pressure_v01.provenance.json \
  --output /absolute/offline/full-new \
  --synthetic-z-preview --compare-layouts
```

The selected layout writes every fragment/event/provenance and a manifest. Other
layouts in the comparison are fully processed/validated for statistics, without
duplicating large stream files. Use `--layout B`, `--layout C --gap-mm 50` or
`--layout D` with a new destination to emit a different physical layout's streams.

Omit `--synthetic-z-preview` to leave drawing Z unresolved. Use
`--constant-z-preview=-0.2` for an explicitly invented constant-depth
interpretation, not a hardware command. Use `--calibration-profile /path/profile.json`
for a future brush profile matching `BrushCalibration` fields; domains must cover
all supplied artistic pressure. Unsupported pressures fail instead of clipping
or extrapolating. Measured status requires observations, a date and surface height;
no profile enables machine output or validates compatibility automatically.

Registration can be externalized with `--layout-config /path/layout.json`:

```json
{"mode":"C","gap_mm":50,"registrations":[
  {"panel":"P1","x_mm":0,"y_mm":0,"rotation_deg":0},
  {"panel":"P2","x_mm":350,"y_mm":0,"rotation_deg":0}
]}
```

These numbers are a mathematical example, not measured placement. Explicit
registrations override the automatic gap placement for those panels. Python APIs
also accept `Layout`, `Registration`, `MotionSettings`, `BrushCalibration` and
`EstimateAssumptions` for reusable measured input. No final machine starting X is
invented. `WorkToMachine` requires an explicitly verified offset and is not used
to produce a Spring machine trajectory in this Work.

Output groups:

- `summary.json` and `MANIFEST_SHA256.json`.
- `layout_A/result.json`, `setup_order.jsonl.gz`, `station_operations.jsonl.gz`.
- Four `P{1,2}_{ink,color}.{events.jsonl,fragments.jsonl,preview.gcode.txt}.gz`
  streams and four `.work.svg.gz` files.
- `layout_A/spring_3d_review.html` with actual representative fragments/events.
- `calibration/` benchmark JSON/SVG, 3D review, commented preview and recording/
  station templates. All feed/depth/loading examples require physical testing.

Gzip streams use empty embedded filenames and mtime=0. Geometry, events and
statistics are deterministic given identical inputs/settings; runtime/RSS fields
and manifests containing those runtime reports naturally vary. Large derived
streams are regenerated rather than committed. The compact final report and
representative assets are preserved under `docs/plotter_backend_v02/review/`.

Read back and audit every actual compressed export:

```sh
PYTHONPATH=src python -m datascape.gcode.validation \
  --output /absolute/offline/full-new \
  --machine /absolute/offline/spring_v13.pressure_v01.machine.json \
  --provenance /absolute/offline/spring_v13.pressure_v01.provenance.json
```

This validates output hashes, every event sample against its original source
segment, fragment/order-manifest coverage, absence of physical trajectories and
all preview lines being comments. It targets the current uncalibrated full run.

## 5. Check source immutability

Run `git diff --exit-code` in both read-only source checkouts. The accepted adapter
also verifies every frozen manifest entry. The new Backend diff must include no
`artworks/` or `hardware/` modifications. The new Draft targets PR23's branch.
No existing Draft is merged, rewritten, closed or force-pushed.
