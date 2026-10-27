"""Source-width color/ink previews and a self-contained physical review report."""
from collections import Counter, defaultdict
from pathlib import Path
from math import dist
import base64, html, io, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from .spring_color_execution import read, save, ROOT, sha

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def render(path, selected, ink, palette, *, mode='primary', crop=(300,0,600,900), scale=2,
           include_ink=True, diagnostic=None, d4_ids=()):
    x0,y0,x1,y1=crop;dpi=120
    fig=plt.figure(figsize=((x1-x0)*scale/dpi,(y1-y0)*scale/dpi),dpi=dpi,facecolor='white')
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    ink_events=read(ROOT/'docs/spring_panels_contact20_v01/review/P2.execution_manifest.json.gz')['events']
    tones={e['source']:e['ink'] for e in ink_events}
    def lines(xy,width,opacities,color,fallback,order):
        xy=np.asarray(xy);n=len(xy)
        if n<2:return
        segments=np.stack([xy[:-1],xy[1:]],axis=1)
        w=np.asarray(width if isinstance(width,list) else [width]*n)
        if len(w)!=n:w=np.full(n,fallback)
        alpha=np.asarray(opacities if isinstance(opacities,list) else [opacities]*n)
        if len(alpha)!=n:alpha=np.full(n,.4)
        rgba=np.tile(to_rgba(color),(n-1,1));rgba[:,3]=np.clip((alpha[:-1]+alpha[1:])/2,0,1)
        lc=LineCollection(segments,linewidths=(w[:-1]+w[1:])/2*scale*72/dpi,
                          colors=rgba,zorder=order,capstyle='round',joinstyle='round')
        ax.add_collection(lc)
    if include_ink:
        for i,r in enumerate(ink):
            xy=np.asarray(r['xy_mm'])
            if xy[:,0].max()<x0 or xy[:,0].min()>x1 or xy[:,1].max()<y0 or xy[:,1].min()>y1:continue
            alpha=.42 if tones.get(i)=='LIGHT_INK' else .86
            lines(xy,r.get('width_profile_mm',r['width_mm']),alpha,'#151a18',r['width_mm'],1)
    for u in selected:
        if mode=='baseline' and not u.get('baseline_all',False):continue
        r=u['rich'];xy=np.asarray(r['xy_mm'])
        if xy[:,0].max()<x0 or xy[:,0].min()>x1 or xy[:,1].max()<y0 or xy[:,1].min()>y1:continue
        slot=u['legacy_slot'] if mode=='baseline' else u['physical_slot']
        if mode=='D4_old' and u['legacy_slot']=='D4':slot='D4'
        if mode=='D4_restrained' and u['id'] in d4_ids:slot='D4'
        color=palette['slots'][slot]['preview_hex']
        if diagnostic=='roles':color={'base':'#93a99c','structural':'#326c56','accent':'#e6b540'}[u['physical_role']]
        elif diagnostic=='overlap':color='#c94d3e' if u['crowded'] else '#5b9a83'
        elif diagnostic=='D4':color='#a2432b' if u['id'] in d4_ids else '#aab5ae'
        # The swatches and original expressive widths/alpha are display proxies.
        # Compression is not converted to physical width or pigment opacity.
        alpha=r.get('opacity_profile',r.get('preview_opacity',.4))
        if not isinstance(alpha,list):alpha=[alpha]*len(xy)
        alpha=[min(.78,max(.16,a)*1.25) for a in alpha]
        lines(xy,r.get('width_profile_mm',r['width_mm']),alpha,color,r['width_mm'],2)
    fig.savefig(path,dpi=dpi,facecolor='white');plt.close(fig)


def sheet(path, paths, labels, *, width=420,height=1250,title='Spring P2 / display proxies, not a wet-print prediction'):
    result=Image.new('RGB',(width*len(paths),height+90),'#f3f4ef');draw=ImageDraw.Draw(result)
    draw.text((16,12),title,font=ImageFont.truetype(FONT,19),fill='#243e33')
    for i,(p,label) in enumerate(zip(paths,labels)):
        draw.text((i*width+14,49),label,font=ImageFont.truetype(FONT,16),fill='#243e33')
        with Image.open(p) as im:
            im=im.convert('RGB');im.thumbnail((width-16,height-10));result.paste(im,(i*width+(width-im.width)//2,85))
    result.save(path)


def mixing_report(commands,selected,edges,summary):
    pos=(0,900,35);seconds=0.;begin={};end={}
    for c in commands:
        if c.kind=='move':seconds+=dist(pos,c.xyz)/c.feed_mm_min*60;pos=c.xyz
        elif c.kind=='dwell':seconds+=c.seconds
        elif c.action=='source_begin':begin[c.source_id]=seconds
        elif c.action=='source_complete':end[c.source_id]=seconds
    records=[]
    for a,b in edges:
        u,v=selected[a],selected[b]
        if u['physical_slot']==v['physical_slot']:continue
        delay=begin[v['id']]-end[u['id']]
        same=u['group']==v['group'];wet=summary['wet_opportunity']['group']
        intent='dry-over-dry target; verify paper by inspection'
        if same and u['physical_slot']=='C1' and v['physical_slot']=='A5' and u['group']==wet:
            intent='controlled overlap opportunity; actual wetness unmeasured'
        records.append(dict(under_source=u['id'],over_source=v['id'],under_slot=u['physical_slot'],over_slot=v['physical_slot'],
            group=u['group'] if same else None,commanded_feed_lag_seconds=delay,intent=intent,
            measured_dry_or_wet_state=None))
    pairs=defaultdict(list)
    for r in records:pairs[r['under_slot']+' -> '+r['over_slot']].append(r['commanded_feed_lag_seconds'])
    return dict(records=records,per_pair_commanded_lag_seconds={k:dict(count=len(v),minimum=min(v),median=float(np.median(v)),maximum=max(v)) for k,v in sorted(pairs.items())},
        intervals_include_programmed_wash_and_load=True,manual_delays_included=False,
        pigment_mixing_ratio=None,drying_time_calibrated=False,
        note='Feed-time intervals are model lower bounds, not pigment or hanji drying measurements. Full-panel completion can be long enough for underlayers to dry; no automatic dry guarantee.')


def svg_export(path,units,ink,palette):
    # Real vector layers, with source IDs and authored paths, in global drawing
    # coordinates. The SVG viewBox clips to P2; no coordinate translation.
    from xml.sax.saxutils import escape
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="900mm" viewBox="300 0 300 900">',
        '<metadata>Source-width display proxy; not calibrated brush/pigment behavior</metadata>',
        '<rect x="300" y="0" width="300" height="900" fill="white"/>']
    for slot in ['INK']+sorted(set(u['physical_slot'] for u in units)):
        lines.append('<g id="'+slot+'">')
        records=[(r,r['id'],'#151a18',r.get('preview_opacity',.5)) for r in ink] if slot=='INK' else [(u['rich'],u['id'],palette['slots'][slot]['preview_hex'],u['rich'].get('preview_opacity',.4)) for u in units if u['physical_slot']==slot]
        for r,ident,color,alpha in records:
            points=' '.join(f'{x:.9f},{y:.9f}' for x,y in r['xy_mm'])
            lines.append(f'<polyline data-source-id="{escape(ident)}" points="{points}" fill="none" stroke="{color}" stroke-width="{r["width_mm"]:.9f}" opacity="{min(.8,alpha):.6f}" stroke-linecap="round"/>')
        lines.append('</g>')
    lines.append('</svg>');path.write_text('\n'.join(lines))


def tables(out,summary,palette):
    rows=read(out/'pigment_slots.json')
    with (out/'pigment_slots.csv').open('w',newline='') as f:
        import csv
        fields=['slot','name','source_count','drawing_mm','contacts','load_count','batch_visits']
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in fields} for r in rows)
    with (out/'source_to_slot_replacements.csv').open('w',newline='') as f:
        import csv
        w=csv.writer(f,lineterminator='\n');w.writerow(['source_slot','physical_slot','source_count','drawing_mm'])
        for k,r in read(out/'source_to_slot_replacements.json').items():
            a,b=k.split(' -> ');w.writerow([a,b,r['count'],r['length_mm']])


def make_review(out,context,units,selected,order,batches,edges,commands,palette,ink,summary,d4):
    print('Rendering source-width previews and overlap report',flush=True)
    out=Path(out);ordered=[selected[i] for i in order]
    render(out/'P2_PR35_color_primary.png',ordered,ink,palette)
    render(out/'P2_color_only.png',ordered,ink,palette,include_ink=False)
    render(out/'P2_PR35_ink_only.png',[],ink,palette)
    baseline=[u|dict(baseline_all=True) for u in sorted(units,key=lambda u:u['rank'])]
    render(out/'P2_S3a_legacy_full.png',baseline,ink,palette,mode='baseline')
    sheet(out/'P2_comparison.png',[out/'P2_PR35_ink_only.png',out/'P2_S3a_legacy_full.png',out/'P2_PR35_color_primary.png'],
        ['PR35 ink on physical P2','Original full S3a color proxy','Selected six-slot experiment'])
    # Cumulative sequence follows real pigment batches, not a fictitious set of
    # three rigid role passes. Role-only views are separate diagnostic images.
    cumulative=[];sequence_paths=[];sequence_labels=[]
    for b in batches:
        cumulative.extend(selected[i] for i in b['unit_indices']);name=f'sequence_{b["index"]+1:02d}_{b["slot"]}.png'
        render(out/name,cumulative,ink,palette,scale=1.2);sequence_paths.append(out/name);sequence_labels.append(f'{b["index"]+1}. {b["slot"]} / {len(b["unit_indices"])} sources')
    sheet(out/'P2_sequence.png',sequence_paths,sequence_labels,width=250,height=750,title='Actual cumulative pigment order / source-width display proxy')
    for role in ['base','structural','accent']:
        render(out/('role_'+role+'.png'),[u for u in ordered if u['physical_role']==role],ink,palette)
    sheet(out/'P2_roles.png',[out/('role_'+r+'.png') for r in ['base','structural','accent']],['Base / underlays','Structure / grouped cores','Accents / fresh tips'])
    slotpaths=[];slotlabels=[]
    for slot in summary['pigment_order']:
        if slot in slotlabels:continue
        path=out/('slot_'+slot+'.png');render(path,[u for u in ordered if u['physical_slot']==slot],ink,palette,include_ink=False,scale=1.4)
        slotpaths.append(path);slotlabels.append(slot)
    sheet(out/'P2_pigment_slots.png',slotpaths,slotlabels,width=250,height=750,title='Actual pigment slot allocations / display swatches are uncalibrated')
    render(out/'P2_overlap_map.png',ordered,ink,palette,diagnostic='overlap')
    render(out/'P2_role_map.png',ordered,ink,palette,diagnostic='roles')
    d4_ids={u['id'] for u in d4}
    paths=[]
    for label,mode in [('replacement','primary'),('legacy_D4','D4_old'),('restrained_D4','D4_restrained')]:
        path=out/('D4_'+label+'.png');render(path,ordered,ink,palette,mode=mode,crop=(320,600,600,895),scale=2.5,d4_ids=d4_ids);paths.append(path)
    sheet(out/'P2_D4_comparison.png',paths,['Primary pale replacement','Selected sources: legacy D4','Restricted structural D4'],width=680,height=740,
          title='Same frozen geometry / no display-alpha to dilution conversion')
    for label,crop in [('foreground',(330,650,600,895)),('middle',(320,390,600,650)),('far',(320,180,600,390))]:
        paths=[]
        for name,us,mode in [('legacy',baseline,'baseline'),('primary',ordered,'primary')]:
            path=out/(label+'_'+name+'.png');render(path,us,ink,palette,mode=mode,crop=crop,scale=3);paths.append(path)
        sheet(out/(label+'_comparison.png'),paths,['Original full S3a display proxy','Selected physical-slot experiment'],width=760,height=int((crop[3]-crop[1])/(crop[2]-crop[0])*730)+25)
    mixing=mixing_report(commands,selected,edges,summary);save(out/'overlap_and_mixing_intent.json.gz',mixing)
    svg_export(out/'P2_layers.svg',ordered,ink,palette)
    # Exact schedule/runtime graphics are ordinary plots, not generated imagery.
    comparison=read(out/'S3a_comparison.json')
    fig,ax=plt.subplots(figsize=(10,4),constrained_layout=True)
    names=[k for k in comparison if k!='attribution_seconds'];values=[comparison[n]['modeled_seconds']/60 for n in names]
    if names:
        ax.barh(range(len(names)),values,color=['#b6c2b9','#91ab9b','#709485','#356e5a'][:len(names)])
        ax.set_yticks(range(len(names)),[n.replace('_',' ') for n in names]);ax.invert_yaxis();ax.set_xlabel('Modeled minutes / assumed JD0.01 / no drying or manual time')
        for i,v in enumerate(values):ax.text(v+.4,i,f'{v:.1f}',va='center')
    fig.savefig(out/'runtime_comparison.png',dpi=160);plt.close(fig)
    tables(out,summary,palette)
    slots=read(out/'pigment_slots.json');primary=summary['primary']
    header='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Spring P2 Color Execution v01</title><style>body{font:16px/1.65 system-ui;color:#20392f;background:#f4f5f0;max-width:1450px;margin:0 auto;padding:32px}h1{font-size:36px}h2{margin-top:48px}img{max-width:100%;display:block;background:white}.note{padding:18px;background:#ebe2cf;border-left:4px solid #a97445}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:9px;border-bottom:1px solid #c9d2c8}a{color:#27694b}pre{white-space:pre-wrap;background:white;padding:18px}details{margin:18px 0}code{overflow-wrap:anywhere}</style><h1>Spring P2 · Color Execution v01</h1>'''
    text=header+f'<p>{summary["selected_sources"]:,} complete original color sources · {primary["drawing_length_mm"]/1000:.2f} m · {primary["pigment_changes"]} pigment changes · {primary["same_pigment_reloads"]} same-pigment reloads · {primary["modeled_seconds"]/60:.1f} modeled minutes.</p>'
    text+='''<p class="note"><b>Complete numerical physical-review candidate. Color pressure and station swept clearance remain unmeasured.</b> This first job is for the existing PR35 ink P2 only. It adds no PR39/41 ink-deferred geometry. Keep global G54 X300–600 and the original panel registration. Paper touch Z10, approach15, hover20, global station35, start0/900/35, terminal800/800/35/M2. Do not add the backing thickness again. No routine M0. Review the separate trial curve and station paths before contact.</p>'''
    def image(name,heading,description=''):
        nonlocal text
        raw=base64.b64encode((out/name).read_bytes()).decode()
        text+='<h2>'+heading+'</h2><p>'+description+'</p><img loading="lazy" src="data:image/png;base64,'+raw+'">'
    image('P2_comparison.png','PR35 ink and the first overprint','Same original projection and expressive source widths. Ink display uses the PR35 light/dark allocation. Slot swatches and source alpha are uncalibrated display proxies, never a pigment recipe or brush-width prediction.')
    image('P2_sequence.png','Actual pigment sequence','The physical roles share coherent pigment batches. No material switch is inserted after every small vegetation group. Long canonical terrain episodes and complete rays keep their direction; omitted short episodes receive no artificial connector.')
    image('P2_roles.png','Base, structure and accents','Roles express layering intent. Some fresh C2 strokes bind groups and others keep protruding tips visible; their shared pigment avoids a separate global accent-brush stage.')
    text+='<h2>Physical palette and loading</h2><table><tr><th>Slot</th><th>Role / source swatch</th><th>Sources</th><th>Drawing m</th><th>Loads</th><th>Visits</th></tr>'
    for r in slots:text+=f'<tr><td>{r["slot"]}</td><td>{r["name"]}; {html.escape(str(r["roles"]))}</td><td>{r["source_count"]}</td><td>{r["drawing_mm"]/1000:.3f}</td><td>{r["load_count"]}</td><td>{r["batch_visits"]}</td></tr>'
    text+='</table><p>600mm distance-only replenishment is inherited from the color backend. Counters reset on a pigment change/load; a complete source is atomic, with any threshold overrun logged. Same-pigment reload does not wash. Actual changes wash in the new container, touch PURGE, rewet, then load the selected slot. No measured dilution or mixing ratios are claimed.</p>'
    image('P2_pigment_slots.png','Per-slot source geometry')
    image('P2_D4_comparison.png','D4 replacement and a restrained structural alternative',f'Primary D4 use is zero. The offline alternative restores only {len(d4)} selected long near rock/ground sources ({sum(u["length_mm"] for u in d4):.1f}mm). It is not an alpha-based dilution, and D5 is not substituted indiscriminately. Actual source-to-slot replacements are in the JSON/CSV ledgers.')
    image('P2_overlap_map.png','Existing PR35 ink overlap audit','Red marks identify sources with a crowded authored-width ink proxy; green marks are other selected canonical color support. This is not a measured spread/occlusion model. The machine manifest records omissions and explicit 0.65 execution-compression factors while preserving all original artistic pressure values.')
    image('foreground_comparison.png','Foreground review')
    image('middle_comparison.png','Middle-distance review')
    image('far_comparison.png','Far-distance review')
    image('runtime_comparison.png','S3a comparison with controlled mechanics','All scenarios use the same new color trial curve, station/wash/lip/cleanup mechanics and 600mm reload policy. These are reconstructed comparison workloads, not byte-for-byte historical runs. Separate content reduction, slot consolidation and the cost of protected layering; actual switching savings must not be confused with omitted drawing.')
    text+='<details><summary>Numerical comparison and attribution</summary><pre>'+html.escape(json.dumps(comparison,indent=2))+'</pre></details>'
    text+='<h2>Overlap, mixing and drying</h2><p>The local dependency graph protects pale support before grouped color cores, jade before fresh tips, and original within-slot overlapping order. It is an explicit artistic execution graph based on authored display footprints; it does not claim to recover every original 2.5D occlusion or wet-brush footprint. Selected C1/A5 body overlaps are opportunities for related-pigment interaction. Feed-time lags include washing and loading; pigment wetness, hanji absorption and actual dry-over-dry behavior must be observed. Long global batches often imply dry layering. For a fully dry layer, use the independent stage files and inspect the paper between them.</p>'
    text+='<details><summary>Actual cross-pigment lag ranges, seconds</summary><pre>'+html.escape(json.dumps(mixing['per_pair_commanded_lag_seconds'],indent=2))+'</pre></details>'
    text+='''<h2>Recommended first-print sequence</h2><ol><li>Keep the PR35 sheet registration. Check the repaired machine/homing state, current G54 readback, G92/TLO zero and clean conditioned small Baegunmo. The inherited start is G54 0/900/35; do not assume an older Y898 home. Inspect the workpiece alignment at X300 and X600 without marking it.</li><li>Run the complete AIR with the mounted holder/brush only after inspecting its Z35 envelope. It reproduces every paper and station XY command at Z35, including palette circles and lip paths. AIR cannot verify immersion, bottom or lip contact clearance.</li><li>On spare backed hanji, review the numerical COLOR_RESPONSE_COUPON and station-specific contact trace. Measure color delivery, touch, compression, taper and dry appearance. The trial curve is 0–2.4mm compression and is independent of ink. If its response is wrong, edit only the color trial configuration and regenerate all affected files.</li><li>Verify actual palette level, floor/immersion, circle radius5, holder/rim and Z28 lip approach. Palette center liquid6/dip5/floor1/exit8 are inherited nominal references; the new water uses center840/45/contact20/approach25 and a distinct vertical container grammar. Inspect every connecting swept path. No new physical measurement is fabricated.</li><li>Choose either COMPLETE, or the four separated stages in numeric order. Never run both on the same sheet. Each separated file includes full loading/terminal cleanup and returns to800/800/35; manually restore the known start pose at Z35, inspect dryness and condition the brush before the next file without changing work registration.</li><li>Inspect early pale mineral support and coherent growth groups before committing to all stronger color. Compare D4 alternatives on a separate sample; do not add the offline D4 paths over the completed primary merely to compare them.</li></ol>'''
    text+='''<h2>Later dual-brush P2</h2><p>The compatibility manifest uses the published PR42 recommended B, branch spring/p2-a-brush-hierarchy-v01 at cf010e6f41de36baee83ed7a04cacbc3f0931e23. Its642 color-deferred sources are already ink on this first PR35 sheet, so none is added here. The224 fine-brush sources, including12 selective A and10 terrain-support transfers, are listed as ink-executed responsibilities for the future matched dual-brush sheet;985 remain main. Use the current review_role field: PR42 retains legacy variant_B values from PR39, which would give the wrong current brush counts. The original color vectors remain intact; selected color geometry, overlap factors and deferred-ink responsibilities need a second review after the first physical result. Fine-brush color is an offline list only; no unmeasured fine contact program blocks the primary small-brush job.</p>
<h2>Feedback for the second iteration</h2><ul><li>Record actual pigment slots and prepared liquid levels; photograph wet and fully dry color with a neutral reference.</li><li>Record whether A2/A4 remain pale enough for the ink, and whether A5/C3/C2 form a celadon-to-fresh-green hierarchy.</li><li>Mark excessive merges, isolated dots, dry tails, weak long terrain flow, and areas that should stay ink-only using source IDs or crop coordinates.</li><li>Record C1/A5 overlap wetness at the actual time, color contamination after washes, replenishment quality before/after600mm and measured total runtime.</li><li>Compare mineral replacement against the restrained D4 sample before assigning any D4 to the next sheet.</li></ul>
<p>All time estimates use recorded acceleration references and assumed junction deviation0.01/full lookahead, include programmed stations/dwells and terminal cleaning, and exclude manual setup/drying and real streaming/brush effects. Offline verification is not a machine safety certificate.</p></html>'''
    (out/'Review.html').write_text(text)
