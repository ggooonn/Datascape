"""Approved Spring v13 snapshot, explicit offline export and exact replay.

No geometry generation occurs during export. Unresolved pressure requires an
explicit offline placeholder; it is never normalized from width or alpha.
"""
from pathlib import Path
from copy import deepcopy
import argparse,gzip,hashlib,json,math

ROOT=Path(__file__).resolve().parents[2]
SNAPSHOT=ROOT/'artworks/spring_v13'


def read(path):
    path=Path(path)
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    path.write_bytes(gzip.compress(data,mtime=0) if path.suffix=='.gz' else data)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_snapshot(root=SNAPSHOT):
    approval=read(root/'approval.json')
    for n,h in approval['approved_snapshot_hashes'].items():
        if sha(root/n)!=h:raise ValueError('approved snapshot hash mismatch: '+n)
    rows=[]
    for medium in ['ink','color']:
        for index,r in enumerate(read(root/f'visible_{medium}.json.gz')['strokes']):rows.append((medium,index,r))
    return rows,read(root/'ordering.json')['phases'],read(root/'palette.json')


def inspect_path(r,medium,palette):
    p=r['xy_mm'];ident=r['id']
    if len(p)<2:raise ValueError('unsupported point-contact primitive: '+ident)
    if any(len(v)!=2 or not all(math.isfinite(x) for x in v) or not 0<=v[0]<=600 or not 0<=v[1]<=900 for v in p):raise ValueError('invalid artwork geometry: '+ident)
    length=sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(p,p[1:]))
    if length<=0:raise ValueError('unsupported zero-length/dot primitive: '+ident)
    if any(r.get(k) is True for k in ['nonplotting','guide_only','diagnostic_only']):raise ValueError('nonplotting record in canonical snapshot: '+ident)
    if medium=='ink' and 'palette_slot' in r:raise ValueError('palette color in ink data')
    if medium=='color' and r.get('palette_slot') not in palette['slots']:raise ValueError('unknown color slot')
    for k in ['width_profile_mm','opacity_profile','source_forward_profile_m','pressure_intent_samples']:
        if k in r and (len(r[k])!=len(p) or not all(math.isfinite(x) for x in r[k])):raise ValueError('invalid profile: '+ident+'/'+k)
    if 'pressure_intent_samples' in r and not all(0<=x<=1 for x in r['pressure_intent_samples']):raise ValueError('pressure outside [0,1]')
    return length


def export(output,metadata,unresolved_pressure=None,offline_only=False,root=SNAPSHOT):
    rows,phases,palette=load_snapshot(root);missing=sum('pressure_intent_samples' not in r for _,_,r in rows)
    if missing and (unresolved_pressure is None or not offline_only):raise ValueError(f'{missing} strokes lack original normalized pressure; require --offline-only and --unresolved-pressure VALUE')
    if unresolved_pressure is not None and (not math.isfinite(unresolved_pressure) or not 0<=unresolved_pressure<=1):raise ValueError('explicit offline pressure must be in [0,1]')
    strokes=[];info=[];seen=set();counts={'ink':0,'color':0};point_counts={'source_pressure':0,'offline_placeholder':0}
    for sequence,(medium,index,r) in enumerate(rows):
        ident=r['id'];length=inspect_path(r,medium,palette)
        if ident in seen:raise ValueError('duplicate stroke ID: '+ident)
        seen.add(ident);counts[medium]+=1
        phase=next(p for p in phases if p['start']<=sequence<p['start']+p['count'])
        available='pressure_intent_samples' in r;pressure=r.get('pressure_intent_samples',[unresolved_pressure]*len(r['xy_mm']))
        points=[dict(x=p[0],y=p[1],pressure=q) for p,q in zip(r['xy_mm'],pressure)]
        point_counts['source_pressure' if available else 'offline_placeholder']+=len(points)
        strokes.append(dict(stroke_id=ident,points=points,medium=medium,layer=r.get('layer') or r['source_family'],color_slot='INK' if medium=='ink' else r['palette_slot'],order_group=phase['order_group'],sequence=sequence,reorderable=False,reversible=False))
        info.append(dict(stroke_id=ident,source_record_file=f'visible_{medium}.json.gz',source_record_index=index,source_record_sha256=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),source_family=r['source_family'],owner_id=r.get('owner_id'),material_role=r.get('color_kind',r.get('grammar_part',r['source_family'])),channel=phase['name'],pressure_status='original_normalized_intent' if available else 'missing_in_source_explicit_offline_placeholder',original_normalized_pressure_present=available,width_profile_present='width_profile_mm' in r,expressive_width_intent=bool(r.get('expressive_width_intent')),short_polyline_under_1mm=length<1.0))
    machine=dict(schema='datascape.machine_vectors.v0.1',artwork_size_mm=[600,900],strokes=strokes)
    manifest=dict(schema='datascape.spring_machine_metadata.v1',counts=counts,total_strokes=len(strokes),original_pressure_strokes=len(strokes)-missing,missing_original_pressure_strokes=missing,point_pressure_counts=point_counts,offline_placeholder=unresolved_pressure,offline_placeholder_is_original_or_calibrated=False,offline_only=offline_only,all_strokes_preserved=True,all_XY_points_preserved=True,unsupported_point_or_zero_length_primitives=[],direction='source vertex order, reversal disabled',ordering='frozen ink then original color-channel order, all sequence positions locked',physical_wet_sequence_calibrated=False,width_to_pressure_mapping=None,preview_alpha_is_pigment_concentration=False,per_stroke=info)
    write(output,machine);write(metadata,manifest);return manifest


def verify(machine_path,metadata_path,root=SNAPSHOT):
    rows,phases,palette=load_snapshot(root);machine=read(machine_path);meta=read(metadata_path)
    assert machine['schema']=='datascape.machine_vectors.v0.1' and machine['artwork_size_mm']==[600,900]
    assert len(machine['strokes'])==len(rows)==len(meta['per_stroke'])==14951
    seen=set()
    for seq,((medium,index,r),s,m) in enumerate(zip(rows,machine['strokes'],meta['per_stroke'])):
        inspect_path(r,medium,palette)
        assert s['stroke_id']==m['stroke_id']==r['id'] and s['stroke_id'] not in seen;seen.add(s['stroke_id'])
        assert [[p['x'],p['y']] for p in s['points']]==r['xy_mm']
        assert all('pressure' in p and math.isfinite(p['pressure']) and 0<=p['pressure']<=1 for p in s['points'])
        expected=r.get('pressure_intent_samples',[meta['offline_placeholder']]*len(r['xy_mm']))
        assert [p['pressure'] for p in s['points']]==expected
        assert m['original_normalized_pressure_present']==('pressure_intent_samples' in r)
        assert m['source_record_file']==f'visible_{medium}.json.gz' and m['source_record_index']==index
        assert m['source_record_sha256']==hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        phase=next(p for p in phases if p['start']<=seq<p['start']+p['count'])
        assert s['medium']==medium and s['layer']==(r.get('layer') or r['source_family'])
        assert s['color_slot']==('INK' if medium=='ink' else r['palette_slot'])
        assert s['order_group']==phase['order_group'] and s['sequence']==seq and not s['reversible'] and not s['reorderable']
    assert meta['counts']=={'ink':3345,'color':11606} and meta['original_pressure_strokes']==675 and meta['missing_original_pressure_strokes']==14276
    assert meta['offline_only'] and not meta['offline_placeholder_is_original_or_calibrated']
    return dict(strokes=len(rows),counts=meta['counts'],original_pressure_strokes=meta['original_pressure_strokes'],missing_original_pressure_strokes=meta['missing_original_pressure_strokes'],all_XY_and_IDs_exact=True,all_ordering_and_slots_exact=True,explicit_pressure_at_every_backend_point=True)


def backend_check(machine_path,backend_directory):
    """Read PR23's loader/models/scheduler without changing or running its CLI."""
    import sys,types,importlib
    obj=read(machine_path)
    assert all('pressure' in p for s in obj['strokes'] for p in s['points'])
    name='_spring_v13_contract_check';package=types.ModuleType(name);package.__path__=[str(backend_directory)];sys.modules[name]=package
    io=importlib.import_module(name+'.io');schedule=importlib.import_module(name+'.scheduling').schedule
    if machine_path.suffix=='.gz':raise ValueError('Decompress or export ordinary JSON for the unmodified PR23 loader')
    strokes=io.load_strokes(machine_path);ordered=schedule(strokes)
    assert [s.stroke_id for s in ordered]==[s['stroke_id'] for s in obj['strokes']]
    return dict(backend_loader_strokes=len(strokes),scheduler_order_preserved=True,backend_files_sha256={n:sha(backend_directory/n) for n in ['io.py','models.py','scheduling.py']},G_code_generated=False)


def preview(machine_path,output,compress_svg=False,root=SNAPSHOT):
    """XY from the export; artistic display profiles from immutable rich records.

Physical pressure is NOT used as display width. The SVG has the same profiled
ink segments and display-only color footprint as the approved raster renderer.
"""
    import io,re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection,PolyCollection
    from datascape.rendering.spring_macro_study import width_envelope
    from datascape.rendering.spring_massing_v07 import readable
    rows,_,palette=load_snapshot(root);machine=read(machine_path);ink=[];color=[]
    assert len(rows)==len(machine['strokes'])
    for (medium,_,r),s in zip(rows,machine['strokes']):
        assert s['stroke_id']==r['id'];r=deepcopy(r);r['xy_mm']=[[p['x'],p['y']] for p in s['points']]
        (ink if medium=='ink' else color).append(r)
    color=readable(color,read(root/'source/render_config.json'));output.mkdir(parents=True,exist_ok=True)
    with matplotlib.rc_context({'svg.hashsalt':'datascape-spring-v13-checkpoint'}):
        for mode in ['ink','color','combined']:
            fig=plt.figure(figsize=(8,12),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,600),ylim=(900,0));ax.axis('off');ax.patch.set_alpha(0)
            for records,is_color in [([] if mode=='color' else ink,False),([] if mode=='ink' else color,True)]:
                lines=[];widths=[];colors=[];polys=[];pc=[]
                for r in records:
                    p=np.array(r['xy_mm']);w=np.asarray(r.get('width_profile_mm',[r['width_mm']]*len(p)));a=np.asarray(r.get('opacity_profile',[r.get('preview_opacity',r.get('opacity',1.))]*len(p)))
                    rgb=matplotlib.colors.to_rgb(palette['slots'][r['palette_slot']]['preview_hex']) if is_color else (0,0,0)
                    if is_color and r.get('expressive_width_intent'):
                        shape=width_envelope(r)
                        for part in getattr(shape,'geoms',[shape]):
                            if part.geom_type=='Polygon':polys.append(np.asarray(part.exterior.coords));pc.append((*rgb,float(a.mean())))
                    elif is_color:lines.append(p);widths.append(float(w.mean()));colors.append((*rgb,float(a.mean())))
                    else:
                        lines.extend(np.stack([p[:-1],p[1:]],axis=1));widths.extend((w[:-1]+w[1:])/2);colors.extend([(*rgb,float(v)) for v in (a[:-1]+a[1:])/2])
                ax.add_collection(LineCollection(lines,linewidths=np.asarray(widths)*1200/600*72/150,colors=colors,capstyle='round',joinstyle='round'))
                if polys:ax.add_collection(PolyCollection(polys,facecolors=pc,edgecolors='none'))
            fig.savefig(output/(mode+'.png'),format='png',dpi=150,transparent=False,facecolor='white')
            buf=io.BytesIO();fig.savefig(buf,format='svg',metadata={'Date':None});plt.close(fig)
            text=buf.getvalue().decode();text=re.sub(r'(<svg\b[^>]*?)\bwidth="[^"]+"',r'\1width="600mm"',text,count=1,flags=re.S);text=re.sub(r'(<svg\b[^>]*?)\bheight="[^"]+"',r'\1height="900mm"',text,count=1,flags=re.S)
            (output/(mode+'.svg.gz' if compress_svg else mode+'.svg')).write_bytes(gzip.compress(text.encode(),mtime=0) if compress_svg else text.encode())


def replay(output,root=SNAPSHOT):
    """Re-run only the approved deterministic left-foreground operation."""
    from datascape.integration.recovered_spring_v13 import run
    from datascape.rendering.spring_macro_study import write_gz
    output.mkdir(parents=True,exist_ok=False);control=output/'control';inputs=output/'inputs';control.mkdir();inputs.mkdir()
    obj=read(root/'source/replay_control.json.gz')
    write_gz(control/'after_ink.json.gz',dict(strokes=obj['ink']))
    for k,rr in obj['channels'].items():write_gz(control/f'after_channel_{k}.json.gz',dict(strokes=rr))
    order=['A','C','rock_soil','gestures','trunk','RSU'];write_gz(control/'after_color.json.gz',dict(strokes=sum((obj['channels'][k] for k in order),[])))
    (control/'config.json').write_text(obj['config_text']);(control/'record.json').write_text(obj['record_text'])
    manifest=read(root/'source/fields_manifest.json');parts=[]
    for part in manifest['parts']:
        path=root/'source'/part['path'];assert sha(path)==part['sha256'];parts.append(path.read_bytes())
    data=b''.join(parts);assert hashlib.sha256(data).hexdigest()==manifest['file_sha256'];(inputs/'fields.npz').write_bytes(data);(inputs/'objects.json').write_bytes((root/'source/objects.json').read_bytes())
    run(control,inputs,output/'vectors')
    result={f'visible_{k}.json.gz':sha(output/f'vectors/after_{k}.json.gz')==sha(root/f'visible_{k}.json.gz') for k in ['ink','color']}
    assert all(result.values());return dict(canonical_vector_bytes_exact=result)


def main():
    p=argparse.ArgumentParser(__doc__);sub=p.add_subparsers(dest='command',required=True)
    e=sub.add_parser('export');e.add_argument('--output',type=Path,required=True);e.add_argument('--metadata',type=Path,required=True);e.add_argument('--offline-only',action='store_true');e.add_argument('--unresolved-pressure',type=float)
    v=sub.add_parser('verify');v.add_argument('--machine',type=Path,required=True);v.add_argument('--metadata',type=Path,required=True)
    b=sub.add_parser('backend-check');b.add_argument('--machine',type=Path,required=True);b.add_argument('--backend-directory',type=Path,required=True)
    d=sub.add_parser('preview');d.add_argument('--machine',type=Path,required=True);d.add_argument('--output',type=Path,required=True);d.add_argument('--compress-svg',action='store_true')
    a=sub.add_parser('replay');a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='export':r=export(a.output,a.metadata,a.unresolved_pressure,a.offline_only);print(json.dumps({k:v for k,v in r.items() if k!='per_stroke'},indent=2))
    elif a.command=='verify':print(json.dumps(verify(a.machine,a.metadata),indent=2))
    elif a.command=='backend-check':print(json.dumps(backend_check(a.machine,a.backend_directory),indent=2))
    elif a.command=='replay':print(json.dumps(replay(a.output),indent=2))
    else:preview(a.machine,a.output,a.compress_svg)


if __name__=='__main__':main()
