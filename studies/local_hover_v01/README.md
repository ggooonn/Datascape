# Local hover and incomplete Spring review v01

Independent study branch based on Backend PR #27 at
`12b28bd5b7ad575b1438ed5af61618746c7effe9`. PR #27 is unchanged.
The requested Korean report is in `results/Datascape_Local_Hover_v01.ko.html`.

## Implemented behavior

The compatible v0.3 extension selects a lower **retraction target before leaving
an original stroke**, then starts the following approach from that same height.
It preserves all accepted vertices, pressure samples, directions and source order.
Only consecutive complete source units with the same setup/panel/material/color,
within the configured endpoint/start distance and without a pending reload or
color change, qualify. No painted strokes are joined. Swept-path validation is
still required; a blocked low corridor falls back to the normal validated route.
Air exports retain normal hover. Enabling local hover for painting requires
current `local_hover_clearance` evidence, scoped to machine, motion and brush.
The candidate configuration keeps it **disabled**.

`config.py` leaves machine offsets, stone deep/shallow points, sponge surface,
contact volumes, station feeds/dwells/pattern dimensions and physical motion
boundaries unresolved. Historical XY points are nominal references, not measured
G54. The review layer cannot write `.nc`; every preview line is commented.
`UNRESOLVED` records preserve the missing station geometry and grammar. Never
remove comments and send this review text to a controller. Physical exports use
the existing `datascape.gcode.production` gates and read-back workflow.

Time fields explicitly represent **paper + nominal station-center transport**.
Station contact/handling is null, not zero. Known partial totals exclude it.
Low acceleration is synthetic. DEV YAML is unverified and can exceed brush-safe
limits; state-specific wet/contact acceleration limits remain unmeasured. Both
scenarios assume junction deviation 0.01 mm and adequate continuous lookahead.
The old station allowance is separate prior-study context, not current timing.

## Reproduce

Use Python 3.10+; the study and verifier use the standard library. The optional
report plot uses matplotlib. Start at this branch's repository root. Use the
accepted PR25 read-only checkout at
`d30ac7be302e1cbfcd2cf66de9087e35ea091b6c` as `/absolute/Pressure`.
Create canonical bound input using `bind_with_accepted_adapter` exactly as in
`docs/plotter_backend_v03/REPRODUCE.md`; do not regenerate artwork or pressure.
The original color-sequencing v02 package provides `source/study_v02.py`,
`source/optimization.py`, and the pinned S3a execution-order archive. The run
checks their order archive and records source hashes. Keep the previous study
commit `cc83b34f18c2498b0f6dd4f559333c9cbfe8e307` available in git for its explicitly
separate historical station allowance. It is read only through `git show`.

```sh
PYTHONPATH=src:. python -m studies.local_hover_v01.run \
  --machine /absolute/offline/spring.machine.json \
  --provenance /absolute/offline/spring.provenance.json \
  --pressure-root /absolute/Pressure \
  --routing-reference /absolute/Datascape_Color_Sequencing_v02 \
  --output /absolute/offline/local-hover-new

PYTHONPATH=src:. python -m studies.local_hover_v01.verify \
  --package /absolute/offline/local-hover-new \
  --machine /absolute/offline/spring.machine.json \
  --provenance /absolute/offline/spring.provenance.json

PYTHONPATH=src:. python -m studies.local_hover_v01.report \
  --package /absolute/offline/local-hover-new

PYTHONPATH=src:. python -m unittest discover -s tests -p 'test_gcode*.py' -v
```

The output directory must be new. The computation covers 108 job/policy/curve
cases with two acceleration models (216 modeled cases): six A/D jobs, two depth
curves, normal hover plus eight local policies. D preferred outputs use p.2→−2,
local +5 mm and distance ≤10 mm. The physical profile keeps local hover disabled;
the review manifest records this deliberate hypothetical override explicitly.
`run.py` writes a SHA256 manifest for its outputs. Reports/read-back may be added
afterward; regenerate that manifest when packaging, excluding the manifest itself.

## Delivered data

The compact git results contain all A/D comparisons, routing audit, exact current
profile blockers, provisional profile, report/plot, read-back and representative
comment-only excerpts. The separately delivered ZIP includes both full plans,
the full D trajectories, pressure/source tags, local transition indexes, full
comment-only previews and SHA256 hashes. The verifier works offline on that ZIP;
canonical input paths are optional but enable an additional independent source
binding and complete-plan comparison. No executable Spring `.nc` is delivered.
A's exact boundary clipping adds fragments/samples; D retains all originals unsplit.

The next steps are measured machine/station registration, limited brush contact
and recovery tests, and scoped authorization through existing v0.3 readiness,
air, calibration and painting exports. No v0.4 architecture is needed.
