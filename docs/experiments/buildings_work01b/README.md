# Datascape Buildings 01B

## Status

The official Korean height enrichment remains pending. VWorld, the Seoul title CSV and Building HUB did not return their original files in this environment. The acquired Seoul research release supplies Korean government-derived building outlines for a real spatial-match test. It does not supply attributable official height evidence at the building level. See [source access and rights](SOURCES.md).

Work 01 is the locked base at [Draft PR 47](https://github.com/ggooonn/Datascape/pull/47), commit `acd7d992493cea7b685cdd9678d16c37b0a69769`. The study verifies the original three view records, their two comparison plates and the registered ground samples against the checkpoint. It reproduces A0/H0 with exact per-object visibility and occlusion counts. Spring P3, 1,320 × 900 pixels, 440 × 300 mm, Overture 2026-11-18.0, UTM 52N and the original two FABDEM tiles remain the controlled references. The new implementation is additive. PR 46 is a pictorial reference and its catalog is unchanged.

## Acquisition and footprint matching

The work window spans 126.930 to 127.085°E and 37.555 to 37.684°N. The 601,066-row Seoul research GeoPackage yielded 215,814 valid intersecting polygons within that window. The two sources use different geometries and building inclusion policies. The resulting overlap is a regional-reference diagnostic.

| Geometry relationship | Overture records |
| --- | ---: |
| High-confidence reciprocal shape matches | 15,262 |
| Ambiguous | 88,756 |
| One to many | 6,756 |
| Many to one | 6,284 |
| Many to many | 640 |
| No qualifying candidate | 7,730 |
| Total | 125,428 |

A candidate needs ≥4 m² intersection and ≥20% of the smaller outline. An accepted candidate needs ≥0.65 IoU, ≥70% coverage of each outline, ≥0.15 IoU separation from a rival in either direction, and no competing overlap that covers at least 20% of the source side examined. Exact textual provider IDs survive ingestion. A duplicated regional ID blocks height uptake. The possible cases include merged apartment envelopes, separate wings, attached structures and unrelated changes between datasets. This step estimates shape correspondence. It cannot prove the same legal building identity. The median best candidate IoU is 0.456. Among accepted links it is 0.727. The study does not apply a geographic shift or a nearest-building fallback.

The Overture extract has no shared government building ID or PNU field. The research GeoPackage does not publish the government ID or address used by its authors. With an official integrated layer, preserve its property identifiers and confirm difficult links against building-level IDs, parcel/address and surveyed building area. A title-only CSV needs a spatial bridge. Do not use a parcel ID by itself to choose one of several structures on that parcel.

## Height and classification evidence

| Exact Overture class | Records | Positive native height | Native floors | Floor-derived additions | Unresolved height |
| --- | ---: | ---: | ---: | ---: | ---: |
| apartments | 7,113 | 5,191 | 6,558 | 1,373 | 549 |
| house | 3,902 | 16 | 61 | 46 | 3,840 |
| detached | 45 | 2 | 3 | 1 | 42 |
| commercial | 3,513 | 143 | 476 | 340 | 3,030 |
| retail | 337 | 7 | 81 | 74 | 256 |
| residential | 2,046 | 12 | 143 | 132 | 1,902 |
| all classes and blanks | 125,428 | 6,950 | 9,376 | 3,022 | 115,456 |

Native class or subtype is present on 21,263 records. Zero official height, floor or use fields were ingested, so their coverage gain and agreement are unmeasured. The use and native geometry of each Overture record remain intact. Research archetypes are recorded as a reference attribute and have no authority in H1 or H2.

H0 uses the native height field. With an official regional file, H1 uses a positive registry height after a high-confidence spatial match. For an existing native value with a difference greater than max(3 m, 20% of native height), both values and a conflict flag survive and the native height carries forward until review. Korean use stays in its native label and code even when a research group is used for review. H2 is an optional estimate only where neither H0 nor H1 supplies a height and a positive above-ground floor count is available. H3 denotes unresolved values. Underground and floor-only floating structures retain the base eligibility policy.

The provisional sensitivity ranges per floor are 2.6–3.4 m for small and other residential, 2.7–3.3 m for apartments, 3.0–3.8 m for neighborhood facilities, 3.0–4.0 m for commercial and 3.2–4.2 m for retail. The comparison uses the configured central value for each group. Every estimated record stores its lower and upper candidate. These are diagnostic assumptions. The run used native floors only. All newly eligible masses keep Overture outlines. DTM registration reuses the same terrain and sampling policy. The original DSM diagnostics are in the Work 01 checkpoint.

## Pictorial results

| Study | Visible | Floor estimates visible | Urban share of frame | Near visible width × height, median | Near surface-stroke size candidates |
| --- | ---: | ---: | ---: | ---: | ---: |
| A0/H0, 3,300 m | 410 | 0 | 14.0% | 4.7 × 10.3 mm | 28 |
| A0/H2, 3,300 m | 613 | 203 | 16.1% | 4.8 × 9.0 mm | 41 |
| A1, 2,200 m | 417 | 126 | 26.0% | 7.3 × 13.3 mm | 56 |
| A1, 1,650 m | 303 | 92 | 32.8% | 9.7 × 11.0 mm | 25 |
| A2, 820 m | 100 | 74 | 6.9% | 24.3 × 7.0 mm | 18 |

A0/H1 is held open in the aligned plate pending the official file. A0/H2 retains the exact A0 camera, anchors, terrain and raster. Native commercial visibility rises from 29 to 72 and house from 3 to 11 when native floors are introduced. Five retail records become visible. The building count rises by roughly half while the building area increases by only 2.1 percentage points. More small masses are depicted, and the sole near small-residential mass in A0/H2 is 2.0 × 2.3 mm and only silhouette-size. Both vertical-evidence availability and screen scale matter. The H2 test quantifies the effect from available native floor counts. It leaves the impact of complete registry data open.

A1 candidates uniformly crop the charted P3 projection in both axes, with the same map camera, depth anchors and physical buildings. The 2,200 m candidate keeps a readable open slope while doubling the count of near surface-size candidates versus A0/H0. The 1,650 m view gives buildings almost a third of the composition and truncates more terrain. A2 is a focused scale study near 126.9730°E, 37.5884°N. Its local DTM probe has 24.1 m relief across a 150 m cross. Of its 100 visible masses, 41 are classed commercial, 14 apartments, six house and two detached. Some of the small views read as partial profiles where the terrain covers the walls.

The thresholds at 440 × 300 mm are 1.2 × 1.0 mm for silhouette, 3 × 2 mm for occasional roof or primary divisions, and 6 × 4 mm projected visible wall extent for surface-stroke trials. Each record carries visible width, height, area, wall area and wall extent plus hidden percentages for terrain and other buildings. The wall extent is a bounding box over final wall pixels, which can span multiple disconnected pieces. It is a geometric upper bound on stroke space. Approximately 0.33 mm raster pixels, line width, bleeding and clear gaps constrain physical interpretation. Current review does not certify physical stroke spacing.

## Reproduce

Use the pinned [Work 01 installation and source recipe](../buildings_work01/README.md#reproduce). Preserve that output directory as the original checkpoint. Obtain the public reference from the [published Seoul GeoPackage link](https://zenodo.org/records/21881381/files/Seoul_residential_stock_EC_v4_5_8.gpkg?download=1) and keep it outside Git. The provider config pins the downloaded digest.

```sh
python -m pip install pyogrio==0.13.0
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1
config=docs/experiments/buildings_work01b
python -m datascape.buildings.enrichment_study "$config/seoul.json" \
  --extract ../buildings-inputs/overture --checkpoint ../buildings-review \
  --dtm ../buildings-inputs/N37E126_FABDEM_V1-2.tif ../buildings-inputs/N37E127_FABDEM_V1-2.tif \
  --regional ../seoul_research.gpkg --provider "$config/research_reference.json" \
  --output ../buildings-work01b-review
python -m pytest -q
```

For official data, pass an authorized local polygon source (SHP, GeoPackage, or normalized WKB Parquet) with a JSON provider mapping its real field names. Required provider metadata are source, version, license and authoritative. Map fields.id for every source. Optional normalized field keys include parcel_id, address, building_name, height_m, floors, floors_underground, use_code, use_name, structure, roof and building_area_m2. Geometry readers respect the layer CRS. For WKB Parquet, declare crs and use the name geometry. Keep the input CSV or DBF IDs as strings. Do not coerce a float back into a government ID. Only set authoritative after checking the official file and its field definitions.

See [validation](validation.json) and [the next-work handoff](HANDOFF.md).
