"""Run via: python -m datascape.gcode INPUT.json OUTPUT_DIR"""
import argparse
from pathlib import Path
from . import PANELS,load_strokes,plan,preview_gcode,preview_svg


def main():
    parser=argparse.ArgumentParser(description='NON-EXECUTABLE offline previews only')
    parser.add_argument('input',help='Machine vector JSON')
    parser.add_argument('output_dir')
    args=parser.parse_args()
    strokes=load_strokes(args.input)
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    for panel in PANELS:
        for medium in ('ink','color'):
            motions,ordered=plan(strokes,panel,medium=medium)
            name=f'spring_{panel.name}_{medium}'
            (dest/f'{name}.preview.gcode.txt').write_text(preview_gcode(motions,panel),encoding='utf-8')
            (dest/f'{name}.svg').write_text(preview_svg(ordered,panel),encoding='utf-8')
            print(name,'segments:',len(ordered),'motions:',len(motions))
    print('PREVIEWS ONLY. No runnable G-code generated.')


if __name__=='__main__':
    main()
