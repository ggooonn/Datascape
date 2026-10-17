"""Reproduce spring A/B/C and material diagnostics from immutable source vectors."""
from pathlib import Path
from copy import deepcopy
import argparse,base64,gzip,hashlib,html,json,platform,shutil,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath
from shapely.geometry import LineString,Point,Polygon,mapping,GeometryCollection
from shapely.ops import unary_union
from scipy.ndimage import binary_dilation
from rasterio.features import shapes
import yaml
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.vector import read_vectors,sample
from datascape.strokes.density_rhythm import layer_digest
from datascape.integration.visibility import (adapt,digest,clip_source,object_gate,
    terrain_gate,depth_field,signed_clearance,burn,regions_from_tree,behind_object)
from datascape.integration.objects import build_objects,final_regions
from datascape.rendering.a_density_v03_study import _physical_pair


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def write_gz(path,value):
    with open(path,'wb') as h:
        with gzip.GzipFile(fileobj=h,mode='wb',mtime=0) as z:
            z.write(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def geometry_mask(mask):
    from shapely.geometry import shape
    return unary_union([shape(g) for g,v in shapes(mask.astype('uint8'),mask=mask) if v])


def assignment(site,family,config,palette):
    xyz=site['source_xyz_utm_m']; cell=(int(xyz[0]//220),int(xyz[1]//220))
    token=hashlib.sha256(f'{config["seed"]}/{cell}/{family}'.encode()).hexdigest()
    u=int(token[:12],16)/16**12; keys=list(config['spring_slot_weights'])
    weights=np.asarray([config['spring_slot_weights'][k] for k in keys],float)
    i=min(int(np.searchsorted(np.cumsum(weights/weights.sum()),u)),len(keys)-1)
    return keys[i]


def resolve(fixed,baseline,config,variant,corridor):
    objects,replace_v,patches,contacts=build_objects(fixed,baseline,config,variant,corridor)
    initial={o['id']:o['regions']['body'].copy() for o in objects}
    # Resolve semantic solid visibility against all other initial solids in one
    # union. A rear body's hidden pixels cannot act as independent occluders.
    for o in objects:
        for front in objects:
            if o['id']==front['id']:continue
            hidden=initial[front['id']] & behind_object(o,front,o['q'],front['q'])
            o['visible'] &= ~hidden
            o['regions']['body'] &= ~hidden
            o['regions']['soft'] *= ~hidden
        o['body_distance']=signed_clearance(o['regions']['body'])
    preliminary={}; object_audit=[]
    for o in objects:
        gate=object_gate(fixed,o,objects); visible=[]
        for r in o['records']:
            parts,a=clip_source(r,gate);visible+=parts;object_audit.append(a)
        preliminary[o['id']]=visible
    # Masks are rebuilt from the surviving ink/visible solids, then terrain is
    # clipped only once. Original object sources remain in the source archive.
    for o in objects:final_regions(o,preliminary[o['id']])
    gate=terrain_gate(fixed,sorted(objects,key=lambda o:o['id']),patches)
    terrain=[];terrain_audit=[]
    for source in baseline:
        r=adapt(source,'baseline','baseline/'+source.get('source_root_id',source['layer']),source['layer'])
        force=('selected-V-root-replacement:'+source['source_root_id']) if source.get('source_root_id') in replace_v else None
        parts,a=clip_source(r,gate,force_reason=force)
        terrain+=parts;terrain_audit.append(a)
    obj_records=[r for o in sorted(objects,key=lambda o:o['id']) for r in preliminary[o['id']]]
    return dict(objects=objects,terrain=terrain,new=obj_records,strokes=terrain+obj_records,
                replacements=sorted(replace_v),terrain_audit=terrain_audit,object_audit=object_audit,
                contacts=contacts,patches=patches)


def polygon_patch(ax,geometry,color,alpha):
    if geometry.is_empty:return
    if geometry.geom_type=='Polygon':
        verts=[];codes=[]
        for ring in [geometry.exterior,*geometry.interiors]:
            p=np.asarray(ring.coords);verts.extend(p)
            codes.extend([MPath.MOVETO]+[MPath.LINETO]*(len(p)-2)+[MPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MPath(verts,codes),facecolor=color,alpha=alpha,edgecolor='none'))
    else:
        for g in getattr(geometry,'geoms',[]):polygon_patch(ax,g,color,alpha)


def render(records,path,bounds=(0,0,600,900),pixels=(1200,1800),mode='scene',washes=(),palette=None):
    x0,y0,x1,y1=bounds;pw,ph=pixels
    fig=plt.figure(figsize=(pw/150,ph/150),dpi=150,facecolor='#F8F8F5' if mode=='color' else 'white')
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    if mode=='color':
        for g,slot,alpha in washes:polygon_patch(ax,g,palette['slots'][slot]['preview_hex'],alpha)
    colors={'A':'#52565d','B':'#a15bac','C':'#3789b1','D':'#d04c3e','V':'#63a993',
            'tree':'#173425','rock':'#5f3b2d','Soil':'#b39345'}
    lines=[];widths=[];rgba=[]
    for s in records:
        family=s.get('source_family',s['layer'])
        if mode=='ink' and family=='C':continue
        if mode=='C_only' and family!='C':continue
        if mode=='Soil_only' and family!='Soil':continue
        p=np.asarray(s['xy_mm']); b=(p[:,0].min(),p[:,1].min(),p[:,0].max(),p[:,1].max())
        if b[2]<x0 or b[0]>x1 or b[3]<y0 or b[1]>y1:continue
        wp=np.asarray(s.get('width_profile_mm',[s['width_mm']]*len(p)))
        op=np.asarray(s.get('opacity_profile',[s.get('preview_opacity',1.)]*len(p)))
        color='black'
        if mode=='layers':color=colors.get(family,'#333');op=np.ones(len(p))
        if mode=='C_only':color='#3789b1';op=np.ones(len(p));wp=wp*2
        if mode=='color' and family=='C':
            color=palette['slots'][s['preview_palette_slot']]['preview_hex'];op=np.maximum(op,.42)
        for i in range(len(p)-1):
            lines.append(p[i:i+2]);widths.append((wp[i]+wp[i+1])/2)
            rgba.append(matplotlib.colors.to_rgba(color,float(np.clip((op[i]+op[i+1])/2,0,1))))
    ax.add_collection(LineCollection(lines,linewidths=np.asarray(widths)*pw/(x1-x0)*72/150,
                                    colors=rgba,capstyle='round',joinstyle='round'))
    fig.savefig(path,dpi=150,facecolor=fig.get_facecolor());plt.close(fig)


def sheet(paths,labels,output,width=600):
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',21)
    panels=[]
    for p,label in zip(paths,labels):
        im=Image.open(p).convert('RGB');height=round(im.height*width/im.width)
        im=im.resize((width,height),Image.Resampling.LANCZOS)
        panel=Image.new('RGB',(width+24,height+68),'#f2f1ed');panel.paste(im,(12,56))
        ImageDraw.Draw(panel).text((14,16),label,font=font,fill='#262b2a');panels.append(panel)
    canvas=Image.new('RGB',(sum(p.width for p in panels),max(p.height for p in panels)),'white')
    x=0
    for p in panels:canvas.paste(p,(x,0));x+=p.width
    canvas.save(output)


def audits(result,baseline,fixed,config):
    bylayer={}
    for family in 'ABCDV':
        rows=[a for a in result['terrain_audit'] if next(s for s in baseline if s['id']==a['source_id'])['layer']==family]
        bylayer[family]=dict(source_paths=len(rows),source_mm=sum(a['source_length_mm'] for a in rows),
            removed_mm=sum(a['removed_mm'] for a in rows),short_dropped_mm=sum(a['short_dropped_mm'] for a in rows))
    allr=result['strokes'];new=result['new']; c=[r for r in allr if r['source_family']=='C']
    soil=[r for r in new if r['source_family']=='Soil'];rock=[r for r in new if r['source_family']=='rock']
    tree=[r for r in new if r['source_family']=='tree']
    def cover(records):return unary_union([LineString(r['xy_mm']).buffer(r.get('assumed_footprint_mm',r['width_mm'])/2) for r in records])
    ccover=cover(c);soilcover=cover(soil)
    families={fam:dict(paths=sum(r['source_family']==fam for r in allr),
          length_mm=sum(LineString(r['xy_mm']).length for r in allr if r['source_family']==fam))
          for fam in ['A','B','C','D','V','tree','rock','Soil']}
    contacts=[]
    for obj in result['objects']:
        xy=obj['site']['xy_mm']; near=Point(xy).buffer(9)
        retained=[];ground_support=[]
        for r in result['terrain']:
            if r['source_family'] not in ('A','D'):continue
            hit=LineString(r['xy_mm']).intersection(near)
            if hit.length>1:
                from datascape.vegetation.tree_occlusion_proof import line_parts
                line=LineString(r['xy_mm'])
                for part in line_parts(hit):
                    aa=line.project(Point(part.coords[0]));bb=line.project(Point(part.coords[-1]))
                    retained.append(dict(source_id=r['source_stroke_id'],source_arc_mm=[r['source_arc_mm'][0]+min(aa,bb),r['source_arc_mm'][0]+max(aa,bb)],near_contact_mm=part.length))
        for r in new:
            if r['source_family'] not in ('rock','Soil'):continue
            hit=LineString(r['xy_mm']).intersection(near)
            if hit.length>1:
                ground_support.append(dict(source_id=r['source_stroke_id'],owner_id=r['owner_id'],near_contact_mm=hit.length))
        contacts.append(dict(object_id=obj['id'],selected_supports=retained,selected_new_ground=ground_support,
                            contact_site=obj['site'],status='review; no blanket collar exception'))
    # Matched actual-terrain canopy control, including footprints and local q.
    canopy=[]
    from datascape.strokes.vector import resample
    for obj in result['objects']:
        if obj['kind']!='tree':continue
        reg=obj['regions']; counts=dict(unmasked_mm=0.,v10_removed_mm=0.,proposal_removed_mm=0.,full_removed_mm=0.)
        for r in baseline:
            if r['layer']!='A':continue
            p=resample(r['xy_mm'],.5)
            if len(p)<2:continue
            inside=sample(reg['full'].astype(float),p)>.5
            behind=sample(fixed['base']['depth_m'],p)>sample(obj['q'],p)+25
            ll=np.linalg.norm(np.diff(p,axis=0),axis=1);eligible=inside[:-1]&behind[:-1]
            counts['unmasked_mm']+=float(ll[eligible].sum())
            for key,mask in [('v10_removed_mm',reg['v10']),('full_removed_mm',reg['full'])]:
                hit=sample(mask.astype(float),p)>.5;counts[key]+=float(ll[eligible&hit[:-1]].sum())
            # Measure the actual plan against source intervals, not opacity.
            gate=terrain_gate(fixed,[obj]);v,_=gate(p,np.r_[0,np.cumsum(ll)],adapt(r,'baseline','baseline/A','A'))
            counts['proposal_removed_mm']+=float(ll[eligible&(v[:-1]<=0)].sum())
        canopy.append(dict(object_id=obj['id'],**counts,core_area_mm2=reg['core_area_mm2'],
             foliage_footprint_mm2=reg['retained_foliage_footprint_mm2'],sigma_mm=reg['sigma_mm'],
             note='0.5 mm diagnostic length sampling; actual output ledger has exact arc intervals'))
    return dict(families=families,baseline_layers=bylayer,
        replaced_V_root_ids=result['replacements'],contacts=contacts,rock_host_contacts=result['contacts'],
        C_Soil_footprint_overlap_mm2=ccover.intersection(soilcover).area,
        V_tree_footprint_overlap_mm2=cover([r for r in result['terrain'] if r['source_family']=='V']).intersection(cover(tree)).area,
        A_Soil_footprint_overlap_mm2=cover([r for r in result['terrain'] if r['source_family']=='A']).intersection(soilcover).area,
        new_minimum_mm=min((LineString(r['xy_mm']).length for r in new),default=None),
        baseline_short_paths_preserved=sum(LineString(r['xy_mm']).length<2.8 for r in result['terrain']),
        canopy_comparison=canopy,
        gate_status={k:'diagnostic only; artist/material acceptance pending' for k in ['OCC-01','OCC-02','OCC-03','OCC-04','OCC-05','OCC-06','OCC-07','OCC-08']})


def canopy_controls(fixed,result,baseline,out):
    obj=next(o for o in result['objects'] if o['id'].endswith('/right-middle'))
    original=[adapt(r,'baseline','baseline/A','A') for r in baseline if r['layer']=='A']
    tree=[r for r in result['new'] if r['owner_id']==obj['id']]
    bounds=(440,535,555,655);pix=(690,720);paths=[]
    for mode in ['unmasked','v10','proposal','full']:
        output=[]
        distance=signed_clearance(obj['regions'][mode]) if mode in ('v10','full') else None
        def control_gate(xy,arc,r):
            behind=sample(fixed['base']['depth_m'],xy)>sample(obj['q'],xy)+25
            return np.where(behind,sample(distance,xy)-1.,1e6),[mode+'-control']
        gate=terrain_gate(fixed,[obj]) if mode=='proposal' else control_gate if mode!='unmasked' else None
        for r in original:
            parts,_=clip_source(r,gate);output+=parts
        path=out/('canopy_'+mode+'.png');paths.append(path)
        render(output+tree,path,bounds,pix,mode='ink')
    sheet(paths,['No exclusion','v10 footprint control','Occupied-core proposal','Full-support control'],out/'canopy_controls.png',width=480)


def run(master,veg,config_path,output):
    start=time.time();cp=Path(config_path).resolve();root=cp.parents[2];c=json.loads(cp.read_text())
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    declared={'minimum_mm':2.8,'arc_sample_mm':.35,'edge_mm':.15,'raster_guard_mm':1.,
              'tree_footprint_mm':.8,'rock_footprint_mm':.65,'soil_footprint_mm':.6}
    if c['visibility']!=declared or c['depth_policy']['tolerance_m']!=25 or c['depth_policy']['lateral_bound_m']!=35:
        raise ValueError('This revision pins the diagnostic policy; update the implementation and tests to change it')
    bp=root/c['baseline'];assert hashlib.sha256(bp.read_bytes()).hexdigest()==c['baseline_sha256']
    baseline=read_vectors(bp)['strokes'];source_digest=digest(baseline)
    print('Restore exact locked F2 source/retention fields',flush=True)
    fixed=load_selected_scene(master,veg,root,json.loads((root/'configs/scenes/seoul_spring_selected_C.json').read_text()))
    field_hashes={key:hashlib.sha256(fixed['base'][key].tobytes()).hexdigest() for key in ['xyz','depth_m','occupied']}
    field_hashes['retention']=hashlib.sha256(fixed['retention'].tobytes()).hexdigest()
    corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']])
    palette=yaml.safe_load((root/c['palette_sources'][0]).read_text())
    shutil.copy2(bp.parent/'production.png',out/'A_baseline.png')
    base_records=[adapt(s,'baseline','baseline/'+s['layer'],s['layer']) for s in baseline]
    render(base_records,out/'A_structural_ink.png',mode='ink')
    results={}; record=dict(start_commit=c['start_commit'],baseline_sha256=c['baseline_sha256'],
        source_layer_digests={k:layer_digest(baseline,k) for k in 'ABCDV'},
        field_sha256=field_hashes,config=c,config_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),
        input_sha256=fixed['selection']['input_sha256'],
        palette_sources={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in c['palette_sources']},
        implementation_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__),*sorted((root/'src/datascape/integration').glob('*.py'))]},
        runtime=dict(python=platform.python_version(),numpy=np.__version__),variants={})
    for variant in ['B','C']:
        print('Resolve variant',variant,flush=True)
        result=resolve(fixed,baseline,c,variant,corridor);results[variant]=result
        washes=[];features=[];sites=[]
        for obj in result['objects']:
            slot=c['wash_roles'][obj['tree'].structure.get('catalog_form')] if obj['kind']=='tree' else c['wash_roles']['Soil']
            visible=np.asarray(obj['visible'])
            if obj['kind']=='tree':g=geometry_mask((obj['regions']['occupancy']>.018)&visible);alpha=.18 if slot=='C1' else .13
            elif obj['kind']=='soil':g=obj['pigment'].intersection(geometry_mask(visible));alpha=.10
            else:continue
            g=g.difference(corridor)
            washes.append((g,slot,alpha));features.append(dict(type='Feature',geometry=mapping(g),
                properties=dict(owner=obj['id'],material_channel='nonplotting-wash-intent',palette_slot=slot,display_alpha=alpha,
                                opacity_calibrated=False,source_contact=obj['site'])))
        for r in result['strokes']:
            if r['source_family']=='C':
                p=np.asarray(r['xy_mm']);mid=p[len(p)//2];xyz=np.array([sample(fixed['base']['xyz'][:,:,i],[mid])[0] for i in range(3)])
                if not np.isfinite(xyz).all():raise ValueError('C support has no source XYZ')
                r['preview_palette_slot']=assignment(dict(source_xyz_utm_m=xyz),'C',c,palette)
        print('Audit and render variant',variant,flush=True)
        record['variants'][variant]=audits(result,baseline,fixed,c)
        render(result['strokes'],out/f'{variant}_scene.png')
        render(result['strokes'],out/f'{variant}_ink.png',mode='ink')
        render(result['strokes'],out/f'{variant}_color.png',mode='color',washes=washes,palette=palette)
        if variant=='C':
            render(result['strokes'],out/'C_layers.png',mode='layers')
            for name,bounds in [('foreground',(70,625,565,875)),('middle',(15,550,580,720))]:
                pix=(1584,round(1584*(bounds[3]-bounds[1])/(bounds[2]-bounds[0])))
                render(result['strokes'],out/f'C_{name}_ink.png',bounds,pix,mode='ink')
                render(result['strokes'],out/f'C_{name}_color.png',bounds,pix,mode='color',washes=washes,palette=palette)
            render(result['strokes'],out/'C_only.png',mode='C_only')
            render(result['strokes'],out/'Soil_only.png',mode='Soil_only')
            _physical_pair(out/'C_color.png',out/'C_physical_pair.png')
        write_gz(out/f'{variant}_vectors.json.gz',dict(schema='datascape.spring-integration/0.1',continuous_mm=[600,900],
            panel_width_mm=300,physical_gap_mm=40,baseline_sha256=c['baseline_sha256'],
            strokes=result['strokes']))
        write_gz(out/f'{variant}_sources_and_ledger.json.gz',dict(
            baseline_reference=c['baseline'],baseline_sha256=c['baseline_sha256'],
            new_sources=[r for o in result['objects'] for r in o['records']],
            terrain_decisions=result['terrain_audit'],object_decisions=result['object_audit']))
        write_json(out/f'{variant}_supports.geojson',dict(type='FeatureCollection',
            coordinate_system='local canvas millimeters; not longitude/latitude',features=features))
        # Contact geometry and depth are exported independently of displayed ink.
        write_json(out/f'{variant}_sites.json',[dict(object_id=o['id'],kind=o['kind'],group=o['group'],
            site=o['site'],depth_policy=c['depth_policy'],host_source_id=o.get('host_source_id'),
            parent_mass_id=o.get('parent_mass_id'),catalog_local_rank=o.get('catalog_local_rank'),host_basis=o.get('host_basis'),nonplotting_host=o.get('host'),canonical_tree_sha256=o.get('raw_catalog_sha256')) for o in result['objects']])
    canopy_controls(fixed,results['C'],baseline,out)
    assert digest(baseline)==source_digest
    for k in 'ABCDV':assert layer_digest(baseline,k)==record['source_layer_digests'][k]
    assert hashlib.sha256(fixed['retention'].tobytes()).hexdigest()==field_hashes['retention']
    sheet([out/p for p in ['A_baseline.png','B_scene.png','C_scene.png','C_color.png']],
          ['A / unchanged baseline','B / restrained integration','C / richer integration','D / spring color-ready'],out/'comparison.png')
    sheet([out/p for p in ['A_structural_ink.png','B_ink.png','C_ink.png']],
          ['A / matched structural ink','B / structural ink','C / structural ink'],out/'ink_comparison.png')
    sheet([out/p for p in ['C_only.png','Soil_only.png','C_layers.png']],
          ['C / color-support geometry','Soil / structural ink','Material / source ownership'],out/'materials.png')
    record['elapsed_seconds']=time.time()-start
    record['unchanged_baseline_sources']=True
    record['readiness']='Not ready'
    record['limitations']=['Upright bounded 2.5D diagnostic, not branch/rock volume reconstruction',
        'One-mm visibility fields with explicit 1 mm guard; brush footprints unmeasured',
        'Canonical short baseline strokes remain; no production path acceptance',
        'Existing V remains outside explicitly replaced roots; mixed grammar requires review',
        'Color hex/alpha are display intentions, not dry pigment behavior']
    write_json(out/'record.json',record)
    print('Finished',out,'seconds',time.time()-start,flush=True)
    return results,record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True);p.add_argument('--veg',required=True)
    p.add_argument('--config',default='configs/scenes/seoul_spring_integration_v01.json')
    p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
