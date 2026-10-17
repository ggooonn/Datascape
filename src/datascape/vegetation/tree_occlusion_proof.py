"""Isolated vector-mask design proof, deliberately disconnected from scenes.

Shapely buffers are planning envelopes, not measurements of wet ink. Root
depth is a synthetic constant, not per-branch 3D. No accepted terrain archive
is loaded or rewritten by this module.
"""
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
import numpy as np
from shapely.geometry import LineString, Polygon, GeometryCollection, box
from shapely.ops import unary_union
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_plot_scale as physical


@dataclass(frozen=True)
class MaskAssumptions:
    vegetation_width_mm: float = .8
    terrain_width_mm: float = .6
    edge_tolerance_mm: float = .15
    minimum_fragment_mm: float = 2.8
    depth_tolerance_m: float = 25.

    def validate(self):
        values = tuple(self.__dict__.values())
        if not all(np.isfinite(v) and v >= 0 for v in values): raise ValueError('finite positive mask assumptions required')
        if self.vegetation_width_mm <= 0 or self.terrain_width_mm <= 0: raise ValueError('positive brush widths required')


def _member_body(points, radius, key, seed, width, joints=(), branch=False):
    marks, _, _ = physical.safe_contours(points, radius, key, seed, width, joints, branch)
    sides = defaultdict(list)
    for m in marks:
        if '/side-1/' in m.key: sides[-1].append(m.xy)
        elif '/side1/' in m.key: sides[1].append(m.xy)
    if not sides[-1] or not sides[1]: return GeometryCollection()
    left = np.concatenate(sides[-1]); right = np.concatenate(sides[1])
    # Follow the actual paired-to-single taper; do not use the uncollapsed
    # envelope returned for interior branch trimming in older catalog code.
    return Polygon(np.vstack([left, right[::-1]])).buffer(0)


def masks(tree, assumptions=None):
    a = assumptions or MaskAssumptions(); a.validate()
    members = {k: np.asarray(p) for k, p in tree.structure['members'].items()}
    axis = np.vstack([p if i == 0 else p[1:] for i, (k, p) in enumerate((x for x in members.items() if x[0].startswith('axis/')))])
    form = tree.structure.get('catalog_form', 'B')
    radius = tree.height * (.014 if form == 'W' else {'P': .022, 'B': .018, 'U': .012}[form])
    joints = [p[0] for k, p in members.items() if k.startswith('arm-')]
    bodies = [_member_body(axis, radius, 'axis', tree.seed, a.vegetation_width_mm, joints)]
    for key, p in members.items():
        if key.startswith('arm-'):
            bodies.append(_member_body(p, radius * (.4 if form == 'W' else .46), key, tree.seed, a.vegetation_width_mm, branch=True))
        elif form == 'U' and key.startswith('basal-'):
            bodies.append(_member_body(p, tree.height * .012 * .65, key, tree.seed, a.vegetation_width_mm))
    structural = [LineString(m.xy).buffer(a.vegetation_width_mm / 2, quad_segs=8)
                  for m in tree.marks if m.part != 'foliage-field']
    body = unary_union(bodies + structural)
    by_unit = defaultdict(list)
    for m in tree.marks:
        if m.part == 'foliage-field': by_unit[m.key.rsplit('-', 1)[0]].append(m)
    metadata = {u['key']: u for u in tree.canopy_diagnostics['units']}
    foliage = []
    for key, mm in by_unit.items():
        ink = unary_union([LineString(m.xy).buffer(a.vegetation_width_mm / 2, quad_segs=8) for m in mm])
        u = metadata.get(key, {})
        if u.get('state') == 'dense' and u.get('radius_fraction', 1) < .5 and len(mm) >= 2:
            # Only compact occupied core units bridge their own inter-ray gaps.
            # No hull is drawn between distinct units or across an empty pad.
            ink = ink.convex_hull
        foliage.append(ink)
    margin = a.terrain_width_mm / 2 + a.edge_tolerance_mm
    strong = body.buffer(margin, quad_segs=8)
    canopy = unary_union(foliage).buffer(margin, quad_segs=8)
    root_x, root_y = tree.root
    ground_collar = box(root_x - 9, root_y - 1.5, root_x + 9, root_y + 6).difference(strong)
    selective = strong.union(canopy).difference(ground_collar)
    support = unary_union([Polygon(old.halo_outline(l, tree.season, scale=1)) for l in tree.lobes])
    full = strong.union(support.buffer(margin))
    return {'body': strong, 'canopy': canopy, 'root_protection': ground_collar,
            'full': full, 'selective': selective,
            'note': 'Root collar preserves surrounding probes, but does not solve actual attachment or supporting ground selection'}


def line_parts(geometry):
    if geometry.is_empty: return []
    if geometry.geom_type == 'LineString': return [geometry]
    if hasattr(geometry, 'geoms'): return [p for g in geometry.geoms for p in line_parts(g)]
    return []


def clip_vectors(records, mask, object_depth_m, assumptions=None):
    """Split original vectors before plotting; preserve parent IDs and depths.

    Positive forward depth is farther. Equal/supporting depth is retained.
    Production must supply local depth and visible-object masks instead of
    assuming the entire object is in front of every terrain stroke.
    """
    a = assumptions or MaskAssumptions(); a.validate()
    result = []; removed = 0.; short = 0.; eligible = 0
    for source in records:
        line = LineString(source['xy_mm'])
        if source['forward_depth_m'] <= object_depth_m + a.depth_tolerance_m:
            result.append(deepcopy(source)); continue
        eligible += 1
        parts = sorted(line_parts(line.difference(mask)), key=lambda p: line.project(p.interpolate(.5, normalized=True)))
        kept = 0.
        for j, part in enumerate(parts):
            if part.length < a.minimum_fragment_mm:
                short += part.length; continue
            points = list(part.coords)
            if line.project(part.interpolate(0)) > line.project(part.interpolate(1, normalized=True)): points.reverse()
            result.append({**deepcopy(source), 'id': source['id'] + f'/visible-{j}',
                           'source_stroke_id': source['id'], 'xy_mm': [list(p) for p in points]})
            kept += part.length
        removed += line.length - kept
    return result, {'source_paths': len(records), 'eligible_source_paths': eligible, 'retained_paths': len(result),
                    'removed_length_mm': removed, 'short_fragment_length_dropped_mm': short,
                    'minimum_fragment_mm': a.minimum_fragment_mm, 'vector_operation': 'LineString difference of buffered polygons'}


def synthetic_probes():
    """Simple crossing rulers, not a rock/soil/terrain stroke grammar."""
    result = []
    for i, y in enumerate(np.arange(54., 178., 4.)):
        x = np.linspace(45., 170., 100)
        p = np.column_stack([x, y + 1.3 * np.sin((x - 40) / 35 + i * .22)])
        result.append({'id': f'synthetic-ruler-{i}', 'layer': 'terrain-ink', 'xy_mm': p.tolist(),
                       'forward_depth_m': 1800., 'synthetic': True})
    result.append({'id': 'nearer-depth-ruler', 'layer': 'terrain-ink', 'xy_mm': [[45., 153.], [170., 153.]],
                   'forward_depth_m': 900., 'synthetic': True})
    return result
