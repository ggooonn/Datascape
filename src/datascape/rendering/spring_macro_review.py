"""Actual-scene v04 diagnostic sheets, source checks and numerical review."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,html,csv,textwrap,xml.etree.ElementTree as ET
import numpy as np
import yaml
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import substring
from shapely import contains_xy
from datascape.strokes.vector import read_vectors,resample,sample
from datascape.integration.visibility import digest,burn
from datascape.integration.cluster_scene import intersects
from datascape.integration.macro_wash import source_basis
from datascape.rendering.spring_integration import write_json
from datascape.rendering.spring_macro_study import render,width_envelope,write_gz
from datascape.rendering.spring_diverse_study import display_records
from datascape.rendering.spring_diverse_diagnostics import grid as legacy_grid,font,export_channel_svg


def grid(panels,path,title,columns=3,cell=(480,340),note=''):
    """Verify each complete sheet before replacing its public filename."""
    path=Path(path);tmp=path.with_name(path.stem+'.pending.png')
    legacy_grid(panels,tmp,title,columns=columns,cell=cell,note=note)
    with Image.open(tmp) as im:im.load()
    tmp.replace(path)


def control_vectors(root):
    path=root/'outputs/spring-diverse-vector-v03'
    return sum((read_vectors(path/(key+'_color.json.gz'))['strokes'] for key in ['A','C','material_layered']),[])


def spatial_metrics(records,fixed,ctx):
    qfield=fixed['base']['depth_m'];far=qfield>=2200;common=ctx['common_eligible'];e=ctx['D_emphasis']
    masks={'D_focus':common&far&(e>.35),'far_surround':common&far&(e<.12),'far_all':common&far}
    result={k:dict(area_mm2=int(mask.sum()),paths=0,A_length_mm=0.,terrain_length_mm=0.) for k,mask in masks.items()}
    masks={k:v.astype(float) for k,v in masks.items()}
    for r in records:
        if r['color_kind']!='terrain':continue
        p=resample(r['xy_mm'],.5);mid=(p[:-1]+p[1:])/2;length=np.linalg.norm(np.diff(p,axis=0),axis=1)
        for key,mask in masks.items():
            inside=sample(mask,mid)>.5;value=float(length[inside].sum())
            if value:
                result[key]['paths']+=1;result[key]['terrain_length_mm']+=value
                if r['color_channel']=='A-derived':result[key]['A_length_mm']+=value
    for v in result.values():v['A_density_mm_per_mm2']=v['A_length_mm']/max(v['area_mm2'],1);v['terrain_density_mm_per_mm2']=v['terrain_length_mm']/max(v['area_mm2'],1)
    return result


def mist_metrics(records,fixed,ctx):
    edges=[.001,.08,.20,.35,.48,1.01];out=[dict(retention_range=[a,b],length_mm=0.,paths=0,area_mm2=int(((fixed['retention']>=a)&(fixed['retention']<b)&fixed['base']['occupied']).sum())) for a,b in zip(edges[:-1],edges[1:])]
    for r in records:
        p=resample(r['xy_mm'],.5);mid=(p[:-1]+p[1:])/2;length=np.linalg.norm(np.diff(p,axis=0),axis=1);ret=sample(fixed['retention'],mid)
        for i,(a,b) in enumerate(zip(edges[:-1],edges[1:])):
            value=float(length[(ret>=a)&(ret<b)].sum())
            if value:out[i]['length_mm']+=value;out[i]['paths']+=1
    for row in out:row['length_density_mm_per_mm2']=row['length_mm']/max(row['area_mm2'],1)
    return out


def macro_metrics(result,c,fixed):
    groups=defaultdict(list)
    for s in result['sites']:
        if s['kind']!='soil':groups[s['group']].append(s)
    output=[]
    for field in c['macro_fields']:
        nodes=[]
        for key in field['groups']:
            rows=groups[key];xyz=np.median([s['site']['source_xyz_utm_m'] for s in rows],axis=0);q=float(np.median([s['site']['source_forward_m'] for s in rows]));nodes.append(dict(group=key,source_forward_m=q,source_xyz_m=xyz.tolist(),xy_mm=np.median([s['site']['xy_mm'] for s in rows],axis=0).tolist()))
        edges=[dict(from_group=a['group'],to_group=b['group'],delta_source_forward_m=b['source_forward_m']-a['source_forward_m'],source_distance_m=float(np.linalg.norm(np.asarray(a['source_xyz_m'])-b['source_xyz_m'])),open_interval=[a['group'],b['group']] in field['open_edges']) for a,b in zip(nodes[:-1],nodes[1:])]
        output.append(dict(id=field['id'],role=field['role'],nodes=nodes,edges=edges))
    return output


def reference_sheet(result,c,fixed,refs,out,combined,palette):
    canvas=Image.open(out/'caseA_ink.png').convert('RGB');draw=ImageDraw.Draw(canvas);colors=['#4C8060','#9B613E','#617D9A'];fields=macro_metrics(result,c,fixed)
    for n,field in enumerate(fields):
        nodes=field['nodes'];color=colors[n]
        for edge,a,b in zip(field['edges'],nodes[:-1],nodes[1:]):
            p=np.asarray(a['xy_mm'])*2;q=np.asarray(b['xy_mm'])*2
            if edge['open_interval']:
                draw.line([tuple(p),tuple(p+(q-p)*.33)],fill=color,width=4);draw.line([tuple(p+(q-p)*.70),tuple(q)],fill=color,width=4)
            else:draw.line([tuple(p),tuple(q)],fill=color,width=4)
            d=q-p;d/=max(np.linalg.norm(d),1);normal=np.array([-d[1],d[0]]);tip=p+(q-p)*.62;draw.polygon([tuple(tip+d*10),tuple(tip-d*5+normal*5),tuple(tip-d*5-normal*5)],fill=color)
        for i,node in enumerate(nodes):
            x,y=np.asarray(node['xy_mm'])*2;radius=12 if i==0 else 6;draw.ellipse((x-radius,y-radius,x+radius,y+radius),outline=color,width=3);draw.text((x+10,y+3),f'{n+1}.{i+1}',font=font(18),fill=color,stroke_width=2,stroke_fill='white')
    for corridor in c['corridors']:
        v=[(x*2,y*2) for x,y in corridor['vertices_mm']];draw.line(v+[v[0]],fill='#9D84B4',width=3)
    canvas.save(out/'macro_fields.png');panels=[(out/'macro_fields.png','Source-depth macro fields','1: left grove / 2: rear rock field / 3: punctuated edge; gaps stay open')]
    examples=[(35,675,265,850),(330,652,599,815),(245,215,370,345),(230,492,380,650),(65,680,217,850)]
    for i,(rule,bounds) in enumerate(zip(c['reference_rules'],examples)):
        tile=Image.new('RGB',(1000,650),'white');d=ImageDraw.Draw(tile);ref=Image.open(refs/rule['files'][0]).convert('RGB');ref.thumbnail((200,385));tile.paste(ref,(12,20));y=20
        texts=[('OBSERVED',rule['observed']),('RULE',rule['rule']),('APPLIED',', '.join(rule['application']))]
        for label,text in texts:
            d.text((233,y),label,font=font(15),fill='#69825D');y+=25
            for line in textwrap.wrap(text,75):d.text((233,y),line,font=font(16),fill='#293D34');y+=23
            y+=12
        crop=out/f'ref_scene_{i}.png';render(result['ink'],combined,crop,palette,bounds);im=Image.open(crop).convert('RGB');im.thumbnail((700,240));tile.paste(im,(233,398));path=out/f'reference_rule_{i}.png';tile.save(path);panels.append((path,rule['id']+' / relationship to rule','Reference silhouette and texture are not copied'))
    grid(panels,out/'sheet02_reference_macro.png','02 / Reference relationships translated into F2',columns=2,cell=(1000,650),note='Nonplotting scene graph uses actual source-q contacts. Private reference thumbnails are for this analytical review only.')
    return fields


def render_sheets(fixed,result,c,corridor,data,out,root,refs):
    sets,raw,sources,vis,feather,ctx,regions=data;p=yaml.safe_load((root/c['palette_source']).read_text());ink=result['ink'];diag=lambda r:display_records(r,c,'diagnostic');old=control_vectors(root);oldink=read_vectors(root/'outputs/spring-diverse-vector-v03/ink.json.gz')['strokes']
    grid([(root/'outputs/spring-diverse-vector-v03/case3_restrained.png','Control / v03 unchanged','Original approved-comparison source preserved'),(out/'caseA_ink.png','A / macro fields in ink','79 trees; larger native rock; reallocated relays'),(out/'caseB_restrained.png','B / terrain revision','Selective A/D and geometric mist; old thin foliage method'),(out/'caseC_restrained.png','C / combined candidate','Same ink and terrain; growth-width intent and trunk wash')],out/'sheet01_full_comparison.png','01 / Fixed 600 x 900 mm Spring comparison',columns=4,cell=(570,855),note='Consistent physical scale. Width envelopes are an uncalibrated preview of explicit centerline profiles, not painted region fills.')
    fields=reference_sheet(result,c,fixed,refs,out,diag(sets['caseC']),p)
    panels=[];aink=[r for r in ink if r['source_family'] in ['A','D']]
    for name,bounds in [('Central D peak',(245,215,370,345)),('Right D peak',(395,237,520,357)),('Adjacent restrained far',(110,310,235,435))]:
        combinations=[('v03 actual control',oldink,old),('A/D ink',aink,[]),('v04 A color only',[],sets['A']),('v04 terrain on same ink',ink,sets['terrain'])]
        for i,(label,base,color) in enumerate(combinations):
            path=out/f'far_{name.split()[0]}_{i}.png';render(base,diag(color),path,p,bounds);panels.append((path,name+' / '+label,str(bounds)+' mm'))
    bounds=(235,488,375,638)
    for i,(label,base,color) in enumerate([('Hard clipping only',ink,sets['hard_only_terrain']),('Geometric feather',ink,sets['terrain']),('Final vectors only',[],sets['terrain'])]):
        path=out/f'mist_{i}.png';render(base,diag(color),path,p,bounds);panels.append((path,label,'Same raw candidate organization; alpha policy identical'))
    ret=fixed['retention'];im=np.full((900,600,3),255,dtype='uint8');im[(ret>.001)&(ret<.08)]=[205,205,205];im[(ret>=.08)&(ret<.48)]=[224,211,170];im[ret>=.48]=[187,213,192];Image.fromarray(im).crop(bounds).resize((560,600)).save(out/'mist_zones.png');panels.append((out/'mist_zones.png','Nonplotting eligibility map','White: fully omitted; gray: extra guard; gold: transition; green: eligible'))
    grid(panels,out/'sheet03_far_D_mist.png','03 / Selective distant A/D color and real vector dissolution',columns=4,cell=(480,470),note='D remains black structural ink. Selection uses source lateral/forward/elevation meters, not a screen-distance color halo.')
    panels=[]
    for name,bounds in [('Large P / H130',(65,680,217,850)),('Overlapping B / H95',(45,710,130,837))]:
        for i,(label,color,envelopes) in enumerate([('v03 thin method',sets['thin'],False),('New gesture centerlines',sets['gestures'],False),('New width-intent envelopes',sets['gestures'],True),('Gestures + longitudinal trunk',sets['gestures']+sets['trunk'],True)]):
            path=out/f'foliage_{name.split()[0]}_{i}.png';render(ink,diag(color),path,p,bounds,envelopes=envelopes);panels.append((path,name+' / '+label,'Identical v04 tree ink and actual scene crop'))
    bounds=(105,740,168,837)
    for i,(label,color,envelopes) in enumerate([('Trunk before',[],False),('Longitudinal centerlines',sets['trunk'],False),('Trunk width-intent preview',sets['trunk'],True)]):
        path=out/f'trunk_{i}.png';render(ink,diag(color),path,p,bounds,envelopes=envelopes);panels.append((path,label,'Paths constrained to actual posed paired ink boundaries'))
    import matplotlib.pyplot as plt
    specimen=max(sets['gestures'],key=lambda r:max(r['width_profile_mm']));xy=np.asarray(specimen['xy_mm']);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    fig,ax=plt.subplots(figsize=(6,5));ax.plot(arc,specimen['width_profile_mm'],color='#64864F',lw=2);ax.set(xlabel='Centerline arc (mm)',ylabel='Preview width intent (mm)',title='One stored gesture: widening / release');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'width_profile.png',dpi=140);plt.close(fig);panels.append((out/'width_profile.png','Explicit profile / no Z calibration',specimen['id'][-62:]))
    grid(panels,out/'sheet04_vegetation_brush.png','04 / Same ink: thin paths, growth gestures and trunk wash',columns=4,cell=(485,545),note='Continuous variable-width footprints are appearance-only previews. JSON retains open centerlines, widths and normalized uncalibrated intent.')
    panels=[]
    for i,(label,bounds) in enumerate([('Dominant tree group',(35,675,265,850)),('Rock-led / rear trees',(330,655,600,819)),('Middle vegetation flow',(335,539,535,638)),('Foreground-to-middle relay',(40,620,240,834)),('Color / mist transition',(235,488,375,650))]):
        path=out/f'integrated_{i}.png';render(ink,diag(sets['caseC']),path,p,bounds);panels.append((path,label,str(bounds)+' mm; actual integrated vectors'))
    bounds=(330,655,600,819);base=Image.open(out/'integrated_1.png').convert('RGBA');overlay=np.zeros((900,600,4),dtype='uint8')
    for o in result['objects']:
        overlay[o['regions']['soft']>.1]=[62,143,115,65];overlay[o['regions']['body']]=[173,67,79,100]
    overlay=Image.fromarray(overlay).crop(bounds).resize(base.size,Image.Resampling.NEAREST);Image.alpha_composite(base,overlay).convert('RGB').save(out/'occlusion_detail.png');panels.append((out/'occlusion_detail.png','Nonplotting occlusion / contacts','Red: visible solid body; green: occupied foliage transition'))
    grid(panels,out/'sheet05_integrated_detail.png','05 / Integrated relationships and actual visibility',columns=3,cell=(690,550),note='These are actual scene crops. Source-arc and footprint checks accompany the previews; no white raster patches simulate occlusion.')
    export_channel_svg(out/'scene_centerlines.svg',ink,sets['caseC'],p);export_channel_svg(out/'color_centerlines.svg',[],sets['caseC'],p)
    for path in [out/'scene_centerlines.svg',out/'color_centerlines.svg']:
        text=path.read_text().replace('Spring v03','Spring v04').replace('Source q in meters;','Width profiles are retained in JSON; mean-width SVG is a centerline export, not a pressure simulation. Source q in meters;');path.write_text(text)
    return fields


def validate(fixed,baseline,result,c,data,out,root):
    sets,raw,sources,vis,feather,ctx,regions=data;lookup={r['id']:r for r in baseline+result['new_sources']};error=0.
    for r in result['ink']:
        line=LineString(lookup[r['source_stroke_id']]['xy_mm']);a,b=r['source_arc_mm'];error=max(error,substring(line,a,b).hausdorff_distance(LineString(r['xy_mm'])))
    assert error<1e-6 and not any(r['source_family']=='V' for r in result['ink'])
    for key in sources:
        source_lookup={r['id']:r for r in sources[key]};raw_lookup={r['id']:r for r in raw[key]}
        for r in sources[key]:
            parent=raw_lookup[r['feather_parent_source_id']];a,b=r['feather_parent_arc_mm'];assert substring(LineString(parent['xy_mm']),a,b).hausdorff_distance(LineString(r['xy_mm']))<1e-6
        for row in feather[key]+vis[key]:assert abs(sum(b-a for a,b in row['kept_intervals_mm'])+row['removed_mm']-row['source_length_mm'])<1e-6
        for r in sets[key]:
            line=LineString(source_lookup[r['source_stroke_id']]['xy_mm']);a,b=r['source_arc_mm'];p=np.asarray(r['xy_mm']);assert substring(line,a,b).hausdorff_distance(LineString(p))<1e-6;assert LineString(p).length>=2.8-1e-7
            assert r['palette_slot'] in c['spring_active_target_percent'] and np.isfinite(p).all() and p[:,0].min()>=0 and p[:,0].max()<=600 and p[:,1].max()<898
            for k in ['width_profile_mm','opacity_profile','source_forward_profile_m']+(['pressure_intent_samples'] if 'pressure_intent_samples' in r else []):assert len(r[k])==len(p) and np.isfinite(r[k]).all()
    intrusions=0;protected=0;contact_hits=0
    for r in sets['terrain']:
        xy=resample(r['xy_mm'],.45);q=sample(fixed['base']['depth_m'],xy);bb=LineString(xy).bounds;protected+=int((sample(fixed['retention'],xy)<=.001).sum());contact_hits+=int((sample(ctx['contact_clearance'],xy)<0).sum())
        for o in result['objects']:
            if intersects(bb,o['bounds']):intrusions+=int(((q>=sample(o['q'],xy)-25)&(sample(o['body_distance'],xy)<-.01)).sum())
    assert intrusions==protected==contact_hits==0
    outside=0.
    for r in sets['trunk']:outside+=width_envelope(r).difference(regions[r['structural_region_id']]).area
    assert outside<1e-5
    previous=json.loads((root/'outputs/spring-diverse-vector-v03/record.json').read_text())
    for k in ['xyz','depth_m','occupied']:assert hashlib.sha256(fixed['base'][k].tobytes()).hexdigest()==previous['field_sha256'][k]
    assert hashlib.sha256(fixed['retention'].tobytes()).hexdigest()==previous['field_sha256']['retention'];assert hashlib.sha256((root/c['palette_source']).read_bytes()).hexdigest()==previous['palette_sha256']
    for path in ['scene_centerlines.svg','color_centerlines.svg']:
        tree=ET.parse(out/path);assert all(e.attrib.get('fill','none')=='none' for e in tree.iter());assert not any(e.tag.rsplit('}',1)[-1] in ['polygon','rect','image'] for e in tree.iter())
    assert sets['caseB'][:len(sets['terrain'])]==sets['caseC'][:len(sets['terrain'])]
    return dict(ink_source_arc_error_mm=error,raw_feather_visible_lineage_exact=True,source_length_conserved=True,profiles_aligned=True,legacy_V_absent=True,terrain_hard_body_intrusions=intrusions,fully_omitted_terrain_color_samples=protected,protected_root_color_hits=contact_hits,trunk_preview_outside_paired_support_mm2=outside,same_ink_for_A_B_C=digest(result['ink']),same_terrain_color_for_B_C=True,source_fields_and_palette_unchanged=True,SVG_open_centerlines_only=True,pressure_calibrated=False)


def review_pass(fixed,baseline,result,c,corridor,data,out,root,refs):
    sets,raw,sources,vis,feather,ctx,regions=data;fields=render_sheets(fixed,result,c,corridor,data,out,root,refs);validation=validate(fixed,baseline,result,c,data,out,root)
    control=control_vectors(root);spatial={k:spatial_metrics(v,fixed,ctx) for k,v in [('v03',control),('v04',sets['terrain'])]};mist={k:mist_metrics(v,fixed,ctx) for k,v in [('hard_only',sets['hard_only_terrain']),('feathered',sets['terrain'])]}
    old=json.loads((root/'outputs/spring-diverse-vector-v03/record.json').read_text());counts={key:dict(paths=len(value),length_mm=sum(LineString(r['xy_mm']).length for r in value)) for key,value in sets.items()}
    r=dict(study=c['study'],config=c,control_v03_commit=c['control_v03_commit'],field_sha256=old['field_sha256'],input_sha256=old['input_sha256'],baseline_sha256=c['baseline_sha256'],palette_sha256=old['palette_sha256'],reference_sha256=c['reference_sha256'],macro_fields=fields,spatial_color=spatial,mist=mist,counts=counts,validation=validation,
        implementation_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'src/datascape/integration/macro_wash.py',root/'src/datascape/rendering/spring_macro_study.py',Path(__file__).resolve(),root/'configs/scenes/seoul_spring_macro_v04.json']},
        publication='Local only; no push, PR update, merge or publication',display='Explicit continuous stroke-footprint envelopes for foliage/trunk preview only. Centerline SVG uses mean width; JSON retains profiles. No pressure/Z/pigment calibration.',readiness='Stop for visual review; no production output')
    write_json(out/'record.json',r);write_json(out/'validation.json',validation)
    with (out/'palette_usage.csv').open('w',newline='') as h:
        w=csv.writer(h);w.writerow(['slot','target_percent','v03_length_mm','v04_length_mm'])
        for slot in c['spring_active_target_percent']:w.writerow([slot,c['spring_active_target_percent'][slot],sum(LineString(x['xy_mm']).length for x in control if x['palette_slot']==slot),sum(LineString(x['xy_mm']).length for x in sets['caseC'] if x['palette_slot']==slot)])
    with (out/'placement.csv').open('w',newline='') as h:
        w=csv.writer(h);w.writerow(['object_id','kind','group','source_forward_m','x_mm','y_mm','height_mm','visible_paths'])
        for o in result['objects']:w.writerow([o['id'],o['kind'],o['group'],o['site']['source_forward_m'],*o['site']['xy_mm'],o.get('height_mm',''),len(result['visible_by_owner'][o['id']])])
    print('Validated v04',json.dumps(spatial),flush=True);return r
