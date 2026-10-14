"""Reconstruct the selected C scene without changing any composition rule."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from datascape.data.quality import sha256_file
from datascape.rendering.painterly_layers import load_features
from datascape.rendering.foreground_continuity import blend_existing_and_selective
from datascape.composition.multidepth import source_features, build_reserves
from datascape.composition.refinement import refine_reserves
from datascape.vegetation.multidepth import render_marks
from datascape.rendering.composition_refinement import combine


def load_selected_scene(master, veg, root, selection):
    """Recompute float64 fields; float16 archives are diagnostic checks only."""
    root = Path(root)
    for path, digest in selection['locked_files_sha256'].items():
        if sha256_file(root / path) != digest:
            raise ValueError(f'Frozen baseline file changed: {path}')
    for path, key in [(master, 'master'), (veg, 'vegetation')]:
        if sha256_file(path) != selection['input_sha256'][key]:
            raise ValueError(f'Wrong source input: {key}')
    c = json.loads((root / selection['continuity_config']).read_text())
    v3 = json.loads((root / c['source_config']).read_text())
    v2 = json.loads((root / v3['source_config']).read_text())
    scene = json.loads((root / v2['source_composition']).read_text())
    layer = json.loads((root / v2['source_layer_config']).read_text())
    terrain, base, ndvi, counts, source = load_features(master, veg, scene, layer)
    features = source_features(master, base, {**v2['terrain'], 'seed': v2['seed']})
    old = build_reserves(base, features, v2)
    small = json.loads((root / v3['previous_results'] / 'marks.json').read_text())['marks']
    refined = refine_reserves(base, old, small, v3, v2)
    reps = json.loads((root / c['previous_results'] / 'representative_trees.json').read_text())['representatives']
    local = blend_existing_and_selective(refined['legacy_local_retention'],
                                         refined['local_core_retention'], .70)
    retention = local * refined['global_retention']
    s, _, _ = render_marks(small, base, refined, v2['vegetation'])
    t, _, _ = render_marks(reps, base, refined, v2['vegetation'])
    reproduced = np.round((1-combine((1-terrain['shade'])*retention, combine(s,t)))*255).astype('uint8')
    with Image.open(root / selection['selected_image']) as im:
        if not np.array_equal(reproduced, np.asarray(im)):
            raise AssertionError('Selected C image did not reproduce exactly.')
    with Image.open(root / layer['baseline_image']) as im:
        if not np.array_equal(np.round(terrain['shade']*255).astype('uint8'), np.asarray(im)):
            raise AssertionError('F2 geometry baseline changed.')
    with np.load(root / selection['retention_archive']) as archive:
        if not np.array_equal(retention.astype('float16'), archive['terrain_retention_C']):
            raise AssertionError('Selected C retention snapshot changed.')
    return dict(base=base, terrain=terrain, features=features, old=old,
                refined=refined, retention=retention, scene=scene, source=source,
                small=small, representatives=reps, vegetation_config=v2['vegetation'],
                ndvi=ndvi, counts=counts, selection=selection)
