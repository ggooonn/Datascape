"""Bounded Spring integration adapters; accepted source/catalog bytes stay immutable."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter,distance_transform_edt
from shapely.geometry import LineString, Polygon
from shapely.ops import substring, unary_union
from datascape.strokes.vector import sample, resample
from datascape.integration.visibility import contact, signed_clearance, burn, clip_source
from datascape.integration.cluster_scene import intersects
from datascape.integration.macro_wash import (make_context, source_basis, geometric_feather,
    gate_v04, foliage_candidates, paired_supports, trunk_candidates, trim_profiles)
from datascape.integration.diverse_color import displaced_a, make_carrier, build_c_color, build_material_color
from datascape.integration.vector_wash import quantile
from datascape.rendering.spring_integration import geometry_mask
from datascape.vegetation.mid_far import Evidence
from datascape.vegetation.territorial_mid_far_v04 import (support_field, generate, visibility,
    vegetation_overlap, colorize, clip_profiled)
from datascape.vegetation.structural_mid_far_v02 import ink_from_graph

ROOT=Path(__file__).resolve().parents[3]


class FullPrecisionEvidence(Evidence):
    """Exact root triangles; crown depth remains the declared 2.5D carrier model."""
    def __init__(self, fixed, corridor):
        b=fixed['base'];self.fixed=fixed
        super().__init__(b['depth_m'],b['xyz'],b['current_ndvi'],b['current_observations'],
            b['occupied'],fixed['retention'],fixed['refined']['global_retention'],
            signed_clearance((fixed['retention']<=0)|(~b['occupied'])|burn(corridor)),
            dict(depth_provider='full-precision-F2',root_contact='exact mapped triangle'))
        self.protected_clearance[898:]=-100

    def point(self,xy):
        try:
            s=contact(self.fixed,xy);s.update(exact_contact=True,depth_provider='full-precision-F2-triangle')
            return s
        except ValueError as exc:
            # support_field requires a site object; rejected before graph construction.
            return dict(xy_mm=list(map(float,xy)),exact_contact=False,rejection=str(exc),source_forward_m=None)


def normalize_rsu(r):
    r=deepcopy(r);color='palette_slot' in r
    r.update(source_family='RSU',material_channel='color-support' if color else 'structural-ink',
        physical_plotting_validated=False,catalog_version='mid-far-v05-handoff',origin_kind='derived-RSU',depth_provider='full-precision-F2-root-with-2.5D-carrier')
    if color:
        if r['palette_slot']=='C5':r['palette_slot']='C4';r['palette_remap']='C5 experimental intent to active C4'
        r['source_forward_mean_m']=float(np.mean(r['source_forward_profile_m']))
    return r


def stable_overlap(ink,color,config):
    """Integration-only stable depth ties; accepted catalog implementation is untouched."""
    allrows=ink+color
    owners=sorted({r['owner_id'] for r in allrows},key=lambda own:(min(min(r['source_forward_profile_m']) for r in allrows if r['owner_id']==own),own))
    nearq=np.full((900,600),np.inf);out=[];ledger=[]
    for owner in owners:
        rows=sorted([r for r in allrows if r['owner_id']==owner],key=lambda r:r['id']);mask=np.isfinite(nearq)
        if mask.any():
            clearance=signed_clearance(mask);idx=distance_transform_edt(~mask,return_distances=False,return_indices=True);nearest_q=nearq[tuple(idx)]
        kept=[]
        for r in rows:
            if mask.any():
                def gate(xy,aa,rec):
                    arcs=np.r_[0,np.cumsum(np.linalg.norm(np.diff(rec['xy_mm'],axis=0),axis=1))]
                    qq=np.interp(aa,arcs,rec['source_forward_profile_m']);behind=qq>sample(nearest_q,xy,order=0)+25.
                    return np.where(behind,sample(clearance,xy,order=0)-rec['assumed_footprint_mm']/2-.25,1.),['nearer-dense-new-vegetation']
                parts,d=clip_profiled(r,gate,config);ledger.append(d)
            else:parts=[r]
            kept+=parts
        count=np.zeros((900,600),np.float32)
        for r in kept:
            if 'palette_slot' in r:count+=burn(LineString(r['xy_mm']).buffer(.6))
        core=gaussian_filter(count,.65)>=1.7;depth=max(max(r['source_forward_profile_m']) for r in rows)
        nearq[core]=np.minimum(nearq[core],depth);out+=kept
    out.sort(key=lambda r:(-r['source_forward_m'],r['owner_id'],r['id']))
    return [r for r in out if 'palette_slot' not in r],[r for r in out if 'palette_slot' in r],ledger


def build_forest(fixed,native,c,corridor):
    evidence=FullPrecisionEvidence(fixed,corridor)
    mc=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v04.json').read_text())
    v2=json.loads((ROOT/mc['v02_config']).read_text());mc={**v2,**mc}
    raw=[];sites=[];rejected=[];links=[];vl=[];all_ink=[];all_color=[]
    for spec in c['forest_passages']:
        cfg=deepcopy(mc);cfg['regions']={spec['id']:spec}
        ss,rr=support_field(spec['id'],'clustered',[],evidence,cfg)
        for s in ss:
            if not s['site']['exact_contact']:rr.append(dict(id=s['id'],reason=s['site']['rejection']))
        ss=[s for s in ss if s['site']['exact_contact']]
        if spec['mode'].startswith('M'):
            heroes=[s for s in ss if s['stand_role']=='dominant'][:2]
            for s in heroes:s['height_mm']*=1.48
        graphs,ink,col,ln=generate(ss,spec['mode'],spec['family'],cfg)
        if spec['mode'].startswith('M'):
            for s,g in zip(ss,graphs):
                if s.get('height_mm',0)>spec['base_height_mm']*1.25:
                    extra=ink_from_graph(s,g,cfg)
                    known={r['id'] for r in ink}
                    for r in extra:
                        if r['id'] in known:continue
                        r.update(source_forward_profile_m=[s['site']['source_forward_m']]*len(r['xy_mm']),pictorial_family=spec['family'],hierarchy_tier='primary',patch_id=s['patch_id'])
                        ink.append(r)
        raw+=ink+col
        ii,il=visibility(ink,evidence,cfg);cc,cl=visibility(col,evidence,cfg)
        ii,cc,ol=stable_overlap(ii,cc,cfg);cc=colorize(cc,cfg)
        # Foreground visible body occlusion only; terrain itself is never erased.
        kept=[]
        for r in ii+cc:
            def gate(xy,aa,rec):
                q=np.interp(aa,np.r_[0,np.cumsum(np.linalg.norm(np.diff(rec['xy_mm'],axis=0),axis=1))],rec['source_forward_profile_m'])
                good=np.ones(len(xy))*1e6
                for o in native['objects']:
                    if not intersects(LineString(rec['xy_mm']).bounds,o['bounds']):continue
                    behind=q>sample(o['q'],xy)+25
                    good=np.minimum(good,np.where(behind,sample(o['body_distance'],xy)-rec['assumed_footprint_mm']/2-1.15,1e6))
                return good,['foreground-body-depth','RSU-overlay-no-terrain-deletion']
            pp,d=clip_profiled(r,gate,cfg);kept+=pp;vl.append(d)
        all_ink +=[normalize_rsu(r) for r in kept if 'palette_slot' not in r]
        all_color +=[normalize_rsu(r) for r in kept if 'palette_slot' in r]
        sites+=ss;rejected +=[dict(passage=spec['id'],**r) for r in rr];links+=ln;vl+=il+cl+ol
        print('RSU',spec['id'],len(ss),'sites',flush=True)
    return dict(ink=all_ink,color=all_color,raw=raw,sites=sites,rejected=rejected,links=links,visibility=vl,terrain_deleted_mm=0.)


def slope_field(fixed,anchors,c):
    """Extend peak-related emphasis down associated source-space mountainsides."""
    ctl=c['slope_color_controls'];p=source_basis(fixed,np.nan_to_num(fixed['base']['xyz']));aa=source_basis(fixed,[a['source_xyz_m'] for a in anchors]);field=np.zeros(p.shape[:2])
    for a in aa:
        d=p-a;descent=-d[...,2];qscale=np.where(d[...,1]<0,ctl['forward_down_sigma_m'],ctl['forward_up_sigma_m'])
        weight=np.exp(-.5*((d[...,0]/ctl['lateral_sigma_m'])**2+(d[...,1]/qscale)**2))
        weight*=np.clip(1-descent/ctl['maximum_descent_m'],0,1)**.35
        weight*=((descent>=-ctl['maximum_ascent_m'])&(descent<=ctl['maximum_descent_m']))
        field=np.maximum(field,weight)
    rhythm=.58+.42*(.5+.5*np.sin(p[...,0]/73+p[...,2]/57)*np.cos(p[...,1]/133))
    return (field*rhythm*fixed['base']['occupied']).astype('float32')


def expanded_a(fixed,native,c,ctx):
    paths=[r for r in native['terrain'] if r['source_family']=='A'];cloud=[];labels=[]
    for r in paths:
        pp=resample(r['xy_mm'],2.);cloud.extend(pp);labels.extend([r['source_stroke_id']]*len(pp))
    tree=cKDTree(cloud);labels=np.asarray(labels,dtype=object);out=[];ctl=c['slope_color_controls']
    for src in paths:
        line=LineString(src['xy_mm']);n=max(1,int(np.ceil(line.length/ctl['episode_mm'])))
        for j in range(n):
            a,b=line.length*j/n,line.length*(j+1)/n;trim=(b-a)*(.035+.12*quantile(src['id']+f'/episode-{j}',c['seed']));a+=trim*.4;b-=trim*.6
            if b-a<3.2:continue
            part=substring(line,a,b);mid=part.interpolate(.5,normalized=True).coords[0];q=float(sample(fixed['base']['depth_m'],[mid])[0]);e=float(sample(ctx['slope_focus'],[mid])[0])
            background=float(np.interp(q,c['a_color_controls']['selection_depth_knots_m'],c['a_color_controls']['selection_near_middle_far']));prob=background+(ctl['focus_probability']-background)*e
            if quantile(src['id']+f'/A05-select-{j}',c['seed'])>prob:continue
            count=2 if e>ctl['second_pass_threshold'] and quantile(src['id']+f'/second-{j}',c['seed'])<ctl['second_pass_probability'] else 1
            for k in range(count):
                key=f'v05/A-color/{src["id"]}/episode-{j}/pass-{k}';p,controls=displaced_a(part.coords,key,c,(tree,labels,src['source_stroke_id']))
                pc=deepcopy(c)
                for slot in pc['object_palette_weights']['terrain']:
                    if slot in ['C1','C2','D1']:pc['object_palette_weights']['terrain'][slot]*=1+.5*e
                    elif slot=='A3':pc['object_palette_weights']['terrain'][slot]*=1-.35*e
                r=make_carrier(p,key,'terrain-A','terrain',sample(fixed['base']['depth_m'],p),pc,src['source_stroke_id']+f'/region-{j//2}/pass-{k}','A-derived',
                    [dict(source_id=src['source_stroke_id'],visible_fragment_id=src['id'],original_arc_mm=[src['source_arc_mm'][0]+a,src['source_arc_mm'][0]+b]),dict(role='source-space downward focus',selected_D_ids=c['d_color_controls']['selected_source_ids'])],k)
                if r:r.update(derivation_controls=controls,slope_focus=e,color_subchannel='slope-A',source_selection_probability=prob);out.append(r)
    return out


def retain_color(r,gate,sources,ledger,records):
    """Enforce color floor even when clip_source's fully-visible fast path applies."""
    if r is None:return
    sources.append(r);length=LineString(r['xy_mm']).length
    if length<3.2:
        ledger.append(dict(source_id=r['id'],source_length_mm=length,kept_intervals_mm=[],removed_mm=length,reason='color-minimum-3.2'));return
    pp,d=clip_source(r,gate,minimum_mm=3.2);ledger.append(d)
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
    for p in pp:
        a=p['source_arc_mm'][0];at=a+np.r_[0,np.cumsum(np.linalg.norm(np.diff(p['xy_mm'],axis=0),axis=1))]
        for field in ['source_forward_profile_m','pressure_intent_samples']:
            if field in r:p[field]=np.interp(at,arc,r[field]).tolist()
        p['source_forward_mean_m']=float(np.mean(p['source_forward_profile_m']));records.append(p)


def build_colors(fixed,native,forest,c,corridor):
    ctx=make_context(fixed,native,c,corridor);ctx['slope_focus']=slope_field(fixed,ctx['D_anchors'],c)
    raw=dict(A=expanded_a(fixed,native,c,ctx));print('A proposals',len(raw['A']),flush=True)
    _,cc,_=build_c_color(fixed,native,c,ctx)
    # Finite C episodes and occurrence near supported objects/groves, rather than opacity gain.
    supports=[s['site']['xy_mm'] for s in native['sites']]+[s['root_xy_mm'] for s in forest['sites']]
    tree=cKDTree(np.asarray(supports)/[42,26]);raw['C']=[]
    for r in cc:
        line=LineString(r['xy_mm']);n=max(1,int(np.ceil(line.length/34.)))
        for j in range(n):
            a,b=line.length*j/n,line.length*(j+1)/n
            if b-a<3.2:continue
            mid=np.asarray(line.interpolate((a+b)/2).coords[0]);d,_=tree.query(mid/[42,26]);local=.45+.55*np.exp(-.5*d*d)
            rate=c['c_color_controls']['source_episode_selection'] if r['owner_id']=='terrain-C' else local
            if quantile(r['id']+f'/C05-episode-{j}',c['seed'])>rate:continue
            p=trim_profiles(r,a,b,r['id']+f'/v05-episode-{j}');p['support_selection_probability']=float(rate);raw['C'].append(p)
    print('C proposals',len(raw['C']),flush=True)
    _,old,_=build_material_color(fixed,native,c,ctx,corridor,True)
    raw['rock_soil']=[r for r in old if r['color_kind']!='vegetation'];raw['gestures']=[];raw['trunk']=[];regions={}
    for o in native['objects']:
        if o['kind']!='tree':continue
        raw['gestures'].extend(foliage_candidates(fixed,o,native['visible_by_owner'][o['id']],c))
        for r,reg in trunk_candidates(fixed,o,c,paired_supports(o)):regions[r['structural_region_id']]=reg;raw['trunk'].append(r)
    final={};sources={};vis={};feather={};objects={o['id']:o for o in native['objects']}
    for channel,rr in raw.items():
        final[channel]=[];sources[channel]=[];vis[channel]=[];feather[channel]=[]
        for r in rr:
            o=objects.get(r['owner_id']);region=None;exact=False
            if channel=='gestures':
                region=geometry_mask((o['regions']['occupancy']>.012)&o['visible']).buffer(1.5)
                region=region.union(unary_union([LineString(p).buffer(2.4) for k,p in o['tree'].structure['members'].items() if k.startswith('arm-')]))
            elif channel=='rock_soil':region=o['support'].buffer(5.5*(o.get('color_expansion',1.4)-1) if o['kind']=='soil' else 0)
            elif channel=='trunk':region=regions[r['structural_region_id']];exact=True
            if region is not None:region=region.difference(corridor)
            peers=[obj for obj in native['objects'] if intersects(LineString(r['xy_mm']).bounds,obj['bounds'])]
            source,decision=geometric_feather(r,fixed,c,o);feather[channel].append(decision)
            retain_color(source,gate_v04(fixed,ctx,peers,c,o,region,exact_region=exact),sources[channel],vis[channel],final[channel])
        print('Visible color',channel,len(final[channel]),flush=True)
    final['RSU']=forest['color'];expanded=sum((final[k] for k in ['A','C','rock_soil','gestures','trunk','RSU']),[])
    restrained=[r for r in expanded if quantile(r['id']+'/restrained',c['seed'])<(.42 if r['owner_id'] in ['terrain-A','terrain-C','terrain-C-field'] else .55)]
    return dict(channels=final,expanded=expanded,restrained=restrained,raw=raw,sources=sources,visibility=vis,feather=feather,anchors=ctx['D_anchors'],regions=regions,context=ctx)
