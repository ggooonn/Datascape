# Tests

As algorithms are implemented, test NoData versus valid negative values, CRS/grid alignment, geographic/screen/panel transforms, boundary crossings with both endpoints outside, pressure interpolation, panel gaps, and direction/order preservation. Later G-code tests should cover calibrated tool access, Z values, and stop/recovery behavior.

The structural baseline contains no engine behavior tests. Source bytes/checksums, Python/JSON/YAML syntax, package imports, scaffold notebook execution, and documentation links are the relevant structural checks. They do not validate terrain reproduction or physical hardware.
