"""Reproducible seasonal display studies on the pinned eight-panel geometry."""
from model import *
from render import render
from audit import audit,recommendations
import argparse,shutil
from collections import defaultdict,Counter
from PIL import ImageDraw,ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def panel_length(row,lo,hi):
    p=np.asarray(row['xy_mm']);a=p[:-1];b=p[1:];dx=b[:,0]-a[:,0]
    t0=np.divide(lo-a[:,0],dx,out=np.zeros(len(dx)),where=abs(dx)>1e-12)
    t1=np.divide(hi-a[:,0],dx,out=np.ones(len(dx)),where=abs(dx)>1e-12)
    fraction=np.maximum(0,np.minimum(1,np.maximum(t0,t1))-np.maximum(0,np.minimum(t0,t1)))
    vertical=abs(dx)<=1e-12
    fraction[vertical]=((a[vertical,0]>=lo)&((a[vertical,0]<hi)|(hi==600))).astype(float)
    return float((fraction*np.linalg.norm(b-a,axis=1)).sum())

def case(season):
    c=read(CONFIG);scene=load_scene(season);sidecar=styles(scene,c);aux=guides(scene,c)
    out=OUT/season;out.mkdir(parents=True,exist_ok=True)
    gz(out/'style_intent.json.gz',sidecar);gz(out/'color_territory_guides.json.gz',dict(status=c['guide_policy']['status'],spring_geometry_modified=False,guides=aux))
    print(season,'color styles',len(sidecar['color']),'ink styles',len(sidecar['ink']),'auxiliary guide suggestions',len(aux),flush=True)
    for mode,name,pixels in [('baseline','baseline_control.png',(1200,1800)),('theme','theme.png',(1200,1800)),('quiet','ink_led.png',(1200,1800)),('color_only','color_only.png',(720,1080)),('ink_only','ink_tone.png',(720,1080))]:
        render(scene,sidecar,aux,c,out/name,mode,pixels=pixels)
        print(season,name,'ready',flush=True)
    substrates={'spring':'#F8F8F5','summer':'#E8E4D9','autumn':'#EDE4D2','winter':'#DDD9CF'}
    render(scene,sidecar,aux,c,out/'candidate_substrate.png','candidate_paper',pixels=(720,1080),background=substrates[season])
    pair=ORDER.index(season)*2
    with Image.open(out/'theme.png') as im:
        for local in [0,1]:png(OUT/f'P{pair+local+1}.png',im.crop((local*600,0,(local+1)*600,1800)))
    stats={}
    for local in [0,1]:
        n=pair+local+1;lo=local*300;hi=lo+300
        ink=defaultdict(float);colors=defaultdict(float);extra=defaultdict(float)
        for r,s in zip(scene['ink'],sidecar['ink']):ink[s['cohort']]+=panel_length(r,lo,hi)
        for r,s in zip(scene['color'],sidecar['color']):colors[s['role']]+=panel_length(r,lo,hi)
        for r in aux:extra[r['role']]+=panel_length(r,lo,hi)
        total=sum(ink.values())
        stats[f'P{n}']=dict(ink_length_mm=total,ink_cohort_length_shares={k:v/total for k,v in ink.items()},ink_cohort_target=c['panels'][n-1]['ink_mix_target'],
            source_color_length_by_role_mm=dict(colors),supplemental_guide_length_by_role_mm=dict(extra),physical_D4_assigned=False)
    save(out/'statistics.json',dict(panels=stats,geometry_signatures=sidecar['geometry_signatures'],source_files=sidecar['source_files'],
        depth_role_bases=dict(Counter(s['depth_basis'] for s in sidecar['ink']+sidecar['color'])),
        metric_scope='Path-length cohort shares and color-source lengths, not pigment quantities, coverage or calibrated light/dark dilution ratios'))
    if season=='spring':
        selected=[]
        for kind in ['ink','color']:
            for r,s in zip(scene[kind],sidecar[kind]):
                if panel_length(r,300,600)>0:selected.append(s)
        gz(out/'P2_style_handoff.json.gz',dict(panel='P2',continuous_x_offset_mm=300,source_files=scene['source_files'],styles=selected,
            geometry_included=False,execution_ready=False,physical_palette_map=None,pressure_profiles_modified=False,
            instruction='Reference the frozen Spring canonical IDs; exact panel clipping belongs to the established source-arc contract. No color dose, contact schedule or Z mapping is supplied.'))
        d4=[r for r in scene['color'] if r.get('palette_slot')=='D4' and np.mean(np.asarray(r['xy_mm'])[:,0])>=300 and np.mean(np.asarray(r['xy_mm'])[:,1])>520]
        centers=np.array([np.mean(r['xy_mm'],axis=0) for r in d4]);x,y=np.median(centers,axis=0)
        x0=float(np.clip(x-95,300,400));y0=float(np.clip(y-85,400,728));bounds=(x0,y0,x0+200,y0+170)
        for mode,name in [('baseline','D4_current.png'),('theme','D4_replaced.png'),('low_D4','D4_low_display.png')]:render(scene,sidecar,aux,c,out/name,mode,bounds=bounds,pixels=(1000,850))
        save(out/'D4_coupon.json',dict(bounds_continuous_mm=bounds,source_D4_paths=len(d4),low_display_multiplier=c['D4_policy']['comparison_display_multiplier'],not_a_physical_dilution=True))
    assert geometry_signature(scene['ink'])==sidecar['geometry_signatures']['ink']
    assert geometry_signature(scene['color'])==sidecar['geometry_signatures']['color']
    return out

def assemble(name,files,labels=None):
    canvas=Image.new('RGB',(5360,1880),'#E9E7E0');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype(FONT,25)
    for pair,path in enumerate(files):
        with Image.open(path) as im:
            if abs(im.width/im.height-2/3)>1e-3:raise ValueError('Wrong pair aspect ratio')
            im=im.convert('RGB').resize((1200,1800),Image.Resampling.LANCZOS)
            for local in [0,1]:
                i=pair*2+local;x=i*680;canvas.paste(im.crop((local*600,0,(local+1)*600,1800)),(x,65))
                draw.text((x+15,15),f'P{i+1} / {ORDER[pair].title()}',font=font,fill='#405A53')
    png(OUT/name,canvas)

def framework_graph(c):
    fig,axes=plt.subplots(5,1,figsize=(20,7.8),gridspec_kw=dict(height_ratios=[1,1,1,1,1.5]),sharex=True)
    x=np.linspace(0,2400,2400)
    for ax,key,label in zip(axes[:4],['base','structural','mineral','accent'],['Base / underlying','Structure / vegetation','Structure / mineral companion','Accent / protruding']):
        image=palette_at(c,x,key)[None,:,:];ax.imshow(np.repeat(image,35,axis=0),extent=[0,2400,0,1],aspect='auto');ax.set_yticks([]);ax.set_ylabel(label,rotation=0,ha='right',va='center',fontsize=10)
        for j in range(1,8):ax.axvline(j*300,c='#FFFFFF',lw=2)
    data=np.array([p['ink_mix_target'] for p in c['panels']]);bottom=np.zeros(8)
    for values,col,label in zip(data.T,['#B6BABC','#747A7D','#283034'],['light','middle','dark']):
        axes[4].bar(np.arange(8)*300+150,values,bottom=bottom,width=250,color=col,label=label);bottom+=values
    axes[4].set_ylim(0,1);axes[4].set_ylabel('Artistic cohort\ntarget',rotation=0,ha='right',va='center',fontsize=10);axes[4].legend(loc='upper center',ncol=3,fontsize=8)
    axes[-1].set_xticks(np.arange(8)*300+150,[p['id']+' / '+p['stage'] for p in c['panels']],rotation=14,ha='right',fontsize=8)
    fig.suptitle('One continuous seasonal role system / display colors and ink cohorts, not pigment recipes')
    fig.tight_layout();figure_png(fig,OUT/'framework_ribbon.png');plt.close(fig)
    boundaries=[]
    for j,t in enumerate(c['transitions'],1):
        position=j*300;colors={role:palette_at(c,position,role).tolist() for role in ['base','structural','mineral','accent']}
        errors={role:float(abs(palette_at(c,position-1e-7,role)-palette_at(c,position+1e-7,role)).max()) for role in colors}
        boundaries.append(dict(**t,painted_boundary_x_mm=position,role_display_RGB=colors,max_numeric_boundary_color_error=max(errors.values()),
            logic_scope='Continuous display-role function; actual painted territories may meet through paper or unequal source coverage. No geometric seam fitting.'))
    save(OUT/'transitions.json',dict(transitions=boundaries,physical_pigment_interpolation=False))
    return boundaries

def finalize():
    c=read(CONFIG);OUT.mkdir(parents=True,exist_ok=True)
    scenes=[load_scene(s) for s in ORDER];evidence=audit(scenes,c);proposals=recommendations()
    save(OUT/'framework.json',c);transitions=framework_graph(c)
    for name,source in [('P1_P8_theme.png','theme.png'),('P1_P8_baseline_control.png','baseline_control.png'),('P1_P8_ink_led.png','ink_led.png'),('P1_P8_ink_tone.png','ink_tone.png'),('P1_P8_color_only.png','color_only.png'),('P1_P8_candidate_substrate.png','candidate_substrate.png')]:assemble(name,[OUT/s/source for s in ORDER])
    canvas=Image.new('RGB',(5360,3880),'#E9E7E0');d=ImageDraw.Draw(canvas);font=ImageFont.truetype(FONT,32)
    for j,(name,title) in enumerate([('P1_P8_baseline_control.png','PR38 palettes / matched-renderer control'),('P1_P8_theme.png','Seasonal color / tone study v01 — same canonical geometry; supplemental color guides after Spring')]):
        d.text((20,j*1940+8),title,fill='#30483F',font=font)
        with Image.open(OUT/name) as im:canvas.paste(im,(0,j*1940+52))
    png(OUT/'P1_P8_before_after.png',canvas)
    coupon=Image.new('RGB',(3060,980),'#EEEDE6');d=ImageDraw.Draw(coupon)
    for j,(name,title) in enumerate([('D4_current.png','Existing D4 display'),('D4_replaced.png','Primary / pale mineral replacement'),('D4_low_display.png','D4 x0.18 display only / not dilution')]):
        d.text((j*1020+12,12),title,font=ImageFont.truetype(FONT,22),fill='#30483F')
        with Image.open(OUT/'spring'/name) as im:coupon.paste(im,(j*1020+10,60))
    d.text((16,930),'Same frozen P2 source crop. No approved geometry, pressure profile or physical station map is changed.',font=ImageFont.truetype(FONT,21),fill='#5F6057');png(OUT/'P2_D4_comparison.png',coupon)
    stats={}
    for s in ORDER:stats.update(read(OUT/s/'statistics.json')['panels'])
    save(OUT/'panel_intent_statistics.json',stats)
    from notes import write_notes,write_html
    write_notes(c,evidence,proposals,transitions);write_html(c)
    shutil.copyfile(ROOT/'docs/experiments/seasonal_composition_v03/P1_P8_full.png',OUT/'PR38_archived_reference.png')
    print('Complete eight-panel color/tone review ready',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=ORDER);p.add_argument('--finalize',action='store_true');a=p.parse_args()
    if a.scene:case(a.scene)
    elif a.finalize:finalize()
    else:
        for s in ORDER:case(s)
        finalize()
