"""Isolate foreground target strength on PR #14's fixed mountain phase."""
from pathlib import Path
import argparse
import hashlib
import json
import platform

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from datascape.data.quality import sha256_file
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors, resample, sample
from datascape.strokes.generators import continuity_mask
from datascape.strokes.density_rhythm import (
    a_proposals, density_profile, foreground_a, layer_digest, transfer,
)
from datascape.strokes.mass_density import mass_coordinates, generate_a
from datascape.strokes.spacing_schedule import phase_ablation
from datascape.strokes.accordion import (
    mountain_target, foreground_target, local_monotone_projection,
)
from datascape.rendering.accordion_study import near_path, summary
from datascape.rendering.a_density_v03_study import (
    _render, _compose, _physical_pair, _crossings,
)
from datascape.rendering.grammar_study import validate
from datascape.rendering.hierarchy_study import publish_vectors, metrics
from datascape.rendering.density_rhythm_study import length_map, save_figure


def compare(images, path, title, bounds=(0, 0, 600, 900)):
    """Show all five settings with a shared, readable physical scale."""
    x0, y0, x1, y1 = bounds
    fig, axes = plt.subplots(1, len(images), figsize=(4.4 * len(images),
        4.4 * (y1 - y0) / (x1 - x0) + 1.0), layout='constrained')
    for i, (ax, (label, source)) in enumerate(zip(np.atleast_1d(axes), images.items())):
        with Image.open(source) as im:
            ax.imshow(np.asarray(im), extent=[x0, x1, y1, y0])
        ax.set_title(label, fontsize=10)
        ax.set_xlabel('mm')
        ax.set_aspect('equal')
        if i:
            ax.tick_params(labelleft=False)
    fig.suptitle(title, fontsize=11)
    save_figure(fig, path)


def prepare(master, veg, root, config):
    """Reproduce existing float64 inputs and mountain phase without tuning."""
    c = json.loads((root / config['parent_config']).read_text())
    for path, digest in c['locked_source_sha256'].items():
        if sha256_file(root / path) != digest:
            raise ValueError('Locked source changed: ' + path)
    v2 = json.loads((root / c['v2_config']).read_text())
    old = json.loads((root / v2['baseline_config']).read_text())
    selection = json.loads((root / c['selection']).read_text())
    f = load_selected_scene(master, veg, root, selection)
    f['_grammar_safe'] = distance_transform_edt(
        (f['retention'] > 1e-8) & f['base']['occupied'])
    f['_grammar_xyz'] = np.nan_to_num(f['base']['xyz'])
    parent = read_vectors(root / c['baseline_vectors'])['strokes']
    profile = density_profile(f, old)
    mass = mass_coordinates(f, parent, v2)
    v3 = phase_ablation(f, mass, profile, v2, minimum_derivative_ratio=.05)
    target, _ = mountain_target(
        f, mass, profile, v2, release_strength=c['mountain']['release_strength'])
    target = v3['phase'] + c['mountain']['target_strength'] * (target - v3['phase'])
    phase1, solver = local_monotone_projection(
        f, v3['phase'], target, profile['phase_field'],
        (mass['labels'] > 0) & (f['retention'] > .01), **c['mountain']['solver'])
    nt, near = foreground_target(
        f, phase1, c['foreground']['cutoff_m'], settings=c['foreground']['field'])
    return dict(fixed=f, parent=parent, profile=profile, mass=mass,
                v3=v3, v2config=v2, old=old, config=c, phase1=phase1,
                near_target=nt, near=near, mountain_solver=solver)


def geometry_digest(strokes):
    """Compare final records while ignoring only absolute draw order."""
    return layer_digest(strokes, 'A')


def near_strokes(strokes, fixed, cutoff):
    return [s for s in strokes if s['layer'] == 'A' and near_path(s, fixed, cutoff)]


def path_length(strokes):
    return float(sum(np.linalg.norm(np.diff(s['xy_mm'], axis=0), axis=1).sum()
                     for s in strokes))


def gap_probes(strokes, xs, y_bounds):
    result = {}
    for x in xs:
        y = _crossings(strokes, x, y_bounds)
        gaps = np.diff(y)
        result[str(x)] = dict(crossings=y.tolist(), gaps_mm=gaps.tolist(),
                             median_gap_mm=float(np.median(gaps)) if len(gaps) else None)
    return result


def run(master, veg, config_path, output, repo_root=None, prepared=None):
    cp = Path(config_path).resolve()
    root = Path(repo_root) if repo_root else cp.parents[2]
    config = json.loads(cp.read_text())
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    for path, digest in config['locked_sha256'].items():
        if sha256_file(root / path) != digest:
            raise ValueError('Interpolation input changed: ' + path)
    data = prepared if prepared is not None else prepare(master, veg, root, config)
    f, profile, c, phase1, nt, near, v2 = (
        data[k] for k in ['fixed', 'profile', 'config', 'phase1', 'near_target', 'near', 'v2config'])
    cutoff = c['foreground']['cutoff_m']
    mist = json.loads((root / c['mist_config']).read_text())
    reference = read_vectors(root / config['candidate1_vectors'])['strokes']
    endpoint = read_vectors(root / config['candidate2_vectors'])['strokes']
    original = read_vectors(root / c['baseline_vectors'])['strokes']
    frozen_mountain = [s for s in reference if s['layer'] == 'A' and not near_path(s, f, cutoff)]
    retention_hash = hashlib.sha256(f['retention'].tobytes()).hexdigest()
    xyz_hash = hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    print('Check regenerated Candidate 1 foreground endpoint', flush=True)
    # PR #14 Candidate 1 preserves a legacy extractor. Regenerate that endpoint
    # from its original rules; do not morph or select finished near polylines.
    legacy_raw = foreground_a(a_proposals(f, profile, data['old']), f, .72)
    legacy_near = near_strokes(transfer(legacy_raw, f, mist), f, cutoff)
    assert geometry_digest(legacy_near) == geometry_digest(near_strokes(reference, f, cutoff))
    assert geometry_digest(legacy_near) == geometry_digest(near_strokes(original, f, cutoff))
    domain = f['base']['occupied'] & (f['base']['depth_m'] < cutoff) & (f['retention'] > .01)
    near_region = f['base']['occupied'] & (f['base']['depth_m'] < cutoff) & (f['retention'] > .05)
    masks = {'island': near_region & (near['island'] > .12),
             'channel': near_region & (near['channel'] > .20) & (near['island'] < .05)}
    entries = [(f'strength_{s:.2f}'.replace('.', '_'), s, False) for s in config['strengths']]
    # Same phase as Candidate 1, but through Candidate 2's newer extractor.
    entries.append(('zero_reextracted', 0., True))
    sets, records, phases, raw_gaps = {}, {}, {}, {}
    zero_identity_control = None
    for key, strength, reextract_zero in entries:
        print(f'Generate {key}', flush=True)
        target = phase1 + strength * (nt - phase1)
        if strength == 0:
            phase = phase1.copy()
            sr = dict(solver_status='zero request; identity', maximum_phase_change=0.,
                      nonpositive_phase_derivative_pixels=0)
        else:
            phase, sr = local_monotone_projection(
                f, phase1, target, profile['phase_field'], domain, **c['foreground']['solver'])
        if strength == 0 and not reextract_zero:
            aa = legacy_near
            raw = legacy_raw
            generation = {'extractor': 'legacy a_proposals; exact regenerated Candidate 1 endpoint'}
        else:
            _, raw, generation = generate_a(f, {'phase': phase}, original, v2, mist)
            aa = [{**s, 'id': 'v4n-' + s['id']} for s in near_strokes(transfer(raw, f, mist), f, cutoff)]
            generation['extractor'] = 'PR #14 Candidate 2 generate_a / transfer'
        if reextract_zero:
            # Controlled ID-only ablation: do not change the production sweep.
            renamed = [{**s, 'id': s['id'].replace('A-mass-', 'A-rhythm-')} for s in raw]
            restored = near_strokes(transfer(renamed, f, mist), f, cutoff)
            old_raw_near = near_strokes(legacy_raw, f, cutoff)
            renamed_raw_near = near_strokes(renamed, f, cutoff)
            zero_identity_control = dict(
                legacy_raw_near_paths=len(old_raw_near),
                new_raw_near_paths=len(renamed_raw_near),
                raw_near_geometry_equal_ignoring_id=geometry_digest(renamed_raw_near) == geometry_digest(old_raw_near),
                renaming_only_restores_legacy_final_records=geometry_digest(restored) == geometry_digest(legacy_near),
                renamed_final_near_path_count=len(restored),
                renamed_final_near_length_mm=path_length(restored),
                legacy_final_near_length_mm=path_length(legacy_near))
            assert zero_identity_control['raw_near_geometry_equal_ignoring_id']
            assert zero_identity_control['renaming_only_restores_legacy_final_records']
        ss = _compose(reference, aa + frozen_mountain)
        validate(ss, f)
        for layer in ['B', 'C', 'D', 'V']:
            assert layer_digest(ss, layer) == layer_digest(reference, layer)
        mountain = [s for s in ss if s['layer'] == 'A' and not near_path(s, f, cutoff)]
        assert geometry_digest(mountain) == geometry_digest(frozen_mountain)
        assert len({s['id'] for s in ss}) == len(ss)
        if strength == 0 and not reextract_zero:
            assert geometry_digest(ss) == geometry_digest(reference)
        if strength == .65:
            assert geometry_digest(ss) == geometry_digest(endpoint)
        provenance = dict(study=config['study'], parent_commit=config['parent_commit'],
                          target_strength=strength, regenerated_zero_control=reextract_zero,
                          seed=c['seed'], input_sha256=f['selection']['input_sha256'],
                          config_sha256=sha256_file(cp), retention_sha256=retention_hash,
                          source_XYZ_sha256=xyz_hash)
        publish_vectors(out / f'{key}_strokes.json.gz', ss, provenance)
        ss = read_vectors(out / f'{key}_strokes.json.gz')['strokes']
        sets[key] = ss
        phases[key] = phase
        a = [s for s in ss if s['layer'] == 'A']
        one = length_map(a, 1)
        raw_gaps[key] = gap_probes(raw, config['probe_x_mm'], config['probe_y_mm'])
        records[key] = dict(target_strength=strength, solver=summary(sr), generation=generation,
                            metrics=metrics(ss, f['base']), near_path_count=len(aa),
                            near_path_length_mm=path_length(aa),
                            foreground_density={name: dict(area_mm2=int(m.sum()),
                                A_length_per_mm2=float(one[m].mean())) for name, m in masks.items()},
                            before_mist_spacing=raw_gaps[key],
                            after_mist_spacing=gap_probes(a, config['probe_x_mm'], config['probe_y_mm']),
                            near_source_identities=sorted({s.get('source_stroke_id', '') for s in aa}),
                            frozen_layers=True, frozen_mountain_A=True)
        _render(ss, out / f'{key}_production.png')
        _physical_pair(out / f'{key}_production.png', out / f'{key}_physical.png')
        bounds = tuple(config['foreground_crop_mm'])
        pixels = (1200, round(1200 * (bounds[3] - bounds[1]) / (bounds[2] - bounds[0])))
        _render(ss, out / f'{key}_foreground.png', bounds=bounds, pixels=pixels)
        _render(ss, out / f'{key}_foreground_A.png', bounds=bounds, pixels=pixels, mode='A_only')
    names = {key: f'{strength:.2f}' + (' · Candidate 1' if strength == 0 else
             (' · Candidate 2' if strength == .65 else '')) for key, strength, control in entries if not control}
    for suffix, filename, title, bounds in [
        ('foreground', 'foreground_comparison.png', 'Foreground target strength · identical production styling', tuple(config['foreground_crop_mm'])),
        ('foreground_A', 'foreground_A_comparison.png', 'Actual A paths · identical opaque 0.32 mm width', tuple(config['foreground_crop_mm'])),
        ('production', 'production_comparison.png', 'Fixed Candidate 1 mountain A and B/C/D/V · near target only', (0, 0, 600, 900)),
        ('physical', 'physical_comparison.png', '300 + 300 mm content · 40 mm physical gap', (0, 0, 640, 900)),
    ]:
        compare({name: out / f'{key}_{suffix}.png' for key, name in names.items()}, out / filename, title, bounds)
    compare({'0 · legacy endpoint': out / 'strength_0_00_foreground_A.png',
             '0 · phase re-extraction': out / 'zero_reextracted_foreground_A.png',
             '0.20 · phase re-extraction': out / 'strength_0_20_foreground_A.png'},
            out / 'zero_endpoint_diagnostic.png',
            'Zero phase control · same candidate geometry, different ID-keyed mist decisions', tuple(config['foreground_crop_mm']))
    qy, qx = np.gradient(f['base']['depth_m'])
    py, px = np.gradient(profile['phase_field'])
    den = px * qx + py * qy
    safe = binary_erosion(continuity_mask(f['base']), iterations=2) & (den > 1e-8)
    d65 = phases['strength_0_65'] - phase1
    measured_domain = domain & (np.abs(nt - phase1) > .02)
    for key, phase in phases.items():
        yy, xx = np.gradient(phase)
        ratio = (xx * qx + yy * qy) / np.maximum(den, 1e-8)
        assert not np.any(safe & (ratio <= 0))
        d = phase - phase1
        s = records[key]['target_strength']
        records[key]['phase_measurements'] = dict(
            minimum_directional_ratio=float(ratio[safe].min()),
            nonpositive_checked_pixels=int(np.sum(safe & (ratio <= 0))),
            near_floor_pixels=int(np.sum(domain & safe & (ratio < .051))),
            maximum_displacement_cycles=float(np.max(np.abs(d))),
            mean_abs_displacement_cycles=float(np.abs(d[measured_domain]).mean()),
            rms_deviation_from_scaled_endpoint=float(np.sqrt(np.mean((d[measured_domain] - s / .65 * d65[measured_domain]) ** 2))))
    previous = None
    for key, _, _ in entries:
        if key == 'zero_reextracted':
            continue
        if previous:
            a = set(records[key]['near_source_identities'])
            b = set(records[previous]['near_source_identities'])
            records[key]['previous_source_identity_jaccard'] = len(a & b) / max(1, len(a | b))
        previous = key
    assert retention_hash == hashlib.sha256(f['retention'].tobytes()).hexdigest()
    assert xyz_hash == hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    record = dict(study=config['study'], config=config, variants=records,
                  seed=c['seed'], input_sha256=f['selection']['input_sha256'],
                  retention_sha256=retention_hash, source_XYZ_sha256=xyz_hash,
                  implementation_sha256=sha256_file(Path(__file__)),
                  zero_identity_control=zero_identity_control,
                  mountain_solver=summary(data['mountain_solver']),
                  invariants=dict(exact_regenerated_candidate1_endpoint=True,
                      exact_candidate2_endpoint=True, B_C_D_V_fixed=True,
                      mountain_A_fixed=True, source_XYZ_fixed=True,
                      retention_fixed=True, bottom_2mm_empty=True),
                  versions=dict(python=platform.python_version(), numpy=np.__version__,
                                scipy=__import__('scipy').__version__, osqp=__import__('osqp').__version__))
    (out / 'record.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
    # Compact diagnostics only. Generation, validation and canonical vectors
    # above use the original float64 fields throughout.
    np.savez_compressed(out / 'phase_diagnostics.npz', reference=phase1.astype('float32'),
                        full_foreground_target=nt.astype('float32'),
                        **{k: (v - phase1).astype('float32') for k, v in phases.items()})
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
