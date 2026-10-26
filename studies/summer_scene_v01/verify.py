"""Independent artifact readback, lineage and panel-conservation verification."""
from pathlib import Path
import argparse, gzip, hashlib, importlib.metadata, json, subprocess, sys
import numpy as np
from shapely.geometry import LineString
from shapely.ops import substring
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'docs/experiments/summer_scene_v01'
BASE='d30ac7be302e1cbfcd2cf66de9087e35ea091b6c'

def read(path):
    raw=Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)

def validate_rows(rows,sources,*,minimum=2.8):
    ids=set();maximum_error=0.;length=0.
    for r in rows:
        if r['id'] in ids:raise ValueError('duplicate final id')
        ids.add(r['id']);p=np.asarray(r['xy_mm'],float)
        if p.ndim!=2 or p.shape[1]!=2 or len(p)<2 or not np.isfinite(p).all():raise ValueError('invalid path')
        if np.any(p[:,0]<-1e-7) or np.any(p[:,0]>600+1e-7) or p[:,1].min()<0 or p[:,1].max()>=898:raise ValueError('canvas/bottom guard')
        for key in ['width_profile_mm','opacity_profile']:
            if key in r and (len(r[key])!=len(p) or not np.isfinite(r[key]).all()):raise ValueError('profile alignment')
        if 'intensity_samples' in r.get('expression',{}):
            if len(r['expression']['intensity_samples'])!=len(p):raise ValueError('expression alignment')
        source_id=r['source_stroke_id']
        if source_id not in sources:raise ValueError('missing direct authoring source')
        source=sources[source_id];a,b=r['source_arc_mm'];line=LineString(source['xy_mm'])
        if not -1e-7<=a<=b<=line.length+1e-7:raise ValueError('source interval')
        actual=LineString(p);expected=substring(line,a,b)
        error=actual.hausdorff_distance(expected);maximum_error=max(maximum_error,error)
        if error>1e-6 or abs(actual.length-(b-a))>1e-6:raise ValueError('original-arc geometry mismatch')
        if actual.length<minimum-1e-6:raise ValueError('short canonical fragment')
        for key in ['width_profile_mm','opacity_profile']:
            if key in source:
                arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(source['xy_mm'],axis=0),axis=1))]
                at=np.r_[a,a+np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
                if not np.allclose(r[key],np.interp(at,arc,source[key]),atol=1e-8,rtol=0):raise ValueError('profile lineage mismatch')
        length+=actual.length
    return dict(paths=len(rows),length_mm=length,max_source_hausdorff_error_mm=maximum_error)

def check_panels(full,panels):
    byid={r['id']:r for r in full};conservation={k:0. for k in byid};max_error=0.;short=[]
    for number,rows in panels.items():
        for r in rows:
            p=np.asarray(r['xy_mm']);offset=(number-3)*300
            if p[:,0].min()<-1e-7 or p[:,0].max()>300+1e-7:raise ValueError('panel range')
            if r['continuous_x_offset_mm']!=offset:raise ValueError('panel registration')
            source=byid[r['canonical_source_id']];a,b=r['canonical_arc_mm'];line=LineString(source['xy_mm'])
            actual=LineString(p+[offset,0]);expected=substring(line,a,b);err=actual.hausdorff_distance(expected);max_error=max(max_error,err)
            if err>1e-6 or abs(actual.length-(b-a))>1e-6:raise ValueError('panel geometry or source arc mismatch')
            source_arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(source['xy_mm'],axis=0),axis=1))]
            at=np.r_[a,a+np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
            for key in ('width_profile_mm','opacity_profile'):
                if key in source:
                    if len(r[key])!=len(p) or not np.allclose(r[key],np.interp(at,source_arc,source[key]),atol=1e-8,rtol=0):raise ValueError('panel profile interpolation')
            if 'intensity_samples' in source.get('expression',{}):
                expected_profile=np.interp(at,source_arc,source['expression']['intensity_samples'])
                if not np.allclose(r['expression']['intensity_samples'],expected_profile,atol=1e-8,rtol=0):raise ValueError('panel expression interpolation')
            conservation[source['id']]+=actual.length
            if actual.length<2.8:short.append(dict(id=r['id'],length_mm=actual.length))
    error=max(abs(conservation[k]-LineString(r['xy_mm']).length) for k,r in byid.items())
    if error>1e-6:raise ValueError('panel length loss/duplication')
    return dict(max_source_length_error_mm=error,max_geometry_error_mm=max_error,short_seam_fragments=short)

def run(out=DEFAULT):
    out=Path(out);ink=read(out/'summer_ink.json.gz')['strokes'];col=read(out/'summer_color_intent.json.gz')['strokes'];source=read(out/'authoring_sources.json.gz')['strokes']
    sources={r['id']:r for r in source}
    if len(sources)!=len(source):raise ValueError('duplicate authoring IDs')
    checks=dict(ink=validate_rows(ink,sources),color=validate_rows(col,sources))
    checks['panels']=check_panels(ink+col,{n:read(out/f'P{n}.vectors.json.gz')['strokes'] for n in (3,4)})
    ledger=read(out/'visibility_ledger.json.gz')['entries'];retained={}
    for entry in ledger:
        kept=sum(b-a for a,b in entry['kept_intervals_mm'])
        if abs(entry['source_length_mm']-entry['removed_mm']-kept)>1e-6:raise ValueError('ledger length conservation')
        retained[entry['source_id']]=kept
    actual={}
    for r in ink+col:actual[r['source_stroke_id']]=actual.get(r['source_stroke_id'],0)+LineString(r['xy_mm']).length
    if any(abs(v-actual.get(k,0))>1e-6 for k,v in retained.items()):raise ValueError('ledger differs from visible output')
    baseline=subprocess.check_output(['git','ls-tree','-r',BASE],cwd=ROOT,text=True).splitlines();changed=[]
    for line in baseline:
        meta,name=line.split('\t');mode,kind,blob=meta.split()
        if kind!='blob':continue
        p=ROOT/name
        if not p.exists():changed.append(name);continue
        raw=p.read_bytes();actual_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if actual_blob!=blob:changed.append(name)
    if changed:raise ValueError('Inherited source changed: '+str(changed))
    for p in out.glob('*.png'):
        with Image.open(p) as im:im.load()
    if list(out.rglob('*.gcode')):raise ValueError('Unexpected motion output')
    gen=read(out/'generation.json')
    if gen['far_micro_B_enabled'] or gen['production_Gcode_generated'] or gen['Spring_modified']:raise ValueError('scope violation')
    for name in ('mountain_solver','foreground_solver'):
        solver=gen['terrain'][name]
        if solver['solver_status']!='solved' or solver['nonpositive_phase_derivative_pixels']!=0:raise ValueError('A phase topology')
    versions={k:importlib.metadata.version(k) for k in ['numpy','scipy','matplotlib','rasterio','shapely','contourpy','osqp','pillow','PyYAML','pytest']}
    result=dict(status='passed',checks=checks,ledger_entries=len(ledger),inherited_files_verified=len(baseline),inherited_changes=changed,
        PNGs_decoded=len(list(out.glob('*.png'))),versions=versions,scope='Offline artifact geometry and provenance; no physical calibration assertion')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT);a=p.parse_args();run(a.output)
