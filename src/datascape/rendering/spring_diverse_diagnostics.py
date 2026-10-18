"""Focused actual-scene diagnostics, provenance checks and records for v03."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,time,platform,xml.etree.ElementTree as ET
import html,csv
import numpy as np
import yaml
from PIL import Image,ImageDraw,ImageFont,ImageOps
from shapely.geometry import LineString,Point,box
from shapely.ops import substring
from datascape.rendering.spring_diverse_study import render as _render
from datascape.rendering.spring_diverse_study import display_records
from datascape.integration.visibility import digest
from datascape.strokes.density_rhythm import layer_digest
from datascape.strokes.vector import read_vectors,resample,sample

def render(ink,color,path,palette,bounds,pixels=None):
    x0,y0,x1,y1=bounds
    return _render(ink,color,path,palette,bounds,(round((x1-x0)*4),round((y1-y0)*4)))


FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def font(size):return ImageFont.truetype(FONT,size)


def grid(panels,path,title,columns=3,cell=(480,340),note=''):
    cw,ch=cell;rows=int(np.ceil(len(panels)/columns));top=88 if note else 62
    canvas=Image.new('RGB',(columns*cw+32,rows*(ch+65)+top+20),'#F1F0EC');d=ImageDraw.Draw(canvas)
    d.text((16,14),title,font=font(24),fill='#172D2B')
    if note:d.text((16,48),note,font=font(14),fill='#455450')
    for i,(p,label,sub) in enumerate(panels):
        x=16+(i%columns)*cw;y=top+(i//columns)*(ch+65)
        d.text((x+4,y),label,font=font(17),fill='#172D2B')
        if sub:d.text((x+4,y+25),sub,font=font(12),fill='#5D625F')
        img=Image.open(p).convert('RGB');img=ImageOps.contain(img,(cw-16,ch))
        canvas.paste(img,(x+(cw-16-img.width)//2,y+48+(ch-img.height)//2))
    canvas.save(path)


def export_channel_svg(path,ink,colors,palette):
    """Open carrier paths with inspectable palette, channel and source identity."""
    with Path(path).open('w') as h:
        h.write('<svg xmlns="http://www.w3.org/2000/svg" width="600mm" height="900mm" viewBox="0 0 600 900">\n<title>Datascape Spring v03 vector supports</title>\n')
        h.write('<metadata>Source q in meters; canvas in mm. Display alpha is not dilution. See JSON for complete source arcs and profiles. No painted regions.</metadata>\n')
        channels=[('structural-ink',ink)]+[(k,[r for r in colors if r['color_channel']==k]) for k in ['A-derived','C-derived','material-C-like']]
        for channel,records in channels:
            h.write(f'<g id="{channel}" fill="none" stroke-linecap="round" stroke-linejoin="round">\n')
            for r in records:
                p=np.asarray(r['xy_mm']);w=np.asarray(r.get('width_profile_mm',[r['width_mm']]*len(p)));a=np.asarray(r.get('opacity_profile',[r.get('preview_opacity',1.)]*len(p)))
                slot=r.get('palette_slot','ink');hexvalue=palette['slots'][slot]['preview_hex'] if slot!='ink' else '#000000'
                attrs=f'data-source="{html.escape(r["source_stroke_id"],quote=True)}" data-slot="{slot}" data-owner="{html.escape(r["owner_id"],quote=True)}"'
                if channel=='structural-ink':
                    for j,(u,v,ww,aa) in enumerate(zip(p[:-1],p[1:],(w[:-1]+w[1:])/2,(a[:-1]+a[1:])/2)):
                        h.write(f'<path {attrs} d="M{u[0]:.6f},{u[1]:.6f} L{v[0]:.6f},{v[1]:.6f}" stroke="{hexvalue}" stroke-width="{ww:.6f}" stroke-opacity="{aa:.6f}"/>\n')
                else:
                    d='M'+f'{p[0,0]:.6f},{p[0,1]:.6f}'+' '.join(f' L{x:.6f},{y:.6f}' for x,y in p[1:])
                    h.write(f'<path {attrs} d="{d}" stroke="{hexvalue}" stroke-width="{w.mean():.6f}" stroke-opacity="{a.mean():.6f}"/>\n')
            h.write('</g>\n')
        h.write('</svg>\n')


def render_diagnostics(fixed,result,c,corridor,sets,context,out):
    out=Path(out);p=yaml.safe_load(Path(c['palette_source']).read_text());ink=result['ink'];diag=lambda a:display_records(a,c,'diagnostic')
    control=Path('outputs/spring-cluster-vector-v02/03_layered.png')
    grid([(control,'Case 0 / frozen v02','Original 03 layered image; unchanged'),(out/'case1_ink.png','Case 1 / diverse ink','Same ink is used in Cases 2 and 3'),
        (out/'case2_restrained.png','Case 2 / A + C','Displaced A / denser C / restrained materials'),
        (out/'case3_restrained.png','Case 3 / structured layers','Growth / rock structure / shared ground')],out/'sheet01_full_comparison.png',
        '01 / Continuous Spring comparison',columns=4,cell=(570,855),note='All compositions are 600 x 900 mm at the same scale. Restrained display; diagnostic visibility is supplied separately.')
    # The matched A-control comparison is generated from the same A selection.
    crops=[('Near',(190,716,290,796)),('Middle',(200,510,300,590)),('Far',(240,265,340,345))]
    aink=[r for r in ink if r['source_family']=='A'];panels=[]
    combinations=[('A ink',aink,[]),('Coincident control',aink,sets['A_coincident']),('Displaced A',aink,sets['A']),
                  ('A color only',[],sets['A']),('C color only',[],sets['C']),('Ink + displaced A + C',ink,sets['A']+sets['C'])]
    for depth,bounds in crops:
        for j,(label,base,color) in enumerate(combinations):
            path=out/f's02_{depth.lower()}_{j}.png';render(base,diag(color),path,p,bounds,(500,400))
            panels.append((path,depth+' / '+label,f'crop {bounds}; mm'))
    grid(panels,out/'sheet02_color_structure.png','02 / A displacement and C structure',columns=6,cell=(410,328),
        note='Same crop in each row. Diagnostic alpha x2.8. A frame: <=2.4 mm normal offset, local-spacing bound; C: 3 passes + 8-mm field lattice.')
    group_crops=[('Tree-dominant',(35,674,220,851)),('Rock-dominant',(342,664,561,815)),('Vegetation only',(0,567,75,651)),
                 ('Rock only',(0,694,88,763)),('Mixed attachment',(89,557,229,681)),('Middle vegetation belt',(337,537,536,630))]
    panels=[]
    for i,(label,bounds) in enumerate(group_crops):
        path=out/f's03_group_{i}.png';render(ink,diag(sets['case3']),path,p,bounds,(780,620))
        panels.append((path,label,f'Actual scene crop {bounds} mm; individual crop scale'))
    grid(panels,out/'sheet03_composition_roles.png','03 / Different relationships in the actual scene',columns=3,cell=(660,510),
        note='No catalog-only demonstrations. Every panel is a crop from the fixed Case 1/2/3 composition.')
    panels=[];materials=[('Vegetation / branch growth',(52,672,218,840),'vegetation'),('Rock / planes and burial',(348,676,554,809),'rock'),('Soil / shared broader support',(82,807,213,854),'Soil')]
    for i,(label,bounds,kind) in enumerate(materials):
        local=[r for r in sets['material_layered'] if r['color_kind']==kind]
        for j,(base,title) in enumerate([([],label+' / color only'),(ink,label+' / ink + color')]):
            path=out/f's04_material_{i}_{j}.png';render(base,diag(local),path,p,bounds,(900,550));panels.append((path,title,str(bounds)+' mm'))
    panels=[panels[i] for i in [0,2,4,1,3,5]]
    for name,bounds in [('Near',(49,680,219,850)),('Middle',(343,485,513,655)),('Far',(423,317,593,487))]:
        path=out/f's04_depth_{name.lower()}.png';render(ink,diag(sets['case3']),path,p,bounds,(700,700));panels.append((path,name+' / source-q modulation','Same physical crop 170 x 170 mm'))
    grid(panels,out/'sheet04_material_depth.png','04 / Structure-specific color and actual depth',columns=3,cell=(620,420),
        note='Discrete palette slots only. Diagnostic display. The JSON/SVG retains slot IDs, branch/plane/terrain references and source q.')
    # Placement and protected whitespace overlay. This is explicitly nonplotting.
    placement=Image.open(out/'case1_ink.png').convert('RGBA');d=ImageDraw.Draw(placement)
    colors={'near':'#A3472D','middle':'#276D55','far':'#2D628B'}
    for site in result['sites']:
        x,y=site['site']['xy_mm'];q=site['site']['source_forward_m'];name='near' if q<1000 else 'middle' if q<2200 else 'far'
        d.ellipse((x*2-3,y*2-3,x*2+3,y*2+3),fill=colors[name])
    for g in c['corridors']:
        v=[(x*2,y*2) for x,y in g['vertices_mm']];d.line(v+[v[0]],fill='#997CBB',width=3)
    for i,g in enumerate(c['groups']):
        x,y=g['center_mm'];label=f'G{i+1:02d} / {g["role"]}'
        xx=max(8,min(815,int(x*2-60)));yy=int(y*2+14)
        d.text((xx,yy),label,font=font(16),fill='#273E37',stroke_width=2,stroke_fill='white')
    placement.convert('RGB').save(out/'placement_map.png')
    # Masks derive from retained ink. Diagnostic colored areas are never paint.
    overlay=np.zeros((900,600,4),dtype='uint8')
    for o in result['objects']:
        if o['kind'] not in ('tree','rock'):continue
        overlay[o['regions']['soft']>.05]=[222,177,55,70]
        if o['kind']=='tree':overlay[o['regions']['core']&o['visible']]=[44,121,114,95]
        overlay[o['regions']['body']]=[171,57,73,130]
    maskimage=Image.fromarray(overlay).resize((1200,1800),Image.Resampling.NEAREST)
    masked=Image.alpha_composite(Image.open(out/'case1_ink.png').convert('RGBA'),maskimage)
    maskbounds=(342,662,561,817);masked.crop(tuple(int(v*2) for v in maskbounds)).convert('RGB').save(out/'occupied_core_diagnostic.png')
    raw=[r for r in read_vectors(c['baseline'])['strokes'] if r['layer'] not in ('V','C')]+result['new_sources']
    raw=[r for r in raw if r.get('source_family')!='C']
    render(raw,[],out/'overlap_before.png',p,maskbounds,(876,620));render(ink,[],out/'overlap_after.png',p,maskbounds,(876,620))
    rootbounds=(154,796,225,849)
    render(ink,diag(sets['case3']),out/'root_contact_crop.png',p,rootbounds,(852,636))
    grid([(out/'placement_map.png','Contact / depth / protected corridors','Rust <1km; green 1-2.2km; blue >=2.2km; purple: open corridor'),
          (out/'occupied_core_diagnostic.png','Nonplotting masks','Red: body; green: occupied core; gold: selective transition'),
          (out/'overlap_before.png','Before vector clipping','Original sources; includes deliberately hidden portions'),
          (out/'overlap_after.png','After vector clipping','Rock in front; rear tree parts physically omitted from vectors'),
          (out/'root_contact_crop.png','Exposed root support repair','Selective native Soil addition, not a white or opaque mock-up')],
        out/'sheet05_placement_visibility.png','05 / Placement, real clipping and whitespace',columns=3,cell=(630,700),
        note='All color overlays on this sheet are diagnostics only. See placement.csv for physical dimensions and exact source-q contacts.')
    export_channel_svg(out/'scene_layers.svg',ink,sets['case3'],p);export_channel_svg(out/'color_only.svg',[],sets['case3'],p)
    for ch in ['A','C'] :export_channel_svg(out/(ch+'_color_only.svg'),[],sets[ch],p)
    measure_A_separation(ink,sets,out)
    with (out/'placement.csv').open('w',newline='') as h:
        w=csv.writer(h);w.writerow(['object_id','group','composition_role','kind','source_forward_m','x_mm','y_mm','height_mm','support_bounds_mm','representation','visible_path_count'])
        for o in result['objects']:w.writerow([o['id'],o['group'],o['composition_role'],o['kind'],o['site']['source_forward_m'],*o['site']['xy_mm'],o.get('height_mm',''),list(o['support'].bounds) if 'support' in o else '',o['representation'],len(result['visible_by_owner'][o['id']])])


def measure_A_separation(ink,sets,out):
    """Reproducible sampled distance from color to the visible A centerlines."""
    from scipy.spatial import cKDTree
    from datascape.rendering.spring_integration import write_json
    cloud=np.concatenate([resample(r['xy_mm'],.2) for r in ink if r['source_family']=='A']);tree=cKDTree(cloud);result={}
    for key,records in [('displaced',sets['A']),('coincident_control',sets['A_coincident'])]:
        distances=[];depths=[]
        for r in records:
            xy=np.asarray(r['xy_mm']);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
            points=resample(xy,.3);at=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
            distances.extend(tree.query(points)[0]);depths.extend(np.interp(at,arc,r['source_forward_profile_m']))
        d=np.asarray(distances);q=np.asarray(depths);stats={}
        for label,mask in [('all',np.ones(len(d),bool)),('near',q<1000),('middle',(q>=1000)&(q<2200)),('far',q>=2200)]:
            z=d[mask];stats[label]=dict(samples=len(z),nearest_A_centerline_distance_p10_p50_p90_mm=np.quantile(z,[.1,.5,.9]).tolist(),fraction_more_than_0_25mm_from_A=float((z>.25).mean()))
        result[key]=stats
    result['method']='Visible A sampled every .2mm; color every .3mm; nearest sampled centerline distance. Approximate separation, not pigment/brush-edge clearance.'
    write_json(Path(out)/'A_separation_metrics.json',result)
    return result


def validate_pass(fixed,baseline,result,sets,sources,decisions,c,context,root,out=None):
    out=Path(out) if out is not None else root/'outputs/spring-diverse-vector-v03'
    assert not any(r['source_family']=='V' for r in result['ink'])
    assert sum(s['layer']=='V' for s in baseline)==result['legacy_V_paths_removed']==5200
    all_sources={r['id']:r for r in baseline+result['new_sources']};max_error=0.
    for r in result['ink']:
        original=LineString(all_sources[r['source_stroke_id']]['xy_mm']);a,b=r['source_arc_mm']
        max_error=max(max_error,substring(original,a,b).hausdorff_distance(LineString(r['xy_mm'])))
    assert max_error<1e-6
    for key,rows in decisions.items():
        for row in rows:
            assert abs(sum(b-a for a,b in row['kept_intervals_mm'])+row['removed_mm']-row['source_length_mm'])<1e-6
    for row in result['terrain_ledger']+result['object_ledger']:
        assert abs(sum(b-a for a,b in row['kept_intervals_mm'])+row['removed_mm']-row['source_length_mm'])<1e-6
    for key in sources:
        lookup={r['id']:r for r in sources[key]}
        for r in sets[key]:
            p=np.asarray(r['xy_mm']);assert np.isfinite(p).all() and p[:,0].min()>=0 and p[:,0].max()<=600 and p[:,1].max()<898
            assert r['palette_slot'] in c['spring_active_target_percent']
            for field in ['width_profile_mm','opacity_profile','source_forward_profile_m']:
                assert len(r[field])==len(p) and np.isfinite(r[field]).all()
            original=LineString(lookup[r['source_stroke_id']]['xy_mm']);a,b=r['source_arc_mm']
            assert substring(original,a,b).hausdorff_distance(LineString(p))<1e-6
            assert LineString(p).length>=2.8-1e-7
        assert len(set(r['id'] for r in sets[key]))==len(sets[key])
    assert digest(sets['case2'][:len(sets['A'])+len(sets['C'])])==digest(sets['case3'][:len(sets['A'])+len(sets['C'])])
    from datascape.integration.cluster_scene import intersects
    hard_intrusions=0
    terrain_records=[r for r in result['ink'] if r['source_family'] in ('A','B','D')]+sets['A']+sets['C']
    for r in terrain_records:
        xy=resample(r['xy_mm'],.65);q=sample(fixed['base']['depth_m'],xy);bounds=LineString(xy).bounds
        for o in result['objects']:
            if not intersects(bounds,o['bounds']):continue
            back=q>=sample(o['q'],xy)-25.
            hard_intrusions+=int(np.sum(back&(sample(o['body_distance'],xy)<-.01)))
    assert hard_intrusions==0
    root_sites=[s for s in result['sites'] if s['kind'] in ('tree','rock')]
    assert all(min(s['site']['barycentric'])>=-1e-7 for s in root_sites)
    palette=root/c['palette_source'];assert hashlib.sha256(palette.read_bytes()).hexdigest()==json.loads((root/'outputs/spring-cluster-vector-v02/record.json').read_text())['palette_sha256']
    for path in ['scene_layers.svg','color_only.svg','A_color_only.svg','C_color_only.svg']:
        tree=ET.parse(out/path)
        assert all(e.attrib.get('fill','none')=='none' for e in tree.iter())
        assert not any(e.tag.rsplit('}',1)[-1] in ['polygon','rect','ellipse','image'] for e in tree.iter())
    return dict(legacy_V_absent=True,ink_source_arc_max_error_mm=max_error,color_source_arc_exact=True,
        ledger_length_conserved=True,profiles_aligned=True,active_palette_hex_unchanged=True,
        same_ink_geometry_for_case1_case2_case3=digest(result['ink']),same_A_C_geometry_between_case2_case3=True,
        contact_barycentric_valid=True,terrain_color_hard_body_intrusions=hard_intrusions,no_SVG_painted_regions=True,physical_calibration_claim=False,
        geometric_limits='Support-relative 2.5D clipping and raster decisions; no volumetric overhang/depth certification')


def write_record(fixed,baseline,result,c,sets,color_metrics,validation,frozen,out,root,start):
    files=[root/'src/datascape/integration/diverse_scene.py',root/'src/datascape/integration/diverse_color.py',
        root/'src/datascape/rendering/spring_diverse_study.py',root/'src/datascape/rendering/spring_diverse_diagnostics.py',root/'configs/scenes/seoul_spring_diverse_v03.json']
    object_bands={k:Counter() for k in ['near','middle','far']}
    for o in result['objects']:
        q=o['site']['source_forward_m'];band='near' if q<1000 else 'middle' if q<2200 else 'far'
        object_bands[band][o['kind']]+=1
    r=dict(study=c['study'],parent_commit=c['parent_commit'],config=c,continuous_mm=[600,900],
        fixed_control='outputs/spring-cluster-vector-v02/03_layered.png',
        v02_control_sha256=hashlib.sha256((root/'outputs/spring-cluster-vector-v02/03_layered.png').read_bytes()).hexdigest(),
        baseline_sha256=c['baseline_sha256'],field_sha256=frozen,input_sha256=fixed['selection']['input_sha256'],
        source_layer_digests={k:layer_digest(baseline,k) for k in 'ABCDV'},
        implementation_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        palette_sha256=hashlib.sha256((root/c['palette_source']).read_bytes()).hexdigest(),
        source_historical=dict(file='artworks/2026-03-17_geumgang/original/source.py',sha256=hashlib.sha256((root/'artworks/2026-03-17_geumgang/original/source.py').read_bytes()).hexdigest(),
            finding='Independent ink/color row sampling with different start and gap; shared accordion x projection; unseeded historical noise and palette; no reusable bounded xy-displacement module.'),
        ink=__import__('datascape.rendering.spring_cluster_study',fromlist=['metrics']).metrics(result,[]),
        object_depth_distribution=object_bands,contact_repairs=result['contact_repairs'],color=color_metrics,
        validation=validation,runtime=dict(python=platform.python_version(),numpy=np.__version__),
        display='One continuous color stroke per carrier, mean width/alpha. Diagnostic alpha x2.8 capped at .83; restrained uses unchanged v02 policy.',
        source_forward_depth='Actual F2 source forward distance; never replaced by screen y.',
        far_representation='Exact native v10 marks at >=20mm, selectively shown as overlapping canopy aggregates. No scaled glyph copies or species inference.',
        publication='Local only; no push, PR update, merge or publication',readiness='Visual review only; no machine code/calibration',elapsed_seconds=time.time()-start)
    from datascape.rendering.spring_integration import write_json
    write_json(Path(out)/'record.json',r);write_json(Path(out)/'validation.json',validation)
    with (Path(out)/'palette_by_depth.csv').open('w',newline='') as h:
        w=csv.writer(h);w.writerow(['slot','preview_hex','target_percent','actual_case3_percent','near_length_mm','middle_length_mm','far_length_mm'])
        palette=yaml.safe_load((root/c['palette_source']).read_text())['slots'];m=color_metrics['case3']
        for slot in c['spring_active_target_percent']:w.writerow([slot,palette[slot]['preview_hex'],c['spring_active_target_percent'][slot],m['palette_length_percent'].get(slot,0.),*[m['depth'][b]['palette_length_mm'].get(slot,0.) for b in ['near','middle','far']]])
