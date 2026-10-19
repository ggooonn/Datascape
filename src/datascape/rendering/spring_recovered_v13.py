"""Same-scale v12/candidate review; no original v13 identity assertion."""
from pathlib import Path
import argparse,json,yaml
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg
from datascape.rendering.spring_massing_v07 import readable

ROOT=Path(__file__).resolve().parents[3]


def run(path):
    c=json.load(open(path/'config.json'));palette=yaml.safe_load((ROOT/c['palette_source']).read_text());cases=[]
    labels=['Exact recovered control / v12','v13_recovered_candidate / not original proof']
    for name,label in zip(['before','after'],labels):
        ink=read_vectors(path/f'{name}_ink.json.gz')['strokes'];col=read_vectors(path/f'{name}_color.json.gz')['strokes'];cases.append((ink,col))
        for mode in ['full','ink','color']:render([] if mode=='color' else ink,[] if mode=='ink' else readable(col,c),path/f'{name}_{mode}.png',palette)
        svg(path/f'{name}_scene.svg',ink,col,palette);p=path/f'{name}_scene.svg';p.write_text(p.read_text().replace('Spring v05','v13_recovered_candidate - '+label));print('FULL',name,flush=True)
    grid([(path/f'{n}_full.png',l) for n,l in zip(['before','after'],labels)],path/'comparison.png','Spring source recovery - v12 control and reconstructed candidate',columns=2,cell=(800,1200),note='Same 600 x 900 mm, palette and display alpha. Original v13 PNG comparison is pending; no identity claim.')
    bounds=(0,630,310,875);panels=[]
    for name,label,(ink,col) in zip(['before','after'],labels,cases):
        p=path/f'{name}_left.png';render(ink,readable(col,c),p,palette,bounds,pixels=(1240,980));panels.append((p,label))
    grid(panels,path/'comparison_left.png','Matched left foreground / v12 to recovered candidate',columns=2,cell=(800,632),note='Only the recorded left foreground operation is reconstructed; right anchor and middle-distance receiving group stay.')
    rows=read_vectors(path/'removed_objects.json.gz')['strokes'];ii=[r for r in rows if 'palette_slot' not in r];cc=[r for r in rows if 'palette_slot' in r];render(ii,readable(cc,c),path/'removed_only.png',palette,bounds,pixels=(1240,980))
    ink,col=cases[1];ground=lambda r:r['source_family'] in ['A','B','C','D','Soil'] or r.get('color_kind') in ['terrain','Soil']
    render([r for r in ink if ground(r)],readable([r for r in col if ground(r)],c),path/'remaining_ground.png',palette,bounds,pixels=(1240,980))
    grid([(path/'removed_only.png','Removed object/contact cohorts'),(path/'remaining_ground.png','Remaining terrain + low ground cues')],path/'diagnostic_left.png','Source isolation / removed cohorts and remaining ground',columns=2,cell=(800,632),note='No raster tracing or blank image mask. The new geometry comes only from the inherited ground catalog.')
    print('RENDERED_RECOVERED_CANDIDATE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();run(Path(a.source))
