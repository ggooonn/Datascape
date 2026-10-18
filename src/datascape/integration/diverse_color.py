"""Separate A-displaced, C-guided and growth/material color vectors for v03.

Geometry quantity, discrete palette assignment and preview alpha are distinct.
Every derived carrier is independently identified, clipped once in its own arc
space and linked to its visible ink/field references. No polygon is painted.
"""
from copy import deepcopy
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString,Point
from shapely.ops import substring
from datascape.strokes.vector import sample,resample
from datascape.integration.vector_wash import color_record,quantile,depth_parameters
from datascape.integration.visibility import burn,signed_clearance,clip_source
from datascape.integration.cluster_scene import intersects,terrain_gate_v02
from datascape.integration.diverse_scene import object_gate_v03
from datascape.rendering.spring_integration import geometry_mask
from datascape.vegetation.tree_occlusion_proof import line_parts


def terrain_eligibility(fixed,objects,corridor):
    b=fixed['base'];mask=b['occupied']&(fixed['retention']>.23)&(fixed['refined']['global_retention']>0)&~burn(corridor)
    mask[898:]=False
    for o in objects:
        back=b['depth_m']>=o['q']-25
        mask &= ~(back & o['regions']['body'])
        mask &= ~((b['depth_m']>o['q']+25)&(o['regions']['soft']>.68))
    return mask


def color_context(fixed,result,corridor):
    eligible=terrain_eligibility(fixed,result['objects'],corridor)
    common=fixed['base']['occupied']&(fixed['retention']>.23)&(fixed['refined']['global_retention']>0)&~burn(corridor)
    common[898:]=False
    return dict(eligible=eligible,common_eligible=common,eligible_clearance=signed_clearance(~eligible).astype('float32'),
        corridor_clearance=signed_clearance(burn(corridor)).astype('float32'),
        global_clearance=signed_clearance(fixed['refined']['global_retention']<=0).astype('float32'))


def color_gate(fixed,context,objects,obj=None,region=None):
    underlying=object_gate_v03(fixed,obj,objects) if obj else terrain_gate_v02(fixed,objects)
    region_distance=signed_clearance(~burn(region)).astype('float32') if region is not None else None
    def gate(xy,arc,r):
        g,reasons=underlying(xy,arc,r);w=max(r['width_profile_mm']);margin=w/2+1.1
        g=np.minimum.reduce([g,sample(context['global_clearance'],xy)-margin,
            sample(context['corridor_clearance'],xy)-margin,xy[:,0]-w/2,600-w/2-xy[:,0],898-w/2-xy[:,1]])
        if obj is None:
            g=np.minimum(g,sample(context['eligible_clearance'],xy)-margin)
            ph=quantile(r['id']+'/retention-phase',0)
            g=np.minimum(g,sample(fixed['retention'],xy)-(.12+.18*(.5+.5*np.sin(arc/23+ph*6.28))))
        if region_distance is not None:g=np.minimum(g,sample(region_distance,xy)-w/2-.1)
        return g,reasons+['color-footprint-reserves','visible-terrain-or-object-support','bounded-open-corridor']
    return gate


def make_carrier(points,key,owner,kind,q,config,basis,channel,refs,pass_index=0):
    p=np.asarray(points,float);q=np.asarray(q,float)
    r=color_record(p,key,owner,kind,q,config,basis,pass_index)
    if r is None:return None
    # color_record may shorten accent paths. Re-evaluate profiles by source arc.
    original=LineString(p);at=np.array([original.project(Point(x)) for x in r['xy_mm']]);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    qp=np.interp(at,arc,q)
    r.update(source_family=channel,color_channel=channel,support_references=refs,
        source_forward_profile_m=qp.tolist(),source_forward_mean_m=float(qp.mean()),
        assumed_footprint_mm=max(r['width_profile_mm']),carrier_basis=basis)
    return r


def retain_carrier(r,gate,sources,ledger,records):
    if r is None:return
    sources.append(r);parts,decision=clip_source(r,gate);ledger.append(decision)
    arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
    for p in parts:
        a,b=p['source_arc_mm'];xy=np.asarray(p['xy_mm']);at=np.r_[a,a+np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        p['source_forward_profile_m']=np.interp(at,arc,r['source_forward_profile_m']).tolist()
        p['source_forward_mean_m']=float(np.mean(p['source_forward_profile_m']));records.append(p)


def local_frame(points):
    p=np.asarray(points);t=np.gradient(p,axis=0)
    for j in range(2):t[:,j]=np.convolve(np.pad(t[:,j],(2,2),mode='edge'),np.ones(5)/5,mode='valid')
    t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-9)
    return t,np.c_[-t[:,1],t[:,0]]


def displaced_a(points,key,config,spacing=None,coincident=False):
    if coincident:return np.asarray(points,float).copy(),dict(max_displacement_mm=0.,mean_normal_offset_mm=0.,mode='coincident-control')
    p=resample(points,.9);t,n=local_frame(p);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    ctl=config['a_color_controls'];ph=quantile(key+'/offset',config['seed'])*2*np.pi
    if spacing is None:gap=np.full(len(p),4.)
    else:
        distances,ids=spacing[0].query(p,k=24)
        labels=spacing[1][ids];valid=labels!=spacing[2]
        gap=np.min(np.where(valid,distances,20.),axis=1)
    gap=np.convolve(np.pad(gap,(4,4),mode='edge'),np.ones(9)/9,mode='valid')
    amplitude=np.minimum(ctl['normal_offset_mm'][1],np.maximum(.32,gap*.37))
    sign=1 if quantile(key+'/side',config['seed'])>.5 else -1
    offset=sign*amplitude*(.80+.20*np.sin(arc/ctl['phase_wavelength_mm']*2*np.pi+ph))
    slide=ctl['tangent_shift_mm']*.35*np.sin(arc/(ctl['phase_wavelength_mm']*1.3)+ph)
    delta=n*offset[:,None]+t*slide[:,None]
    # Bound rapid local phase changes in compressed mountain forms. The
    # derivative bound limits additional local turn; geometry is never jittered.
    dd=np.gradient(delta,axis=0);ds=np.maximum(np.linalg.norm(np.gradient(p,axis=0),axis=1),1e-5)
    rate=np.max(np.linalg.norm(dd,axis=1)/ds)
    scale=min(1.,np.tan(np.radians(ctl['maximum_turn_deg']))/max(rate,1e-9))
    delta*=scale
    return p+delta,dict(max_displacement_mm=float(np.linalg.norm(delta,axis=1).max()),
        mean_normal_offset_mm=float(np.mean(np.abs(offset*scale))),phase_radians=ph,turn_derivative_bound_deg=ctl['maximum_turn_deg'],mode='terrain-frame-displaced')


def build_a_color(fixed,result,config,context,coincident=False):
    records=[];sources=[];ledger=[];a=[r for r in result['terrain'] if r['source_family']=='A']
    samples=[];labels=[]
    for i,r in enumerate(a):
        p=resample(r['xy_mm'],2.);samples.extend(p);labels.extend([r['source_stroke_id']]*len(p))
    tree=cKDTree(np.asarray(samples));labels=np.array(labels,dtype=object)
    for i,source in enumerate(a):
        line=LineString(source['xy_mm']);q=float(sample(fixed['base']['depth_m'],[line.interpolate(.5,normalized=True).coords[0]])[0]);u=float(depth_parameters(q,config)['u'])
        probability=float(np.interp(q,config['a_color_controls']['selection_depth_knots_m'],config['a_color_controls']['selection_near_middle_far']))
        if quantile(source['id']+'/A-color-select',config['seed'])>probability:continue
        segment=52.-u*12.;count=max(1,int(np.ceil(line.length/segment)))
        for j in range(count):
            lo=j*line.length/count;hi=(j+1)*line.length/count
            frac=quantile(source['id']+f'/episode-{j}',config['seed']);trim=(.035+.14*frac)*(hi-lo)
            aa,bb=lo+trim*.4,hi-trim*.6
            if bb-aa<3.3:continue
            original=substring(line,aa,bb);key=f'v03/A-color/{source["id"]}/episode-{j}'
            p,controls=displaced_a(original.coords,key,config,(tree,labels,source['source_stroke_id']),coincident)
            r=make_carrier(p,key,'terrain-A','terrain',sample(fixed['base']['depth_m'],p),config,
                source['source_stroke_id']+f'/color-region-{j//2}','A-derived',
                [dict(source_id=source['source_stroke_id'],visible_fragment_id=source['id'],
                      visible_arc_mm=[aa,bb],original_arc_mm=[source['source_arc_mm'][0]+aa,source['source_arc_mm'][0]+bb])])
            if r:r['derivation_controls']=controls
            bbounds=LineString(p).bounds;peers=[o for o in result['objects'] if intersects(bbounds,o['bounds'])]
            retain_carrier(r,color_gate(fixed,context,peers),sources,ledger,records)
    return records,sources,ledger


class DirectionField:
    """Nearest real C/B tangent references, smoothly sign-aligned locally."""
    def __init__(self,terrain,neighbors=8,b_blend_range=(.18,.53)):
        self.data={};self.neighbors=neighbors;self.b_blend_range=b_blend_range
        for layer in ['C','B']:
            points=[];directions=[];owners=[]
            for r in terrain:
                if r['source_family']!=layer:continue
                p=resample(r['xy_mm'],4.);t,_=local_frame(p)
                flip=t[:,0]<0;t[flip]*=-1
                points.extend(p);directions.extend(t);owners.extend([r['id']]*len(p))
            self.data[layer]=(cKDTree(points),np.asarray(directions),np.asarray(owners,dtype=object))
    def at(self,xy):
        xy=np.atleast_2d(xy);answers={}
        for layer in ['C','B']:
            tree,tangents,owners=self.data[layer];distance,index=tree.query(xy,k=min(self.neighbors,len(tangents)))
            if distance.ndim==1:distance=distance[:,None];index=index[:,None]
            weights=1/(distance+5.)**2;weights/=weights.sum(axis=1)[:,None]
            theta=np.arctan2(tangents[index,1],tangents[index,0])
            angle=.5*np.arctan2(np.sum(weights*np.sin(2*theta),axis=1),np.sum(weights*np.cos(2*theta),axis=1))
            answers[layer]=(np.c_[np.cos(angle),np.sin(angle)],distance[:,0],owners[index[:,0]])
        tc,dc,cref=answers['C'];tb,db,bref=answers['B']
        # Align the undirected fields before blending; opposite vertical
        # parameterization must not create a false horizontal turn.
        tb[np.sum(tc*tb,axis=1)<0]*=-1
        lo,hi=self.b_blend_range;blend=np.clip(lo+(hi-lo)*dc/(dc+db+1e-6),lo,hi)
        t=tc*(1-blend[:,None])+tb*blend[:,None]
        t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-9)
        return t,cref,bref
    def references(self,xy):
        refs=[]
        for layer in ['C','B']:
            tree,t,owners=self.data[layer];distance,index=tree.query(xy,k=min(self.neighbors,len(t)))
            for owner in sorted(set(owners[np.asarray(index)].ravel())):
                refs.append(dict(source_id=str(owner),role=layer+' interpolated local direction'))
        return refs


def build_c_color(fixed,result,config,context):
    records=[];sources=[];ledger=[];ctl=config['c_color_controls'];field=DirectionField(result['terrain'],ctl['direction_interpolation_neighbors'],ctl['b_blend_range'])
    for source in result['color_sources']:
        p=resample(source['xy_mm'],1.);t,n=local_frame(p)
        source_q=float(sample(fixed['base']['depth_m'],[p[len(p)//2]])[0])
        for k in range(ctl['source_passes']):
            keep=float(np.interp(source_q,ctl['selection_depth_knots_m'],ctl['parallel_pass_retention'][k]))
            if quantile(source['id']+f'/C-parallel-{k}',config['seed'])>keep:continue
            if k==0:points=p
            else:
                arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
                offset=(2.6 if k==1 else -3.2)*(1+.12*np.sin(arc/21+k));points=p+n*offset[:,None]
            key=f'v03/C-color/{source["id"]}/pass-{k}'
            r=make_carrier(points,key,'terrain-C','terrain',sample(fixed['base']['depth_m'],points),config,
                source['source_stroke_id']+f'/region-{k}','C-derived',
                [dict(source_id=source['source_stroke_id'],visible_fragment_id=source['id'],original_arc_mm=source['source_arc_mm'])],k)
            if r:r['derivation_controls']=dict(normal_offset_mm=0 if k==0 else 2.6 if k==1 else -3.2,source_pass=k)
            peers=[o for o in result['objects'] if intersects(LineString(points).bounds,o['bounds'])]
            retain_carrier(r,color_gate(fixed,context,peers),sources,ledger,records)
    pitch=ctl['extra_field_pitch_mm'];qfield=fixed['base']['depth_m']
    for row,y in enumerate(np.arange(230,888,pitch)):
        # The staggered field is one canvas lattice, not a new hatch per object.
        for col,x in enumerate(np.arange(7+(row%2)*pitch*.5,596,pitch*1.6)):
            if sample(context['eligible_clearance'],[[x,y]])[0]<3:continue
            q=float(sample(qfield,[[x,y]])[0]);u=float(depth_parameters(q,config)['u']);key=f'v03/C-field/row-{row}/col-{col}'
            # Low-frequency concentrations and dissolution, with actual open corridors.
            local=.60+.40*(.5+.5*np.sin(x/69+y/93)*np.cos(y/53-x/170))
            rate=(ctl['field_selection_near_far'][0]*(1-u)+ctl['field_selection_near_far'][1]*u)*local
            rate*=float(np.interp(q,ctl['selection_depth_knots_m'],ctl['field_depth_multiplier']))
            if quantile(key,config['seed'])>rate:continue
            length=ctl['field_length_near_far_mm'][0]*(1-u)+ctl['field_length_near_far_mm'][1]*u
            paths=[]
            for sign in [-1,1]:
                path=[np.array([x,y],float)];previous=field.at(path[-1])[0][0]*sign
                for j in range(int(length/2)):
                    tangent=field.at(path[-1])[0][0]
                    if np.dot(tangent,previous)<0:tangent=-tangent
                    inertia=ctl['streamline_turn_inertia'];direction=previous*inertia+tangent*(1-inertia)
                    direction/=max(np.linalg.norm(direction),1e-9)
                    path.append(path[-1]+direction);previous=direction
                paths.append(np.asarray(path))
            points=np.vstack([paths[0][::-1],paths[1][1:]])
            _,cref,bref=field.at([[x,y]])
            r=make_carrier(points,key,'terrain-C-field','terrain',sample(qfield,points),config,
                f'C-field/region-{row//5}-{col//4}','C-derived',
                field.references([x,y]))
            if r:r['derivation_controls']=dict(canvas_pitch_mm=pitch,local_selection=rate,field_length_mm=length,source='nearest visible C and B tangents')
            peers=[o for o in result['objects'] if intersects(LineString(points).bounds,o['bounds'])]
            retain_carrier(r,color_gate(fixed,context,peers),sources,ledger,records)
    return records,sources,ledger


def foliage_colors(fixed,obj,visible,config,structured):
    """Actual accepted foliage rays + their branch origins, never rotated hatch."""
    rays=[r for r in visible if r['grammar_part']=='foliage-field'];units=defaultdict(list)
    for r in rays:units[r.get('component_key',r['id']).rsplit('-',1)[0]].append(r)
    tree=obj['tree'];lobes={l['key']:l for l in tree.lobes}
    meta={u['key']:u for u in tree.canopy_diagnostics['units']}
    for unit,rr in sorted(units.items()):
        info=meta.get(unit,{});state=info.get('state','light');pad=info.get('pad',info.get('owner_pad',unit.split('/')[0]));lobe=lobes.get(pad)
        probability={'dense':.96,'light':.76,'open':.38,'remnant':.35}.get(state,.7)
        if quantile(obj['id']+'/'+unit+'/color-unit',config['seed'])>probability:continue
        for i,s in enumerate(sorted(rr,key=lambda r:r['id'])):
            if obj['representation']=='aggregate' and i>0:continue
            p=np.asarray(s['xy_mm']);d=p[-1]-p[0];d/=max(np.linalg.norm(d),1e-9)
            pivot=p[0];branch_key=lobe.get('source_branch') if lobe else None
            branch=np.asarray(tree.structure['members'].get(branch_key,[pivot-d*4,pivot]))
            radial=pivot-branch[0];radial/=max(np.linalg.norm(radial),1e-9)
            if np.dot(radial,d)<0:radial=-radial
            direction=d*.68+radial*.32 if structured else d
            direction/=max(np.linalg.norm(direction),1e-9);normal=np.array([-direction[1],direction[0]])
            passes=2 if structured and obj['height_mm']>=65 and state=='dense' and i==0 else 1
            for k in range(passes):
                phase=quantile(unit+f'/stroke-{i}-{k}',config['seed']);length=max(3.1,min(10.5,LineString(p).length*(1.12+.35*phase)))
                if obj['representation']=='aggregate':length=min(length,4.8)
                start=pivot+normal*(.8 if k==0 else -1.1)+direction*(phase-.5)*1.3
                t=np.linspace(0,1,7);bend=(.55 if structured else .10)*(1 if i%2 else -1)
                points=start+t[:,None]*length*direction+np.sin(np.pi*t)[:,None]*normal*bend
                refs=[dict(source_id=s['id'],role='visible accepted foliage ray',catalog_component=s.get('component_key'))]
                if structured:refs.append(dict(source_id=obj['id']+'/'+str(branch_key),role='catalog branch origin',branch_points_mm=branch.tolist()))
                yield points,f'{obj["id"]}/{unit}/ray-{i}/pass-{k}',f'{obj["group"]}/{pad}/color-zone-{i//3}/pass-{k}',refs,k


def rock_colors(obj,visible,config,structured):
    candidates=[r for r in visible if r['grammar_part'] not in ('ink-contour','feature-terminal')]
    for j,s in enumerate(sorted(candidates,key=lambda r:r['id'])):
        if not structured and j%2:continue
        p=resample(s['xy_mm'],.8)
        if len(p)<2:continue
        t,n=local_frame(p)
        for k in range(2 if structured and obj['native_width_mm']>=65 else 1):
            side=1 if (j+k)%2 else -1
            offset=side*(1.3+1.5*k)
            points=p+n*offset
            # Actual bedding/fracture/spall paths supply changing surface directions.
            yield points,f'{obj["id"]}/plane-{j}/pass-{k}',f'{obj["group"]}/{obj["field_regime"]}/plane-zone-{j//3}/pass-{k}',[
                dict(source_id=s['id'],role='visible rock structural carrier',grammar_part=s['grammar_part'],structural_field_id=obj.get('field_regime'))],k


def soil_colors(fixed,obj,config,structured):
    host=np.asarray(obj['host']['xy_mm']);x0,y0,x1,y1=obj['support'].bounds
    spread=obj.get('color_expansion',1.4) if structured else 1.1
    region=obj['support'].buffer(5.5*(spread-1),join_style=1)
    x0,y0,x1,y1=region.bounds;hf=np.interp
    # A shared broader support receives several local concentrations. It is not painted.
    cx=(x0+x1)/2;phase=quantile(obj['group']+'/Soil-flow',config['seed'])*6.28
    for row,offset in enumerate(np.arange(y0-float(host[:,1].max())-4,y1-float(host[:,1].min())+4,2.8 if structured else 4.8)):
        x=np.linspace(x0,x1,max(12,int(x1-x0)));base=np.interp(x,host[:,0],host[:,1]);drift=-.16*(x-cx)+.7*np.sin((x-cx)/27+phase)
        points=np.c_[x,base+offset+drift]
        for j,g in enumerate(line_parts(LineString(points).intersection(region))):
            if g.length<3.1:continue
            # Alternating broad color and bare ink patches, not one uniform mound.
            local=.55+.45*np.sin((g.centroid.x-cx)/22+phase)**2
            if quantile(obj['id']+f'/row-{row}/{j}',config['seed'])>local:continue
            yield np.asarray(g.coords),f'{obj["id"]}/broad-flow-{row}/{j}',f'{obj["group"]}/Soil-zone-{row//3}',[
                dict(source_id=obj['host']['id'],role='actual terrain host'),dict(source_id=obj['cross_flow_source_id'],role='neighboring C flow')],0


def build_material_color(fixed,result,config,context,corridor,structured):
    records=[];sources=[];ledger=[]
    for obj in result['objects']:
        kind={'tree':'vegetation','rock':'rock','soil':'Soil'}[obj['kind']];visible=result['visible_by_owner'][obj['id']]
        if not visible:continue
        if obj['kind']=='tree':
            generator=foliage_colors(fixed,obj,visible,config,structured)
            region=geometry_mask((obj['regions']['occupancy']>.012)&obj['visible']).buffer(1.5)
        elif obj['kind']=='rock':
            generator=rock_colors(obj,visible,config,structured);region=obj['support']
        else:
            generator=soil_colors(fixed,obj,config,structured);region=obj['support'].buffer(5.5*(obj.get('color_expansion',1.4)-1) if structured else .55)
        peers=[o for o in result['objects'] if intersects(region.bounds,o['bounds'])]
        gate=color_gate(fixed,context,peers,obj,region.difference(corridor))
        for p,key,basis,refs,k in generator:
            qvals=sample(obj['q'],p)
            r=make_carrier(p,'v03/material/'+key,obj['id'],kind,qvals,config,basis,'material-C-like',refs,k)
            if r:r.update(group_id=obj['group'],catalog_object_id=obj['id'],material_structure='growth/plane/shared-ground' if structured else 'restrained catalog-ray/carrier')
            retain_carrier(r,gate,sources,ledger,records)
    return records,sources,ledger


def coverage_metrics(records,fixed,context):
    """Split final centerline length by actual source q, not by screen y or alpha."""
    names=['near','middle','far'];by={k:dict(paths=0,length_mm=0.,common_domain_terrain_length_mm=0.,palette_length_mm={},channel_length_mm={}) for k in names}
    eligible=context['eligible'];q=fixed['base']['depth_m'];common_float=context['common_eligible'].astype(float)
    masks=[q<1000,(q>=1000)&(q<2200),q>=2200]
    for name,mask in zip(names,masks):
        by[name]['eligible_visible_terrain_mm2']=int((mask&eligible).sum())
        by[name]['common_visible_terrain_mm2']=int((mask&context['common_eligible']).sum())
    slot={};channel={}
    for r in records:
        p=np.asarray(r['xy_mm']);a=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];length=a[-1]
        at=np.linspace(0,length,max(2,int(np.ceil(length/.6))+1));x=np.interp(at,a,p[:,0]);y=np.interp(at,a,p[:,1]);qq=np.interp(at,a,r['source_forward_profile_m'])
        dl=np.diff(at);mid=(qq[:-1]+qq[1:])/2;bands=np.where(mid<1000,0,np.where(mid<2200,1,2));pal=r['palette_slot'];ch=r['color_channel']
        slot[pal]=slot.get(pal,0.)+length;channel[ch]=channel.get(ch,0.)+length
        for i,name in enumerate(names):
            value=float(dl[bands==i].sum())
            if not value:continue
            b=by[name];b['paths']+=1;b['length_mm']+=value
            if ch!='material-C-like':
                midxy=np.c_[(x[:-1]+x[1:])/2,(y[:-1]+y[1:])/2];inside=sample(common_float,midxy)>.5
                b['common_domain_terrain_length_mm']+=float(dl[(bands==i)&inside].sum())
            b['palette_length_mm'][pal]=b['palette_length_mm'].get(pal,0.)+value
            b['channel_length_mm'][ch]=b['channel_length_mm'].get(ch,0.)+value
    for name,b in by.items():
        area=b['eligible_visible_terrain_mm2'];terrain=sum(v for k,v in b['channel_length_mm'].items() if k!='material-C-like')
        b['terrain_color_length_mm']=terrain;b['terrain_length_density_mm_per_mm2']=terrain/max(area,1)
        b['all_color_length_density_mm_per_mm2']=b['length_mm']/max(area,1)
        b['common_domain_terrain_density_mm_per_mm2']=b['common_domain_terrain_length_mm']/max(b['common_visible_terrain_mm2'],1)
    total=sum(slot.values())
    return dict(paths=len(records),length_mm=total,depth=by,palette_length_mm=slot,
        palette_length_percent={k:100*v/max(total,1e-9) for k,v in slot.items()},channel_length_mm=channel,
        basis='Final vector centerline length; source-q splitting. A path crossing bands counts in each; no pigment volume or dry opacity claim.',
        eligibility='one-mm F2 occupied cells, retention > .23, global reserve and corridors excluded, visible core/body exclusions')
