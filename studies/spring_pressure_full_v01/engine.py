#!/usr/bin/env python3
"""Painterly pressure-intent engine; frozen Spring v13 is read-only.
No machine export, canonical edits, geometry generation or hardware mapping.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,base64,csv,gzip,hashlib,html,io,json,shutil,subprocess,sys
import numpy as np
from scipy.ndimage import distance_transform_edt,gaussian_filter1d,map_coordinates
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from PIL import Image

PIN='67ba146b1213644d40bc9dabed9d52024d2bbe58'
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
C=json.loads((HERE/'config.json').read_text())
CMAP='viridis';NORM=Normalize(0,1)

def atomic_savefig(fig,path,**kwargs):
 path=Path(path);temporary=path.with_name(path.stem+'.rendering.png');fig.savefig(temporary,**kwargs)
 with Image.open(temporary) as image:image.verify()
 temporary.replace(path)

def read(p):
 return json.loads((gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()))
def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def hobj(o):return hashlib.sha256(canonical(o)).hexdigest()
def write(p,o):p.write_bytes(canonical(o)+b'\n')
def arc(p):return np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
def at(r,n=9):
 p=np.asarray(r['xy_mm']);a=arc(p);u=np.linspace(0,a[-1],n);return np.c_[np.interp(u,a,p[:,0]),np.interp(u,a,p[:,1])]
def interp(v,a,b):return np.interp(b,a,v)
def smooth(v,a,mm=1.2):
 if len(v)<3 or a[-1]<1e-9:return np.asarray(v)
 u=np.linspace(0,a[-1],max(3,int(np.ceil(a[-1]/.35))+1));v0=np.interp(u,a,v);vv=gaussian_filter1d(v0,mm/max(u[1]-u[0],1e-9),mode='nearest');return np.interp(a,u,vv)
def resample(r,step=2.):return at(r,max(2,int(np.ceil(arc(np.asarray(r['xy_mm']))[-1]/step))+1))
def family(r):
 f=r['source_family'];k=r.get('color_kind');g=r.get('grammar_part','')
 if f in ['A','B','D','rock','Soil']:return f
 if f=='A-derived':return 'A-color'
 if f=='C-derived':return 'C'
 if k=='rock':return 'rock'
 if k=='Soil':return 'Soil'
 if f=='RSU':return 'mid-far-vegetation'
 if g=='trunk-contour' or k=='trunk':return 'trunk'
 # In the preserved tree_pattern/tree_plot_scale generators, axis is the
 # main stem and its arm-* children are primary branches; twigs are children of arms.
 if g=='branch-contour' and (r.get('parent_component_key') in ['trunk','main-trunk'] or (r.get('parent_component_key')=='axis' and r.get('component_key','').startswith('arm-'))):return 'trunk'
 return 'branch-foliage'
def vegetation(r):return family(r) in ['branch-foliage','mid-far-vegetation'] and (r.get('grammar_part') not in ['branch-contour','twig','bark-grain'])
def sourceq(r,p,terrain_q):
 a=arc(np.asarray(r['xy_mm']));b=arc(p)
 if 'source_forward_profile_m' in r:return np.interp(b/max(b[-1],1e-9)*a[-1],a,r['source_forward_profile_m'])
 return np.full(len(p),r.get('source_object_depth_m',r.get('source_forward_m',np.nan))) if ('source_object_depth_m' in r or 'source_forward_m' in r) else terrain_q

class Context:
 def __init__(self,rows,snap):
  self.rows=rows;self.idx={r['id']:r for r in rows}
  m=read(snap/'source/fields_manifest.json');parts=[]
  for p in m['parts']:
   f=snap/'source'/p['path'];assert sha(f)==p['sha256'];parts.append(f.read_bytes())
  payload=b''.join(parts);assert hashlib.sha256(payload).hexdigest()==m['file_sha256'];self.field_sha=m['file_sha256']
  z=np.load(io.BytesIO(payload));self.xyz=z['f_xyz'];self.q=z['f_depth'];self.occupied=z['f_occupied'];self.ret=z['f_retention'];self.glob=z['f_global'];self.objects=read(snap/'source/objects.json')
  self.valid=self.occupied&(self.q>0)&np.isfinite(self.xyz).all(axis=2)
  self.dist,self.nearest=distance_transform_edt(~self.valid,return_indices=True)
  # Source-world point cloud, not screen-height or display darkness.
  yy,xx=np.mgrid[0:900:3,0:600:3];ok=self.valid[yy,xx];self.cloud=self.xyz[yy[ok],xx[ok]];self.cloudq=self.q[yy[ok],xx[ok]];self.tree=cKDTree(self.cloud[:,:2])
  self.D=[r for r in rows if r['source_family']=='D'];self.cohorts={};self.dxyz=[];self.dq=[];self.dlabel=[]
  for r in self.D:
   p=resample(r,1.5);xyz,q,valid,attachment=self.surface(p);label='events-'+','.join(map(str,r['source_event']))
   self.cohorts.setdefault(label,[]).extend(xyz[valid].tolist());self.dxyz.extend(xyz[valid]);self.dq.extend(q[valid]);self.dlabel.extend([label]*int(valid.sum()))
  self.dxyz=np.asarray(self.dxyz);self.dq=np.asarray(self.dq);self.dlabel=np.asarray(self.dlabel);self.dtree=cKDTree(self.dxyz[:,:2]);self.stats={}
  for label,points in self.cohorts.items():
   points=np.asarray(points);center=np.median(points,axis=0);ids=self.tree.query_ball_point(center[:2],650.);zz=self.cloud[ids,2] if ids else points[:,2]
   lo,hi=np.percentile(zz,[10,95]);peak=float(np.percentile(points[:,2],95));prom=max(0.,peak-lo)
   self.stats[label]=dict(center_xyz_m=center.tolist(),source_elevation_p95_m=peak,local_prominence_proxy_m=prom,local_z10_m=float(lo),local_z95_m=float(max(hi,peak)),stroke_ids=[r['id'] for r in self.D if 'events-'+','.join(map(str,r['source_event']))==label],status='original D event cohort; estimated mountain neighborhood, not original mountain identity')
  height=np.array([v['source_elevation_p95_m'] for v in self.stats.values()]);prom=np.array([v['local_prominence_proxy_m'] for v in self.stats.values()]);hr=max(np.ptp(height),1);pr=max(np.ptp(prom),1)
  for s in self.stats.values():s['between_mass_rank']=float(.65*(s['source_elevation_p95_m']-height.min())/hr+.35*(s['local_prominence_proxy_m']-prom.min())/pr)
  # Independent visible-stroke length samples. Exclude own stroke at query time.
  vp=[];vq=[];vi=[];vl=[];gp=[];gq=[];gi=[];gl=[]
  for i,r in enumerate(rows):
   if not vegetation(r) and family(r) not in ['A','A-color','C','Soil']:continue
   p=resample(r,2.);_,qt,_,_=self.surface(p);q=sourceq(r,p,qt);weight=arc(p)[-1]/len(p)
   dest=(vp,vq,vi,vl) if vegetation(r) else (gp,gq,gi,gl)
   dest[0].extend(p);dest[1].extend(q);dest[2].extend([i]*len(p));dest[3].extend([weight]*len(p))
  self.vtree=cKDTree(vp);self.vq=np.asarray(vq);self.vi=np.asarray(vi);self.vl=np.asarray(vl)
  self.gtree=cKDTree(gp);self.gq=np.asarray(gq);self.gi=np.asarray(gi);self.gl=np.asarray(gl);self.rownum={r['id']:i for i,r in enumerate(rows)}
  self.rawz=z
 def surface(self,p):
  p=np.asarray(p);ij=np.clip(np.floor(p).astype(int),[0,0],[599,899]);y,x=self.nearest[:,ij[:,1],ij[:,0]];distance=np.linalg.norm(np.c_[x+.5,y+.5]-p,axis=1)
  return self.xyz[y,x],self.q[y,x],distance<=C['maximum_ground_attachment_mm'],distance
 def fields(self,p):
  xy=np.asarray(p);ij=np.c_[xy[:,1]-.5,xy[:,0]-.5].T
  return np.clip(map_coordinates(self.ret,ij,order=1,mode='nearest'),0,1),np.clip(map_coordinates(self.glob,ij,order=1,mode='nearest'),0,1)
 def terrain(self,p):
  xyz,q,valid,attachment=self.surface(p);dd,nn=self.tree.query(xyz[:,:2],k=C['source_patch_neighbors']);nb=self.cloud[nn];nq=self.cloudq[nn]
  # Remove other depth sheets from local plane/TPI estimates.
  ok=np.abs(nq-q[:,None])<np.maximum(180.,q[:,None]*.12);w=np.exp(-.5*(dd/np.maximum(dd[:,-1:],20))**2)*ok
  meanz=(nb[:,:,2]*w).sum(axis=1)/np.maximum(w.sum(axis=1),1e-9)
  tpi=xyz[:,2]-meanz;slope=[]
  for i in range(len(p)):
   d=nb[i,:,:2]-xyz[i,:2];A=np.c_[d,np.ones(len(d))];ww=w[i];coef=np.linalg.lstsq(A*ww[:,None]**.5,(nb[i,:,2]-xyz[i,2])*ww**.5,rcond=None)[0];slope.append(np.arctan(np.linalg.norm(coef[:2]))*180/np.pi)
  slope=np.asarray(slope);peak=np.clip(tpi/12,0,1)*valid;valley=np.clip(-tpi/10,0,1)*valid
  _,di=self.dtree.query(xyz[:,:2]);labels=self.dlabel[di];D=np.zeros(len(p))
  for i in range(len(p)):
   ids=self.dtree.query_ball_point(xyz[i,:2],C['D_source_distance_sigma_m']*3)
   compatible=[j for j in ids if abs(self.dq[j]-q[i])<=C['D_same_depth_tolerance_m'] and self.dlabel[j]==labels[i]]
   if compatible and valid[i]:
    d=np.linalg.norm((self.dxyz[compatible]-xyz[i])/np.array([180.,180.,100.]),axis=1);D[i]=np.exp(-.5*d.min()**2)
  ret,glob=self.fields(p);mist=1-np.minimum(ret,glob)
  structval=valley*np.clip(slope/35,0,1)*(1-mist);mistval=valley*mist
  return dict(xyz=xyz,q=q,valid=valid,attachment=attachment,peak=peak,valley=valley,slope=slope,mist=mist,structural_valley=structval,mist_valley=mistval,D=D,labels=labels)
 def crowd(self,r,p,q,ground=False):
  tree,qv,ids,lens=(self.gtree,self.gq,self.gi,self.gl) if ground else (self.vtree,self.vq,self.vi,self.vl)
  radius=5. if ground else C['crowding_radius_mm'];found=tree.query_ball_point(p,radius);result=[];own=self.rownum[r['id']]
  for j,near in enumerate(found):
   ns=np.asarray(near,int);good=(ids[ns]!=own)&(np.abs(qv[ns]-q[j])<max(C['minimum_crowding_depth_gate_m'],q[j]*C['crowding_relative_depth_gate']))
   # This is a length-density proxy; neither pigment concentration nor botanical observation.
   density=lens[ns[good]].sum()/(np.pi*radius**2);result.append(np.clip((density-.12)/.65,0,1))
  return np.asarray(result)


def propose(r,ctx):
 p=np.asarray(r['xy_mm']);a=arc(p);t=a/a[-1];f=family(r);base=C['bases'][f];n=len(p)
 w=np.asarray(r.get('width_profile_mm',[r.get('width_mm',.5)]*n),float);has='width_profile_mm' in r
 # Relative width, bounded once. Display alpha/intensity is never a pressure input.
 wd=np.clip(C['width_log2_gain']*np.log2(np.maximum(w,.0001)/max(np.median(w),.0001)),-C['width_delta_cap'],C['width_delta_cap']) if has else np.zeros(n)
 wd=smooth(wd,a,C['smoothing_mm']);widthonly=np.clip(base+wd,*C['limits'][f]);zero=np.zeros(n);mods={};uncertainty=[];host=None
 terr=None;qp=None
 if f in ['A','B','D','A-color','C']:
  evalp=p
  if f=='A-color':
   refs=r.get('support_references',[]);host=next((ctx.idx.get(ref.get('visible_fragment_id',ref.get('source_id'))) for ref in refs if ctx.idx.get(ref.get('visible_fragment_id',ref.get('source_id')))),None)
   if host is not None:
    hp=np.asarray(host['xy_mm']);ha=arc(hp);_,near=cKDTree(hp).query(p);evalp=hp[near];uncertainty.append('A host linkage exact; nearest host vertex is an estimated arc correspondence')
   else:uncertainty.append('No resolved exact A host: pressure uses attached terrain proxy')
  terr=ctx.terrain(evalp);qp=terr['q'];scale=C['color_context_gain'] if f in ['A-color','C'] else 1.
  if f=='D':
   label='events-'+','.join(map(str,r['source_event']));s=ctx.stats[label]
   mods['between_mass_estimate']=np.full(n,C['D_between_mass_gain']*(s['between_mass_rank']-.5))
   local=np.clip((terr['xyz'][:,2]-s['local_z10_m'])/max(s['local_z95_m']-s['local_z10_m'],1),0,1)
   mods['within_mass_peak_estimate']=C['D_within_mass_gain']*(local-.5)*terr['valid'];mods['mist_release']=-.055*terr['mist'];uncertainty.append('D event cohort is not a proven mountain mass; both hierarchy terms are estimated')
  else:
   mods['local_peak_estimate']=C['terrain_peak_gain']*scale*terr['peak'];mods['source_slope_estimate']=C['terrain_slope_gain']*scale*np.clip(terr['slope']/45,0,1)*terr['valid']
   mods['structural_valley_estimate']=C['structural_valley_gain']*scale*terr['structural_valley'];mods['mist_release']=-C['mist_release_gain']*scale*terr['mist']
   if f in ['A','A-color']:mods['source_depth_compatible_D']=C['A_D_gain']*scale*terr['D']
   if f=='C':mods['ground_flow_crowding']=-.035*ctx.crowd(r,p,sourceq(r,p,qp),True)
  if not terr['valid'].all():uncertainty.append('Terrain attachment farther than 6 mm; peak/slope/valley/D bonuses disabled there')
 elif f=='rock':
  xyz,q,v,d=ctx.surface(p);qp=sourceq(r,p,q);ret,glob=ctx.fields(p)
  envelope=C['rock_entry_gain']*np.exp(-t/.16)+C['rock_release_gain']*(1-np.exp(-t/.28))+C['rock_terminal_gain']*np.exp(-.5*((t-.90)/.065)**2)
  mods['rock_progression']=envelope*(C['sub_1mm_envelope_gain'] if a[-1]<1 else min(1.,a[-1]/4))
  mods['mist_release']=-.035*(1-np.minimum(ret,glob))
 elif f=='Soil':
  _,q,_,_=ctx.surface(p);qp=sourceq(r,p,q);ret,glob=ctx.fields(p)
  mods['foreground_depth']=.045*(1-np.clip((qp-100)/1800,0,1));mods['overlapping_ground_hatch']=-.065*ctx.crowd(r,p,qp,True);mods['mist_release']=-.055*(1-np.minimum(ret,glob))
 else:
  _,q,_,_=ctx.surface(p);qp=sourceq(r,p,q);ret,glob=ctx.fields(p)
  # No isolation bonus. Only crowding subtracts from the family base.
  cr=ctx.crowd(r,p,qp);mods['canopy_crowding']=-C['crowding_maximum_reduction']*cr
  mods['depth_release']=-.035*np.clip((qp-500)/2400,0,1)
  mods['mist_release']=-.04*(1-np.minimum(ret,glob))
  if f in ['branch-foliage','mid-far-vegetation']:
   mods['growth_progression']=(C['branch_entry_gain']*(1-t)-C['branch_exit_release']*t)*(C['sub_1mm_envelope_gain'] if a[-1]<1 else min(1.,a[-1]/4))
  elif f=='trunk':mods['trunk_progression']=.025*(1-t)-(.045 if r.get('grammar_part')=='branch-contour' else .02)*t
  if 'source_forward_profile_m' not in r and 'source_object_depth_m' not in r:uncertainty.append('No explicit object depth; underlying terrain depth proxy used')
 # Resolve every component on arclength, then constrain the combined context once.
 mods={k:smooth(v,a,C['smoothing_mm']) for k,v in mods.items()}
 # Width is the primary progression signal. Damp only positively correlated
 # within-stroke contextual oscillation; retain its mean hierarchy/concentration.
 overlap_guard=np.zeros(n)
 if np.std(wd)>.02:
  wc=wd-wd.mean()
  for v in mods.values():
   vc=v-v.mean();den=np.linalg.norm(wc)*np.linalg.norm(vc)
   correlation=max(0.,float(wc@vc/den)) if den>1e-12 else 0.
   overlap_guard-=.5*correlation*vc
 if np.any(np.abs(overlap_guard)>1e-12):mods['width_context_overlap_guard']=overlap_guard
 raw=sum(mods.values(),np.zeros(n));bounded=np.clip(raw,-C['context_budget'],C['context_budget']);budget_delta=bounded-raw
 if np.any(np.abs(budget_delta)>1e-12):mods['context_budget_limit']=budget_delta
 proposal=np.clip(base+wd+bounded,*C['limits'][f]);mods['family_range_limit']=proposal-(base+wd+bounded)
 return dict(stroke_id=r['id'],family=f,pictorial_role=r.get('grammar_part',r.get('color_kind',r['source_family'])),medium='color' if 'palette_slot' in r else 'ink',color_slot=r.get('palette_slot','INK'),sequence=ctx.rownum[r['id']],source_record_sha256=hobj(r),xy_sha256=hobj(r['xy_mm']),vertex_count=n,length_mm=float(a[-1]),arclength_mm=a.tolist(),base=base,width_source='original width_profile_mm' if has else 'constant width_mm only; no expressive width variation',original_width_mm=w.tolist(),width_contribution=wd.tolist(),width_only_pressure=widthonly.tolist(),modifier_contributions={k:v.tolist() for k,v in mods.items()},proposed_pressure=proposal.tolist(),original_pressure=r.get('pressure_intent_samples'),original_pressure_status='historical_experimental_reference_only_new_intent_recomputed' if 'pressure_intent_samples' in r else 'absent; machine 0.5 placeholder ignored',context=dict(source_depth_m=qp.tolist(),mist_release_factor=(terr['mist'].tolist() if terr is not None else (1-np.minimum(*ctx.fields(p))).tolist()),D_strength=terr['D'].tolist() if terr is not None else None,structural_valley_proxy=terr['structural_valley'].tolist() if terr is not None else None,mist_valley_proxy=terr['mist_valley'].tolist() if terr is not None else None,source_attachment_mm=terr['attachment'].tolist() if terr is not None else None,A_host_id=host['id'] if host is not None else None),uncertainties=uncertainty,status='provisional full-generation artistic proposal; not calibrated or approved for hardware')

def draw_pressure(ax,r,values,width=2.3):
 p=np.asarray(r['xy_mm']);seg=np.stack([p[:-1],p[1:]],axis=1);lc=LineCollection(seg,array=(np.asarray(values[:-1])+values[1:])/2,cmap=CMAP,norm=NORM,linewidths=width,capstyle='round',zorder=3);ax.add_collection(lc)
 ax.scatter(*p[0],s=17,marker='o',facecolor='white',edgecolor='#303030',zorder=4);ax.scatter(*p[-1],s=18,marker='s',color='#303030',zorder=4)
 return lc

BACKGROUND_CACHE={}
def background(ax,rows,bounds=None):
 key=id(rows)
 if key not in BACKGROUND_CACHE:
  pp=[np.asarray(r['xy_mm']) for r in rows];bb=np.array([np.r_[p.min(axis=0),p.max(axis=0)] for p in pp]);BACKGROUND_CACHE[key]=(pp,bb)
 pp,bb=BACKGROUND_CACHE[key];paths=pp
 if bounds:
  x0,y0,x1,y1=bounds;ids=np.flatnonzero((bb[:,0]<=x1)&(bb[:,2]>=x0)&(bb[:,1]<=y1)&(bb[:,3]>=y0));paths=[pp[i] for i in ids]
 ax.add_collection(LineCollection(paths,colors='#d9dde0',linewidths=.35,zorder=1))

def crop_fig(out,ctx,samples,group,title):
 ss=[s for s in samples if s['group']==group];rr=[ctx.idx[s['stroke_id']] for s in ss];p=np.concatenate([r['xy_mm'] for r in rr]);x0,y0=p.min(axis=0);x1,y1=p.max(axis=0);margin=max(5,min(18,max(x1-x0,y1-y0)*.14));bounds=[max(0,x0-margin),max(0,y0-margin),min(600,x1+margin),min(900,y1+margin)]
 # Widely separated samples are shown as separate rows with matched per-row scales.
 fig,axes=plt.subplots(len(ss),3,figsize=(13,3.25*len(ss)),squeeze=False)
 for row,(s,r) in enumerate(zip(ss,rr)):
  p=np.asarray(r['xy_mm']);lo=p.min(axis=0);hi=p.max(axis=0);span=np.maximum(hi-lo,6);margin=max(3,min(10,span.max()*.12));b=[max(0,lo[0]-margin),max(0,lo[1]-margin),min(600,hi[0]+margin),min(900,hi[1]+margin)]
  # Same extent in the width-only and contextual diagnostics; fixed color scale for every crop.
  for col in [0,1]:
   ax=axes[row,col];background(ax,ctx.rows,b);values=s['width_only_pressure'] if col==0 else s['proposed_pressure'];lc=draw_pressure(ax,r,np.array(values),3)
   ax.set(xlim=(b[0],b[2]),ylim=(b[3],b[1]),aspect='equal');ax.tick_params(labelsize=7);ax.set_title(f"{s['sample_id']} / {'base + width' if col==0 else '+ contextual modifiers'}",fontsize=10);ax.set_xlabel('Artwork X (mm)',fontsize=8);ax.set_ylabel('Artwork Y (mm)',fontsize=8)
  ax=axes[row,2];t=np.asarray(s['arclength_mm'])/s['length_mm'];ax.plot(t,s['width_only_pressure'],color='#5d94bc',linestyle=':',label='Base + width');ax.plot(t,s['proposed_pressure'],color='#ca472a',lw=1.8,label='Context proposal')
  if s['original_pressure'] is not None:ax.plot(t,s['original_pressure'],color='#242424',ls='--',lw=1.5,label='Historical experiment (reference)')
  ax.axhline(s['base'],color='#bbb',lw=.6);ax.set(xlim=(0,1),ylim=(0,1),xlabel='Original vertex direction / normalized arclength',ylabel='Normalized pressure');ax.tick_params(labelsize=7);ax.grid(alpha=.18);ax2=ax.twinx();ax2.plot(t,s['original_width_mm'],color='#27936b',alpha=.55,lw=1,label='Original width (mm)');ax2.set_ylabel('Original width (mm)',color='#27936b',fontsize=8);ax2.tick_params(labelsize=7)
  ax.set_title(f"{s['family']} / {s.get('pictorial_role',s['family'])}\nL={s['length_mm']:.2f} mm · vertices={s['vertex_count']}",fontsize=9)
  if row==0:
   aa,bb=ax.get_legend_handles_labels();cc,dd=ax2.get_legend_handles_labels();ax.legend(aa+cc,bb+dd,fontsize=6,loc='lower center',framealpha=.9)
 fig.suptitle(title+'\nCircle = original first vertex; square = original final vertex. Pressure is color, never added artwork.',fontsize=12,y=1)
 fig.tight_layout(rect=(0,0,1,.97));atomic_savefig(fig,out/f'{group}.png',dpi=125,bbox_inches='tight');plt.close(fig)

def contributions(out,samples):
 with (out/'modifier_contributions.csv').open('w') as f:
  writer=csv.writer(f);writer.writerow(['sample_id','stroke_id','family','term','minimum','mean','maximum','status'])
  for s in samples:
   for k,v in [('base',[s['base']]),('width_derived_contribution',s['width_contribution']),*s['modifier_contributions'].items()]:writer.writerow([s['sample_id'],s['stroke_id'],s['family'],k,min(v),np.mean(v),max(v),'provisional study coefficient'])
 with (out/'samples.csv').open('w') as f:
  writer=csv.writer(f);writer.writerow(['sample_id','group','stroke_id','family','medium','slot','vertices','length_mm','proposed_min','proposed_mean','proposed_max','original_pressure_present'])
  for s in samples:writer.writerow([s['sample_id'],s['group'],s['stroke_id'],s['family'],s['medium'],s['color_slot'],s['vertex_count'],s['length_mm'],min(s['proposed_pressure']),np.mean(s['proposed_pressure']),max(s['proposed_pressure']),s['original_pressure'] is not None])

def context_overview(out,snap):
 m=read(snap/'source/fields_manifest.json');z=np.load(io.BytesIO(b''.join((snap/'source'/x['path']).read_bytes() for x in m['parts'])));occupied=z['f_occupied']&(z['f_depth']>0)
 fig,axes=plt.subplots(1,3,figsize=(13,8))
 for ax,field,title,cmap,vmax in zip(axes,[z['f_xyz'][:,:,2],z['f_depth'],1-np.minimum(z['f_retention'],z['f_global'])],['Preserved UTM elevation (m)','Preserved forward depth (m)','Preserved mist/release factor (0–1)'],['terrain','cividis','Blues'],[850,8000,1]):
  im=ax.imshow(np.where(occupied,field,np.nan),extent=(0,600,900,0),vmin=0,vmax=vmax,cmap=cmap);ax.set_title(title,fontsize=10);ax.set_xlabel('Artwork X (mm)');ax.set_ylabel('Artwork Y (mm)');fig.colorbar(im,ax=ax,fraction=.04,pad=.03)
 fig.suptitle('Actual preserved context fields / explanatory maps, not assigned pressure profiles',fontsize=12);fig.tight_layout();atomic_savefig(fig,out/'preserved_context_fields.png',dpi=140,bbox_inches='tight');plt.close(fig)

def audit(ctx,rows,snap):
 keys=['width_profile_mm','pressure_intent_samples','source_forward_profile_m','source_object_depth_m','source_forward_m','source_root_xyz_m','source_site','support_references','source_event','parent_component_key','source_root_id']
 result={}
 for f in C['bases']:
  rr=[r for r in rows if family(r)==f];result[f]=dict(count=len(rr),fields_present={k:sum(k in r for r in rr) for k in keys})
 return dict(baseline_commit=PIN,per_family=result,source_fields=dict(xyz_utm_m=list(ctx.xyz.shape),source_depth_m=list(ctx.q.shape),occupied=list(ctx.occupied.shape),retention=list(ctx.ret.shape),global_retention=list(ctx.glob.shape),object_2_5D_inventory_count=len(ctx.objects),fields_sha256=ctx.field_sha),available=['Original visible XY, IDs, vertex order, color slots, ordering, width profiles and 675 pressure records','Preserved F2 projected UTM XYZ including real elevation, forward-depth raster, occupancy, total/global retention','D original support event IDs and support_type, not mountain mass IDs','A-derived original support references, source-forward profiles; vegetation growth graph and object source depth','Original 2.5D canopy occupancy crops and q sheets for historical objects (not a complete current 3D tree model)'],estimated=['Nearest occupied F2 pixel attachment (maximum 6 mm), with uncertainty and invalid bonus suppression','Source-coordinate local plane slope and 48-neighbor elevation TPI; source-depth-gated, not screen Y','D support-event cohorts as candidate mountain neighborhoods; height/local relief ranks and local peak position','Valley semantic proxy: negative local TPI combined with slope and preserved mist retention; no authored valley labels','Current visible foliage line-length density with source-depth gate; not pigment density or biological canopy volume','A-color exact host ID where available, estimated nearest-vertex arc correspondence','Primary arm contours identified from original axis -> arm-* -> twig hierarchy, confirmed in tree_pattern.py and tree_plot_scale.py; primary arms use 0.63 and twigs/foliage use 0.45'],unavailable=['Original authoritative mountain mass IDs / complete source DEM derivative rasters in this compact field bundle','Original semantic structural-valley vs mist-valley labels','Full 3D canopy volume, brush bending, entry/exit contact surface normals and calibrated pressure/force/Z mapping','Original pressure for 14,276 strokes; offline 0.5 values are not artistic observations','Any proven exact identity with lost historical v13 source (visual equality was user verified)'])

def historical_audit(root):
 result=[]
 for folder,nb,terms in [('2026-03-17_geumgang','datascape_0317test.ipynb',['get_dynamic_z','pressure_factor','mist_intensity']),('2026-08-15_taebaek_yang','datascape_0815_Taebaek.ipynb',['get_z_pressure_ink','get_z_pressure_color','crowdedness']),('2026-08-20_taebaek_eum','datascape_0820_Taebaek.ipynb',['dummy_z','valley_slit_val','gold_tone'])]:
  base=root/'artworks'/folder;source=base/'original/source.py';manifest=read(base/'source_manifest.json');assert sha(source)==manifest['derived_source']['sha256'];item=dict(artwork=folder,reviewed_code=str(source.relative_to(root)),code_sha256=sha(source),original_notebook_available=(base/'original'/nb).exists(),terms_reviewed=terms,executed=False,hardware_parameters_reused=False)
  if item['original_notebook_available']:
   notebook=base/'original'/nb;assert sha(notebook)==manifest['original_notebook']['sha256'];doc=read(notebook);item['notebook_sha256']=sha(notebook);item['relevant_code_cell_indices_zero_based']=[i for i,c in enumerate(doc['cells']) if c['cell_type']=='code' and any(t in ''.join(c['source']) for t in terms)]
  else:item['limitation']='Original Yang ipynb absent from pinned repository; unchanged code-cell extraction reviewed instead.'
  result.append(item)
 return result
