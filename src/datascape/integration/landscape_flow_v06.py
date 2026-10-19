"""Landscape-scale placement supports and color adapters on immutable F2 fields.

Spines are nonplotting composition hints, not traced silhouettes or terrain edits.
Accepted catalogs remain unchanged. New S spans are integration-level continuity
supports between measured roots, not approval of a new general forest grammar.
"""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial import cKDTree
from shapely.geometry import LineString,Polygon
from shapely.ops import substring,unary_union
from datascape.strokes.vector import sample,resample,phase
from datascape.integration.visibility import contact,digest
from datascape.integration.cluster_scene import intersects
from datascape.integration.spring_unified_v05 import (FullPrecisionEvidence,normalize_rsu,
    slope_field,expanded_a,retain_color)
from datascape.integration.macro_wash import (make_context,geometric_feather,gate_v04,
    foliage_candidates,paired_supports,trunk_candidates,trim_profiles)
from datascape.integration.diverse_color import build_c_color,build_material_color
from datascape.integration.vector_wash import quantile
from datascape.rendering.spring_integration import geometry_mask
from datascape.vegetation.pictorial_families_v03 import supported_root,measured_tangent
from datascape.vegetation.territorial_mid_far_v04 import generate,colorize,make_record,clip_profiled
from datascape.vegetation.structural_mid_far_v02 import ink_from_graph
from datascape.vegetation.mid_far import root_visibility

ROOT=Path(__file__).resolve().parents[3]


def attach_hint(fixed,xy,maximum):
    """Snap a nonplotting hint only; final roots always need exact triangles."""
    candidates=[]
    for dy in np.arange(-maximum,maximum+.1,1.):
        for dx in np.arange(-maximum,maximum+.1,1.):
            if dx*dx+dy*dy<=maximum*maximum:candidates.append((dx*dx+dy*dy,xy[0]+dx,xy[1]+dy))
    for distance,x,y in sorted(candidates):
        try:return contact(fixed,[x,y]),float(np.sqrt(distance))
        except ValueError:continue
    raise ValueError(f'No exact F2 contact near hint {xy}')


def prepare_zones(fixed,c):
    zones=[];field=np.zeros((900,600),np.float32);yy,xx=np.mgrid[:900,:600];xx=xx+.5;yy=yy+.5;q=fixed['base']['depth_m']
    for spec in c['zones']:
        anchors=[]
        for xy in spec['spine_mm']:
            s,d=attach_hint(fixed,xy,c['zone_policy']['maximum_anchor_snap_mm']);anchors.append(dict(hint_xy_mm=xy,site=s,snap_mm=d))
        x=np.array([a['site']['xy_mm'][0] for a in anchors]);y=np.array([a['site']['xy_mm'][1] for a in anchors]);qq=np.array([a['site']['source_forward_m'] for a in anchors])
        if not np.all(np.diff(x)>0):raise ValueError('Zone spine must be x-monotonic')
        yf=PchipInterpolator(x,y);qf=PchipInterpolator(x,qq);at=np.clip(xx,x[0],x[-1]);u=(at-x[0])/(x[-1]-x[0]);edge=np.exp(-.5*((xx-at)/14.)**2)
        rhythm=.48+.52*(.5+.5*np.cos(u*np.pi*3.4+phase(spec['id'],c['seed'])*5))
        weight=np.exp(-.5*((q-qf(at))/spec['width_q_m'])**2)*edge*rhythm
        weight*=fixed['base']['occupied']&(np.abs(yy-yf(at))<65)
        field=np.maximum(field,weight.astype('float32'))
        zones.append(dict(spec=spec,anchors=anchors,x=x,y=y,q=qq,yf=yf,qf=qf,field=weight.astype('float32')))
    return zones,field


def zone_sites(zone,evidence,c):
    spec=zone['spec'];x0,x1=zone['x'][[0,-1]];sites=[];rejected=[]
    for layer,family in enumerate(spec['families']):
        spacing=spec['spacing_mm']*(1.6 if family in ['R','U'] else 1.)
        xs=np.arange(x0+spacing*.45+layer*spacing*.29,x1-spacing*.15,spacing)
        for j,x in enumerate(xs):
            u=float((x-x0)/(x1-x0));rhythm=.58+.42*(.5+.5*np.cos(u*np.pi*3.4+phase(spec['id'],c['seed'])*5))
            # Continuous S floors retain longitudinal occupation; fringe accents
            # thin independently instead of breaking the whole zone into islands.
            if family!='S' and phase(f'{spec["id"]}/{layer}/{j}/fringe',c['seed'])>rhythm:continue
            baseq=float(zone['qf'](x));shift=(layer-(len(spec['families'])-1)/2)*spec['width_q_m']*.62
            q=baseq+shift+spec['width_q_m']*.17*np.sin(u*19+layer*1.4);yh=float(zone['yf'](x))
            radius=c['zone_policy']['source_root_search_radius_mm'];window=[max(1,yh-radius),min(897,yh+radius)]
            ident=f'v06/{spec["id"]}/stratum-{layer}/body-{j}'
            try:
                p=supported_root(evidence,x,q,yh,window);site=evidence.point(p)
                if not site['exact_contact']:raise ValueError(site['rejection'])
                if sample(evidence.protected_clearance,[p],order=0)[0]<3:raise ValueError('locked-reserve-footprint')
            except ValueError as exc:rejected.append(dict(id=ident,x_mm=float(x),requested_q_m=float(q),reason=str(exc)));continue
            scale=(.72+.52*rhythm)*(.88+.22*phase(ident+'/height',c['seed']))
            role='dominant' if rhythm>.78 else 'subordinate';height=spec['height_mm']*scale
            mode='M2' if site['source_forward_m']<1700 else 'F1' if site['source_forward_m']<2700 else 'F2'
            sites.append(dict(id=ident,stand_id=f'v06/{spec["id"]}/stratum-{layer}',patch_id=f'v06/{spec["id"]}/stratum-{layer}',zone_id=spec['id'],
                stand_index=layer,stand_role=role,member_index=j,member_count=len(xs),root_xy_mm=p.tolist(),height_mm=height,
                form=['P','B','U'][j%3],site=site,guide_u=u,guide_source_id='v06/nonplotting/'+spec['id'],
                tangent_xy=measured_tangent(evidence,p,[1.,0.]),family=family,mode=mode,source_q_offset_m=float(q-baseq)))
    return sites,rejected


def continuity_spans(sites,graphs,cfg,c):
    """Long S-based supports within connected runs, with explicit source-q profiles."""
    rows=[];links=[];lookup={g['body_id']:g for g in graphs}
    for group in sorted({s['stand_id'] for s in sites if s['family']=='S'}):
        ss=sorted([s for s in sites if s['stand_id']==group],key=lambda s:s['root_xy_mm'][0]);runs=[];current=[]
        for s in ss:
            if current:
                p=np.array(s['root_xy_mm']);last=np.array(current[-1]['root_xy_mm'])
                if np.linalg.norm(p-last)>c['zone_policy']['max_supported_gap_mm'] or abs(s['site']['source_forward_m']-current[-1]['site']['source_forward_m'])>280:
                    runs.append(current);current=[]
            current.append(s)
        if current:runs.append(current)
        for ri,run in enumerate(runs):
            if len(run)<3:continue
            x=np.array([s['root_xy_mm'][0] for s in run]);y=np.array([s['root_xy_mm'][1]-s['height_mm']*.64 for s in run]);q=np.array([s['site']['source_forward_m'] for s in run]);yf=PchipInterpolator(x,y);qf=PchipInterpolator(x,q)
            step=c['zone_policy']['continuous_span_mm']-c['zone_policy']['span_overlap_mm']
            for j,start in enumerate(np.arange(x[0],x[-1]-6,step)):
                end=min(x[-1],start+c['zone_policy']['continuous_span_mm']);members=[s for s in run if start-8<=s['root_xy_mm'][0]<=end+8];site=members[len(members)//2];g=lookup[site['id']]
                ident=group+f'/S-zone-support/run-{ri}/span-{j}'
                for k,offset in enumerate([0.]):
                    a=start+(end-start)*(.08 if k==1 else .02);b=end-(end-start)*(.13 if k==2 else .01);xx=np.linspace(a,b,max(12,int((b-a)/.5)));u=(xx-a)/(b-a)
                    xy=np.c_[xx,yf(xx)+offset+.65*np.sin(u*np.pi*1.5+ri*.7+k*.4)]
                    r=make_record(ident+f'/layer-{k}',xy,site,g,None,'color','S','long',cfg,
                        source_member_ids=[s['id'] for s in members],carrier_id=ident,zone_id=site['zone_id'],
                        local_role='body',color_channel='material-C-like',
                        generation_rule='scene continuity support from measured roots; existing S surface tendency, not a new catalog baseline')
                    r['source_forward_profile_m']=qf(xx).tolist();r['source_forward_m']=float(np.mean(qf(xx)))
                    peak=float(np.interp(r['source_forward_m'],[500,1600,3300],[2.3,1.8,1.05]))*(.86+.24*phase(ident,c['seed']))
                    widths=peak*(.12+.88*np.sin(np.pi*u)**.65)
                    r.update(width_mm=float(widths.mean()),width_profile_mm=widths.tolist(),assumed_footprint_mm=float(widths.max()),expressive_width_intent=True,brush_pressure_calibrated=False,width_intent='integration wash-support stroke; uncalibrated profile, not region fill')
                    rows.append(r)
                links.append(dict(id=ident,member_ids=[s['id'] for s in members],x_range_mm=[float(start),float(end)],nonplotting=True))
    return rows,links


def visible_flow(rows,evidence,native,cfg,c):
    kept=[];ledger=[];sources=[]
    for original in rows:
        r=deepcopy(original);length=LineString(r['xy_mm']).length;arcs=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
        ret,_=root_visibility(evidence,dict(source_forward_m=np.array(r['source_forward_profile_m'])),np.array(r['xy_mm']));strength=float(np.clip((np.mean(ret)-.025)/.55,0,1))
        if 'palette_slot' in r:
            # Retreat endpoints progressively; do not use one hard zone boundary.
            fraction=.45+.55*strength**.75;trim=length*(1-fraction)*.65;bias=.25+.5*phase(r['id']+'/retreat',c['seed']);a=trim*bias;b=length-trim*(1-bias)
            if b-a<3.2:continue
            sources.append(original);r=trim_profiles(r,a,b,r['id']+'/mist-release');r.update(parent_source_id=original['id'],parent_source_arc_mm=[a,b])
        sources.append(r);bounds=LineString(r['xy_mm']).bounds;peers=[o for o in native['objects'] if intersects(bounds,o['bounds'])]
        def gate(xy,aa,rec):
            ar=np.r_[0,np.cumsum(np.linalg.norm(np.diff(rec['xy_mm'],axis=0),axis=1))];q=np.interp(aa,ar,rec['source_forward_profile_m']);ret,vis=root_visibility(evidence,dict(source_forward_m=q),xy)
            margin=rec['assumed_footprint_mm']/2+1.4;safe=sample(evidence.protected_clearance,xy,order=0)-margin
            out=np.minimum.reduce([safe,ret-.025,np.where(vis,1.,-1.),xy[:,0]-margin,600-margin-xy[:,0],898-margin-xy[:,1]])
            for o in peers:
                behind=q>sample(o['q'],xy)+25;out=np.minimum(out,np.where(behind,sample(o['body_distance'],xy)-margin,1e6))
            return out,['unchanged-F2-reserve','source-q-mist-geometry','foreground-body-depth','midfar-overlay-no-terrain-deletion']
        pp,d=clip_profiled(r,gate,cfg);ledger.append(d)
        for p in pp:p['mean_retention']=float(np.mean(ret));kept.append(p)
    return kept,ledger,sources


def build_flow_forest(fixed,native,c,corridor,zones):
    evidence=FullPrecisionEvidence(fixed,corridor);mc=json.loads((ROOT/'configs/experiments/mid_far_vegetation_v04.json').read_text());mc={**json.loads((ROOT/mc['v02_config']).read_text()),**mc};all_sites=[];rejected=[];raw=[];links=[]
    for zone in zones:
        ss,rr=zone_sites(zone,evidence,c);all_sites+=ss;rejected+=rr;zone_graphs=[]
        for group in sorted({(s['stand_id'],s['family'],s['mode']) for s in ss}):
            part=[s for s in ss if (s['stand_id'],s['family'],s['mode'])==group];graphs,ink,col,ln=generate(part,group[2],group[1],mc)
            # A shared q band can straddle representation thresholds. Keep its
            # source IDs distinct instead of silently replacing another mode.
            for r in col:
                if '/S/band-' in r['id']:
                    suffix='/mode-'+group[2];r['id']+=suffix;r['source_stroke_id']=r['id'];r['owner_id']+=suffix
                    if 'carrier_id' in r:r['carrier_id']+=suffix
            for link in ln:link['id']+='/mode-'+group[2]
            zone_graphs+=graphs;raw+=ink+col;links+=ln
            for s,g in zip(part,graphs):
                if group[2].startswith('M') and s['stand_role']=='dominant' and s['member_index']%9==0:
                    for r in ink_from_graph(s,g,mc):
                        r.update(source_forward_profile_m=[s['site']['source_forward_m']]*len(r['xy_mm']),pictorial_family=group[1],hierarchy_tier='primary',zone_id=s['zone_id']);raw.append(r)
        spans,ln=continuity_spans(ss,zone_graphs,mc,c);raw+=spans;links+=ln;print('ZONE',zone['spec']['id'],len(ss),'roots',len(spans),'long supports',flush=True)
    # Deduplicate only exact source IDs, never coalesce different short strokes.
    unique={}
    for r in raw:
        if r['id'] in unique and r!=unique[r['id']]:raise ValueError('Conflicting generated source ID: '+r['id'])
        unique[r['id']]=r
    raw=list(unique.values());visible,ledger,sources=visible_flow(raw,evidence,native,mc,c)
    color=colorize([r for r in visible if 'palette_slot' in r],mc);ink=[r for r in visible if 'palette_slot' not in r]
    color=[normalize_rsu(r) for r in color];ink=[normalize_rsu(r) for r in ink]
    return dict(ink=ink,color=color,raw=sources,sites=all_sites,rejected=rejected,links=links,visibility=ledger,terrain_deleted_mm=0.)


def build_flow_colors(fixed,native,forest,c,corridor,zone_field):
    ctx=make_context(fixed,native,c,corridor);ctx['slope_focus']=slope_field(fixed,ctx['D_anchors'],c)
    # Source-depth zone support connects selected mountain shoulders without tinting all terrain.
    ctx['slope_focus']=np.maximum(ctx['slope_focus'],zone_field*.65*(fixed['base']['depth_m']>=1200))
    raw=dict(A=expanded_a(fixed,native,c,ctx));print('A proposals',len(raw['A']),flush=True)
    _,cc,_=build_c_color(fixed,native,c,ctx);raw['C']=[]
    for r in cc:
        line=LineString(r['xy_mm']);n=max(1,int(np.ceil(line.length/47.)))
        for j in range(n):
            a,b=line.length*j/n,line.length*(j+1)/n
            if b-a<3.2:continue
            mid=line.interpolate((a+b)/2).coords[0];weight=float(sample(zone_field,[mid])[0]);prob=.24+.74*weight if r['owner_id']=='terrain-C' else .12+.87*weight
            if quantile(r['id']+f'/zone-C-{j}',c['seed'])>prob:continue
            rec=trim_profiles(r,a,b,r['id']+f'/v06-zone-episode-{j}');rec['zone_weight']=weight;raw['C'].append(rec)
    print('C zone proposals',len(raw['C']),flush=True)
    _,old,_=build_material_color(fixed,native,c,ctx,corridor,True);raw['rock_soil']=[r for r in old if r['color_kind']!='vegetation'];raw['gestures']=[];raw['trunk']=[];regions={}
    for o in native['objects']:
        if o['kind']!='tree':continue
        raw['gestures'].extend(foliage_candidates(fixed,o,native['visible_by_owner'][o['id']],c))
        for r,reg in trunk_candidates(fixed,o,c,paired_supports(o)):regions[r['structural_region_id']]=reg;raw['trunk'].append(r)
    final={};sources={};visibility={};feather={};owners={o['id']:o for o in native['objects']}
    for channel,rows in raw.items():
        final[channel]=[];sources[channel]=[];visibility[channel]=[];feather[channel]=[]
        for original in rows:
            original.update(id='v06/'+original['id'],source_stroke_id='v06/'+original['id']);r=deepcopy(original);obj=owners.get(r['owner_id']);region=None;exact=False
            if channel=='gestures':
                region=geometry_mask((obj['regions']['occupancy']>.012)&obj['visible']).buffer(1.5)
                region=region.union(unary_union([LineString(p).buffer(2.4) for k,p in obj['tree'].structure['members'].items() if k.startswith('arm-')]))
            elif channel=='rock_soil':region=obj['support'].buffer(5.5*(obj.get('color_expansion',1.4)-1) if obj['kind']=='soil' else 0)
            elif channel=='trunk':region=regions[r['structural_region_id']];exact=True
            if region is not None:region=region.difference(corridor)
            peers=[o for o in native['objects'] if intersects(LineString(r['xy_mm']).bounds,o['bounds'])]
            source,d=geometric_feather(r,fixed,c,obj);feather[channel].append(d);retain_color(source,gate_v04(fixed,ctx,peers,c,obj,region,exact_region=exact),sources[channel],visibility[channel],final[channel])
        print('Visible color',channel,len(final[channel]),flush=True)
    final['RSU']=forest['color'];expanded=sum((final[k] for k in ['A','C','rock_soil','gestures','trunk','RSU']),[])
    restrained=[r for r in expanded if r.get('color_channel') not in ['A-derived','C-derived'] or quantile(r['id']+'/restrained',c['seed'])<.44]
    return dict(channels=final,expanded=expanded,restrained=restrained,raw=raw,sources=sources,visibility=visibility,feather=feather,anchors=ctx['D_anchors'],regions=regions,context=ctx)
