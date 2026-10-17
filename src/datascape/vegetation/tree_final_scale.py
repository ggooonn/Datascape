"""Final catalog-only scale operators on the immutable v09 tree grammar.

Unit count, touches per unit and correlated length hierarchy are separate
inputs. They share a physical clearance constraint, so achieved outputs are
reported separately. No scene, terrain generator or hardware is imported.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import numpy as np
from scipy.spatial import cKDTree
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_form_calibration as prior
from datascape.vegetation import tree_rhythm as rhythm
from datascape.strokes.vector import resample


@dataclass(frozen=True)
class FoliageControls:
    touches: str = 'scale'
    unit_count_scale: float = 1.0
    length_variation: float = .12
    length_growth: bool = True

    def validate(self):
        if self.touches not in ('v09', 'scale'): raise ValueError('unknown touch policy')
        if not np.isfinite(self.unit_count_scale) or not 1 <= self.unit_count_scale <= 1.5:
            raise ValueError('unit count scale must be 1–1.5; vigor remains the reduction control')
        if not np.isfinite(self.length_variation) or not 0 <= self.length_variation <= .15:
            raise ValueError('correlated variation must be 0–0.15')
        if not isinstance(self.length_growth, bool): raise ValueError('length growth must be boolean')


PROFILES = {
    'touch': FoliageControls(length_variation=0, length_growth=False),
    'units': FoliageControls(touches='v09', unit_count_scale=1.35, length_variation=0, length_growth=False),
    'length': FoliageControls(touches='v09'),
    'refined': FoliageControls(),
}


def bundles(marks):
    result = defaultdict(list)
    for m in marks:
        if m.part == 'foliage-field': result[m.key.rsplit('-', 1)[0]].append(m)
    return result


def scale_touch_target(height, state, radius, seed, key, current):
    """One stable quantile per whole bundle, conditioned by pad and edge role."""
    if height < 35 or state in ('open', 'remnant'): return current
    q = float(old.rng_for(seed, key + '/final-touch-quantile').random())
    if radius > .75 and q < .65: return current
    if height < 70:
        # Most H45 units stay untouched; selected core units gain one ray.
        return max(current, min(4, current + 1)) if state == 'dense' and q > .65 else current
    weights = (.13, .47, .31, .09, 0.) if height < 112 else (.10, .30, .34, .21, .05)
    n = int(np.searchsorted(np.cumsum(weights), q)) + 1
    if state == 'light': n = min(n, 3 if height < 112 else 4)
    if radius > .70: n = min(n, 2)
    return max(current, n)


def clearance(marks, others, width, gap):
    """Conservative sampled centerline guard between distinct local units.

    The 0.14 mm guard exceeds the 0.12 mm sampling uncertainty. Touches in
    one unit may join deliberately; this is not a separated-leaf guarantee.
    """
    if not others: return True, None
    a = np.concatenate([resample(m.xy, .12) for m in marks])
    b = np.concatenate([resample(m.xy, .12) for m in others])
    distance = float(cKDTree(b).query(a)[0].min())
    return distance >= width + gap + .14, distance


def length_summary(marks):
    values = [old.length(m.xy) for m in marks if m.part == 'foliage-field']
    if not values: return {'count': 0, 'min': None, 'p10': None, 'median': None, 'p90': None, 'max': None}
    q = np.quantile(values, [0, .1, .5, .9, 1])
    return dict(count=len(values), **dict(zip(('min', 'p10', 'median', 'p90', 'max'), map(float, q))))


def make_tree(form='B', root=(110, 180), height=95, seed=20261017, identity='tree-0',
              posture='auto', accent='none', profile='refined', controls=None,
              growth_controls=None, architecture='base', design_width_mm=.8, clear_gap_mm=.5):
    if profile not in ('v09', *PROFILES): raise ValueError('unknown final-scale profile')
    kw = dict(form=form, root=root, height=height, seed=seed, identity=identity, posture=posture,
              accent=accent, growth_controls=growth_controls, architecture=architecture,
              design_width_mm=design_width_mm, clear_gap_mm=clear_gap_mm)
    base = prior.make_tree(**kw)
    if profile == 'v09':
        if controls is not None: raise ValueError('v09 control must remain exact')
        return base
    settings = controls or PROFILES[profile]; settings.validate()
    # At the smallest class the legacy rays already sit on the assumed
    # execution floor. Preserve the exact geometry instead of adding length
    # detail that is better reserved for a larger object.
    if height < 35 and settings.unit_count_scale == 1:
        return base
    source = rhythm.make_tree(prior.FORMS[form], root, height, 'spring', seed, accent, identity,
                             'near' if height >= 70 else 'middle', posture=posture)
    growth = growth_controls or prior.GrowthControls()
    source = prior.stem_layout(source, growth.stem_ratio)
    if form == 'W': source = prior.hanging_source(source)
    elif architecture == 'terminal-droop': source = prior.terminal_droop(source)
    candidates = bundles(source.marks)
    info = {u['key']: u for u in source.canopy_diagnostics['units'] if u['retained']}
    selected = bundles(deepcopy(base.marks))
    baseline_keys = set(selected)
    extra_candidate_units = 0
    if settings.unit_count_scale > 1:
        proposed, _ = prior.thin(source, form, prior.density_gain(form, height) * growth.vigor * settings.unit_count_scale,
                                 design_width_mm, clear_gap_mm)
        for key, mm in bundles(proposed).items():
            if key in selected: continue
            extra_candidate_units += 1
            ok, _ = clearance(mm, [m for marks in selected.values() for m in marks], design_width_mm, clear_gap_mm)
            if ok: selected[key] = mm
    records = []
    floor = max(2.8, 3.5 * design_width_mm)
    growth_factor = float(np.interp(height, [22, 45, 95, 130], [1, 1, 1.04, 1.07])) if settings.length_growth else 1.
    for key in list(selected):
        mm = selected[key]; meta = info[key]; available = candidates[key]
        requested = scale_touch_target(height, meta['state'], meta['radius_fraction'], seed, key, len(mm)) if settings.touches == 'scale' else len(mm)
        n = min(requested, len(available))
        # Retain v09 rays first; add only exact existing V02-derived candidates.
        # W deliberately remains capped at its three existing rays.
        by_key = {m.key: m for m in mm}; additions = []
        for original in available:
            if len(by_key) >= n: break
            if original.key in by_key: continue
            m = deepcopy(original); length = old.length(m.xy)
            target = max(floor, min(6.2, length))
            m.xy = m.xy[0] + (m.xy - m.xy[0]) * target / max(length, 1e-9)
            by_key[m.key] = m; additions.append(m.key)
        others = [m for k, marks in selected.items() if k != key for m in marks]
        rejected = 0
        # Never remove an existing unit to make a fuller neighbor fit.
        while additions and not clearance(list(by_key.values()), others, design_width_mm, clear_gap_mm)[0]:
            del by_key[additions.pop()]; rejected += 1
        mm = list(by_key.values()); changed = deepcopy(mm)
        # Correlated unit field + edge hierarchy + ray ordering; no per-ray RNG.
        phase = float(old.rng_for(seed, key + '/length-field').uniform(-math.pi, math.pi))
        role = np.clip((.55 - meta['radius_fraction']) / .7, -1, 1)
        for j, m in enumerate(changed):
            ray = 0 if len(changed) == 1 else (2 * j / (len(changed) - 1) - 1)
            field = .45 * math.sin(phase) + .30 * role + .25 * ray
            original_length = old.length(m.xy)
            target = max(floor, original_length * growth_factor * (1 + settings.length_variation * field))
            m.xy = m.xy[0] + (m.xy - m.xy[0]) * target / max(original_length, 1e-9)
        length_fallback = False
        if not clearance(changed, others, design_width_mm, clear_gap_mm)[0]:
            changed = mm; length_fallback = True
        selected[key] = changed
        records.append({'key': key, 'pad': meta['owner_pad'], 'state': meta['state'],
                        'radius_fraction': meta['radius_fraction'], 'rotation_deg': meta['rotation_deg'],
                        'baseline_unit': key in baseline_keys, 'available_touches': len(available),
                        'requested_touches': requested, 'touches': len(changed),
                        'added_rays_rejected_by_gap': rejected, 'length_fallback': length_fallback,
                        'lengths_mm': [old.length(m.xy) for m in changed]})
    foliage = [m for marks in selected.values() for m in marks]
    base.marks = [m for m in base.marks if m.part != 'foliage-field'] + foliage
    base.canopy = 'final-scale-units'
    base.structure.update(catalog_profile='v10-final-scale', foliage_controls=asdict(settings))
    base.canopy_diagnostics = {'controls': asdict(settings), 'form': form, 'units': records,
        'pads': deepcopy(base.canopy_diagnostics['pads']), 'retained_units': len(selected),
        'retained_foliage_paths': len(foliage), 'unit_touch_histogram': dict(Counter(u['touches'] for u in records)),
        'available_candidate_units': len(candidates), 'extra_candidate_units': extra_candidate_units,
        'extra_units_accepted': len(selected) - len(baseline_keys), 'minimum_leaf_length_mm': floor,
        'length_growth_factor': growth_factor, 'length_summary_mm': length_summary(foliage),
        'design_width_mm': design_width_mm, 'clear_gap_mm': clear_gap_mm,
        'within_unit_merging': 'Allowed calligraphic joins; separated individual leaf impressions are not guaranteed',
        'physical_plotting_validated': False, 'cross_tree_spacing': 'not guaranteed'}
    for pad in base.canopy_diagnostics['pads']:
        subset = [u for u in records if u['pad'] == pad['key']]
        pad['retained_units'] = len(subset); pad['retained_paths'] = sum(u['touches'] for u in subset)
    return base


def vector_records(marks, trees):
    result = []; lookup = {t.identity: t for t in trees}
    for m in marks:
        t = lookup[m.owner]
        if t.canopy != 'final-scale-units': records = prior.vector_records([m], [t])
        else:
            records = old.vector_records([m], [t])
            for r in records:
                r.update(id=r['id'].replace('catalog-v02/', 'catalog-v10/', 1), catalog_version='0.10',
                         catalog_form=t.structure['catalog_form'], foliage_controls=t.structure['foliage_controls'],
                         physical_design_assumption_mm=t.canopy_diagnostics['design_width_mm'], physical_plotting_validated=False)
        for r in records: r['draw_order'] = len(result); result.append(r)
    return result
