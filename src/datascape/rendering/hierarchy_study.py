"""Compare a fixed spring stroke hierarchy, not another composition search."""
from pathlib import Path
from copy import deepcopy
import argparse,json,platform,io,os,gzip
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from datascape.data.quality import sha256_file
from datascape.strokes.scene import load_selected_scene
from datascape.strokes.generators import terrain_derivatives
from datascape.strokes.vector import read_vectors,save_vectors,resample,sample
from datascape.strokes.hierarchy import style,select_a,select_b,select_c,select_d,total_length,path_length
from datascape.rendering.composition_study import save_figure
from datascape.rendering.ground_study import make_camera


COLORS={'A':'#384d7a','B':'#874a92','C':'#55a9a3','D':'#b52b26','V':'#9a9a9a'}


def publish_png(data,path):
    """Decode and atomically publish complete PNG bytes."""
    with Image.open(io.BytesIO(data)) as image:image.load()
    path=Path(path);temp=path.with_name(path.stem+'.writing.png')
    with temp.open('wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    with Image.open(temp) as image:image.load()
    temp.replace(path)


def publish_vectors(path,strokes,provenance):
    """Publish a fully decoded deterministic vector payload atomically."""
    payload={'schema':'datascape.vector-strokes/0.1','units':'mm','origin':'upper left; y downward',
        'continuous_mm':[600,900],'panel_width_mm':300,'physical_gap_mm':40,
        'provenance':provenance,'strokes':strokes}
    buffer=io.BytesIO()
    with gzip.GzipFile(filename='',mode='wb',fileobj=buffer,mtime=0) as stream:
        stream.write((json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n').encode())
    data=buffer.getvalue();assert json.loads(gzip.decompress(data))['strokes']==strokes
    path=Path(path);temp=path.with_name(path.name+'.writing')
    with temp.open('wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    assert json.loads(gzip.decompress(temp.read_bytes()))['strokes']==strokes
    temp.replace(path)


def compose(pool,layers,c_low=False):
    result=[]
    for layer in layers:
        for s in pool:
            if s['layer']==layer and (not c_low or layer!='C' or s['density_low_member']):
                result.append({**s,'draw_order':len(result)})
    return result


def segments(strokes,mode,bounds,pixels):
    lines=[];widths=[];colors=[];pw=pixels[0];x0,y0,x1,y1=bounds
    for s in strokes:
        p=np.asarray(s['xy_mm']);profile=s.get('width_profile_mm')
        color=COLORS[s['layer']] if mode=='hierarchy' else 'black'
        opacity=s['preview_opacity'] if mode=='density' else 1
        rgba=matplotlib.colors.to_rgba(color,opacity)
        if profile is not None:
            for i in range(len(p)-1):
                lines.append(p[i:i+2]);widths.append((profile[i]+profile[i+1])/2);colors.append(rgba)
        else:lines.append(p);widths.append(s['width_mm']);colors.append(rgba)
    return lines,np.asarray(widths)*pw/(x1-x0)*72/150,colors


def render(strokes,path,mode='black',bounds=(0,0,600,900),pixels=(1200,1800)):
    x0,y0,x1,y1=bounds;pw,ph=pixels
    fig=plt.figure(figsize=(pw/150,ph/150),dpi=150,facecolor='white');ax=fig.add_axes([0,0,1,1])
    ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off')
    lines,widths,colors=segments(strokes,mode,bounds,pixels)
    ax.add_collection(LineCollection(lines,linewidths=widths,colors=colors,capstyle='round',joinstyle='round'))
    buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=150,facecolor='white');plt.close(fig);publish_png(buffer.getvalue(),path)


def write_svg(strokes,path,panel=None):
    width=600 if panel is None else 300;shift=300 if panel==2 else 0
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="900mm" viewBox="0 0 {width} 900">',
        '<rect width="100%" height="100%" fill="white"/>','<g fill="none" stroke="black" stroke-linecap="round" stroke-linejoin="round">']
    for s in strokes:
        if panel and s['panel']!=panel:continue
        p=np.array(s['xy_mm']);p[:,0]-=shift;profile=s.get('width_profile_mm')
        parts=[(s['id'],p,s['width_mm'])] if profile is None else [(s['id']+f'-{i}',p[i:i+2],(profile[i]+profile[i+1])/2) for i in range(len(p)-1)]
        for identity,xy,width in parts:
            points=' '.join(f'{x:g},{y:g}' for x,y in xy)
            lines.append(f'<polyline id="{identity}" stroke-width="{width:g}" points="{points}"/>')
    lines+=['</g>','</svg>'];Path(path).write_text('\n'.join(lines)+'\n')


def comparison(images,path,title,extent=(0,600,900,0)):
    fig,axes=plt.subplots(1,len(images),figsize=(4*len(images),6.5))
    for ax,(label,p) in zip(np.atleast_1d(axes),images.items()):
        ax.imshow(Image.open(p),extent=extent);ax.set_title(label,fontsize=10);ax.set_xlabel('mm');ax.set_yticks([0,300,600,900])
    fig.suptitle(title);fig.tight_layout();save_figure(fig,path)


def metrics(strokes,base):
    result={}
    for layer in ['A','B','C','D','V']:
        subset=[s for s in strokes if s['layer']==layer];length=total_length(subset)
        roles={key:0. for key in ['near','middle','far']}
        for s in subset:
            p=resample(s['xy_mm'],1);q=sample(base['depth_m'],p);dl=np.linalg.norm(np.diff(p,axis=0),axis=1)
            for key,lo,hi in [('near',0,1600),('middle',1600,3400),('far',3400,np.inf)]:roles[key]+=float(dl[(q[:-1]>=lo)&(q[:-1]<hi)].sum())
        result[layer]={'vectors':len(subset),'length_mm':length,'length_by_depth_mm':roles}
    all_length=sum(v['length_mm'] for v in result.values());terrain=all_length-result['V']['length_mm']
    return {'layers':result,'all_length_mm':all_length,'terrain_length_mm':terrain,
            'D_all_length_fraction':result['D']['length_mm']/max(all_length,1),
            'D_terrain_length_fraction':result['D']['length_mm']/max(terrain,1)}


def validate(pool,fixed,config):
    safe=distance_transform_edt((fixed['retention']>1e-8)&fixed['base']['occupied']);violations=0
    for s in pool:
        p=resample(s['xy_mm'],.16);width=max(s.get('width_profile_mm',[s['width_mm']]))
        if p[:,1].max()+width/2>=898:raise AssertionError('Bottom footprint violated.')
        if s['layer']!='V':violations+=int((sample(safe,p,order=0)<=width/2+.025).sum())
        if not np.isfinite(p).all():raise AssertionError('Nonfinite vector.')
    if violations:raise AssertionError(f'Omission-core violations: {violations}')
    d=[s for s in pool if s['layer']=='D'];parents={}
    for s in d:parents.setdefault(s['parent_path'],[]).append(resample(s['xy_mm'],.5))
    nearest=[];values=list(parents.values())
    for i,a in enumerate(values):
        if i+1<len(values):nearest.append(float(cKDTree(np.concatenate([p for group in values[i+1:] for p in group])).query(np.concatenate(a))[0].min()))
    min_spacing=min(nearest) if nearest else None
    if min_spacing is not None and min_spacing<config['D']['minimum_spacing_mm']-.1:raise AssertionError('D NMS spacing violated.')
    return {'terrain_core_sample_violations':violations,'all_footprints_empty_in_bottom_2mm':True,
            'D_minimum_other_event_spacing_mm':min_spacing,'D_parent_events':len(parents)}


def run(master,veg,config_path,output,repo_root=None):
    config_path=Path(config_path);root=Path(repo_root) if repo_root else config_path.resolve().parents[2]
    c=json.loads(config_path.read_text());selection=json.loads((root/c['selection']).read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    for path,digest in c['source_vector_sha256'].items():
        if sha256_file(root/path)!=digest:raise ValueError('Archived vector changed: '+path)
    print('Reconstruct fixed F2 C',flush=True);fixed=load_selected_scene(master,veg,root,selection)
    source={key:read_vectors(root/path)['strokes'] for key,path in c['source_vectors'].items()}
    a=select_a([s for s in source['A'] if s.get('layer')=='terrain'],fixed,c)
    context=style([s for s in source['A'] if s.get('layer')=='vegetation'],'V',c)
    derivative=terrain_derivatives(master,fixed['base'],c['derivatives'])
    b=select_b([s for s in source['B'] if s.get('layer')=='terrain'],fixed,derivative,c,total_length(a))
    flow=[s for s in source['C'] if s.get('layer')=='terrain']
    low=select_c(flow,fixed['base'],c,c['C']['low_density']);high=select_c(flow,fixed['base'],c,c['C']['dense_density'])
    low_ids={s['id'] for s in low}
    for s in high:s['density_low_member']=s['id'] in low_ids
    import rasterio
    sc=fixed['scene']
    with rasterio.open(master) as ds:camera,_=make_camera(ds,sc['primary_eye_xy_m'],sc['look_target_xy_m'],sc['eye_clearance_m'],sc['pitch_deg'],sc['vertical_fov_deg'],sc['near_m'])
    print('Select sparse one-sided skeleton',flush=True)
    d,selection_record=select_d(fixed,derivative,camera.azimuth_deg,c,a+b+high,context)
    pool=a+b+high+d+context;provenance={'study':c['study'],'config_sha256':sha256_file(config_path),
        'selection_sha256':sha256_file(root/c['selection']),'parent_vector_commit':c['parent_vector_commit'],
        'input_sha256':selection['input_sha256'],'seed':c['seed'],'preview_profiles':c['styles']}
    publish_vectors(out/'layer_pool.json.gz',pool,provenance);pool=read_vectors(out/'layer_pool.json.gz')['strokes']
    checks=validate(pool,fixed,c);combinations={};stats={}
    order={'01_A':['A','V'],'02_AC':['C','A','V'],'03_ABC':['C','A','B','V'],'04_ABCD':['C','A','B','V','D']}
    for name,layers in order.items():
        strokes=compose(pool,layers);combinations[name]=strokes;stats[name]=metrics(strokes,fixed['base'])
        for mode in ['black','density']:render(strokes,out/f'{name}_{mode}.png',mode)
        write_svg(strokes,out/f'{name}.svg')
        with Image.open(out/f'{name}_density.png') as im:
            image=np.asarray(im.convert('RGB'));h,w=image.shape[:2]
        buffer=io.BytesIO();Image.fromarray(np.concatenate([image[:,:w//2],np.full((h,80,3),225,np.uint8),image[:,w//2:]],axis=1)).save(buffer,format='PNG')
        publish_png(buffer.getvalue(),out/f'{name}_physical.png')
    final=combinations['04_ABCD'];publish_vectors(out/'final_strokes.json.gz',final,provenance)
    final=read_vectors(out/'final_strokes.json.gz')['strokes']
    assert stats['04_ABCD']['D_all_length_fraction']<=c['D']['maximum_terrain_length_fraction']
    assert stats['04_ABCD']['D_terrain_length_fraction']<=c['D']['maximum_terrain_length_fraction']
    for panel in [1,2]:write_svg(final,out/f'final_panel_{panel}.svg',panel)
    render(final,out/'final_hierarchy.png','hierarchy')
    for mode in ['black','density']:comparison({k.replace('_',' '):out/f'{k}_{mode}.png' for k in combinations},out/f'comparison_{mode}.png','Fixed F2 C | A body / B structure / C grain / D final skeleton')
    comparison({k.replace('_',' '):out/f'{k}_physical.png' for k in combinations},out/'physical_comparison.png','Same painting | 300 mm + 40 mm gap + 300 mm',extent=(0,640,900,0))
    render(compose(pool,['C','A','V'],c_low=True),out/'C_low.png','density')
    comparison({'Sparse C':out/'C_low.png','Dense C':out/'02_AC_density.png'},out/'C_density_comparison.png','C density only changes | same width, opacity, A and vegetation')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,label,strokes in [(axes[0],'Sparse C',compose(pool,['C','A','V'],c_low=True)),(axes[1],'Dense C',compose(pool,['C','A','V']))]:
        path=out/('C_'+label.split()[0].lower()+'_near_detail.png');render(strokes,path,'density',(60,650,360,850),(1200,800))
        ax.imshow(Image.open(path));ax.axis('off');ax.set_title(label+' | 0.16 mm, same preview opacity')
    fig.suptitle('Near-ground grain | only the number of actual C paths changes');fig.tight_layout();save_figure(fig,out/'C_density_near_detail.png')
    for name,layers in [('D_only',['D']),('B_only',['B']),('C_only',['C'])]:render(compose(pool,layers),out/f'{name}.png','black')
    fig,axes=plt.subplots(2,3,figsize=(12,7))
    for col,(role,bounds) in enumerate(c['detail_crops_mm'].items()):
        for row,key in enumerate(['03_ABC','04_ABCD']):
            path=out/f'{role}_{key}.png';render(combinations[key],path,'density',tuple(bounds),(800,500))
            axes[row,col].imshow(Image.open(path));axes[row,col].axis('off');axes[row,col].set_title(role+' | '+('before D' if row==0 else 'after D'))
    fig.suptitle('D cap / spine / foothold detail | identical underlying A/B/C');fig.tight_layout();save_figure(fig,out/'D_before_after_details.png')
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    layers=['C','A','B','D'];pos=np.arange(4);widths=[c['styles'][k]['width_mm'] for k in layers]
    axes[0].bar(layers,widths,color=[COLORS[k] for k in layers]);axes[0].set_title('Nominal width (mm)')
    axes[1].bar(layers,[stats['04_ABCD']['layers'][k]['length_mm']/1000 for k in layers],color=[COLORS[k] for k in layers]);axes[1].set_title('Actual vector length (m)')
    fig.suptitle('Strength and density are independent variables');fig.tight_layout();save_figure(fig,out/'hierarchy_diagnostics.png')
    endpoints=[]
    for s in a:
        p=np.array(s['xy_mm'])[[0,-1]]
        eligible=(sample(fixed['base']['depth_m'],p)>1600)&(sample(fixed['features']['ridge'],p)>.3)
        eligible&=(np.abs(p[:,0]-300)>1)&(p[:,0]>1)&(p[:,0]<599)
        endpoints.extend(p[eligible])
    cap={'eligible_upper_A_endpoints':len(endpoints),'D_distance_threshold_mm':4}
    if d and endpoints:
        distance=cKDTree(np.concatenate([resample(s['xy_mm'],.4) for s in d])).query(np.asarray(endpoints))[0]
        cap['endpoints_with_D_within_threshold']=int((distance<=4).sum())
        cap['interpretation']='Local anchoring opportunity, not proof that every endpoint belongs to a crest or should be capped.'
    else:cap['endpoints_with_D_within_threshold']=0
    record={'study':c['study'],'config':c,'provenance':provenance,'metrics':stats,'D_selection':selection_record,'checks':checks,
        'C_density':{'low_vectors':len(low),'dense_vectors':len(high),'low_length_mm':total_length(low),'dense_length_mm':total_length(high),'nested_subset':low_ids.issubset({s['id'] for s in high})},'D_endpoint_anchor_diagnostic':cap,
        'invariants':{'selected_C_grayscale_pixels_identical':True,'selected_C_retention_archive_identical':True,
            'all_source_vectors_unchanged':all(sha256_file(root/p)==h for p,h in c['source_vector_sha256'].items()),
            'source_inputs_unchanged':all(sha256_file(p)==selection['input_sha256'][k] for p,k in [(master,'master'),(veg,'vegetation')])},
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'matplotlib':matplotlib.__version__},
        'order':order,'limits':['D cliff/foothold candidates are DEM support proxies, not verified rock or geology edges.','Opacity is a preview profile; dimensionless intensity is not calibrated machine pressure.','Nominal width does not predict wet ink spread. No G-code or hardware calls.']}
    (out/'record.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');print(json.dumps({'metrics':stats['04_ABCD'],'D':selection_record,'checks':checks,'C_density':record['C_density']},indent=2),flush=True)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('master');p.add_argument('veg');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
