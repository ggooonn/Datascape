"""Bounded Spring v03 comparison, preserving v02 and locked source files."""
from pathlib import Path
from copy import deepcopy
import argparse,json,hashlib,time,gc,platform
import numpy as np
import yaml
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,sample
from datascape.strokes.density_rhythm import layer_digest
from datascape.integration.visibility import digest
from datascape.integration.diverse_scene import resolve_diverse
from datascape.integration.diverse_color import (color_context,build_a_color,build_c_color,
    build_material_color,coverage_metrics)
from datascape.rendering.spring_cluster_study import render as _render,export_svg,metrics
from datascape.rendering.spring_integration import write_json,write_gz


def render(ink,color,path,palette,bounds=(0,0,600,900),pixels=(1200,1800)):
    """Publish each local PNG only after a complete image has been verified."""
    from PIL import Image
    path=Path(path);temporary=path.with_name(path.stem+'.pending.png')
    _render(ink,color,temporary,palette,bounds,pixels)
    with Image.open(temporary) as image:image.load()
    temporary.replace(path)


def display_records(records,config,mode):
    if mode=='restrained':return records
    d=config['display_modes'][mode];out=[]
    for r in records:
        s=dict(r);s['opacity_profile']=[min(d['maximum_alpha'],a*d['alpha_multiplier']) for a in r['opacity_profile']]
        s['preview_opacity']=float(np.mean(s['opacity_profile']));out.append(s)
    return out


def compute_colors(fixed,result,c,corridor,out):
    out=Path(out);context=color_context(fixed,result,corridor);sets={};sources={};decisions={}
    print('Build independently displaced A color',flush=True)
    sets['A'],sources['A'],decisions['A']=build_a_color(fixed,result,c,context)
    print('Build C parallels and C/B-guided field',flush=True)
    sets['C'],sources['C'],decisions['C']=build_c_color(fixed,result,c,context)
    for key,structured in [('material_restrained',False),('material_layered',True)]:
        print('Build',key,flush=True)
        sets[key],sources[key],decisions[key]=build_material_color(fixed,result,c,context,corridor,structured)
    print('Build coincident A diagnostic control',flush=True)
    sets['A_coincident'],sources['A_coincident'],decisions['A_coincident']=build_a_color(fixed,result,c,context,coincident=True)
    sets['case2']=sets['A']+sets['C']+sets['material_restrained']
    sets['case3']=sets['A']+sets['C']+sets['material_layered']
    for key,data in sets.items():write_gz(out/(key+'_color.json.gz'),dict(continuous_mm=[600,900],strokes=data))
    write_gz(out/'color_sources_ledger.json.gz',dict(sources=sources,decisions=decisions))
    m={key:coverage_metrics(sets[key],fixed,context) for key in ['A','C','case2','case3']}
    control=read_vectors('outputs/spring-cluster-vector-v02/03_layered_color.json.gz')['strokes']
    for r in control:
        p=np.asarray(r['xy_mm']);r['color_channel']='C-derived' if r['color_kind']=='terrain' else 'material-C-like'
        r['source_forward_profile_m']=(sample(fixed['base']['depth_m'],p) if r['color_kind']=='terrain' else np.full(len(p),r['source_forward_mean_m'])).tolist()
    m['v02_control_common_domain']=coverage_metrics(control,fixed,context)
    write_json(out/'color_metrics.json',m)
    for case in ['case2','case3']:
        for mode in ['restrained','diagnostic']:
            render(result['ink'],display_records(sets[case],c,mode),out/(case+'_'+mode+'.png'),yaml.safe_load(Path(c['palette_source']).read_text()))
    p=yaml.safe_load(Path(c['palette_source']).read_text())
    render([],display_records(sets['case3'],c,'diagnostic'),out/'color_only_diagnostic.png',p)
    export_svg(out/'scene_layers.svg',result['ink'],sets['case3'],p)
    export_svg(out/'color_only.svg',[],sets['case3'],p)
    # Explicit source-channel groups make the export easier to inspect.
    svg=(out/'color_only.svg').read_text().replace('Datascape spring v02','Datascape spring v03')
    (out/'color_only.svg').write_text(svg)
    svg=(out/'scene_layers.svg').read_text().replace('Datascape spring v02','Datascape spring v03')
    (out/'scene_layers.svg').write_text(svg)
    print('Color vectors complete', {key:len(sets[key]) for key in sets},flush=True)
    return sets,sources,decisions,context,m


def run(master,veg,config,output):
    start=time.time();cp=Path(config).resolve();root=cp.parents[2];c=json.loads(cp.read_text());out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    baseline_path=root/c['baseline'];assert hashlib.sha256(baseline_path.read_bytes()).hexdigest()==c['baseline_sha256']
    fixed=load_selected_scene(master,veg,root,json.loads((root/'configs/scenes/seoul_spring_selected_C.json').read_text()))
    baseline=read_vectors(baseline_path)['strokes'];before=digest(baseline)
    frozen={k:hashlib.sha256(fixed['base'][k].tobytes()).hexdigest() for k in ['xyz','depth_m','occupied']}
    frozen['retention']=hashlib.sha256(fixed['retention'].tobytes()).hexdigest()
    corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']])
    result=resolve_diverse(fixed,baseline,c,corridor)
    write_gz(out/'ink.json.gz',dict(continuous_mm=[600,900],strokes=result['ink']))
    write_gz(out/'source_ledger.json.gz',dict(new_sources=result['new_sources'],terrain_decisions=result['terrain_ledger'],object_decisions=result['object_ledger']))
    write_json(out/'sites.json',result['sites']);write_json(out/'contact_repairs.json',result['contact_repairs']);write_json(out/'ink_metrics.json',metrics(result,[]))
    render(result['ink'],[],out/'case1_ink.png',yaml.safe_load((root/c['palette_source']).read_text()))
    sets,sources,decisions,context,color_metrics=compute_colors(fixed,result,c,corridor,out)
    from datascape.rendering.spring_diverse_diagnostics import render_diagnostics,validate_pass,write_record
    render_diagnostics(fixed,result,c,corridor,sets,context,out)
    validation=validate_pass(fixed,baseline,result,sets,sources,decisions,c,context,root,out)
    assert digest(baseline)==before
    for key in ['xyz','depth_m','occupied']:assert hashlib.sha256(fixed['base'][key].tobytes()).hexdigest()==frozen[key]
    assert hashlib.sha256(fixed['retention'].tobytes()).hexdigest()==frozen['retention']
    write_record(fixed,baseline,result,c,sets,color_metrics,validation,frozen,out,root,start)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--master',required=True);p.add_argument('--veg',required=True)
    p.add_argument('--config',default='configs/scenes/seoul_spring_diverse_v03.json');p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
