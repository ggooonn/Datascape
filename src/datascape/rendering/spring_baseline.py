"""Freeze the selected 0.25 near-A setting without further optimization."""
from pathlib import Path
import argparse
import hashlib
import json
import platform

import numpy as np
from scipy.ndimage import binary_erosion

from datascape.data.quality import sha256_file
from datascape.strokes.accordion import local_monotone_projection
from datascape.strokes.density_rhythm import layer_digest, transfer
from datascape.strokes.generators import continuity_mask
from datascape.strokes.mass_density import generate_a
from datascape.strokes.vector import read_vectors
from datascape.rendering.accordion_study import summary, near_path
from datascape.rendering.a_density_v03_study import _compose, _render, _physical_pair
from datascape.rendering.foreground_interpolation_study import (
    prepare, near_strokes, geometry_digest, path_length,
)
from datascape.rendering.grammar_study import validate
from datascape.rendering.hierarchy_study import publish_vectors, metrics


def run(master, veg, config_path, output, repo_root=None):
    cp = Path(config_path).resolve()
    root = Path(repo_root) if repo_root else cp.parents[2]
    c = json.loads(cp.read_text())
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    for path, digest in c['locked_sha256'].items():
        if sha256_file(root / path) != digest:
            raise ValueError('Provisional baseline input changed: ' + path)
    interpolation = json.loads((root / c['interpolation_config']).read_text())
    for path, digest in interpolation['locked_sha256'].items():
        if sha256_file(root / path) != digest:
            raise ValueError('Interpolation source changed: ' + path)
    print('Reconstruct fixed F2-C and Candidate 1 mountain phase', flush=True)
    d = prepare(master, veg, root, interpolation)
    f = d['fixed']
    parent_config = d['config']
    assert parent_config['seed'] == c['seed']
    cutoff = parent_config['foreground']['cutoff_m']
    reference = read_vectors(root / interpolation['candidate1_vectors'])['strokes']
    reference_record = json.loads((root / c['interpolation_record']).read_text())
    retention_hash = hashlib.sha256(f['retention'].tobytes()).hexdigest()
    xyz_hash = hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    assert retention_hash == reference_record['retention_sha256']
    assert xyz_hash == reference_record['source_XYZ_sha256']
    mist = json.loads((root / parent_config['mist_config']).read_text())
    target = d['phase1'] + c['foreground_target_strength'] * (d['near_target'] - d['phase1'])
    domain = f['base']['occupied'] & (f['base']['depth_m'] < cutoff) & (f['retention'] > .01)
    print('Regenerate foreground A at target strength 0.25', flush=True)
    phase, solver = local_monotone_projection(
        f, d['phase1'], target, d['profile']['phase_field'], domain,
        **parent_config['foreground']['solver'])
    _, raw, generation = generate_a(f, {'phase': phase}, d['parent'], d['v2config'], mist)
    near = [{**s, 'id': 'v4n-' + s['id']}
            for s in near_strokes(transfer(raw, f, mist), f, cutoff)]
    # Preserve PR #15's exact identity policy. Do not rename A-mass candidates
    # to A-rhythm: that would change the current ID-keyed omission decisions.
    mountain = [s for s in reference if s['layer'] == 'A' and not near_path(s, f, cutoff)]
    strokes = _compose(reference, near + mountain)
    validate(strokes, f)
    assert len({s['id'] for s in strokes}) == len(strokes)
    for layer in ['B', 'C', 'D', 'V']:
        assert layer_digest(strokes, layer) == layer_digest(reference, layer)
    actual_mountain = [s for s in strokes if s['layer'] == 'A' and not near_path(s, f, cutoff)]
    assert geometry_digest(actual_mountain) == geometry_digest(mountain)
    qy, qx = np.gradient(f['base']['depth_m'])
    py, px = np.gradient(d['profile']['phase_field'])
    den = px * qx + py * qy
    gy, gx = np.gradient(phase)
    safe = binary_erosion(continuity_mask(f['base']), iterations=2) & (den > 1e-8)
    ratio = (gx * qx + gy * qy) / np.maximum(den, 1e-8)
    assert not np.any(safe & (ratio <= 0))
    provenance = dict(
        baseline_id=c['baseline_id'], status=c['status'], seed=c['seed'],
        implementation_parent_commit=c['implementation_parent_commit'],
        mountain_reference_commit=c['mountain_reference_commit'],
        foreground_target_strength=c['foreground_target_strength'],
        config_sha256=sha256_file(cp), implementation_sha256=sha256_file(Path(__file__)),
        input_sha256=f['selection']['input_sha256'], retention_sha256=retention_hash,
        source_XYZ_sha256=xyz_hash, path_identity_policy=c['path_identity_policy'])
    publish_vectors(out / 'baseline_strokes.json.gz', strokes, provenance)
    strokes = read_vectors(out / 'baseline_strokes.json.gz')['strokes']
    print('Render canonical full composition and physical pair', flush=True)
    _render(strokes, out / 'production.png')
    _physical_pair(out / 'production.png', out / 'physical_pair.png')
    assert retention_hash == hashlib.sha256(f['retention'].tobytes()).hexdigest()
    assert xyz_hash == hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    outputs = {name: sha256_file(out / name) for name in
               ['baseline_strokes.json.gz', 'production.png', 'physical_pair.png']}
    record = dict(
        provenance=provenance, config=c, metrics=metrics(strokes, f['base']),
        near_A=dict(paths=len(near), length_mm=path_length(near)),
        solver=dict(mountain=summary(d['mountain_solver']), foreground=summary(solver)),
        generation=generation, phase_topology=dict(nonpositive_checked_pixels=0,
            minimum_directional_ratio=float(ratio[safe].min())),
        frozen_layer_digests={layer: layer_digest(strokes, layer) for layer in ['B', 'C', 'D', 'V']},
        mountain_A_digest=geometry_digest(mountain), output_sha256=outputs,
        invariants=dict(F2_C_source_XYZ_fixed=True, retention_70_30_fixed=True,
            mountain_A_exact_candidate1=True, B_C_D_V_exact_candidate1=True,
            bottom_2mm_empty=True, omission_cores_empty=True,
            palette_and_hardware_locked=True, previous_results_unchanged=True),
        known_issue=dict(path_id_dependent_mist_omission=True,
            reference='docs/experiments/spring_foreground_interpolation_v01/record.json#zero_identity_control',
            note='Phase-target interpolation is not a linear interpolation of final stroke visibility. Preserve raw A-mass IDs and the seed; renaming can change omissions.'),
        versions=dict(python=platform.python_version(), numpy=np.__version__,
            scipy=__import__('scipy').__version__, osqp=__import__('osqp').__version__,
            matplotlib=__import__('matplotlib').__version__))
    (out / 'record.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    print('Provisional baseline saved and validated', flush=True)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('master')
    p.add_argument('veg')
    p.add_argument('--config', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    run(a.master, a.veg, a.config, a.output)


if __name__ == '__main__':
    main()
