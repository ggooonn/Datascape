# FluidNC — Unverified Development Settings

- [Preserved development configuration](config_DEV_2026-10-10_UNVERIFIED.yaml): supplied bytes, unchanged.
- [Example](config.example.yaml): the same values with explanatory comments. It is not calibrated.
- Reported controller: MKS DLC32 V2.2. The source `board` label remains V2.1.
- [Tool coordinates](tool_coordinates.yaml): supplied XY values; the coordinate frame, water/ink well mapping, and Z values are unset.
- [Physical validation records](calibration/README.md).

Verify axis directions, origins, limit pins/wiring, machine positions, work offsets, safe Z, and tool access. The approximate 800 × 900 mm drawing area is separate from the tool access area. Coordinates alone do not establish reachability at X = 847 mm or head clearance.

Do not combine historical negative X/Z values with the new configuration. Pins, rates, acceleration, homing, and limits are preserved. Keep actual `config.yaml` files and network credentials out of Git.
