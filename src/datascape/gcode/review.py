"""Self-contained offline review assets; no external scripts or controller APIs."""
from dataclasses import asdict
from html import escape
import json
from .calibration import benchmarks,recording_template,synthetic_profile
from .motion import MotionSettings,fragments,stroke_events,commented_preview
from .layout import Layout
from .stations import configuration_template


def work_svg(parts,layout):
    parts=list(parts)
    bounds=[layout.footprint(p) for p in layout.panels]
    xmin=min(v[0] for v in bounds);ymin=min(v[1] for v in bounds)
    xmax=max(v[2] for v in bounds);ymax=max(v[3] for v in bounds)
    rows=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{xmin} {ymin} {xmax-xmin} {ymax-ymin}">',
          '<rect width="100%" height="100%" fill="white"/>',
          '<!-- Display work Y-up in SVG Y-down exactly once. Centerlines, not a physical mark prediction. -->',
          f'<g transform="translate(0,{ymax+ymin}) scale(1,-1)">']
    for panel in layout.panels:
        corners=[layout.work_xy(panel,x,y) for x,y in ((panel.x_min,panel.y_min),(panel.x_max,panel.y_min),
                                                    (panel.x_max,panel.y_max),(panel.x_min,panel.y_max))]
        rows.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in corners)+'" fill="none" stroke="#999" stroke-width=".4"/>')
    for f in parts:
        xy=' '.join(f'{x:.6f},{y:.6f}' for x,y in f.work_xy)
        color='#1c2526' if f.stroke.medium=='ink' else '#4d9b73'
        rows.append(f'<polyline points="{xy}" fill="none" stroke="{color}" stroke-width=".3"><title>{escape(f.stroke.stroke_id)}</title></polyline>')
    rows+=['</g></svg>']
    return '\n'.join(rows)


def trajectory_html(parts,settings):
    # Bounded representative set; every embedded sample is an actual IR event.
    data=[]
    for f in parts:
        controls=settings(f) if callable(settings) else settings
        events=list(stroke_events(f,controls))
        x,y=f.work_xy[0]
        data.append({'id':f.stroke.origin_id,'panel':f.panel,'medium':f.stroke.medium,
                     'z_status':('constant_synthetic_preview' if controls.mode=='constant' else controls.profile.status if controls.profile else 'unresolved'),
                     'events':[[e.action.value,
                                None if e.work_xy is None else e.work_xy[0]-x,
                                None if e.work_xy is None else e.work_xy[1]-y,
                                e.preview_z_mm,e.artistic_pressure] for e in events]})
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Datascape v0.2 · offline brush trajectory</title>
<style>body{background:#eeeae0;color:#21312e;font:16px system-ui;margin:28px}h1{font-size:26px}canvas{background:white;width:100%;height:550px;border:1px solid #aab8ae}label{margin:12px;display:inline-block}p{max-width:1000px}select{max-width:95%;padding:8px}#readout{white-space:pre-wrap}</style>
<h1>Brush trajectory · offline v0.2</h1><p>Fragment XY and pressure samples. Spring review uses frozen data; calibration review uses synthetic benchmark paths. Z is an invented visualization scale or unresolved (not a tested brush or safe depth). Unresolved drawing Z is shown on the contact plane for XY inspection only. Calibrated Z and machine coordinates are absent. Entry/contact/release motions do not replace artistic taper.</p>
<select id="choice"></select><br><label>Rotation <input id="yaw" type="range" min="-180" max="180" value="-35"></label><label>Tilt <input id="tilt" type="range" min="5" max="85" value="35"></label><label>Z exaggeration <input id="ze" type="range" min="1" max="50" value="10"></label><label>Path progress <input id="progress" type="range" min="1" max="100" value="100"></label><canvas id="view" width="1400" height="650"></canvas><p>Dark: draw · blue: travel/lift · orange: approach/contact/release. Work Y increases rearward. X/Y/Z axes originate at each selected fragment's start. Distances remain in mm before display scaling.</p><pre id="readout"></pre>
<script>const data=__DATA__;const q=id=>document.getElementById(id);data.forEach((d,i)=>{let o=document.createElement('option');o.value=i;o.textContent=d.panel+' / '+d.medium+' / '+d.id;q('choice').appendChild(o)});
function draw(){const d=data[+q('choice').value],c=q('view'),g=c.getContext('2d');g.clearRect(0,0,c.width,c.height);const yaw=+q('yaw').value*Math.PI/180,tilt=+q('tilt').value*Math.PI/180,zscale=+q('ze').value;let x=0,y=0,z=3;const points=d.events.map(e=>{if(e[1]!==null){x=e[1];y=e[2]}if(e[3]!==null)z=e[3];return [e[0],x,y,z,e[4]]});const max=Math.max(20,...points.map(p=>Math.hypot(p[1],p[2],p[3]*zscale)));const scale=240/max;
function project(x,y,z){let u=x*Math.cos(yaw)-y*Math.sin(yaw),v=x*Math.sin(yaw)+y*Math.cos(yaw);return [650+u*scale,350+(v*Math.sin(tilt)-z*zscale*Math.cos(tilt))*scale]}
for(const [label,v] of [['X',[10,0,0]],['Y',[0,10,0]],['Z',[0,0,1]]]){let a=project(0,0,0),b=project(...v);g.strokeStyle='#a0aaa4';g.beginPath();g.moveTo(...a);g.lineTo(...b);g.stroke();g.fillStyle='#555';g.fillText(label,...b)}
let prev=null,count=Math.ceil(points.length*+q('progress').value/100);for(const p of points.slice(0,count)){const pos=project(p[1],p[2],p[3]);if(prev){g.strokeStyle=p[0]==='draw'||p[0]==='pressure_variation'?'#263b30':p[0]==='travel'||p[0]==='lift'?'#6197b5':'#d28c35';g.lineWidth=p[4]===null?1.5:1+p[4]*3;g.beginPath();g.moveTo(...prev);g.lineTo(...pos);g.stroke()}prev=pos}const last=points[Math.max(0,count-1)];q('readout').textContent=JSON.stringify({source:d.id,event:last[0],local_display_xy_mm:last.slice(1,3),preview_z_mm:d.events[Math.max(0,count-1)][3],artistic_pressure:last[4],z_status:d.z_status,calibrated_z:null,machine_xyz:null},null,2)}
['choice','yaw','tilt','ze','progress'].forEach(id=>q(id).addEventListener('input',draw));draw();</script></html>'''.replace('__DATA__',json.dumps(data).replace('</','<\\/'))


def write_benchmarks(destination):
    destination.mkdir(parents=True,exist_ok=True)
    records=[];svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 440"><rect width="600" height="440" fill="#fff"/>']
    for b in benchmarks():
        records.append(asdict(b))
        pts=' '.join(f'{p.x},{p.y}' for p in b.stroke.points)
        svg.append(f'<text x="20" y="{b.stroke.points[0].y-4}" font-size="4">{escape(b.name)} | {b.feed_mm_min:g} mm/min candidate</text>')
        svg.append(f'<polyline points="{pts}" fill="none" stroke="#243c37" stroke-width=".4"/>')
    svg.append('</svg>')
    (destination/'benchmarks.svg').write_text('\n'.join(svg))
    (destination/'benchmarks.json').write_text(json.dumps(records,indent=2)+'\n')
    (destination/'recording_template.json').write_text(json.dumps(recording_template(),indent=2)+'\n')
    (destination/'stations_template.json').write_text(json.dumps(configuration_template(),indent=2)+'\n')
    # Benchmark fragments use the standard motion interpreter, with no clipping
    # or resynthesis of Spring vectors. Each benchmark keeps its own mode/feed.
    from .motion import Fragment
    sample=[]
    lines=[]
    for b in benchmarks():
        f=Fragment(b.stroke,'CALIBRATION','SYNTHETIC',tuple((p.x,p.y) for p in b.stroke.points))
        settings=MotionSettings(synthetic_profile(),b.mode,b.constant_z_mm)
        lines.extend(commented_preview(stroke_events(f,settings)))
        sample.append(f)
    (destination/'benchmarks.preview.gcode.txt').write_text(''.join(lines))
    # Each benchmark keeps its own constant/variable interpretation in 3D too.
    controls={b.name:MotionSettings(synthetic_profile(),b.mode,b.constant_z_mm) for b in benchmarks()}
    (destination/'benchmarks_3d.html').write_text(trajectory_html(sample,lambda f: controls[f.stroke.stroke_id]))
