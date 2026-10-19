"""Focused v05/v06 comparisons with matched readable, semi-transparent display."""
from pathlib import Path
from copy import deepcopy
import json,pickle,argparse,hashlib,io
import numpy as np
import yaml
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg,save_geometry,save_image
from datascape.rendering.spring_macro_study import write_gz
from datascape.integration.visibility import digest

ROOT=Path(__file__).resolve().parents[3]
CROPS=[('Left bench / broad lateral flow',(0,435,310,555)),('Right passage / staggered emergence',(385,335,600,610)),('Far slopes / A and vegetation',(130,245,545,415)),('Foreground / related rock-ground masses',(0,620,600,865))]


def readable(rows,c):
    """Display-only copy: no geometry, palette, ID, or physical dilution changes."""
    out=deepcopy(rows);ctl=c['readable_display']
    for r in out:
        a=np.array(r.get('opacity_profile',[r.get('preview_opacity',1.)]*len(r['xy_mm'])))*ctl['alpha_multiplier'];a=np.clip(a,ctl['minimum_alpha'],ctl['maximum_alpha']);r['opacity_profile']=a.tolist();r['preview_opacity']=float(a.mean())
    return out


def pdf_review(cases,palette,out,c):
    from datascape.rendering import spring_integration_v05 as helper
    from pypdf import PdfReader,PdfWriter
    previous=helper.CROPS;helper.CROPS=CROPS
    adjusted=[]
    for ink,color in cases:
        cc=readable(color,c)
        for r in cc:r['opacity_profile']=(np.array(r['opacity_profile'])/2.8).tolist()
        adjusted.append((ink,cc))
    try:helper.native_pdf(adjusted,palette,out/'native_scale_review.pending.pdf')
    finally:helper.CROPS=previous
    reader=PdfReader(out/'native_scale_review.pending.pdf');w=PdfWriter();w.clone_document_from_reader(reader);w.add_metadata({'/Title':'Datascape Spring v06 - landscape continuity at native mm'})
    buf=io.BytesIO();w.write(buf);data=buf.getvalue();assert len(PdfReader(io.BytesIO(data)).pages)==10
    tmp=out/'native_scale_review.complete';tmp.write_bytes(data);tmp.replace(out/'native_scale_review.pdf')
    (out/'native_scale_review.pending.pdf').unlink()


def render_all(out,native,forest,colors,c,zones=None,field=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);palette=yaml.safe_load((ROOT/c['palette_source']).read_text());control=ROOT/'outputs/spring-integration-v05'
    oldink=read_vectors(control/'case12_ink.json.gz')['strokes'];oldcolor=read_vectors(control/'case2_color.json.gz')['strokes'];ink=native['ink']+forest['ink']
    cases=[(oldink,oldcolor),(ink,colors['restrained']),(ink,colors['expanded'])]
    panels=[]
    for i,(ii,cc) in enumerate(cases):
        render(ii,readable(cc,c),out/f'case{i}_readable.png',palette);render(ii,[],out/f'case{i}_ink.png',palette);render([],readable(cc,c),out/f'case{i}_color.png',palette)
        opaque=deepcopy(cc)
        for r in opaque:r['opacity_profile']=[1.]*len(r['xy_mm'])
        render(ii,opaque,out/f'case{i}_opaque.png',palette);panels.append((out/f'case{i}_readable.png',['0 / v05 - matched visibility','1 / v06 zones - restrained A/C','2 / v06 zones - extended A/C'][i]))
    grid(panels,out/'sheet01_full_comparison.png','Spring v06 - large zones and legible color supports',note='All three use the SAME readable alpha policy, still translucent. Cases 1 and 2 share exactly one ink set.')
    from datascape.rendering.spring_integration_v05 import display
    render(oldink,display(oldcolor,'diagnostic'),out/'v05_original_visibility.png',palette)
    crop_panels=[]
    for j,(label,bounds) in enumerate(CROPS):
        for i,(ii,cc) in enumerate(cases):
            path=out/f'crop{j}_case{i}.png';render(ii,readable(cc,c),path,palette,bounds,pixels=(int((bounds[2]-bounds[0])*3),int((bounds[3]-bounds[1])*3)));crop_panels.append((path,label+f' / Case {i}'))
    grid(crop_panels,out/'sheet02_flow_crops.png','Related whole-terrain passages - matched crops',columns=3,cell=(660,430),note='Each row shares exact bounds. The PDF carries artwork at native millimeters.')
    pp=[]
    for key,oldname in [('A','channel_A.json.gz'),('C','channel_C.json.gz'),('RSU','channel_RSU.json.gz')]:
        old=read_vectors(control/oldname)['strokes']
        for label,rr in [('v05',old),('v06',colors['channels'][key])]:
            path=out/f'{label}_{key}_color.png';render([],readable(rr,c),path,palette);pp.append((path,label+' / '+key+' supports only'))
    grid(pp,out/'sheet03_color_structure.png','Actual vectors separated from ink',columns=2,cell=(520,780),note='Matched translucent visibility. No terrain/canopy region fills. A and C growth is actual geometry.')
    render(ink,readable(colors['expanded'],c),out/'case2_transparent.png',palette,transparent=True)
    svg(out/'case2_scene_centerlines.svg',ink,colors['expanded'],palette)
    svg(out/'case2_color_centerlines.svg',[],colors['expanded'],palette)
    for name in ['case2_scene_centerlines.svg','case2_color_centerlines.svg']:
        p=out/name;p.write_text(p.read_text().replace('Spring v05','Spring v06'))
    if zones is not None:
        base=Image.open(out/'case2_ink.png').convert('RGB');d=ImageDraw.Draw(base);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
        for i,z in enumerate(zones):
            pts=np.array([a['site']['xy_mm'] for a in z['anchors']])*2;col=['#b75a25','#47795b','#85763d'][i%3];d.line([tuple(v) for v in pts],fill=col,width=4)
            for p in pts:d.ellipse((p[0]-3,p[1]-3,p[0]+3,p[1]+3),fill=col)
            d.text(tuple(pts[len(pts)//2]+[4,-23]),f'Z{i+1}',font=font,fill=col)
        save_image(base,out/'zone_hierarchy_map.png')
    pdf_review(cases,palette,out,c)


def run(master,veg,output):
    from datascape.strokes.scene import load_selected_scene
    from datascape.integration.diverse_scene import resolve_diverse
    from datascape.integration.landscape_flow_v06 import prepare_zones,build_flow_forest,build_flow_colors
    from datascape.integration.continuity_audit_v06 import audit
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Use a new output directory')
    c=json.loads((ROOT/'configs/scenes/seoul_spring_integration_v06.json').read_text());f=load_selected_scene(master,veg,ROOT,json.loads((ROOT/'configs/scenes/seoul_spring_selected_C.json').read_text()));b=read_vectors(ROOT/c['baseline'])['strokes'];co=unary_union([Polygon(x['vertices_mm']) for x in c['corridors']]);native=resolve_diverse(f,b,c,co);zones,field=prepare_zones(f,c);forest=build_flow_forest(f,native,c,co,zones);colors=build_flow_colors(f,native,forest,c,co,field);save_geometry(out,native,forest,colors,c);audit(f,native,forest,colors,c,zones,field,out,b);render_all(out,native,forest,colors,c,zones,field)


def replay(source,output):
    src=Path(source);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Use a new output directory')
    c=json.loads((src/'config.json').read_text());ink=read_vectors(src/'case12_ink.json.gz')['strokes'];color={name:read_vectors(src/(name+'.json.gz'))['strokes'] for name in ['case1_color','case2_color']};channels={k:read_vectors(src/f'channel_{k}.json.gz')['strokes'] for k in ['A','C','rock_soil','gestures','trunk','RSU']};render_all(out,dict(ink=ink),dict(ink=[]),dict(restrained=color['case1_color'],expanded=color['case2_color'],channels=channels),c)
    same={}
    for i in range(3):
        name=f'case{i}_readable.png'
        with Image.open(src/name) as a,Image.open(out/name) as b:same[name]=bool(np.array_equal(np.asarray(a),np.asarray(b)))
    (out/'replay_validation.json').write_text(json.dumps(same,indent=2)+'\n');assert all(same.values());return same


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--master');p.add_argument('--veg');p.add_argument('--output',required=True);p.add_argument('--replay-from');a=p.parse_args()
    if a.replay_from:print(replay(a.replay_from,a.output))
    elif a.master and a.veg:run(a.master,a.veg,a.output)
    else:p.error('Supply --replay-from or both TIFF arguments')
if __name__=='__main__':main()
