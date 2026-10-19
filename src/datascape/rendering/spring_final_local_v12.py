"""Matched v11/v12 review with local source diagnostics only."""
from pathlib import Path
import argparse,json
import yaml
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg
from datascape.rendering.spring_massing_v07 import readable

ROOT=Path(__file__).resolve().parents[3]
CROPS=[('right_pair',(330,555,595,825)),('left_vegetation',(95,640,285,765)),('left_ground',(10,735,280,855))]


def run(path):
    c=json.load(open(path/'config.json'));palette=yaml.safe_load((ROOT/c['palette_source']).read_text());labels=['Control / v11','Final local candidate / v12'];cases=[]
    for name,label in zip(['before','after'],labels):
        ink=read_vectors(path/f'{name}_ink.json.gz')['strokes'];col=read_vectors(path/f'{name}_color.json.gz')['strokes'];cases.append((ink,col))
        for mode in ['full','ink','color']:render([] if mode=='color' else ink,[] if mode=='ink' else readable(col,c),path/f'{name}_{mode}.png',palette)
        svg(path/f'{name}_scene.svg',ink,col,palette);p=path/f'{name}_scene.svg';p.write_text(p.read_text().replace('Spring v05','Spring v12 - '+label));print('FULL',name,flush=True)
    grid([(path/f'{n}_full.png',label) for n,label in zip(['before','after'],labels)],path/'comparison.png','Spring v12 - paired right anchor and open left foreground ground',columns=2,cell=(800,1200),note='Same 600 x 900 mm, palette and display alpha. Fixed A/B/D ink, A color, far vegetation and global mist are preserved.')
    for zone,bounds in CROPS:
        panels=[]
        for name,label,(ink,col) in zip(['before','after'],labels,cases):
            p=path/f'{name}_{zone}.png';render(ink,readable(col,c),p,palette,bounds,pixels=(int((bounds[2]-bounds[0])*4),int((bounds[3]-bounds[1])*4)));panels.append((p,label))
        grid(panels,path/f'comparison_{zone}.png','Matched '+zone+' / v11 to v12',columns=2,cell=(800,int(800*(bounds[3]-bounds[1])/(bounds[2]-bounds[0]))),note='Identical local bounds and magnification.');print('CROP',zone,flush=True)
    panels=[];bounds=(95,640,285,765)
    for kind,title in [('RSU','Receiving R/S/U'),('native','Native tree foliage'),('Soil','Soil ink + color')]:
        for name,label,(ink,col) in zip(['before','after'],labels,cases):
            if kind=='RSU':ii=[r for r in ink if r['source_family']=='RSU'];cc=[r for r in col if r['source_family']=='RSU']
            elif kind=='native':ii=[r for r in ink if r['source_family']=='tree'];cc=[r for r in col if r.get('color_kind')=='vegetation' and r['source_family']!='RSU']
            else:ii=[r for r in ink if r['source_family']=='Soil'];cc=[r for r in col if r.get('color_kind')=='Soil']
            p=path/f'{name}_source_{kind}.png';render(ii,readable(cc,c),p,palette,bounds,pixels=(950,625));panels.append((p,title+' / '+label))
    grid(panels,path/'diagnostic_left.png','Left accumulation / actual contributors',columns=2,cell=(800,530),note='Separate R/S/U, native tree canopy and Soil. Low vegetation replaces crowded source units; native trees stay intact.')
    panels=[];bounds=CROPS[0][1];owners={'v03/tree/near-right-exposure/behind-main','v03/tree/near-right-exposure/emerging-crown'}
    for name,label,(ink,col) in zip(['before','after'],labels,cases):
        ii=[r for r in ink if r['owner_id'] in owners or (r['source_family']=='rock' and 'near-right-exposure' in r['owner_id'])];cc=[r for r in col if r['owner_id'] in owners or (r.get('color_kind')=='rock' and 'near-right-exposure' in r['owner_id'])];p=path/f'{name}_pair_only.png';render(ii,readable(cc,c),p,palette,bounds,pixels=(1060,1080));panels.append((p,label))
    grid(panels,path/'diagnostic_pair.png','Two related P trees + rocks / source-depth grouping',columns=2,cell=(750,765),note='Two exact existing roots at different source q. Near rocks mask bases; the nearer main selectively masks the deeper secondary.')
    ink,col=cases[1];bounds=CROPS[2][1];p=path/'new_ground_only.png';render([r for r in ink if r.get('v12_rule')=='open-left-ground-patch'],readable([r for r in col if r.get('v12_rule')=='restrained-left-C-ground-cue'],c),p,palette,bounds,pixels=(1350,600))
    print('RENDERED_V12',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();run(Path(a.source))
