"""Review-only Summer vectors from DEM, accepted grammars and authored groups.

Canonical coordinates are top-down millimeters. Pressure, brush width, pigment
slots and physical timing remain uncalibrated. No motion backend is imported.
"""
from pathlib import Path
from copy import deepcopy
import argparse, gzip, hashlib, html, io, json, pickle, sys
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_erosion
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from datascape.rendering.painterly_layers import load_features
from datascape.rendering.ground_study import make_camera
from datascape.projection.ground import GroundComposite
from datascape.composition.multidepth import source_features, build_reserves
from datascape.composition.refinement import refine_reserves
from datascape.strokes.vector import sample, resample, split_at_gate, phase, clip_polyline
from datascape.strokes.generators import terrain_derivatives, structure_lines, continuity_mask
from datascape.strokes.density_rhythm import density_profile, foreground_a, transfer, c_proposals, select_c_role
from datascape.strokes.mass_density import mass_coordinates
from datascape.strokes.spacing_schedule import explicit_source_spacing_phase, trace_phase
from datascape.strokes.accordion import foreground_target, mountain_target, local_monotone_projection
from datascape.strokes.hierarchy import select_b, select_d, style, total_length
from datascape.strokes.grammar import strength_envelope
from datascape.vegetation.tree_final_scale import make_tree, vector_records, FoliageControls
from datascape.vegetation.tree_form_calibration import GrowthControls
from datascape.ground.structural_detail_v05 import formation, FormationControls, feature_detail
from datascape.rendering.rock_ground_catalog import place
from datascape.ground.patch_system_v04 import PatchSpec, PatchControls, patch_system, host_function
from datascape.integration.objects import supporting_surface, final_regions
from datascape.integration.visibility import (contact, depth_field, visibility_field, adapt,
    regions_from_tree, signed_clearance, burn, behind_object, object_gate, terrain_gate, clip_source)
from datascape.vegetation.mid_far import Evidence
from datascape.vegetation.pictorial_families_v03 import measured_tangent
from datascape.vegetation.structural_mid_far_v02 import build_representation
from datascape.rendering.spring_integration_v05 import render, grid
from viewpoints import spring_fields, skyline, boundary

ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'docs/experiments/summer_scene_v01'

def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def gz(path,value):
    with open(path,'wb') as f:
        with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:z.write(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def clip_review(original,gate,minimum_mm=2.8):
    """Bind direct source lineage and enforce the floor even for uncut paths.

    The inherited clipper retains fully positive paths unchanged. Its catalog
    floor recognizes an earlier origin tag; Summer must enforce its own floor
    before that fast path, without modifying the reusable clipping module.
    """
    r=deepcopy(original);length=LineString(r['xy_mm']).length
    if length<minimum_mm:
        return [],dict(source_id=r['id'],source_length_mm=length,kept_intervals_mm=[],
            removed_mm=length,short_dropped_mm=length,reasons=['summer-minimum-path'])
    if 'source_stroke_id' in r:r['upstream_source_stroke_id']=r['source_stroke_id']
    if 'source_arc_mm' in r:r['upstream_source_arc_mm']=r['source_arc_mm']
    r.update(source_stroke_id=r['id'],source_arc_mm=[0.,length])
    return clip_source(r,gate,minimum_mm=minimum_mm)

def progress(x):
    t=np.clip((np.asarray(x)-210)/180,0,1)
    return t*t*(3-2*t)

def fields(master,veg,out,c):
    scene=read(out/(c['selected_view']+'_scene.json'))
    lc=read(ROOT/'configs/scenes/seoul_f2_painterly_layers_v01.json');lc.update(season='SUMMER',seed=c['seed'])
    terrain,b,ndvi,counts,source=load_features(master,veg,scene,lc)
    v2=read(ROOT/'configs/scenes/seoul_f2_multidepth_whitespace_v02.json');v2['seed']=c['seed']
    v2['vegetation']['season']='SUMMER'
    f=source_features(master,b,{**v2['terrain'],'seed':c['seed']});old=build_reserves(b,f,v2)
    v3=read(ROOT/'configs/scenes/seoul_f2_painterly_composition_v03.json')
    refined=refine_reserves(b,old,[],v3,v2)
    retention=(.70*refined['legacy_local_retention']+.30*refined['local_core_retention'])*refined['global_retention']*b['occupied']
    terrain_xyz=np.nan_to_num(b['xyz']);safe=distance_transform_edt((retention>0)&b['occupied'])
    fixed=dict(base=b,terrain=terrain,features=f,old=old,refined=refined,retention=retention,
        scene=scene,source=source,vegetation_config=v2['vegetation'],_grammar_xyz=terrain_xyz,_grammar_safe=safe)
    with rasterio.open(master) as ds:camera,site=make_camera(ds,scene['primary_eye_xy_m'],scene['look_target_xy_m'],2,0,36,1)
    fixed['projection']=GroundComposite(camera,site['source_dem_at_eye_m'],**scene['composite'])
    return fixed

def terrain_vectors(fixed,master,c):
    print('Generate terrain derivatives and local A phase',flush=True)
    hc=read(ROOT/'configs/scenes/seoul_spring_stroke_hierarchy_v02.json');hc['seed']=c['seed']
    dc=read(ROOT/'configs/scenes/seoul_spring_density_rhythm_v01.json');dc['seed']=c['seed'];dc['A']['density_gain']=1.12
    dc['C']['integration'].update(seed_spacing_mm=12,separation_mm=3)
    mc=read(ROOT/'configs/scenes/seoul_spring_stroke_grammar_v03.json');mc['seed']=c['seed']
    v2=read(ROOT/'configs/scenes/seoul_spring_a_density_v02.json')
    profile=density_profile(fixed,dc);mass=mass_coordinates(fixed,[],v2)
    # Reuse the accepted local monotone solver on the new Summer terrain.
    mt,_=mountain_target(fixed,mass,profile,v2)
    b=fixed['base'];domain=continuity_mask(b)&(b['depth_m']>=1600)&(fixed['retention']>.01)
    mp,ma=local_monotone_projection(fixed,profile['phase_field'],profile['phase_field']+.70*(mt-profile['phase_field']),profile['phase_field'],domain,time_limit=90)
    nt,_=foreground_target(fixed,mp,1600)
    domain=continuity_mask(b)&(b['depth_m']<1600)&(fixed['retention']>.01)
    np_phase,na=local_monotone_projection(fixed,mp,mp+.25*(nt-mp),profile['phase_field'],domain,smoothness=6,maximum_change=6,time_limit=90)
    raw_a,aa=trace_phase(np_phase,fixed);raw_a=foreground_a(raw_a,fixed,.72)
    a=transfer(raw_a,fixed,mc)
    derivative=terrain_derivatives(master,b,{'derivative_sigma_m':60})
    vector=read(ROOT/'configs/scenes/seoul_spring_vector_study_v01.json')
    struct,_=structure_lines(b,derivative,vector['structure'],fixed['projection'].camera.azimuth_deg)
    structrows=[dict(id=f'summer-B-{i}',xy_mm=p.tolist(),width_mm=.46,layer='B') for i,p in enumerate(struct)]
    bb=transfer(select_b(structrows,fixed,derivative,hc,total_length(a)),fixed,mc)
    print('Generate directional C and sparse D',flush=True)
    cc,ca=c_proposals(fixed,derivative,fixed['projection'],dc)
    cc=transfer(select_c_role(cc,fixed,{'near':.65,'middle':.22,'far':.08},c['seed']),fixed,mc)
    dd,da=select_d(fixed,derivative,fixed['projection'].camera.azimuth_deg,hc,a+bb+cc,[])
    for r in dd:
        n=len(r['xy_mm']);envelope=strength_envelope(np.linspace(0,1,n))
        r['width_profile_mm']=(r['width_mm']*envelope).tolist();r['opacity_profile']=(.15+.85*envelope).tolist()
        r['expression']['intensity_samples']=envelope.tolist()
    rows=a+bb+cc+dd
    for r in rows:r.update(id='summer/'+r['id'],source_family=r['layer'],owner_id='summer/terrain',medium='ink',pressure_intent_compatible=True,pressure_calibrated=False)
    return rows,dict(A=aa,C=ca,D=da,masses=mass['masses'],mountain_solver=ma,foreground_solver=na),np_phase

def select_contact(fixed,xy,reach=30):
    b=fixed['base'];yy,xx=np.mgrid[:900,:600];d=(xx+.5-xy[0])**2+(yy+.5-xy[1])**2
    good=b['occupied']&(fixed['retention']>.32)&np.isfinite(b['current_ndvi'])&(b['current_observations']>=6)&(xx>25)&(xx<575)&(yy<860)
    if not (good&(d<reach*reach)).any():raise ValueError('Unsupported authored root '+str(xy))
    y,x=np.unravel_index(np.argmin(np.where(good,d,np.inf)),d.shape)
    return contact(fixed,[x+.5,y+.5])

def catalog_objects(fixed,terrain,c):
    objs=[];raw_color=[];notes=[]
    for group in c['near_groups']:
        for j,(dx,dy,height,form) in enumerate(group['members']):
            site=select_contact(fixed,[group['center_mm'][0]+dx,group['center_mm'][1]+dy]);xy=site['xy_mm'];t=float(progress(xy[0]));sc=c['summer_progression']
            lerp=lambda key:float(np.interp(t,[0,1],sc[key]))
            ident=f'summer/{group["id"]}/tree-{j}'
            tree=make_tree(form,root=xy,height=height,seed=c['seed'],identity=ident,
                controls=FoliageControls(unit_count_scale=lerp('foliage_unit_count_scale')),
                growth_controls=GrowthControls(stem_ratio=lerp('stem_ratio'),vigor=lerp('foliage_vigor')))
            rows=[adapt(r,'summer-catalog',ident,'tree') for r in vector_records(tree.marks,[tree])]
            q=depth_field(site);ret,visible=visibility_field(fixed,q);visible &= ret>.12
            obj=dict(id=ident,kind='tree',tree=tree,records=rows,q=q,retention=ret,visible=visible,site=site,
                group=group['id'],height_mm=height,regions=regions_from_tree(tree,visible))
            obj['body_distance']=signed_clearance(obj['regions']['body']);objs.append(obj)
            for r in rows:r.update(layer='tree',medium='ink',source_object_depth_m=site['source_forward_m'],source_site=site,
                seasonal_progress=t,assumed_footprint_mm=r['width_mm'])
            # Independent broad canopy passages follow catalog lobe surfaces.
            # They are not duplicates or offsets of the individual ink touches.
            for k,lobe in enumerate(tree.lobes):
                center=np.asarray(lobe['center']);rx,ry=np.asarray(lobe['radii']);angle=float(lobe['angle'])
                for v in [-.28,.27]:
                    u=np.linspace(-.75,.8,19);p=np.c_[u*rx,ry*(v+.20*(1-u*u))]
                    rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
                    p=p@rot.T+center
                    raw_color.append(dict(id=ident+f'/color/lobe-{k}-{v}',xy_mm=p.tolist(),width_mm=3.2+2*t,
                        layer='color',source_family='tree',owner_id=ident,medium='color-intent',color_group='canopy_core' if v<0 else 'canopy_edge',
                        preview_opacity=.30,source_site=site,source_object_depth_m=site['source_forward_m'],
                        origin='Independent catalog lobe sections; virtual color grouping',pressure_intent_compatible=True))
            print('Tree',ident,'raw paths',len(rows),flush=True)
    for spec in c['rocks']:
        site=select_contact(fixed,spec['target_mm'],40);spec={**spec,'target_mm':site['xy_mm'],'key':spec['id']}
        host,offset,basis=supporting_surface(fixed,terrain,spec);hf=host_function(host);x=spec['target_mm'][0];y=float(hf(x))
        ident='summer/'+spec['id'];masses=place(formation(ident,FormationControls(width_mm=spec['width_mm'],height_mm=spec['height_mm'],major_count=spec['major_count'],seed=c['seed'])),x,y)
        for mass in masses:
            m,_,_=feature_detail(mass);site=contact(fixed,m.surface.info['anchor_mm']);q=depth_field(site);ret,visible=visibility_field(fixed,q)
            body=burn(m.surface.support)&visible&(ret>.12)
            rows=[adapt(r,'summer-catalog',m.surface.identity,'rock') for r in m.surface.paths]
            for r in rows:r.update(layer='rock',medium='ink',source_site=site,source_object_depth_m=site['source_forward_m'])
            obj=dict(id=m.surface.identity,kind='rock',records=rows,q=q,retention=ret,visible=visible&(ret>.12),site=site,group=spec['group'],
                regions=dict(body=body,soft=np.zeros((900,600))),catalog_local_rank=m.surface.depth,parent_mass_id=ident)
            obj['body_distance']=signed_clearance(body);objs.append(obj)
        notes.append(dict(formation=ident,host=host,host_basis=basis,host_offset_mm=offset))
        # Shared-parent ground patch tied to the same measured support section.
        try:
            ground=patch_system(ident+'/ground',host,[PatchSpec('contact',x,3,spec['width_mm']*4,aspect_ratio=4,irregularity=.30)],
                PatchControls(spacing_mm=4.2,edge_dissolution=.5,relation='connected',merge_gap_mm=1.5),depth=site['source_forward_m'])
            rows=[adapt(r,'summer-ground',ident+'/ground','Soil') for r in ground.surface.paths]
            for r in rows:r.update(layer='Soil',medium='ink',source_site=site)
            q=depth_field(site);ret,visible=visibility_field(fixed,q)
            obj=dict(id=ident+'/ground',kind='soil',records=rows,q=q,retention=ret,visible=visible,site=site,group=spec['group'],regions=dict(body=np.zeros((900,600),bool),soft=np.zeros((900,600))))
            obj['body_distance']=signed_clearance(obj['regions']['body']);objs.append(obj)
        except ValueError as exc:notes[-1]['ground_patch_rejected']=str(exc)
    return objs,raw_color,notes

def mid_far(fixed,c):
    b=fixed['base'];ev=Evidence(b['depth_m'],np.nan_to_num(b['xyz']),np.nan_to_num(b['current_ndvi']),np.nan_to_num(b['current_observations']),b['occupied'],fixed['retention'],fixed['refined']['global_retention'],fixed['_grammar_safe'],{})
    cfg=dict(seed=c['seed'],ink_footprint_mm=.32,color_footprint_mm=1.05,minimum_ink_mm=2.8,minimum_color_mm=2.8)
    ink=[];color=[];roots=[]
    for group in c['mid_far_groups']:
        cx,cy=group['center_mm'];rx,ry=group['radius_mm'];q0,q1=group['q_range_m'];yy,xx=np.mgrid[:900,:600]
        ellipse=((xx+.5-cx)/rx)**2+((yy+.5-cy)/ry)**2
        eligible=b['occupied']&(ellipse<1)&(b['depth_m']>=q0)&(b['depth_m']<=q1)&(fixed['retention']>.25)&(b['current_observations']>=6)&np.isfinite(b['current_ndvi'])
        weight=np.exp(-2*ellipse)*(.2+.8*np.clip(np.nan_to_num(b['current_ndvi']),0,1))*eligible
        if not weight.any():raise ValueError('Empty mid/far group '+group['id'])
        rng=np.random.default_rng(int(phase(group['id'],c['seed'])*2**32));order=rng.choice(weight.size,size=min(12000,int(eligible.sum())),replace=False,p=(weight.ravel()+1e-30)/(weight.ravel()+1e-30).sum())
        sites=[];far=group['id'].startswith('far');spacing=11 if far else 14
        for idx in order:
            y,x=divmod(int(idx),600);p=[x+.5,y+.5]
            if not eligible[y,x] or any(np.linalg.norm(np.array(p)-r['root_xy_mm'])<spacing for r in sites):continue
            j=len(sites);ident=f'summer/{group["id"]}/body-{j}';site=ev.point(p)
            height=float(np.interp(phase(ident,c['seed']),[0,1],group['height_mm']))*(1+.15*float(progress(p[0])))
            r=dict(id=ident,stand_id='summer/'+group['id'],stand_index=0,stand_role='dominant' if j%4<2 else 'subordinate',
                member_index=j,member_count=group['count'],root_xy_mm=p,guide_u=float((x-cx+rx)/(2*rx)),
                guide_source_id='summer/native-q-field/'+group['id'],tangent_xy=measured_tangent(ev,np.array(p),[1,0]),height_mm=height,form=['B','U','B','P'][j%4],site=site)
            sites.append(r)
            if len(sites)>=group['count']:break
        graphs,ii,cc=build_representation(sites,'F2' if far else 'M2',cfg)
        for r in ii:r.update(layer='V',medium='ink',source_family='V',source_object_depth_m=r['source_forward_m'],pressure_intent_compatible=True)
        for r in cc:r.pop('palette_slot',None);r.update(layer='color',medium='color-intent',source_family='V',color_group='distance' if far else 'canopy_core',source_object_depth_m=r['source_forward_m'])
        ink+=ii;color+=cc;roots+=sites
    return ink,color,roots

def resolve(fixed,terrain,objects,vegetation,colors,c):
    print('Resolve reciprocal terrain/catalog visibility',flush=True)
    initial={o['id']:o['regions']['body'].copy() for o in objects}
    for obj in objects:
        for front in objects:
            if obj is front:continue
            hidden=initial[front['id']]&behind_object(obj,front,obj['q'],front['q'])
            obj['visible'] &= ~hidden;obj['regions']['body'] &= ~hidden;obj['regions']['soft'] *= ~hidden
        obj['body_distance']=signed_clearance(obj['regions']['body'])
    result=[];audit=[]
    for obj in objects:
        vv=[];gate=object_gate(fixed,obj,objects)
        for r in obj['records']:
            rows,a=clip_review(r,gate,minimum_mm=c['minimum_visible_path_mm']);vv+=rows;audit.append(a)
        final_regions(obj,vv);obj['body_distance']=signed_clearance(obj['regions']['body']);result+=vv
    tg=terrain_gate(fixed,objects)
    for number,original in enumerate(terrain):
        if number%500==0:print('Terrain visibility',number,'/',len(terrain),flush=True)
        r=adapt(original,'summer-terrain','summer/terrain',original['layer'])
        rows,a=clip_review(r,tg,minimum_mm=c['minimum_visible_path_mm']);result+=rows;audit.append(a)
    byid={o['id']:o for o in objects};col=[];gates={}
    for number,original in enumerate(vegetation+colors):
        if number%500==0:print('Vegetation/color visibility',number,'/',len(vegetation+colors),flush=True)
        r=deepcopy(original);site=r.get('source_site');q0=r.get('source_object_depth_m')
        key=r['owner_id']
        if key not in gates:
            obj=byid.get(key)
            if obj is None:
                q=np.full((900,600),q0);ret,visible=visibility_field(fixed,q)
                obj=dict(id=key,kind='vegetation',q=q,retention=ret,visible=visible,group=r.get('group_id'),site=site)
            gates[key]=object_gate(fixed,obj,objects)
        gate=gates[key]
        rows,a=clip_review(r,gate,minimum_mm=c['minimum_visible_path_mm']);audit.append(a)
        (col if r.get('medium')=='color-intent' else result).extend(rows)
    # Bind every final row to direct authoring records and uncalibrated intent.
    for i,r in enumerate(result+col):
        r.update(draw_order=i,pressure_calibrated=False,physical_plotting_validated=False,
            canonical_geometry='top-down mm; no brush simulation or physical Z',pressure_intent_compatible=True)
        r.setdefault('medium','ink');r.setdefault('expression',dict(intensity=.5,pressure_calibrated=False))
    return result,col,audit

def panel_rows(rows,number):
    """Clip with original segment parameters, including closed/retraced paths."""
    lo=(number-3)*300;hi=lo+300;result=[]
    for r in rows:
        p0=np.asarray(r['xy_mm'],float)
        lengths=np.linalg.norm(np.diff(p0,axis=0),axis=1);source_arc=np.r_[0,np.cumsum(lengths)]
        pieces=[];current=[];current_arcs=[]
        def finish():
            nonlocal current,current_arcs
            if len(current)>1 and current_arcs[-1]-current_arcs[0]>1e-8:
                pieces.append((np.asarray(current),np.asarray(current_arcs)))
            current=[];current_arcs=[]
        for i,(a,b) in enumerate(zip(p0[:-1],p0[1:])):
            if lengths[i]<1e-12:continue
            # A path lying exactly on the seam has one owner (P4), avoiding
            # duplicated length while keeping ordinary crossing endpoints.
            if number==3 and abs(a[0]-300)<1e-10 and abs(b[0]-300)<1e-10:
                finish();continue
            pp=clip_polyline([a,b],(lo,0,hi,900))
            if not pp:finish();continue
            q=pp[0];d=b-a
            at=source_arc[i]+np.clip(((q-a)@d)/(d@d),0,1)*lengths[i]
            if at[-1]-at[0]<1e-10:continue
            if current and abs(current_arcs[-1]-at[0])<1e-7 and np.linalg.norm(current[-1]-q[0])<1e-7:
                current.append(q[-1]);current_arcs.append(at[-1])
            else:
                finish();current=list(q);current_arcs=list(at)
        finish()
        for j,(p,ar) in enumerate(pieces):
            rr=deepcopy(r)
            for key in ('width_profile_mm','opacity_profile'):
                if key in r:rr[key]=np.interp(ar,source_arc,r[key]).tolist()
            if 'intensity_samples' in r.get('expression',{}):rr['expression']['intensity_samples']=np.interp(ar,source_arc,r['expression']['intensity_samples']).tolist()
            rr.update(id=r['id']+f'/P{number}-{j}',canonical_source_id=r['id'],canonical_arc_mm=[float(ar[0]),float(ar[-1])],
                xy_mm=(p-[lo,0]).tolist(),panel=number,continuous_x_offset_mm=lo)
            result.append(rr)
    return result


def stats(rows):
    ll=np.array([LineString(r['xy_mm']).length for r in rows]);layers={}
    for family in sorted(set(r['layer'] for r in rows)):
        ss=[r for r in rows if r['layer']==family];ls=[LineString(r['xy_mm']).length for r in ss]
        layers[family]=dict(strokes=len(ss),length_mm=sum(ls),under_3mm=sum(l<3 for l in ls),under_5mm=sum(l<5 for l in ls))
    dense={}
    for r in rows:
        p=resample(r['xy_mm'],2);ds=np.linalg.norm(np.diff(p,axis=0),axis=1);mid=(p[:-1]+p[1:])/2
        for cell,value in zip(np.floor(mid/100).astype(int),ds):
            key=f'{cell[0]*100},{cell[1]*100}';dense[key]=dense.get(key,0)+float(value)
    return dict(strokes=len(rows),length_mm=float(ll.sum()),length_quantiles_mm=np.quantile(ll,[0,.1,.5,.9,1]).tolist(),
        under_2_8mm=int((ll<2.8-1e-7).sum()),under_3mm=int((ll<3).sum()),under_5mm=int((ll<5).sum()),
        layers=layers,densest_100mm_cells=sorted(dense.items(),key=lambda x:-x[1])[:8],
        paper_engagement_distance_m=float(ll.sum()/1000),atomic_stroke_engagement_lower_bound=len(rows),
        contact_only_minutes_at_hypothetical_600_1200mm_min=[float(ll.sum()/600),float(ll.sum()/1200)],
        timing_scope='Distance/feed only; excludes pressure, acceleration, transfers, reloads, dwell, drying. Not a machine runtime estimate.')

def svg(rows,path,width=600,color=False):
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="900mm" viewBox="0 0 {width} 900">',
        '<title>Summer v01 canonical centerlines; complete variable intent profiles in companion JSON</title>']
    palette=read(Path(__file__).with_name('config.json'))['virtual_color_groups']
    for r in rows:
        rgb=palette[r['color_group']]['preview_hex'] if r.get('medium')=='color-intent' and color else '#202725'
        p=' '.join(f'{x:.6f},{y:.6f}' for x,y in r['xy_mm']);ident=html.escape(r['id'],quote=True)
        w=float(np.mean(r.get('width_profile_mm',[r['width_mm']])));a=float(np.mean(r.get('opacity_profile',[r.get('preview_opacity',.8)])))
        lines.append(f'<polyline data-source="{ident}" points="{p}" fill="none" stroke="{rgb}" stroke-width="{w:.6f}" opacity="{a:.5f}" stroke-linecap="round"/>')
    Path(path).write_text('\n'.join(lines+['</svg>'])+'\n')

def previews(ink,color,out,c):
    from PIL import Image,ImageDraw,ImageFont
    palette={'slots':deepcopy(c['virtual_color_groups'])}
    colored=deepcopy(color)
    for r in colored:r['palette_slot']=r['color_group']
    render(ink,colored,out/'summer_full.png',palette)
    render(ink,[],out/'summer_ink.png',palette)
    render([],colored,out/'summer_color_intent.png',palette)
    for num in (3,4):
        x=(num-3)*300;render(ink,colored,out/f'P{num}.png',palette,bounds=(x,0,x+300,900),pixels=(600,1800))
    with Image.open(out/'summer_full.png') as im:
        im=im.convert('RGB');gap=Image.new('RGB',(1280,1800),'#dedbd3');gap.paste(im.crop((0,0,600,1800)),(0,0));gap.paste(im.crop((600,0,1200,1800)),(680,0));gap.save(out/'summer_physical_pair.png')
    panels=[]
    for layer in ['A','B','C','D','V','tree','rock','Soil']:
        p=out/f'layer_{layer}.png';render([r for r in ink if r['layer']==layer],[],p,palette,pixels=(600,900));panels.append((p,layer))
    grid(panels,out/'layers.png','Summer v01 / actual final vector layers',cell=(300,450),columns=4,note='Same scale; no source geometry hidden by raster masks.')
    studies=[]
    for name,core,edge,dist in [('cool_vegetation','#477766','#a1ab70','#6a9299'),('humid_blue','#4e747b','#8f9d77','#738da7'),('warm_openings','#6b7e58','#b5ab74','#829995')]:
        pal=deepcopy(palette)
        for key,v in [('canopy_core',core),('canopy_edge',edge),('distance',dist)]:pal['slots'][key]['preview_hex']=v
        p=out/f'color_{name}.png';render(ink,colored,p,pal,pixels=(600,900));studies.append((p,name.replace('_',' ')))
    grid(studies,out/'color_studies.png','Virtual color-intent comparison / palette remains open',cell=(450,675),columns=3,note='Identical vectors; display alpha is not pigment calibration.')
    # Physical gaps are pure display insertion; Spring approved raster is untouched.
    spring=Image.open(ROOT/'artworks/spring_v13/review/approved.png').convert('RGB').resize((1200,1800))
    summer=Image.open(out/'summer_full.png').convert('RGB');canvas=Image.new('RGB',(2640,1880),'#e8e5de');draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',26)
    for i in range(4):
        im=spring if i<2 else summer;j=i%2;canvas.paste(im.crop((j*600,0,(j+1)*600,1800)),(i*680,65));draw.text((i*680+20,15),f'P{i+1} / '+('Spring' if i<2 else 'Summer provisional'),fill='#294c46',font=font)
    canvas.save(out/'transition_P1_P4.png')

def run(master,veg,out=DEFAULT,cache=None,render_images=True):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);c=read(Path(__file__).with_name('config.json'))
    if c['far_surface_micro_B_enabled']:raise NotImplementedError('Far B requires a separate linked ink/color review')
    for key,p in [('master',master),('vegetation',veg)]:
        if sha(p)!=c['input_sha256'][key]:raise ValueError('Wrong GIS source: '+key)
    if cache and Path(cache).exists():
        with open(cache,'rb') as f:fixed=pickle.load(f)
    else:
        print('Sample new Summer DEM / NDVI and omission fields',flush=True);fixed=fields(master,veg,out,c)
        if cache:
            with open(cache,'wb') as f:pickle.dump(fixed,f)
    stage=Path(str(cache)+'.previsibility.pkl') if cache else None
    config_hash=sha(Path(__file__).with_name('config.json'))
    if stage and stage.exists():
        with open(stage,'rb') as f:state=pickle.load(f)
        if state[0]!=config_hash:raise ValueError('Stale private stage cache')
        _,terrain,terrain_audit,phase_field,objects,color,notes,vi,roots=state
    else:
        terrain,terrain_audit,phase_field=terrain_vectors(fixed,master,c)
        objects,color,notes=catalog_objects(fixed,terrain,c)
        vi,vc,roots=mid_far(fixed,c);color+=vc
        if stage:
            with open(stage,'wb') as f:pickle.dump((config_hash,terrain,terrain_audit,phase_field,objects,color,notes,vi,roots),f)
    ink,col,audit=resolve(fixed,terrain,objects,vi,color,c)
    source=terrain+[r for o in objects for r in o['records']]+vi+color
    gz(out/'authoring_sources.json.gz',dict(coordinate_system='top-down mm',strokes=source))
    gz(out/'summer_ink.json.gz',dict(continuous_mm=[600,900],strokes=ink))
    gz(out/'summer_color_intent.json.gz',dict(continuous_mm=[600,900],strokes=col))
    gz(out/'visibility_ledger.json.gz',dict(entries=audit))
    save(out/'placement.json',dict(near=[dict(id=o['id'],kind=o['kind'],site=o['site'],group=o.get('group')) for o in objects],mid_far=roots,rocks=notes))
    # Portable reduced-precision diagnostics; production source remains TIFF + config.
    field_buffer=io.BytesIO()
    np.savez_compressed(field_buffer,xyz=fixed['base']['xyz'].astype('float32'),depth=fixed['base']['depth_m'].astype('float32'),
        occupied=fixed['base']['occupied'],retention=fixed['retention'].astype('float32'),phase=phase_field.astype('float32'),ndvi=fixed['base']['current_ndvi'].astype('float32'))
    temporary=out/'summer_fields.npz.pending'
    temporary.write_bytes(field_buffer.getvalue());temporary.replace(out/'summer_fields.npz')
    svg(ink+col,out/'summer_scene.svg',color=True);svg(ink,out/'summer_ink.svg')
    panels={}
    for number in (3,4):
        ii=panel_rows(ink,number);cc=panel_rows(col,number);panels[f'P{number}']=dict(ink=stats(ii),color=stats(cc))
        gz(out/f'P{number}.vectors.json.gz',dict(panel=number,size_mm=[300,900],continuous_x_offset_mm=(number-3)*300,strokes=ii+cc))
        svg(ii+cc,out/f'P{number}.svg',width=300,color=True)
    save(out/'stroke_statistics.json',dict(authoring=stats(source),visible_ink=stats(ink),visible_color_intent=stats(col),panels=panels,
        seam_clipping_note='Clipped panel fragments can be shorter than 2.8 mm; retained losslessly and flagged, not auto-executed.'))
    # Solver diagnostics contain ndarrays; publish only scalar fields and small arrays.
    def portable(x):
        if isinstance(x,np.ndarray):return dict(shape=list(x.shape),min=float(np.nanmin(x)),max=float(np.nanmax(x)))
        if isinstance(x,dict):return {k:portable(v) for k,v in x.items()}
        if isinstance(x,list):return [portable(v) for v in x]
        if isinstance(x,np.generic):return x.item()
        return x
    save(out/'generation.json',dict(config=c,config_sha256=sha(Path(__file__).with_name('config.json')),source=fixed['source'],terrain=portable(terrain_audit),
        selected_view=c['selected_view'],far_micro_B_enabled=False,production_Gcode_generated=False,Spring_modified=False,
        visibility='Accepted reciprocal 2.5D catalog gates and exact original-arc interval clipping; nominal widths, no wet-brush certificate'))
    if render_images:previews(ink,col,out,c)
    print(json.dumps(dict(ink_paths=len(ink),color_paths=len(col),ink_length_mm=total_length(ink)),indent=2),flush=True)
    return ink,col

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--master',required=True);p.add_argument('--vegetation',required=True);p.add_argument('--output',type=Path,default=DEFAULT);p.add_argument('--cache');p.add_argument('--no-previews',action='store_true');a=p.parse_args();run(a.master,a.vegetation,a.output,a.cache,not a.no_previews)
