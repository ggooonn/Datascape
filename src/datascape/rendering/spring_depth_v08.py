"""Three cumulative Spring v08 comparisons from archived, plotter-intent vectors.

Case 0 is frozen v07. Case 1 changes terrain color only. Case 2 also rebuilds
native placement and porous R/S/U growth patches. No machine output is made.
"""
from pathlib import Path
from copy import deepcopy
import argparse,io,json,hashlib
import numpy as np
import yaml
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg,save_geometry
from datascape.rendering.spring_massing_v07 import readable
from datascape.rendering.spring_macro_study import write_gz

ROOT=Path(__file__).resolve().parents[3]
CROPS=[('Far A episodes and quiet C',(165,250,550,415)),('Middle vegetation / small rocks',(350,420,595,615)),('Upward foreground activity',(30,565,305,750)),('Foreground C and ground openings',(15,690,590,870))]
LABELS=['0 / v07 - frozen control','1 / v08 - terrain A/C only','2 / v08 - terrain + porous clusters']


def color_variant(rows,c,mode):
    if mode=='readable':return readable(rows,c)
    cc=deepcopy(rows)
    if mode=='opaque':
        for r in cc:r['opacity_profile']=[1.]*len(r['xy_mm']);r['preview_opacity']=1.
    return cc


def pdf(cases,palette,out,c):
    from datascape.rendering import spring_integration_v05 as helper
    from pypdf import PdfReader,PdfWriter
    crops=helper.CROPS;helper.CROPS=CROPS
    adjusted=[]
    for ink,color in cases:
        cc=readable(color,c)
        for r in cc:r['opacity_profile']=(np.array(r['opacity_profile'])/2.8).tolist()
        adjusted.append((ink,cc))
    try:helper.native_pdf(adjusted,palette,out/'native_scale_review.pending.pdf')
    finally:helper.CROPS=crops
    reader=PdfReader(out/'native_scale_review.pending.pdf');writer=PdfWriter();writer.clone_document_from_reader(reader)
    writer.add_metadata({'/Title':'Datascape Spring v08 - 0 v07, 1 terrain only, 2 full revision'})
    buf=io.BytesIO();writer.write(buf);(out/'native_scale_review.pdf').write_bytes(buf.getvalue());(out/'native_scale_review.pending.pdf').unlink()


def render_saved(out,include_pdf=True):
    out=Path(out);c=json.loads((out/'config.json').read_text());palette=yaml.safe_load((ROOT/c['palette_source']).read_text())
    cases=[tuple(read_vectors(out/f'case{i}_{k}.json.gz')['strokes'] for k in ['ink','color']) for i in range(3)]
    panels=[]
    for i,(ink,color) in enumerate(cases):
        for mode in ['readable','opaque']:render(ink,color_variant(color,c,mode),out/f'case{i}_{mode}.png',palette)
        render(ink,[],out/f'case{i}_ink.png',palette);render([],readable(color,c),out/f'case{i}_color.png',palette)
        panels.append((out/f'case{i}_readable.png',LABELS[i]))
    grid(panels,out/'sheet01_full_comparison.png','Spring v08 - depth, terrain episodes and porous clusters',note='Matched translucent display. Case 0 / 1 share exact ink and placement; Case 2 also changes objects and vegetation.')
    panels=[]
    for j,(label,bounds) in enumerate(CROPS):
        for i,(ii,cc) in enumerate(cases):
            path=out/f'crop{j}_case{i}.png';render(ii,readable(cc,c),path,palette,bounds,pixels=(int((bounds[2]-bounds[0])*3),int((bounds[3]-bounds[1])*3)));panels.append((path,label+f' / {i}'))
    grid(panels,out/'sheet02_crops.png','Matched crops - cumulative changes',columns=3,cell=(660,450),note='Each row shares exact bounds. Foreground rises on existing side benches; central reserves and global mist remain fixed.')
    panels=[]
    for channel in ['A','C','vegetation']:
        for i in range(3):
            keys=['RSU','gestures'] if channel=='vegetation' else [channel]
            rows=sum((read_vectors(out/f'case{i}_channel_{k}.json.gz')['strokes'] for k in keys),[])
            path=out/f'isolated_{channel}_{i}.png';render([],readable(rows,c),path,palette);panels.append((path,channel+' / Case '+str(i)))
    grid(panels,out/'sheet03_layers.png','Actual A / C / vegetation color vectors',columns=3,cell=(430,645),note='Same alpha and scale in every panel. No filled region, guide spine, or raster texture contributes to the scene.')
    # A readable diagnostic at larger size for far episode lengths and palette transitions.
    panels=[];bounds=(155,245,580,445)
    for i in range(3):
        rows=read_vectors(out/f'case{i}_channel_A.json.gz')['strokes'];path=out/f'A_detail_{i}.png';render([],readable(rows,c),path,palette,bounds,pixels=(1700,800));panels.append((path,LABELS[i]))
    grid(panels,out/'sheet04_A_episodes.png','Middle / far A color - same crop without ink',columns=1,cell=(1500,705),note='Gaps are actual missing path intervals. Existing A ink remains continuous where the baseline calls for it.')
    svg(out/'case2_scene_centerlines.svg',*cases[2],palette);svg(out/'case2_color_centerlines.svg',[],cases[2][1],palette)
    for name in ['case2_scene_centerlines.svg','case2_color_centerlines.svg']:
        path=out/name;path.write_text(path.read_text().replace('Spring v05','Spring v08'))
    if include_pdf:pdf(cases,palette,out,c)
    return cases


def save(out,native,forest,colors,c,control=None):
    from datascape.integration.landscape_depth_v08 import refine_terrain
    out=Path(out);out.mkdir(parents=True,exist_ok=True);old=ROOT/'outputs/spring-integration-v07'
    if control is None:
        control={k:read_vectors(old/f'channel_{k}.json.gz')['strokes'] for k in ['A','C','rock_soil','gestures','trunk','RSU']}
        for k in ['A','C']:control[k],_=refine_terrain(control[k],native['_fixed_for_control'],c,k)
    save_geometry(out,native,forest,colors,c)
    (out/'case12_ink.json.gz').rename(out/'case2_ink.json.gz')
    oldink=read_vectors(old/'case12_ink.json.gz')['strokes'];oldcolor=read_vectors(old/'case2_color.json.gz')['strokes']
    for name,rows in [('case0_ink',oldink),('case1_ink',oldink),('case0_color',oldcolor),('case1_color',sum(control.values(),[]))]:
        write_gz(out/(name+'.json.gz'),dict(continuous_mm=[600,900],strokes=rows))
    for i in range(3):
        channels={k:read_vectors(old/f'channel_{k}.json.gz')['strokes'] for k in colors['channels']} if i==0 else control if i==1 else colors['channels']
        for k,rows in channels.items():write_gz(out/f'case{i}_channel_{k}.json.gz',dict(continuous_mm=[600,900],strokes=rows))


def run(master,veg,output):
    from datascape.strokes.scene import load_selected_scene
    from datascape.integration.diverse_scene import resolve_diverse
    from datascape.integration.landscape_depth_v08 import prepare_zones,build_flow_forest,build_flow_colors,apply_depth_color,refine_terrain
    from datascape.integration.depth_audit_v08 import audit
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Use a new output directory')
    c=json.loads((ROOT/'configs/scenes/seoul_spring_integration_v08.json').read_text());f=load_selected_scene(master,veg,ROOT,json.loads((ROOT/'configs/scenes/seoul_spring_selected_C.json').read_text()));baseline=read_vectors(ROOT/c['baseline'])['strokes'];co=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']]);n=resolve_diverse(f,baseline,c,co);zs,field=prepare_zones(f,c);fo=build_flow_forest(f,n,c,co,zs);cs=apply_depth_color(build_flow_colors(f,n,fo,c,co,field),f,c)
    control={k:read_vectors(ROOT/f'outputs/spring-integration-v07/channel_{k}.json.gz')['strokes'] for k in cs['channels']}
    for k in ['A','C']:control[k],_=refine_terrain(control[k],f,c,k)
    save(out,n,fo,cs,c,control);audit(f,n,fo,cs,c,zs,out,baseline);return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--master');p.add_argument('--veg');p.add_argument('--output',required=True);p.add_argument('--replay-from');p.add_argument('--vectors-only',action='store_true');a=p.parse_args()
    if a.replay_from:
        src=Path(a.replay_from);out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
        for item in src.iterdir():
            if item.suffix in ['.gz','.json']:(out/item.name).write_bytes(item.read_bytes())
        render_saved(out)
        same={f'case{i}_readable.png':bool(np.array_equal(np.array(Image.open(src/f'case{i}_readable.png')),np.array(Image.open(out/f'case{i}_readable.png')))) for i in range(3)}
        (out/'replay_validation.json').write_text(json.dumps(same,indent=2)+'\n');assert all(same.values());print(same)
    elif a.master and a.veg:
        out=run(a.master,a.veg,a.output)
        if not a.vectors_only:render_saved(out)
    else:p.error('Supply --replay-from or both original TIFFs')
if __name__=='__main__':main()
