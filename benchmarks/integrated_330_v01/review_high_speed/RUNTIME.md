# Canonical Spring offline runtime (minutes)

Same Z-8 response, XY, accepted pressure and S3a in every scenario. Future lip contact excluded. JD0.01 is ASSUMED; no time is physically verified.

| Scenario/job | Commanded | Config acceleration | Synthetic100 acceleration | Ink load count |
|---|---:|---:|---:|---:|
| A_PR31_Z8/SHARED_COLOR | 299.68 | 359.17 | 670.54 | — |
| A_PR31_Z8/SHARED_INK | 190.50 | 211.12 | 343.15 | 84 |
| B_HIGH_WET12000/SHARED_COLOR | 190.45 | 247.20 | 567.63 | — |
| B_HIGH_WET12000/SHARED_INK | 98.76 | 118.25 | 257.80 | 72 |
| C_HIGH_WET15000/SHARED_COLOR | 187.76 | 245.55 | 567.25 | — |
| C_HIGH_WET15000/SHARED_INK | 94.81 | 115.11 | 257.53 | 72 |

## Exclusive commanded-motion categories (minutes)

| Scenario/job | Drawing | Paper engagement | Other travel | Other station transfers | Used-brush return | Station handling |
|---|---:|---:|---:|---:|---:|---:|
| A_PR31_Z8/SHARED_COLOR | 16.11 | 106.72 | 39.02 | 10.67 | 111.57 | 15.60 |
| A_PR31_Z8/SHARED_INK | 14.72 | 33.01 | 31.03 | 5.34 | 83.71 | 22.69 |
| B_HIGH_WET12000/SHARED_COLOR | 16.11 | 106.72 | 36.77 | 8.35 | 7.27 | 15.23 |
| B_HIGH_WET12000/SHARED_INK | 14.72 | 33.01 | 25.91 | 3.84 | 4.23 | 17.05 |
| C_HIGH_WET15000/SHARED_COLOR | 16.11 | 106.72 | 35.42 | 7.01 | 7.27 | 15.23 |
| C_HIGH_WET15000/SHARED_INK | 14.72 | 33.01 | 22.58 | 3.22 | 4.23 | 17.05 |

Configuration-reference: baseline XY1200/Z1000, high-speed XY1500/Z1000mm/s²;
all rates come from their respective YAML/profile. Synthetic low:100 on all
axes for all scenarios. Both use projected axes, actual XYZ/junction geometry,
reverse braking/forward acceleration and the same assumedJD0.01. Adequate full
lookahead is assumed; finite buffer/TCP/step overhead is not established. Global
XY acceleration also affects drawing/station motions; slow contact feeds do not
constitute a separate hardware acceleration limit. Initial wet12000 is preferred:
wet15000 has modest modeled benefit and requires its own wet-motion trial.
