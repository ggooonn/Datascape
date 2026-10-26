# Spring panels / numerical runtime comparison

All times modeled, not measured. PR34 acceleration references, assumed JD0.01/full lookahead. No changed feeds or physical authorization.

| P2 case | Loads L/D | Switches | Distance/contact/both triggers | Station handling | Station transfer | Drawing | Paper engagement | Non-drawing | Total |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A_contact12 | 168 (121/47) | 22 | 10/131/4 | 47.133 | 14.949 | 10.455 | 24.229 | 12.978 | 109.745 |
| B_contact15 | 142 (100/42) | 22 | 18/98/3 | 40.846 | 13.007 | 10.455 | 24.262 | 13.169 | 101.739 |
| C_contact20 | 116 (82/34) | 22 | 26/67/0 | 34.721 | 10.976 | 10.455 | 24.295 | 13.208 | 93.655 |
| D_distance_only | 70 (46/24) | 22 | 47/0/0 | 23.659 | 7.752 | 10.455 | 24.353 | 13.291 | 79.510 |

Minutes in every time column. Threshold categories are exclusive; switch/initial events are separate. Each concentration switch performs a full wash; each job also has three terminal wash visits. Atomic overruns and simultaneous triggers remain in JSON. No modeled manual-M0 or drying delay.

| P2 case | Full washes (switch + terminal visits) | Max contacts | Max accumulated mm | Max distance overrun mm | Max contact overrun |
| --- | --- | ---: | ---: | ---: | ---: |
| A_contact12 | 22 + 3 | 12 | 986.441 | 186.441 | 0 |
| B_contact15 | 22 + 3 | 15 | 957.597 | 157.597 | 0 |
| C_contact20 | 22 + 3 | 20 | 957.597 | 157.597 | 0 |
| D_distance_only | 22 + 3 | 136 | 957.597 | 157.597 | 0 |

| Selected job | Sources | Contacts | Loads | Modeled minutes |
| --- | ---: | ---: | ---: | ---: |
| P2 | 1851 | 1851 | 116 | 93.655 |
| P1 | 1494 | 1494 | 100 | 84.368 |
| P1P2 | 3345 | 3342 | 207 | 173.875 |
