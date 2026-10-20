# Source and hardware audit

## Exact remote pins checked before implementation

| Source | Branch | Commit |
| --- | --- | --- |
| PR23 Backend v0.1 | feat/plotter-backend-v01-offline | a2c3967b9d79030810f297cf5e1f5df079519aa3 |
| PR24 Spring XY | checkpoint/spring-v13-interim-v01 | 67ba146b1213644d40bc9dabed9d52024d2bbe58 |
| PR25 accepted pressure | checkpoint/spring-v13-pressure-intent-v01 | d30ac7be302e1cbfcd2cf66de9087e35ea091b6c |

All three remote heads matched the requested commits and were open Draft PRs.
Separate worktrees were checked out at these pins. The new branch starts from
PR23's pin and targets its branch, not main. PR24/25 were read-only sources.

Read PR23's implementation/handoff, PR25's exact
`docs/checkpoints/spring_pressure_intent_v01/PLOTTER_BACKEND_HANDOFF.md`,
`REPRODUCE.md`, `KNOWN_LIMITATIONS.md`, the accepted adapter source, actual
machine-vector records, pressure/provenance, original FluidNC YAML and station
coordinate YAML before implementing missing components. The original seven
Backend tests passed before changes.

The existing adapter was invoked as documented, outside frozen directories.
It validated 14,951 strokes / 240,974 pressures and replaced all 675 historical
profiles plus all 14,276 placeholder profiles. No synthesis was run.

| Binding | SHA-256 |
| --- | --- |
| Accepted pressure gzip | 0b8d59b7ca9268c70378b7a78df3f8825763b2b43e5667785459b2838d2b0b4e |
| Bound machine canonical payload | 6586df2ea3c48ee45de7df10926a2845172f39203ec805f61724f0c7e504ff2b |
| Binding provenance core, excluding optional backend_check | c8baa3e46ce773a8752f488c889dc422e34d2ab9ba0ee87582efd9126c7e88d4 |

The new loader verifies these canonical payload/provenance hashes before any
clipping. This is a downstream integrity boundary, not another pressure adapter.
The full per-source binding record stays with regenerated offline outputs.

## Historical notebooks actually inspected

| Notebook | Access | SHA-256 |
| --- | --- | --- |
| datascape_0317test.ipynb | PR23 artworks/2026-03-17_geumgang/original | 32ee14d19805bb561019126e60c518c599f1a9be9c3aeb49e02d3793c40cafd6 |
| datascape_0815_Taebaek(1).ipynb | User file, Library; absent from PR23 tree | 0ebd5e95ae309edf88b6cd1857e12510d5c6e657c1e22d3a604400e7f0b49a77 |
| datascape_0820_Taebaek.ipynb | PR23 artworks/2026-08-20_taebaek_eum/original | 51533b010668e3b56acaa4d08cb3f481cf6fdb725789ba682f341b3d36444d9e |

0317 uses 3D simplification/splines, greedy reversal, layer-specific material
controls, length-triggered dipping and manual wash pauses. 0815 uses separate
ink/color pressure functions, explicit layer order, length-triggered loading,
automatic washing and final deep wash. 0820 adds panel tilt, bidirectional
scheduling, stirring dip and a repeated deep-wash routine. Relevant code cells
were read; no notebook execution was needed or performed.

Reused concepts: separate phases, explicit original ordering, distance-triggered
reload requests, wash/pause states and continuous XY/Z interpretation. Not reused:
historical station coordinates/dip depths, terrain-pressure calculations,
path reversal, splines, point removal, minimum-length cuts, or tilt compensation.
These would change accepted Spring geometry/intent or assume incompatible hardware.
No large historical notebook was duplicated in this focused PR.

## Current hardware knowledge

The user reports an MKS DLC32 **V2.2** with FluidNC and a locally corrected
configuration verified by manual Jog: X+ right, Y+ rear, Z+ up. This is a user
observation, not a hardware test conducted by this Work. GitHub's old V2.1-labeled
YAML is not the installed authoritative configuration and was not applied/edited.

Nominal configuration: X900/Y960/Z50 mm, 80 steps/mm; XY 15,000 and Z 8,000 mm/min
max rates. The redesigned approximately 50-mm Z range is only a planning
assumption. Actual travel, end margins, brush mount, limit operation, homing
repeatability, E-stop/recovery, G54 offset and safe compression remain unverified.
No -12 mm compression is approved. Mechanical redesign is outside this Work.

Homing seek values in the old file are X/Y4,000 and Z1,500 mm/min. Proposed future
X/Y6,000 trials are not applied. Jog feed and homing seek are distinct.

`tool_coordinates.yaml` explicitly has unverified status, null coordinate frame
and null well roles. Coordinates near X840–847 mm cannot be used as G54 station
locations. Container heights (inkstone ~15, palette ~27, sponge <=20 mm above bed)
and paper height (~3–5 mm) are approximate context, not dipping or safe-clearance
measurements. Historical below-bed negative dip values are invalid here.

Pressure limitations remain unchanged: 3,277 profiles with family clipping,
507 nearly flat profiles (including 28 longer expressive-width paths), estimated
D hierarchy and potentially weak marks at 0.22. Calibration does not silently
revise artistic intent.
