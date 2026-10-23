"""Reversible Spring Z-8 integration review: exact source, illustrative widths.

No scene/pressure generation and no physical export. Proxy width is explicitly
unmeasured; authored color/opacity and execution order are retained unchanged.
"""
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import base64
import gzip
import hashlib
import json

from datascape.gcode.binding import load_bound_spring,digest,SIDECAR_SHA
from datascape.gcode.layout import Layout
from datascape.gcode.production.profiles import Profile
from datascape.gcode.production.sequence import reference_order,make_plan,verify_plan
from datascape.gcode.production.trajectory import build_job
from datascape.gcode.production.exporter import _atomic_output,save_json,verify_draw_lineage
from .spring_runtime import RuntimeBuilder,RuntimeMaterials

PIN='19d01e1cdb631ab7f526b95d1272da0a96710a0f'
PLAN_SHA='8b4804f561f0eaab28753ae1790ce3b0f5b9ab8ba9a4a2ffe1e4daecbe2596bd'
KNOTS=((0.,0.),(.2,-1.),(.4,-1.56),(.6,-2.68),(.93,-6.95),(1.,-8.))
ROIS={'mountain':(175,220,375,380),'foreground':(350,670,550,830),'vegetation':(320,500,520,660)}
PROXY='authored width intent * (0.35 + compression_mm / 4); illustrative ONLY, not measured brush width or diffusion'


def candidate_profile(baseline):
    d=deepcopy(baseline.data);d['profile_id']='SPRING-Z8-EXPLICIT-KNOTS-PROVISIONAL'
    for medium in ('ink','color'):
        d['brush_profiles'][medium].update(knots=[list(k) for k in KNOTS],status='unverified',observations=[],
            notes='Separate provisional Spring response; explicit knots, not0.8 rescaling/clamp. Final small-brush test and brush identity calibration pending.')
    d['notes']='Spring-only Z-8 response review; artistic pressures/XY/order unchanged. Benchmark contact range deliberately remains -10..0. No hardware authorization.'
    return Profile.from_dict(d)


def reference_z(pressure,knots):
    """Independent scalar piecewise-linear oracle; no extrapolation."""
    if not knots[0][0]<=pressure<=knots[-1][0]:raise ValueError('outside calibrated knot domain')
    for (p,z),(q,w) in zip(knots,knots[1:]):
        if p<=pressure<=q:return ((q-pressure)*z+(pressure-p)*w)/(q-p)
    raise ValueError('unmapped pressure')


def stats(values):
    import numpy as np
    v=np.asarray(values,dtype=float)
    return dict(count=len(v),min=float(v.min()),p10=float(np.quantile(v,.1)),median=float(np.median(v)),
                p90=float(np.quantile(v,.9)),max=float(v.max()),mean=float(v.mean()))


def validate_trajectories(profile,jobs,manifest):
    result={}
    for job,units in jobs.items():
        b=RuntimeBuilder(profile)
        commands,metrics=build_job(profile,units,'painting',offline_builder=b,offline_material=RuntimeMaterials(b))
        lineage=verify_draw_lineage(commands,manifest['jobs'][job],profile,'painting')
        h=hashlib.sha256();previous_complete=None;pending=None;normal=0;paper_z=[]
        for i,c in enumerate(commands):
            h.update(json.dumps(asdict(c),sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n')
            if c.kind=='marker' and c.action=='source_begin' and previous_complete is not None:
                pending=previous_complete
            if c.kind=='move' and c.action=='draw':
                paper_z.append(c.xyz[2])
                if pending is not None:
                    link=commands[pending+1:i]
                    if not any(row.action.startswith('station_') for row in link):
                        if any(row.kind=='move' and row.xyz[2]>15+1e-9 for row in link):
                            raise ValueError('unexpected global Z35 between normal paper strokes')
                        normal+=1
                    pending=None
            if c.kind=='marker' and c.action=='source_complete':previous_complete=i
        if min(paper_z)<min(profile.brush_for('ink' if job.endswith('INK') else 'color','INK').knots,key=lambda k:k[1])[1]-1e-9:
            raise ValueError('paper drawing exceeds profile compression')
        if any(c.action=='retract' and c.xyz[2]!=15 for c in commands if c.kind=='move'):
            raise ValueError('paper retraction must use Z15')
        if metrics['M0_count'] or tuple(b.position)!=(800,800,35):raise ValueError('pause/park mismatch')
        result[job]=dict(source_units=len(units),pressure_samples_verified=lineage['all_artistic_pressure_samples_verified'],
            trajectory_sha256=h.hexdigest(),trajectory_hash_contract='SHA256 of each canonical sorted command JSON plus newline in order',
            normal_paper_links_without_Z35_checked=normal,paper_Z=stats(paper_z),paper_hover_mm=15,
            M0_count=0,end_G54_xyz=list(b.position),loads_per_slot=metrics['loads_per_slot'],
            collision_clearance_certified=False,authorized_for_machine_execution=False)
        print('validated',profile.data['profile_id'],job,len(paper_z),flush=True)
    return result


def load_visual_records(root,strokes,palette_path,sidecar_path):
    import numpy as np
    raw=Path(sidecar_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SIDECAR_SHA:raise ValueError('wrong accepted family sidecar')
    side=json.loads(gzip.decompress(raw))['strokes']
    records=[r for medium in ('ink','color') for r in json.loads(gzip.decompress((Path(root)/f'visible_{medium}.json.gz').read_bytes()))['strokes']]
    if len(records)!=len(strokes):raise ValueError('rich display source coverage')
    for s,r,f in zip(strokes,records,side):
        if s.stroke_id!=r['id'] or s.stroke_id!=f['stroke_id'] or [[p.x,p.y] for p in s.points]!=r['xy_mm']:
            raise ValueError('display geometry/ID mismatch')
        if [p.pressure for p in s.points]!=f['pressure_intent_samples']:raise ValueError('family pressure mismatch')
        r['_family']=f['family']
    palette=json.loads(Path(palette_path).read_text())
    manifest=json.loads((Path(root)/'MANIFEST_SHA256.json').read_text())
    for medium in ('ink','color'):
        p=Path(root)/f'visible_{medium}.json.gz'
        if hashlib.sha256(p.read_bytes()).hexdigest()!=manifest[p.name]:raise ValueError('rich source bytes changed')
    if hashlib.sha256(Path(palette_path).read_bytes()).hexdigest()!=manifest['palette.json']:raise ValueError('canonical display palette changed')
    return records,palette


def visual_arrays(strokes,records,palette,order,profile):
    import numpy as np
    from matplotlib.colors import to_rgba
    segments=[];widths=[];rgba=[];depths=[];media=[]
    for i in order:
        s,r=strokes[i],records[i];xy=np.array([[p.x,p.y] for p in s.points]);n=len(xy)
        authored=np.asarray(r.get('width_profile_mm',[r.get('width_mm',.3)]*n),dtype=float)
        opacity=np.asarray(r.get('opacity_profile',[r.get('preview_opacity',r.get('opacity',1))]*n),dtype=float)
        if len(authored)!=n or len(opacity)!=n:raise ValueError('authored width/opacity sample mismatch')
        brush=profile.brush_for(s.medium,s.color_slot)
        z=np.array([brush.z_for(p.pressure) for p in s.points])
        color=to_rgba('#000000' if s.medium=='ink' else palette['slots'][s.color_slot]['preview_hex'])
        colors=np.tile(color,(n-1,1));colors[:,3]=np.clip((opacity[:-1]+opacity[1:])/2,0,1)
        segments.append(np.stack((xy[:-1],xy[1:]),axis=1));widths.extend((authored[:-1]+authored[1:])/2)
        rgba.extend(colors);depths.extend(-(z[:-1]+z[1:])/2);media.extend([s.medium=='ink']*(n-1))
    return dict(segments=np.concatenate(segments),width=np.asarray(widths),rgba=np.asarray(rgba),
                depth=np.asarray(depths),ink=np.asarray(media,dtype=bool))


def draw_image(path,arrays,mode='combined',style='proxy',roi=(0,0,600,900),px_per_mm=4):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import LineCollection
    from matplotlib import colormaps
    x0,y0,x1,y1=roi;w=x1-x0;h=y1-y0;dpi=100
    fig=Figure(figsize=(w*px_per_mm/dpi,h*px_per_mm/dpi),dpi=dpi,facecolor='white');FigureCanvasAgg(fig)
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.set_aspect('equal');ax.axis('off')
    s=arrays['segments'];mask=np.ones(len(s),dtype=bool) if mode!='ink' else arrays['ink'].copy()
    mask &= (s[:,:,0].max(1)>=x0)&(s[:,:,0].min(1)<=x1)&(s[:,:,1].max(1)>=y0)&(s[:,:,1].min(1)<=y1)
    depth=arrays['depth'][mask];width=arrays['width'][mask]
    if style=='proxy':width=width*(.35+depth/4.)
    colors=arrays['rgba'][mask]
    if style=='depth':
        # Common absolute0..10mm scale, opaque semantic depth colors. No diffusion.
        colors=colormaps['viridis'](depth/10);width=np.maximum(width,.55)
    # Physical-mm to points uses actual raster geometry; SAME scale per pair.
    lw=width*px_per_mm*72/dpi
    ax.add_collection(LineCollection(s[mask],colors=colors,linewidths=lw,capstyle='round',joinstyle='round',antialiaseds=True))
    fig.savefig(path,dpi=dpi,facecolor='white');fig.clear()


def comparison_sheet(left,right,path,title,subtitle,width=1800):
    from PIL import Image,ImageDraw,ImageFont
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    f=ImageFont.truetype(font,24);small=ImageFont.truetype(font,17)
    images=[Image.open(p).convert('RGB') for p in (left,right)];panel=(width-72)//2
    depth_mode='/ depth /' in title
    height=round(images[0].height*panel/images[0].width);canvas=Image.new('RGB',(width,height+(205 if depth_mode else 145)),'#f4f3f0');d=ImageDraw.Draw(canvas)
    d.text((24,12),title,font=f,fill='#17252a');d.text((24,47),subtitle,font=small,fill='#40525b')
    for i,(im,label) in enumerate(zip(images,('PR31 baseline / Z-10 knots','Candidate / explicit Z-8 knots'))):
        x=24+i*(panel+24);d.text((x,77),label,font=small,fill='#17252a')
        canvas.paste(im.resize((panel,height),Image.Resampling.LANCZOS),(x,108))
    footer=('Common absolute compression colors; display width is a visibility aid, not measured brush behavior.' if depth_mode else
            'Identical XY, frame, colors and display scale. Width proxy is NOT measured brush behavior.')
    d.text((24,height+119),footer,font=small,fill='#40525b')
    if depth_mode:
        from matplotlib import colormaps
        for x in range(500):
            color=tuple(round(c*255) for c in colormaps['viridis'](x/499)[:3])
            d.line((24+x,height+151,24+x,height+170),fill=color)
        for x in range(6):d.text((24+x*100,height+176),str(x*2)+'mm',font=small,fill='#40525b')
    canvas.save(path)


def curve_plot(path,baseline,candidate,pressure,depths):
    import numpy as np
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,4.2),constrained_layout=True)
    colors=('#536879','#d16d25');labels=('PR31 Z-10','Candidate Z-8')
    for p,c,label in zip((baseline,candidate),colors,labels):
        k=np.array(p.data['brush_profiles']['ink']['knots']);axes[0].plot(k[:,0],k[:,1],'-o',c=c,label=label)
    axes[0].set(xlim=(0,1),ylim=(-10.5,.4),xlabel='Unchanged artistic pressure',ylabel='G54 contact Z (mm)',title='Explicit multi-knot response')
    axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].hist(pressure,bins=np.linspace(0,1,51),color='#7e9291');axes[1].set(xlabel='Artistic pressure',ylabel='Accepted samples',title='Same 240,974 samples')
    for d,c,label in zip(depths,colors,labels):axes[2].hist(d,bins=np.linspace(0,10,51),histtype='step',lw=2,color=c,label=label)
    axes[2].set(xlim=(0,10),xlabel='Mapped compression (mm)',ylabel='Samples',title='Same absolute 0–10mm bins');axes[2].legend()
    fig.suptitle('OFFLINE RESPONSE REVIEW — no measured width, diffusion or physical approval',fontsize=12)
    fig.savefig(path,dpi=160);plt.close(fig)


def html_report(out,summary):
    def data(name):
        from io import BytesIO
        from PIL import Image
        im=Image.open(out/name).convert('RGB')
        # Compact interactive display only; original full-resolution PNGs stay
        # in the review package. Both members use identical display dimensions.
        maximum=1200 if name.startswith(('baseline_','candidate_','canonical_')) else 2000
        if im.width>maximum:im=im.resize((maximum,round(im.height*maximum/im.width)),Image.Resampling.LANCZOS)
        encoded=BytesIO();im.save(encoded,format='WEBP',lossless=True,method=4)
        return 'data:image/webp;base64,'+base64.b64encode(encoded.getvalue()).decode()
    modes={mode:{side:data(f'{side}_{mode}.png') for side in ('baseline','candidate')} for mode in ('combined','ink','depth')}
    crop_html=''.join(f'<h2>{name.title()} — identical 200 × 160mm crop</h2><img class="crop" src="{data("crop_"+name+"_comparison.png")}">' for name in ROIS)
    text='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Spring Z-8 response review</title>
<style>body{font:16px system-ui;background:#f4f3f0;color:#17252a;margin:0 auto;padding:28px;max-width:1320px}h1{margin:0 0 12px}p{line-height:1.5}button{font:inherit;padding:8px 18px;margin:5px;cursor:pointer}#pair{position:relative;max-width:800px;margin:auto;background:white;overflow:hidden}#pair img{display:block;width:100%}#over{position:absolute;inset:0;clip-path:inset(0 50% 0 0)}#rule{position:absolute;top:0;bottom:0;left:50%;width:2px;background:#d16d25}input{width:100%}.crop{width:100%;background:white}small{color:#52616b}.legend{display:flex;justify-content:space-between;max-width:800px;margin:10px auto}details{padding:16px;background:white}pre{white-space:pre-wrap}</style>
<h1>Spring — PR31 baseline / explicit Z-8 candidate</h1>
<p>Same 14,951 original strokes, 240,974 artistic pressures, canonical colors and S3a. Nothing is regenerated.</p>
<p><b>Illustrative width proxy, NOT a physical print prediction:</b> authored width × (0.35 + compression / 4mm). Same function, opacity and scale for both curves. No simulated ink diffusion. Actual small-brush widths and recovery remain unmeasured.</p>
<button onclick="mode('combined')">Ink + canonical colors</button><button onclick="mode('ink')">Ink only</button><button onclick="mode('depth')">Depth colors, common 0–10mm scale</button>
<div class="legend"><b>Left: PR31 Z-10</b><b>Right: Z-8 candidate</b></div>
<div id="pair"><img id="new"><div id="over"><img id="old"></div><div id="rule"></div></div>
<p><input aria-label="Comparison slider" type="range" value="50" oninput="document.getElementById('over').style.clipPath='inset(0 '+(100-this.value)+'% 0 0)';document.getElementById('rule').style.left=this.value+'%'"></p>
<p>Depth mode uses viridis: purple = 0mm, yellow = 10mm. Neither image is independently normalized. Canonical display colors are authored previews, not measured dry gouache. This interactive page embeds compact lossless WebP displays; the package retains the original full-resolution PNGs.</p>
<h2>Curve and distributions</h2><img class="crop" src="CURVE">
CROPS
<details><summary>Unmodified canonical width/opacity control (mapping cannot change XY by itself)</summary><img class="crop" src="CONTROL"></details>
<details><summary>Verification and hashes</summary><pre>SUMMARY</pre></details>
<script>const images=IMAGES;function mode(m){document.getElementById('old').src=images[m].baseline;document.getElementById('new').src=images[m].candidate}mode('combined');</script></html>'''
    import html
    text=text.replace('CURVE',data('pressure_depth_comparison.png')).replace('CROPS',crop_html).replace('CONTROL',data('canonical_control.png')).replace('SUMMARY',html.escape(json.dumps(summary,indent=2))).replace('IMAGES',json.dumps(modes))
    (out/'Spring_Z8_Review.html').write_text(text)


def run(root,machine,provenance,rich,palette,sidecar,output):
    import numpy as np
    baseline_path=root/'benchmarks/integrated_330_v01/review_measured_stations/profile.review.json'
    baseline_raw=baseline_path.read_bytes();baseline=Profile.load(baseline_path);candidate=candidate_profile(baseline)
    if baseline.data['motion']!=candidate.data['motion'] or baseline.data['stations']!=candidate.data['stations'] or baseline.data['material']!=candidate.data['material']:
        raise ValueError('candidate changed motion/stations/material order')
    strokes,_=load_bound_spring(machine,provenance);before=digest([asdict(s) for s in strokes])
    order=reference_order(strokes,root/'config/plotter_v03/spring_s3a_order.json')
    jobs,manifest=make_plan(strokes,Layout('D'),order,palette_order=baseline.data['material']['color_order'])
    if digest(manifest)!=PLAN_SHA:raise ValueError('canonical Spring plan changed')
    preserved=verify_plan(manifest,strokes,Layout('D'));records,palette_data=load_visual_records(rich,strokes,palette,sidecar)
    pressures=[];old=[];new=[];groups=defaultdict(lambda:[[],[],[]]);maximum_error=0
    for s,r in zip(strokes,records):
        a=baseline.brush_for(s.medium,s.color_slot);b=candidate.brush_for(s.medium,s.color_slot)
        for p in s.points:
            z=b.z_for(p.pressure);maximum_error=max(maximum_error,abs(z-reference_z(p.pressure,KNOTS)))
            if z < -8-1e-12 or z>0:raise ValueError('candidate outside -8..0')
            d0=-a.z_for(p.pressure);d1=-z
            pressures.append(p.pressure);old.append(d0);new.append(d1)
            for key in (s.medium,s.medium+'/'+r['_family']):
                g=groups[key];g[0].append(p.pressure);g[1].append(d0);g[2].append(d1)
    distributions={key:dict(pressure=stats(v[0]),baseline_compression_mm=stats(v[1]),candidate_compression_mm=stats(v[2])) for key,v in sorted(groups.items())}
    summary=dict(schema='datascape.spring_z8_visual_review.v01',base_commit=PIN,canonical_plan_sha256=PLAN_SHA,
        baseline_profile_sha256=baseline.sha256,candidate_profile_sha256=candidate.sha256,
        canonical_source_sha256=manifest['canonical_source_sha256'],source_readback=preserved,
        all_240974_piecewise_interpolations_checked=True,max_interpolation_error_mm=maximum_error,
        candidate_global_anchor_Z_range=[-8,0],actual_candidate_sample_Z_range=[-max(new),-min(new)],
        pressure_values_unchanged=True,XY_and_source_order_direction_unchanged=True,
        registered_station_and_palette_coordinates_unchanged=True,motion_policy_unchanged=True,
        benchmark_contact_range_preserved=candidate.data['motion']['paper_contact_z_range'],
        width_proxy=PROXY,display_palette_source_sha256=hashlib.sha256(Path(palette).read_bytes()).hexdigest(),
        physical_width_or_diffusion_measured=False,operator_small_brush_test_pending=True,
        physically_authorized=False,production_Gcode_written=False,distribution=distributions,
        crop_regions_artwork_mm=ROIS,trajectory_validation={})
    def write(out):
        save_json(out/'profile.pr31_z10.snapshot.json',baseline.data);save_json(out/'profile.spring_z8.candidate.json',candidate.data)
        if Profile.load(out/'profile.pr31_z10.snapshot.json').sha256!=baseline.sha256 or Profile.load(out/'profile.spring_z8.candidate.json').sha256!=candidate.sha256:
            raise ValueError('serialized profile read-back mismatch')
        summary['saved_profile_readback_verified']=True
        save_json(out/'palette.canonical.json',palette_data)
        for label,p in (('baseline',baseline),('candidate',candidate)):
            summary['trajectory_validation'][label]=validate_trajectories(p,jobs,manifest)
            arrays=visual_arrays(strokes,records,palette_data,order,p)
            for mode in ('combined','ink','depth'):
                draw_image(out/f'{label}_{mode}.png',arrays,'ink' if mode=='ink' else 'combined','depth' if mode=='depth' else 'proxy')
            if label=='baseline':draw_image(out/'canonical_control.png',arrays,style='canonical')
            for name,roi in ROIS.items():draw_image(out/f'crop_{name}_{label}.png',arrays,roi=roi,px_per_mm=8)
            print('rendered',label,flush=True)
        for mode in ('combined','ink','depth'):
            comparison_sheet(out/f'baseline_{mode}.png',out/f'candidate_{mode}.png',out/f'comparison_{mode}.png',
                'Spring / '+mode+' / identical 600 x 900mm frame',
                'Common width proxy; depth colors use the SAME absolute0-10mm range. Unmeasured physical response.')
        for name in ROIS:
            comparison_sheet(out/f'crop_{name}_baseline.png',out/f'crop_{name}_candidate.png',out/f'crop_{name}_comparison.png',
                'Spring / '+name+' / 200 x 160mm region',PROXY,width=2880)
        curve_plot(out/'pressure_depth_comparison.png',baseline,candidate,pressures,(old,new))
        save_json(out/'verification.json',summary);html_report(out,summary)
        distribution_report(out,summary)
        if baseline_path.read_bytes()!=baseline_raw or before!=digest([asdict(s) for s in strokes]):raise ValueError('baseline/source mutated')
        (out/'README.md').write_text(README)
        return summary
    return _atomic_output(output,write)


def distribution_report(out,summary):
    lines=['# Accepted pressures and mapped compression (sample weighted)',
           '', 'Compression is positive millimeters below paper first contact Z0. Depth is calculated, not physically measured.', '',
           '| Medium/family | Samples | Pressure min..max | Baseline median / max mm | Candidate median / max mm |',
           '|---|---:|---:|---:|---:|']
    for key,v in summary['distribution'].items():
        p,a,b=v['pressure'],v['baseline_compression_mm'],v['candidate_compression_mm']
        lines.append(f"| {key} | {p['count']:,} | {p['min']:.3f}..{p['max']:.3f} | {a['median']:.3f} / {a['max']:.3f} | {b['median']:.3f} / {b['max']:.3f} |")
    lines.extend(['', 'Full min/p10/median/p90/max/mean for every medium/family are in verification.json.',
                  'The original pressure distribution is identical in both versions; no exact stroke width or recovery is inferred.'])
    (out/'DISTRIBUTIONS.md').write_text('\n'.join(lines)+'\n')


README='''# Spring explicit Z-8 response candidate

Reversible visual integration review from pinned PR31. Original baseline file,
canonical source, XY, accepted pressure, S3a, palette and motion/station settings
are unchanged. Explicit knots:0/0,.2/-1,.4/-1.56,.6/-2.68,.93/-6.95,1/-8.
Ink/color remain independent profiles, initially identical. Benchmark contact
envelope stays -10..0 and its deliberate -10 lines are not changed.

Open Spring_Z8_Review.html (self-contained, no network): combined/ink/depth
slider, three enlarged same-scale crops, curve/distributions and hashes.
The page embeds lossless WebP displays at compact resolution; original PNGs
remain available for detailed inspection. Both views have identical scale.
comparison_combined.png / comparison_ink.png show ILLUSTRATIVE DEPTH-WIDTH
PROXIES, not measured physical prints. Formula: authored per-sample width intent
times (0.35 + compression_mm/4). Same formula, scale, canonical opacity and color
for both versions. No pigment diffusion, brush recovery or substrate physics is
simulated. canonical_control.png shows unmodified authored widths: the pressure
mapping alone cannot change canonical XY. Depth images share absolute0..10mm
viridis scale, not independently normalized. Palette hex values are existing
display references, not measured dry pigment. All layers retain S3a order.

Each original pressure is checked against an independent linear interpolation
oracle; full production renderer/axis-limited trajectories validate lineage,
Z15 links/no unexpected35, station/parking/M0 and trajectory hashes. Offline
envelope-only sink never asserts physical collision clearance. No production
G-code or passed calibration/authorization evidence is created. The explicit
1.0 anchor is -8; actual Spring max approximately.93 maps near-6.95, not-8.

Physical adoption waits for the final small-brush test: actual width, continuity,
loading, paper response and recovery. X860 installation/readback and existing
formal physical gates remain unchanged. No artistic/grammar/sequence study.

Reproduce from PR31 pinned19d01e1cdb631ab7f526b95d1272da0a96710a0f
plus this focused module (Python, numpy, matplotlib, Pillow):

```bash
PYTHONPATH=src:. python -m benchmarks.integrated_330_v01.spring_z8_preview \\
  --machine "$BOUND/spring.machine.json" --provenance "$BOUND/spring.provenance.json" \\
  --rich "$FROZEN/artworks/spring_v13" \\
  --palette "$FROZEN/artworks/spring_v13/palette.json" \\
  --sidecar "$FROZEN/artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz" \\
  --output "$NEW_REVIEW_DIRECTORY"
```

BOUND is the previously recovered canonical bound input directory; FROZEN is
the byte-verified original PR25 resources. See the existing Spring recovery
handoff for their exact hashes. No terrain regeneration is involved.
'''


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('machine','provenance','rich','palette','sidecar','output'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();run(Path(__file__).resolve().parents[2],**vars(a))
