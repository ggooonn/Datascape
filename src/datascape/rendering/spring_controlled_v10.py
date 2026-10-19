"""Matched-scale review surfaces for the four Spring v10 cases."""
from pathlib import Path
from copy import deepcopy
import json,argparse
import yaml
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg
from datascape.rendering.spring_massing_v07 import readable

ROOT=Path(__file__).resolve().parents[3]
NAMES=['baseline','v10_1','v10_2','v10_3']
LABELS=['Control / v09','v10_1 / shared updates','v10_2 / right vertical + open left','v10_3 / low left + near-middle relay']
CROPS=[('foreground',(0,610,600,875)),('middle',(0,445,600,700)),('far',(45,310,565,500))]


def run(path):
    c=json.load(open(path/'config.json'));palette=yaml.safe_load((ROOT/c['palette_source']).read_text());cases={}
    for name in NAMES:
        ink=read_vectors(path/f'{name}_ink.json.gz')['strokes'];col=read_vectors(path/f'{name}_color.json.gz')['strokes'];cases[name]=(ink,col)
        for mode in ['full','ink','color']:
            render([] if mode=='color' else ink,[] if mode=='ink' else readable(col,c),path/f'{name}_{mode}.png',palette)
        print('FULL',name,flush=True)
        svg(path/f'{name}_scene.svg',ink,col,palette)
        sp=path/f'{name}_scene.svg';sp.write_text(sp.read_text().replace('Spring v05','Spring v10 / '+name))
    grid([(path/f'{n}_full.png',label) for n,label in zip(NAMES,LABELS)],path/'comparison.png','Spring v10 - controlled shared refinement and foreground composition',columns=4,cell=(650,975),note='Same 600 x 900 mm artwork, scale, palette and display alpha. v10_2 and v10_3 branch from shared v10_1.')
    for label,bounds in CROPS:
        panels=[]
        for name,case_label in zip(NAMES,LABELS):
            ink,col=cases[name];p=path/f'{name}_{label}.png';render(ink,readable(col,c),p,palette,bounds,pixels=(1800,int((bounds[3]-bounds[1])/(bounds[2]-bounds[0])*1800)));panels.append((p,case_label))
        grid(panels,path/f'comparison_{label}.png','Matched '+label+' / same source bounds',columns=2,cell=(1050,int((bounds[3]-bounds[1])/(bounds[2]-bounds[0])*1050)),note='Top row: control, v10_1. Bottom row: v10_2, v10_3. No independent crop rescaling.')
        print('CROP',label,flush=True)
    panels=[]
    for name,label in zip(NAMES[:2],LABELS[:2]):
        ink,col=cases[name];aa=read_vectors(path/f'{name}_channel_A.json.gz')['strokes'];bounds=(75,310,560,710);p=path/f'{name}_A_diagnostic.png'
        render([r for r in ink if r['source_family']=='A'],readable(aa,c),p,palette,bounds,pixels=(1455,1200));panels.append((p,label))
    grid(panels,path/'diagnostic_A.png','A ink + displaced A color / control vs shared update',columns=2,cell=(730,605),note='Ink baseline unchanged. Geometry displacement changes; pigment widths and display alpha do not change.')
    candidates=read_vectors(path/'v10_1_channel_A.json.gz')['strokes']
    import numpy as np
    candidates=[r for r in candidates if 340<np.mean(np.array(r['xy_mm'])[:,1])<600]
    chosen=max(candidates,key=lambda r:np.mean(r['v10_added_displacement_mm']))
    cx,cy=np.mean(chosen['xy_mm'],axis=0);bounds=(float(cx-32),float(cy-22),float(cx+32),float(cy+22));panels=[]
    for name,label in zip(NAMES[:2],LABELS[:2]):
        ink,col=cases[name];aa=read_vectors(path/f'{name}_channel_A.json.gz')['strokes'];p=path/f'{name}_A_detail.png'
        render([r for r in ink if r['source_family']=='A'],readable(aa,c),p,palette,bounds,pixels=(1280,880));panels.append((p,label))
    grid(panels,path/'diagnostic_A_detail.png','A displacement / matched 64 x 44 mm detail',columns=2,cell=(800,550),note='Identical local bounds at 20 pixels/mm in source images; local normal shift remains sub-millimeter.')
    panels=[]
    for name,label in zip(NAMES[:2],LABELS[:2]):
        ink,col=cases[name];rr=[r for r in col if r['source_family']=='RSU'];ii=[r for r in ink if r['source_family']=='RSU'];bounds=(0,340,600,735);p=path/f'{name}_RSU_diagnostic.png'
        render(ii,readable(rr,c),p,palette,bounds,pixels=(1800,1185));panels.append((p,label))
    grid(panels,path/'diagnostic_RSU.png','Receiving R/S/U vegetation / control vs shared update',columns=2,cell=(900,593),note='Native foreground canopies and terrain omitted only in this diagnostic. New small units use existing R/S/U generators.')
    name='v10_1';ink,col=cases[name];render([r for r in ink if r.get('v10_new_site_id')],readable([r for r in col if r.get('v10_new_site_id')],c),path/'new_small_units.png',palette,(0,340,600,735),pixels=(1800,1185))
    print('REVIEW_RENDERED',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();run(Path(a.source))
