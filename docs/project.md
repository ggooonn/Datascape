# Datascape Development Guide

Datascape interprets terrain and environmental data through the strokes, texture marks, ink tones, and colors of Korean landscape painting, then makes physical paintings with a brush plotter. Seoul Four Seasons is the next work, not the shared system's only purpose.

## Development Environment

```bash
python -m pip install -e ".[research,dev]"
```

Select that Python environment as the notebook kernel in VSCode. Reusable functions belong in `src/datascape/`, experiments in `notebooks/`, and historical production sources in `artworks/`. The package namespaces are scaffolding, not a working terrain, rendering, or G-code engine. The dependency list is for current research, not a locked environment for past works.

## Shared Path Design — Not Yet Implemented

1. Validate GeoTIFFs while retaining geographic coordinates and masks.
2. Separate terrain from camera settings and artistic distortion.
3. Store vector strokes in millimeters with IDs, colors/materials, expressive intensity, order, seed, and whether reversing direction is allowed.
4. Compute panel boundary intersections and use the same finalized paths for previews and production.
5. Keep machine Z, coordinate transforms, washing, and dipping in a separate calibrated motion plan.

A shared seed does not guarantee the same drawing when preview and production densities differ. The final renderer and G-code backend should read the same finalized vector paths.

## First Improvements

- Replace silent zero-array loading failures and synthetic terrain fallbacks with explicit errors or separate demos.
- Distinguish NoData from valid negative values, and array-index gradients from slopes in physical units.
- Replace point-filter panel clipping with exact segment intersections.
- Distinguish loading NDVI/aspect from actually using them.
- Separate expressive pressure from machine Z; check interpolation bounds and record seeds and input checksums.

Apply these changes to new modules, not historical sources.

## Development Sequence

Data quality → monochrome terrain/viewpoint comparison → vegetation and texture strokes → color and substrates → calibration and small physical tests. Repository organization and artwork archiving were introduced in PR #1.

For each experiment, record the visual question, code version, inputs, settings, seed, comparison images, and reasons for keeping or rejecting a result. Scale from a small region to one seasonal pair, then all eight panels. Record measured validation results separately from planned capabilities.

## Public Language Policy

Write maintained public documentation, new notebook Markdown, comments, docstrings, commits, PR descriptions, issues, and development notes in concise, natural English. Keep the root README minimal: one image, a short introduction, and a small technology list.

Historical artwork sources, archived prototypes, and preserved machine configurations retain their original language and bytes. Add English summaries alongside them when needed. Preserve original titles where useful and keep existing paths stable. Do not rewrite licenses or copyright notices. Internal project context and conversations may remain in Korean.

Use separate branches and PRs for documentation and algorithm development. Merge into `main` only after the owner's review and decision.
