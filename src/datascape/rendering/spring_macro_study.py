"""Bounded v04 Spring comparison with optional, explicit width-intent preview."""
from pathlib import Path
import json,argparse,hashlib,time,gzip
import numpy as np
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection,PolyCollection
from shapely.geometry import Polygon,LineString,mapping
from shapely.ops import unary_union
from PIL import Image
from datascape.strokes.vector import read_vectors,resample
from datascape.strokes.scene import load_selected_scene
from datascape.integration.diverse_scene import resolve_diverse
from datascape.integration.diverse_color import coverage_metrics
from datascape.integration.macro_wash import build_v04_wash,local_frame
from datascape.rendering.spring_diverse_study import display_records
from datascape.rendering.spring_cluster_study import metrics
from datascape.rendering.spring_integration import write_json


def write_gz(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.pending')
    data=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    tmp.write_bytes(gzip.compress(data,mtime=0))
    assert gzip.decompress(tmp.read_bytes())==data
    tmp.replace(path)


def width_envelope(record):
    """Single continuous stroke footprint from an explicit centerline/profile.

    This planning envelope is for display only and is never plotted as a fill.
    No brush-pressure, wet-ink spread or calibrated physical width is implied.
    """
    xy=np.asarray(record['xy_mm']);a=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))];p=resample(xy,.2);s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];w=np.interp(s,a,record['width_profile_mm']);_,n=local_frame(p)
    return Polygon(np.vstack([p+n*w[:,None]/2,(p-n*w[:,None]/2)[::-1]])).buffer(0)


def render(ink,color,path,palette,bounds=(0,0,600,900),pixels=None,envelopes=True):
    x0,y0,x1,y1=bounds
    if pixels is None:pixels=(1200,1800) if bounds==(0,0,600,900) else (round((x1-x0)*4),round((y1-y0)*4))
    pw,ph=pixels;fig=plt.figure(figsize=(pw/150,ph/150),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    for records,is_color in [(ink,False),(color,True)]:
        lines=[];widths=[];colors=[];polys=[];pc=[]
        for r in records:
            p=np.asarray(r['xy_mm']);lo=p.min(axis=0);hi=p.max(axis=0)
            if hi[0]<x0 or lo[0]>x1 or hi[1]<y0 or lo[1]>y1:continue
            w=np.asarray(r.get('width_profile_mm',[r['width_mm']]*len(p)));alpha=np.asarray(r.get('opacity_profile',[r.get('preview_opacity',1.)]*len(p)));rgb=matplotlib.colors.to_rgb(palette['slots'][r['palette_slot']]['preview_hex']) if is_color else (0,0,0)
            if is_color and envelopes and r.get('expressive_width_intent'):
                shape=width_envelope(r)
                for part in getattr(shape,'geoms',[shape]):
                    if part.geom_type=='Polygon':polys.append(np.asarray(part.exterior.coords));pc.append((*rgb,float(alpha.mean())))
            elif is_color:lines.append(p);widths.append(float(w.mean()));colors.append((*rgb,float(alpha.mean())))
            else:
                lines.extend(np.stack([p[:-1],p[1:]],axis=1));widths.extend((w[:-1]+w[1:])/2);colors.extend([(*rgb,float(a)) for a in (alpha[:-1]+alpha[1:])/2])
        ax.add_collection(LineCollection(lines,linewidths=np.asarray(widths)*pw/(x1-x0)*72/150,colors=colors,capstyle='round',joinstyle='round'))
        if polys:ax.add_collection(PolyCollection(polys,facecolors=pc,edgecolors='none',closed=True))
    path=Path(path);tmp=path.with_name(path.stem+'.pending.png');fig.savefig(tmp,dpi=150,facecolor='white');plt.close(fig)
    with Image.open(tmp) as im:im.load()
    tmp.replace(path)


def persist_colors(fixed,result,c,corridor,out):
    data=build_v04_wash(fixed,result,c,corridor);sets,raw,sources,vis,feather,ctx,regions=data
    for key,value in sets.items():write_gz(out/(key+'_color.json.gz'),dict(continuous_mm=[600,900],strokes=value))
    write_gz(out/'color_source_ledger.json.gz',dict(raw_sources=raw,feathered_sources=sources,visibility_decisions=vis,feather_decisions=feather))
    write_json(out/'D_anchors.json',dict(anchors=ctx['D_anchors'],rejected=ctx['D_rejected'],controls=c['d_color_controls']))
    write_json(out/'trunk_supports.geojson',dict(type='FeatureCollection',features=[dict(type='Feature',geometry=mapping(poly),properties=dict(id=key,nonplotting=True)) for key,poly in regions.items()]))
    coverage={k:coverage_metrics(sets[k],fixed,ctx) for k in ['terrain','caseB','caseC']}
    for row in coverage.values():row['eligibility']='Generation: one-mm occupied F2 cells, retention > .08, global reserve/corridors and visible object body/core excluded. Common comparison domain: unchanged retention > .23 before local object exclusions.'
    write_json(out/'color_metrics.json',coverage)
    palette=yaml.safe_load(Path(c['palette_source']).read_text())
    for case in ['caseB','caseC']:
        for mode in ['restrained','diagnostic']:render(result['ink'],display_records(sets[case],c,mode),out/(case+'_'+mode+'.png'),palette)
    render([],display_records(sets['caseC'],c,'diagnostic'),out/'color_only_diagnostic.png',palette)
    return data


def run(master,veg,config,output,references):
    root=Path(config).resolve().parents[2];c=json.loads(Path(config).read_text());out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    f=load_selected_scene(master,veg,root,json.loads((root/'configs/scenes/seoul_spring_selected_C.json').read_text()));b=read_vectors(root/c['baseline'])['strokes'];corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']]);r=resolve_diverse(f,b,c,corridor)
    write_gz(out/'ink.json.gz',dict(continuous_mm=[600,900],strokes=r['ink']));write_gz(out/'source_ledger.json.gz',dict(new_sources=r['new_sources'],terrain_decisions=r['terrain_ledger'],object_decisions=r['object_ledger']));write_json(out/'sites.json',r['sites']);write_json(out/'ink_metrics.json',metrics(r,[]));write_json(out/'contact_repairs.json',r['contact_repairs'])
    render(r['ink'],[],out/'caseA_ink.png',yaml.safe_load((root/c['palette_source']).read_text()));data=persist_colors(f,r,c,corridor,out)
    from datascape.rendering.spring_macro_review import review_pass
    review_pass(f,b,r,c,corridor,data,out,root,Path(references))
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--master',required=True);p.add_argument('--veg',required=True);p.add_argument('--references',required=True);p.add_argument('--config',default='configs/scenes/seoul_spring_macro_v04.json');p.add_argument('--output',required=True);a=p.parse_args();run(a.master,a.veg,a.config,a.output,a.references)
if __name__=='__main__':main()
