"""Actual-vector reviews and source-field diagnostics; no painted over masks."""
from shared import *
from flow import release
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from PIL import Image,ImageDraw,ImageFont

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def scene_review(out,f,flow):
    out=Path(out);c=read(out/'config.json');ink=read(out/'ink.json.gz')['strokes'];color=read(out/'color_intent.json.gz')['strokes']
    from flow import release
    raw_f={**f,'retention':flow['original']}
    fig,axes=plt.subplots(1,len(c['flow_candidates']),figsize=(5*len(c['flow_candidates']),7),squeeze=False)
    records=[]
    for ax,recipe in zip(axes[0],c['flow_candidates']):
        _,fields,record=release(raw_f,recipe);records.append(record)
        ax.imshow(fields['new'],vmin=0,vmax=1,cmap='Greys',extent=[0,600,900,0]);ax.plot(fields['points'][:,0],fields['points'][:,1],c='#9a684d',lw=1.6)
        ax.axvline(300,c='#999',lw=.6,ls='--');ax.set_title(recipe['id']+(' / selected' if recipe['id']==c['selected_flow'] else ''),fontsize=10)
        ax.set(xlabel='Continuous painted X (mm)',ylabel='Top-down Y (mm)')
    fig.suptitle('Asymmetric retention hypotheses / source-valley routes, not separate finished scenes')
    fig.tight_layout();figure_png(fig,out/'composition_studies.png',dpi=140);plt.close(fig)
    save(out/'composition_studies.json',dict(selected=c['selected_flow'],rationale=c['composition_rationale'],hypotheses=records,scope='Field hypotheses; final canonical vectors belong only to the selected composition'))
    fig,axes=plt.subplots(1,3,figsize=(13,6))
    for ax,array,title in zip(axes,[flow['original'],flow['new'],flow['new']-flow['original']],['Inherited retention','Terrain-relative release','Retention change']):
        ax.imshow(array,vmin=-1 if 'change' in title else 0,vmax=1,cmap='RdBu' if 'change' in title else 'Greys',extent=[0,600,900,0]);ax.plot(flow['points'][:,0],flow['points'][:,1],c='#b1784f',lw=1)
        ax.set_ylim(810,250);ax.set_title(title)
    fig.suptitle(c['case']+' / middle release follows measured valley evidence');fig.tight_layout();figure_png(fig,out/'mist_flow_diagnostics.png');plt.close(fig)
    placement=read(out/'placement.json');groups={}
    for obj in placement['catalog']:
        g=groups.setdefault(obj['group'],dict(objects=[],depths=[]))
        g['objects'].append(dict(id=obj['id'],kind=obj['kind'],xy_mm=obj['site']['xy_mm'],depth_m=obj['site']['source_forward_m'],height_mm=obj.get('height_mm'),parent_mass_id=obj.get('parent_mass_id')))
        g['depths'].append(obj['site']['source_forward_m'])
    for g in groups.values():
        g['depth_range_m']=[min(g.pop('depths')),max(o['depth_m'] for o in g['objects'])]
        g['metric_limit']='Contact depths and upright 2.5D silhouettes; not full 3D botanical geometry or wet brush simulation'
    save(out/'grouping_depth_review.json',groups)
    fig,ax=plt.subplots(figsize=(8,7))
    ax.imshow(f['base']['depth_m'],vmin=0,vmax=1800,cmap='terrain',extent=[0,600,900,0],alpha=.3)
    for j,(name,g) in enumerate(groups.items()):
        xy=np.array([o['xy_mm'] for o in g['objects']]);ax.scatter(xy[:,0],xy[:,1],label=name,s=24)
        for o in g['objects']:
            x,y=o['xy_mm'];ax.annotate(o['kind'][0]+f' {o["depth_m"]:.0f}m',(x,y),fontsize=6)
    ax.set(xlim=(0,600),ylim=(900,540),xlabel='Painted X (mm)',ylabel='Top-down Y (mm)',title='Measured contacts / shared groups and source depths');ax.legend(fontsize=7)
    fig.tight_layout();figure_png(fig,out/'grouping_contacts.png');plt.close(fig)
    if c['season']=='summer':
        oldout=ROOT/'docs/experiments/summer_foreground_v02';old=read(oldout/'ink.json.gz')['strokes'];oc=read(oldout/'color_intent.json.gz')['strokes'];oldc=read(oldout/'config.json')
        prior.grid([(oldout/'full.png','PR37 / Summer v02'),(out/'full.png','Summer v03 / provisional')],out/'summer_v02_v03.png','Summer v02 / v03 — same camera and artwork scale',cell=(650,975),columns=2,note='Existing middle/far structure is the starting point; middle release and foreground organization change.')
        for tag,bounds in [('middle',(0,285,600,715)),('foreground',(0,555,600,898))]:
            panels=[]
            for name,ii,cc,cfg in [('v02',old,oc,oldc),('v03',ink,color,c)]:
                p=out/(tag+'_'+name+'.png');accepted_review.render(ii,cc,p,cfg,bounds=bounds,pixels=(1200,int((bounds[3]-bounds[1])*2)));panels.append((p,name))
            prior.grid(panels,out/(tag+'_comparison.png'),'Summer '+tag+' / matched actual-vector crops',cell=(900,int((bounds[3]-bounds[1])*1.5)),columns=2,note='Same bounds and scale; no raster eraser or image retouching.')
        compare={}
        for name,rows in [('v02',old),('v03',ink)]:
            compare[name]=dict(ink_paths=len(rows),length_mm=sum(map(length,rows)),layers={k:dict(paths=sum(r['layer']==k for r in rows),length_mm=sum(length(r) for r in rows if r['layer']==k)) for k in ['A','B','C','D','V','tree','rock','Soil']})
        save(out/'v02_v03_statistics.json',compare)
    workload=accepted_review.workload(ink,dict(depth=f['base']['depth_m']))
    save(out/'workload.json',dict(ink=workload,color=accepted_review.workload(color,dict(depth=f['base']['depth_m'])),physical_note=c['physical_note']))
    text=f'''# {c['case']} / provisional composition review

Start with full.png, physical_pair.png, P{c['panels'][0]}.png, P{c['panels'][1]}.png and layers.png. Middle release evidence is in mist_flow_diagnostics.png, flow_review.json and composition_studies.png. grouping_contacts.png and grouping_depth_review.json show actual shared source contacts; they do not claim complete 3D simulation.

Composition: {c['composition_rationale']}

This is a technical review candidate, not artistic acceptance. Native Tree v10 P/B/U and Rock & Ground v05 anatomy, source-supported groups, near A monotone redistribution, depth-aware visibility and separate color geometry remain reusable. The oblique release combines a broad authored gaze territory with measured valley/ridge evidence; it replaces a depth-local part of inherited omission and never changes source terrain. Global top/bottom reserves remain binding. Far B micro texture is disabled.

The canonical 600 × 900 mm data are ink.json.gz and color_intent.json.gz. P{c['panels'][0]}.vectors.json.gz and P{c['panels'][1]}.vectors.json.gz are exact X=300 clips with local coordinates, source arcs and profiles. SVGs are open mean-width centerlines, not machine instructions. Color is virtual intent only; no physical pigment allocation, dilution or printing plan is finalized.

Source and final visibility are recorded in authoring_sources.json.gz and visibility_ledger.json.gz; organization_ledger.json.gz records intermediate domain/ground selection. fields.npz is a reduced diagnostic archive (occupied/depth/retention), not a full-precision generation source. Config and scene JSON, the original verified TIFFs and the pinned reference phase are the reproducible inputs. Private caches are optional same-run accelerators and are not distributed.

{c['physical_note']} Brush width, compression, pressure-to-Z and drying are uncalibrated; no machine runtime is predicted.

Review the middle-to-near receiving passage, dominant/subordinate rock/tree balance, degree of burial and openness, the high internal-seam summit, and virtual color legibility before further development. Nominal masks retain the inherited one-mm/upright-2.5D limitations.

See the complete seasonal handoff under docs/experiments/seasonal_composition_v03/. All inherited PR37/Spring files are read only, and no PR is merged.
'''
    (out/'README.md').write_text(text);(out/'HANDOFF.md').write_text(text)
    (out/'.gitignore').write_text('*.svg\n')
    for path in out.glob('*.svg'):
        path.with_suffix(path.suffix+'.gz').write_bytes(gzip.compress(path.read_bytes(),mtime=0))

