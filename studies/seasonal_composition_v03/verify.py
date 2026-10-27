"""Read back source arcs, exact panels, ledgers and immutable parent files."""
from shared import *
import argparse, importlib.metadata, subprocess
from PIL import Image

spec=importlib.util.spec_from_file_location('summer_v01_readback',ROOT/'studies/summer_scene_v01/verify.py')
pinned=importlib.util.module_from_spec(spec);spec.loader.exec_module(pinned)

def parent_invariants():
    """Check tracked edits and materialized bytes; sparse files stay in Git.

    The final publication uses PR37's base tree plus additions only. It is not
    necessary to download every inherited raster to assert that tree contract.
    """
    changed=subprocess.check_output(['git','diff','--name-only',PIN,'--'],cwd=ROOT,text=True).splitlines()
    inherited=set(subprocess.check_output(['git','ls-tree','-r','--name-only',PIN],cwd=ROOT,text=True).splitlines())
    violations=sorted(set(changed)&inherited)
    if violations:raise ValueError('Inherited tracked files changed: '+str(violations))
    entries=subprocess.check_output(['git','ls-tree','-r',PIN],cwd=ROOT,text=True).splitlines();checked=0
    for line in entries:
        meta,name=line.split('\t',1);mode,kind,want=meta.split();p=ROOT/name
        if kind!='blob' or not p.exists():continue
        raw=p.read_bytes();got=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if got!=want:raise ValueError('Materialized parent bytes changed: '+name)
        checked+=1
    return dict(parent=PIN,parent_entries=len(inherited),materialized_parent_bytes_checked=checked,inherited_changes=[],sparse_tree_policy='Published Git tree must equal PR37 tree plus new paths only')

def check(out,check_parent=True):
    out=Path(out);c=read(out/'config.json');ink=read(out/'ink.json.gz')['strokes'];color=read(out/'color_intent.json.gz')['strokes']
    sources=read(out/'authoring_sources.json.gz')['strokes'];lookup={r['id']:r for r in sources}
    if any(r.get('scene_season')!=c['season'] for r in ink+color+sources):raise ValueError('Scene season metadata')
    if len(lookup)!=len(sources):raise ValueError('Duplicate source identity')
    checks=dict(ink=pinned.validate_rows(ink,lookup),color=pinned.validate_rows(color,lookup))
    panels={}
    for local,n in enumerate(c['panels']):
        p=read(out/f'P{n}.vectors.json.gz')
        if p['panel']!=n or p['continuous_x_offset_mm']!=local*300:raise ValueError('Actual panel registration')
        for r in p['strokes']:
            if r['panel']!=n or f'/P{n}-' not in r['id']:raise ValueError('Actual panel identity')
        panels[3+local]=p['strokes']
    checks['panels']=pinned.check_panels(ink+color,panels)
    totals={}
    for r in ink+color:totals[r['source_stroke_id']]=totals.get(r['source_stroke_id'],0)+length(r)
    ledger=read(out/'visibility_ledger.json.gz')['entries']
    if len({e['source_id'] for e in ledger})!=len(ledger):raise ValueError('Duplicate final ledger entry')
    for e in ledger:
        kept=sum(b-a for a,b in e['kept_intervals_mm'])
        if abs(kept+e['removed_mm']-e['source_length_mm'])>1e-6 or abs(kept-totals.get(e['source_id'],0))>1e-6:raise ValueError('Visibility ledger conservation')
    if set(totals)-{e['source_id'] for e in ledger}:raise ValueError('Canonical source missing from final ledger')
    g=read(out/'generation.json')
    if g['Spring_modified'] or g['earlier_checkpoint_files_modified'] or g['production_Gcode_generated'] or g['far_micro_B_enabled']:raise ValueError('Scope violation')
    if g['near_solver']['solver_status']!='solved' or g['near_solver']['nonpositive_phase_derivative_pixels']!=0:raise ValueError('Nonmonotone near phase')
    flow=read(out/'flow_review.json')
    evidence=flow['route_source_evidence']
    if flow['global_reserve_override_pixels'] or len(evidence)<8 or np.ptp(np.array([r['xy_mm'][1] for r in evidence]))<180:raise ValueError('Uniform or unbounded middle release')
    with np.load(out/'fields.npz') as z:
        if z['occupied'].shape!=(900,600) or not np.isfinite(z['retention']).all():raise ValueError('Diagnostic fields')
        if np.any(z['retention'][~z['occupied']]!=0):raise ValueError('Retention outside visible terrain')
        if np.any(z['retention'][-2:]!=0):raise ValueError('Bottom reserve')
    images=list(out.glob('*.png'))
    for p in images:
        with Image.open(p) as im:im.load()
    if list(out.glob('*.gcode')):raise ValueError('Unexpected machine program')
    result=dict(status='passed',case=c['case'],checks=checks,authoring_sources=len(sources),visibility_entries=len(ledger),pngs_decoded=len(images),
        parent_invariants=parent_invariants() if check_parent else None,
        scope='Canonical geometry, artistic profiles, source evidence and publication isolation; no physical calibration')
    save(out/'verification.json',result);print('Verified',c['case'],len(ink),len(color),'paths',flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();check(a.output)

