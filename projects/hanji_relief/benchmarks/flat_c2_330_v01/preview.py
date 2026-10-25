"""Exact 330mm paper guides. Annotations are never passed to the motion renderer."""
from pathlib import Path
from html import escape
import json,math
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor,Color

COLOR='#98C245'
RUN_ORDER=['Q2','Q1','Q3','Q4']


def svg(plan,annotated=True):
    diameter=plan['config']['preview_diameter_mm'];r=diameter/2
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="334mm" height="334mm" viewBox="-2 -2 334 334" role="img" aria-label="330mm flat C2 comparison front view">', '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="#687b72"/></marker></defs>', '<rect x="0" y="0" width="330" height="330" fill="#fffef8" stroke="#84958b" stroke-width="0.4"/>']
    if annotated:
        s.append('<path d="M165 0 V330 M0 165 H330" stroke="#9ea9a2" stroke-width="0.35" stroke-dasharray="3 2"/>')
    for q in ['Q1','Q2','Q3','Q4']:
        c=plan['config']['conditions'][q];rows=[r for r in plan['rows'] if r['quadrant']==q]
        if annotated:
            low,hi=c['allowed_centers_xy_mm'];x=c['center_mm'][0];ytop=13 if q in ('Q1','Q2') else 178
            s.append(f'<rect x="{low[0]}" y="{330-hi[1]}" width="{hi[0]-low[0]}" height="{hi[1]-low[1]}" fill="none" stroke="#dce3d9" stroke-width="0.3" stroke-dasharray="2 2"/>')
            s.append(f'<text x="{x}" y="{ytop}" text-anchor="middle" font-family="sans-serif" font-size="5" fill="#263e35">{q} | {c["compression_depth_mm"]:g} mm / {c["dwell_at_depth_s"]:g} s</text>')
            s.append(f'<text x="{x}" y="{ytop+6}" text-anchor="middle" font-family="sans-serif" font-size="2.9" fill="#617268">Run {RUN_ORDER.index(q)+1} | C2 | 20 + refill + 20'+(' | artwork baseline' if q=='Q3' else '')+'</text>')
            for i,(a,b) in enumerate(zip(rows,rows[1:])):
                stroke='#ce8b29' if b['sequence_in_condition']==21 else '#a1aca2'
                s.append(f'<path d="M{a["paper_x_mm"]} {330-a["paper_y_mm"]} L{b["paper_x_mm"]} {330-b["paper_y_mm"]}" fill="none" stroke="{stroke}" stroke-width="{.4 if i==19 else .17}" stroke-dasharray="1 1"'+(' marker-end="url(#arr)"' if i in (0,19) else '')+'/>')
        for row in rows:
            x,y=row['paper_x_mm'],330-row['paper_y_mm'];i=row['sequence_in_condition']
            s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{COLOR}"><title>{q} #{i}, source{row["study_dot_id"]}, batch{row["load_batch_in_condition"]}</title></circle>')
            if annotated:
                if i in (1,20,21):
                    line='#3c7f93' if i==1 else '#cd8c28' if i==20 else '#a45674'
                    s.append(f'<circle cx="{x}" cy="{y}" r="{r+1}" fill="none" stroke="{line}" stroke-width=".4"/>')
                s.append(f'<text x="{x+1.8}" y="{y-1.5}" font-family="sans-serif" font-size="2.25" fill="#263d33">{i}</text>')
    if annotated:
        s.append('<rect x="37" y="155" width="256" height="20" rx="2" fill="#fffef8"/>')
        for y,text,size in [(161,'Run order: Q2 > Q1 > Q3 > Q4',3.6),(167,'Blue=first point | orange=20 | rose=21 after refill',2.8),(172,'Dotted route / labels: GUIDE ONLY. Display diameter '+str(diameter)+' mm is UNMEASURED.',2.6)]:s.append(f'<text x="165" y="{y}" text-anchor="middle" font-size="{size}" font-family="sans-serif" fill="#485f50">{text}</text>')
        s.append('<text x="6" y="326" font-size="2.5" font-family="sans-serif">Paper(0,0) lower-left; X right, Y up. No scaling/rotation of source40-point patch.</text>')
    s.append('</svg>');return ''.join(s)


def pdf(path,plan):
    """One exact-size static print guide; display marks are not physical predictions."""
    c=canvas.Canvas(str(path),pagesize=(330*mm,330*mm),pageCompression=1,invariant=1)
    c.setTitle('Flat C2 330mm four-condition print guide');c.setAuthor('Datascape - Hanji relief benchmark')
    c.setStrokeColor(HexColor('#84958b'));c.setLineWidth(.35*mm);c.rect(.2*mm,.2*mm,329.6*mm,329.6*mm)
    c.setStrokeColor(HexColor('#a2aca3'));c.setDash(3*mm,2*mm);c.line(165*mm,0,165*mm,330*mm);c.line(0,165*mm,330*mm,165*mm);c.setDash()
    radius=plan['config']['preview_diameter_mm']/2
    for q in ['Q1','Q2','Q3','Q4']:
        cfg=plan['config']['conditions'][q];rows=[r for r in plan['rows'] if r['quadrant']==q];cx=cfg['center_mm'][0];top=317 if q in ('Q1','Q2') else 152
        c.setFillColor(HexColor('#263e35'));c.setFont('Helvetica-Bold',14);c.drawCentredString(cx*mm,top*mm,f'{q} | {cfg["compression_depth_mm"]:g} mm / {cfg["dwell_at_depth_s"]:g} s')
        c.setFont('Helvetica',8);c.drawCentredString(cx*mm,(top-6)*mm,f'Run {RUN_ORDER.index(q)+1} | C2 | 20 + refill + 20'+(' | artwork baseline' if q=='Q3' else ''))
        c.setDash(1*mm,1*mm);c.setStrokeColor(HexColor('#a2ada3'));c.setLineWidth(.15*mm)
        for a,b in zip(rows,rows[1:]):c.line(a['paper_x_mm']*mm,a['paper_y_mm']*mm,b['paper_x_mm']*mm,b['paper_y_mm']*mm)
        c.setDash()
        for i in (0,19):
            a,b=rows[i],rows[i+1];dx=b['paper_x_mm']-a['paper_x_mm'];dy=b['paper_y_mm']-a['paper_y_mm'];angle=math.atan2(dy,dx)
            x=a['paper_x_mm']+.6*dx;y=a['paper_y_mm']+.6*dy
            c.setFillColor(HexColor('#687b72' if i==0 else '#cd8c28'))
            path=c.beginPath();path.moveTo(x*mm,y*mm)
            for sign in (-1,1):path.lineTo((x-1.5*math.cos(angle)+sign*.6*math.sin(angle))*mm,(y-1.5*math.sin(angle)-sign*.6*math.cos(angle))*mm)
            path.close();c.drawPath(path,stroke=0,fill=1)
        for r in rows:
            x,y=r['paper_x_mm'],r['paper_y_mm'];i=r['sequence_in_condition'];c.setFillColor(HexColor(COLOR));c.circle(x*mm,y*mm,radius*mm,stroke=0,fill=1)
            if i in (1,20,21):
                c.setStrokeColor(HexColor('#3c7f93' if i==1 else '#cd8c28' if i==20 else '#a45674'));c.setLineWidth(.4*mm);c.circle(x*mm,y*mm,(radius+1)*mm,stroke=1,fill=0)
            c.setFillColor(HexColor('#263d33'));c.setFont('Helvetica',6.4);c.drawString((x+1.8)*mm,(y+1.5)*mm,str(i))
    c.setFillColor(HexColor('#fffef8'));c.roundRect(37*mm,155*mm,256*mm,20*mm,2*mm,stroke=0,fill=1)
    c.setFillColor(HexColor('#485f50'));c.setFont('Helvetica-Bold',10);c.drawCentredString(165*mm,169*mm,'Run order: Q2 > Q1 > Q3 > Q4')
    c.setFont('Helvetica',8);c.drawCentredString(165*mm,163*mm,'Blue=first | orange=20 | rose=21 after refill. Dotted route/labels are GUIDE ONLY.')
    c.setFont('Helvetica',7.5);c.drawCentredString(165*mm,158*mm,f'Paper330x330mm; display mark diameter{radius*2:g}mm is UNMEASURED. No geometry scaling.')
    c.setFont('Helvetica',7);c.drawString(6*mm,4*mm,'(0,0) lower-left; X right / Y up. Print at100% for exact330mm guide; no labels are painted by G-code.')
    c.showPage();c.save()


def write_previews(out,plan,report):
    out=Path(out);bare=svg(plan,False);guide=svg(plan,True)
    (out/'flat_C2_layout.svg').write_text(bare);(out/'flat_C2_numbered_guide.svg').write_text(guide);pdf(out/'flat_C2_numbered_guide_330mm.pdf',plan)
    rows=''.join(f'<tr><td>{name}</td><td>{v["readback"]["contact_count"]}</td><td>{v["readback"]["pigment_loads"]}</td><td>{v["readback"]["condition_preparations"]}</td><td>{v["readback"]["at_depth_dwell_s"]:.0f}s</td><td>{v["timing"]["acceleration_sensitive_seconds"]/60:.2f}min</td></tr>' for name,v in report['jobs'].items())
    label={'paper_xy':'Noncontact paper XY','paper_z_noncontact':'Noncontact Z approach/retract','paper_contact':'Controlled touch / press / release','depth_dwell':'Full at-depth dwell','condition_preparation':'Condition wash / purge / rewet / initial C2 + travel','same_color_refill':'Same C2 reload + round-trip','terminal_cleanup':'Terminal cleaning / park'}
    times=report['jobs']['FLAT_C2_330_ALL_Q2_Q1_Q3_Q4']['timing']['acceleration_sensitive_seconds_by_category']
    t=''.join(f'<tr><td>{label[k]}</td><td>{v:.2f}s</td></tr>' for k,v in times.items() if k in label)
    p=plan['selection'];cfg=plan['config']['registration']
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Flat C2 four-condition comparison</title><style>body{margin:0;color:#263d34;background:#f3f2e9;font:15px/1.7 system-ui,sans-serif}main{max-width:1180px;padding:34px 24px;margin:auto}section{padding:24px;background:#fffef8;border:1px solid #d4dfd1;border-radius:12px;margin:24px 0}h1{font-size:32px;line-height:1.25}.warning{background:#f7e6bd;padding:17px;border-left:5px solid #b8852c}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}svg{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border-bottom:1px solid #d9e1d4;text-align:left}td:first-child{overflow-wrap:anywhere}.scroll{overflow:auto}code{overflow-wrap:anywhere}@media(max-width:760px){.grid{grid-template-columns:1fr}main{padding:20px 13px}section{padding:16px}}</style><main><p>HANJI / FLAT PAPER330mm / C2 / 2026-10-25</p><h1>Same40-point source pattern.<br>Four depth/dwell conditions.</h1><p class="warning"><b>Real numeric offline review commands, not machine-authorized programs.</b> Reference mounting XYOFFSET, flat first-touchZTOUCH, approach15/hover20. Current brush/paper registration has not been freshly measured. No hardware was connected or operated.</p><section><h2>Front view and print guide</h2><p>Left3mm / right4mm. Top0.5s / bottom1s. Q3 is the current artwork baseline. Execution Q2 > Q1 > Q3 > Q4. Each condition receives preparation, initial C2,20dots, one same-color refill before21,20dots. Terminal cleanup once.</p><div class="grid"><div><h3>Paint placement, without numbers</h3>BARE</div><div><h3>Guide only: numbers and lifted travel</h3>GUIDE</div></div><p>Blue circle=first point; orange=20; rose=21 after refill. Display diameter2.8mm is an UNMEASURED rendering assumption; real marks may be larger or overlap. Labels, paths, quadrant lines and annotations are never painted.</p></section><section><h2>Source selection and exact translation</h2><p>40nearest physical-panel4 C2 points to local(100,100), exact-decimal squared distance, source ID tie-break. PATCHSIZE. The identical ordered patch is centered in each quadrant by translation only, without scaling/rotation/mirroring or XY snapping. The125x125 center bounds are respected. Original relief Z is retained as provenance but NOT used for contact height.</p><p>Flat press = ZTOUCH - depth: default3mm -> Z7,4mm -> Z6. Dwell is the full0.5/1s after reaching depth, not descent time. Original study IDs are retained; experimental contact IDs belong to a separate benchmark namespace and cannot complete artwork dots.</p></section><section><h2>Schedules and computed duration</h2><div class="scroll"><table><tr><th>Job</th><th>Dots</th><th>C2 loads</th><th>Preparations</th><th>Depth dwell</th><th>Modeled time</th></tr>ROWS</table></div><table><tr><th>Integrated breakdown</th><th>Modeled duration</th></tr>TIME</table><p>Existing15000 dry/used return,12000 wet travel with arrival/departure zones,7000 noncontact Z and2000 controlled paper motion are preserved. Independent times include their own final cleanup; integrated cleanup occurs only once. Shared Cartesian model: configuration-reference acceleration1500/1500/1000mm/s2, assumed JD0.01/full lookahead. Streaming, steps and brush response are not measured durations.</p></section><section><h2>Observe and compare matched positions</h2><p>Record1-5,16-20,21-25,36-40: dry width/height, bleed, density, neighboring overlap and deformation. Same index/source ID means the same relative position across all four conditions. Other positions may differ for reasons besides depletion. Water state, C2 dilution/binder and loading method stay controlled; no new recipe is prescribed.</p><p>Integrated and individual programs are alternatives. Do not execute both on the same marked sheet. All independent programs begin at the inherited0/900/35 start; each ends with its own terminal cleanup and800/800/35/M2. No routine M0, homing, G92 or controller writes.</p><p>Only actual paper lower-left G54 XY and unchanged mounted-brush flat first touch10 need confirmation before applying this review placement; new fixture/full-tool clearance remains a physical review. Existing station values are not re-estimated or shifted with the paper.</p></section></main></html>'''
    for a,b in {'XYOFFSET':str(cfg['paper_lower_left_g54_xy_mm']),'ZTOUCH':str(cfg['flat_first_touch_g54_z_mm']),'BARE':bare,'GUIDE':guide,'PATCHSIZE':f'Bounding box{p["width_mm"]:.2f}x{p["height_mm"]:.2f}mm','ROWS':rows,'TIME':t}.items():html=html.replace(a,b)
    (out/'Flat_C2_Review.html').write_text(html)
