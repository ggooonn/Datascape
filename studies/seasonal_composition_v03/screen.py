"""Eight-panel review with physical gaps and unchanged approved Spring."""
from shared import *
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import gaussian_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import html

OUT=ROOT/'docs/experiments/seasonal_composition_v03'
CASES=[('summer','summer_composition_v03'),('autumn','autumn_composition_v01'),('winter','winter_composition_v01')]
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def source_skyline(occupied):
    valid=occupied.any(axis=0);y=np.argmax(occupied,axis=0).astype(float)+.5;y[~valid]=np.nan
    return y*900/occupied.shape[0]

def boundary(a,b):
    def slope(values):
        good=np.isfinite(values)
        return float(np.polyfit(np.arange(len(values))[good],values[good],1)[0]) if good.sum()>2 else None
    return dict(height_step_mm=float(b[0]-a[-1]),left_slope_dy_dx=slope(a[-35:]),right_slope_dy_dx=slope(b[:35]))

def panel_workload(rows,panels):
    """Distinguish inherited short sources from newly cut seam fragments."""
    originals={r['id']:r for r in rows};result={}
    for local,n in enumerate(panels):
        parts=prior.panel_rows(rows,3+local)
        small=[r for r in parts if length(r)<2.8]
        inherited=[r for r in small if length(originals[r['canonical_source_id']])<2.8]
        result[f'P{n}']=dict(paths=len(parts),length_mm=sum(map(length,parts)),short_panel_fragments=len(small),inherited_short_sources=len(inherited),new_short_seam_fragments=len(small)-len(inherited))
    return result

def write_html(out,items):
    text=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Datascape — Seasonal Composition v03</title><style>body{max-width:1500px;margin:38px auto;padding:0 24px;background:#f2f1eb;color:#20352f;font:16px/1.6 system-ui}h1,h2{line-height:1.15}a{color:#28605a}section{padding:18px 24px;background:white;margin:24px 0}img{width:100%;height:auto;background:white}figure{margin:24px 0}figcaption{font-weight:600;margin-bottom:8px}.note{padding:12px;border-left:4px solid #a17e50;background:#fff9ee}code{font-size:.9em}nav{display:flex;gap:24px;flex-wrap:wrap}</style><h1>Datascape / Summer v03 and provisional Autumn–Winter</h1><p>Technical review candidate from PR37. Artistic acceptance and physical foreground validation remain open.</p><nav><a href="HANDOFF.md">Handoff</a><a href="README.md">Reproduce</a><a href="PRINTING_REVIEW.md">Physical considerations</a><a href="verification.json">Verification</a></nav><p class="note">Approved Spring is unchanged. Each seasonal pair is independent; skyline relationships are provisional and unfitted. Display gaps are 40 mm. No G-code or final physical palette is included.</p>']
    for title,path,caption in items:
        relative=os.path.relpath(path,out)
        uri=html.escape(relative,quote=True)
        text.append('<section><h2>'+html.escape(title)+'</h2><p>'+html.escape(caption)+'</p><figure><figcaption><a href="'+html.escape(relative,quote=True)+'">Open full-resolution image</a></figcaption><img src="'+uri+'" alt="'+html.escape(title,quote=True)+'"></figure></section>')
    text.append('<section><h2>Canonical vectors</h2><p>JSON preserves complete variable profiles; SVGs show open mean-width centerlines. New seasonal outputs use independent canonical geometry, not recolored Spring.</p><ul>')
    for season,name in CASES:
        path='../'+name+'/'
        text.append('<li>'+season.title()+': <a href="'+path+'README.md">notes</a> · <a href="'+path+'ink.json.gz">ink JSON</a> · <a href="'+path+'color_intent.json.gz">color JSON</a> · <a href="'+path+'scene.svg.gz">compressed SVG</a></li>')
    text.append('</ul><p>Middle/far contour drawing appears relatively stable; foreground is less physically verified. A different foreground brush strategy may be needed. This is a production consideration and does not itself change canonical geometry.</p></section></html>')
    (out/'Review.html').write_text(''.join(text))

def run():
    out=OUT;out.mkdir(parents=True,exist_ok=True)
    spring=ROOT/'artworks/spring_v13'
    spring_ink=read(spring/'visible_ink.json.gz')['strokes'];spring_color=read(spring/'visible_color.json.gz')['strokes']
    prior.render(spring_ink,[],out/'spring_ink.png',read(spring/'palette.json'))
    views=read(accepted.BASE/'viewpoint_review.json')
    skylines=[np.array(views['spring_skyline_mm'])]
    images=[spring/'review/approved.png'];ink_images=[out/'spring_ink.png'];names=['Spring approved']
    masks=[accepted_review.occupancy(spring_ink)]
    workloads={'spring':dict(ink=prior.stats(spring_ink),panels=panel_workload(spring_ink,[1,2]))}
    for season,name in CASES:
        p=ROOT/'docs/experiments'/name;c=read(p/'config.json');ink=read(p/'ink.json.gz')['strokes']
        images.append(p/'full.png');ink_images.append(p/'ink.png');names.append(season.title()+' provisional')
        masks.append(accepted_review.occupancy(ink))
        with np.load(p/'fields.npz') as fields:skylines.append(source_skyline(fields['occupied']))
        workloads[season]=dict(ink=read(p/'workload.json')['ink'],color=read(p/'workload.json')['color'],panels=panel_workload(ink,c['panels']))
    actual_c=np.array(next(v['skyline_mm'] for v in views['candidates'] if v['id']=='C_east'))
    if not np.array_equal(skylines[1],actual_c,equal_nan=True):raise ValueError('Summer projected skyline changed')
    panel_colors=['#556454','#557a70','#9b7953','#71838a']
    for output,inputs in [('P1_P8_full.png',images),('P1_P8_ink.png',ink_images)]:
        canvas=Image.new('RGB',(5360,1880),'#e5e3dc');draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype(FONT,26)
        for pair,path in enumerate(inputs):
            with Image.open(path) as source:
                source=source.convert('RGB')
                if abs(source.width/source.height-2/3)>1e-3:raise ValueError('Review image aspect ratio differs from canonical canvas')
                source=source.resize((1200,1800),Image.Resampling.LANCZOS)
                for local in [0,1]:
                    i=pair*2+local;x=i*680
                    canvas.paste(source.crop((local*600,0,(local+1)*600,1800)),(x,65))
                    draw.text((x+16,15),f'P{i+1} / {names[pair]}',font=font,fill=panel_colors[pair])
        png(out/output,canvas)
    with Image.open(out/'P1_P8_full.png') as im:png(out/'P1_P4_full.png',im.crop((0,0,2640,1880)))
    transitions={name:boundary(skylines[i],skylines[i+1]) for i,name in enumerate(['P2_P3','P4_P5','P6_P7'])}
    save(out/'skyline.json',dict(terrain_silhouettes_mm={name:line.tolist() for name,line in zip(['spring','summer','autumn','winter'],skylines)},transitions=transitions,policy='Actual top-down heights before vegetation/mist; 40 mm display gaps; no fitting, translation or panorama claim'))
    fig,ax=plt.subplots(figsize=(20,5))
    for pair,line in enumerate(skylines):
        for local in [0,1]:
            offset=(pair*2+local)*340;x=np.arange(300)+.5+offset
            ax.plot(x,line[local*300:(local+1)*300],color=panel_colors[pair],lw=1.35)
    for i in range(7):ax.axvspan(i*340+300,(i+1)*340,color='#e3e1d9')
    ax.set(xlim=(0,2680),ylim=(700,40),ylabel='Top-down painted Y (mm)',title='P1–P8 terrain skylines / actual heights, natural within pairs, unfitted across seasons')
    ax.set_xticks([i*340+150 for i in range(8)],[f'P{i+1}' for i in range(8)]);ax.grid(axis='y',alpha=.2)
    fig.tight_layout();figure_png(fig,out/'skyline_P1_P8.png');plt.close(fig)
    density=np.full((900,2680),np.nan);metrics={};xcurves=[]
    for pair,mask in enumerate(masks):
        smooth=gaussian_filter(mask.astype(float),sigma=12)
        for local in [0,1]:
            i=pair*2+local;part=mask[:,local*300:(local+1)*300];density[:,i*340:i*340+300]=smooth[:,local*300:(local+1)*300]
            metrics[f'P{i+1}']=dict(ink_centerline_cell_occupancy=float(part.mean()),cells_without_ink_centerline=float(1-part.mean()))
            xcurves.append((i*340+np.arange(300)+.5,part.mean(axis=0)))
    fig,axes=plt.subplots(2,1,figsize=(20,8),gridspec_kw=dict(height_ratios=[3,1]))
    im=axes[0].imshow(density,extent=[0,2680,900,0],cmap='YlGnBu',vmin=0,vmax=.35,aspect='auto');fig.colorbar(im,ax=axes[0],label='12 mm smoothed 1 mm ink-line cell occupancy',fraction=.018)
    axes[0].set_title('Density / whitespace rhythm — identical metric for every season');axes[0].set_ylabel('Painted Y (mm)')
    for i,(x,y) in enumerate(xcurves):axes[1].plot(x,y,c=panel_colors[i//2],lw=1)
    for ax in axes:
        ax.set_xlim(0,2680)
        for i in range(7):ax.axvspan(i*340+300,(i+1)*340,color='#e4e2da')
        ax.set_xticks([i*340+150 for i in range(8)],[f'P{i+1}' for i in range(8)])
    axes[1].set_ylabel('Column line occupancy');fig.tight_layout();figure_png(fig,out/'density_whitespace_P1_P8.png');plt.close(fig)
    save(out/'density_whitespace.json',dict(panels=metrics,metric='1 mm all-touched ink-centerline cells and column means; no physical width, pigment coverage or drying inference',display_smoothing_mm=12))
    save(out/'workload.json',workloads)
    table=['| Season | Ink paths | Ink length (m) |','| --- | ---: | ---: |']
    for season,d in workloads.items():
        s=d['ink'];count=s.get('strokes',s.get('canonical_strokes'));distance=s.get('length_mm',s.get('drawing_length_mm'));table.append(f'| {season.title()} | {count:,} | {distance/1000:.3f} |')
    seams=['| Panel | Ink fragments | Total short fragments | Inherited short sources | New short seam fragments |','| --- | ---: | ---: | ---: | ---: |']
    for d in workloads.values():
        for name,s in d['panels'].items():seams.append(f'| {name} | {s["paths"]} | {s["short_panel_fragments"]} | {s["inherited_short_sources"]} | {s["new_short_seam_fragments"]} |')
    (out/'PRINTING_REVIEW.md').write_text('# Physical printing awareness / no machine program\n\n'+'\n'.join(table)+'\n\nThese are centerline distances and atomic path counts, not execution times, reload counts or contacts after scheduling. Middle/far contour drawing appears relatively stable. Foreground is less physically verified; native large tree/rock interfaces and dense small contacts may require a different brush strategy from middle/far terrain. Physical testing must decide widths, compression, pressure, loading and drying. This consideration does not automatically change canonical geometry. No G-code or final printing plan is generated.\n\n'+'\n'.join(seams)+'\n\nInherited short Spring sources are distinguished from newly created seam fragments. Do not alter approved Spring or silently discard exact panel-cut fragments. No physical treatment of these fragments is chosen here.\n')
    transition_text='\n'.join(f'- {name.replace("_"," → ")}: next skyline begins {r["height_step_mm"]:+.0f} mm in top-down coordinates; endpoint slopes {r["left_slope_dy_dx"]:+.3f} and {r["right_slope_dy_dx"]:+.3f}.' for name,r in transitions.items())
    notes='''# Seasonal composition v03 / handoff

Actual Summer v03, Autumn P5/P6 and Winter P7/P8 canonical vectors and previews have been generated on the new branch `feat/summer-v03-seasonal-composition-v01` from PR37 `a6ce842cfb894ce35e15332f3b6c6154254708ec`. Approved Spring and every inherited file remain unchanged. This is a provisional artistic review checkpoint, not acceptance or production readiness.

Summer keeps C_east and the existing mountain source structure. Its middle release now follows a terrain-evidenced path inside an authored oblique gaze territory. Three field hypotheses are recorded; only the selected recipe generates the delivered final scene. The left promontory and subordinate relays use larger native tree/rock groups with shared contacts, unequal source depths, overlap and partial exclusion. The residual middle horizontal rhythm and ground/rock/canopy balance remain open to visual review.

Autumn uses the existing A_south view, unequal thinning, retained pine foliage and a larger exposed right support. Winter uses B_northwest, incomplete B/U crowns, residual pine, left shelter, middle bedrock and a longer right/P8 rest. These are independently generated seasonal structures, not recolorings or recovered copies of unavailable older drafts. Colors are virtual territories; no final pigments or printing plan are allocated.

## Seasonal transitions

'''+transition_text+'''

Negative height steps mean the next skyline is higher on the paper. P2–P3 retains the visible slope reversal; P4–P5 has a substantial reset and is an explicit artistic review item. P6–P7 has the smaller winter reset. No scene is shifted, fitted or deformed to erase these differences. Each pair retains its natural projected terrain continuity and independent pictorial identity.

## Review files

Open Review.html, P1_P8_full.png, P1_P8_ink.png, skyline_P1_P8.png and density_whitespace_P1_P8.png. The full horizontal comparison uses 5360 × 1880 pixels at 2 px/mm, eight 300 × 900 mm panels and seven 40 mm gaps. No painted content is stretched or deleted. Spring's approved image is displayed unchanged apart from faithful display-scale resampling; the ink-only Spring view renders its frozen canonical vectors.

Summer's directory contains full/P3/P4/installed/layer reviews, summer_v02_v03.png, middle_comparison.png, foreground_comparison.png, source-field hypotheses and measured group contacts. Each new season has complete canonical ink/color/panel JSON, source and visibility ledgers, configs, actual source camera, statistics, verification and full/panel/layer previews. Authoritative variable artistic profiles live in JSON. SVGs are mean-width open centerlines; compressed copies are in Git and ordinary copies are in the download package.

## Reproduce and continue

Read studies/seasonal_composition_v03/README.md. Entry points are scenes.py for each season, screen.py for the combined review, and verify.py for source/profile/panel readback. recipes.py records requested artistic controls; every scene publishes requested_config.json and final supported config.json. shared.py preserves accepted catalog and source-depth machinery, while flow.py implements the new release. Original SHA-verified MASTER/VEG TIFFs and PR37's bound phase are required; no new extraction or hidden notebook state is needed. Private caches are optional and excluded from delivery.

Read verification.json for the exact scope of checks and reproduction evidence; do not infer full no-cache vector-byte reproduction from a partial replay. Continue from this new branch and the exact commit in the downloadable PUBLICATION.json. Review Summer's remaining middle passage and foreground grouping first, then the seasonal skyline resets and density balance. Do not merge any PR without explicit approval.

Middle/far contour drawing appears relatively stable, while foreground remains less physically verified. A future physical test may require different brush strategies for those roles. That is a production consideration, not a canonical geometry change. Brush widths, pressure-to-Z, ink concentration, pigment slots, loading and drying are uncalibrated. No G-code is included.
'''
    (out/'HANDOFF.md').write_text(notes);(out/'README.md').write_text(notes)
    items=[('P1–P8 full composition',out/'P1_P8_full.png','Frozen Spring and three actual seasonal pairs; 40 mm installation gaps.'),('P1–P8 ink',out/'P1_P8_ink.png','Canonical ink only, at the same display scale.'),('Terrain skyline relationship',out/'skyline_P1_P8.png','Natural within pairs, provisional and unfitted across seasons.'),('Density and whitespace',out/'density_whitespace_P1_P8.png','Ink-line cells only; this is not physical wet coverage.'),('Summer v02 / v03',ROOT/'docs/experiments/summer_composition_v03/summer_v02_v03.png','Same camera; actual new omission and foreground group organization.'),('Summer middle release',ROOT/'docs/experiments/summer_composition_v03/middle_comparison.png','Matched actual-vector crops.'),('Summer foreground',ROOT/'docs/experiments/summer_composition_v03/foreground_comparison.png','Larger native groups and shared source supports.'),('Autumn P5/P6',ROOT/'docs/experiments/autumn_composition_v01/full.png','Unequal thinning and exposed structure; provisional color.'),('Winter P7/P8',ROOT/'docs/experiments/winter_composition_v01/full.png','Residual pine, incomplete crowns and a long right rest.')]
    write_html(out,items)
    print('Eight-panel review complete',transitions,flush=True)
    return out

if __name__=='__main__':run()
