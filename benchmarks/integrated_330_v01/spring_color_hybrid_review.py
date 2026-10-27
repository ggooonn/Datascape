"""Focused comparison report for the immutable PR43 hybrid-reload revision."""
import base64, csv, html, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from . import spring_color_execution as c
from .spring_color_review import mixing_report


def review(out,summary,commands,selected,order):
    out=Path(out);rows=summary['comparisons']
    with (out/'reload_comparison.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['contact_limit','total_loads','same_pigment_reloads','pigment_changes','paper_contacts',
            'max_contacts_since_load','max_distance_since_load_mm','modeled_minutes'])
        for k,r in rows.items():
            w.writerow([r['contact_limit'],r['total_loads'],r['same_pigment_reloads'],r['pigment_changes'],
                r['contact_count'],r['maximum_contacts_since_load'],r['maximum_distance_since_load_mm'],r['modeled_seconds']/60])
    labels=['PR43 distance only','600mm OR15 contacts','600mm OR20 contacts','600mm OR30 contacts']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    values=list(rows.values());colors=['#adb5ae','#386c57','#7c9e86','#a3b4a2']
    axes[0].barh(labels,[r['total_loads'] for r in values],color=colors);axes[0].invert_yaxis()
    axes[0].set_xlabel('Total pigment loading operations')
    axes[1].barh(labels,[r['modeled_seconds']/60 for r in values],color=colors);axes[1].invert_yaxis()
    axes[1].set_xlabel('Modeled minutes; no manual/drying time')
    for i,r in enumerate(values):
        axes[0].text(r['total_loads']+.7,i,str(r['total_loads']),va='center')
        axes[1].text(r['modeled_seconds']/60+.3,i,f"{r['modeled_seconds']/60:.2f}",va='center')
    fig.savefig(out/'reload_comparison.png',dpi=160);plt.close(fig)
    material=c.read(out/'contact_15.material.json.gz')
    figures=plt.figure(figsize=(10,4),layout='constrained')
    ax=figures.subplots()
    budgets=[r['previous_contacts'] for r in material['loads'] if r['reason'] in ('distance_limit','contact_limit')]
    ax.hist(budgets,bins=[x-.5 for x in range(max(budgets,default=15)+2)],color='#477b62',edgecolor='white')
    ax.axvline(15,color='#9e5d38',linestyle='--',label='Preferred contact threshold')
    ax.set(xlabel='Actual paper contacts before same-pigment replenishment',ylabel='Replenishment operations')
    ax.legend();figures.savefig(out/'contact_budget.png',dpi=150);plt.close(figures)
    schedule=c.read(out/'schedule.json');graph=c.read(out/'layering_constraints.json.gz')
    mixing=mixing_report(commands,selected,graph['edges'],dict(wet_opportunity=schedule['wet_opportunity']))
    c.save(out/'overlap_and_mixing_intent.hybrid15.json.gz',mixing)
    p=summary['primary']
    text=f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spring P2 Hybrid Reload v02</title><style>body{{font:16px/1.65 system-ui;max-width:1300px;margin:auto;padding:28px;background:#f5f5ef;color:#203d30}}img{{max-width:100%;display:block}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:9px;border-bottom:1px solid #c6d0c5;text-align:left}}.note{{padding:18px;background:#ebe1cf}}pre{{white-space:pre-wrap;background:white;padding:15px}}</style>
<h1>Spring P2 · Hybrid Reload Revision</h1><p>Preferred:600mm OR15 actual paper contacts, complete-source service boundaries.
{p['total_loads']} pigment loads / {p['same_pigment_reloads']} same-pigment replenishments /5 actual changes.
{p['modeled_seconds']/60:.2f} modeled COLOR minutes;{p['AIR_modeled_seconds']/60:.2f} AIR minutes.</p>
<p class="note">Exact PR43 composition at8f7b1bb0ec2cd0b9fee639f370afe3b0518fa92b.
All3947 sources,40.017m, six pigments, A2→A4→C1→A5→C3→C2, source direction, geometry,
artistic pressure, explicit dose factors, paper XYZ/feed blocks and layering remain unchanged.
This first overprint remains for the existing PR35 ink P2. No ink-deferred stroke is added.</p>
<h2>Loading and runtime comparison</h2><table><tr><th>Policy</th><th>Loads</th><th>Same pigment</th><th>Changes/washes</th><th>Maximum contacts</th><th>Maximum distance mm</th><th>Modeled minutes</th></tr>"""
    for label,r in zip(labels,values):
        text+=f"<tr><td>{label}</td><td>{r['total_loads']}</td><td>{r['same_pigment_reloads']}</td><td>{r['pigment_changes']}</td><td>{r['maximum_contacts_since_load']}</td><td>{r['maximum_distance_since_load_mm']:.2f}</td><td>{r['modeled_seconds']/60:.2f}</td></tr>"
    text+='</table>'
    def image(name,title):
        nonlocal text
        raw=base64.b64encode((out/name).read_bytes()).decode()
        text+='<h2>'+title+'</h2><img src="data:image/png;base64,'+raw+'">'
    image('reload_comparison.png','Same frozen composition, only the loading policy changes')
    image('contact_budget.png','Actual-contact replenishment audit')
    image('P2_comparison.png','Unchanged PR43 composition / authored-width display proxy')
    image('P2_sequence.png','Unchanged pigment and paper-source sequence')
    text+=f"""<h2>Counter semantics</h2><p>A paper contact is one emitted initial_contact engagement, not a point or source ID and not a station dip.
A split source can contain several engagements. Both counters reset after every pigment load.
If either threshold is reached inside a source, finish every fragment of that source before replenishing.
Atomic distance and contact overruns are explicitly logged. This panel has{p['contact_count']} actual contacts.
A required reload occurs before the next source. Same-pigment reload performs no full wash or controlled rewet.
Actual pigment changes still perform one wash/PURGE/rewet before loading. Terminal three-water/two-PURGE cleanup remains separate.</p>
<h2>Primary files and reference alternatives</h2><p>Use the complete HYBRID15 COLOR file and its matching AIR as the primary pair.
The four HYBRID15 numbered stage pairs are alternatives for intermediate inspection.
They preserve the same concatenated source order and finish clean/parked after each stage.
Do not run COMPLETE and all four stages on the same sheet.</p>
<p>PR43's separate color-response coupon and station-only COLOR/AIR traces are byte-identical.
The independent color compression curve remains unmeasured and unchanged.
The new loading policy can change the time between overlapping pigments; updated commanded-feed lag ranges are supplied,
without claiming measured pigment mixing or paper drying.</p>
<h2>Physical first test</h2><p>Retain registered PR35 P2 globalX300–600, touch10/approach15/hover20, global35 transfers,
known start0/900/35 and terminal800/800/35/M2. No extra backing offset, routine M0, machine feed/YAML/station change or fine-brush color stage.
Use the retained spare-backed-hanji response coupon to inspect color delivery before the artwork.
Observe whether15 contacts prevents dry tails and excess loading, whether washing avoids cross-pigment contamination,
and whether increased replenishment changes the C1/A5 overlap appearance.
Existing palette/lip/container inspection limits from PR43 remain applicable.</p>
<p>Time models retain PR43 acceleration references and assumed JD0.01/full lookahead,
include programmed station motion/dwells/cleanup and exclude manual setup, drying and actual streaming/brush effects.
All offline verification is numerical, not a machine-clearance certificate.</p></html>"""
    (out/'Review.html').write_text(text)
