# Future printing workload / review only

Visible Summer ink contains **3,899** canonical paths totaling **122.534 m**. Color intent contains **2,444** paths totaling **14.351 m**. These are independent centerlines, not optimized contacts or reload counts.

The preserved Spring source has 3,345 ink paths / 88.283 m. Summer therefore adds 16.6% paths and 38.8% paper-engagement distance before any physical execution study. This does not compare runtime with Spring's station-inclusive program.

| Canonical visible layer | Paths | Length (m) | Below 5 mm |
| --- | ---: | ---: | ---: |
| A | 2,056 | 106.190 | 97 |
| B | 73 | 0.908 | 5 |
| C | 296 | 4.787 | 32 |
| D | 69 | 1.211 | 0 |
| Soil | 3 | 0.059 | 0 |
| V | 412 | 2.900 | 149 |
| rock | 63 | 0.733 | 13 |
| tree | 927 | 5.745 | 585 |

Canonical ink: 167 paths in the 2.8–3 mm range; 881 paths below 5 mm. Canonical color intent: 1136 paths below 5 mm. No final canonical path is below 2.8 mm. Imported v10 rounding-length deviations and very short terrain fragments are dropped and logged, never lengthened.

Panel fragments are clipped losslessly: P3 has 1,772 ink / 1,034 color-intent fragments; P4 has 2,130 ink / 1,415 color-intent fragments. Seven boundary-created fragments are shorter than 2.8 mm. Their IDs and exact lengths are in `verification.json`; preserve them as evidence and review physical treatment before a future backend pass. Do not discard them silently in this vector scene.

The 100 × 100 mm cells with most ink length are listed in the statistics JSON. The highest cells are around X300–400 / Y100–300 mm (terrain crest/shoulder structure), followed by the X100–200 / Y500–600 mm terrain-to-vegetation transition. Dense small near foliage and rock contacts also warrant measured test crops even when their total length is lower.

At an entirely hypothetical constant 600–1200 mm/min, ink distance alone would take about 204.2–102.1 minutes. This excludes acceleration, pressure, lifts, travel, washing, loading, dwell, manual waits and drying; it is **not a machine runtime estimate**. No G-code or loading threshold is chosen.

Prioritize later simplification of low-value small canopy/ground fragments while preserving dominant/subordinate groups, mountain accordion rhythm, open passages and connected structural emphasis. First compare physical test crops; do not globally thin this scene solely to match a time target.
