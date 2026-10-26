"""Independent geometry, preserved records and panel readback checks."""
from common import *
import subprocess
from PIL import Image
import importlib.util
spec=importlib.util.spec_from_file_location('pinned_verify',ROOT/'studies/summer_scene_v01/verify.py');pinned=importlib.util.module_from_spec(spec);spec.loader.exec_module(pinned)
PIN='f2d03a592aec0e43368557391696f3b4c940db69'

def check(out):
    out=Path(out);c=read(out/'config.json');ink=read(out/'ink.json.gz')['strokes'];color=read(out/'color_intent.json.gz')['strokes'];sources=read(out/'authoring_sources.json.gz')['strokes'];lookup={r['id']:r for r in sources}
    if len(lookup)!=len(sources):raise ValueError('Duplicate source IDs')
    v=dict(ink=pinned.validate_rows(ink,lookup),color=pinned.validate_rows(color,lookup))
    panels={3+j:read(out/f'P{n}.vectors.json.gz')['strokes'] for j,n in enumerate(c['panels'])};v['panels']=pinned.check_panels(ink+color,panels)
    ledger=read(out/'visibility_ledger.json.gz')['entries'];actual={}
    for r in ink+color:actual[r['source_stroke_id']]=actual.get(r['source_stroke_id'],0)+length(r)
    for e in ledger:
        kept=sum(b-a for a,b in e['kept_intervals_mm'])
        if abs(kept+e['removed_mm']-e['source_length_mm'])>1e-6 or abs(kept-actual.get(e['source_id'],0))>1e-6:raise ValueError('Visibility ledger conservation')
    g=read(out/'generation.json')
    if c['case']=='summer-v02':
        oldink=read(BASE/'summer_ink.json.gz')['strokes'];oldcol=read(BASE/'summer_color_intent.json.gz')['strokes'];old={r['id']:r for r in oldink+oldcol};new={r['id']:r for r in ink+color}
        for ident in g['locked_record_ids']+g['frozen_color_ids']:
            if new.get(ident)!=old[ident]:raise ValueError('Pinned middle/far record changed')
        if g['foreground_solver']['nonpositive_phase_derivative_pixels']!=0:raise ValueError('Folded phase')
        v['unchanged_full_middle_far_records']=len(g['locked_record_ids'])+len(g['frozen_color_ids'])
    for p in out.glob('*.png'):
        with Image.open(p) as im:im.load()
    with np.load(out/'fields.npz') as f:
        if f['occupied'].shape!=(900,600):raise ValueError('Field shape')
    if list(out.rglob('*.gcode')):raise ValueError('Unexpected machine output')
    baseline=subprocess.check_output(['git','ls-tree','-r',PIN],cwd=ROOT,text=True).splitlines();changed=[]
    for line in baseline:
        meta,name=line.split('\t');mode,kind,blob=meta.split()
        if kind!='blob':continue
        raw=(ROOT/name).read_bytes();got=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if got!=blob:changed.append(name)
    if changed:raise ValueError('Inherited files changed: '+str(changed))
    result=dict(status='passed',checks=v,baseline_inherited_files_verified=len(baseline),inherited_changes=changed,ledger_entries=len(ledger),no_production_Gcode=True)
    save(out/'verification.json',result);print('Verified',c['case'],len(ink),len(color),'paths');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();check(a.output)
