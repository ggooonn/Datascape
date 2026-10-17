"""Matched final-scale plates and an isolated reciprocal-mask proof."""
from pathlib import Path
from copy import deepcopy
import argparse, csv, hashlib, html, io, json, os, platform, subprocess, tempfile
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from matplotlib.collections import LineCollection
from datascape.vegetation import tree_catalog as old
from datascape.vegetation import tree_final_scale as gram
from datascape.vegetation import tree_occlusion_proof as occlusion
from datascape.vegetation import tree_spatial_groups as groups
from datascape.rendering import tree_review_support as render
from datascape.rendering.tree_review_support import footprint_sheet
from datascape.strokes.vector import save_vectors, read_vectors


def run(config_path, output, repo_root=None):
    """Publish complete figure bytes atomically, including inherited helpers."""
    from matplotlib.figure import Figure
    original = Figure.savefig
    def atomic_savefig(fig, filename, *args, **kwargs):
        if not isinstance(filename, (str, Path)):
            return original(fig, filename, *args, **kwargs)
        path = Path(filename); buffer = io.BytesIO()
        options = dict(kwargs); options.setdefault('format', path.suffix.lstrip('.'))
        original(fig, buffer, *args, **options); data = buffer.getvalue()
        if options['format'] == 'png':
            with Image.open(io.BytesIO(data)) as image: image.verify()
        fd, temporary = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    Figure.savefig = atomic_savefig
    try: return _run(config_path, output, repo_root)
    finally: Figure.savefig = original


def _run(config_path, output, repo_root=None):
    cp = Path(config_path).resolve(); repo = Path(repo_root) if repo_root else cp.parents[2]
    c = json.loads(cp.read_text()); seed = c['seed']; out = Path(output); out.mkdir(parents=True, exist_ok=True)
    parent = c['parent_catalog_commit']
    assert not subprocess.check_output(['git', 'diff', '--diff-filter=DMRT', '--name-only', parent], cwd=repo, text=True).strip()
    cache = {}; studies = {}; sheets = []; summaries = []; detail_windows = {}
    def tree(form, h, profile='refined'):
        key = (form, h, profile)
        if key not in cache:
            cache[key] = gram.make_tree(form, height=h, profile=profile, root=(75, 185), seed=seed, identity=form)
        return cache[key]
    def register(key, trees, clip=False):
        marks, note = old.overlap(trees) if clip else ([m for t in trees for m in t.marks], None)
        rr = gram.vector_records(marks, trees)
        save_vectors(out / (key + '.json.gz'), rr, {'study': c['study'], 'local_overlap': note, 'scene_integration': False})
        assert read_vectors(out / (key + '.json.gz'))['strokes'] == rr
        finalized = [old.length(s['xy_mm']) for s in rr if s['grammar_part'] == 'foliage-field']
        studies[key] = {'objects': [{'identity': t.identity, 'form': t.structure['catalog_form'], 'height_mm': t.height,
                                    'root_mm': t.root.tolist(), 'seed': t.seed, 'structure': t.structure,
                                    'canopy_diagnostics': t.canopy_diagnostics} for t in trees],
                        'local_overlap': note, 'metrics': render.metrics(marks), 'exported_paths': len(rr),
                        'finalized_foliage_paths': len(finalized), 'finalized_foliage_under_2_77_mm': sum(v < 2.77 for v in finalized)}
        wash = old.wash_metadata(trees)
        (out / (key + '.wash.json')).write_text(json.dumps(wash, indent=2, allow_nan=False) + '\n')
        return {'trees': trees, 'marks': marks}
    def stage(t, center_x=75, bottom=185):
        marks = deepcopy(t.marks); p = np.concatenate([m.xy for m in marks])
        shift = np.array([center_x - (p[:, 0].min() + p[:, 0].max()) / 2, bottom - p[:, 1].max()])
        for m in marks: m.xy += shift
        return marks
    def sheet(key, title, subtitle, cells, rows, cols, size, page_mm=None):
        for cell in cells:
            p = np.concatenate([m.xy for m in cell['marks']])
            assert np.all(p.min(axis=0) > [1, 23]) and np.all(p.max(axis=0) < [size[0]-1, size[1]-14]), (key, cell['title'], p.min(0), p.max(0))
        footprint_sheet(out, key, title, subtitle, cells, rows, cols, size, page_mm)
        sheets.append({'key': key, 'title': title, 'rows': rows, 'columns': cols,
                       'preview': 'Native physical coordinates / constant 0.8 mm assumed footprint'})
    # All 80 matched states are archived; named profiles are presets over three knobs.
    for form in 'PBUW':
        for h in c['physical_sizes_mm']:
            for profile in ['v09', 'touch', 'units', 'length', 'refined']:
                t = tree(form, h, profile); key = f'scale-{form}-{h}-{profile}'
                register(key, [t]); d = t.canopy_diagnostics; ll = gram.length_summary(t.marks)
                p = np.concatenate([m.xy for m in t.marks])
                summaries.append({'form': form, 'height_class_mm': h, 'profile': profile,
                    'actual_width_mm': float(np.ptp(p[:,0])), 'actual_height_mm': float(np.ptp(p[:,1])),
                    'units': d['retained_units'], 'foliage_paths': d['retained_foliage_paths'], 'all_paths': len(t.marks),
                    **{'length_'+k+'_mm': v for k, v in ll.items() if k != 'count'},
                    'touch_histogram': json.dumps(d['unit_touch_histogram'], sort_keys=True),
                    'requested_but_unavailable_touches': sum(max(0,u.get('requested_touches',u['touches'])-u.get('available_touches',u['touches'])) for u in d['units']),
                    'gap_rejected_extra_touches': sum(u.get('added_rays_rejected_by_gap',0) for u in d['units']),
                    'length_fallback_units': sum(u.get('length_fallback',False) for u in d['units'])})
            print(f'Matched {form} H{h}', flush=True)
    with (out/'scale_metrics.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summaries[0]),lineterminator='\n');writer.writeheader();writer.writerows(summaries)
    # 01: matched silhouettes across all four requested size classes.
    cells=[]
    for form in 'PBUW':
        for h in c['physical_sizes_mm']:
            a=tree(form,h,'v09');b=tree(form,h)
            cells.append({'marks':stage(a,75)+stage(b,205),'title':f'{form} / H{h} mm / v09 -> refinement',
                          'note':f'{a.canopy_diagnostics["retained_foliage_paths"]} -> {b.canopy_diagnostics["retained_foliage_paths"]} leaf paths / equal physical scale'})
    sheet('01_scale','01  Four forms / four physical size classes',
          'Each cell: immutable v09 left, final scale operator right. U H95/H130 is diagnostic enlargement; W remains experimental.',cells,4,4,(280,215))
    # 02: independent variables, identical sources and candidate supports.
    cells=[]
    for form,h in [('P',95),('P',130),('B',95),('B',130)]:
        for profile in ['v09','touch','units','length','refined']:
            t=tree(form,h,profile);d=t.canopy_diagnostics
            cells.append({'marks':stage(t,75),'title':f'{form} H{h} / {profile}',
                          'note':f'{d["retained_units"]} units / {d["retained_foliage_paths"]} leaf paths'})
    sheet('02_controls','02  Touches / unit count / length hierarchy are separate',
          'Columns: v09 / touch count only / unit budget x1.35 only / length only / touches + length. Physical clearance can couple achieved outputs.',cells,4,5,(150,215))
    # 03: render directly from vector geometry, never enlarge a raster crop.
    w,h=660,585;fig=render.plt.figure(figsize=(w/25.4,h/25.4),facecolor='white')
    title='03  Foliage unit detail / exact vector crop / 3.5x display magnification'
    fig.text(10/w,1-12/h,title,fontsize=15,fontweight='bold',va='top')
    fig.text(10/w,1-23/h,'Each window is 40 x 30 mm in source geometry; 0.8 mm footprint becomes 2.8 mm on this enlarged plate. Not a native-size plate.',fontsize=7.5,va='top')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/>',f'<text x="10" y="15" font-family="sans-serif" font-size="5">{html.escape(title)}</text>']
    for row,form in enumerate('PBUW'):
        for hi,height in enumerate([95,130]):
            t=tree(form,height);d=t.canopy_diagnostics
            unit=min((u for u in d['units'] if u['state']=='dense'),key=lambda u:u['radius_fraction'])
            mm=gram.bundles(t.marks)[unit['key']];center=np.mean(np.concatenate([m.xy for m in mm]),axis=0)
            bounds=[float(center[0]-20),float(center[1]-15),40.,30.];detail_windows[f'{form}-{height}']=bounds
            for j,profile in enumerate(['v09','refined']):
                col=hi*2+j;x=10+160*col;y=35+135*row
                ax=fig.add_axes([(x+5)/w,(h-y-130)/h,140/w,105/h]);ax.set(xlim=(bounds[0],bounds[0]+40),ylim=(bounds[1]+30,bounds[1]),aspect='equal');ax.axis('off')
                ax.add_collection(LineCollection([m.xy for m in tree(form,height,profile).marks],colors='#242c28',linewidths=.8*3.5*72/25.4,capstyle='round',joinstyle='round'))
                caption=f'{form} H{height} / {profile} / window 40 x 30 mm'
                fig.text((x+5)/w,1-(y+6)/h,caption,fontsize=9,va='top')
                svg.append(f'<text x="{x+5}" y="{y+8}" font-size="3" font-family="sans-serif">{html.escape(caption)}</text><svg x="{x+5}" y="{y+25}" width="140" height="105" viewBox="{bounds[0]} {bounds[1]} 40 30" overflow="hidden"><g fill="none" stroke="#242c28" stroke-width=".8" stroke-linecap="round" stroke-linejoin="round">')
                for m in tree(form,height,profile).marks:svg.append('<polyline points="'+' '.join(f'{a:.4f},{b:.4f}' for a,b in m.xy)+'"/>')
                svg.append('</g></svg>')
    fig.savefig(out/'03_detail.png',dpi=120);render.plt.close(fig);svg.append('</svg>');(out/'03_detail.svg').write_text('\n'.join(svg)+'\n')
    sheets.append({'key':'03_detail','title':title,'preview':'3.5x vector crop; source window 40 x 30 mm'})
    # 04: actual length distributions, not requested multiplier labels.
    fig,axs=render.plt.subplots(2,4,figsize=(15,6),sharex=True)
    for row,height in enumerate([95,130]):
        for col,form in enumerate('PBUW'):
            ax=axs[row,col]
            for profile,color in [('v09','#b39778'),('refined','#295647')]:
                vals=[old.length(m.xy) for m in tree(form,height,profile).marks if m.part=='foliage-field']
                ax.hist(vals,bins=np.arange(2.6,7.61,.2),histtype='step',color=color,label=f'{profile} / n={len(vals)}',linewidth=1.6)
            ax.axvline(2.8,color='#aa6258',ls=':',lw=.8);ax.set(title=f'{form} H{height}',xlabel='Leaf path length (mm)',ylabel='Actual paths');ax.legend(fontsize=7);ax.grid(alpha=.12)
    fig.suptitle('04  Source leaf length distributions / 2.8 mm assumed floor, not a measured brush limit',fontsize=13,fontweight='bold');fig.tight_layout(rect=(0,0,1,.95))
    fig.savefig(out/'04_lengths.png',dpi=140);fig.savefig(out/'04_lengths.svg');render.plt.close(fig);sheets.append({'key':'04_lengths','title':'Actual source length distributions','preview':'Data chart, not physical scale'})
    # 00: retain the existing shallow-plane and far-to-near group experiments.
    def group(kind,form=None,profile='refined'):
        members=groups.members(kind)
        if form:members=[groups.GroupMember(m.identity,form,m.u,m.depth,m.size_weight,m.role) for m in members]
        specs=groups.project(members,'spatial',center=(125,165),height_mm=(38 if form=='U' else 60) if kind=='three' else (35 if form=='U' else 42),span_mm=65 if form=='U' else 110,depth_mm=18 if form=='U' else 30)
        result=[]
        for spec in specs:
            m=spec['member'];i=int(m['identity'].rsplit('-',1)[1]);selected='v09' if m['form']=='U' and profile=='refined' else profile
            result.append(gram.make_tree(m['form'],height=spec['height'],root=spec['root'],seed=seed+11*i,identity=m['identity'],profile=selected,
                                         growth_controls=gram.prior.GrowthControls(vigor=.65 if i==1 and kind=='five' else 1)))
        return result
    cells=[]
    for form in 'PBUW':
        height=45 if form=='U' else 95;profile='v09' if form=='U' else 'refined';t=tree(form,height,profile)
        cell=register(f'overview-{form}-single',[t]);cell.update(marks=stage(t,125,165),title=f'{form} / single / H{height}',note='U uses the lighter v09 setting; W remains experimental');cells.append(cell)
        for kind in ['three','eight']:
            ts=group(kind,form);cell=register(f'overview-{form}-{kind}',ts,True)
            cell.update(title=f'{form} / {kind} / local shallow plane',note='Legacy dense-core clipping retained; not scene placement');cells.append(cell)
    sheet('00_overview','00  Provisional catalog / individual, three trees and serial band',
          'P/B are final-scale candidates; U keeps its lighter small-scale setting. W is retained as an experimental structural form.',cells,4,3,(260,205))
    cells=[]
    for kind in ['three','eight']:
        for profile in ['v09','refined']:
            ts=group(kind,profile=profile);cell=register(f'mixed-{kind}-{profile}',ts,True)
            cell.update(title=f'Mixed {kind} / {profile}',note='Same members, roots, seeds and depth order; legacy visibility remains');cells.append(cell)
    sheet('07_mixed','07  Mixed overlap / preserve existing local group tests',
          'Columns v09 / final scale settings. Far-to-near clipping is still a catalog diagnostic; hidden fragments and cross-tree spacing require later integration.',cells,2,2,(260,205))
    # 05: a single B tree over deliberately synthetic crossing rulers.
    proof_tree=gram.make_tree('B',root=(110,170),height=95,seed=seed,identity='mask-tree')
    a=occlusion.MaskAssumptions();masks=occlusion.masks(proof_tree,a);probes=occlusion.synthetic_probes();proof={};cells=[]
    for mode,title in [('none','Unmasked terrain + tree'),('full','Excessive full support masking'),('selective','Selective body + occupied units')]:
        rr,note=(deepcopy(probes),{'source_paths':len(probes),'retained_paths':len(probes),'removed_length_mm':0.,'short_fragment_length_dropped_mm':0.}) if mode=='none' else occlusion.clip_vectors(probes,masks[mode],1200,a)
        (out/f'proof-{mode}.terrain.json').write_text(json.dumps({'synthetic':True,'strokes':rr,'audit':note},indent=2)+'\n')
        marks=[old.Mark(r['id'],np.array(r['xy_mm']),.6,'synthetic-probe',None,'probe') for r in rr]+proof_tree.marks
        cells.append({'marks':marks,'title':title,'note':f'Removed {note["removed_length_mm"]:.1f} mm / {note["retained_paths"]} terrain pieces','footprint_mm':.8})
        proof[mode]=note
    # Separate width-aware proof renderer: terrain 0.6 mm, trees 0.8 mm.
    w,h=620,255;fig=render.plt.figure(figsize=(w/25.4,h/25.4),facecolor='white');fig.text(10/w,1-12/h,'05  Isolated reciprocal vector clipping proof / no F2 inputs',fontsize=14,fontweight='bold',va='top')
    fig.text(10/w,1-24/h,'Synthetic crossing rulers, not terrain grammar. Gray = terrain 0.6 mm; black = tree 0.8 mm. Nearer-depth ruler remains in all cases.',fontsize=7.7,va='top')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/>']
    for i,cell in enumerate(cells):
        x=10+200*i;y=40;ax=fig.add_axes([x/w,(h-y-200)/h,200/w,200/h]);ax.set(xlim=(15,215),ylim=(200,0),aspect='equal');ax.axis('off')
        for part,color,width in [('synthetic-probe','#a5aaa6',.6),('tree','#242c28',.8)]:
            mm=[m for m in cell['marks'] if (m.part=='synthetic-probe')==(part=='synthetic-probe')]
            ax.add_collection(LineCollection([m.xy for m in mm],colors=color,linewidths=width*72/25.4,capstyle='round',joinstyle='round'))
            svg.append(f'<g transform="translate({x-15} {y})" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">')
            for m in mm:svg.append('<polyline points="'+' '.join(f'{a:.4f},{b:.4f}' for a,b in m.xy)+'"/>')
            svg.append('</g>')
        ax.text(.02,.98,cell['title'],transform=ax.transAxes,fontsize=10,va='top');ax.text(.02,.92,cell['note'],transform=ax.transAxes,fontsize=7,va='top')
        svg.append(f'<text x="{x+4}" y="{y+5}" font-size="3.2" font-family="sans-serif">{html.escape(cell["title"])}</text><text x="{x+4}" y="{y+15}" font-size="2.4" font-family="sans-serif">{html.escape(cell["note"])}</text>')
    fig.savefig(out/'05_occlusion.png',dpi=140);render.plt.close(fig);svg.append('</svg>');(out/'05_occlusion.svg').write_text('\n'.join(svg)+'\n')
    save_vectors(out/'proof.vegetation.json.gz',gram.vector_records(proof_tree.marks,[proof_tree]),{'synthetic':True,'not_scene_integration':True})
    (out/'proof.wash.json').write_text(json.dumps(old.wash_metadata([proof_tree]),indent=2)+'\n')
    (out/'proof.masks.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'mask':key,'not_plotter_paths':True},'geometry':value.__geo_interface__} for key,value in masks.items() if key!='note']},indent=2)+'\n')
    sheets.append({'key':'05_occlusion','title':'Isolated reciprocal vector clipping proof','preview':'Width assumptions: terrain 0.6 mm, vegetation 0.8 mm'})
    # Native A4 coupon: translate only, no fit-to-page shape scaling.
    coupon=stage(tree('P',130),62,174)+stage(tree('B',95),153,174)
    for x,form in zip([30,75,120,165],'PBUW'):coupon+=stage(tree(form,22,'v09'),x,232)
    sheet('06_A4','06  Native A4 scale coupon / print at 100 percent',
          'Top: P H130 / B H95. Bottom: P/B/U/W H22. Verify the 10 mm ruler. Constant assumed 0.8 mm footprint; not calibrated ink.',
          [{'marks':coupon,'title':'Nominal class differs from actual extents; see scale_metrics.csv','note':'No pressure, drying, absorption or pigment simulation'}],1,1,(190,252),page_mm=(210,297))
    for path in out.glob('*.svg'):ET.parse(path)
    for path in out.glob('*.png'):
        with Image.open(path) as im:im.verify()
    source_paths=['src/datascape/vegetation/tree_final_scale.py','src/datascape/vegetation/tree_occlusion_proof.py','src/datascape/rendering/tree_final_scale_study.py','tests/test_tree_final_scale_unit.py','tests/test_tree_occlusion_proof_unit.py',str(cp.relative_to(repo))]
    result={'study':c['study'],'immutable_parent_revision':parent,
            'immutable_parent_file_count':len(subprocess.check_output(['git','ls-tree','-r','--name-only',parent],cwd=repo,text=True).splitlines()),
            'source_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in source_paths},
            'baseline_sha256_unchanged':hashlib.sha256((repo/'docs/baselines/spring_f2c_a025_v01/baseline_strokes.json.gz').read_bytes()).hexdigest(),
            'config':c,'sheets':sorted(sheets,key=lambda s:s['key']),'scale_metrics':summaries,'studies':studies,'detail_windows_mm':detail_windows,
            'synthetic_proof':proof,'mask_assumptions':a.__dict__,
            'versions':{'python':platform.python_version(),'numpy':np.__version__,'shapely':__import__('shapely').__version__},
            'validation':{'archive_roundtrip':True,'svg_parse':True,'png_decode':True,'scene_integration':False,'physical_plotting_validated':False,
                          'root_attachment':'unresolved','group_visibility':'legacy diagnostic retained','final_hardware_filter':'not applied to catalog archives'}}
    (out/'record.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='configs/experiments/tree_catalog_v10.json');p.add_argument('--output',default='outputs/tree-catalog-v10')
    a=p.parse_args();r=run(a.config,a.output);print(json.dumps({'states':len(r['studies']),'sheets':len(r['sheets'])}))


if __name__=='__main__':main()
