"""Build a portable review page and separate concentration-intent sidecar."""
from pathlib import Path
import base64, gzip, hashlib, html, json, sys
from PIL import Image
from generate import ROOT,DEFAULT,read,gz,save

def run(out=DEFAULT):
    out=Path(out);ink=json.loads(gzip.decompress((out/'summer_ink.json.gz').read_bytes()))['strokes']
    intents=[]
    for r in ink:
        layer=r['layer'];part=r.get('grammar_part','')
        role='selective-emphasis' if layer=='D' else 'structure' if layer in ('rock','Soil') or layer=='tree' and part!='foliage-field' else 'light-support'
        intents.append(dict(id=r['id'],role=role,concentration_ratio=None,
            note='Artistic cohort only; no physical light/dark allocation or dilution assigned'))
    gz(out/'ink_concentration_intent.json.gz',dict(policy='Independent of canonical XY and virtual color; no fixed 70/30 split',strokes=intents))
    stats=read(out/'stroke_statistics.json');v=read(out/'verification.json')
    images=[('Summer full composition','summer_full.png'),('Physical P3/P4 / 40 mm gap','summer_physical_pair.png'),
        ('Spring to Summer / untouched Spring reference','transition_P1_P4.png'),('Terrain skyline / three candidates','skyline_candidates_P1_P4.png'),
        ('Summer camera candidates','viewpoint_candidates.png'),('Ink only','summer_ink.png'),('Layer separation','layers.png'),('Virtual color studies','color_studies.png')]
    body=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Datascape Summer v01</title>',
        '<style>body{margin:0;background:#e9e6dc;color:#203b35;font:16px/1.6 system-ui}main{max-width:1400px;margin:auto;padding:36px}h1{font-size:38px;line-height:1.2}p{max-width:950px}.tag{color:#66786b}figure{margin:36px 0;background:#f6f4ef;padding:18px;border-radius:6px}img{display:block;max-width:100%;max-height:1000px;margin:auto}figcaption{margin-bottom:16px;font-weight:600}table{border-collapse:collapse;background:#f6f4ef}td,th{padding:10px 18px;border:1px solid #c7cec5;text-align:left}a{color:#365f58}</style><main>',
        '<p class="tag">DATASCAPE / SUMMER P3–P4 / PROVISIONAL v01</p><h1>Growth between ridges</h1>',
        '<p>New Summer viewpoint and vectors, with original Spring geometry preserved. C1-related eastern approach is provisionally selected: the P2–P3 terrain skyline has an unfitted 18 mm height difference, with a visible slope reversal. This relationship is a compositional suggestion, not a seam constraint.</p>',
        '<p>Each panel is 300 × 900 mm; each seasonal painting spans 600 × 900 mm. The installation adds 40 mm gaps. Colors and concentration cohorts are preliminary intent, with no pigment assignment, physical width prediction or production G-code.</p>',
        '<table><tr><th>Output</th><th>Paths</th><th>Centerline length</th></tr>']
    for key,label in [('visible_ink','Visible ink'),('visible_color_intent','Visible color intent'),('authoring','Original authoring proposals')]:
        s=stats[key];body.append(f'<tr><td>{label}</td><td>{s["strokes"]:,}</td><td>{s["length_mm"]/1000:.2f} m</td></tr>')
    body+=['</table>',f'<p>Offline readback: {v["status"]}. All {v["inherited_files_verified"]} inherited files are unchanged. Original-arc geometry, profile interpolation, ledger lengths, panel conservation and positive A-phase derivatives were checked. Short fragments created by exact panel clipping remain flagged for future physical review.</p>']
    for label,name in images:
        uri='data:image/png;base64,'+base64.b64encode((out/name).read_bytes()).decode()
        body.append(f'<figure><figcaption>{html.escape(label)}</figcaption><img alt="{html.escape(label)}" src="{uri}"></figure>')
    body+=['<h2>Next artistic decisions</h2><p>Review the rising right-hand summit, the shallow hollow across P2–P3, and the spacing of the foreground groves. Review virtual color territory separately from ink concentration. Dense canopy contacts, short ground structures and seam fragments need a later measured physical simplification pass.</p>',
        '<p>The original accepted grammars remain reusable modules; new placement and omission fields belong only to Summer. Far-only B surface micro texture is disabled. Mid/far vegetation uses the existing reduced growth graphs and independent foliage-color passages.</p></main></html>']
    (out/'Review.html').write_text('\n'.join(body))
    print('Portable review page written')

if __name__=='__main__':run()
