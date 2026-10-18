"""Reversible v04 source-space D emphasis, geometric mist and growth wash.

Canonical sources are immutable. Width/pressure intent is uncalibrated metadata;
preview envelopes are stroke footprints, never filled terrain/canopy regions.
"""
from collections import defaultdict
from copy import deepcopy
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import substring,unary_union
from shapely import contains_xy,points as shape_points,distance as shape_distance
from datascape.integration.visibility import contact,burn,signed_clearance,clip_source
from datascape.integration.cluster_scene import intersects,terrain_gate_v02
from datascape.integration.diverse_scene import object_gate_v03
from datascape.integration.diverse_color import color_context,displaced_a,make_carrier,build_c_color,build_material_color,local_frame
from datascape.integration.vector_wash import quantile
from datascape.strokes.vector import sample,resample
from datascape.rendering.spring_integration import geometry_mask


def smoothstep(v):
    v=np.clip(v,0,1);return v*v*(3-2*v)


def source_basis(fixed,xyz):
    xyz=np.asarray(xyz);eye=np.asarray(fixed['scene']['primary_eye_xy_m'],dtype=float);f=np.asarray(fixed['scene']['look_target_xy_m'],dtype=float)-eye;f/=np.linalg.norm(f);l=np.array([-f[1],f[0]]);d=xyz[...,:2]-eye
    return np.stack([d@l,d@f,xyz[...,2]],axis=-1)


def d_emphasis(fixed,terrain,c):
    ctl=c['d_color_controls'];occupied=fixed['base']['occupied'];dist,nearest=distance_transform_edt(~occupied,return_indices=True);anchors=[];rejected=[]
    for r in terrain:
        if r['source_family']!='D' or r['source_stroke_id'] not in ctl['selected_source_ids']:continue
        for p in resample(r['xy_mm'],2.):
            ix,iy=int(np.clip(p[0],0,599)),int(np.clip(p[1],0,899));q=p.copy()
            if not occupied[iy,ix]:q=np.array([nearest[1,iy,ix]+.5,nearest[0,iy,ix]+.5])
            if np.linalg.norm(q-p)>ctl['maximum_attachment_distance_mm']:
                rejected.append(dict(source_id=r['source_stroke_id'],xy_mm=p.tolist()));continue
            try:s=contact(fixed,q)
            except ValueError:
                q=np.array([nearest[1,iy,ix]+.5,nearest[0,iy,ix]+.5])
                try:s=contact(fixed,q)
                except ValueError:continue
            anchors.append(dict(source_id=r['source_stroke_id'],source_event=r.get('source_event'),ink_xy_mm=p.tolist(),attached_xy_mm=q.tolist(),source_xyz_m=s['source_xyz_utm_m'],source_forward_m=s['source_forward_m'],attachment_distance_mm=float(np.linalg.norm(q-p)),mapped_face_id=s['mapped_face_id']))
    assert anchors
    sigma=np.asarray(ctl['source_world_sigma_m']);tree=cKDTree(source_basis(fixed,[a['source_xyz_m'] for a in anchors])/sigma)
    query=source_basis(fixed,np.nan_to_num(fixed['base']['xyz']))/sigma;d,_=tree.query(query.reshape(-1,3));field=np.exp(-.5*d.reshape(900,600)**2)*occupied*(fixed['base']['depth_m']>=ctl['far_source_q_m'])
    return field.astype('float32'),anchors,rejected


def make_context(fixed,result,c,corridor):
    ctx=color_context(fixed,result,corridor);b=fixed['base'];eligible=b['occupied']&(fixed['retention']>c['mist_color_controls']['eligible_retention_floor'])&(fixed['refined']['global_retention']>0)&~burn(corridor);eligible[898:]=False
    for o in result['objects']:
        eligible &= ~((b['depth_m']>=o['q']-25)&o['regions']['body']);eligible &= ~((b['depth_m']>o['q']+25)&(o['regions']['soft']>.68))
    ctx['eligible']=eligible;ctx['eligible_clearance']=signed_clearance(~eligible).astype('float32')
    contacts=[LineString(r['xy_mm']).buffer(.48) for o in result['objects'] if o['kind']=='soil' and o['role']=='exposed-root-repair' for r in result['visible_by_owner'][o['id']]]
    ctx['contact_clearance']=signed_clearance(burn(unary_union(contacts))).astype('float32');ctx['D_emphasis'],ctx['D_anchors'],ctx['D_rejected']=d_emphasis(fixed,result['terrain'],c)
    return ctx


def gate_v04(fixed,ctx,peers,c,obj=None,region=None,hard_only=False,exact_region=False):
    underlying=object_gate_v03(fixed,obj,peers) if obj else terrain_gate_v02(fixed,peers)
    rd=signed_clearance(~burn(region)).astype('float32') if region is not None and not exact_region else None
    def gate(xy,arc,r):
        g,reasons=underlying(xy,arc,r);w=max(r['width_profile_mm']);margin=w/2+1.1
        g=np.minimum.reduce([g,sample(ctx['global_clearance'],xy)-margin,sample(ctx['corridor_clearance'],xy)-margin,xy[:,0]-w/2,600-w/2-xy[:,0],898-w/2-xy[:,1]])
        if obj is None:
            g=np.minimum(g,sample(ctx['eligible_clearance'],xy)-margin);g=np.minimum(g,sample(ctx['contact_clearance'],xy)-w/2-.2)
            if not hard_only:
                lo,hi=c['mist_color_controls']['coherent_threshold_range'];cohort=quantile(r['carrier_basis']+'/mist-contour',c['seed']);q=sample(fixed['base']['depth_m'],xy);coherence=.7+.3*(.5+.5*np.sin(q/183+xy[:,0]/71))
                g=np.minimum(g,sample(fixed['retention'],xy)-(lo+(hi-lo)*cohort*coherence))
        if rd is not None:g=np.minimum(g,sample(rd,xy)-w/2-.1)
        if region is not None and exact_region:
            inset=region.buffer(-w/2-.10)
            if inset.is_empty:g=np.minimum(g,-1.)
            else:
                inside=contains_xy(inset,xy[:,0],xy[:,1]);v=shape_distance(shape_points(xy),inset.boundary);g=np.minimum(g,np.where(inside,v,-v)-1e-7)
        return g,reasons+['v04-footprint-reserve','protected-root-contact','hard-only-control' if hard_only else 'geometric-color-mist']
    return gate


def trim_profiles(r,a,b,key):
    s=deepcopy(r);p=np.asarray(substring(LineString(r['xy_mm']),a,b).coords);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))];at=np.r_[a,a+np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    for field in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
        if field in r:s[field]=np.interp(at,arc,r[field]).tolist()
    s.update(id=key,source_stroke_id=key,source_arc_mm=[0.,float(b-a)],xy_mm=p.tolist(),source_forward_mean_m=float(np.mean(s['source_forward_profile_m'])))
    return s


def geometric_feather(r,fixed,c,obj=None):
    line=LineString(r['xy_mm']);ctl=c['mist_color_controls'];p=resample(r['xy_mm'],1.);ret=sample(obj['retention'] if obj else fixed['retention'],p);lo,hi=ctl['feather_retention_range'];strength=float(np.mean(smoothstep((ret-lo)/(hi-lo))))
    probability=ctl['minimum_selection_probability']+(1-ctl['minimum_selection_probability'])*strength;fraction=ctl['minimum_shortened_fraction']+(1-ctl['minimum_shortened_fraction'])*strength**.7
    trim=line.length*(1-fraction)*ctl['shortening_gain'];bias=.22+.56*quantile(r['carrier_basis']+'/release-bias',c['seed']);a=trim*bias;b=line.length-trim*(1-bias)
    keep=quantile(r['id']+'/feather-presence',c['seed'])<probability and b-a>=ctl['minimum_path_mm']
    decision=dict(source_id=r['id'],source_length_mm=line.length,kept_intervals_mm=[[a,b]] if keep else [],removed_mm=line.length-(b-a) if keep else line.length,mean_retention=float(np.mean(ret)),feather_strength=strength,selection_probability=probability,reason='unequal-endpoint-retreat' if keep else 'whole-carrier-dissolution')
    if not keep:return None,decision
    s=trim_profiles(r,a,b,r['id']+'/feathered');s.update(feather_parent_source_id=r['id'],feather_parent_arc_mm=[a,b],feather_strength=strength);return s,decision


def retain(r,gate,sources,ledger,records):
    if r is None:return
    sources.append(r);parts,decision=clip_source(r,gate);ledger.append(decision);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
    for p in parts:
        a,b=p['source_arc_mm'];xy=np.asarray(p['xy_mm']);at=np.r_[a,a+np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        for field in ['source_forward_profile_m','pressure_intent_samples']:
            if field in r:p[field]=np.interp(at,arc,r[field]).tolist()
        p['source_forward_mean_m']=float(np.mean(p['source_forward_profile_m']));records.append(p)


def a_candidates(fixed,result,c,ctx):
    paths=[r for r in result['terrain'] if r['source_family']=='A'];cloud=[];labels=[]
    for r in paths:
        p=resample(r['xy_mm'],2.);cloud.extend(p);labels.extend([r['source_stroke_id']]*len(p))
    tree=cKDTree(cloud);labels=np.asarray(labels,dtype=object);ctl=c['d_color_controls'];out=[]
    for source in paths:
        line=LineString(source['xy_mm']);count=max(1,int(np.ceil(line.length/44)))
        for j in range(count):
            a,b=line.length*j/count,line.length*(j+1)/count;trim=(b-a)*(.035+.12*quantile(source['id']+f'/episode-{j}',c['seed']));a+=trim*.4;b-=trim*.6
            if b-a<3.2:continue
            part=substring(line,a,b);mid=np.asarray(part.interpolate(.5,normalized=True).coords[0]);q=float(sample(fixed['base']['depth_m'],[mid])[0]);e=float(sample(ctx['D_emphasis'],[mid])[0]);prob=float(np.interp(q,c['a_color_controls']['selection_depth_knots_m'],c['a_color_controls']['selection_near_middle_far']))
            if q>=ctl['far_source_q_m']:prob=ctl['background_A_probability']+(ctl['emphasized_A_probability']-ctl['background_A_probability'])*e
            if quantile(source['id']+f'/A04-select-{j}',c['seed'])>prob:continue
            passes=2 if e>ctl['second_pass_emphasis_min'] and quantile(source['id']+f'/second-{j}',c['seed'])<ctl['second_pass_probability'] else 1
            for k in range(passes):
                key=f'v04/A-color/{source["id"]}/episode-{j}/pass-{k}';p,controls=displaced_a(part.coords,key,c,(tree,labels,source['source_stroke_id']));pc=c
                if e>.3:
                    pc=deepcopy(c)
                    for slot in pc['object_palette_weights']['terrain']:pc['object_palette_weights']['terrain'][slot]*=1+(ctl['D_peak_warm_green_gain']-1)*e if slot in ['C1','C2','D1'] else 1-.35*e if slot=='A3' else 1.
                r=make_carrier(p,key,'terrain-A','terrain',sample(fixed['base']['depth_m'],p),pc,source['source_stroke_id']+f'/region-{j//2}/pass-{k}','A-derived',[dict(source_id=source['source_stroke_id'],visible_fragment_id=source['id'],original_arc_mm=[source['source_arc_mm'][0]+a,source['source_arc_mm'][0]+b]),dict(source_ids=ctl['selected_source_ids'],role='source-space D emphasis',world_sigma_m=ctl['source_world_sigma_m'])],k)
                if r:r.update(derivation_controls=controls,D_emphasis=e,source_selection_probability=prob,color_subchannel='D-related-A' if e>.3 else 'background-A');out.append(r)
    return out


def expressive_profile(r,peak,phase):
    p=np.asarray(r['xy_mm']);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];u=arc/max(arc[-1],1e-9);center=.31+.20*phase
    shape=(.14+.86*np.minimum(np.clip(u/center,0,1)**.72,np.clip((1-u)/(1-center),0,1)**.92))*(1+.08*np.sin(u*6+phase*4));widths=peak*shape
    r.update(width_mm=float(np.mean(widths)),width_profile_mm=widths.tolist(),assumed_footprint_mm=float(widths.max()),pressure_intent_samples=(widths/max(widths.max(),1e-9)).tolist(),expressive_width_intent=True,width_intent='uncalibrated widening/release; preview envelope only',brush_pressure_calibrated=False);return r


def foliage_candidates(fixed,obj,visible,c):
    units=defaultdict(list);tree=obj['tree'];meta={u['key']:u for u in tree.canopy_diagnostics['units']};lobes={l['key']:l for l in tree.lobes};ctl=c['brush_controls']
    for r in visible:
        if r['grammar_part']=='foliage-field':units[r['component_key'].rsplit('-',1)[0]].append(r)
    for key,rays in sorted(units.items()):
        info=meta.get(key,{});state=info.get('state','light');prob={'dense':ctl['dense_unit_probability'],'light':ctl['light_unit_probability'],'open':ctl['open_unit_probability'],'remnant':.18}.get(state,.47)
        if quantile(obj['id']+'/'+key+'/gesture-keep',c['seed'])>prob:continue
        rays=sorted(rays,key=lambda r:r['id']);pad=info.get('pad',info.get('owner_pad',key.split('/')[0]));lobe=lobes.get(pad);branch_key=lobe.get('source_branch') if lobe else None
        branch=np.asarray(tree.structure['members'].get(branch_key,[tree.root,tree.root+np.array([0,-obj['height_mm']*.6]) ]));bline=LineString(branch);chosen=[rays[0]]
        if len(rays)>1 and obj['height_mm']>=45:chosen.append(rays[-1])
        if len(rays)>2 and state=='dense' and obj['height_mm']>=95 and quantile(key+'/extra-gesture',c['seed'])<ctl['large_double_gesture_probability']:chosen.append(rays[len(rays)//2])
        for i,s in enumerate(chosen):
            p=np.asarray(s['xy_mm']);pivot=p[0];ray=p[-1]-pivot;ray/=max(np.linalg.norm(ray),1e-9);near=np.asarray(bline.interpolate(bline.project(Point(pivot))).coords[0]);radial=pivot-near;span=np.linalg.norm(radial)
            if span<.2:radial=ray.copy();span=1.
            radial/=span;reach=min(span*.65,ctl['maximum_branch_reach_mm']*np.clip(obj['height_mm']/95,.35,1.));start=pivot-radial*reach;phase=quantile(obj['id']+'/'+key+f'/gesture-{i}',c['seed']);end=pivot+ray*min(6.4,max(3.,LineString(p).length*.95));direction=end-start;length=np.linalg.norm(direction)
            if length>ctl['foliage_gesture_length_mm'][1]:start=end-direction/length*ctl['foliage_gesture_length_mm'][1]
            if np.linalg.norm(end-start)<3.2:continue
            tangent=branch[-1]-branch[max(0,len(branch)-5)];tangent/=max(np.linalg.norm(tangent),1e-9)
            if np.dot(tangent,end-start)<0:tangent=-tangent
            control=start+(end-start)*(.42+.12*phase)+tangent*(.65+1.1*phase);u=np.linspace(0,1,13);xy=(1-u)[:,None]**2*start+2*((1-u)*u)[:,None]*control+u[:,None]**2*end
            r=make_carrier(xy,f'v04/foliage/{obj["id"]}/{key}/gesture-{i}',obj['id'],'vegetation',sample(obj['q'],xy),c,f'{obj["group"]}/{pad}/growth-zone-{i}','material-C-like',[dict(source_id=s['id'],role='visible leaf-unit origin',catalog_component=s['component_key']),dict(source_id=obj['id']+'/'+str(branch_key),role='actual branch curve',branch_points_mm=branch.tolist())],i)
            if r:
                peak=float(np.interp(obj['height_mm'],[20,45,95,130],[.7,1.25,2.25,ctl['foliage_peak_width_mm'][1]]))*(.84+.25*phase);expressive_profile(r,peak,phase);r.update(color_subchannel='foliage-gesture',group_id=obj['group'],catalog_object_id=obj['id'],branch_origin_xy_mm=near.tolist(),growth_state=state);yield r


def paired_supports(obj):
    """Use actual posed paired contour vertices, not regenerated axis buffers."""
    groups=defaultdict(lambda:defaultdict(list));m=obj['tree'].structure['members'];axis=np.vstack([np.asarray(p) if i==0 else np.asarray(p)[1:] for i,(k,p) in enumerate((x for x in m.items() if x[0].startswith('axis/')))])
    paths={**{k:np.asarray(p) for k,p in m.items() if k.startswith('arm-')},'axis':axis}
    for r in obj['records']:
        key=r.get('component_key','');member=key.split('/')[0];side=-1 if '/side-1/' in key else 1 if '/side1/' in key else None
        if side is not None and member in paths and r['grammar_part'] in ['trunk-contour','branch-contour']:groups[member][side].append(np.asarray(r['xy_mm']))
    supports={}
    for member,sides in groups.items():
        if not sides[-1] or not sides[1]:continue
        center=LineString(paths[member]);edges=[np.vstack(sorted(sides[side],key=lambda p:center.project(Point(p[0])))) for side in [-1,1]];poly=Polygon(np.vstack([edges[0],edges[1][::-1]])).buffer(0)
        if not poly.is_empty:supports[member]=(poly,paths[member])
    return supports


def trunk_candidates(fixed,obj,c,supports):
    if obj['height_mm']<c['brush_controls']['trunk_minimum_height_mm'] or obj['representation']=='aggregate':return
    for member,(region,center) in supports.items():
        if member!='axis' and obj['height_mm']<95:continue
        p=resample(center,.55);t,n=local_frame(p);axis=member=='axis';offsets=[-.42,.34]+([.92] if obj['height_mm']>=120 else []) if axis else [0.]
        for j,offset in enumerate(offsets):
            line=LineString(p+n*offset);a=line.length*(.05+.17*j if axis else .12);b=line.length*(.88-.12*j if axis else .72)
            if b-a<4:continue
            xy=np.asarray(substring(line,a,b).coords);key=f'v04/trunk/{obj["id"]}/{member}/longitudinal-{j}'
            r=make_carrier(xy,key,obj['id'],'trunk',sample(obj['q'],xy),c,f'{obj["group"]}/{member}/warm-grain-{j}','material-C-like',[dict(source_id=obj['id']+'/'+member,role='longitudinal member',member_points_mm=np.asarray(center).tolist()),dict(source_ids=[s['id'] for s in obj['records'] if s.get('component_key','').startswith(member+'/side')],role='actual paired ink boundaries')])
            if r:
                peak=c['brush_controls']['trunk_peak_width_mm']*(.8 if j else 1.) if axis else c['brush_controls']['branch_peak_width_mm'];expressive_profile(r,peak,quantile(key,c['seed']));r.update(color_subchannel='trunk-longitudinal',group_id=obj['group'],catalog_object_id=obj['id'],structural_region_id=obj['id']+'/'+member);yield r,region


def build_v04_wash(fixed,result,c,corridor):
    ctx=make_context(fixed,result,c,corridor);raw={};final={};sources={};visibility={};feather={};hard=[];regions={};objects={o['id']:o for o in result['objects']}
    print('Generate selective A and bounded C',flush=True);raw['A']=a_candidates(fixed,result,c,ctx);_,raw['C'],_=build_c_color(fixed,result,c,ctx)
    print('Generate thin-method control and material carriers',flush=True);_,old,_=build_material_color(fixed,result,c,ctx,corridor,True);raw['thin']=[r for r in old if r['color_kind']=='vegetation'];raw['rock_soil']=[r for r in old if r['color_kind']!='vegetation'];raw['gestures']=[];raw['trunk']=[]
    for obj in sorted(result['objects'],key=lambda o:o['id']):
        if obj['kind']!='tree':continue
        raw['gestures'].extend(foliage_candidates(fixed,obj,result['visible_by_owner'][obj['id']],c))
        for r,region in trunk_candidates(fixed,obj,c,paired_supports(obj)):regions[r['structural_region_id']]=region;raw['trunk'].append(r)
    print('Feather and clip actual color geometry',flush=True)
    for channel,candidates in raw.items():
        final[channel]=[];sources[channel]=[];visibility[channel]=[];feather[channel]=[]
        for original in candidates:
            r=deepcopy(original)
            if not r['id'].startswith('v04/'):r.update(id='v04/'+r['id'],source_stroke_id='v04/'+r['id'])
            original.update(id=r['id'],source_stroke_id=r['source_stroke_id']);obj=objects.get(r['owner_id']);p=np.asarray(r['xy_mm']);e=float(sample(ctx['D_emphasis'],[p[len(p)//2]])[0]);r['D_emphasis']=r.get('D_emphasis',e)
            if channel=='C' and r['source_forward_mean_m']>=c['d_color_controls']['far_source_q_m']:
                keep=c['d_color_controls']['far_C_background_keep']+(c['d_color_controls']['far_C_emphasized_keep']-c['d_color_controls']['far_C_background_keep'])*e
                if quantile(r['id']+'/far-C-restraint',c['seed'])>keep:
                    length=LineString(r['xy_mm']).length;feather[channel].append(dict(source_id=r['id'],source_length_mm=length,kept_intervals_mm=[],removed_mm=length,reason='selective-far-C-restraint'));continue
            region=None;exact=False
            if channel in ['thin','gestures']:
                region=geometry_mask((obj['regions']['occupancy']>.012)&obj['visible']).buffer(1.5)
                if channel=='gestures':region=region.union(unary_union([LineString(p).buffer(2.4) for k,p in obj['tree'].structure['members'].items() if k.startswith('arm-')]))
            elif channel=='rock_soil':region=obj['support'].buffer(5.5*(obj.get('color_expansion',1.4)-1) if obj['kind']=='soil' else 0)
            elif channel=='trunk':region=regions[r['structural_region_id']];exact=True
            peers=[o for o in result['objects'] if intersects(LineString(r['xy_mm']).bounds,o['bounds'])]
            if region is not None:region=region.difference(corridor)
            if channel in ['A','C']:retain(r,gate_v04(fixed,ctx,peers,c,hard_only=True),[],[],hard)
            source,decision=geometric_feather(r,fixed,c,obj);feather[channel].append(decision);retain(source,gate_v04(fixed,ctx,peers,c,obj,region,exact_region=exact),sources[channel],visibility[channel],final[channel])
    final['terrain']=final['A']+final['C'];final['caseB']=final['terrain']+final['rock_soil']+final['thin'];final['caseC']=final['terrain']+final['rock_soil']+final['gestures']+final['trunk'];final['hard_only_terrain']=hard
    return final,raw,sources,visibility,feather,ctx,regions
