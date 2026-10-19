"""Same-scale v10_3/v11 review and isolated patch/C/far diagnostics."""
from pathlib import Path
import argparse,json
import yaml
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg
from datascape.rendering.spring_massing_v07 import readable

ROOT=Path(__file__).resolve().parents[3]
CROPS=[('anchor',(325,570,590,825)),('patch',(330,770,590,885)),('transition',(335,560,590,790)),('far',(20,265,585,525))]


def run(path):
    c=json.load(open(path/'config.json'));palette=yaml.safe_load((ROOT/c['palette_source']).read_text());cases=[];labels=['Control / v10_3','Refinement / v11']
    for name,label in zip(['before','after'],labels):
        ink=read_vectors(path/f'{name}_ink.json.gz')['strokes'];col=read_vectors(path/f'{name}_color.json.gz')['strokes'];cases.append((ink,col))
        for mode in ['full','ink','color']:render([] if mode=='color' else ink,[] if mode=='ink' else readable(col,c),path/f'{name}_{mode}.png',palette)
        svg(path/f'{name}_scene.svg',ink,col,palette);p=path/f'{name}_scene.svg';p.write_text(p.read_text().replace('Spring v05','Spring v11 - '+label));print('FULL',name,flush=True)
    grid([(path/f'{n}_full.png',label) for n,label in zip(['before','after'],labels)],path/'comparison.png','Spring v11 - focused refinement of v10_3',columns=2,cell=(800,1200),note='Same 600 x 900 mm, palette and display alpha. A/B/D/rock ink and A color remain exact.')
    for zone,bounds in CROPS:
        pp=[]
        for name,label,(ink,col) in zip(['before','after'],labels,cases):
            p=path/f'{name}_{zone}.png';render(ink,readable(col,c),p,palette,bounds,pixels=(int((bounds[2]-bounds[0])*4),int((bounds[3]-bounds[1])*4)));pp.append((p,label))
        ratio=(bounds[3]-bounds[1])/(bounds[2]-bounds[0]);grid(pp,path/f'comparison_{zone}.png','Matched '+zone+' / v10_3 to v11',columns=2,cell=(800,int(800*ratio)),note='Identical local bounds and magnification within the pair.');print('CROP',zone,flush=True)
    panels=[];bounds=(330,755,595,888)
    for kind,title in [('C','Terrain C color'),('Soil','Soil ink + color'),('low','Low-right planting + attached ground')]:
        for name,label,(ink,col) in zip(['before','after'],labels,cases):
            if kind=='C':ii=[];cc=read_vectors(path/f'{name}_channel_C.json.gz')['strokes']
            elif kind=='Soil':ii=[r for r in ink if r['source_family']=='Soil'];cc=[r for r in col if r.get('color_kind')=='Soil']
            else:
                ii=[r for r in ink if 'near-right-shrubs' in r.get('owner_id','')];cc=[r for r in col if 'near-right-shrubs' in r.get('owner_id','')]
            p=path/f'{name}_source_{kind}.png';render(ii,readable(cc,c),p,palette,bounds,pixels=(1060,532));panels.append((p,title+' / '+label))
    grid(panels,path/'diagnostic_patch.png','Actual patch contributors / isolated before and after',columns=2,cell=(800,410),note='C, Soil and low-right planting are separate sources. A color is unchanged and remains visible in the full crop.')
    panels=[];bounds=CROPS[-1][1]
    for name,label,(ink,col) in zip(['before','after'],labels,cases):
        rr=[r for r in col if r['source_family']=='RSU' and r.get('source_forward_m',0)>=1900];ii=[r for r in ink if r['source_family']=='RSU' and r.get('source_forward_m',0)>=1900];p=path/f'{name}_far_RSU.png';render(ii,readable(rr,c),p,palette,bounds,pixels=(1695,780));panels.append((p,label))
    grid(panels,path/'diagnostic_far.png','Far R/S/U only / inherited depth palette and mist',columns=2,cell=(1000,460),note='Unequal local additions, not a uniform density multiplier. Native far trees omitted in this isolated source view.')
    print('RENDERED_V11',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();run(Path(a.source))
