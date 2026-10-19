"""Recovered bounded v09 adapter on immutable v08 Case 2 visible vectors.

Only source-depth canopy conflicts, selected contacts and derived hatch stacks
change. Native depth sheets remain declared 2.5D, not full 3D certification.
"""
from pathlib import Path
from copy import deepcopy
from collections import defaultdict,Counter
import json,gzip,pickle,hashlib,argparse,csv
import numpy as np
from scipy.ndimage import gaussian_filter,distance_transform_edt
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union
from datascape.strokes.vector import read_vectors,resample,sample,phase
from datascape.integration.visibility import burn,signed_clearance,clip_source,digest
from datascape.integration.cluster_scene import intersects
from datascape.integration.spring_v05_audit import source_audit,length
from datascape.rendering.spring_macro_study import write_gz,width_envelope
ROOT=Path(__file__).resolve().parents[3]
CHANNELS=['A','C','rock_soil','gestures','trunk','RSU']


def load_control(path):
 p=Path(path);return dict(ink=read_vectors(p/'case2_ink.json.gz')['strokes'],channels={k:read_vectors(p/f'case2_channel_{k}.json.gz')['strokes'] for k in CHANNELS})


def cut(r,gate,minimum,reason):
 parts,d=clip_source(deepcopy(r),gate,minimum_mm=minimum,step_mm=.22);d['adapter_reason']=reason
 if d['removed_mm']<1e-8:return [r],d
 arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))]
 for s in parts:
  a,b=s['source_arc_mm'];at=a+np.r_[0,np.cumsum(np.linalg.norm(np.diff(s['xy_mm'],axis=0),axis=1))]
  for k in ['source_forward_profile_m','pressure_intent_samples']:
   if k in r:s[k]=np.interp(at,arc,r[k]).tolist()
  s.update(integration_parent_id=r['id'],integration_parent_arc_mm=[a,b],integration_rule=reason)
  if 'source_forward_profile_m' in s:s['source_forward_mean_m']=float(np.mean(s['source_forward_profile_m']))
 return parts,d


def q_at(r,xy,arc):
 if 'source_forward_profile_m' not in r:return np.full(len(xy),r.get('source_object_depth_m',r.get('source_forward_m',0.)))
 aa=np.r_[0,np.cumsum(np.linalg.norm(np.diff(r['xy_mm'],axis=0),axis=1))];return np.interp(arc,aa,r['source_forward_profile_m'])


def masks(context,ch):
 by=defaultdict(list)
 for r in ch['gestures']:by[r['owner_id']].append(r)
 trees=[]
 for old in context['objects']:
  if old['kind']!='tree':continue
  o=dict(old);paint=np.zeros((900,600),bool)
  for r in by[o['id']]:paint|=burn(width_envelope(r) if r.get('expressive_width_intent') else LineString(r['xy_mm']).buffer(r['width_mm']/2))
  o['combined_occupancy']=np.maximum(o['occupancy'],gaussian_filter(paint.astype('float32'),o['sigma_mm']));trees.append(o)
 return trees


def canopy_gate(trees,c,r):
 peers=[o for o in trees if intersects(LineString(r['xy_mm']).bounds,o['bounds'])];cohort=r.get('source_member_ids',[r.get('owner_id',r['id'])])[0]
 def gate(xy,arcs,rec):
  q=q_at(rec,xy,arcs);good=np.full(len(xy),1e6);reasons=[];p=np.array(rec['xy_mm']);t=np.gradient(p,axis=0);t/=np.maximum(np.linalg.norm(t,axis=1)[:,None],1e-9);n=np.c_[-t[:,1],t[:,0]];aa=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];normal=np.c_[np.interp(arcs,aa,n[:,0]),np.interp(arcs,aa,n[:,1])];w=float(max(rec.get('width_profile_mm',[rec.get('assumed_footprint_mm',rec['width_mm'])])))
  for o in peers:
   behind=q-np.interp(xy[:,0],np.arange(600)+.5,o['q_row'])>25
   if not behind.any():continue
   occ=np.maximum.reduce([sample(o['combined_occupancy'],xy),sample(o['combined_occupancy'],xy+normal*w/2),sample(o['combined_occupancy'],xy-normal*w/2)])
   threshold=.045+(.27-.045)*(.55+.44*phase(cohort+'/'+o['id']+'/edge-release',c['seed']));core=threshold-occ;hard=sample(o['body_distance'],xy)-w/2-.7;good=np.minimum(good,np.where(behind,np.minimum(hard,core),1e6))
   if np.any(behind&((core<0)|(hard<0))):reasons.append('source-behind-native:'+o['id'])
  return good,reasons+['v09-visible-occupancy-core-and-graduated-edges']
 return gate


def coverage(rows):
 out=set()
 for r in rows:out.update(map(tuple,np.floor(resample(r['xy_mm'],1.)/12).astype(int)))
 return out


def horizontal(r):
 d=np.diff(r['xy_mm'],axis=0);ll=np.linalg.norm(d,axis=1);return float(ll[np.abs(d[:,1])<=np.abs(d[:,0])*np.tan(np.deg2rad(15))].sum()/max(ll.sum(),1e-9))


def classify(ink,ch):
 return {'A_ink':[r for r in ink if r['source_family']=='A'],'A_color':ch['A'],'C_color':ch['C'],'Soil_ink':[r for r in ink if r['source_family']=='Soil' and '/root-contact-Soil' not in r['owner_id'] and not r.get('grounding_tree_id')],'tree_ground_ink':[r for r in ink if '/root-contact-Soil' in r['owner_id'] or r.get('grounding_tree_id')],'Soil_color':[r for r in ch['rock_soil'] if r.get('color_kind')=='Soil'],'rock_ink':[r for r in ink if r['source_family']=='rock']}


def hatch_fields(cats):
 fields={};counts={}
 for k,rows in cats.items():
  mask=np.zeros((900,600),bool);count=np.zeros((900,600),np.uint16)
  for r in rows:
   if horizontal(r)<.70 or np.mean(np.array(r['xy_mm'])[:,1])<555:continue
   line=LineString(r['xy_mm']);mask|=burn(line.buffer(.65));count+=burn(line.buffer(2.1))
  fields[k]=distance_transform_edt(~mask) if mask.any() else np.full((900,600),1e6);counts[k]=count
 return fields,counts


def root_plans(ink,trees,context,fixed,c):
 ground=[(r,LineString(r['xy_mm'])) for r in ink if r['source_family'] in ['A','Soil'] and '/root-contact-Soil' not in r['owner_id']];by=defaultdict(list)
 for r in ink:
  if r['source_family']=='tree' and r.get('grammar_part')=='trunk-contour':by[r['owner_id']].append(r)
 plans=[];added=[];protected=set();burials={};sources=[];global_clear=signed_clearance(fixed['refined']['global_retention']<=0);reserve=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']]);reserve_clear=signed_clearance(burn(reserve))
 for o in trees:
  root=np.array(o['site']['xy_mm']);h=o['height_mm'];feet=[]
  for r in by[o['id']]:
   p=np.array(r['xy_mm'])
   for end in [0,-1]:
    foot=p[end]
    if np.linalg.norm(foot-root)<max(5.,h*.09) and foot[1]>root[1]-h*.065:feet.append((float(np.linalg.norm(foot-root)),r,foot,end))
  if not feet:continue
  feet.sort(key=lambda x:(x[0],x[1]['id'],x[3]));_,trunk,foot,end=feet[0];best=[]
  for r,line in ground:
   if line.distance(Point(foot))>9:continue
   near=np.array(line.interpolate(line.project(Point(foot))).coords[0]);q=float(sample(fixed['base']['depth_m'],[near])[0]);delta=abs(q-o['site']['source_forward_m'])
   if delta<=max(35,.055*o['site']['source_forward_m']):best.append((line.distance(Point(foot))+(0 if r['source_family']=='A' else .6),r['id'],r,line,near,delta))
  row=dict(tree_id=o['id'],root_xy_mm=root.tolist(),visible_foot_xy_mm=foot.tolist(),height_mm=h,status='no-close-depth-compatible-support')
  if not best:plans.append(row);continue
  _,_,host,line,near,delta=min(best,key=lambda x:(x[0],x[1]));gap=float(np.linalg.norm(near-foot));protected.add(host['id']);row.update(host_id=host['id'],host_nearest_xy_mm=near.tolist(),gap_before_mm=gap,source_depth_difference_m=delta)
  if gap<1.35:row['status']='existing-ground-contact';plans.append(row);continue
  if 1.35<=gap<=5.5 and .7<foot[1]-near[1]<=min(4.5,h*.055) and h>=38:
   ar=line.project(Point(near));a=np.array(line.interpolate(max(0,ar-1)).coords[0]);b=np.array(line.interpolate(min(line.length,ar+1)).coords[0]);d=b-a
   if abs(d[0])>.1:burials[o['id']]=dict(host=host,near=near.tolist(),slope=float(d[1]/d[0]),radius_mm=min(7.,h*.07),root=root.tolist());row['status']='partial-burial-at-existing-ground';plans.append(row);continue
  rate=float(np.interp(h,[24,45,75,130],[.12,.40,.78,.95]))
  if phase(o['id']+'/selective-contact',c['seed'])>rate or h<34:row['status']='selective-exposed-root';plans.append(row);continue
  side=1 if foot[0]>=root[0] else -1;reach=float(np.interp(h,[30,130],[4.5,11.]))*(.7+.6*phase(o['id']+'/root-reach',c['seed']));at=line.project(Point(foot));tangent=np.array(line.interpolate(min(line.length,at+1)).coords[0])-np.array(line.interpolate(max(0,at-1)).coords[0]);direction=side if tangent[0]>=0 else -side;aa=float(np.clip(at+direction*reach,0,line.length));anchor=np.array(line.interpolate(aa).coords[0])
  if anchor[1]<foot[1]-.3:row['status']='exposed-root-no-downhill-anchor';plans.append(row);continue
  if (anchor[0]-foot[0])*side<1 or np.linalg.norm(anchor-foot)>17:row['status']='no-safe-outward-anchor';plans.append(row);continue
  t=np.linspace(0,1,31);c1=foot+[side*1.2,.45];c2=anchor-[side*min(3.,reach*.3),0.];p=(1-t)[:,None]**3*foot+3*((1-t)**2*t)[:,None]*c1+3*((1-t)*t*t)[:,None]*c2+t[:,None]**3*anchor
  if np.any((p[:,0]-foot[0])*side<-.2):row['status']='rejected-inward-contact';plans.append(row);continue
  ident='v09/contact/'+o['id'];L=LineString(p).length;peak=.40+.19*np.clip(h/130,0,1);w=peak*(.40+.60*np.sin(np.pi*(.12+.76*t))**.7)
  r=dict(id=ident,source_stroke_id=ident,source_arc_mm=[0.,L],xy_mm=p.tolist(),owner_id=ident,source_family='Soil',layer='soil-ink',grammar_part='integration-contact-support',origin_kind='v09-ground-integration',width_mm=float(w.mean()),width_profile_mm=w.tolist(),assumed_footprint_mm=float(w.max()),preview_opacity=.78,source_forward_profile_m=sample(fixed['base']['depth_m'],p).tolist(),physical_plotting_validated=False,grounding_tree_id=o['id'],support_references=[dict(source_id=trunk['id'],role='visible trunk endpoint',endpoint_index=end,xy_mm=foot.tolist()),dict(source_id=host['id'],role='existing visible A/Soil anchor',arc_mm=aa,xy_mm=anchor.tolist())],generation_rule='one selected asymmetric contact between actual visible foot and existing depth-compatible A/Soil');margin=w.max()/2+.55
  def gate(xy,arcs,rec):
   good=np.minimum.reduce([sample(global_clear,xy)-margin,sample(reserve_clear,xy)-margin,sample(fixed['retention'],xy)-.20,xy[:,0]-margin,600-margin-xy[:,0],898-margin-xy[:,1]]);qq=sample(fixed['base']['depth_m'],xy)
   for other in context['objects']:
    if other['id']==o['id'] or not intersects(LineString(p).bounds,other['bounds']):continue
    oq=np.interp(xy[:,0],np.arange(600)+.5,other['q_row']);good=np.minimum(good,np.where(qq>=oq-25,sample(other['body_distance'],xy)-margin,1e6))
   return good,['locked-reserves','depth-compatible-visible-ground','selected-foot-outward-contact']
  pieces,d=cut(r,gate,2.8,'v09-selective-ground-contact');sources.append(r);connected=[s for s in pieces if LineString(s['xy_mm']).distance(Point(foot))<.25 and LineString(s['xy_mm']).distance(Point(anchor))<.25]
  if connected:added+=connected;row.update(status='asymmetric-existing-surface-contact',new_ids=[s['id'] for s in connected],anchor_xy_mm=anchor.tolist())
  else:row['status']='contact-blocked-by-mist-or-body'
  plans.append(row)
 return plans,added,protected,burials,sources


def burial_gate(spec):
 root=np.array(spec['root']);near=np.array(spec['near']);slope=spec['slope'];radius=spec['radius_mm']
 def gate(xy,arc,rec):
  local=(np.linalg.norm(xy-root,axis=1)<radius)&(xy[:,1]>root[1]-radius);return np.where(local,near[1]+slope*(xy[:,0]-near[0])-xy[:,1],1e6),['selected-existing-ground-burial']
 return gate


def refine(control,context,fixed,c):
 ink0=control['ink'];ch0=control['channels'];trees=masks(context,ch0);ledger=[];plans,bridges,protected,burials,sources=root_plans(ink0,trees,context,fixed,c);print('ROOT_PLANS',Counter(p['status'] for p in plans),flush=True);fields,counts=hatch_fields(classify(ink0,ch0));ch={k:[] for k in CHANNELS};ink=[];roots={o['id']:o for o in trees};groups=defaultdict(list)
 for r in ink0:
  if '/root-contact-Soil' in r['owner_id']:groups[r['owner_id']].append(r)
 attached={r['grounding_tree_id'] for r in bridges};keepers={min(rows,key=lambda r:(LineString(r['xy_mm']).distance(Point(roots[owner.rsplit('/root-contact-Soil',1)[0]]['site']['xy_mm'])),r['id']))['id'] for owner,rows in groups.items() if owner.rsplit('/root-contact-Soil',1)[0] not in attached}
 def hatch(r,key):
  if r['id'] in protected or horizontal(r)<.70 or np.mean(np.array(r['xy_mm'])[:,1])<555:return [r],None
  p=resample(r['xy_mm'],.8);nearA=sample(fields['A_ink'],p)<3.3;ph=r.get('carrier_basis',r['source_stroke_id'])
  if key=='A_color':overlap=(sample(fields['C_color'],p)<2.7)|(sample(fields['Soil_ink'],p)<2.1)|(sample(fields['tree_ground_ink'],p)<2.1)|(sample(counts['A_color'],p,order=0)>=3);rate=.52 if r.get('cross_layer',0)>0 else .82
  elif key=='C_color':overlap=sample(fields['A_color'],p)<2.7;rate=.43
  elif key=='Soil_color':overlap=(sample(fields['A_color'],p)<2.1)|(sample(fields['C_color'],p)<2.1);rate=.48
  else:overlap=(sample(fields['A_color'],p)<2.4)|(sample(fields['C_color'],p)<2.4);rate=.52
  if np.mean(nearA&overlap)<.32 or phase(ph+'/v09-hatch-priority',c['seed'])<rate:return [r],None
  L=length(r);u=phase(r['id']+'/v09-unequal-release',c['seed']);a=L*(.10+.25*u);b=L*(.58+.24*u);return cut(r,lambda xy,arcs,rec:(np.minimum(arcs-a,b-arcs),['derived-near-parallel-layer-stack']),3.2 if 'palette_slot' in r else 2.8,'v09-selective-derived-hatch-release')
 for r in ink0:
  fam=r['source_family'];parts=[r];d=None
  if fam=='RSU':parts,d=cut(r,canopy_gate(trees,c,r),2.8,'v09-source-depth-canopy-separation')
  elif fam=='tree' and r['owner_id'] in burials and r.get('grammar_part')=='trunk-contour':parts,d=cut(r,burial_gate(burials[r['owner_id']]),2.8,'v09-partial-ground-burial')
  elif fam=='Soil':
   if '/root-contact-Soil' in r['owner_id'] and r['id'] not in keepers and r['id'] not in protected:parts=[];d=dict(source_id=r['id'],source_length_mm=length(r),kept_intervals_mm=[],removed_mm=length(r),adapter_reason='v09-remove-repeated-root-underlines')
   else:parts,d=hatch(r,'Soil_ink')
  if d:ledger.append(d)
  ink+=parts
 ink+=bridges
 for k,rows in ch0.items():
  for r in rows:
   parts=[r];d=None
   if k=='RSU':parts,d=cut(r,canopy_gate(trees,c,r),3.2,'v09-source-depth-canopy-separation')
   elif k=='trunk' and r['owner_id'] in burials:parts,d=cut(r,burial_gate(burials[r['owner_id']]),3.2,'v09-partial-ground-burial')
   elif k in ['A','C']:parts,d=hatch(r,k+'_color')
   elif k=='rock_soil' and r.get('color_kind')=='Soil':parts,d=hatch(r,'Soil_color')
   if d:ledger.append(d)
   ch[k]+=parts
 return dict(ink=ink,channels=ch,ledger=ledger,new_sources=sources,root_plans=plans,trees=trees,protected_support_ids=sorted(protected),burials=burials)


def metrics(rows):
 lower=[r for r in rows if horizontal(r)>=.70 and np.mean(np.array(r['xy_mm'])[:,1])>=555];return dict(paths=len(rows),length_mm=sum(map(length,rows)),horizontal_lower_paths=len(lower),horizontal_lower_length_mm=sum(map(length,lower)))


def canopy_evidence(control,result,out):
 trees=result['trees'];table=[];totals={}
 for label,case in [('before',control),('after',result)]:
  core=edge=front=0
  for r in case['ink']+case['channels']['RSU']:
   if r['source_family']!='RSU':continue
   line=LineString(r['xy_mm']);peers=[o for o in trees if intersects(line.bounds,o['bounds'])]
   if not peers:continue
   aa=np.linspace(0,line.length,max(2,int(np.ceil(line.length/.4))+1));p=np.array([line.interpolate(a).coords[0] for a in aa]);q=q_at(r,p,aa);n=np.gradient(p,axis=0);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-8);n=np.c_[-n[:,1],n[:,0]];w=max(r.get('width_profile_mm',[r.get('assumed_footprint_mm',r['width_mm'])]))
   for o in peers:
    delta=q-np.interp(p[:,0],np.arange(600)+.5,o['q_row']);occ=np.maximum.reduce([sample(o['combined_occupancy'],p),sample(o['combined_occupancy'],p+n*w/2),sample(o['combined_occupancy'],p-n*w/2)]);hit=(delta>25)&(occ>=.27);core+=int(hit.sum());edge+=int(((delta>25)&(occ>=.06)&(occ<.18)).sum());front+=int(((delta< -25)&(occ>=.27)).sum())
    if label=='before' and hit.any():table.append(dict(RSU_id=r['id'],native_tree_id=o['id'],RSU_q_mean_m=float(q.mean()),native_q_mean_m=float(np.mean(q-delta)),minimum_delta_q_m=float(delta.min()),maximum_delta_q_m=float(delta.max()),maximum_occupancy=float(occ.max()),core_samples=int(hit.sum())))
  totals[label]=dict(behind_dense_core_samples=core,behind_allowed_edge_samples=edge,nearer_RSU_dense_overlap_samples=front)
 table.sort(key=lambda x:(-x['core_samples'],x['RSU_id'],x['native_tree_id']))
 with (out/'canopy_source_depth_conflicts.csv').open('w') as f:
  if table:w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 evidence=dict(samples=totals,top_conflicts=table[:12],depth_provider='Original RSU source-q profiles versus native F2 contact sheets, bounded lateral depth; still 2.5D',sample_step_mm=.4,occupancy_footprint='center and +/- half receiving width');(out/'canopy_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');return evidence


def audit(control,result,fixed,c,out):
 oldink=control['ink'];newink=result['ink'];oldcol=sum(control['channels'].values(),[]);newcol=sum(result['channels'].values(),[]);oldidx={r['id']:r for r in oldcol};oldinkidx={r['id']:r for r in oldink};changed=[r for r in newink+newcol if r.get('integration_parent_id') or r['id'].startswith('v09/contact/')];lineage=source_audit(changed,oldink+oldcol+result['new_sources']);exact={k:digest([r for r in oldink if r['source_family']==k])==digest([r for r in newink if r['source_family']==k]) for k in ['A','B','D','rock']}
 oldrs=[r for r in oldink+oldcol if r['source_family']=='RSU'];newrs=[r for r in newink+newcol if r['source_family']=='RSU'];rs0=coverage(oldrs);rs1=coverage(newrs);ratio=len(rs0&rs1)/len(rs0);lr=sum(map(length,newrs))/sum(map(length,oldrs))
 def vegetation(rows):return [r for r in rows if r['source_family']=='RSU' or (r['source_family']=='tree' and r.get('grammar_part')=='foliage-field') or r.get('color_kind')=='vegetation']
 vg0=coverage(vegetation(oldink+oldcol));vg1=coverage(vegetation(newink+newcol));vr=len(vg0&vg1)/len(vg0);hashes={k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in dict(xyz=fixed['base']['xyz'],depth_m=fixed['base']['depth_m'],occupied=fixed['base']['occupied'],retention=fixed['retention']).items()};original=json.loads((ROOT/'outputs/spring-integration-v08/record.json').read_text())['field_sha256'];canopy=canopy_evidence(control,result,out)
 endpoint_errors=[];omission=0;reserve=burn(unary_union([Polygon(x['vertices_mm']) for x in c['corridors']]));contacts=[r for r in newink if r.get('grounding_tree_id')]
 for r in contacts:
  for ref in r['support_references']:pt=Point(ref['xy_mm']);endpoint_errors.extend([LineString(r['xy_mm']).distance(pt),LineString(oldinkidx[ref['source_id']]['xy_mm']).distance(pt)])
  p=resample(r['xy_mm'],.25);omission+=int(((sample(fixed['refined']['global_retention'],p)<=0)|(sample(reserve.astype(float),p,order=0)>.5)).sum())
 checks=dict(**lineage,unchanged_F2_field_hashes=hashes==original,exact_control_terrain_and_rock=exact,unique_ids=len({r['id'] for r in newink+newcol})==len(newink+newcol),color_minimum_3_2=all(length(r)>=3.2-1e-7 for r in newcol),new_ink_minimum_2_8=all(length(r)>=2.8-1e-7 for r in changed if 'palette_slot' not in r),all_vegetation_12mm_grid_coverage_ratio=vr,RSU_12mm_grid_coverage_ratio=ratio,RSU_length_ratio=lr,source_palette_preserved=all(r['palette_slot']==oldidx[r.get('integration_parent_id',r['id'])]['palette_slot'] for r in newcol),foreground_canopy_color_exact=digest(control['channels']['gestures'])==digest(result['channels']['gestures']),native_foliage_ink_exact=digest([r for r in oldink if r.get('grammar_part')=='foliage-field'])==digest([r for r in newink if r.get('grammar_part')=='foliage-field']),maximum_contact_endpoint_error_mm=max(endpoint_errors,default=0.),new_contacts_in_protected_whitespace_samples=omission,protected_supports_exact=all(oldinkidx[k] in newink for k in result['protected_support_ids']),behind_dense_canopy_samples_before=canopy['samples']['before']['behind_dense_core_samples'],behind_dense_canopy_samples_after=canopy['samples']['after']['behind_dense_core_samples'],selective_canopy_edge_samples_after=canopy['samples']['after']['behind_allowed_edge_samples'],published=False,machine_changes=False)
 cats0=classify(oldink,control['channels']);cats1=classify(newink,result['channels']);zones={}
 for z in c['zones']:
  aa=[r for r in oldrs if (r.get('zone_id') or r.get('guide_source_id','').split('/')[-1])==z['id']];bb=[r for r in newrs if (r.get('zone_id') or r.get('guide_source_id','').split('/')[-1])==z['id']];a=coverage(aa);b=coverage(bb);zones[z['id']]=dict(before=metrics(aa),after=metrics(bb),grid_coverage_ratio=len(a&b)/len(a) if a else 1.)
 record=dict(study=c['study'],parent_commit=c['parent_commit'],field_sha256=hashes,validation=checks,hatch_provenance={k:dict(before=metrics(cats0[k]),after=metrics(cats1[k])) for k in cats0},RSU_zones=zones,root_status=dict(Counter(p['status'] for p in result['root_plans'])),root_plans=result['root_plans'],protected_support_ids=result['protected_support_ids'],removed_by_reason=dict(Counter(d['adapter_reason'] for d in result['ledger'] if d.get('removed_mm',0)>1e-8)),limitations=['Native source-depth sheets are 2.5D, not full 3D crown order.','Some roots stay exposed or blocked by existing mist/bodies.','The A ink horizontal rhythm is intentionally unchanged.','Visual review only; no backend checkpoint, publication or production approval.'])
 (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');(out/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
 assert checks['unchanged_F2_field_hashes'] and all(exact.values()) and checks['unique_ids'] and checks['source_palette_preserved']
 assert checks['foreground_canopy_color_exact'] and checks['native_foliage_ink_exact'] and checks['protected_supports_exact']
 assert not lineage['missing_source_ids'] and not lineage['profile_errors'] and lineage['maximum_source_arc_error_mm']<1e-6
 assert checks['color_minimum_3_2'] and checks['new_ink_minimum_2_8'] and checks['maximum_contact_endpoint_error_mm']<.25 and omission==0
 assert vr>=.98 and ratio>=.92 and lr>=.84 and checks['behind_dense_canopy_samples_after']==0 and checks['selective_canopy_edge_samples_after']>0,checks
 return record


def save(out,control,result,c,fixed):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 for i,case in enumerate([control,result]):
  for k,rows in [('ink',case['ink']),('color',sum(case['channels'].values(),[]))]+[('channel_'+k,v) for k,v in case['channels'].items()]+[('source_'+k,v) for k,v in classify(case['ink'],case['channels']).items()]:write_gz(out/f'case{i}_{k}.json.gz',dict(continuous_mm=[600,900],strokes=rows))
 write_gz(out/'local_source_ledger.json.gz',dict(parent_visible_ink=control['ink'],parent_visible_color=sum(control['channels'].values(),[]),new_contact_sources=result['new_sources'],decisions=result['ledger']));(out/'config.json').write_text(json.dumps(c,indent=2)+'\n');return audit(control,result,fixed,c,out)


def export_inputs(context,fixed,directory):
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);arrays={};meta=[]
 for i,o in enumerate(context['objects']):
  x0,y0,x1,y1=o['bounds'];x0=max(0,int(np.floor(x0))-4);y0=max(0,int(np.floor(y0))-4);x1=min(600,int(np.ceil(x1))+4);y1=min(900,int(np.ceil(y1))+4);key=f'o{i:03d}';item={k:v for k,v in o.items() if k not in ['q_row','body_distance','occupancy']};item.update(array_key=key,roi=[x0,y0,x1,y1]);meta.append(item);arrays[key+'_q']=o['q_row'];arrays[key+'_body']=o['body_distance'][y0:y1,x0:x1]
  if o['kind']=='tree':arrays[key+'_occupancy']=o['occupancy'][y0:y1,x0:x1]
 arrays.update(f_xyz=fixed['base']['xyz'],f_depth=fixed['base']['depth_m'],f_occupied=fixed['base']['occupied'],f_retention=fixed['retention'],f_global=fixed['refined']['global_retention']);np.savez_compressed(directory/'fields.npz',**arrays);(directory/'objects.json').write_text(json.dumps(meta,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else x)+'\n')


def load_inputs(directory):
 p=Path(directory);meta=json.loads((p/'objects.json').read_text());objects=[]
 with np.load(p/'fields.npz',allow_pickle=False) as data:
  for item in meta:
   o={k:v for k,v in item.items() if k not in ['array_key','roi']};key=item['array_key'];x0,y0,x1,y1=item['roi'];o['q_row']=data[key+'_q'];o['body_distance']=np.full((900,600),20.,np.float32);o['body_distance'][y0:y1,x0:x1]=data[key+'_body']
   if o['kind']=='tree':o['occupancy']=np.zeros((900,600),np.float32);o['occupancy'][y0:y1,x0:x1]=data[key+'_occupancy']
   objects.append(o)
  f=dict(base=dict(xyz=data['f_xyz'],depth_m=data['f_depth'],occupied=data['f_occupied']),retention=data['f_retention'],refined=dict(global_retention=data['f_global']))
 return dict(objects=objects),f


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',required=True);p.add_argument('--control',default='outputs/spring-integration-v08');p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
 if out.exists():raise FileExistsError('Use a fresh output directory')
 context,fixed=load_inputs(a.inputs);c=json.load(open(ROOT/'configs/scenes/seoul_spring_integration_v09.json'));control=load_control(a.control);result=refine(control,context,fixed,c);save(out,control,result,c,fixed);print('V09_REGENERATED',flush=True)
if __name__=='__main__':main()
