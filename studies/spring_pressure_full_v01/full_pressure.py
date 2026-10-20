#!/usr/bin/env python3
"""Recompute all Spring v13 artistic pressure, separate from immutable vectors.
Historical experimental pressure is reference only, never a model input.
No physical force/Z conversion or machine motion is implemented.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,base64,csv,gzip,hashlib,html,io,json,shutil,subprocess,sys,time
import numpy as np
import engine as e
from scipy import __version__ as scipy_version
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from PIL import Image,__version__ as pillow_version

HERE=Path(__file__).resolve().parent;ROOT=e.ROOT;SNAP=ROOT/'artworks/spring_v13'
FAMILIES=list(e.C['bases']);BASE_FILES=['visible_ink.json.gz','visible_color.json.gz','palette.json','ordering.json','review/approved.png']
FLAGS={'flat_span':.01,'exact_flat_span':1e-6,'width_nonflat_relative_span':.10,'abrupt_delta':.08,'abrupt_max_segment_mm':1.,'large_adjacent_delta':.12,'high_gradient_per_mm':.10}

def save(p,obj):
 data=e.canonical(obj)+b'\n';p.write_bytes(gzip.compress(data,mtime=0) if p.suffix=='.gz' else data)

def load_baseline():
 # Study commits may descend from the pin; immutable source bytes are checked below.
 assert subprocess.call(['git','merge-base','--is-ancestor',e.PIN,'HEAD'],cwd=ROOT)==0
 manifest=e.read(SNAP/'MANIFEST_SHA256.json');assert all(e.sha(SNAP/k)==h for k,h in manifest.items())
 sys.path.insert(0,str(ROOT/'src'));from datascape.spring_checkpoint import load_snapshot,inspect_path
 raw,phases,palette=load_snapshot(SNAP);rows=[r for med,i,r in raw]
 assert len(rows)==14951 and len({r['id'] for r in rows})==14951
 for med,i,r in raw:inspect_path(r,med,palette)
 assert sum(len(r['xy_mm']) for r in rows)==240974
 return raw,rows,phases,palette,manifest

class CachedContext(e.Context):
 """Memoize point-local terrain calculations, without altering their arithmetic."""
 def __init__(self,rows,snap):super().__init__(rows,snap);self._point_cache={};self.cache_hits=0
 def terrain(self,p):
  p=np.asarray(p);keys=[tuple(v) for v in p];missing=list(dict.fromkeys(k for k in keys if k not in self._point_cache));self.cache_hits+=len(p)-len(missing)
  if missing:
   data=super().terrain(np.asarray(missing))
   for i,k in enumerate(missing):self._point_cache[k]={n:v[i].copy() if isinstance(v[i],np.ndarray) else v[i] for n,v in data.items()}
  first=self._point_cache[keys[0]]
  return {n:np.asarray([self._point_cache[k][n] for k in keys]) for n in first}

def metrics(r,s):
 p=np.asarray(s['proposed_pressure']);a=np.asarray(s['arclength_mm']);ds=np.diff(a);dp=np.abs(np.diff(p));lo,hi=e.C['limits'][s['family']];satlo=np.isclose(p,lo,atol=1e-10,rtol=0);sathi=np.isclose(p,hi,atol=1e-10,rtol=0);w=np.asarray(s['original_width_mm']);span=float(np.ptp(p));m=dict(stroke_id=r['id'],sequence=s['sequence'],family=s['family'],source_family=r['source_family'],role=s['pictorial_role'],medium=s['medium'],color_slot=s['color_slot'],vertex_count=len(p),length_mm=s['length_mm'],minimum=float(p.min()),maximum=float(p.max()),median=float(np.median(p)),mean=float(p.mean()),standard_deviation=float(p.std()),span=span,arclength_mean=float(np.sum((p[:-1]+p[1:])*.5*ds)/a[-1]),early_quarter_mean=float(np.interp(np.linspace(0,.25,21)*a[-1],a,p).mean()),late_quarter_mean=float(np.interp(np.linspace(.75,1,21)*a[-1],a,p).mean()),max_adjacent_delta=float(dp.max()),max_gradient_per_mm=float(np.max(dp/np.maximum(ds,1e-12))),abrupt_segments=int(np.sum((dp>FLAGS['abrupt_delta'])&(ds<=FLAGS['abrupt_max_segment_mm']))),large_adjacent_delta_segments=int(np.sum(dp>FLAGS['large_adjacent_delta'])),lower_bound_vertices=int(satlo.sum()),upper_bound_vertices=int(sathi.sum()),bound_fraction_vertices=float((satlo|sathi).mean()),bound_length_fraction=float(np.sum(ds*((satlo|sathi)[:-1].astype(float)+(satlo|sathi)[1:].astype(float))*.5)/a[-1]),family_clipped_vertices=int(np.sum(np.abs(s['modifier_contributions']['family_range_limit'])>1e-10)),context_budget_limited='context_budget_limit' in s['modifier_contributions'],width_context_overlap_guard='width_context_overlap_guard' in s['modifier_contributions'],width_profile_available='width_profile_mm' in r,width_relative_span=float(np.ptp(w)/max(np.median(w),1e-12)),historical_experimental_pressure_present='pressure_intent_samples' in r,original_pressure_authoritative=False,estimated_mean_source_depth_m=float(np.mean(s['context']['source_depth_m'])),A_host_id=s['context']['A_host_id'])
 m['flat_profile']=span<FLAGS['flat_span'];m['exact_flat_profile']=span<FLAGS['exact_flat_span'];m['flat_despite_nonflat_width']=bool(m['flat_profile'] and m['width_relative_span']>FLAGS['width_nonflat_relative_span'] and a[-1]>=2)
 m['flags']=';'.join(k for k,v in [('family_saturation',m['family_clipped_vertices']>0),('abrupt_short_segment',m['abrupt_segments']>0),('large_adjacent_delta',m['large_adjacent_delta_segments']>0),('high_gradient',m['max_gradient_per_mm']>FLAGS['high_gradient_per_mm']),('flat',m['flat_profile']),('flat_despite_width',m['flat_despite_nonflat_width'])] if v)
 return m

def write_csv(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def summarize(stats,sidecar,historical):
 out={};by={s['stroke_id']:s for s in sidecar}
 for fam in FAMILIES:
  rr=[r for r in stats if r['family']==fam];pooled=np.concatenate([by[r['stroke_id']]['pressure_intent_samples'] for r in rr]);med=np.array([r['median'] for r in rr]);spans=np.array([r['span'] for r in rr]);points=sum(r['vertex_count'] for r in rr)
  out[fam]=dict(strokes=len(rr),vertices=points,base=e.C['bases'][fam],allowed_range=e.C['limits'][fam],point_minimum=float(pooled.min()),point_maximum=float(pooled.max()),point_median=float(np.median(pooled)),stroke_median_median=float(np.median(med)),stroke_median_p05_p95=np.percentile(med,[5,95]).tolist(),within_stroke_span_min_median_p95_max=[float(spans.min()),float(np.median(spans)),float(np.percentile(spans,95)),float(spans.max())],saturated_strokes=sum(r['family_clipped_vertices']>0 for r in rr),saturated_vertices=sum(r['lower_bound_vertices']+r['upper_bound_vertices'] for r in rr),saturated_vertex_fraction=sum(r['lower_bound_vertices']+r['upper_bound_vertices'] for r in rr)/points,flat_strokes=sum(r['flat_profile'] for r in rr),exact_flat_strokes=sum(r['exact_flat_profile'] for r in rr),flat_despite_nonflat_width_strokes=sum(r['flat_despite_nonflat_width'] for r in rr),abrupt_short_segment_strokes=sum(r['abrupt_segments']>0 for r in rr),large_adjacent_delta_strokes=sum(r['large_adjacent_delta_segments']>0 for r in rr),high_gradient_strokes=sum(r['max_gradient_per_mm']>FLAGS['high_gradient_per_mm'] for r in rr))
 comparisons=[]
 for h in historical:
  new=np.asarray(by[h['stroke_id']]['pressure_intent_samples']);old=np.asarray(h['pressure_intent_samples']);comparisons.append(dict(stroke_id=h['stroke_id'],family=by[h['stroke_id']]['family'],vertices=len(old),historical_min=float(old.min()),historical_max=float(old.max()),historical_median=float(np.median(old)),historical_span=float(np.ptp(old)),new_min=float(new.min()),new_max=float(new.max()),new_median=float(np.median(new)),new_span=float(np.ptp(new)),mean_absolute_difference=float(np.mean(np.abs(new-old))),root_mean_squared_difference=float(np.sqrt(np.mean((new-old)**2))),exactly_equal=np.array_equal(new,old)))
 hs=np.array([r['historical_span'] for r in comparisons]);ns=np.array([r['new_span'] for r in comparisons]);summary=dict(strokes=len(comparisons),vertices=sum(r['vertices'] for r in comparisons),identical_profiles=sum(r['exactly_equal'] for r in comparisons),historical_span_min_median_p95_max=np.percentile(hs,[0,50,95,100]).tolist(),new_span_min_median_p95_max=np.percentile(ns,[0,50,95,100]).tolist(),historical_spans_over_0_8=int((hs>.8).sum()),new_spans_over_0_8=int((ns>.8).sum()),median_mean_absolute_difference=float(np.median([r['mean_absolute_difference'] for r in comparisons])),policy='All recomputed from new width/context rules; historical values are reference only.')
 return out,comparisons,summary

def generate(out):
 out.mkdir(parents=True,exist_ok=False);start=time.monotonic();raw,rows,phases,palette,manifest=load_baseline();baseline_hashes={k:e.sha(SNAP/k) for k in BASE_FILES};record_hash=e.hobj(rows);historic=[dict(stroke_id=r['id'],source_record_sha256=e.hobj(r),pressure_intent_samples=r['pressure_intent_samples']) for r in rows if 'pressure_intent_samples' in r];assert len(historic)==675
 print('Frozen source verified: 14951 strokes / 240974 vertices / 675 historical experiments',flush=True);ctx=CachedContext(rows,SNAP);print('Source-world context ready',flush=True)
 sidecar=[];decomposition=[];stats=[];historical_input_independence=0
 for sequence,r in enumerate(rows):
  s=e.propose(r,ctx);pp=np.asarray(s['proposed_pressure']);assert len(pp)==len(r['xy_mm']) and np.isfinite(pp).all() and ((pp>0)&(pp<1)).all();lo,hi=e.C['limits'][s['family']];assert np.all((pp>=lo-1e-12)&(pp<=hi+1e-12))
  reconstructed=s['base']+np.asarray(s['width_contribution'])+sum((np.asarray(v) for v in s['modifier_contributions'].values()),np.zeros(len(pp)));assert np.max(np.abs(reconstructed-pp))<1e-12
  if 'pressure_intent_samples' in r:
   alternative=dict(r);alternative.pop('pressure_intent_samples');assert e.propose(alternative,ctx)['proposed_pressure']==s['proposed_pressure'];historical_input_independence+=1
  phase=next(x for x in phases if x['start']<=sequence<x['start']+x['count'])
  sidecar.append(dict(stroke_id=r['id'],sequence=sequence,source_record_sha256=e.hobj(r),xy_sha256=e.hobj(r['xy_mm']),width_profile_sha256=e.hobj({k:r[k] for k in ['width_mm','width_profile_mm','expression','expressive_width_intent'] if k in r}),vertex_count=len(pp),medium=s['medium'],layer=r['layer'],family=s['family'],pictorial_role=s['pictorial_role'],color_slot=s['color_slot'],order_group=phase['order_group'],reorderable=False,reversible=False,pressure_intent_samples=s['proposed_pressure'],pressure_origin='new_painterly_pressure_intent_v01',source_pressure_status='historical_experimental_recomputed' if 'pressure_intent_samples' in r else 'no_historical_pressure_newly_computed',calibrated=False))
  decomposition.append(dict(stroke_id=r['id'],base=s['base'],width_contribution=s['width_contribution'],width_only_pressure=s['width_only_pressure'],modifier_contributions=s['modifier_contributions'],context=s['context'],uncertainties=s['uncertainties'],direction='unchanged canonical vertex order; existing growth role used where recorded; no geometric reversal'))
  stats.append(metrics(r,s))
  if (sequence+1)%500==0:print(f'Generated {sequence+1}/14951; unique terrain samples {len(ctx._point_cache)}; elapsed {time.monotonic()-start:.1f}s',flush=True)
 # Preserve all artistic records and protected source files, not only XY.
 assert e.hobj(rows)==record_hash and all(e.sha(SNAP/k)==h for k,h in manifest.items()) and baseline_hashes=={k:e.sha(SNAP/k) for k in BASE_FILES}
 assert historical_input_independence==675
 dataset=dict(schema='datascape.pressure_intent.v0.1',status='provisional_full_candidate_for_review',baseline_commit=e.PIN,artwork_size_mm=[600,900],coordinate_binding='No XY stored or regenerated; per-vertex values bind to exact canonical XY by stroke_id, vertex_count and hashes.',normalized_artistic_intent_only=True,calibrated=False,hardware_mapping=None,historical_pressure_policy='All 675 experimental profiles recomputed; originals remain unchanged in PR24 and separate reference file; never used as input.',offline_machine_placeholder_used=False,config_sha256=e.sha(HERE/'config.json'),strokes=sidecar)
 save(out/'spring_v13.pressure_intent_v01.json.gz',dataset);save(out/'artistic_modifiers.json.gz',dict(schema='datascape.pressure_intent.decomposition.v01',baseline_commit=e.PIN,strokes=decomposition));save(out/'historical_675_experimental_reference.json.gz',dict(schema='datascape.pressure_intent.historical_reference.v01',status='historical experimental values, not authoritative and not model inputs',baseline_commit=e.PIN,strokes=historic));write_csv(out/'stroke_statistics.csv',stats)
 summary,comparisons,hist_summary=summarize(stats,sidecar,historic);save(out/'family_statistics.json',summary);save(out/'historical_comparison_summary.json',hist_summary);write_csv(out/'historical_675_comparison.csv',comparisons);save(out/'D_hierarchy_cohorts.json',ctx.stats);save(out/'context_audit.json',e.audit(ctx,rows,SNAP));save(out/'historical_reference_audit.json',e.historical_audit(ROOT))
 anomalous=[r for r in stats if r['flags']];write_csv(out/'anomaly_audit.csv',anomalous)
 policy=dict(semantic_pressure_scope='normalized artistic intent only',historical_675='recomputed, never authoritative; canonical historical records remain exact',coefficients_identical_to_sample_study=True,diagnostic_thresholds=FLAGS,branch_policy='Original axis -> arm-* -> twig hierarchy; primary arms/trunks base 0.63, subordinate twigs/foliage base 0.45',width_policy='0.085*log2(width/stroke median) bounded to +/-0.15, 1.2 mm arclength smoothing; never minmax 0-1',context_policy='bounded +/-0.13; positively correlated width/context oscillation reduced up to 50%; family ranges applied',ordering='Baseline sequence and vertex direction locked; no reversal or reordering',saturation_is_not_failure='Bounds are provisional artistic limits. Every clip, flat profile and rapid transition is reported, not silently corrected.',estimated_fields='D mountain neighborhoods and valley semantics remain estimates, not original mass/valley IDs.')
 save(out/'generation_policy.json',policy)
 global_p=np.concatenate([s['pressure_intent_samples'] for s in sidecar]);validation=dict(baseline_commit=e.PIN,strokes=len(rows),vertices=int(len(global_p)),ink_strokes=sum(med=='ink' for med,i,r in raw),color_strokes=sum(med=='color' for med,i,r in raw),all_14951_profiles_recomputed=True,historical_675_recomputed=True,historical_675_input_removal_counterfactuals_passed=historical_input_independence,source_historical_pressure_sha256=e.hobj(historic),source_all_rich_records_sha256=record_hash,all_source_manifest_hashes_unchanged=True,baseline_file_sha256=baseline_hashes,all_unique_ids_exact=True,all_XY_vertex_order_width_expression_colors_layers_and_drawing_order_unchanged=True,pressure_per_original_vertex=True,all_family_ranges_valid=True,no_forced_0_or_1=True,pressure_minimum=float(global_p.min()),pressure_maximum=float(global_p.max()),pressure_point_median=float(np.median(global_p)),source_palette_color_slots=len(palette['slots']),all_modifier_decompositions_reconstruct_pressure=True,offline_machine_placeholder_used=False,approved_png_bytes_unchanged=True,approved_png_differing_RGBA_pixels=0,full_candidate_payload_sha256=e.hobj(dataset),data_file_sha256=e.sha(out/'spring_v13.pressure_intent_v01.json.gz'),runtime=dict(python=sys.version.split()[0],numpy=np.__version__,scipy=scipy_version,matplotlib=e.matplotlib.__version__,Pillow=pillow_version),hardware_Z_force_mapping_or_Gcode_created=False,PR24_modified_or_merged=False,new_PR_published=False)
 save(out/'validation.json',validation);shutil.copyfile(SNAP/'review/approved.png',out/'approved_unchanged.png');print('FULL GENERATION COMPLETE',json.dumps(dict(validation=validation,historical=hist_summary)),flush=True)


def load_review(out):
 raw,rows,phases,palette,manifest=load_baseline();dataset=e.read(out/'spring_v13.pressure_intent_v01.json.gz');dec=e.read(out/'artistic_modifiers.json.gz')['strokes'];stats=[]
 with (out/'stroke_statistics.csv').open() as f:
  for row in csv.DictReader(f):
   converted={}
   for k,v in row.items():
    if v in ['True','False']:converted[k]=v=='True'
    else:
     try:converted[k]=float(v) if '.' in v or 'e-' in v or 'e+' in v else int(v)
     except ValueError:converted[k]=v
   stats.append(converted)
 assert len(dataset['strokes'])==len(dec)==len(stats)==14951
 return rows,dataset,dec,stats

def plot_full_scene(out,rows,profiles):
 fig,axes=plt.subplots(1,3,figsize=(16,10));norm=Normalize(0,1)
 axes[0].imshow(Image.open(out/'approved_unchanged.png'),extent=(0,600,900,0));axes[0].set_title('Approved Spring v13 / unchanged')
 axes[1].add_collection(LineCollection([r['xy_mm'] for r in rows],array=np.asarray([e.C['bases'][e.family(r)] for r in rows]),cmap='viridis',norm=norm,linewidths=.45));axes[1].set_title('Family bases / comparison only')
 segments=[];values=[]
 for r,s in zip(rows,profiles):
  p=np.asarray(r['xy_mm']);v=np.asarray(s['pressure_intent_samples']);segments.extend(np.stack([p[:-1],p[1:]],axis=1));values.extend((v[:-1]+v[1:])/2)
 lc=LineCollection(segments,array=np.asarray(values),cmap='viridis',norm=norm,linewidths=.5);axes[2].add_collection(lc);axes[2].set_title('New full pressure intent / 14,951 strokes\n675 historical experiments also recomputed')
 for ax in axes:ax.set(xlim=(0,600),ylim=(900,0),aspect='equal');ax.axis('off')
 fig.colorbar(lc,ax=list(axes),fraction=.025,pad=.02,label='Normalized artistic intent (0–1), not force or Z');fig.suptitle('Spring Pressure Intent v01 / full provisional candidate / diagnostic colors only',fontsize=14);e.atomic_savefig(fig,out/'full_pressure_overview.png',dpi=155,bbox_inches='tight');plt.close(fig)

def plot_separate_media(out,rows,profiles):
 fig,axes=plt.subplots(1,2,figsize=(11,9));norm=Normalize(0,1)
 for ax,medium in zip(axes,['ink','color']):
  segments=[];values=[];count=0
  for r,p in zip(rows,profiles):
   if p['medium']!=medium:continue
   xy=np.asarray(r['xy_mm']);v=np.asarray(p['pressure_intent_samples']);segments.extend(np.stack([xy[:-1],xy[1:]],axis=1));values.extend((v[:-1]+v[1:])/2);count+=1
  lc=LineCollection(segments,array=np.asarray(values),cmap='viridis',norm=norm,linewidths=.65);ax.add_collection(lc);ax.set(xlim=(0,600),ylim=(900,0),aspect='equal');ax.axis('off');ax.set_title(f'{medium.upper()} / {count:,} recomputed profiles')
 fig.colorbar(lc,ax=list(axes),fraction=.03,pad=.03,label='Normalized artistic pressure intent (0–1)');fig.suptitle('Isolated ink and color pressure diagnostics / identical geometry and scale',fontsize=12);e.atomic_savefig(fig,out/'ink_color_pressure_overview.png',dpi=150,bbox_inches='tight');plt.close(fig)


def plot_distributions(out,stats,profiles):
 fig,axes=plt.subplots(2,5,figsize=(16,7),sharex=True)
 by={p['stroke_id']:p for p in profiles}
 for ax,fam in zip(axes.flat,FAMILIES):
  rr=[r for r in stats if r['family']==fam];pooled=np.concatenate([by[r['stroke_id']]['pressure_intent_samples'] for r in rr]);med=[r['median'] for r in rr]
  ax.hist(pooled,bins=np.linspace(0,1,51),density=True,color='#5a9b98',alpha=.65,label='Vertices (unequal per stroke)');ax.hist(med,bins=np.linspace(0,1,51),density=True,histtype='step',color='#ac4d35',linewidth=1.4,label='Stroke medians (equal strokes)');ax.axvline(e.C['bases'][fam],color='#222',ls=':',lw=1);ax.set_title(f'{fam} / n={len(rr)}',fontsize=10);ax.set(xlim=(0,1),xlabel='Normalized intent',ylabel='Density');ax.grid(alpha=.15)
 axes.flat[0].legend(fontsize=6);fig.suptitle('Full-family pressure distributions / fixed 0–1 horizontal scale',fontsize=13);fig.tight_layout();e.atomic_savefig(fig,out/'family_distributions.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(13,6));data=[[r['span'] for r in stats if r['family']==f] for f in FAMILIES];axes[0].boxplot(data,orientation='horizontal',tick_labels=FAMILIES,showfliers=False);axes[0].set(xlim=(0,.55),xlabel='Within-stroke pressure span (max − min)',title='Per-stroke variation / median and IQR');axes[1].barh(FAMILIES,[sum(r['family']==f and r['family_clipped_vertices']>0 for r in stats) for f in FAMILIES],color='#c77c55',label='Family-bound clipping');axes[1].barh(FAMILIES,[-sum(r['family']==f and r['flat_profile'] for r in stats) for f in FAMILIES],color='#709f9c',label='Flat span < 0.01 (shown left)');axes[1].set(xlabel='Stroke count (flat left / clipped right)',title='Flags for review, not automatic failures');axes[1].legend(fontsize=8);fig.tight_layout();e.atomic_savefig(fig,out/'variation_and_flags.png',dpi=150);plt.close(fig)


def plot_historical(out,rows,profiles):
 fig,axes=plt.subplots(1,3,figsize=(15,4.8));old=[];new=[];oldspan=[];newspan=[];medold=[];mednew=[]
 for r,p in zip(rows,profiles):
  if 'pressure_intent_samples' not in r:continue
  aa=np.asarray(r['pressure_intent_samples']);bb=np.asarray(p['pressure_intent_samples']);old.extend(aa);new.extend(bb);oldspan.append(np.ptp(aa));newspan.append(np.ptp(bb));medold.append(np.median(aa));mednew.append(np.median(bb))
 axes[0].hist(old,bins=np.linspace(0,1,41),density=True,histtype='step',color='#333',label='Historical experiment');axes[0].hist(new,bins=np.linspace(0,1,41),density=True,color='#5b9c98',alpha=.55,label='New painterly intent');axes[0].set(xlim=(0,1),title='All 8,975 historical vertices / recomputed',xlabel='Normalized artistic intent',ylabel='Density');axes[0].legend(fontsize=8)
 axes[1].scatter(oldspan,newspan,s=9,alpha=.35,color='#4c8d8a');axes[1].plot([0,1],[0,1],ls=':',color='#aaa');axes[1].set(xlim=(0,1),ylim=(0,1),xlabel='Historical within-stroke span',ylabel='New within-stroke span',title='675 strokes / variation is restrained')
 axes[2].scatter(medold,mednew,s=9,alpha=.35,color='#ac6949');axes[2].plot([0,1],[0,1],ls=':',color='#aaa');axes[2].set(xlim=(0,1),ylim=(0,1),xlabel='Historical stroke median',ylabel='New stroke median',title='Medians / no historical authority retained')
 fig.tight_layout();e.atomic_savefig(fig,out/'historical_675_comparison.png',dpi=155);plt.close(fig)


def make_plot_record(r,p,d,group,sample_id):
 return dict(stroke_id=r['id'],sample_id=sample_id,group=group,family=p['family'],pictorial_role=p['pictorial_role'],arclength_mm=e.arc(np.asarray(r['xy_mm'])).tolist(),length_mm=float(e.arc(np.asarray(r['xy_mm']))[-1]),vertex_count=p['vertex_count'],base=d['base'],width_only_pressure=d['width_only_pressure'],proposed_pressure=p['pressure_intent_samples'],original_width_mm=r.get('width_profile_mm',[r['width_mm']]*len(r['xy_mm'])),original_pressure=r.get('pressure_intent_samples'),modifier_contributions=d['modifier_contributions'],context=d['context'],uncertainties=d['uncertainties'])

GROUPS=[('A_peak_D','A / concentration near related D'),('A_mist','A / release into mist'),('D_hierarchy','D / both mountain hierarchy levels'),('valley_structure','A / structural-valley estimate'),('valley_mist','A / mist-valley estimate'),('rock','Rock / strong entry, release, final renewal'),('Soil','Soil / ground and hatch overlap'),('trunk','Tree / structural trunks'),('branches','Primary branches, subordinate twigs and foliage'),('vegetation_dense','Dense vegetation / individual pressure reduction'),('vegetation_sparse','Sparse vegetation / no isolation bonus'),('A_color','A-derived color / softer structure response'),('C_color','C color / ground flow'),('original_pressure','Historical experimental pressure / fully recomputed'),('short_strokes','Sub-mm geometry / preserved'),('B_structure','B / structural ink')]


def review(out,reproduction,old_study):
 rows,dataset,decs,stats=load_review(out);profiles=dataset['strokes'];index={r['id']:i for i,r in enumerate(rows)};ctx=type('PlotContext',(),dict(rows=rows,idx={r['id']:r for r in rows}))()
 files=['spring_v13.pressure_intent_v01.json.gz','artistic_modifiers.json.gz','historical_675_experimental_reference.json.gz','stroke_statistics.csv','family_statistics.json','historical_675_comparison.csv','historical_comparison_summary.json','context_audit.json','D_hierarchy_cohorts.json','generation_policy.json','anomaly_audit.csv','validation.json'];checks={n:(out/n).read_bytes()==(reproduction/n).read_bytes() for n in files};assert all(checks.values()),checks
 save(out/'independent_reproduction.json',dict(files_byte_identical=checks,full_candidate_file_sha256=e.sha(out/'spring_v13.pressure_intent_v01.json.gz'),separate_source_regenerations=True))
 old=e.read(old_study/'representative_pressure_intent.json' if old_study is not None else HERE/'reference_samples.json.gz')['selected_strokes'];maxerr=0;examples=[]
 for s in old:
  i=index[s['stroke_id']];p=profiles[i];d=decs[i];maxerr=max(maxerr,float(np.max(np.abs(np.asarray(s['proposed_pressure'])-p['pressure_intent_samples']))));examples.append(make_plot_record(rows[i],p,d,s['group'],s['sample_id']))
 assert maxerr<1e-12
 save(out/'previous_sample_rule_equivalence.json',dict(samples=len(old),maximum_absolute_pressure_difference=maxerr,rule_coefficients_unchanged=True,math_policy='Same bounded relative-width and contextual arithmetic; old 675 now reference only for every stroke.'))
 print('Review: full scene and distributions',flush=True);plot_full_scene(out,rows,profiles);plot_separate_media(out,rows,profiles);plot_distributions(out,stats,profiles);plot_historical(out,rows,profiles);e.context_overview(out,SNAP)
 # Retain matched examples; all D and all four earlier historical samples are included.
 for group,title in GROUPS:
  print('Review examples',group,flush=True);e.crop_fig(out,ctx,examples,group,title)
 save(out/'matched_examples.json.gz',dict(status='Examples selected from the complete candidate, not a separate pressure policy',strokes=examples))
 # Select the most informative anomaly examples, with exact full-candidate values.
 anomaly_examples=[];used=set()
 selectors=[('clipping',lambda r:r['family_clipped_vertices']>0,lambda r:r['bound_fraction_vertices']),('abrupt',lambda r:r['abrupt_segments']>0,lambda r:r['max_adjacent_delta']),('flat_width',lambda r:r['flat_despite_nonflat_width'],lambda r:r['length_mm']),('flat',lambda r:r['flat_profile'],lambda r:r['length_mm'])]
 for label,pred,key in selectors:
  rr=sorted([r for r in stats if pred(r) and r['stroke_id'] not in used],key=lambda r:(key(r),r['stroke_id']),reverse=True)
  for r in rr[:2]:
   i=index[r['stroke_id']];anomaly_examples.append(make_plot_record(rows[i],profiles[i],decs[i],'anomalies',f'Q{len(anomaly_examples)+1:02d}'));used.add(r['stroke_id'])
 if anomaly_examples:e.crop_fig(out,ctx,anomaly_examples,'anomalies','Audit cases / clipping, short-segment changes and flatness');save(out/'anomaly_examples.json.gz',dict(strokes=anomaly_examples))
 detailed_audit(out,rows,profiles,decs,stats);build_report(out,stats,examples);package_sources(out);save(out/'MANIFEST_SHA256.json',{str(f.relative_to(out)):e.sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='MANIFEST_SHA256.json'});print('REVIEW COMPLETE',flush=True)


def package_sources(out):
 dest=out/'source';dest.mkdir(exist_ok=True)
 for n in ['engine.py','config.json','full_pressure.py','bindings.py','test_bindings.py','reference_samples.json.gz']:shutil.copyfile(HERE/n,dest/n)
 v=e.read(out/'validation.json')['runtime'];(dest/'requirements.txt').write_text('\n'.join(f'{k}=={v[k]}' for k in ['numpy','scipy','matplotlib','Pillow'])+'\n')
 (out/'README.md').write_text('''# Spring v13 Pressure Intent v01 — Full Provisional Candidate

All 14,951 profiles are newly computed, including the historical 675 experiments. If this candidate is approved, its profiles must be used consistently for every ID; do not mix the old 675 into the new dataset or fall back to the offline 0.5 placeholder. At present it remains a provisional candidate for review. Historical pressure is preserved in frozen PR24 and a separate reference file, but is not authoritative and is never a model input. No force, Z, executable G-code or machine calibration is supplied.

Repository: https://github.com/ggooonn/Datascape

Frozen XY baseline: `67ba146b1213644d40bc9dabed9d52024d2bbe58` (PR https://github.com/ggooonn/Datascape/pull/24). The source representation is unchanged. The sidecar has no regenerated XY and is not a machine-vector export.

## Reproduce

Check out that exact repository commit. Copy this package's `source/` into `studies/spring_pressure_full_v01/`. Install `source/requirements.txt` (Python '''+v['python']+'''). Run from the repository root with fresh absolute paths:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/spring_pressure_full_v01/full_pressure.py generate --output /absolute/full-candidate
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/spring_pressure_full_v01/full_pressure.py generate --output /absolute/independent-reproduction
```

Compare every pressure, decomposition, statistics and validation byte. Gzip headers use mtime=0. The review stage uses bundled reference_samples.json.gz to retain matched crops from the previous study, so that prior package is not required. It does not change pressure values:

```sh
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python studies/spring_pressure_full_v01/full_pressure.py review --output /absolute/full-candidate --reproduction /absolute/independent-reproduction
```

## Load and bind, without changing frozen source

```python
from pathlib import Path
from bindings import load_bound_pressure
pressure_by_id = load_bound_pressure(
    Path('/absolute/Datascape/artworks/spring_v13'),
    Path('/absolute/full-candidate/spring_v13.pressure_intent_v01.json.gz'))
# Use only after artistic review: arrays align one-to-one with original XY vertices.
# The binder verifies complete IDs/order, source record hashes, geometry and widths.
# Run meaningful positive/negative binding tests (no source file mutations):
# python studies/spring_pressure_full_v01/test_bindings.py --snapshot /absolute/Datascape/artworks/spring_v13 --pressure /absolute/full-candidate/spring_v13.pressure_intent_v01.json.gz
```

- `spring_v13.pressure_intent_v01.json.gz`: canonical full provisional ID-linked sidecar (14,951 strokes / 240,974 pressure values).
- `artistic_modifiers.json.gz`: base, width, named contextual modifiers and estimation caveats.
- `historical_675_experimental_reference.json.gz`: unchanged historical pressure for provenance only.
- `stroke_statistics.csv`, `family_statistics.json`: distributions and within-stroke variation.
- `historical_675_comparison.csv`: old versus recomputed values for every historical stroke.
- `anomaly_audit.csv`, `generation_policy.json`: explicit thresholds, saturation, rapid transitions and flatness.
- `validation.json`, `independent_reproduction.json`: source preservation and deterministic regeneration.
- `context_audit.json`: available source fields versus estimates; D cohorts are not proven mountain IDs.

Source width remains artistic width metadata, not calibrated physical pressure. Display opacity is not a pressure input. No per-stroke minmax normalization, forcing to 0/1, reversal, reordered geometry, PR publication or merge occurs.
''')


def build_report(out,stats,examples):
 # Implemented below: Korean report derived only from generated statistics.
 summary=e.read(out/'family_statistics.json');hist=e.read(out/'historical_comparison_summary.json');val=e.read(out/'validation.json');repro=e.read(out/'independent_reproduction.json');audit=e.read(out/'context_audit.json')
 def embed(name):return '<img loading="lazy" alt="'+name+'" src="data:image/png;base64,'+base64.b64encode((out/name).read_bytes()).decode()+'">'
 def fmt(x):return f'{x:.3f}'
 table=''
 for fam in FAMILIES:
  s=summary[fam];sp=s['within_stroke_span_min_median_p95_max'];table+=f'<tr><td>{fam}</td><td>{s["strokes"]:,}</td><td>{fmt(s["base"])}</td><td>{fmt(s["allowed_range"][0])}–{fmt(s["allowed_range"][1])}</td><td>{fmt(s["point_minimum"])} / {fmt(s["point_median"])} / {fmt(s["point_maximum"])}</td><td>{fmt(sp[0])} / {fmt(sp[1])} / {fmt(sp[2])} / {fmt(sp[3])}</td><td>{s["saturated_strokes"]}</td><td>{s["flat_strokes"]}</td><td>{s["abrupt_short_segment_strokes"]}</td></tr>'
 counts=dict(saturated_strokes=sum(r['family_clipped_vertices']>0 for r in stats),saturated_vertices=sum(r['lower_bound_vertices']+r['upper_bound_vertices'] for r in stats),flat_strokes=sum(r['flat_profile'] for r in stats),exact_flat_strokes=sum(r['exact_flat_profile'] for r in stats),flat_despite_nonflat_width=sum(r['flat_despite_nonflat_width'] for r in stats),abrupt_short_segment_strokes=sum(r['abrupt_segments']>0 for r in stats),large_adjacent_delta_strokes=sum(r['large_adjacent_delta_segments']>0 for r in stats),high_gradient_strokes=sum(r['max_gradient_per_mm']>FLAGS['high_gradient_per_mm'] for r in stats))
 save(out/'review_counts.json',counts)
 amed=summary['A']['stroke_median_median'];dmed=summary['D']['stroke_median_median'];delta=dmed-amed
 body='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>Spring Pressure Intent v01 — Full Candidate</title><style>body{font:15px/1.7 system-ui,sans-serif;margin:0;background:#f6f5f1;color:#25313a}main{max-width:1350px;margin:auto;padding:36px}h1{font-size:34px}h2{margin-top:50px}img{width:100%;height:auto;background:white}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;font-size:12px;padding:9px;border-bottom:1px solid #ddd}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px}.notice{background:#f7ebd4;padding:22px;border-left:4px solid #ba8c41}.table{overflow-x:auto}</style><main><h1>Spring Pressure Intent v01 · 전체 후보</h1>'''
 body+=f'<p>고정 기준 <a href="https://github.com/ggooonn/Datascape/pull/24">PR #24</a> · <code>{e.PIN}</code> · 연속 600 × 900 mm · 14,951 경로 / 240,974 꼭짓점</p><div class="notice"><b>정책 변경 적용.</b> 과거 675개 필압은 초기 실험 기록이며 권위 있는 정답으로 고정하지 않습니다. 이번 14,951개는 모두 같은 새 규칙으로 재계산했습니다. 과거 값은 PR #24와 별도 reference 파일에 그대로 남기고, 새 후보는 별도 ID 연결 데이터에 저장했습니다. 정규화된 예술적 의도이며 물리 힘·Z 깊이·12 mm 압축 변환·G-code가 아닙니다.</div>'
 body+='<h2>01 · 한국어 검토</h2>'
 body+=f'<p><b>전체 결과.</b> 새 필압은 {val["pressure_minimum"]:.3f}–{val["pressure_maximum"]:.3f}에 분포하고 0 또는 1로 강제된 값이 없습니다. 경로별 중앙값을 다시 요약한 A 중앙값은 {amed:.3f}, D는 {dmed:.3f}로 차이가 {delta:.3f}입니다. 경로 내 변화폭의 최댓값은 {max(r['span'] for r in stats):.3f}입니다. 폭은 0–1 전구간으로 늘리지 않고 상대 폭의 로그 변화 ±0.15만 사용했습니다. 문맥 보정은 ±0.13 안에서 적용하고 가족별 범위를 지켰습니다.</p>'
 body+=f'<p><b>과거 675개.</b> 모두 새로 계산했고, 기존 필압을 입력에서 제거한 675회 반사실 검증도 통과했습니다. 과거 경로 내 변화폭의 중앙값은 {hist["historical_span_min_median_p95_max"][1]:.3f}, 새 값은 {hist["new_span_min_median_p95_max"][1]:.3f}입니다. 변화폭이 0.8을 넘는 과거 경로 {hist["historical_spans_over_0_8"]}개에 비해 새 후보는 {hist["new_spans_over_0_8"]}개입니다. 과거 값의 영향 없이 폭·구조·안개·혼잡으로 계산한 새 의도입니다.</p>'
 body+=f'<p><b>검토할 부분.</b> 가족 범위에 의해 일부 값이 잘린 경로는 {counts["saturated_strokes"]}개, 변화폭 0.01 미만은 {counts["flat_strokes"]}개입니다. 폭 자체는 변하는데 2 mm 이상 경로에서 압력 변화폭이 0.01 미만인 경우 {counts["flat_despite_nonflat_width"]}개를 따로 표시했습니다. 1 mm 이하 구간에서 압력 차가 0.08을 넘는 경로는 {counts["abrupt_short_segment_strokes"]}개입니다. 이 표시는 자동 실패나 숨은 수정이 아니라 시각 검토 대상입니다.</p>'
 body+='<p><b>문맥의 한계.</b> 산괴 ID와 계곡 의미 분류는 원본에 명시되어 있지 않습니다. 보존 UTM 고도·전방 깊이·retention을 쓰되 D support event 묶음은 산지 이웃의 추정이고, 계곡 유형도 고도 TPI·경사·안개의 조합 추정입니다. 잘린 D 조각의 현재 경로 중앙 폭을 기준으로 하는 정규화와 하한에 머무는 조밀한 식생은 후속 조정 후보입니다. 이번 전체 생성에서는 승인된 계수를 임의로 바꾸거나 포화·평탄 경로를 자동으로 재설계하지 않았습니다.</p>'
 body+='<h2>02 · 전체 필압 분포</h2><p>왼쪽 승인 이미지는 독립적으로 보존했습니다. 가운데는 가족별 기준값 대조, 오른쪽은 이번에 재계산한 <b>전체 14,951개</b>의 실제 경로별 필압입니다. 진단 색상척도는 항상 0–1이며 승인 그림에 새 먹·채색을 더한 것이 아닙니다.</p>'+embed('full_pressure_overview.png')
 if (out/'ink_color_pressure_overview.png').exists():body+='<p>아래는 먹·색 분리 진단입니다. D와 A의 관계 및 채색의 낮은 필압을 합성 순서에 가려지지 않게 볼 수 있습니다.</p>'+embed('ink_color_pressure_overview.png')
 body+='<h2>03 · 가족별 수치와 경로 내부 변화</h2><p>압력 min/median/max는 원래 꼭짓점 전체를 모은 값입니다. 경로 내 span은 각 경로의 max−min이며 min/median/P95/max를 표시합니다. 꼭짓점 수가 많은 경로의 가중과 경로별 동등 가중은 구분했습니다. 모든 경로의 min/max/median/평균/표준편차/span/구간 변화는 stroke_statistics.csv에 있습니다.</p><div class="table"><table><tr><th>Family</th><th>경로 수</th><th>기준</th><th>허용 범위</th><th>압력 min / median / max</th><th>경로 내 span min / median / P95 / max</th><th>범위 clipping</th><th>평탄 &lt;.01</th><th>짧은 급변</th></tr>'+table+'</table></div>'+embed('family_distributions.png')+embed('variation_and_flags.png')
 body+='<h2>04 · 과거 675개 실험과 새 계산</h2><p>검은 선은 과거 실험, 색 선은 새 의도입니다. 동일 ID와 동일 꼭짓점에서 비교했습니다. 과거 필압의 보존은 출처 보존이며 새 후보에서 과거 값에 우선권을 주지 않습니다.</p>'+embed('historical_675_comparison.png')+'<pre>'+html.escape(json.dumps(hist,ensure_ascii=False,indent=2))+'</pre>'
 body+='<h2>05 · 실제 경로 확대와 폭·필압 그래프</h2><p>이전 스터디의 동일 55개 경로를 이번 전체 후보에서 추출했습니다. 압력 계산 규칙은 그대로이고 과거 675개에 대한 정책만 바뀌었습니다. 왼쪽은 기준+폭, 가운데는 전체 문맥 보정, 오른쪽은 새 압력과 원본 폭(mm)입니다. 과거 실험이 있으면 검은 점선으로만 비교합니다. 원은 첫 꼭짓점, 사각형은 마지막 꼭짓점이며 좌표·방향은 바꾸지 않았습니다.</p>'
 for group,title in GROUPS:
  if (out/(group+'.png')).exists():body+='<details><summary>'+html.escape(title)+'</summary>'+embed(group+'.png')+'</details>'
 body+='<h2>06 · 포화·급변·평탄 감사</h2><p>기준: 평탄 span&lt;0.01; 거의 완전 평탄 span&lt;1e−6; 급변 |Δp|&gt;0.08이면서 구간 길이≤1 mm. 긴 구간에서 |Δp|&gt;0.12와 기울기&gt;0.10/mm도 별도 플래그입니다. 기울기 플래그는 짧은 조각의 작은 변화에도 생길 수 있으므로 압력 차·길이·폭 변화와 함께 읽어야 합니다. 모든 후보는 원래 꼭짓점 사이 선형 보간을 전제로 연속적이며, 이 감사는 물리 시간축이나 Z 속도 검증이 아닙니다.</p><pre>'+html.escape(json.dumps(counts,ensure_ascii=False,indent=2))+'</pre>'
 if (out/'anomalies.png').exists():body+=embed('anomalies.png')
 if (out/'saturation_analysis.json').exists():
  detail=e.read(out/'saturation_analysis.json');veg=detail['by_family']['mid-far-vegetation'];body+='<h3>하한 포화의 위치와 길이</h3><p>중·원경 식생 '+str(veg['clipped_strokes'])+'개에서 일부 하한 clipping이 있습니다. 이 중 정규화 호 길이의 중앙 절반(0.25–0.75)에 clipping이 있는 경로는 '+str(veg['middle_half_clipped_strokes'])+'개, 전체 길이의 절반 이상이 정확한 하한 plateau인 경로는 '+str(veg['plateau_over_half_length_strokes'])+'개입니다. 중앙 절반은 통계용 구간이며 실제 나무 몸통/수관의 의미 분류가 아닙니다. 말단에만 생긴 포화로 단정하지 않았습니다. 원래 폭 변화가 거의 없는 A·Soil의 평탄함은 새 신호를 인위적으로 만들지 않은 결과일 수 있지만, 폭이 변해도 평탄해진 경로는 평활화·문맥 상쇄·하한 제한을 함께 검토해야 합니다.</p>'+embed('saturation_positions.png')+'<pre>'+html.escape(json.dumps(detail,ensure_ascii=False,indent=2))+'</pre>'
 body+='<h2>07 · 보존된 실제 필드와 추정 구분</h2>'+embed('preserved_context_fields.png')
 for key,label in [('available','보존된 정보'),('estimated','추정한 문맥'),('unavailable','부재 또는 미확정 정보')]:body+='<h3>'+label+'</h3><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in audit[key])+'</ul>'
 body+='<h2>08 · 재현·보존 검증</h2><p>새 전체 후보·보정항·통계·이상 경로 감사는 원본 입력에서 별도 프로세스로 두 번 계산하여 바이트 단위 일치를 확인했습니다. 원본 675개와 폭·XY·색·순서·mist/occlusion을 포함한 고정 원본 파일은 모든 manifest 해시가 그대로입니다. 승인 PNG는 바이트 일치하므로 RGBA 차이도 0입니다.</p><pre>'+html.escape(json.dumps(val,ensure_ascii=False,indent=2))+'</pre><pre>'+html.escape(json.dumps(repro,ensure_ascii=False,indent=2))+'</pre>'
 if (out/'binding_validation.json').exists():body+='<h3>ID 결합 검사</h3><pre>'+html.escape((out/'binding_validation.json').read_text())+'</pre>'
 body+='<h2>09 · 데이터 사용과 검토 경계</h2><p>기준 파일은 <code>spring_v13.pressure_intent_v01.json.gz</code>입니다. 새로운 normalized pressure_intent_samples를 ID와 원래 꼭짓점 인덱스로 연결합니다. <code>artistic_modifiers.json.gz</code>는 폭·기준값·문맥 항을 분리하고, <code>historical_675_experimental_reference.json.gz</code>는 과거 실험만 보존합니다. frozen source에 덮어쓰지 마십시오. <code>source/bindings.py</code>가 원본 해시·ID·순서·폭과 점 수를 확인한 뒤 메모리의 ID→필압 배열을 반환합니다.</p><p>재현 명령과 의존성은 README.md와 source/에 있습니다. PR #24 변경·병합, 새 PR 발행, 물리 Z·힘 변환, 세척·급액·보정 및 실행 G-code 생성은 하지 않았습니다. 전체 후보를 잠정 자료로 제시하고 검토를 기다립니다.</p></main></html>'
 (out/'Spring_Pressure_Intent_v01_Full_Review.html').write_text(body)


def detailed_audit(out,rows,profiles,decs,stats):
 by=defaultdict(list);position_hist=defaultdict(lambda:np.zeros(20));details=[]
 for r,p,d,m in zip(rows,profiles,decs,stats):
  if not m['family_clipped_vertices']:continue
  pressure=np.asarray(p['pressure_intent_samples']);a=e.arc(np.asarray(r['xy_mm']));t=a/a[-1];ds=np.diff(a);adjust=np.asarray(d['modifier_contributions']['family_range_limit']);low=adjust>1e-10;high=adjust< -1e-10;clipped=low|high;middle=(t>=.25)&(t<=.75)
  plateau=clipped[:-1]&clipped[1:]&(np.abs(np.diff(pressure))<1e-12);plateau_length=float(ds[plateau].sum());run=0.;maximum_run=0.
  for length,on in zip(ds,plateau):
   run=run+length if on else 0.;maximum_run=max(maximum_run,run)
  v=dict(stroke_id=r['id'],family=p['family'],length_mm=float(a[-1]),lower_clipped_vertices=int(low.sum()),upper_clipped_vertices=int(high.sum()),middle_half_clipped_vertices=int((clipped&middle).sum()),entry_exit_quarters_clipped_vertices=int((clipped&~middle).sum()),plateau_length_mm=plateau_length,plateau_length_fraction=float(plateau_length/a[-1]),longest_plateau_fraction=float(maximum_run/a[-1]),mean_width_delta_at_clipped_vertices=float(np.asarray(d['width_contribution'])[clipped].mean()),mean_context_delta_at_clipped_vertices=float(sum((np.asarray(z) for key,z in d['modifier_contributions'].items() if key!='family_range_limit'),np.zeros(len(pressure)))[clipped].mean()))
  details.append(v);by[p['family']].append(v);position_hist[p['family']]+=np.histogram(t[clipped],bins=np.linspace(0,1,21))[0]
 result={}
 for fam in FAMILIES:
  rr=by[fam];result[fam]=dict(clipped_strokes=len(rr),clipped_vertices=sum(r['lower_clipped_vertices']+r['upper_clipped_vertices'] for r in rr),middle_half_clipped_strokes=sum(r['middle_half_clipped_vertices']>0 for r in rr),entry_exit_only_clipped_strokes=sum(r['middle_half_clipped_vertices']==0 for r in rr),plateau_over_half_length_strokes=sum(r['plateau_length_fraction']>.5 for r in rr),median_plateau_length_fraction=float(np.median([r['plateau_length_fraction'] for r in rr])) if rr else 0.,maximum_plateau_length_fraction=max((r['plateau_length_fraction'] for r in rr),default=0.))
 large_events=[]
 for r,p,m in zip(rows,profiles,stats):
  if not m['large_adjacent_delta_segments']:continue
  aa=e.arc(np.asarray(r['xy_mm']));vv=np.asarray(p['pressure_intent_samples']);dd=np.abs(np.diff(vv))
  for j in np.flatnonzero(dd>FLAGS['large_adjacent_delta']):large_events.append(dict(stroke_id=r['id'],segment_index=int(j),segment_length_mm=float(aa[j+1]-aa[j]),absolute_pressure_delta=float(dd[j]),gradient_per_mm=float(dd[j]/max(aa[j+1]-aa[j],1e-12))))
 payload=dict(large_adjacent_events=large_events,position_definition='Original arclength normalized to 0-1; middle half 0.25-0.75 is a statistical phase, not semantic trunk/canopy occupancy.',plateau_definition='Consecutive original vertices at the same clipped family bound; sum of original segment lengths, not physical contact time.',by_family=result,flat_total=sum(m['flat_profile'] for m in stats),flat_with_constant_or_nearly_constant_width=sum(m['flat_profile'] and m['width_relative_span']<=FLAGS['width_nonflat_relative_span'] for m in stats),flat_under_2mm=sum(m['flat_profile'] and m['length_mm']<2 for m in stats),flat_despite_nonflat_width_over_2mm=sum(m['flat_despite_nonflat_width'] for m in stats))
 save(out/'saturation_analysis.json',payload);write_csv(out/'saturation_by_stroke.csv',details)
 fig,axes=plt.subplots(1,2,figsize=(13,5));centers=(np.linspace(0,1,21)[:-1]+np.linspace(0,1,21)[1:])/2
 for fam in ['mid-far-vegetation','branch-foliage','D']:
  h=position_hist[fam]
  if h.sum():axes[0].plot(centers,h/h.sum(),label=fam,marker='.',lw=1.2)
 axes[0].axvspan(.25,.75,color='#888',alpha=.08);axes[0].set(xlim=(0,1),xlabel='Normalized original arclength',ylabel='Fraction of clipped vertices',title='Where family-bound clipping occurs');axes[0].legend(fontsize=8)
 for fam,color in [('mid-far-vegetation','#5c9692'),('branch-foliage','#bf8657')]:
  values=[r['plateau_length_fraction'] for r in by[fam]]
  axes[1].hist(values,bins=np.linspace(0,1,21),histtype='step',lw=1.5,color=color,label=fam)
 axes[1].set(xlim=(0,1),xlabel='Fraction of full stroke length at exact bound plateau',ylabel='Stroke count',title='Plateau length / clipped strokes only');axes[1].legend(fontsize=8);fig.tight_layout();e.atomic_savefig(fig,out/'saturation_positions.png',dpi=150);plt.close(fig)


def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
 g=sub.add_parser('generate');g.add_argument('--output',type=Path,required=True)
 r=sub.add_parser('review');r.add_argument('--output',type=Path,required=True);r.add_argument('--reproduction',type=Path,required=True);r.add_argument('--old-study',type=Path,help='Optional original sample study directory; otherwise use bundled reference_samples.json.gz')
 args=ap.parse_args()
 if args.cmd=='generate':generate(args.output.resolve())
 else:review(args.output.resolve(),args.reproduction.resolve(),args.old_study.resolve() if args.old_study else None)

if __name__=='__main__':main()
