"""Matched-renderer color studies; original centerlines/profiles stay read only."""
from model import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

def profile(row,key,fallback):
    a=np.asarray(row.get(key,[fallback]*len(row['xy_mm'])),float)
    return a if a.size==len(row['xy_mm']) else np.full(len(row['xy_mm']),float(a.mean()))

def virtual_rgb(style,scene,c,points):
    x=points[:,0]+ORDER.index(scene['season'])*600
    key='mineral' if style['material']=='mineral' and style['role']=='structural' else style['role']
    color=palette_at(c,x,key)
    if style['material']=='mineral' and style['role']=='accent':color=blend(color,palette_at(c,x,'mineral'),.45)
    if style['depth_role']=='far':color=blend(color,rgb(c['display']['common_far_neutral']),c['display']['far_chroma_neutralization'])
    return color

def render(scene,sidecar,aux,c,path,mode='theme',bounds=(0,0,600,900),pixels=(1200,1800),only_role=None,background='#FFFFFF'):
    x0,y0,x1,y1=bounds;pw,ph=pixels;dpi=150
    fig=plt.figure(figsize=(pw/dpi,ph/dpi),dpi=dpi,facecolor=background)
    ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(x0,x1),ylim=(y1,y0));ax.axis('off');ax.set_facecolor(background)
    source_palette=read(ROOT/'artworks/spring_v13/palette.json')['slots'] if scene['season']=='spring' else scene['config']['virtual_color_groups']
    quiet=c['display']['quiet_color_gain'] if mode=='quiet' else 1.
    ink_map={r['source_id']:r for r in sidecar['ink']};color_map={r['source_id']:r for r in sidecar['color']}
    def collection(items,kind):
        lines=[];widths=[];rgba=[]
        for row,style in items:
            p=np.asarray(row['xy_mm'],float)
            if p[:,0].max()<x0 or p[:,0].min()>x1 or p[:,1].max()<y0 or p[:,1].min()>y1:continue
            if kind=='guide':
                n=len(p);t=np.linspace(0,1,n);w=row['display_width_mm']*(.25+.75*np.sin(np.pi*t)**.65)
                alpha=np.full(n,row['display_alpha']*quiet);color=virtual_rgb(row,scene,c,p)
            else:
                w=profile(row,'width_profile_mm',row['width_mm'])
                alpha=profile(row,'opacity_profile',row.get('preview_opacity',row.get('opacity',1.)))
                if kind=='ink':
                    if mode=='baseline':color=np.zeros((len(p),3))
                    else:
                        x=p[:,0]+ORDER.index(scene['season'])*600
                        index={'light':0,'middle':1,'dark':2}[style['cohort']]
                        value=scalar_at(c,x,'ink_gray')[:,index]
                        color=np.stack([value*.97,value,value*1.01],axis=1)
                elif mode=='baseline':
                    slot=row.get('palette_slot',row.get('color_group'));color=np.broadcast_to(rgb(source_palette[slot]['preview_hex']),(len(p),3))
                else:
                    color=virtual_rgb(style,scene,c,p)
                    gain=style['display_gain']*quiet
                    alpha=np.clip(alpha*gain,0,c['display']['alpha_caps'][style['role']])
                    if style['depth_role']=='far':alpha*=.78
                    if mode=='low_D4' and row.get('palette_slot')=='D4':
                        color=np.broadcast_to(rgb(source_palette['D4']['preview_hex']),(len(p),3));alpha=profile(row,'opacity_profile',row.get('preview_opacity',1.))*c['D4_policy']['comparison_display_multiplier']
            lines.extend(np.stack([p[:-1],p[1:]],axis=1));widths.extend((w[:-1]+w[1:])/2)
            cm=(color[:-1]+color[1:])/2;am=np.clip((alpha[:-1]+alpha[1:])/2,0,1)
            rgba.extend(np.column_stack([cm,am]))
        if lines:ax.add_collection(LineCollection(lines,linewidths=np.asarray(widths)*pw/(x1-x0)*72/dpi,colors=rgba,capstyle='round',joinstyle='round'))
    if mode!='ink_only':
        for role in ['base','structural']:
            if only_role and only_role!=role:continue
            if mode!='baseline':collection([(r,r) for r in aux if r['role']==role],'guide')
            collection([(r,color_map[r['id']]) for r in scene['color'] if color_map[r['id']]['role']==role],'color')
    if only_role is None and mode!='color_only':collection([(r,ink_map[r['id']]) for r in scene['ink']],'ink')
    if mode!='ink_only' and (only_role is None or only_role=='accent'):
        collection([(r,color_map[r['id']]) for r in scene['color'] if color_map[r['id']]['role']=='accent'],'color')
    buf=io.BytesIO();fig.savefig(buf,format='png',dpi=dpi,facecolor=background);plt.close(fig)
    with Image.open(io.BytesIO(buf.getvalue())) as im:im.load();png(path,im)
