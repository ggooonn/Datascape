"""Replay immutable Spring v04 vectors without TIFFs or private references.

This does not regenerate placement, clipping, depth fields or artistic choices.
The original study modules remain unchanged for full source regeneration.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import numpy as np
import yaml
from PIL import Image
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_macro_study import render, write_gz
from datascape.rendering.spring_diverse_study import display_records, render as render_ink
from datascape.rendering.spring_diverse_diagnostics import export_channel_svg

ROOT = Path(__file__).resolve().parents[3]
DEFAULT = ROOT / 'docs/checkpoints/spring_integration_v04'
PRIMITIVES = ('A', 'C', 'thin', 'rock_soil', 'gestures', 'trunk', 'hard_only_terrain')


def verify(checkpoint=DEFAULT):
    checkpoint = Path(checkpoint).resolve()
    manifest = json.loads((checkpoint / 'checkpoint_manifest.json').read_text())
    for group in ['retained_artifact_sha256', 'locked_source_sha256', 'original_implementation_sha256']:
        base = checkpoint if group == 'retained_artifact_sha256' else ROOT
        for name, expected in manifest[group].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f'Checkpoint hash mismatch: {name}')
    return manifest


def channels(checkpoint=DEFAULT):
    path = Path(checkpoint) / 'artifacts'
    sets = {name: read_vectors(path / (name + '_color.json.gz'))['strokes'] for name in PRIMITIVES}
    sets['terrain'] = sets['A'] + sets['C']
    sets['caseB'] = sets['terrain'] + sets['rock_soil'] + sets['thin']
    sets['caseC'] = sets['terrain'] + sets['rock_soil'] + sets['gestures'] + sets['trunk']
    return read_vectors(path / 'ink.json.gz')['strokes'], sets


def restore_controls(checkpoint=DEFAULT):
    destination = ROOT / 'outputs/spring-diverse-vector-v03'
    destination.mkdir(parents=True, exist_ok=True)
    for source in (Path(checkpoint) / 'control_v03').iterdir():
        target = destination / source.name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise FileExistsError(f'Preserving different local control: {target}')
        if not target.exists():
            shutil.copyfile(source, target)
    return destination


def replay(output, checkpoint=DEFAULT):
    checkpoint = Path(checkpoint).resolve()
    verify(checkpoint)
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a new or empty output directory; prior experiments are preserved.')
    if output == checkpoint or checkpoint in output.parents:
        raise ValueError('Replay output must be outside the immutable checkpoint.')
    output.mkdir(parents=True, exist_ok=True)
    ink, sets = channels(checkpoint)
    config = json.loads((ROOT / 'configs/scenes/seoul_spring_macro_v04.json').read_text())
    palette = yaml.safe_load((ROOT / config['palette_source']).read_text())
    for key in ['terrain', 'caseB', 'caseC']:
        write_gz(output / (key + '_color.json.gz'), dict(continuous_mm=[600, 900], strokes=sets[key]))
    # The archived A used the original v03 renderer, unlike B/C.
    render_ink(ink, [], output / 'caseA_ink.png', palette)
    for case in ['caseB', 'caseC']:
        for mode in ['restrained', 'diagnostic']:
            render(ink, display_records(sets[case], config, mode), output / f'{case}_{mode}.png', palette)
    render([], display_records(sets['caseC'], config, 'diagnostic'), output / 'color_only_diagnostic.png', palette)
    export_channel_svg(output / 'scene_centerlines.svg', ink, sets['caseC'], palette)
    export_channel_svg(output / 'color_centerlines.svg', [], sets['caseC'], palette)
    for name in ['scene_centerlines.svg', 'color_centerlines.svg']:
        path = output / name
        path.write_text(path.read_text().replace('Spring v03', 'Spring v04').replace(
            'Source q in meters;', 'Mean-width centerlines only; JSON retains uncalibrated width intent. Source q in meters;'))
    equal = {}
    for name in ['caseC_diagnostic.png', 'color_only_diagnostic.png']:
        with Image.open(output / name) as actual, Image.open(checkpoint / 'artifacts' / name) as original:
            equal[name] = bool(np.array_equal(np.asarray(actual), np.asarray(original)))
    result = dict(replayed_counts={name: len(rows) for name, rows in sets.items()}, archived_pixels_equal=equal,
                  scope='Saved-vector replay only; no TIFF/source-field/placement regeneration or physical calibration.')
    (output / 'replay_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    if not all(equal.values()):
        raise ValueError('Replay differs from archived pixels; inspect dependency versions before using it.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--restore-controls', action='store_true')
    args = parser.parse_args()
    verify(args.checkpoint)
    if args.restore_controls:
        restore_controls(args.checkpoint)
    if args.output:
        print(json.dumps(replay(args.output, args.checkpoint), indent=2))
    else:
        print('Checkpoint hashes verified.')


if __name__ == '__main__':
    main()
