# Datascape Buildings 01

## Result

The pilot covers 126.930°E to 127.085°E and 37.555°N to 37.684°N. The terrain retains the project’s Seoul North bounds from 126.82°E to 127.12°E and 37.50°N to 37.71°N. The building input is **Overture Maps 2026-11-18.0**. Three new viewing axes use the Spring P3 mapping.

| Candidate | Target longitude, latitude | UTM grid bearing | Near visible | Middle visible | Finding |
| --- | --- | ---: | ---: | ---: | --- |
| **A · Hongje to Inwangsan** | 126.955, 37.582 | 123° | **111** | **299** | Selected. An open ridge foreground, an apartment band and smaller buildings along the urban edge read together. |
| B · Jeongneung to Bukhansan | 127.005, 37.610 | 324° | 576 | 25 | A compact near-field apartment mass sits below dominant mountain terrain. |
| C · Suyu to Bukhansan | 127.017, 37.644 | 290° | 263 | 0 | The strongest mountain profile, with buildings confined mostly to the lower edge. |

Counts use the native height field and require at least one owned pixel in the final raster. In A's middle ground, visible records include 29 commercial, three house, two detached and 147 apartments records. The near field has 111 apartments records. The views are virtual. The extract and terrain have different bounds, and open areas beyond the building extract have unknown building coverage.

## Data audit

| Evidence | Buildings | Parts |
| --- | ---: | ---: |
| Spatially intersecting valid footprints or roofprints | 125,428 | 599 |
| Native class populated | 20,313 (16.19%) | No class field |
| Native subtype populated | 21,263 (16.95%) | No subtype field |
| Positive native height | 6,950 (5.54%) | 254 (42.40%) |
| Positive floor count | 9,376 (7.47%) | 181 (30.22%) |
| Any roof attribute | 529 (0.42%) | 127 (21.20%) |
| Multipolygons | 98 | 7 |

The inclusive STAC and feature bbox filter returned 125,446 buildings and 599 parts. Exact polygon intersection discarded 18 bbox-only building hits. The acquired records had zero invalid polygon hits and zero repeated IDs. The building-to-building audit found 845 intersections larger than 0.01 m², four near-duplicate candidates at IoU ≥ 0.90, and zero topologically equal pairs. All candidates retain their original IDs and geometry. All 599 parts link to 143 parents in the extract. Seventeen parts extend outside their parent by more than both 0.5 m² and 1% of part area. Same-parent pairs include 848 positive-area overlaps in plan and 504 with positive overlap between modeled vertical intervals where both heights are present. The interval audit uses bottom = min_height and top = bottom + height, with zero as the assumed bottom for absent min_height. A floor-only start is ineligible for extrusion.

Native categories include apartments (7,113), house (3,902), detached (45), residential (2,046), commercial (3,513) and retail (337). A house stays a source house record. Korean detached-house, neighborhood commercial or mixed-use categories need additional evidence. The v2.0.0 class vocabulary has no explicit mixed-use value. Original fields, source records and nulls are preserved.

Of these buildings, 49,313 cite OpenStreetMap and 76,115 cite the East Asian footprints dataset at DOI 10.5281/zenodo.8174931. Every positive height and floor count is on a record citing OpenStreetMap in this extraction. The provenance arrays do not report separate field-level contributing records in this sample. Height coverage is 5,191/7,113 for apartments, 16/3,902 for house, 2/45 for detached, 143/3,513 for commercial and 7/337 for retail. Open spaces in the mass view can be either geography or missing height coverage. Read the mass view with the plan.

Footprint area p05/p50/p95 is 21.16 / 72.59 / 629.64 m². Elongation p05/p50/p95 is 1.00 / 1.37 / 3.14. The alignment rule identifies 4,050 pairs of similarly oriented elongated apartments records. Of 97,576 footprints from 20 to 180 m², 82,401 have five or more other footprints of the same size range within 35 m. This measures plan density. Ownership, complex membership and use require separate evidence.

See [building schema](https://docs.overturemaps.org/schema/reference/buildings/building/), [class vocabulary](https://docs.overturemaps.org/schema/reference/buildings/types/building_class/), [part schema](https://docs.overturemaps.org/schema/reference/buildings/building_part/) and the [pinned STAC index](https://stac.overturemaps.org/2026-11-18.0/collections.parquet). The optional Microsoft comparison was outside the run.

## 2.5D geometry and vertical uncertainty

The exact native outline can represent a ground footprint or a roofprint. The pilot has no paired ground geometry to resolve which. The extrusion uses the captured plan directly. It preserves IDs, polygon holes and all multipolygon components, and generates vertical faces and a triangulated flat top. Elevated parts share the parent ground datum. The source outlines and attributes remain available.

The main view uses **6,950 source-height masses**. The ochre diagnostic adds the 3,022 floor-only inputs under an explicit 3 m/floor estimate. A shows 203 of these. The remaining 115,456 buildings lack both native height and usable floor evidence. The metric outlines and independent ground samples join by Overture ID. The prism function reproduces the vertical walls and top surfaces.

FABDEM v1.2 provides a 30 m bare-earth proxy for non-commercial research. A single base samples its surface at an interior point. The vertical datum is EGM2008. Raw Copernicus DSM minus DTM ground is +3.64 m at median (p05 +0.66, p95 +9.80). Adding reported building height to the raw DSM would risk counting surface height twice. A local plane fitted to footprint-free DSM cells had enough enclosing support for 7,510 contacts. Its median difference from FABDEM was +3.70 m (p05 +0.88, p95 +8.59). The sample neighborhoods can include trees and unrecorded buildings. There are 1,060 height-bearing outlines with more than 5 m of DTM relief across footprint vertices. Contact position and slope remain uncertain at building scale.

## Projection and visibility

The source extract retains WGS84 geometry. Local processing uses configurable EPSG:32652. The 30 m terrain shares its metric frame with the buildings. The existing ProductionMapping maps both to P3 coordinates and virtual depth with new view anchors. Final diagnostic sheets use 440 × 300 mm proportions. Source-depth thirds and projected-pixel size gate depiction. Middle-distance outlines simplify at 1.2 m with topology preserved. A comparison enables the normally omitted far building layer. Terrain contrast fades by source depth while its visibility buffer remains intact.

A has 410 visible buildings in the strict pass. Building surfaces cover 166,867 previously visible terrain pixels, including 19,078 pixels in the diagnostic 25 m contour bands. Against each object's isolated raster surface, terrain blocks 8,269 object-pixels and nearer buildings block 103,839. Four objects are fully hidden by terrain alone. Object-pixel totals can count different objects at the same pixel. The default pass omits 586 projected far candidates. With the far layer enabled, they own 201,114 final pixels.

The part comparison isolates parent e6cc5d5d-8f9e-4e07-a8f9-67d13baf3865 at 126.983627°E, 37.570729°N. Its six height-bearing parts have nine plan overlaps and 47,728 object-pixels blocked by nearer parts. For the overview, parent envelopes represent buildings. In the isolated comparison the parts take the place of that parent. The shared raster provides display visibility. Overlapping, missing or tied vertical part intervals need interpretation before a physical solid union.

## Repository recovery and dependencies

| Reference | Inspected head | Reuse or decision |
| --- | --- | --- |
| [Main](https://github.com/ggooonn/Datascape/tree/e4934547f5b901a2fc736baf876cddc9c3af6be7) | e4934547f5b901a2fc736baf876cddc9c3af6be7 | Finite masks and checksums, TerrainGrid, real terrain mesh, Spring P3 controls and mapped-depth rasterizer. |
| [PR 18](https://github.com/ggooonn/Datascape/pull/18) | f858e7816822c539944c8244677c29a7dd39fc0a | Local-millimeter tree placement and near-scale rules. |
| [PR 19](https://github.com/ggooonn/Datascape/pull/19) | 6fcac2864e7b7fdd5ae626f8a8161c01e5c90994 | Rock faces, face-local paths and occlusion precedent. |
| [PR 22](https://github.com/ggooonn/Datascape/pull/22) | 1c798a7fd8becdf530b338260447e20e36f6b31d | Middle/far vegetation handoff and optional far-only micro treatment. |
| [PR 24](https://github.com/ggooonn/Datascape/pull/24) | 67ba146b1213644d40bc9dabed9d52024d2bbe58 | Artwork coordinates, vector identity and lineage reference. Compressed F2 fields belong to the locked scene. |
| [PR 46](https://github.com/ggooonn/Datascape/pull/46) | 3ca625eda63e2f22a760c9980abba3845be37fb3 | Independent v08 catalog, including outlines, contact clipping, seeded variants and INK/COLOR provenance. |

All five PRs were open drafts and unmerged when inspected. The verified SeoulNorth_v02_MASTER_30m.tif and SeoulNorth_v02_VEG_10m.tif were unavailable in the inspected refs, workspace and file search. See the [GEE exporter](../../../gee/seoul_north_v02.js) and [dataset manifest](../../datasets/seoul_north_v02.json). The terrain tiles and checksums used here are recorded in the results. Spring supplies the mapping settings. The native 2022–2025 Spring NDVI composite and metric-anchored vegetation/rock occlusion remain open dependencies.

In v08, catalog.geometry.Stroke records a path in millimeters and an owner. rock_overlap_v05.projected_mask and color_v03.project_clip operate on outlines in that same artwork plane. ground_enrichment_v08.enrich retains contacts and clips against solid footprints. The exemplar coordinates supply neither a projected metric origin for the pilot nor mapped depth per sample. See the [Work 02 handoff](WORK_02.md) for a proposed common adapter.

## Reproduce

Run from the repository root with Python 3.12. Inputs and rendered outputs live outside the source tree. The accompanying requirements file pins the versions used.

```sh
python -m pip install -r docs/experiments/buildings_work01/requirements.txt pytest
config=docs/experiments/buildings_work01/seoul_north.json
inputs=../buildings-inputs
out=../buildings-review
mkdir -p "$inputs"
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1
python -m datascape.buildings.acquire "$config" "$inputs/overture"
for longitude in 126 127; do
  tile="Copernicus_DSM_COG_10_N37_00_E${longitude}_00_DEM"
  curl -fL "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/$tile/$tile.tif" \
    -o "$inputs/$tile.tif"
  tile="N37E${longitude}_FABDEM_V1-2"
  curl -fL "https://huggingface.co/buckets/links-ads/fabdem/resolve/tiles/N30E120-N40E130_FABDEM_V1-2/$tile.tif" \
    -o "$inputs/$tile.tif"
done
python -m datascape.buildings.study "$config" \
  --extract "$inputs/overture" --dsm "$inputs"/Copernicus*.tif \
  --dtm "$inputs"/*FABDEM*.tif --output "$out"
python -m pytest -q
```

The research package includes raster comparisons, an SVG source plan, an SVG part diagnostic, per-view visibility tables, input checksums and the geometry and elevation layers. See [validation](validation.json) for measured checks.

## Sources and rights

The building extraction and derived footprint and height table use ODbL 1.0. Credits include © OpenStreetMap contributors and Qian Shi et al., East Asian Building Footprints, [DOI 10.5281/zenodo.8174931](https://doi.org/10.5281/zenodo.8174931). Public use of derivative databases or produced works from them can trigger access and share-alike terms in sections 4.3–4.6. Preserve the attribution and access to the applicable source or alteration method if using the building data for public artwork. See [Overture attribution](https://docs.overturemaps.org/attribution/) and [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).

Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. The FABDEM v1.2 ground, plots and terrain-based diagnostics are for non-commercial research. Resolve separate commercial permission or use a suitable commercially usable DTM before carrying these elevations into a saleable artwork. See [Copernicus terms](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) and [FABDEM v1.2](https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/).
