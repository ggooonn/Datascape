"""Authored-width concentration/layer diagnostics; no inferred small-brush width."""
from pathlib import Path
from collections import Counter
import base64,io,json,os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from PIL import Image,ImageDraw,ImageFont


def image_save(image,path):
    b=io.BytesIO();image.save(b,format='PNG');data=b.getvalue()
    with Image.open(io.BytesIO(data)) as check:check.load()
    p=Path(path);t=p.with_suffix('.pending');t.write_bytes(data);t.replace(p)


def render(path,rows,fs,events,bounds=(0,0,600,900),scale=2):
    x0,y0,x1,y1=bounds;lines=[];widths=[];colors=[]
    for e in events:
        i=e['source'];r=rows[i];xy=np.asarray(r['xy_mm']);w=np.asarray(r.get('width_profile_mm',[r['width_mm']]*len(xy)))
        if xy[:,0].max()<x0 or xy[:,0].min()>x1 or xy[:,1].max()<y0 or xy[:,1].min()>y1:continue
        slot=e.get('ink','BASE');alpha={'LIGHT_INK':.42,'DARK_INK':.86,'BASE':.82}[slot]
        rgb=(.14,.19,.21) if slot=='LIGHT_INK' else (0,0,0)
        lines.extend(np.stack([xy[:-1],xy[1:]],axis=1));widths.extend((w[:-1]+w[1:])/2);colors.extend([(*rgb,alpha)]*(len(xy)-1))
    fig=plt.figure(figsize=((x1-x0)*scale/150,(y1-y0)*scale/150),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    ax.add_collection(LineCollection(lines,linewidths=np.array(widths)*scale*72/150,colors=colors,capstyle='round',joinstyle='round'))
    b=io.BytesIO();fig.savefig(b,format='png',dpi=150,facecolor='white');plt.close(fig)
    with Image.open(io.BytesIO(b.getvalue())) as im:image_save(im.copy(),path)


def sheet(out,paths,labels,name,cell=(500,775)):
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';cw,ch=cell
    image=Image.new('RGB',(cw*len(paths),ch+85),'#f4f4ed');d=ImageDraw.Draw(image)
    d.text((15,10),'Spring INK / authored widths only / no physical brush-width prediction',font=ImageFont.truetype(font,19),fill='#17382e')
    for k,(p,label) in enumerate(zip(paths,labels)):
        d.text((k*cw+12,53),label,font=ImageFont.truetype(font,16),fill='#18352e');im=Image.open(p).convert('RGB');im.thumbnail((cw-20,ch-25));image.paste(im,(k*cw+(cw-im.width)//2,85))
    image_save(image,out/name)


def render_review(out,rows,fs,plans,report):
    out=Path(out);base=[dict(source=i,ink='BASE') for i in range(len(rows))]
    for name,events in [('baseline',base),('single_pass',plans['SINGLE_PASS']['events']),('selective_layered',plans['SELECTIVE_LAYERED']['events'])]:render(out/(name+'.png'),rows,fs,events)
    sheet(out,[out/(n+'.png') for n in ['baseline','single_pass','selective_layered']],['Canonical ink control','Light / dark single pass','Selected light repeats'], 'comparison_full.png')
    extras=[e['source'] for e in plans['SELECTIVE_LAYERED']['events'] if e['pass_index']]
    selected=max(extras,key=lambda i:fs[i]['length_mm']) if extras else 0
    xy=np.array(rows[selected]['xy_mm']);center=xy.mean(axis=0);x0=float(np.clip(center[0]-70,0,460));y0=float(np.clip(center[1]-65,0,770))
    regions={'layered_terrain':(x0,y0,x0+140,y0+130),'trees_rocks':(350,650,590,875),'middle_detail':(320,430,540,630)}
    for kind,bounds in regions.items():
        paths=[]
        for name,events in [('baseline',base),('single_pass',plans['SINGLE_PASS']['events']),('selective_layered',plans['SELECTIVE_LAYERED']['events'])]:
            p=out/(kind+'_'+name+'.png');render(p,rows,fs,events,bounds,3);paths.append(p)
        sheet(out,paths,['Canonical control','Single pass','Selected repeats'],kind+'_comparison.png',(650,650))
    def img(n):return 'data:image/png;base64,'+base64.b64encode((out/n).read_bytes()).decode()
    allocation=report['allocation'];jobs=report['jobs'];rows_html=[]
    for name,j in jobs.items():rows_html.append('<tr><td>'+name+'</td><td>'+str(j['source_occurrences'])+'</td><td>'+f"{j['runtime']['models']['configuration_reference']['acceleration_sensitive_seconds']/60:.2f}"+'</td><td>'+str(j['M0_count'])+'</td></tr>')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Spring Physical Ink Refinement v01</title><style>body{font:16px/1.6 system-ui;max-width:1250px;margin:auto;padding:25px;background:#f6f5f0;color:#21372e}img{max-width:100%}pre{white-space:pre-wrap;background:#e7eae2;padding:15px}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #aaa}.gate{background:#f0dfcb;padding:15px}</style><h1>Spring Physical Ink Refinement v01</h1>
<p class="gate"><b>Complete numerical review files, NOT machine authorization.</b> Small Baegunmo paper first-touch G54 Z10, approach15, hover20 on operator-confirmed3mm wooden backing; no added substrate offset. PR32 compression is unchanged. Small-brush safe compression and new-container bottom/holder/connecting clearance remain unverified. INK programs begin with a calibration M0; this is not a safety interlock. AIR is all Z35, still requiring actual elevated swept-clearance and registration checks.</p>
<h2>Matched geometry and concentration/pass diagnostics</h2><p>All original3345 ink strokes/69101 pressures remain unchanged. Widths below are authored source widths. Light/dark display alpha .42/.86 is illustrative: no new small-brush width, spreading, concentration or physical pigment response is invented. Additional light passes are explicit repeats of34 original middle/far paths. No near repeats, no dark double passes.</p>'''
    html+='<img src="'+img('comparison_full.png')+'">'
    for kind in regions:html+='<h3>'+kind.replace('_',' ')+'</h3><img src="'+img(kind+'_comparison.png')+'">'
    html+='<h2>Original-workload allocation</h2><pre>'+json.dumps(allocation,indent=2)+'</pre>'
    html+='<h2>Complete files and assumed runtime</h2><p>Minutes use inherited configuration-reference acceleration and ASSUMED junction deviation .01 with full lookahead. Dwell/stations/contact are included; manual M0 delay, paper drying, actual controller behavior and physical widths are not measured.</p><table><tr><th>Program</th><th>Source occurrences</th><th>Modeled minutes</th><th>M0</th></tr>'+''.join(rows_html)+'</table>'
    html+='''<h2>Physical execution policy</h2><p>800mm OR12 actual paper engagements trigger replenishment at intact original-source/gesture boundaries; both counters reset on loading. Two independent ink budgets are logged. A15-contact comparison is provided separately. Three exact shared-endpoint D joins remove three engagements without adding XY. No vegetation dots, textures, clipped/mist gaps or unrelated paths are joined. Existing sharp turns remain continuous; new positive-gap connectors require explicit shared junction provenance and containment in authored display support.</p>
<p>Spatial nearest-contour A parity alternates light/light, never light/dark stripes. Protected footprint/source-owner dependencies can constrain the phases. This is not proof of drying or a complete authoritative occlusion DAG. The near-to-far preference applies only among currently eligible sources. Added passes finish before their protected later original successors.</p>
<h2>New station model and review order</h2><p>Run no job from an unknown coordinate state. Review STATIONS_AIR_FIRST before contact-capable candidates. AIR reproduces planned station XY atZ35 and does not establish immersion/bottom/holder clearance. New container center840/45 at selectedZ20; vertical release/reentry to22 is a provisional agitation candidate, with no lateral submerged sweep. Withdraw vertically to25 then35; approach lip at35, descend at790/45/25, strip to775/45/25, lift35. No sloped-inkstone withdrawal or shallow stone wipe is used for water.</p>
<p>WELL_1 is LIGHT_INK; WELL_2 is DARK_INK, each retains its PR32 well geometry/shallow wipe/lip. On concentration change: new water wash → existing PURGE840/137.5 contact1.5 → controlled rewet → load the target well. Terminal cleanup: three new-water visits10s each/three provisional vertical cycles, two PURGE contacts4s each, park800/800/35, M2; no final rewet. Future color lips are recorded only and never visited.</p>
<h2>Before any physical contact</h2><ol><li>Retain confirmed small-brush touch10 and paper registration; verify mounting has not slipped and axis registration is recovered.</li><li>Measure safe compression/contact behavior for this small brush. The inherited response reaches10.2mm at.93; no samples are clamped. All affected/missing-range sources are in the compression audit.</li><li>Inspect vessel bottom, water surface, lip, holder/brush swept envelope, provisional20↔22 vertical agitation and all35-plane connecting movements.</li><li>Confirm light/dark ink well fill, cloth condition, wipe/lip loading and actual800mm/12-contact delivery on the supplied intact-source crops. Washing does not certify paper dryness.</li><li>Compare single pass before adopting selected layered full output. Do not run both complete jobs on the same artwork unintentionally.</li></ol>
<p>Separate all-light/all-dark full stages are intentionally omitted: arbitrary filtering could violate protected mixed-concentration precedence. Use the complete interleaved program. Crop jobs retain original G54 positions, are not re-centered or scaled to a330mm sheet, and require the same registration.</p></html>'''
    html=html.replace('34 original',str(plans['SELECTIVE_LAYERED']['diagnostics']['extra_light_passes'])+' original')
    (out/'Review.html').write_text(html)
