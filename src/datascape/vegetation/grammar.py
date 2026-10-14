"""Seeded botanical presence at fixed measured roots; no observed-tree claim."""
import numpy as np
from scipy.ndimage import distance_transform_edt
from datascape.strokes.vector import sample,resample,split_at_gate,finalize,phase
from datascape.vegetation.multidepth import object_retention


def bezier(a,b,c,d,count=13):
    t=np.linspace(0,1,count)[:,None]
    return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d


def tree_paths(mark,rng,config):
    """Asymmetric trunk/branch hierarchy with open, scattered foliage strokes."""
    root=np.array(mark['root_pixel_xy']);height=mark['height_mm'];hero=bool(mark.get('representative'))
    lean=rng.uniform(-.12,.12)*height;top=root+[lean,-height]
    trunk=bezier(root,root+[lean*.15,-height*.35],top+[-lean*.25,height*.3],top,25)
    paths=[(trunk,config['hero_trunk_width_mm'] if hero else config['trunk_width_mm'],'trunk')];tips=[]
    levels=np.sort(rng.uniform(.22,.86,8 if hero else 6));previous_side=-1
    for i,t in enumerate(levels):
        start=trunk[int(t*(len(trunk)-1))];side=1 if rng.random()>.45 else -1
        if i>0 and side==previous_side and rng.random()<.7:side=-side
        previous_side=side;length=height*rng.uniform(.18,.34)*(1-.45*t)
        end=start+[side*length,-length*rng.uniform(.45,.95)]
        branch=bezier(start,start+[side*length*.35,-length*.1],end+[-side*length*.2,length*.25],end,11)
        paths.append((branch,config['branch_width_mm']*(1-.35*t),'branch'));tips.append(end)
        for fraction in rng.uniform(.4,.82,2 if hero else 1):
            origin=branch[int(fraction*(len(branch)-1))];twig=end-origin
            target=origin+twig*rng.uniform(.55,.8)+[-side*length*.20,-length*.20]
            paths.append((bezier(origin,origin+twig*.2,target+[0,length*.1],target,7),config['twig_width_mm'],'twig'));tips.append(target)
    tips.append(top)
    # Crown presence comes from many short gestures, not stacked closed loops.
    count=config['hero_leaf_marks'] if hero else config['leaf_marks']
    for _ in range(count):
        tip=tips[int(rng.integers(len(tips)))];radius=height*(.045 if hero else .05)
        center=tip+rng.normal(size=2)*[radius,radius*.55]
        length=rng.uniform(.9,2.8)*(2.1 if hero else 1)
        tangent=np.array([rng.uniform(-1,1),rng.uniform(-.8,-.1)]);tangent/=max(np.linalg.norm(tangent),1e-9)
        a=center-tangent*length/2;d=center+tangent*length/2
        paths.append((bezier(a,a+tangent*length*.4+[0,-length*.25],d-tangent*length*.3,d,5),config['foliage_width_mm'],'foliage'))
    return paths


def cluster_paths(mark,rng,config):
    """Overlapping irregular masses; no individual near-tree icon at scale."""
    root=np.array(mark['root_pixel_xy']);height=mark['height_mm'];paths=[]
    vigor=np.clip((mark['ndvi']-.1)/.55,0,1)
    for _ in range(int(config['cluster_marks']*(.65+.35*vigor))):
        center=root+[rng.normal()*height*.9,-abs(rng.normal())*height*.5]
        length=rng.uniform(1.3,3.6);a=center+[-length*.5,length*.2];d=center+[length*.5,0]
        paths.append((bezier(a,center+[-length*.3,-length*.6],center+[length*.1,-length*.45],d,6),config['cluster_width_mm'],'cluster-grain'))
    return paths


def far_paths(mark,rng,config,ridge_support):
    if ridge_support<config['minimum_far_ridge_support']:return []
    root=np.array(mark['root_pixel_xy']);paths=[]
    for _ in range(1+int(ridge_support>.65)):
        a=root+rng.uniform(-1,1,2)*[1.4,.8];d=a+[rng.uniform(.25,1.1),-rng.uniform(.1,.5)]
        paths.append((np.array([a,d]),config['far_width_mm'],'ridge-touch'))
    return paths


def redesign(fixed,config):
    """Retain source roots/heights, consolidate old duplicated hero parents."""
    c=config['vegetation'];base=fixed['base'];r=fixed['refined'];result=[];roots=[]
    heroes=fixed['representatives'];replaced={m['parent_small_mark_id'] for m in heroes}
    marks=[m for m in fixed['small'] if m['id'] not in replaced]+heroes
    local=np.divide(fixed['retention'],r['global_retention'],out=np.zeros_like(fixed['retention']),where=r['global_retention']>0)
    for mark in marks:
        identity=mark['id'];rng=np.random.default_rng(np.random.SeedSequence([config['seed'],int(phase(identity,901)*2**31)]))
        role=mark['kind'];root=mark['root_pixel_xy']
        ridge=float(sample(np.maximum(fixed['features']['ridge'],fixed['features']['silhouette']),[root])[0])
        paths=tree_paths(mark,rng,c) if role=='near' else cluster_paths(mark,rng,c) if role=='middle' else far_paths(mark,rng,c,ridge)
        if not paths:continue
        probability=object_retention(base['depth_m'],base['occupied'],mark['forward_depth_m'],local,r['global_retention'],fixed['vegetation_config'])
        safe=distance_transform_edt(probability>1e-8)
        retained=0
        for index,(line,width,part) in enumerate(paths):
            p=resample(line,.4);rr=sample(probability,p)
            gate=np.minimum.reduce([rr-c['minimum_retention'],sample(safe,p,order=0)-width/2-1,
                p[:,0]-width/2,600-width/2-p[:,0],p[:,1]-width/2,898-width/2-.002-p[:,1]])
            for run in split_at_gate(p,gate,c['minimum_touch_mm']):
                records=finalize([run],f'V-{identity}-{index}-{retained}',width,{'layer':'V','preview_opacity':1,'vegetation_role':role,'grammar_part':part})
                for s in records:
                    xy=np.array(s['xy_mm']);rr=np.clip(sample(probability,xy),0,1)
                    taper=np.linspace(1,.2,len(xy)) if part=='trunk' else np.linspace(1,.35,len(xy)) if part in ['branch','twig'] else np.ones(len(xy))
                    s['width_profile_mm']=(width*taper*(.35+.65*rr**.4)).round(4).tolist()
                    s['opacity_profile']=(c['role_opacity'][role]*rr**.45).round(4).tolist()
                    s['expression']={'intensity':.5,'intensity_samples':(.5*rr).round(4).tolist(),'pressure_calibrated':False}
                    s.update(source_root_id=identity,source_root_xyz_m=mark['source_xyz_m'],source_root_xy_mm=root,
                        source_object_depth_m=mark['forward_depth_m'],source_height_mm=mark['height_mm'],hero=bool(mark.get('representative')))
                    result.append(s);retained+=1
        roots.append({'id':identity,'role':role,'root_xy_mm':root,'source_xyz_m':mark['source_xyz_m'],
            'height_mm':mark['height_mm'],'hero':bool(mark.get('representative')),'ndvi':mark['ndvi'],
            'effective_observations':mark['effective_observations'],'ridge_support':ridge,'vectors':retained})
    return result,{'displayed_root_sites':roots,'hero_small_glyphs_consolidated':sorted(replaced),
        'new_root_positions':0,'interpretation':'Seeded expression at archived data-supported roots; not an observed tree or species inventory.'}
