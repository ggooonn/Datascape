"""Standalone scientific review, SVG figures and compact English handoff."""
from pathlib import Path
import json
import html
from math import isclose
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datascape.gcode.production.profiles import Profile
from .curves import offline_profile,load_catalog

ROOT=Path(__file__).resolve().parent
COLORS={'global_linear':'#787f86','anchored_linear':'#3278a4','convex_reference':'#8870b2','three_region':'#d86c25'}
LABELS={'global_linear':'Global linear','anchored_linear':'Anchor-preserving linear','convex_reference':'Convex reference (quadratic knots)','three_region':'Adjustable three-region'}
plt.rcParams.update({'font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,
                     'figure.facecolor':'white','axes.labelcolor':'#283944','text.color':'#283944','axes.titleweight':'bold'})


def table(headers,rows):
    return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def figures(r,repo):
    folder=ROOT/'figures';folder.mkdir(exist_ok=True)
    base=Profile.load(repo/'config/plotter_v03/cost_scenario.synthetic.json')
    fig,axes=plt.subplots(1,2,figsize=(11.6,5.1),sharey=True,layout='constrained')
    for ax,maximum in zip(axes,(10,12)):
        for lo,hi in ((.2,.4),(.4,.6),(.6,.93)):ax.axvspan(lo,hi,alpha=.035,color='#d86c25')
        ax.axvspan(.22,.35,alpha=.11,color='#579d79')
        for model in LABELS:
            c=next(c for c in r['curves'] if c['id']==f'{model}_{maximum}')
            b=offline_profile(base,c).brush_for('ink','INK');x=[i/1000 for i in range(1001)]
            ax.plot(x,[b.z_for(p) for p in x],color=COLORS[model],lw=2.7 if model=='three_region' else 1.6,
                    ls='-' if model=='three_region' else '--',label=LABELS[model])
            if model=='three_region':
                xx,zz=zip(*c['knots']);ax.scatter(xx,zz,s=32,color=COLORS[model],zorder=5)
                for p,z in c['knots']:
                    ax.annotate(f'{p:g}, {z:g}',(p,z),xytext=(-6 if p>=.93 else 4, -17 if p==1 else 8),textcoords='offset points',fontsize=8,
                                ha='right' if p>=.93 else 'left')
        ax.set(title=f'{maximum} mm maximum — unmeasured',xlabel='Accepted Pressure Intent (unchanged)',xlim=(-.02,1.05),ylim=(-12.8,.5))
        ax.set_xticks([0,.2,.4,.6,.8,.93,1]);ax.grid(alpha=.16)
    axes[0].set_ylabel('G54 work Z (mm): first contact = 0')
    axes[1].legend(loc='upper right',fontsize=8,frameon=False)
    fig.savefig(folder/'curve_comparison.svg');fig.savefig('/workspace/scratch/dfdcee762036/offline/pressure_curve_qa.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11.6,5.3),layout='constrained',sharex=True)
    for ax,medium in zip(axes,('ink','color')):
        rows=[f for f in r['families'] if f['medium']==medium]
        for i,f in enumerate(rows):
            for offset,maximum,color in ((-.11,10,'#d86c25'),(.11,12,'#3278a4')):
                s=f['mapped_Z_mm'][f'three_region_{maximum}'];y=i+offset
                ax.plot([s['p10'],s['p90']],[y,y],color=color,lw=3,alpha=.65)
                ax.scatter([s['median']],[y],color=color,s=25,label=f'{maximum} mm candidate' if i==0 else None)
        ax.set_yticks(range(len(rows)),[f['family'] for f in rows]);ax.invert_yaxis()
        ax.set(title=f'{medium.title()} — original-vertex P10–P90 and median',xlabel='Mapped G54 Z (mm)',xlim=(-12,.1));ax.grid(axis='x',alpha=.15)
    axes[1].legend(frameon=False,loc='lower left',fontsize=8)
    fig.savefig(folder/'family_Z_distributions.svg');fig.savefig('/workspace/scratch/dfdcee762036/offline/pressure_family_qa.png',dpi=150);plt.close(fig)
    categories=['drawing','paper_engagement','non_drawing_travel','station_transfer','station_handling']
    palette=['#385f79','#d8844d','#8cb2bd','#b3a58b','#778a68']
    labels=['Drawing','Paper engagement','Other XY/Z travel','Station transfer','Station handling']
    ids=['global_linear_10','global_linear_12','three_region_10','three_region_12']
    fig,axes=plt.subplots(1,2,figsize=(11.6,5.2),layout='constrained',sharey=True)
    for ax,mode,title in zip(axes,('synthetic_low','unverified_DEV'),('Low-acceleration synthetic case','Unverified DEV-reference case')):
        left=[0.]*4
        for category,color,label in zip(categories,palette,labels):
            values=[r['layouts']['D']['curves'][c]['SHARED_COLOR'][mode]['acceleration_sensitive_seconds_by_category'][category]/3600 for c in ids]
            ax.barh(range(4),values,left=left,color=color,label=label,height=.55)
            left=[a+b for a,b in zip(left,values)]
        ax.axvspan(4,5,color='#a8d2a4',alpha=.24,zorder=0);ax.axvline(5,color='#698d62',lw=.8,ls=':')
        for i,x in enumerate(left):ax.text(x+.06,i,f'{x:.2f} h',va='center',fontsize=9)
        ax.set_yticks(range(4),['Linear 10','Linear 12','Three-region 10','Three-region 12'])
        ax.set(title=title,xlabel='Modeled D color hours — not measured',xlim=(0,18.3 if mode=='synthetic_low' else 5.7));ax.grid(axis='x',alpha=.12)
    axes[0].invert_yaxis()
    axes[1].legend(loc='upper left',bbox_to_anchor=(0,-.15),ncol=2,frameon=False,fontsize=8)
    fig.savefig(folder/'runtime_D_color.svg');fig.savefig('/workspace/scratch/dfdcee762036/offline/pressure_time_qa.png',dpi=150);plt.close(fig)
    for path in folder.glob('*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    return folder


def main():
    repo=ROOT.parents[1];r=json.loads((ROOT/'results/full_study.json').read_text());curves=load_catalog(ROOT/'candidate_curves.json')
    assert curves==r['curves'];folder=figures(r,repo)
    def image(name,alt):
        svg=(folder/name).read_text();svg=svg[svg.index('<svg'):]
        return '<figure aria-label="'+html.escape(alt)+'">'+svg+'<figcaption>'+html.escape(alt)+'</figcaption></figure>'
    preferred=[next(c for c in curves if c['id']==f'three_region_{m}') for m in (10,12)]
    knots=table(['Pressure Intent','Candidate A: 10-mm max Z','Candidate B: 12-mm max Z'],
                [[f'{p:.2f}',f'{z:.3f} mm',f'{preferred[1]["knots"][i][1]:.3f} mm'] for i,(p,z) in enumerate(preferred[0]['knots'])])
    family_rows=[]
    for f in r['families']:
        vals=[]
        for maximum in (10,12):
            s=f['mapped_Z_mm'][f'three_region_{maximum}'];vals.append(f'{s["median"]:.3f} [{s["p10"]:.3f}, {s["p90"]:.3f}]')
        family_rows.append([f'{f["medium"]} / {f["family"]}',f'{f["original_strokes"]:,}',f'{f["pressure"]["samples"]:,}',f'{f["pressure"]["median"]:.3f}',*vals])
    family_table=table(['Accepted family','Strokes','Samples','Median intent','A: median Z [P10,P90] mm','B: median Z [P10,P90] mm'],family_rows)
    median_tables=''
    for maximum in (10,12):
        rows=[[f'{f["medium"]} / {f["family"]}',*[f'{f["mapped_Z_mm"][model+"_"+str(maximum)]["median"]:.3f}' for model in LABELS]] for f in r['families']]
        median_tables+=f'<details><summary>Compare all four models: {maximum}-mm maximum, family median work Z</summary>'+table(['Accepted family','Global linear','Anchored linear','Convex reference','Three-region'],rows)+'</details>'
    runtime_default=[]
    for mode in ('D','A'):
        for name,j in r['layouts'][mode]['curves']['three_region_10'].items():
            t=j['unverified_DEV'];runtime_default.append([name,*[f'{t["acceleration_sensitive_seconds_by_category"][k]/3600:.3f}' for k in ('drawing','paper_engagement','non_drawing_travel','station_transfer','station_handling')],f'{t["acceleration_sensitive_seconds"]/3600:.3f}'])
    runtime_static=table(['Job','Drawing h','Paper engagement h','Other travel h','Station transfer h','Station handling h','Total h'],runtime_default)
    before={c:{name:j['unverified_DEV']['acceleration_sensitive_seconds']/3600 for name,j in r['layouts']['D']['curves'][c].items()} for c in ('global_linear_10','global_linear_12','three_region_10','three_region_12')}
    comparison=table(['D job','Global linear 10','Global linear 12','Three-region 10','Three-region 12'],
                     [[name,*[f'{before[c][name]:.3f} h' for c in before]] for name in ('SHARED_INK','SHARED_COLOR')])
    all_knots=''
    for c in curves:all_knots+=f'<details><summary>{c["id"]}: {len(c["knots"])} knots</summary>'+table(['Pressure','G54 Z mm'],[[f'{p:g}',f'{z:.6f}'] for p,z in c['knots']])+'</details>'
    history=json.loads((ROOT/'historical_source_review.json').read_text())['reviews']
    history_table=table(['Historical work','Drawing coordinates/design intent','Station coordinates','Reference limitation'],
                        [[html.escape(x['source']),html.escape(x['drawing']),html.escape(x['stations']),html.escape(x['coordinate_reference'])] for x in history])
    benchmark=json.loads((ROOT/'benchmark_plan.json').read_text())
    benchmark_table=table(['Stage','Test design','Decision'],[
        ['1 • shallow ladder','Direct compression candidates 0.25 / 0.5 / 1 / 2 / 3 mm; isolated 20-mm lines. Initial draw 500, contact 100 mm/min are test conditions only.','Each smaller depth must be observed and cleared; no depth/feed is assumed safe.'],
        ['2 • low-region first test','Candidate A at p=.20 / .28 / .35: short/20-mm marks and a low-pressure transition.','If 3-mm preload is too broad or unstable, revise the .2 anchor without changing Spring Pressure Intent.'],
        ['3 • A coupon','18 patterns: nine 20-mm constants (.20,.28,.35,.40,.50,.60,.75,.85,.93), three 5-mm strokes, three 100-mm strokes and three continuous ramps.','Clear intermediate depths before increasing; p=.93 requests 8.95 mm, not 10 mm.'],
        ['4 • B comparison','Same geometry/loading/substrate on fresh paper, only if A leaves a measured need.','p=.93 requests 10.65 mm. Select B only for an observed quality benefit.'],
        ['5 • speed/recovery','One variable at a time; draw candidates 500→1,000→2,500→5,000; contact/release 100→300→1,000→1,500→2,000.','Inspect initial width, continuity, pigment, paper and recovery before each step.'],
        ['6 • media and repeats','Repeat .28/.50/.85 at least twice; test ink and diluted gouache/glue separately with reference loading.','Retain separate brush/media profiles only where measurements justify them.']])
    style='''body{margin:0;background:#f4f3ef;color:#24333c;font:16px/1.6 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:42px 30px 80px}h1{font-size:38px;line-height:1.15;margin:12px 0}h2{font-size:25px;margin-top:42px}h3{font-size:19px}p{max-width:1020px}.eyebrow{letter-spacing:.12em;text-transform:uppercase;font-size:12px;color:#6b777c}.note{border-left:4px solid #d86c25;padding:10px 18px;background:#fff9f2}.quiet{color:#62727a;font-size:14px}.tag{display:inline-block;border:1px solid #ccd4d5;padding:2px 9px;border-radius:20px;margin-right:6px;font-size:12px}figure{background:white;padding:16px;margin:22px 0;border:1px solid #e1e5e3;border-radius:8px}figure svg{width:100%;height:auto}figcaption{font-size:13px;color:#67767e}table{border-collapse:collapse;width:100%;font-size:13px;background:white;margin:14px 0}th,td{padding:9px 11px;border-bottom:1px solid #e1e7e7;text-align:left;vertical-align:top}th{background:#e9eeec}td:first-child{font-weight:550}tr:last-child td{border-bottom:0}.table-scroll{overflow-x:auto}select{font:inherit;padding:6px;margin:8px 14px 8px 0;max-width:100%}details{margin:10px 0;background:#fff;padding:10px 15px}summary{cursor:pointer}a{color:#27667f}code{font-size:13px}ul,ol{padding-left:24px}nav a{margin-right:14px}.controls{position:relative;background:#e9eeec;padding:12px;border-radius:8px}@media print{body{background:white}main{padding:0}figure,table{break-inside:avoid}details{display:block}.controls{display:none}}'''
    document=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Datascape — Three-region brush calibration v01</title><style>{style}</style></head><body><main>
<div class="eyebrow">Datascape / Independent calibration study v01 / 21 October 2026</div>
<h1>Three-region brush response<br>10 mm and 12 mm candidates</h1>
<p><span class="tag">Offline only</span><span class="tag">Unmeasured 10 / 12 mm candidates</span><span class="tag">PR #27 unchanged</span></p>
<p>Large Baegunmo brush, approximately 20 mm or longer free bristles (verify). Base: <code>{r['backend_pin']}</code>. Spring has 14,951 original strokes and 240,974 accepted pressure samples. No artwork, Pressure Intent or S3a order is regenerated.</p>
<p class="note"><b>First-test recommendation:</b> use Candidate A (10-mm maximum) as the initial response hypothesis, beginning with the smaller direct-depth ladder and then the .20–.35 region. Do not begin by pressing 10 mm. B is a later comparison if it produces a demonstrated mark/recovery advantage; its additional depth has little modeled runtime effect.</p>
<nav><a href="#curves">Curves</a><a href="#spring">Spring families</a><a href="#runtime">Runtime</a><a href="#history">Historical context</a><a href="#benchmark">Physical benchmark</a></nav>
<h2 id="curves">1. A three-region response is not three knots</h2>
<p>Use the unchanged multi-knot <code>BrushCalibration</code> piecewise-linear mapper. The principal regions are .20–.40, .40–.60 and .60–.93. The lower 0–.20 calibration interval and upper .93–1.0 reserve are separate. Six knots are the minimal arrangement with these four boundaries and both global anchors.</p>
{knots}
<p>After the common 3-mm compression at .20, the preferred .40/.60/.93 knots use 8% / 24% / 85% of the remaining compression budget. These are transparent design hypotheses, not fitted physical measurements. The principal compression slopes are 2.8 / 5.6 / 12.94 mm per intent unit for A and 3.6 / 7.2 / 16.64 for B. The .93–1.0 tails remain monotonic at 15.0 / 19.29 mm per intent unit. The original maximum .93 maps to 8.95 / 10.65 mm, leaving 1.05 / 1.35 mm to the global endpoint.</p>
{image('curve_comparison.svg','Four response models at each maximum; green band marks the important .22–.35 range. All curves are unmeasured.')}
<p><b>Fair comparisons:</b> global linear C(p)=Mp gives .20→2.0 / 2.4 mm and therefore does not satisfy the requested 3-mm anchor. Anchor-preserving linear uses 0→0, .20→3, 1→M. The convex reference samples C=3+(M−3)((p−.2)/.8)² above .2 into eleven piecewise-linear knots; it is a quadratic-shaped reference, not an exponential fit or spline. Maximum quadratic interpolation error is at most about 0.027 / 0.035 mm here, unrelated to physical accuracy.</p>
<p>Both outer domains are explicit, with no extrapolation outside 0–1, reversal or overshoot. Work Z is minus compression. Values apply at original accepted vertices; each original G1 segment interpolates its endpoint XYZ. No new vertices are inserted when an artistic-pressure segment crosses a calibration knot. Slope continuity is not claimed; physical microsegment tests determine whether any later interpolation improvement is needed.</p>
<details><summary>Exact coordinates for all eight comparison mappings</summary>{all_knots}</details>
<p><b>An extra .8 knot?</b> Only ink D has samples above .8: 902 samples in the D family, about 0.37% of the whole vertex workload. A collinear .8 knot would be Z−7.268 / −8.487 and would change nothing. Move/add it only if .75/.85/.93 D tests show a need to separate two strong-response regimes; there is no physical evidence for choosing that additional depth yet.</p>
<h2 id="spring">2. Full Spring mapped-Z analysis</h2>
<p>Ink: 3,345 strokes / 69,101 samples. Color: 11,606 strokes / 171,873 samples. Accepted sidecar family labels are verified against every original ID and pressure sample; statistics below are original-vertex weighted, not stroke-count or brush-contact-area weighted.</p>
<p class="note">The .22–.35 range contains 96,988 samples: 91,286 color and 5,702 ink (40.25% of all samples). The preferred low range maps to Z−3.056…−3.420 (A) or Z−3.072…−3.540 (B). Its small variation does not make its absolute mark thin: the initial 3-mm preload can already make a broad mark. Pressure/Z alone cannot predict exact width, pigmentation, force or recovery.</p>
{image('family_Z_distributions.svg','Original accepted families: mapped Z median and central 80% range for the preferred A and B curves.')}
{family_table}
{median_tables}
<p>The region model gives independent low/middle/strong control. It keeps ordinary A behavior relatively shallow while preserving a steeper high-intent response. It has no proven artistic advantage until physical marks are compared. Global-linear A is slightly faster for D color; the anchor-preserving linear control is slower than the preferred curve. This separates response design from a blanket speed claim.</p>
<h2 id="runtime">3. Full A/D trajectory and runtime comparison</h2>
<p>Every curve rebuilds real Spring XYZ trajectories, including deep initial compression, synchronized pressure variation, controlled release to Z0 and the approach boundary, and fast retraction. The previous 1-mm synthetic curve is not substituted. Source plans are written/read back unchanged, every trajectory sample is checked, and all 50 X=300 crossing originals remain continuous in D.</p>
{comparison}
<p class="quiet">The compact table uses unverified DEV-reference acceleration-model hours. All six A/D jobs, eight mappings and three time views are available below.</p>
<div class="controls"><label>Curve <select id="curve-select">{''.join(f'<option value="{c["id"]}" '+('selected' if c['id']=='three_region_10' else '')+'>'+c['id']+'</option>' for c in curves)}</select></label><label>Time view <select id="mode-select"><option value="DEV">Unverified DEV acceleration model</option><option value="low">Low-acceleration synthetic model</option><option value="feed">Commanded-feed subtotal</option></select></label></div>
<div id="runtime-table">{runtime_static}</div><noscript><p>JavaScript is disabled. The default A10 DEV category table is retained; all other category values are in results/full_study.json.</p></noscript>
<p>Categories are disjoint: drawing; approach/contact/first compression/release/retraction; other XY/Z travel; station access/return/park; and station operations/dwells/retraction. General Z stays 6,000; approach 5,000; contact/release and pressure-driven Z up to 2,000; drawing 5,000; ordinary XY 12,000; wet travel 3,000→9,000→3,000 mm/min. Station feeds/dwells and 10-mm wet end lengths remain the inherited synthetic assumptions.</p>
{image('runtime_D_color.svg','D color acceleration-sensitive category totals. Green band is the 4–5-hour target, not an approval or verified bound.')}
<p><b>Target assessment:</b> with unverified DEV assumptions A gives D ink/color 2.420 / 4.557 h and B gives 2.436 / 4.575 h. The B color penalty is about 1.1 minutes. A’s modeled color categories are drawing 0.514, paper engagement 1.924, other travel 0.905, station transfer 0.291 and station handling 0.923 h. Repeated brush entry/release dominates; faster drawing alone would address a small fraction.</p>
<p>Low acceleration gives D color 15.307 / 15.402 h, so the 4–5-hour target is conditional on measured, brush-compatible dynamics. The DEV reference has XYZ rates 15,000/15,000/8,000 mm/min and accelerations 1,200/1,200/1,000 mm/s²; the low case uses 15,000/15,000/6,000 and 100/100/20. Both assume synthetic junction deviation .01 mm, absent from the DEV YAML. The DEV file is unverified and exceeds current fixture brush-acceleration limits; using it in a study never authorizes motion.</p>
<p class="note">Neither model is a verified printing time or bound. Full lookahead and continuous streaming are assumed; finite buffer, step rounding, serial/CPU overhead, mounting variation, actual brush compression/recovery and operator preparation/drying are not modeled. The roughly 27-minute margin from A’s DEV result to five hours is not a hardware guarantee. Stop-each-segment sensitivity values are retained in the JSON.</p>
<h2 id="history">4. Historical drawing Z is not current compression</h2>
{history_table}
<p>Historical originals were read as source only, never executed or regenerated. In particular, Eum’s −12-mm pigment dipping does not establish −12-mm paper compression. Its stated central drawing intent is only .3 mm relative to its old −5-mm contact reference. All three works need their original offsets, mounting, paper plane and actual brush state to interpret physical compression; no numeric setting is transferred into current G54 Z0.</p>
<h2 id="benchmark">5. Compact physical benchmark and decision</h2>
{benchmark_table}
<p>Use the fixed 18-pattern coupon inside a nominal 140×260-mm area (actual reachable/free paper area must be measured), preserving the same geometry between A/B and media. Constant, 5-mm, 100-mm and continuous rise/fall patterns exercise entry bloom, ordinary marks, strong D/rock marks, sustained loading and recovery. Pressure transitions are test strokes, separate from the accepted artwork.</p>
<p>Record wet/dry width at start/middle/end, continuity, pigment distribution, paper disturbance and recovery time/clearance, plus photos with scale. Record the brush’s actual free length/mount, medium/dilution/glue/reference loading, substrate/mounting, exact depth/feed and installed acceleration/junction settings. Stop or reduce if clearance is uncertain, paper fibers lift, marks split/pool, or recovery is incomplete. No width or safety result is prefilled.</p>
<p><b>Before physical execution:</b> confirm installed controller/frame/limits/E-stop; establish and verify G54 first-contact Z0; measure the free approach/hover/recovery envelope, station contacts and park; obtain current air/contact/calibration evidence and separate operator authorization. Coupon tests may intentionally stop for observation; production retains zero routine M0. No executable benchmark or production Spring file is created here.</p>
<p>Optional p=1.0 tests establish the actual 10/12-mm endpoints only after smaller depths pass. To enable a full 0–1 measured mapping, existing gates require observations at every retained knot, including 1.0. If that endpoint is not cleared, keep this candidate unverified or separately review a measured domain ending at .93 with its same 8.95/10.65-mm depth; do not silently move .93 to the maximum or extrapolate.</p>
<p><code>first_depth.request.json</code> is a non-executable request in the existing v0.3 constant-Z calibration schema for only the first −0.25-mm, 20-mm line. Its coordinates, depth and speed still require physical approval. Later depths are separate reviewed requests. The full <code>benchmark_plan.json</code> is a design, not direct CLI input: the existing calibration CLI supports isolated constant-Z lines; continuous-pressure coupons require the existing test-source planning/export API with measured profiles, current evidence and separate authorization after the initial depth tests. This study generates neither program.</p>
<h2>6. Reproducibility and scope</h2>
<p>Eight focused study tests plus the unchanged backend regressions cover monotonicity, anchors, editable configuration, source preservation, Z caps, synthetic-only export rejection and benchmark design. The full run rebuilds 48 jobs (8 curves × 6 jobs), verifies 50 continuous crossing sources in every D case and keeps reloads A ink/color 84/108 and D 83/114. Between-color washing, centered PURGE, final park, source boundaries and zero routine M0 are preserved.</p>
<p>Artifacts: candidate_curves.json; results/full_study.json; benchmark_plan.json; observations.template.json; historical_source_review.json; this standalone HTML and three SVG figures. No installed YAML, backend source or PR #27 branch is modified. Measured knot revisions and brush/media profiles remain normal v0.3 calibration work.</p>
<p class="quiet">S3a D plan SHA256: {r['layouts']['D']['plan_sha256']}<br>S3a A plan SHA256: {r['layouts']['A']['plan_sha256']}<br>Full offline rebuild/analysis elapsed: {r['elapsed_seconds']:.2f} s. These are compute times, not physical tests.</p>
</main><script type="application/json" id="study-data">{json.dumps(r,separators=(',',':')).replace('</','<\\/')}</script><script>
const study=JSON.parse(document.getElementById('study-data').textContent);const cats=['drawing','paper_engagement','non_drawing_travel','station_transfer','station_handling'];
function render(){{const curve=document.getElementById('curve-select').value;const mode=document.getElementById('mode-select').value;let rows='';for(const layout of ['D','A']){{for(const [name,j] of Object.entries(study.layouts[layout].curves[curve])){{let t=j[mode==='DEV'?'unverified_DEV':'synthetic_low'];let key=mode==='feed'?'commanded_feed_seconds_by_category':'acceleration_sensitive_seconds_by_category';let total=mode==='feed'?t.commanded_feed_seconds:t.acceleration_sensitive_seconds;rows+='<tr><td>'+name+'</td>'+cats.map(c=>'<td>'+(t[key][c]/3600).toFixed(3)+'</td>').join('')+'<td><b>'+(total/3600).toFixed(3)+'</b></td></tr>';}}}}document.getElementById('runtime-table').innerHTML='<div class="table-scroll"><table><thead><tr><th>Job</th><th>Drawing h</th><th>Paper engagement h</th><th>Other travel h</th><th>Station transfer h</th><th>Station handling h</th><th>Total h</th></tr></thead><tbody>'+rows+'</tbody></table></div>';}}
document.getElementById('curve-select').addEventListener('change',render);document.getElementById('mode-select').addEventListener('change',render);render();
</script></body></html>'''
    (ROOT/'Datascape_Three_Region_Pressure_v01.html').write_text(document)
    print('Report and three SVG figures generated')


if __name__=='__main__':main()
