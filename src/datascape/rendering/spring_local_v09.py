"""Matched v08/v09 source diagnostics; review only, no machine output."""
from pathlib import Path
from copy import deepcopy
import argparse,json,io
import numpy as np
import yaml,matplotlib
from PIL import Image
from datascape.strokes.vector import read_vectors
from datascape.rendering.spring_integration_v05 import render,grid,svg,display
from datascape.rendering.spring_macro_study import width_envelope
from datascape.rendering.spring_massing_v07 import readable
ROOT=Path(__file__).resolve().parents[3]
CROPS=[('Left canopy / deeper RSU',(100,615,300,770)),('Right canopy / deeper RSU',(400,570,590,720)),('Visible roots / A and Soil',(70,765,250,860)),('Lower-middle hatch stack',(205,590,405,730))]
SOURCE_KEYS=['A_ink','A_color','C_color','Soil_ink','tree_ground_ink','Soil_color','rock_ink']
SOURCE_LABELS=['A ink - unchanged','A-derived color','C color','Shared Soil ink','Tree grounding','Soil color','Rock structure - unchanged']


def load(p):
 p=Path(p);return json.load(open(p/'config.json')),[tuple(read_vectors(p/f'case{i}_{k}.json.gz')['strokes'] for k in ['ink','color']) for i in range(2)]


def render_review(path):
 path=Path(path);c,cases=load(path);palette=yaml.safe_load((ROOT/c['palette_source']).read_text());panels=[]
 for i,(ink,col) in enumerate(cases):
  for mode in ['readable','ink','color','opaque']:
   cc=readable(col,c) if mode in ['readable','color'] else deepcopy(col)
   if mode=='opaque':
    for r in cc:r['opacity_profile']=[1.]*len(r['xy_mm'])
   render([] if mode=='color' else ink,[] if mode=='ink' else cc,path/f'case{i}_{mode}.png',palette)
  panels.append((path/f'case{i}_readable.png',['Before / v08 Case 2','After / v09'][i]))
 grid(panels,path/'sheet01_full_comparison.png','Spring v09 - bounded local refinement',columns=2,note='Identical 600 x 900 mm and translucent display. A/B/D ink and rock vectors remain exactly unchanged.')
 panels=[]
 for j,(label,bounds) in enumerate(CROPS):
  for i,(ink,col) in enumerate(cases):
   p=path/f'crop{j}_case{i}.png';render(ink,readable(col,c),p,palette,bounds,pixels=(int((bounds[2]-bounds[0])*4),int((bounds[3]-bounds[1])*4)));panels.append((p,label+[' / Before',' / After'][i]))
 grid(panels,path/'sheet02_matched_crops.png','Matched local interfaces - before / after',columns=2,cell=(720,530),note='Same bounds within every pair. Source depth controls RSU removal; native foreground leaf ink/color stay exact.')
 panels=[];bounds=(40,575,575,870)
 for k,label in zip(SOURCE_KEYS,SOURCE_LABELS):
  for i in range(2):
   rows=read_vectors(path/f'case{i}_source_{k}.json.gz')['strokes'];ink=[r for r in rows if 'palette_slot' not in r];col=[r for r in rows if 'palette_slot' in r];p=path/f'source_{k}_{i}.png';render(ink,readable(col,c),p,palette,bounds,pixels=(1605,885));panels.append((p,label+[' / Before',' / After'][i]))
 grid(panels,path/'sheet03_hatch_provenance.png','Horizontal marks separated by actual source layer',columns=2,cell=(850,485),note='Lower-middle and foreground, same crop. A ink, A color, C, Soil, contacts and rock structure are shown independently.')
 panels=[];bounds=(90,595,595,790)
 for k,label in [('RSU','Receiving RSU only'),('gestures','Native canopy color - unchanged')]:
  for i in range(2):
   cc=read_vectors(path/f'case{i}_channel_{k}.json.gz')['strokes'];ii=[r for r in cases[i][0] if r['source_family']=='RSU'] if k=='RSU' else [r for r in cases[i][0] if r['source_family']=='tree' and r.get('grammar_part')=='foliage-field'];p=path/f'canopy_{k}_{i}.png';render(ii,readable(cc,c),p,palette,bounds,pixels=(1515,585));panels.append((p,label+[' / Before',' / After'][i]))
 grid(panels,path/'sheet04_canopy_sources.png','Receiver / foreground canopy source separation',columns=2,cell=(900,390),note='Changes are surviving vectors, not opacity tricks. Native leaf ink and canopy color are identical.')
 svg(path/'v09_scene_centerlines.svg',*cases[1],palette);svg(path/'v09_color_centerlines.svg',[],cases[1][1],palette)
 for name in ['v09_scene_centerlines.svg','v09_color_centerlines.svg']:
  p=path/name;p.write_text(p.read_text().replace('Spring v05','Spring v09'))
 adjusted=[]
 for ink,col in cases:
  cc=readable(col,c)
  for r in cc:r['opacity_profile']=(np.array(r['opacity_profile'])/2.8).tolist()
  adjusted.append((ink,cc))
 contact_details(path,c,cases,palette)
 native_pdf(adjusted,palette,path/'native_scale_review.pdf')


def contact_details(path,c,cases,palette):
 record=json.load(open(path/'record.json'));links=sorted([r for r in record['root_plans'] if r['status']=='asymmetric-existing-surface-contact'],key=lambda x:-x['gap_before_mm'])[:2];links += [r for r in record['root_plans'] if r['status']=='partial-burial-at-existing-ground'][:1];panels=[]
 for j,row in enumerate(links):
  x,y=row['visible_foot_xy_mm'];bounds=(x-18,y-13,x+20,y+13)
  for i,(ink,col) in enumerate(cases):
   p=path/f'contact{j}_case{i}.png';render(ink,readable(col,c),p,palette,bounds,pixels=(760,520));panels.append((p,('Partial burial at existing ground' if j==2 else 'Contact to existing A/Soil')+[' / Before',' / After'][i]))
 grid(panels,path/'sheet05_contact_details.png','Selected root / surface contacts - actual source endpoints',columns=2,cell=(700,480),note='Two unequal contacts and one partial burial, same local bounds within each pair. No new terrain A is drawn.')


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--replay-output');a=p.parse_args();source=Path(a.source)
 if a.replay_output:
  out=Path(a.replay_output);out.mkdir(exist_ok=False,parents=True);c,cases=load(source);palette=yaml.safe_load((ROOT/c['palette_source']).read_text());checks={}
  for i,(ink,col) in enumerate(cases):
   name=f'case{i}_readable.png';render(ink,readable(col,c),out/name,palette);checks[name]=bool(np.array_equal(np.array(Image.open(source/name)),np.array(Image.open(out/name))))
  (out/'replay_validation.json').write_text(json.dumps(checks,indent=2)+'\n');assert all(checks.values());print(checks)
 else:render_review(source)

def native_pdf(cases,palette,path):
    """Artwork in native mm, no fit-to-page. Preview widths are uncalibrated."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    cv=canvas.Canvas(str(path),pageCompression=1);cv.setTitle('Datascape Spring v09 - native artwork scale')
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
        furniture(620,940,['Before / v08 Case 2 - 600 x 900 mm','After / v09 - 600 x 900 mm'][i]);draw(ink,col,(0,0,600,900),10,915);cv.showPage()
    for label,b in CROPS:
        w,h=b[2]-b[0],b[3]-b[1];furniture(w*2+30,h+55,label+' - before / after');draw(*cases[0],b,10,h+30);draw(*cases[1],b,w+20,h+30);cv.showPage()
    for label,b in [CROPS[0],CROPS[2],CROPS[3]]:
        w,h=b[2]-b[0],b[3]-b[1];furniture(w*3+40,h+55,label+' - ink / color / combined');draw(cases[1][0],[],b,10,h+30);draw([],cases[1][1],b,w+20,h+30);draw(*cases[1],b,w*2+30,h+30);cv.showPage()
    cv.save()

if __name__=='__main__':main()
