"""Landscape-scale placement supports and color adapters on immutable F2 fields.

Spines are nonplotting composition hints, not traced silhouettes or terrain edits.
Accepted catalogs remain unchanged. Short S crown lobes are integration-level
wash experiments on supported growth graphs, not a new approved forest catalog.
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
            ident=f'v07/{spec["id"]}/stratum-{layer}/body-{j}'
            try:
                p=supported_root(evidence,x,q,yh,window);site=evidence.point(p)
                if not site['exact_contact']:raise ValueError(site['rejection'])
                if sample(evidence.protected_clearance,[p],order=0)[0]<3:raise ValueError('locked-reserve-footprint')
            except ValueError as exc:rejected.append(dict(id=ident,x_mm=float(x),requested_q_m=float(q),reason=str(exc)));continue
            scale=(.72+.52*rhythm)*(.88+.22*phase(ident+'/height',c['seed']))
            role='dominant' if rhythm>.78 else 'subordinate';height=spec['height_mm']*scale
            mode='M2' if site['source_forward_m']<1700 else 'F1' if site['source_forward_m']<2700 else 'F2'
            sites.append(dict(id=ident,stand_id=f'v07/{spec["id"]}/stratum-{layer}',patch_id=f'v07/{spec["id"]}/stratum-{layer}',zone_id=spec['id'],
                stand_index=layer,stand_role=role,member_index=j,member_count=len(xs),root_xy_mm=p.tolist(),height_mm=height,
                form=['P','B','U'][j%3],site=site,guide_u=u,guide_source_id='v07/nonplotting/'+spec['id'],
                tangent_xy=measured_tangent(evidence,p,[1.,0.]),family=family,mode=mode,source_q_offset_m=float(q-baseq)))
    return sites,rejected


def crown_units(sites,graphs,cfg,c):
    """Short oblique crown lobes around individual growth graphs, never connectors.

    Larger masses arise from denser, overlapping strata of supported units.
    Each stroke belongs to one local crown; no path interpolates between roots.
    """
    rows=[];lookup={g['body_id']:g for g in graphs}
    for site in sites:
        if site['family']!='S':continue
        g=lookup[site['id']];root=np.array(site['root_xy_mm']);h=site['height_mm'];far=g['mode'].startswith('F')
        n=8 if far else 13
        for j in range(n):
            key=site['id']+f'/S-crown/lobe-{j}';ph=phase(key,c['seed']);v=phase(key+'/position',c['seed'])
            # Unequal local patches: broad middle, narrowing top and releases.
            t=(j+.5)/n;across=(v-.5)*h*(.42 if far else .72)*np.sin(np.pi*t)**.5
            center=root+[across,-h*(.34+.62*t)]
            length=min(15.6,max(3.6,h*(.20+.18*ph)))
            theta=(-.70+1.25*ph)+(0.22 if site['stand_index']%2 else -.16)
            direction=np.array([np.cos(theta),np.sin(theta)]);normal=np.array([-direction[1],direction[0]])
            u=np.linspace(0,1,max(12,int(length/.35)));p=center+(u-.5)[:,None]*length*direction+np.sin(u*np.pi)[:,None]*normal*(.25+.5*v)
            rec=make_record(key,p,site,g,g['branches'][1],'color','S','medium' if j%3 else 'short',cfg,
                local_role='shadow' if j%5==0 else 'tip' if j%4==0 else 'body',
                zone_id=site['zone_id'],carrier_id=key,source_member_ids=[site['id']],
                generation_rule='single-root short crown lobe; continuity comes from overlapping local units, no inter-root painted guide')
            peak=(1.15 if far else 2.25)*(.72+.58*ph)
            widths=peak*(.22+.78*np.sin(np.pi*u)**.65)
            rec.update(width_mm=float(widths.mean()),width_profile_mm=widths.tolist(),assumed_footprint_mm=float(widths.max()),expressive_width_intent=True,brush_pressure_calibrated=False)
            rows.append(rec)
    return rows,[]


def vegetation_palette(rows,c):
    """Patch-coherent warm, muted and cool roles using existing pigment slots."""
    out=[]
    regimes=[(['C1','C2','C4','A5','D1'],[.23,.40,.23,.10,.04]),
             (['C1','C2','C4','A5','C3'],[.12,.21,.40,.22,.05]),
             (['C1','C2','C3','A3','A5','C4'],[.10,.12,.31,.15,.20,.12])]
    for old in rows:
        rec=deepcopy(old);xy=np.array(rec['xy_mm']);q=float(np.mean(rec.get('source_forward_profile_m',[rec.get('source_forward_m',1200)])))
        zone=rec.get('zone_id',rec.get('group_id',rec['owner_id']));x=float(xy[:,0].mean())
        # Shared broad palette neighbourhood, no independent rainbow per stroke.
        regime=int(phase(zone+f'/palette-patch-{int(x//45)}',c['seed'])*3)
        slots,weights=regimes[regime];w=np.array(weights);depth=np.clip((q-800)/2600,0,1)
        for j,slot in enumerate(slots):
            if slot in ['C1','A3','A5']:w[j]*=1+.55*depth
            elif slot=='C3':w[j]*=1-.40*depth
            if rec.get('local_role')=='tip' and slot in ['C1','C2']:w[j]*=1.3
        u=phase(rec['source_stroke_id']+'/v07-vegetation-palette',c['seed']);idx=min(len(w)-1,int(np.searchsorted(np.cumsum(w)/w.sum(),u)))
        rec.update(palette_slot=slots[idx],color_logic='v07-vegetation-patch-and-depth',palette_regime=['warm-yellow-green','muted-olive','cool-jade-gray'][regime])
        out.append(rec)
    return out


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
            zone_graphs+=graphs;raw+=ink+([] if group[1]=='S' else col);links+=ln
            for s,g in zip(part,graphs):
                if group[2].startswith('M') and s['stand_role']=='dominant' and s['member_index']%9==0:
                    for r in ink_from_graph(s,g,mc):
                        r.update(source_forward_profile_m=[s['site']['source_forward_m']]*len(r['xy_mm']),pictorial_family=group[1],hierarchy_tier='primary',zone_id=s['zone_id']);raw.append(r)
        spans,ln=crown_units(ss,zone_graphs,mc,c);raw+=spans;links+=ln;print('ZONE',zone['spec']['id'],len(ss),'roots',len(spans),'local crown strokes',flush=True)
    # Deduplicate only exact source IDs, never coalesce different short strokes.
    unique={}
    for r in raw:
        if r['id'] in unique and r!=unique[r['id']]:raise ValueError('Conflicting generated source ID: '+r['id'])
        unique[r['id']]=r
    raw=list(unique.values());visible,ledger,sources=visible_flow(raw,evidence,native,mc,c)
    color=colorize([r for r in visible if 'palette_slot' in r],mc);ink=[r for r in visible if 'palette_slot' not in r]
    color=vegetation_palette([normalize_rsu(r) for r in color],c);ink=[normalize_rsu(r) for r in ink]
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
            rec=trim_profiles(r,a,b,r['id']+f'/v07-zone-episode-{j}');rec['zone_weight']=weight;raw['C'].append(rec)
    print('C zone proposals',len(raw['C']),flush=True)
    _,old,_=build_material_color(fixed,native,c,ctx,corridor,True);raw['rock_soil']=[r for r in old if r['color_kind']!='vegetation'];raw['gestures']=[];raw['trunk']=[];regions={}
    for o in native['objects']:
        if o['kind']!='tree':continue
        raw['gestures'].extend(foliage_candidates(fixed,o,native['visible_by_owner'][o['id']],c))
        for r,reg in trunk_candidates(fixed,o,c,paired_supports(o)):regions[r['structural_region_id']]=reg;raw['trunk'].append(r)
    foliage_regions={}
    final={};sources={};visibility={};feather={};owners={o['id']:o for o in native['objects']}
    for channel,rows in raw.items():
        final[channel]=[];sources[channel]=[];visibility[channel]=[];feather[channel]=[]
        for original in rows:
            original.update(id='v07/'+original['id'],source_stroke_id='v07/'+original['id']);r=deepcopy(original);obj=owners.get(r['owner_id']);region=None;exact=False
            if channel=='gestures':
                if obj['id'] not in foliage_regions:
                    local=geometry_mask((obj['regions']['occupancy']>.012)&obj['visible']).buffer(1.5)
                    foliage_regions[obj['id']]=local.union(unary_union([LineString(p).buffer(2.4) for k,p in obj['tree'].structure['members'].items() if k.startswith('arm-')]))
                region=foliage_regions[obj['id']]
            elif channel=='rock_soil':region=obj['support'].buffer(5.5*(obj.get('color_expansion',1.4)-1) if obj['kind']=='soil' else 0)
            elif channel=='trunk':region=regions[r['structural_region_id']];exact=True
            if region is not None:region=region.difference(corridor)
            peers=[o for o in native['objects'] if intersects(LineString(r['xy_mm']).bounds,o['bounds'])]
            source,d=geometric_feather(r,fixed,c,obj);feather[channel].append(d);retain_color(source,gate_v04(fixed,ctx,peers,c,obj,region,exact_region=exact),sources[channel],visibility[channel],final[channel])
        print('Visible color',channel,len(final[channel]),flush=True)
    final['gestures']=vegetation_palette(final['gestures'],c)
    final['RSU']=forest['color'];expanded=sum((final[k] for k in ['A','C','rock_soil','gestures','trunk','RSU']),[])
    restrained=[r for r in expanded if r.get('source_family')!='RSU' or quantile(r['id']+'/lighter-crown',c['seed'])<.40]
    return dict(channels=final,expanded=expanded,restrained=restrained,raw=raw,sources=sources,visibility=visibility,feather=feather,anchors=ctx['D_anchors'],regions=regions,context=ctx)
