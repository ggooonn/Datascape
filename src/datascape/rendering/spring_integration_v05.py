"""Reproducible Spring v05 review; no toolpath scheduling, machine edits or publishing."""
from pathlib import Path
from copy import deepcopy
import argparse,io,json,gzip,html,hashlib
import numpy as np
import yaml
from PIL import Image,ImageDraw,ImageFont,ImageOps
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection,PolyCollection
from shapely.geometry import Polygon,LineString
from shapely.ops import unary_union
from datascape.rendering.spring_macro_study import write_gz,width_envelope
from datascape.rendering.spring_checkpoint import channels,verify
from datascape.strokes.vector import read_vectors
from datascape.integration.visibility import digest

ROOT=Path(__file__).resolve().parents[3]
CROPS=[('Foreground',(315,652,580,856)),('Middle',(310,510,535,665)),('Distant A',(235,245,415,410)),('Mist transition',(75,440,260,615))]
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def save_image(img,path):
    buf=io.BytesIO();img.save(buf,format='PNG');data=buf.getvalue()
    with Image.open(io.BytesIO(data)) as im:im.load()
    p=Path(path);tmp=p.with_name(p.name+'.pending');tmp.write_bytes(data);tmp.replace(p)


def display(rows,mode):
    rr=deepcopy(rows)
    for r in rr:
        value=r.get('preview_opacity',r.get('opacity',1.));a=np.asarray(r.get('opacity_profile',[value]*len(r['xy_mm'])))
        if mode=='opaque':a[:]=1.
        elif mode=='diagnostic':a=np.minimum(a*2.8,.83)
        r['opacity_profile']=a.tolist();r['preview_opacity']=float(a.mean())
    return rr


def render(ink,color,path,palette,bounds=(0,0,600,900),pixels=None,transparent=False):
    x0,y0,x1,y1=bounds;pw,ph=pixels or (int((x1-x0)*2),int((y1-y0)*2));dpi=150
    fig=plt.figure(figsize=(pw/dpi,ph/dpi),dpi=dpi,facecolor='none' if transparent else 'white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off');ax.patch.set_alpha(0)
    for rows,is_color in [(ink,False),(color,True)]:
        lines=[];widths=[];colors=[];polys=[];pc=[]
        for r in rows:
            p=np.array(r['xy_mm']);lo=p.min(axis=0);hi=p.max(axis=0)
            if hi[0]<x0 or lo[0]>x1 or hi[1]<y0 or lo[1]>y1:continue
            w=np.asarray(r.get('width_profile_mm',[r['width_mm']]*len(p)));a=np.asarray(r.get('opacity_profile',[r.get('preview_opacity',r.get('opacity',1.))]*len(p)))
            rgb=matplotlib.colors.to_rgb(palette['slots'][r['palette_slot']]['preview_hex']) if is_color else (0,0,0)
            if is_color and r.get('expressive_width_intent'):
                shape=width_envelope(r)
                for part in getattr(shape,'geoms',[shape]):
                    if part.geom_type=='Polygon':polys.append(np.asarray(part.exterior.coords));pc.append((*rgb,float(a.mean())))
            elif is_color:lines.append(p);widths.append(float(w.mean()));colors.append((*rgb,float(a.mean())))
            else:
                lines.extend(np.stack([p[:-1],p[1:]],axis=1));widths.extend((w[:-1]+w[1:])/2);colors.extend([(*rgb,float(v)) for v in (a[:-1]+a[1:])/2])
        ax.add_collection(LineCollection(lines,linewidths=np.asarray(widths)*pw/(x1-x0)*72/dpi,colors=colors,capstyle='round',joinstyle='round'))
        if polys:ax.add_collection(PolyCollection(polys,facecolors=pc,edgecolors='none'))
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=dpi,transparent=transparent,facecolor='none' if transparent else 'white');plt.close(fig)
    with Image.open(io.BytesIO(buf.getvalue())) as im:save_image(im,path)


def grid(panels,path,title,cell=(600,900),columns=3,note=''):
    cw,ch=cell;rows=int(np.ceil(len(panels)/columns));canvas=Image.new('RGB',(columns*cw+32,rows*(ch+55)+110),'#efeee8');d=ImageDraw.Draw(canvas)
    d.text((16,15),title,font=ImageFont.truetype(FONT,26),fill='#183d37');d.text((16,53),note,font=ImageFont.truetype(FONT,14),fill='#425951')
    for i,(p,label) in enumerate(panels):
        x=16+(i%columns)*cw;y=88+(i//columns)*(ch+55);d.text((x,y),label,font=ImageFont.truetype(FONT,18),fill='#183d37')
        with Image.open(p) as src:im=ImageOps.contain(src.convert('RGB'),(cw-14,ch))
        canvas.paste(im,(x+(cw-14-im.width)//2,y+31+(ch-im.height)//2))
    save_image(canvas,path)


def native_pdf(cases,palette,path):
    """Artwork in native mm, no fit-to-page. Preview widths are uncalibrated."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    cv=canvas.Canvas(str(path),pageCompression=1);cv.setTitle('Datascape Spring v05 - native artwork scale')
    def draw(ink,cols,bounds,left,top):
        x0,y0,x1,y1=bounds;cv.saveState();p=cv.beginPath();p.rect(left*mm,(top-y1+y0)*mm,(x1-x0)*mm,(y1-y0)*mm);cv.clipPath(p,stroke=0,fill=0)
        def points(coords):return [(float((left+x-x0)*mm),float((top-y+y0)*mm)) for x,y in coords]
        for rows,color in [(ink,False),(display(cols,'diagnostic'),True)]:
            for r in rows:
                xy=np.asarray(r['xy_mm']);lo=xy.min(axis=0);hi=xy.max(axis=0)
                if hi[0]<x0 or lo[0]>x1 or hi[1]<y0 or lo[1]>y1:continue
                rgb=matplotlib.colors.to_rgb(palette['slots'][r['palette_slot']]['preview_hex']) if color else (0,0,0)
                w=np.asarray(r.get('width_profile_mm',[r['width_mm']]*len(xy)));aa=r.get('opacity_profile',[r.get('preview_opacity',1.)]*len(xy));cv.setLineCap(1);cv.setLineJoin(1)
                if color and r.get('expressive_width_intent'):
                    shape=width_envelope(r);cv.setFillColorRGB(*rgb);cv.setFillAlpha(float(np.mean(aa)))
                    for geom in getattr(shape,'geoms',[shape]):
                        if geom.geom_type!='Polygon':continue
                        p=cv.beginPath();pts=points(geom.exterior.coords);p.moveTo(*pts[0])
                        for v in pts[1:]:p.lineTo(*v)
                        p.close();cv.drawPath(p,fill=1,stroke=0)
                else:
                    cv.setStrokeColorRGB(*rgb)
                    if color:
                        cv.setStrokeAlpha(float(np.mean(aa)));cv.setLineWidth(float(w.mean())*mm);p=cv.beginPath();pts=points(xy);p.moveTo(*pts[0])
                        for v in pts[1:]:p.lineTo(*v)
                        cv.drawPath(p)
                    else:
                        # Open mean-width ink centerline, matching SVG convention.
                        cv.setStrokeAlpha(float(np.mean(aa)));cv.setLineWidth(float(w.mean())*mm)
                        p=cv.beginPath();pts=points(xy);p.moveTo(*pts[0])
                        for v in pts[1:]:p.lineTo(*v)
                        cv.drawPath(p)
        cv.restoreState()
    def furniture(width,height,title):
        cv.setPageSize((width*mm,height*mm));cv.setFillColorRGB(.08,.2,.17);cv.setFont('Helvetica',13);cv.drawString(10*mm,(height-12)*mm,title)
        cv.setFont('Helvetica',8);cv.drawString(10*mm,14*mm,'Native mm - print 100%, no scaling. Mean-width ink; full profiles in JSON. Alpha/width are uncalibrated.')
        cv.setStrokeColorRGB(0,0,0);cv.setStrokeAlpha(1);cv.setLineWidth(.3*mm);cv.line(10*mm,8*mm,60*mm,8*mm);cv.drawString(64*mm,7*mm,'50 mm')
    for i,(ink,col) in enumerate(cases):
        furniture(620,940,f'Case {i} - continuous 600 x 900 mm');draw(ink,col,(0,0,600,900),10,915);cv.showPage()
    for label,b in CROPS:
        w,h=b[2]-b[0],b[3]-b[1];furniture(w*2+30,h+55,label+' - Case 0 / Case 2');draw(*cases[0],b,10,h+30);draw(*cases[2],b,w+20,h+30);cv.showPage()
    for label,b in CROPS[:3]:
        w,h=b[2]-b[0],b[3]-b[1];furniture(w*3+40,h+55,label+' - ink / color / combined');draw(cases[2][0],[],b,10,h+30);draw([],cases[2][1],b,w+20,h+30);draw(*cases[2],b,w*2+30,h+30);cv.showPage()
    cv.save()


def svg(path,ink,color,palette):
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="600mm" height="900mm" viewBox="0 0 600 900">','<title>Spring v05 - mean-width centerlines; full profiles in JSON, uncalibrated</title>']
    for records in [ink,color]:
        for r in records:
            xy=r['xy_mm'];d='M'+str(xy[0][0])+','+str(xy[0][1])+' '.join(' L'+str(x)+','+str(y) for x,y in xy[1:]);rgb=palette['slots'][r['palette_slot']]['preview_hex'] if 'palette_slot' in r else '#000000';w=np.mean(r.get('width_profile_mm',[r['width_mm']]));a=np.mean(r.get('opacity_profile',[r.get('preview_opacity',1.)]));ident=html.escape(r['id'],quote=True)
            parts.append(f'<path data-id="{ident}" d="{d}" fill="none" stroke="{rgb}" stroke-width="{w}" stroke-opacity="{a}" stroke-linecap="round" stroke-linejoin="round"/>')
    path.write_text('\n'.join(parts+['</svg>']))


def render_review(out,cases,channels_,config,fixed=None):
    palette=yaml.safe_load((ROOT/config['palette_source']).read_text());panels=[]
    for i,(ink,col) in enumerate(cases):
        for mode in ['restrained','diagnostic','opaque']:
            render(ink,display(col,mode),out/f'case{i}_{mode}.png',palette)
        render(ink,[],out/f'case{i}_ink.png',palette);render([],display(col,'diagnostic'),out/f'case{i}_color.png',palette)
        panels.append((out/f'case{i}_diagnostic.png',f'Case {i} / '+['Frozen v04','Revised ink, restrained color','Same ink, expanded vectors'][i]))
    grid(panels,out/'sheet01_full_comparison.png','Spring v05 - fixed 600 x 900 mm comparison',note='Same scale. Diagnostic alpha x2.8 for all. Case 1 and Case 2 share identical ink.')
    render(cases[2][0],display(cases[2][1],'restrained'),out/'case2_transparent.png',palette,transparent=True)
    crop_panels=[]
    for j,(label,b) in enumerate(CROPS):
        for i,(ink,col) in enumerate(cases):
            p=out/f'crop{j}_case{i}.png';render(ink,display(col,'diagnostic'),p,palette,b,pixels=(int((b[2]-b[0])*4),int((b[3]-b[1])*4)));crop_panels.append((p,f'{label} / Case {i}'))
    grid(crop_panels,out/'sheet02_native_crops.png','Matched scene crops - 4 pixels/mm sources',cell=(640,520),note='Each row has identical crop bounds; native physical scale is in PDF.')
    pp=[]
    for key,rr in channels_.items():
        p=out/f'channel_{key}.png';render([],display(rr,'diagnostic'),p,palette);pp.append((p,key))
    grid(pp,out/'sheet03_color_channels.png','Actual color supports isolated from ink',columns=3,cell=(450,675),note='A / C / rock-Soil / foliage / trunk / R-S-U. No area color fill.')
    svg(out/'case2_scene_centerlines.svg',cases[2][0],cases[2][1],palette);svg(out/'case2_color_centerlines.svg',[],cases[2][1],palette)
    native_pdf(cases,palette,out/'native_scale_review.pdf')
    if fixed is not None:
        focus=channels_.get('A',[])
        # Maps are nonplotting evidence, not additional scene paint.
        yy,xx=np.mgrid[:900,:600];q=fixed['base']['depth_m'];a=np.nan_to_num((q-250)/3150).clip(0,1)
        img=np.stack([255*(1-a*.55),255*(1-a*.35),255*(1-a*.15)],axis=-1).astype('uint8');img[~fixed['base']['occupied']]=255;save_image(Image.fromarray(img),out/'source_depth_map.png')


def save_geometry(out,native,forest,colors,config):
    ink=native['ink']+forest['ink']
    for name,rows in [('case12_ink',ink),('case1_color',colors['restrained']),('case2_color',colors['expanded'])]+[(f'channel_{k}',v) for k,v in colors['channels'].items()]:write_gz(out/(name+'.json.gz'),dict(continuous_mm=[600,900],strokes=rows))
    write_gz(out/'source_ledger.json.gz',dict(native_sources=native['new_sources'],terrain_decisions=native['terrain_ledger'],native_decisions=native['object_ledger'],RSU_sources=forest['raw'],RSU_visibility=sorted([d for d in forest['visibility'] if d.get('removed_mm',0)>1e-9],key=digest),color_raw=colors['raw'],color_feathered_sources=colors['sources'],color_visibility=colors['visibility'],color_feather=colors['feather']))
    (out/'sites.json').write_text(json.dumps(dict(native=native['sites'],RSU=forest['sites'],rejected=forest['rejected'],carrier_links=forest['links']),indent=2)+'\n')
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n');(out/'D_anchors.json').write_text(json.dumps(colors['anchors'],indent=2)+'\n')


def run(master,veg,output,config=ROOT/'configs/scenes/seoul_spring_integration_v05.json'):
    from datascape.strokes.scene import load_selected_scene
    from datascape.integration.diverse_scene import resolve_diverse
    from datascape.integration.spring_unified_v05 import build_forest,build_colors
    from datascape.integration.spring_v05_audit import audit
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Use a new output directory')
    c=json.loads(Path(config).read_text());verify();fixed=load_selected_scene(master,veg,ROOT,json.loads((ROOT/'configs/scenes/seoul_spring_selected_C.json').read_text()));baseline=read_vectors(ROOT/c['baseline'])['strokes'];corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']])
    native=resolve_diverse(fixed,baseline,c,corridor);forest=build_forest(fixed,native,c,corridor);colors=build_colors(fixed,native,forest,c,corridor);save_geometry(out,native,forest,colors,c);audit(fixed,native,forest,colors,c,out,baseline)
    ci,cc=channels();render_review(out,[(ci,cc['caseC']),(native['ink']+forest['ink'],colors['restrained']),(native['ink']+forest['ink'],colors['expanded'])],colors['channels'],c,fixed)


def replay(source,output):
    src=Path(source);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError('Use a new output directory')
    c=json.loads((src/'config.json').read_text());ink=read_vectors(src/'case12_ink.json.gz')['strokes'];c1=read_vectors(src/'case1_color.json.gz')['strokes'];c2=read_vectors(src/'case2_color.json.gz')['strokes'];ch={k:read_vectors(src/f'channel_{k}.json.gz')['strokes'] for k in ['A','C','rock_soil','gestures','trunk','RSU']};ci,cc=channels();verify();render_review(out,[(ci,cc['caseC']),(ink,c1),(ink,c2)],ch,c)
    result={}
    for name in ['case1_diagnostic.png','case2_diagnostic.png']:
        with Image.open(src/name) as a,Image.open(out/name) as b:result[name]=bool(np.array_equal(np.asarray(a),np.asarray(b)))
    (out/'saved_replay_validation.json').write_text(json.dumps(result,indent=2)+'\n');assert all(result.values());return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--master');p.add_argument('--veg');p.add_argument('--output',required=True);p.add_argument('--replay-from');a=p.parse_args()
    if a.replay_from:print(replay(a.replay_from,a.output))
    elif a.master and a.veg:run(a.master,a.veg,a.output)
    else:p.error('Provide --replay-from or both --master and --veg')
if __name__=='__main__':main()
