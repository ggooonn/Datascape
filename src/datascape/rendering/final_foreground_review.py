"""One bounded foreground compression review on the immutable PR #16 baseline."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from scipy.ndimage import label, binary_erosion, binary_dilation, gaussian_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.data.quality import sha256_file
from datascape.projection.composition import smoothstep
from datascape.strokes.vector import read_vectors, sample
from datascape.strokes.generators import continuity_mask
from datascape.strokes.accordion import integrated_target, local_monotone_projection
from datascape.strokes.mass_density import generate_a
from datascape.strokes.density_rhythm import transfer, layer_digest
from datascape.rendering.accordion_study import near_path, summary
from datascape.rendering.foreground_interpolation_study import (
    prepare, near_strokes, geometry_digest, path_length, compare,
)
from datascape.rendering.a_density_v03_study import _compose, _render, _physical_pair, _crossings
from datascape.rendering.hierarchy_study import publish_vectors, metrics
from datascape.rendering.grammar_study import validate
from datascape.rendering.density_rhythm_study import length_map, save_figure


def prepare_review(master, veg, root, c):
    p = json.loads((root / c['interpolation_config']).read_text())
    d = prepare(master, veg, root, p)
    f = d['fixed']; pc = d['config']; cutoff = pc['foreground']['cutoff_m']
    mist = json.loads((root / pc['mist_config']).read_text())
    domain = f['base']['occupied'] & (f['base']['depth_m'] < cutoff) & (f['retention'] > .01)
    phase, solver = local_monotone_projection(f, d['phase1'],
        d['phase1'] + .25 * (d['near_target'] - d['phase1']),
        d['profile']['phase_field'], domain, **pc['foreground']['solver'])
    _, raw, _ = generate_a(f, {'phase': phase}, d['parent'], d['v2config'], mist)
    baseline = read_vectors(root / c['baseline_vectors'])['strokes']
    near = [{**s, 'id': 'v4n-' + s['id']} for s in near_strokes(transfer(raw, f, mist), f, cutoff)]
    assert geometry_digest(near) == geometry_digest(near_strokes(baseline, f, cutoff))
    d.update(baseline=baseline, baseline_phase=phase, baseline_raw=raw,
             baseline_solver=solver, mist=mist)
    return d


def ellipse(shape, xy, radii):
    y, x = np.indices(shape)
    return ((x + .5 - xy[0]) / radii[0]) ** 2 + ((y + .5 - xy[1]) / radii[1]) ** 2


def root_sites(strokes):
    roots = {}
    for s in strokes:
        if s['layer'] == 'V' and s.get('vegetation_role') == 'near':
            roots[s['source_root_id']] = dict(id=s['source_root_id'],
                xy_mm=s['source_root_xy_mm'], hero=s.get('hero', False),
                source_xyz_m=s['source_root_xyz_m'])
    return list(roots.values())


def weighted_display_maps(strokes):
    """Length-weighted saved alpha and width; no opacity-based geometry effect."""
    alpha = np.zeros((900, 600)); footprint = alpha.copy()
    for s in strokes:
        p = np.array(s['xy_mm']); mid = (p[:-1] + p[1:]) / 2
        dl = np.linalg.norm(np.diff(p, axis=0), axis=1)
        op = np.array(s.get('opacity_profile', [s.get('preview_opacity', 1)] * len(p)))
        width = np.array(s.get('width_profile_mm', [s['width_mm']] * len(p)))
        ix = np.clip(mid[:, 0].astype(int), 0, 599); iy = np.clip(mid[:, 1].astype(int), 0, 899)
        a = (op[:-1] + op[1:]) / 2; w = (width[:-1] + width[1:]) / 2
        np.add.at(alpha, (iy, ix), dl * a)
        np.add.at(footprint, (iy, ix), dl * a * w)
    return alpha, footprint


def gaps(strokes, region):
    x, y = region['center_mm']; rx, ry = region['measurement_radii_mm']
    all_gaps = []; crossings = []
    for px in np.linspace(x - rx * .55, x + rx * .55, 5):
        span = ry * np.sqrt(max(0, 1 - ((px - x) / rx) ** 2))
        yy = _crossings(strokes, float(px), (y - span, y + span))
        all_gaps.extend(np.diff(yy).tolist()); crossings.append(dict(x_mm=float(px), y_mm=yy.tolist()))
    return dict(intervals=len(all_gaps), median_mm=float(np.median(all_gaps)) if all_gaps else None,
                p10_p90_mm=np.percentile(all_gaps, [10, 90]).tolist() if all_gaps else [], probes=crossings)


def measures(raw, final, f, regions):
    before = length_map(raw, 1); after = length_map(final, 1)
    alpha, footprint = weighted_display_maps(final)
    out = {}
    for reg in regions:
        m = ellipse(before.shape, reg['center_mm'], reg['measurement_radii_mm']) < 1
        m &= f['base']['occupied'] & (f['base']['depth_m'] < 1600)
        a = before[m].sum(); b = after[m].sum()
        out[reg['name']] = dict(area_mm2=int(m.sum()),
            mean_retention=float(f['retention'][m].mean()),
            mean_slope_deg=float(f['base']['slope_deg'][m].mean()),
            before_length_mm=float(a), after_length_mm=float(b),
            before_density=float(before[m].mean()), after_density=float(after[m].mean()),
            geometric_survival_fraction=float(b / max(a, 1e-9)),
            mean_final_opacity=float(alpha[m].sum() / max(b, 1e-9)),
            alpha_width_footprint_per_mm2=float(footprint[m].mean()),
            before_spacing=gaps(raw, reg), after_spacing=gaps(final, reg))
    return out, before, after


def local_schedule(d, c):
    f = d['fixed']; b = f['base']; q = b['depth_m']; r = f['retention']
    valid = continuity_mask(b) & (q < 1600)
    shape = q.shape; union = np.zeros(shape, bool); focus = np.zeros(shape)
    gentle = 1 - smoothstep((np.nan_to_num(b['slope_deg'], nan=45) - 4) / 20)
    for reg in c['regions']:
        if reg['role'] != 'compress':
            continue
        dist = ellipse(shape, reg['center_mm'], reg['scope_radii_mm'])
        patch = dist < 1
        terrain = gentle if reg['support'] == 'retained_root_ground' else np.maximum(f['features']['mound'], f['features']['ridge']) * gentle
        support = np.clip(1 - dist, 0, 1) ** 2 * terrain
        support *= smoothstep((r - .25) / .35)
        support *= 1 - smoothstep(d['near']['channel'] / .25)
        focus = np.maximum(focus, support)
        union |= patch
    domain = union & valid & (r > .25)
    labels, _ = label(domain)
    py, px = np.gradient(d['baseline_phase']); qy, qx = np.gradient(q)
    frequency = np.maximum((px * qx + py * qy) / np.maximum(qx * qx + qy * qy, 1e-8), 1e-6)
    return labels, focus, frequency


def run(master, veg, config_path, output, repo_root=None, prepared=None):
    cp = Path(config_path).resolve(); root = Path(repo_root) if repo_root else cp.parents[2]
    c = json.loads(cp.read_text()); out = Path(output); out.mkdir(parents=True, exist_ok=True)
    for path, h in c['locked_sha256'].items():
        assert sha256_file(root / path) == h, path
    d = prepared if prepared is not None else prepare_review(master, veg, root, c)
    f = d['fixed']; baseline = d['baseline']; b = f['base']; r = f['retention']
    roots = root_sites(baseline); labels, focus, frequency = local_schedule(d, c)
    rh = hashlib.sha256(r.tobytes()).hexdigest(); xh = hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    frozen = [s for s in baseline if s['layer'] == 'A' and not near_path(s, f, 1600)]
    sets = {'baseline': baseline}; raw_sets = {'baseline': d['baseline_raw']}; solvers = {}
    for name, gain in c['gains'].items():
        print('Generate local compression ' + name, flush=True)
        target, integration = integrated_target(f, d['baseline_phase'], labels,
            frequency * (1 + gain * focus), feather_mm=15, smoothing_mm=4, maximum_displacement=10)
        phase, solver = local_monotone_projection(f, d['baseline_phase'], target,
            d['profile']['phase_field'], labels > 0, **d['config']['foreground']['solver'])
        _, raw, generation = generate_a(f, {'phase': phase}, d['parent'], d['v2config'], d['mist'])
        near = [{**s, 'id': 'v4n-' + s['id']} for s in near_strokes(transfer(raw, f, d['mist']), f, 1600)]
        ss = _compose(baseline, near + frozen); validate(ss, f)
        for layer in ['B', 'C', 'D', 'V']:
            assert layer_digest(ss, layer) == layer_digest(baseline, layer)
        assert geometry_digest([s for s in ss if s['layer'] == 'A' and not near_path(s, f, 1600)]) == geometry_digest(frozen)
        assert np.array_equal(phase[labels == 0], d['baseline_phase'][labels == 0])
        qy, qx = np.gradient(b['depth_m']); py, px = np.gradient(d['profile']['phase_field'])
        den = px * qx + py * qy; gy, gx = np.gradient(phase)
        safe = binary_erosion(continuity_mask(b), iterations=2) & (den > 1e-8)
        assert not np.any(safe & ((gx * qx + gy * qy) <= 0))
        provenance = dict(study=c['study'], baseline_commit=c['baseline_commit'], local_gain=gain,
            seed=20261015, config_sha256=sha256_file(cp), retention_sha256=rh,
            source_XYZ_sha256=xh, implementation_sha256=sha256_file(Path(__file__)))
        publish_vectors(out / f'{name}_strokes.json.gz', ss, provenance)
        sets[name] = read_vectors(out / f'{name}_strokes.json.gz')['strokes']; raw_sets[name] = raw
        solvers[name] = dict(solver=summary(solver), integration=integration, generation=generation,
            phase_unchanged_outside_local_domains=True,
            maximum_requested_compression=float((1 + gain * focus).max()))
    validate(baseline, f)
    print('Measure actual pre/final paths and render comparisons', flush=True)
    results = {}; maps = {}
    for name, ss in sets.items():
        aa = [s for s in ss if s['layer'] == 'A']
        result, before, after = measures(raw_sets[name], aa, f, c['regions'])
        maps[name] = (before, after); results[name] = dict(regions=result,
            metrics=metrics(ss, b), near_A_paths=len(near_strokes(ss, f, 1600)),
            near_A_length_mm=path_length(near_strokes(ss, f, 1600)))
        _render(ss, out / f'{name}_production.png'); _physical_pair(out / f'{name}_production.png', out / f'{name}_physical.png')
        _render(ss, out / f'{name}_A.png', bounds=(30, 600, 570, 890), pixels=(1500, 806), mode='A_only')
        _render(raw_sets[name], out / f'{name}_before_A.png', bounds=(30, 600, 570, 890), pixels=(1500, 806), mode='A_only')
    for suffix, bounds, title in [
        ('A', (30, 600, 570, 890), 'Final A paths · same opaque 0.32 mm width'),
        ('before_A', (30, 600, 570, 890), 'Actual A before unchanged mist · same opaque 0.32 mm width'),
        ('production', (0, 0, 600, 900), 'Same production styling · fixed mountain A and B/C/D/V'),
        ('physical', (0, 0, 640, 900), 'Physical two-panel comparison · 40 mm interval')]:
        compare({c['names'][n]: out / f'{n}_{suffix}.png' for n in sets}, out / f'{suffix}_comparison.png', title, bounds)
    near = b['occupied'] & (b['depth_m'] < 1600) & (np.indices(r.shape)[0] >= 600)
    bins = []
    for lo, hi in [(0, .1), (.1, .25), (.25, .5), (.5, .75), (.75, 1.001)]:
        mask = near & (r >= lo) & (r < hi); a, z = maps['baseline']
        bins.append(dict(retention=[lo, min(hi, 1)], pixels=int(mask.sum()),
            before_density=float(a[mask].mean()), after_density=float(z[mask].mean()),
            survival=float(z[mask].sum() / max(a[mask].sum(), 1e-9))))
    for rt in roots:
        rt['retention'] = float(sample(r, [rt['xy_mm']])[0])
    for name in c['gains']:
        outside = near & ~binary_dilation(labels > 0, iterations=10)
        results[name]['outside_scope_L1_change_mm'] = dict(
            before=float(np.abs(maps[name][0] - maps['baseline'][0])[outside].sum()),
            after=float(np.abs(maps[name][1] - maps['baseline'][1])[outside].sum()))
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    panels = [('Unchanged terrain retention R', r, 1), ('Existing mound/gentle support', d['near']['island'], .4),
        ('Local compression support only', focus, 1), ('Baseline before mist', gaussian_filter(maps['baseline'][0], 5), .4),
        ('Baseline after mist', gaussian_filter(maps['baseline'][1], 5), .4),
        ('Existing valley support', d['near']['channel'], .4)]
    for ax, (title, array, top) in zip(axes.flat, panels):
        im = ax.imshow(np.where(near, array, np.nan), extent=[0, 600, 900, 0], cmap='viridis', vmin=0, vmax=top)
        ax.set_ylim(900, 590); ax.set_title(title); fig.colorbar(im, ax=ax, shrink=.65)
        for rt in roots:
            ax.plot(*rt['xy_mm'], '.', color='#dd4444', ms=2)
        for reg in c['regions']:
            x, y = reg['center_mm']; ax.text(x, y, reg['short'], color='black', fontsize=8,
                bbox=dict(facecolor='white', alpha=.8, edgecolor='none'))
    save_figure(fig, out / 'field_diagnosis.png')
    # Local crop sheets expose path bunching without the production alpha.
    for reg in c['regions']:
        if reg['role'] != 'compress':
            continue
        x, y = reg['center_mm']; rx, ry = reg['scope_radii_mm']; bounds = (x-rx, y-ry, x+rx, y+ry)
        for name, ss in sets.items():
            _render(ss, out / f'{name}_{reg["short"]}.png', bounds=bounds, pixels=(900, round(900*ry/rx)), mode='A_only')
        compare({c['names'][n]: out / f'{n}_{reg["short"]}.png' for n in sets},
            out / f'{reg["short"]}_comparison.png', 'Actual final A · '+reg['name'], bounds)
    assert rh == hashlib.sha256(r.tobytes()).hexdigest()
    assert xh == hashlib.sha256(f['_grammar_xyz'].tobytes()).hexdigest()
    anchors = []
    for reg in c['regions']:
        xy = [reg['center_mm']]
        anchors.append(dict(name=reg['name'], screen_xy_mm=reg['center_mm'],
            source_xyz_m=[float(sample(f['_grammar_xyz'][:, :, i], xy)[0]) for i in range(3)],
            slope_deg=float(sample(b['slope_deg'], xy)[0]),
            source_depth_m=float(sample(b['depth_m'], xy)[0])))
    record = dict(study=c['study'], config=c, baseline_regenerated_exact=True,
        seed=d['config']['seed'], input_sha256=f['selection']['input_sha256'],
        config_sha256=sha256_file(cp), region_source_anchors=anchors,
        variants=results, solvers=solvers, baseline_solver=summary(d['baseline_solver']),
        baseline_retention_bins=bins, root_sites=roots,
        retention_sha256=rh, source_XYZ_sha256=xh,
        invariants=dict(mountain_A_fixed=True, B_C_D_V_fixed=True, retention_fixed=True,
            bottom_2mm_empty=True, omission_cores_empty=True, checked_phase_derivatives_positive=True),
        known_issue='Unchanged ID-keyed mist transfer; current extraction enumeration can change omission decisions outside a phase-edit patch.',
        implementation_sha256=sha256_file(Path(__file__)),
        versions=dict(numpy=np.__version__, scipy=__import__('scipy').__version__,
                      osqp=__import__('osqp').__version__, matplotlib=matplotlib.__version__))
    (out / 'record.json').write_text(json.dumps(record, indent=2, allow_nan=False)+'\n')
    print('Bounded comparison complete; no baseline adopted or overwritten', flush=True)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('master'); p.add_argument('veg'); p.add_argument('--config', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.master, a.veg, a.config, a.output)


if __name__ == '__main__':
    main()
