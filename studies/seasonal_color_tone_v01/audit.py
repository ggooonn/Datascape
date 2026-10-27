"""Read-only evidence for repeated composition recipes and legacy D4 intent."""
from model import *
from collections import Counter,defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import ImageDraw,ImageFont

def row_alpha(r):return float(np.mean(r.get('opacity_profile',[r.get('preview_opacity',r.get('opacity',1.))])))

def audit(scenes,c):
    palette=read(ROOT/'artworks/spring_v13/palette.json')['slots'];record={}
    for scene in scenes:
        season=scene['season'];ink=scene['ink'];colors=scene['color'];owners={}
        for r in ink:
            if r.get('catalog_version')=='0.10':owners.setdefault(r.get('owner_id',r['id']),dict(form=r.get('catalog_form'),accent=r.get('accent')))
        rock=[r for r in ink if 'rock' in r.get('layer','')]
        regimes=defaultdict(lambda:dict(paths=0,length_mm=0.))
        for r in rock:
            name=r.get('structural_regime','unclassified');regimes[name]['paths']+=1;regimes[name]['length_mm']+=length(r)
        data=dict(ink_paths=len(ink),color_paths=len(colors),color_groups=dict(Counter(r.get('palette_slot',r.get('color_group','unassigned')) for r in colors)),
            native_tree_owners=len(owners),tree_forms=dict(Counter(r['form'] for r in owners.values())),tree_accents=dict(Counter(str(r['accent']) for r in owners.values())),rock_regimes=dict(regimes),
            canonical_geometry_signatures=dict(ink=geometry_signature(ink),color=geometry_signature(colors)),source_files=scene['source_files'])
        if season!='spring':
            cfg=scene['config'];data['near_group_centers_mm']=[dict(id=g['id'],xy_mm=g['center_mm']) for g in cfg['near_groups']]
            data['source_camera']=read(ROOT/SCENES[season]/'scene.json')
        record[season]=data
    spring=scenes[0];earth={}
    for panel,lo,hi in [('P1',0,300),('P2',300,600)]:
        earth[panel]={}
        for slot in ['D4','D5']:
            rows=[r for r in spring['color'] if r.get('palette_slot')==slot and lo<=np.mean(np.asarray(r['xy_mm'])[:,0])<hi]
            area=sum(length(r)*float(np.mean(r.get('width_profile_mm',[r['width_mm']])))*row_alpha(r) for r in rows)
            earth[panel][slot]=dict(paths_by_centroid=len(rows),centerline_length_mm=sum(map(length,rows)),width_length_alpha_proxy_mm2=area,recorded_name=palette[slot]['name'])
    record['legacy_earth_audit']=dict(panels=earth,D4_total_source_paths=sum(r.get('palette_slot')=='D4' for r in spring['color']),
        metric='Centroid attribution and length x mean width x mean display alpha; overlapping area, physical pigment strength and wet coverage are not measured',
        physical_observation='The artist reports D4 as too dominant. This digital audit does not recalibrate that physical observation.',
        summer_physical_slots_assigned=False)
    save(OUT/'baseline_audit.json',record)
    views=read(ROOT/'docs/experiments/seasonal_composition_v03/skyline.json')['terrain_silhouettes_mm'];ranges={}
    for j,season in enumerate(ORDER):
        for local in [0,1]:
            y=np.array(views[season][local*300:(local+1)*300]);ranges[f'P{j*2+local+1}']=dict(skyline_range_mm=float(np.ptp(y)),mean_abs_adjacent_height_change_mm=float(np.mean(np.abs(np.diff(y)))))
    save(OUT/'mountain_character_evidence.json',dict(panels=ranges,interpretation='Different silhouettes and cameras share one DEM window, depth-unfolding map and A/B/C/D language. Similar visual character is not proof of copied terrain geometry.'))
    fig,ax=plt.subplots(figsize=(8,7))
    colors=['#397567','#af7547','#748697']
    for season,col in zip(ORDER[1:],colors):
        camera=record[season]['source_camera'];eye=np.array(camera['primary_eye_xy_m']);target=np.array(camera['look_target_xy_m'])
        e=(eye-[315000,4162500])/1000;t=(target-[315000,4162500])/1000
        ax.scatter(*e,c=col,s=50);ax.annotate('',xy=t,xytext=e,arrowprops=dict(arrowstyle='->',color=col,lw=2));ax.text(e[0]+.15,e[1]+.18,season.title(),color=col)
    ax.set(xlim=(0,15),ylim=(0,13.2),aspect='equal',xlabel='East from common ROI origin (km)',ylabel='North from common ROI origin (km)',title='Existing seasonal source views / same ROI, different eyes and directions')
    ax.grid(alpha=.2);fig.tight_layout();figure_png(fig,OUT/'source_view_evidence.png');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,5),sharex=True,sharey=True)
    for ax,season,col in zip(axes,ORDER[1:],colors):
        groups=record[season]['near_group_centers_mm'];xy=np.array([g['xy_mm'] for g in groups]);ax.scatter(xy[:,0],xy[:,1],s=130,c=col)
        for p,g in zip(xy,groups):ax.text(p[0],p[1]-10,g['id'].replace(season,'').replace('v03-',''),fontsize=7,ha='center')
        ax.set(xlim=(0,600),ylim=(890,580),xlabel='Painted X (mm)',title=season.title()+' / current shared-support groups');ax.axvline(300,c='#ccc',ls='--');ax.grid(alpha=.18)
    axes[0].set_ylabel('Top-down painted Y (mm)');fig.suptitle('Recurring left / relay / right scaffold — different sizes and depth, still similar layout');fig.tight_layout();figure_png(fig,OUT/'foreground_scaffold_review.png');plt.close(fig)
    return record

def recommendations():
    proposals={
      'summer':dict(status='proposed, not applied',baseline_groups=['v03-left-promontory','v03-right-bank'],
        vegetation='Make B the continuous overhanging bank body and U a low connected underlayer; retain P as a counter-accent rather than repeating three upright groups.',
        existing_controls=['tree_final_scale.make_tree(form="B", architecture="terminal-droop") for one supported bank member','P/B/U posture, stem_ratio and vigor; keep U small/light'],
        rocks='Replace one upright jointed plinth with lower compact/rounded base_mass and partly buried layered bedrock; keep B-type supporting masses unequal.',
        library_entrypoints=['datascape.vegetation.tree_final_scale.make_tree','datascape.ground.structural_detail_v05.base_mass(form="compact", regime="rounded")'],
        ground='Use a low shared bank and connected color support, retaining the diagonal passage rather than a separate pedestal below every tree.'),
      'autumn':dict(status='proposed, not applied',baseline_groups=['autumn-saddle','autumn-right-mass'],
        vegetation='Break one B crown episode with dead-limb or damaged-crown; retain unequal P/B remnants and reduce the repeated center-relay silhouette.',
        existing_controls=['accent="dead-limb" or "damaged-crown" on selected P/B/U members','Unequal vigor and stem_ratio; no new botanical family'],
        rocks='Expose angular/layered ledges and fewer unequal blocks, rather than only enlarging the same jointed-parent/layered-front B recipe.',
        library_entrypoints=['datascape.vegetation.tree_final_scale.make_tree','datascape.ground.structural_detail_v05.base_mass(form="angular", regime="layered")'],
        ground='Use broken bedding/contact cues and an asymmetric terrace; separate dry exposed ground from retreating canopy color.'),
      'winter':dict(status='proposed, not applied',baseline_groups=['winter-left-shelter','winter-middle-remnant','winter-right-remnant'],
        vegetation='Keep one P shelter and an incomplete B skeleton, using broken-top or suppressed accents selectively; make the small P8 remnant subordinate to its long rest.',
        existing_controls=['accent="broken-top" or "suppressed" only on selected members','Retain pine foliage; do not make every tree uniformly bare'],
        rocks='Use one coherent A-style bedrock mass plus a few subordinate stones instead of three similar B plinth formations.',
        library_entrypoints=['datascape.vegetation.tree_final_scale.make_tree','datascape.ground.structural_detail_v05.base_mass(form="bedrock", regime="jointed")'],
        ground='Expose a broad structural plane and isolated contacts. Preserve P8 terrain, skyline and gentle ending.')}
    save(OUT/'foreground_identity_proposals.json',dict(proposals=proposals,W_status='Experimental only; no promotion to default and no W generation in this Work',geometry_changes_applied=False,library_policy='Use accepted anatomy and bounded scene arrangements; do not introduce a new botanical or rock engine'))
    return proposals
