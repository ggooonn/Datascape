"""Four material-aware physical-size catalog sheets; no locked scene inputs."""
import argparse,gzip,hashlib,html,json,math
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict,replace
import xml.etree.ElementTree as ET
import numpy as np
from shapely import affinity
from shapely.geometry import LineString,Point,Polygon,box,mapping
from shapely.ops import unary_union
from datascape.ground.grammar import path_record
from datascape.ground.structure_v02 import make_mass
from datascape.rendering.rock_ground_review_controls import alternatives,hierarchical_detail,DensityControls
from datascape.ground.structural_detail_v05 import base_mass,formation,FormationControls,feature_detail,PhysicalDetailPolicy
from datascape.ground.material_review_v05 import tag,family,appearance,angle_audit,c_intersections,ground_gradient
from datascape.ground.patch_system_v04 import PatchSpec,PatchControls,patch_system,host_function
from datascape.ground.surface_ground_v02 import ground_source
from datascape.ground.interaction import plan,replacement_intervals,Corridor,Region,duplicate_coverage
from datascape.rendering.rock_ground_catalog_support import tree_fixture
from datascape.rendering.rock_ground_catalog_fixtures import shared_ground_fixture
from datascape.rendering.rock_ground_catalog_support import _paths,body_regions,_geometry,_poly


def place(masses,center_x,baseline):
    masses=deepcopy(masses);b=unary_union([m.surface.support for m in masses]).bounds
    dx=center_x-(b[0]+b[2])/2;dy=baseline-b[3];delta=np.array([dx,dy])
    for m in masses:
        m.surface.support=affinity.translate(m.surface.support,dx,dy)
        m.surface.planes=[np.asarray(p)+delta for p in m.surface.planes]
        m.white_reserve=affinity.translate(m.white_reserve,dx,dy);m.pigment_support=affinity.translate(m.pigment_support,dx,dy)
        m.gaps=[dict(g,geometry=affinity.translate(g['geometry'],dx,dy)) for g in m.gaps]
        m.field=replace(m.field,origin=tuple(np.asarray(m.field.origin)+delta))
        if 'anchor_mm' in m.surface.info:m.surface.info['anchor_mm']=(np.asarray(m.surface.info['anchor_mm'])+delta).tolist()
        for p in m.surface.paths:p['xy_mm']=(np.asarray(p['xy_mm'])+delta).tolist()
    return masses


def cell(title,note,paths,masses=(),ground=None,mode='ink',diagnostic=False,corridor=None,features=None):
    return dict(title=title,note=note,paths=paths,masses=masses,ground=ground,mode=mode,diagnostic=diagnostic,corridor=corridor,features=features or [])


def regular(cells,page=(420,594),cols=1):
    w,h=page;rows=math.ceil(len(cells)/cols);cw=(w-28-4*(cols-1))/cols;ch=(h-56-7*(rows-1))/rows
    return [(14+(i%cols)*(cw+4),28+(i//cols)*(ch+7),cw,ch,c) for i,c in enumerate(cells)]


def sheet(out,key,title,subtitle,layout,page):
    w,h=page
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">',f'<rect width="{w}" height="{h}" fill="white"/>',
         f'<text x="14" y="13" font-family="sans-serif" font-size="5" font-weight="bold">{html.escape(title)}</text>',
         f'<text x="14" y="21" font-family="sans-serif" font-size="2.4" fill="#555">{html.escape(subtitle)}</text>',
         f'<text x="14" y="{h-7}" font-family="sans-serif" font-size="2.3" fill="#666">{w} x {h} mm | Native mm, print 100%; check ruler. 0.60/0.65 mm rock, 0.60 ground, 0.80 tree footprints are assumptions.</text>']
    for i,(x,y,cw,ch,c) in enumerate(layout):
        svg.append(f'<g transform="translate({x} {y})" data-cell="{i}">')
        svg.append(f'<text x="1" y="5" font-family="sans-serif" font-size="3.2" font-weight="bold">{html.escape(c["title"])}</text>')
        for j,line in enumerate(c['note'].split('\n')):svg.append(f'<text x="1" y="{10+j*3.6}" font-family="sans-serif" font-size="2.15" fill="#666">{html.escape(line)}</text>')
        if c['diagnostic']:
            for m in c['masses']:
                svg.append(_geometry(m.surface.support,'#adb5b1','1.4 .8',.17))
                for p in m.surface.planes:svg.append(_geometry(Polygon(p).intersection(m.surface.support),'#b0bdc3','1 .6',.15))
            if c['ground']:
                svg.append(_geometry(c['ground'].surface.support,'#bdb28d','1 .6',.2))
                svg.append(_geometry(c['ground'].pigment_support,'#c2b99b','1 .6',.14,fill='#f0ecdf'))
                svg.append(_geometry(c['ground'].white_reserve,'#b69cba','1.5 .8',.2))
            if c['corridor']:svg.append(_geometry(c['corridor'].geometry,'#b69cba','1.5 .8',.2))
            for f in c['features']:
                svg.append(_geometry(f['zone'],'#b5ab75','1 .7',.16))
                svg.append(_poly(f['carrier'].coords,'fill="none" stroke="#b06b55" stroke-width=".35" stroke-dasharray="1 .7"'))
        svg.append('<g fill="none" stroke-linecap="round" stroke-linejoin="round">')
        for p in c['paths']:
            color=appearance(p,c['mode'])
            if color is None:continue
            width=p.get('assumed_footprint_mm',p['width_mm'])
            svg.append(_poly(p['xy_mm'],f'stroke="{color}" stroke-width="{width}" data-family="{family(p)}" data-source="{html.escape(p.get("source_stroke_id",p["id"]))}"'))
        svg.append('</g>')
        svg.append(f'<path d="M3 {ch-4} h10 M3 {ch-6} v4 M13 {ch-6} v4" fill="none" stroke="#666" stroke-width=".18"/><text x="16" y="{ch-3}" font-family="sans-serif" font-size="2.1" fill="#666">10 mm</text></g>')
    svg.append('</svg>');data='\n'.join(svg)
    ET.fromstring(data);(out/f'{key}.svg').write_text(data)
    import cairosvg
    cairosvg.svg2png(bytestring=data.encode(),write_to=str(out/f'{key}.png'),dpi=105)


DEFAULT_CONFIG=Path(__file__).resolve().parents[3]/'configs/catalogs/rock_ground_v05.json'

def build(config_path=DEFAULT_CONFIG):
    config=json.loads(Path(config_path).read_text())
    physical=PhysicalDetailPolicy(**config['physical_detail_policy'])
    states={};sources={};audits={};geometry={};fixtures=[];sheets=[];supp=[];catalog=[]
    def solve(key,raw,masses=(),regions=(),corridor=None,replacements=None,protected=None):
        raw=tag(raw)
        for p in raw:
            if p['layer']=='rock-ink' and regions:p['assumed_footprint_mm']=max(.6,p['width_mm'])
        final,a=plan(raw,[*body_regions(masses),*regions],corridor,replacements,protected=protected)
        states[key]=final;sources[key]=raw;audits[key]=a
        return final
    # Same accepted B mass geometry and source macro, old detail versus feature detail.
    b=alternatives()['B'];old=[hierarchical_detail(m,DensityControls(detail_level=1))[0] for m in b]
    new=[];feature_info=[];detail_audits=[]
    for m in b:
        refined,a,z=feature_detail(m,physical_policy=physical);new.append(refined);feature_info+=z['features'];detail_audits.append(a)
    old_final=solve('structure-v04',_paths(old),old);new_final=solve('structure-v05',_paths(new),new)
    audits['structure-v05']['feature_details']=detail_audits
    geometry['structure-v04']=dict(masses=old);geometry['structure-v05']=dict(masses=new,features=feature_info)
    cells=[cell('v04 routine | same B composition',f'{len(old_final)} rock paths | unchanged body / seed / field\nMeso lattice in bounded local windows',old_final,old),
           cell('v05 | feature-linked structural shoulders',f'{len(new_final)} rock paths | unchanged body / macro\nUnequal short runs beside existing fractures; open release',new_final,new)]
    sheets.append(('01_structure','01 / Structural stroke refinement','Accepted B composition held fixed. Shape is not reopened; structural feature carriers replace the v04 hatch-window detail.',regular(cells,(420,297)),(420,297)))
    dc=[cell(c['title'],c['note'],c['paths'],c['masses'],mode='sources',diagnostic=True,features=feature_info if i else []) for i,c in enumerate(cells)]
    supp.append(('01_feature_layers','Structure / carrier and support diagnostic','Dashed ochre regions follow actual fracture carriers, not rectangular or elliptic texture windows. No added detail on XS/S.',regular(dc,(420,297)),(420,297)))
    # Curated physical-scale matrix: all examples generated at requested dimensions.
    specs=config['catalog_specimens']
    rows=[(0,4,29,100,85),(4,3,143,130,100),(7,2,287,130,105),(9,2,431,138,116)]
    layout=[]
    for start,count,yy,ch,baseline in rows:
        cw=(566-4*(count-1))/count
        for j in range(count):
            key,cls,form,regime,w,h,n=specs[start+j]
            ms=formation('catalog/'+key,FormationControls(width_mm=w,height_mm=h,major_count=n,seed=config['seed'],**config['formation_controls'])) if n else [base_mass('catalog/'+key,w,h,'bedrock' if form=='bedrock A' else form,regime,seed=config['seed'])]
            ms=place(ms,cw/2,baseline);refined=[];info=[];features=[]
            for m in ms:
                r,a,z=feature_detail(m,physical_policy=physical);refined.append(r);info.append(a);features+=z['features']
            final=solve(key,_paths(refined),refined);support=unary_union([m.surface.support for m in refined]);bb=support.bounds
            counts=sum(a['added_paths'] for a in info);level='minimal' if cls=='XS' else 'sparse macro' if cls=='S' else 'macro + local shoulder'+(' / terminal' if any(p.get('detail_level')=='micro' for p in final) else '')
            density=sum(LineString(p['xy_mm']).length for p in final)/support.area
            note=f'{form} / {regime} | body {bb[2]-bb[0]:.1f} x {bb[3]-bb[1]:.1f} mm\n{level} | {len(final)} paths | {density:.3f} mm/mm2'
            c=cell(key+' | '+cls,note,final,refined);layout.append((14+j*(cw+4),yy,cw,ch,c))
            catalog.append(dict(key=key,size_class=cls,morphology=form,treatment=regime,nominal_scaffold_mm=[w,h],body_bounds_mm=list(bb),body_area_mm2=support.area,path_count=len(final),length_density_mm_per_mm2=density,detail_level=level,major_mass_count=len(refined),added_paths=counts,features=info))
            geometry[key]=dict(masses=refined,features=features);audits[key]['detail']=info
    sheets.append(('02_scale_catalog','02 / Scale-dependent Rock Catalog / XS to XL','Native physical sizes; 11 curated specimens. B groups use two / three / four major masses. A is optional exposed bedrock.',layout,(594,594)))
    # Exact v04 shared ground fixture; material intent is additional metadata only.
    g4,ms,corr,raw,_,_=shared_ground_fixture()
    raw=deepcopy(raw);fixed=[p for p in raw if family(p)!='soil'];contact=[p for p in fixed if 'protected' in p.get('grammar_part','')]
    _,_,tregs,tf=tree_fixture(root=(22,77),height=45,identity='v04/patch-tree',depth=2.2);fixtures.append(tf)
    g5,ga,contacts=ground_gradient(g4,ms,contact)
    ac=[p for p in fixed if p.get('grammar_part') in ('A-like','C-like')]
    rep=replacement_intervals(ac,g4.surface.support.buffer(.5));protect={p['id']:[[0,LineString(p['xy_mm']).length]] for p in contact}
    before=solve('ground-v04',fixed+g4.surface.paths,ms,tregs,corr,rep,protect)
    after=solve('ground-v05',fixed+g5.surface.paths,ms,tregs,corr,rep,protect)
    audits['ground-v05']['soil_gradient']=ga;audits['ground-v05']['raw_angles']=angle_audit(sources['ground-v05']);audits['ground-v05']['final_angles']=angle_audit(after)
    audits['ground-v05']['C_policy']='retain source C geometry and existing local interaction; exclude C only from ink display; final material deferred'
    for key,g in [('ground-v04',g4),('ground-v05',g5)]:geometry[key]=dict(masses=ms,ground=g,corridor=corr,contacts=contacts)
    # A single synthetic geometric contact proposal, separate from material display.
    # Original C records stay intact; only one derived interval is shortened.
    contact_footprint=unary_union([LineString(p['xy_mm']).buffer(.3) for p in contact])
    receiver_region=Region('v05/C-protected-support','v04/contact',contact_footprint,4.4,'C-contact-proposal','protected-ink-footprint',0.,0.)
    c_inputs=tag([p for p in fixed if family(p)=='C']);c_ids={p['id'] for p in c_inputs}
    c_proposed,ca=plan(c_inputs,[*body_regions(ms),*tregs,receiver_region],corr,{k:v for k,v in rep.items() if k in c_ids})
    proposed=[p for p in after if family(p)!='C']+c_proposed
    states['ground-C-contact-proposal']=proposed;sources['ground-C-contact-proposal']=deepcopy(sources['ground-v05'])
    audits['ground-C-contact-proposal']=dict(C_only_clipping=ca,nonC_reused_from='ground-v05',status='isolated polygon-clearance proposal; not adopted scene geometry',
        replacement_precision_note='Arc-substring-only trial retained 0.011 mm2 contact overlap; shared consumer unchanged. This trial uses an explicit clearance region on original C sources.')
    geometry['ground-C-contact-proposal']=dict(masses=ms,ground=g5,corridor=corr,C_clearance=receiver_region.geometry.buffer(.45,quad_segs=12))
    for key,paths in [('ground-v05',after),('ground-C-contact-proposal',proposed)]:
        cpaths=[p for p in paths if family(p)=='C']
        audits[key]['C_footprint_overlap_mm2']={f:duplicate_coverage([p for p in paths if family(p)==f],cpaths)['duplicate_mm2'] for f in ['A','rock','soil','support']}
    cc=[cell('Unchanged C | color-ready category','Original C with existing visibility / replacement\nProtected support crossing remains a physical interaction',after,ms,g5,mode='color-ready',corridor=corr),
        cell('One local C clearance | isolated proposal','Only the C0 contact interval changes\nA / object ink / protected support remain identical',proposed,ms,g5,mode='color-ready',corridor=corr)]
    supp.append(('03_C_contact_test','C / isolated protected-support interaction','Geometric contact clearance is separate from material display. This proposal does not edit the locked scene or default catalog sources.',regular(cc,(420,180),2),(420,180)))
    csrc=tag([p for p in ac if p['grammar_part']=='C-like']);asrc=tag([p for p in ac if p['grammar_part']=='A-like'])
    crossing=c_intersections(csrc,ms,g4);sources['raw-C-intersections']=crossing
    select=lambda paths,f:[p for p in paths if family(p) in f]
    cells=[cell('A | immutable source ink','Original A-like terrain source only\nNo C, rock or Soil',asrc),
           cell('C | immutable color-oriented source','Original C-like source only, diagnostic blue\nGeometry retained; no material calibration',csrc,mode='C-only'),
           cell('Rock | generated structural ink','Only rock-generated contours and structure\nSteep rock joints remain identifiable',select(after,['rock']),ms),
           cell('Soil | v04 uniform-flow control','Soil-generated ink only\nSame patch ownership as the next cell',select(before,['soil']),ground=g4),
           cell('Soil | v05 contact-density gradient','Soil ink only; length / occupancy varies near contacts\nPatch geometry and pigment support unchanged',select(after,['soil']),ground=g5),
           cell('C intersections | raw geometry audit','Blue C / red in rock / ochre in patch ownership\nDiagnostic intersection pieces never plot',csrc+crossing,ms,g4,mode='C-only',diagnostic=True),
           cell('Ink-only | C excluded from black composite','A + rock + Soil + v10 tree + protected support\nC records remain in the vector archive',after,ms,g5,corridor=corr),
           cell('Source separated | same final geometry','A gray-blue / C blue / rock brown / Soil ochre\nSupport purple / tree green / pale wash intent',after,ms,g5,mode='sources',diagnostic=True,corridor=corr),
           cell('Conceptual color-ready | same geometry','C blue color-stroke category with structural ink\nNo palette change, wash model or pressure mapping',after,ms,g5,mode='color-ready',corridor=corr)]
    sheets.append(('03_material_layers','03 / Soil, A and C / separate geometry from material','Raw sources remain intact; source intersections and final visibility are distinct. Color is a review category, not calibrated pigment.',regular(cells,(594,420),3),(594,420)))
    # One compact overview fixture, plus a less frequent A condition.
    overview=[]
    for variant in ['B','A']:
        core=formation('overview/B',FormationControls(width_mm=190,height_mm=65,major_count=3)) if variant=='B' else [base_mass('overview/A',245,76,'bedrock','jointed')]
        core=place(core,143,122);core=[feature_detail(m,physical_policy=physical)[0] for m in core]
        floor=ground_source(266,'overview/'+variant+'/AC',base_y=133);host=floor[2];fy=host_function(host)
        sub=[base_mass('overview/'+variant+'/medium',55,35,'angular','layered',anchor=(65,float(fy(65))),depth=2.5),
             base_mass('overview/'+variant+'/compact',32,22,'compact','rounded',anchor=(224,float(fy(224))),depth=2.4),
             base_mass('overview/'+variant+'/stone',14,10,'angular','layered',anchor=(252,float(fy(252))),depth=2.2)]
        sub=[feature_detail(m,physical_policy=physical)[0] for m in sub];allm=core+sub
        _,tp,tr,tf=tree_fixture(root=(22,float(fy(22))),height=35,identity='overview/'+variant+'/tree',depth=2.);tf.update(root_support_mm=[22,float(fy(22))],support_source_id=host['id']);fixtures.append(tf)
        root=path_record('overview/'+variant+'/root-support',np.c_[np.linspace(13,31,25),fy(np.linspace(13,31,25))+1.4],'overview/'+variant+'/support','protected-root-support',.6,4.5,'terrain-ink')
        opening=Corridor('overview/'+variant+'/opening',box(130,139,146,172))
        patch=patch_system('overview/'+variant+'/soil',host,[PatchSpec('medium-contact',67,2,670,3.6),PatchSpec('small-shared',229,2,430,4)],PatchControls(),opening,cross_flow_record=next(p for p in floor if p['grammar_part']=='C-like'))
        patch,pg,ci=ground_gradient(patch,allm,[root]);inputs=floor+_paths(allm)+tp+patch.surface.paths+[root]
        final=solve('overview-'+variant,inputs,allm,tr,opening,replacement_intervals(floor,patch.surface.support.buffer(.5)),{root['id']:[[0,LineString(root['xy_mm']).length]]})
        geometry['overview-'+variant]=dict(masses=allm,ground=patch,corridor=opening,contacts=ci)
        if variant=='B':
            overview += [cell('B | general-use catalog assembly','Connected mass / medium rock / compact / XS / v10 B35\nInk-only; C remains a separate source family',final,allm,patch,corridor=opening),
                         cell('B | conceptual color-ready','Exactly the same geometry as ink-only\nColor-oriented C shown separately from black ink',final,allm,patch,mode='color-ready',corridor=opening),
                         cell('B | source / ownership diagnostic','Same objects, synthetic ranks and patch ownership\nActual terrain and root attachment remain open',final,allm,patch,mode='sources',diagnostic=True,corridor=opening)]
        else:overview.append(cell('A | optional exposed-bedrock condition','Less frequent coherent mass, same subordinate policy\nCatalog fixture only; no reopened A/B silhouette study',final,allm,patch,corridor=opening))
    sheets.append(('04_overview','04 / Provisional complete Rock and Ground overview','B is the preferred general composition; A remains optional. Local catalog fixtures only; no spring scene data loaded.',regular(overview,(594,420),2),(594,420)))
    return sheets,supp,states,sources,audits,geometry,fixtures,catalog


def run(output,config_path=DEFAULT_CONFIG):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    sheets,supp,states,sources,audits,geometry,fixtures,catalog=build(config_path)
    for key,title,subtitle,layout,page in sheets+supp:sheet(out,key,title,subtitle,layout,page)
    with gzip.GzipFile(filename=str(out/'vectors.json.gz'),mode='wb',mtime=0) as f:f.write(json.dumps(dict(version='v05',states=states,source_records=sources),sort_keys=True).encode())
    (out/'audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    features=[]
    def emit(key,kind,g,**props):features.append(dict(type='Feature',geometry=mapping(g),properties=dict(state=key,kind=kind,plot=False,**props)))
    for key,item in geometry.items():
        for m in item.get('masses',[]):
            emit(key,'body-support',m.surface.support,owner=m.surface.identity,depth_rank=m.surface.depth)
            emit(key,'pictorial-white',m.white_reserve,owner=m.surface.identity)
            emit(key,'pigment-support',m.pigment_support,owner=m.surface.identity)
        for f in item.get('features',[]):
            emit(key,'feature-carrier',f['carrier'],source_id=f['source_id']);emit(key,'feature-influence',f['zone'],source_id=f['source_id'])
        if item.get('ground'):
            g=item['ground'];emit(key,'patch-ownership',g.surface.support);emit(key,'wash-intent',g.pigment_support);emit(key,'patch-white',g.white_reserve)
        if item.get('corridor'):emit(key,'open-corridor',item['corridor'].geometry)
        if item.get('C_clearance') is not None:emit(key,'C-receiver-clearance',item['C_clearance'])
        if item.get('contacts') is not None:emit(key,'declared-ground-contacts',item['contacts'])
    (out/'supports.geojson').write_text(json.dumps(dict(type='FeatureCollection',coordinate_system='local drawing millimeters; not geographic coordinates',features=features)))
    metrics={}
    for key,paths in states.items():
        ink=[p for p in paths if family(p)!='C'];lines=[LineString(p['xy_mm']) for p in paths]
        metrics[key]=dict(all_paths=len(paths),ink_paths=len(ink),C_paths=sum(family(p)=='C' for p in paths),length_mm=sum(p.length for p in lines),ink_length_mm=sum(LineString(p['xy_mm']).length for p in ink),minimum_mm=min(p.length for p in lines),bounds_mm=list(unary_union(lines).bounds))
    crop_dir=out/'specimens';crop_dir.mkdir(exist_ok=True)
    for specimen in catalog:
        key=specimen['key'];paths=states[key];b=unary_union([LineString(p['xy_mm']) for p in paths]).bounds
        margin=3.;x,y=b[0]-margin,b[1]-margin;w,h=b[2]-b[0]+margin*2,b[3]-b[1]+margin*2
        data=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="{x} {y} {w} {h}">',f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white"/>','<g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round">']
        for p in paths:data.append(_poly(p['xy_mm'],f'stroke-width="{p.get("assumed_footprint_mm",p["width_mm"])}"'))
        data+=['</g></svg>'];(crop_dir/(key+'.svg')).write_text('\n'.join(data))
    record=dict(version='v05',parent_v04='797bae966e7975c8394415169b18b80189949347',pages={s[0]:s[4] for s in sheets+supp},metrics=metrics,catalog=catalog,fixtures=fixtures,
        assumptions=dict(units='mm',rock_screen_mm=.6,contour_mm=.65,ground_mm=.6,tree_mm=.8,minimum_final_mm=2.8,measured=False),material_policy='A/object structural ink; C color-oriented intent; wash supports separate; no final palette assignment',full_scene_loaded=False,status='visual review; catalog not locked')
    record['source_files_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).parents[1]/'ground/structural_detail_v05.py',Path(__file__).parents[1]/'ground/material_review_v05.py']}
    (out/'record.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),metrics=metrics),indent=2));return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='outputs/rock-ground-v05');p.add_argument('--config',default=str(DEFAULT_CONFIG));a=p.parse_args();run(a.output,a.config)
