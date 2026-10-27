"""Additive seasonal composition study on the immutable PR37 checkpoint."""
from pathlib import Path
from copy import deepcopy
import gzip, hashlib, importlib.util, io, json, os, pickle, sys
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, gaussian_filter1d
from shapely.geometry import LineString

ROOT=Path(__file__).resolve().parents[2]
PIN='a6ce842cfb894ce35e15332f3b6c6154254708ec'
sys.path.insert(0,str(ROOT/'studies/seasonal_screen_v01'))
import common as accepted
import diagnostics as accepted_review
prior=accepted.prior
read=accepted.read
sample=accepted.sample
smoothstep=accepted.smoothstep
phase=accepted.phase
digest=accepted.digest
length=accepted.length

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.pending')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temp.replace(path)

def gz(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    temp=path.with_name(path.name+'.pending')
    temp.write_bytes(gzip.compress(raw,mtime=0));temp.replace(path)

def png(path,image):
    """Install a complete decoded PNG atomically, including large reviews."""
    from PIL import Image
    buf=io.BytesIO();image.save(buf,format='PNG');raw=buf.getvalue()
    with Image.open(io.BytesIO(raw)) as check:check.load()
    path=Path(path);temp=path.with_name(path.name+'.pending');temp.write_bytes(raw);temp.replace(path)

def figure_png(fig,path,dpi=150):
    from PIL import Image
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=dpi)
    with Image.open(io.BytesIO(buf.getvalue())) as im:im.load();png(path,im)

def portable(value):
    if isinstance(value,np.ndarray):
        good=value[np.isfinite(value)]
        return dict(shape=list(value.shape),minimum=float(good.min()) if good.size else None,maximum=float(good.max()) if good.size else None)
    if isinstance(value,dict):return {k:portable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [portable(v) for v in value]
    if isinstance(value,np.generic):return value.item()
    return value

def rename(value,case):
    if isinstance(value,str):return value.replace('summer/',case+'/')
    if isinstance(value,list):return [rename(v,case) for v in value]
    if isinstance(value,dict):return {k:rename(v,case) for k,v in value.items()}
    return value

def clip_depth(rows,f,lo=0,hi=np.inf,namespace='domain'):
    """Clip in original arc space; never move a contour to match a boundary."""
    out=[];ledger=[];sources=[]
    q=f['base']['depth_m']
    for i,original in enumerate(rows):
        r=deepcopy(original);r['id']=namespace+'/'+str(i)+'/'+r['id']
        sources.append(r)
        def gate(p,arc,r):
            at=sample(q,p)
            return np.minimum(at-lo,hi-at),['source-depth-domain']
        parts,a=prior.clip_review(r,gate,minimum_mm=2.8)
        out.extend(parts);ledger.append(a)
    return out,sources,ledger

def publish(out,ink,color,sources,ledger,f,c,placement,generation):
    """Atomic canonical output and lossless panels with actual P1–P8 IDs."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for r in ink+color+sources:
        r['scene_season']=c['season']
        if r.get('catalog_version') and 'season' in r:r['catalog_reference_season']=r['season']
    unique={}
    for r in sources:
        if r['id'] in unique:
            for key in ['xy_mm','width_mm','width_profile_mm','opacity_profile']:
                if unique[r['id']].get(key)!=r.get(key):raise ValueError('Conflicting authoring identity '+r['id'])
        unique[r['id']]=r
    gz(out/'ink.json.gz',dict(continuous_mm=[600,900],strokes=ink))
    gz(out/'color_intent.json.gz',dict(continuous_mm=[600,900],strokes=color))
    gz(out/'authoring_sources.json.gz',dict(strokes=list(unique.values())))
    gz(out/'visibility_ledger.json.gz',dict(entries=ledger))
    panels={}
    for local,n in enumerate(c['panels']):
        ii=prior.panel_rows(ink,3+local);cc=prior.panel_rows(color,3+local)
        for r in ii+cc:
            r['panel']=n
            r['id']=r['id'].replace(f'/P{3+local}-',f'/P{n}-')
        gz(out/f'P{n}.vectors.json.gz',dict(panel=n,size_mm=[300,900],continuous_x_offset_mm=local*300,strokes=ii+cc))
        panels[f'P{n}']=dict(ink=prior.stats(ii),color=prior.stats(cc))
    save(out/'statistics.json',dict(ink=prior.stats(ink),color=prior.stats(color),panels=panels))
    save(out/'config.json',c);save(out/'placement.json',placement);save(out/'generation.json',portable(generation))
    buf=io.BytesIO()
    np.savez_compressed(buf,occupied=f['base']['occupied'],depth=f['base']['depth_m'].astype('float32'),retention=f['retention'].astype('float32'))
    tmp=out/'fields.npz.pending';tmp.write_bytes(buf.getvalue());tmp.replace(out/'fields.npz')
    for key,rr,width in [('scene',ink+color,600),('ink',ink,600)]:accepted_review.svg(rr,out/(key+'.svg'),c,width)
    for n in c['panels']:accepted_review.svg(read(out/f'P{n}.vectors.json.gz')['strokes'],out/f'P{n}.svg',c,300)

