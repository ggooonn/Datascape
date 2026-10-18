"""Local-only clustered spring / open-vector wash diagnostic, v02."""
from pathlib import Path
import argparse,hashlib,json,time,platform,gc
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union
import yaml
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,resample,sample
from datascape.strokes.density_rhythm import layer_digest
from datascape.integration.visibility import digest,signed_clearance
from datascape.integration.cluster_scene import resolve_clusters
from datascape.integration.vector_wash import build_wash,wash_metrics,depth_parameters,palette_weights
from datascape.rendering.spring_integration import write_json,write_gz,sheet
from datascape.rendering.a_density_v03_study import _physical_pair


def render(ink,color,path,palette,bounds=(0,0,600,900),pixels=(1200,1800)):
    x0,y0,x1,y1=bounds;pw,ph=pixels
    fig=plt.figure(figsize=(pw/150,ph/150),dpi=150,facecolor='white')
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    for records,is_color in [(ink,False),(color,True)]:
        lines=[];widths=[];rgba=[]
        for s in records:
            p=np.asarray(s['xy_mm']);lo=p.min(axis=0);hi=p.max(axis=0)
            if hi[0]<x0 or lo[0]>x1 or hi[1]<y0 or lo[1]>y1:continue
            wp=np.asarray(s.get('width_profile_mm',[s['width_mm']]*len(p)))
            op=np.asarray(s.get('opacity_profile',[s.get('preview_opacity',1.)]*len(p)))
            rgb=matplotlib.colors.to_rgb(palette['slots'][s['palette_slot']]['preview_hex']) if is_color else (0,0,0)
            if is_color:
                # One continuous translucent stroke: segment caps must not
                # accumulate artificial dark beads at every stored vertex.
                # Detailed profiles remain in the vector records; this display
                # uses their per-carrier means, not a calibrated brush model.
                lines.append(p);widths.append(float(np.mean(wp)))
                rgba.append((*rgb,float(np.clip(np.mean(op),0,1))))
            else:
                lines.extend(np.stack([p[:-1],p[1:]],axis=1));widths.extend((wp[:-1]+wp[1:])/2)
                rgba.extend([(rgb[0],rgb[1],rgb[2],float(np.clip(a,0,1))) for a in (op[:-1]+op[1:])/2])
        ax.add_collection(LineCollection(lines,linewidths=np.asarray(widths)*pw/(x1-x0)*72/150,
            colors=rgba,capstyle='round',joinstyle='round'))
    fig.savefig(path,dpi=150,facecolor='white');plt.close(fig)


def export_svg(path,ink,color,palette):
    with open(path,'w') as h:
        h.write('<svg xmlns="http://www.w3.org/2000/svg" width="600mm" height="900mm" viewBox="0 0 600 900">\n')
        h.write('<title>Datascape spring v02: open-vector ink and color supports</title>\n')
        h.write('<metadata>Local canvas millimeters. No filled paint regions. Display widths and alpha are uncalibrated. See vectors and record for lineage.</metadata>\n')
        for records,channel in [(ink,'structural-ink'),(color,'vector-color-support')]:
            h.write(f'<g id="{channel}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n')
            for s in records:
                p=np.asarray(s['xy_mm']);wp=np.asarray(s.get('width_profile_mm',[s['width_mm']]*len(p)))
                op=np.asarray(s.get('opacity_profile',[s.get('preview_opacity',1.)]*len(p)))
                color_hex=palette['slots'][s['palette_slot']]['preview_hex'] if channel=='vector-color-support' else '#000000'
                if channel=='vector-color-support':
                    d='M'+f'{p[0,0]:.6f},{p[0,1]:.6f}'+' '.join(f' L{x:.6f},{y:.6f}' for x,y in p[1:])
                    h.write(f'<path d="{d}" stroke="{color_hex}" stroke-width="{np.mean(wp):.6f}" stroke-opacity="{np.mean(op):.6f}"/>\n')
                else:
                    for a,b,w,alpha in zip(p[:-1],p[1:],(wp[:-1]+wp[1:])/2,(op[:-1]+op[1:])/2):
                        h.write(f'<path d="M{a[0]:.6f},{a[1]:.6f} L{b[0]:.6f},{b[1]:.6f}" stroke="{color_hex}" stroke-width="{w:.6f}" stroke-opacity="{alpha:.6f}"/>\n')
            h.write('</g>\n')
        h.write('</svg>\n')


def metrics(result,color):
    families=Counter(r['source_family'] for r in result['ink'])
    lengths={k:sum(LineString(r['xy_mm']).length for r in result['ink'] if r['source_family']==k) for k in families}
    root_checks=[]
    ground=[r for r in result['ink'] if r['source_family'] in ('A','Soil','rock')]
    for o in result['objects']:
        if o['kind']!='tree':continue
        root=Point(o['site']['xy_mm']);near=[]
        for r in ground:
            line=LineString(r['xy_mm'])
            if line.distance(root)<7:near.append((r['source_family'],line.intersection(root.buffer(7)).length))
        root_checks.append(dict(object_id=o['id'],height_mm=o['height_mm'],root_retention=o['site']['retained_ground'],
            root_ground_length_mm=sum(v for _,v in near),root_ground_families=sorted(set(k for k,_ in near))))
    height=[o['height_mm'] for o in result['objects'] if o['kind']=='tree']
    return dict(legacy_V_paths_removed=result['legacy_V_paths_removed'],legacy_V_paths_visible=0,
        catalog_objects=Counter(o['kind'] for o in result['objects']),ink_paths=dict(families),ink_length_mm=lengths,
        cluster_specs=result['clusters'],height_min_median_max_mm=[min(height),float(np.median(height)),max(height)],
        root_contacts=root_checks,roots_with_ground_within_7mm=sum(r['root_ground_length_mm']>2 for r in root_checks),
        wash=wash_metrics(color),ink_sha256=digest(result['ink']))


def validate_records(result,color,baseline,fixed,c):
    ink=result['ink'];assert not any(r['source_family']=='V' for r in ink)
    assert result['legacy_V_paths_removed']==sum(r['layer']=='V' for r in baseline)
    assert all(not a['kept_intervals_mm'] for a in result['terrain_ledger'] if a['reasons']==['v02-remove-all-legacy-V-placement'])
    sources={r['id']:r for r in baseline+result['new_sources']}
    max_original_error=0.
    for r in ink+result['color_sources']:
        assert len(r['xy_mm'])>=2
        if r['origin_kind']=='new-catalog':assert LineString(r['xy_mm']).length>=2.8-1e-7
        if r['source_stroke_id'] in sources:
            from shapely.ops import substring
            source=LineString(sources[r['source_stroke_id']]['xy_mm']);a,b=r['source_arc_mm']
            max_original_error=max(max_original_error,source.hausdorff_distance(LineString(r['xy_mm'])) if a==0 and b==source.length else substring(source,a,b).hausdorff_distance(LineString(r['xy_mm'])))
    for r in ink+color:
        p=np.asarray(r['xy_mm']);assert np.isfinite(p).all()
        for key in ('width_profile_mm','opacity_profile'):
            if key in r:assert len(r[key])==len(p)
        if 'intensity_samples' in r.get('expression',{}):assert len(r['expression']['intensity_samples'])==len(p)
        assert p[:,0].min()>=0 and p[:,0].max()<=600 and p[:,1].max()<898
    assert max_original_error<1e-6
    assert set(r['palette_slot'] for r in color)<=set(c['spring_active_target_percent'])
    assert min(LineString(r['xy_mm']).length for r in color)>=2.8-1e-7
    assert len({r['id'] for r in color})==len(color)
    return dict(legacy_V_absent=True,baseline_and_catalog_sources_immutable=True,
        profiles_aligned=True,exact_original_arc_error_mm=max_original_error,
        new_minimum_2_8mm=True,canvas_bottom_guard=True,active_palette_only=True,
        no_polygon_color_fills=True,paper_background='#FFFFFF')


def run(master,veg,config,output):
    t=time.time();cp=Path(config).resolve();root=cp.parents[2];c=json.loads(cp.read_text())
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    bp=root/c['baseline'];assert hashlib.sha256(bp.read_bytes()).hexdigest()==c['baseline_sha256']
    baseline=read_vectors(bp)['strokes'];original=digest(baseline)
    print('Restore hash-verified exact F2 fields',flush=True)
    fixed=load_selected_scene(master,veg,root,json.loads((root/'configs/scenes/seoul_spring_selected_C.json').read_text()))
    frozen={k:hashlib.sha256(fixed['base'][k].tobytes()).hexdigest() for k in ['xyz','depth_m','occupied']}
    frozen['retention']=hashlib.sha256(fixed['retention'].tobytes()).hexdigest()
    corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']])
    palette=yaml.safe_load((root/c['palette_source']).read_text())
    record=dict(study=c['study'],parent_commit=c['parent_commit'],config=c,
        baseline_sha256=c['baseline_sha256'],source_layer_digests={k:layer_digest(baseline,k) for k in 'ABCDV'},
        field_sha256=frozen,input_sha256=fixed['selection']['input_sha256'],variants={},validation={},
        paper_background='#FFFFFF',filled_color_regions=0,
        color_display='One continuous stroke per carrier, per-carrier mean width/alpha; detailed profiles retained separately',
        implementation_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),root/'src/datascape/integration/cluster_scene.py',root/'src/datascape/integration/vector_wash.py']},
        palette_sha256=hashlib.sha256((root/c['palette_source']).read_bytes()).hexdigest(),runtime=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__),
        publication='Local only; no GitHub push, PR update or merge authorized',readiness='Not ready for production')
    files=[]
    for level,names in [('clean',[('01_clean','restrained')]),('clustered',[('02_clustered','restrained'),('03_layered','layered')])]:
        print('Resolve catalog-only',level,flush=True);result=resolve_clusters(fixed,baseline,c,level,corridor)
        write_gz(out/(level+'_ink.json.gz'),dict(continuous_mm=[600,900],panel_width_mm=300,physical_gap_mm=40,strokes=result['ink']))
        write_gz(out/(level+'_source_ledger.json.gz'),dict(baseline_reference=c['baseline'],baseline_sha256=c['baseline_sha256'],
            new_sources=result['new_sources'],terrain_decisions=result['terrain_ledger'],object_decisions=result['object_ledger']))
        write_json(out/(level+'_sites.json'),result['sites'])
        render(result['ink'],[],out/(level+'_ink.png'),palette)
        for name,mode in names:
            print('Build open-vector color',name,mode,flush=True)
            color,sources,ledger=build_wash(fixed,result,c,mode,corridor)
            record['variants'][name]=metrics(result,color)
            record['validation'][name]=validate_records(result,color,baseline,fixed,c)
            write_gz(out/(name+'_color.json.gz'),dict(continuous_mm=[600,900],strokes=color))
            write_gz(out/(name+'_color_sources_ledger.json.gz'),dict(sources=sources,decisions=ledger))
            render(result['ink'],color,out/(name+'.png'),palette);files.append(out/(name+'.png'))
            if name=='03_layered':
                render([],color,out/'color_support_only.png',palette)
                bounds=(35,590,565,860);pix=(1696,864)
                render(result['ink'],color,out/'foreground_color.png',palette,bounds,pix)
                render(result['ink'],[],out/'foreground_ink.png',palette,bounds,pix)
                render([],color,out/'foreground_color_only.png',palette,bounds,pix)
                depth_crops=[('near',(70,680,270,850)),('middle',(60,565,260,735)),('upper',(395,395,595,565))]
                for label,crop in depth_crops:
                    render(result['ink'],color,out/f'depth_{label}.png',palette,crop,(800,680))
                sheet([out/f'depth_{label}.png' for label,_ in depth_crops],
                    ['Near / contact q about 0.27 km','Middle / contact q about 0.93 km','Upper / contact q about 2.18 km'],out/'depth_comparison.png',width=600)
                _physical_pair(out/(name+'.png'),out/'physical_pair.png')
                export_svg(out/'scene_layers.svg',result['ink'],color,palette)
                export_svg(out/'color_support_only.svg',[],color,palette)
        del result;gc.collect()
    assert record['variants']['02_clustered']['ink_sha256']==record['variants']['03_layered']['ink_sha256']
    assert digest(baseline)==original
    assert hashlib.sha256(fixed['retention'].tobytes()).hexdigest()==frozen['retention']
    for k in 'ABCDV':assert layer_digest(baseline,k)==record['source_layer_digests'][k]
    sheet(files,['01 / cleaned serial clusters','02 / developed + restrained wash','03 / same ink + layered wash'],out/'comparison.png',width=640)
    sheet([out/'foreground_ink.png',out/'foreground_color_only.png',out/'foreground_color.png'],
          ['Structural ink only','Open color-support vectors only','Ink with overlapping color vectors'],out/'material_comparison.png',width=750)
    record['elapsed_seconds']=time.time()-t;write_json(out/'record.json',record)
    print('Complete',out,'seconds',record['elapsed_seconds'],flush=True)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True);p.add_argument('--veg',required=True)
    p.add_argument('--config',default='configs/scenes/seoul_spring_clusters_v02.json');p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
