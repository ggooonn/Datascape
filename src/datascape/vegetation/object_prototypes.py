"""Independent centerline object experiments after a pinned Shan Shui audit.

No upstream JavaScript is copied or translated. Tree/rock placement remains
Datascape terrain data; procedural silhouettes are not geographic observations.
"""
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.ndimage import distance_transform_edt
from datascape.strokes.vector import resample,sample,split_at_gate,finalize,phase
from datascape.strokes.color_ready import arc,profile_vertices
from datascape.vegetation.multidepth import object_retention


def bend_line(knots,step=.7):
    knots=np.asarray(knots);t=arc(knots)
    if len(knots)<4:return resample(knots,step)
    return CubicSpline(t,knots,axis=0,bc_type='natural')(np.linspace(0,t[-1],max(3,int(t[-1]/step)+1)))


def tree_centerlines(mark,seed,config):
    """Irregular trunk, nonuniform hierarchical branches and attached sprays."""
    rng=np.random.default_rng(np.random.SeedSequence([seed,int(phase(mark['id'],81)*2**31)]))
    root=np.asarray(mark['root_pixel_xy']);height=mark['height_mm'];trunk_width=config['trunk_width_mm'];result=[]
    y=np.linspace(0,1,7);bend=rng.normal(0,.035,7);bend[0]=0;bend=np.cumsum(bend)*height
    knots=root+np.column_stack([bend,-y*height]);trunk=bend_line(knots);result.append((trunk,trunk_width,'trunk'))
    tips=[];levels=np.sort(rng.uniform(.22,.88,rng.integers(6,9)));last_side=1
    for i,level in enumerate(levels):
        origin=trunk[min(int(level*(len(trunk)-1)),len(trunk)-1)]
        side=-last_side if rng.random()<.75 else last_side;last_side=side
        length=height*rng.uniform(.16,.30)*(1-.35*level);rise=length*rng.uniform(.35,.85)
        points=[origin,origin+[side*length*.32,-rise*.1],origin+[side*length*.72,-rise*.6],origin+[side*length,-rise]]
        branch=bend_line(points);result.append((branch,config['branch_width_mm']*(1-.35*level),'branch'));tips.append(branch[-1])
        for k,fraction in enumerate(rng.uniform(.45,.88,rng.integers(2,4))):
            anchor=branch[int(fraction*(len(branch)-1))];reach=length*rng.uniform(.16,.35)
            tip=anchor+[side*reach*rng.uniform(-.35,.9),-reach*rng.uniform(.8,1.5)]
            twig=bend_line([anchor,anchor+[side*reach*.2,-reach*.4],tip+[0,reach*.2],tip]);result.append((twig,config['twig_width_mm'],'twig'));tips.append(tip)
    tips.append(trunk[-1])
    vigor=np.clip((mark['ndvi']-.1)/.55,0,1);leaf_count=int(config['foliage_marks']*(.65+.35*vigor)*config['spring_foliage_fraction'])
    # Each spray is attached to a branch tip; its short curves remain centerlines.
    for tip in tips:
        size=height*rng.uniform(.025,.055)
        direction=rng.uniform(-.45,.45)
        stem=tip+np.array([np.sin(direction),-np.cos(direction)])*size
        result.append((bend_line([tip,tip+[0,-size*.3],stem+[size*.15,size*.2],stem]),config['twig_width_mm'],'spray-stem'))
        for j in range(max(2,leaf_count//len(tips))):
            t=rng.uniform(.15,1);center=tip+(stem-tip)*t
            side=rng.choice([-1,1]);length=rng.uniform(1.5,4.5)
            end=center+[side*length,-length*rng.uniform(.2,.9)]
            result.append((bend_line([center,center+[side*length*.3,-length*.25],end+[0,length*.2],end]),config['leaf_width_mm'],'foliage-touch'))
    top=min(float(p[:,1].min()) for p,_,_ in result);factor=height/max(root[1]-top,1e-9)
    for p,_,_ in result:p[:,1]=root[1]+(p[:,1]-root[1])*factor
    return result


def rock_centerlines(anchor,seed,config):
    """Open upper facets and internal grain; never a filled rock polygon."""
    rng=np.random.default_rng(seed);root=np.asarray(anchor['xy_mm']);width,height=anchor['width_mm'],anchor['height_mm']
    tilt=np.clip(anchor['orientation_xy'][1],-.7,.7)*height*.15
    upper=root+np.array([[-.5*width,-height*.12],[-.3*width,-height*.8],[.08*width,-height],[.43*width,-height*.48]])
    upper[:,1]+=np.linspace(-tilt,tilt,len(upper));upper+=rng.normal(size=upper.shape)*[width*.025,height*.04]
    lines=[(bend_line(upper),config['rock_edge_width_mm'],'upper-facet')]
    for a,b in [(upper[1],root+[-width*.1,-height*.15]),(upper[2],root+[width*.3,-height*.1])]:
        lines.append((bend_line([a,a+(b-a)*.33+[width*.02,0],a+(b-a)*.75,b]),config['rock_structure_width_mm'],'facet-break'))
    for _ in range(config['rock_texture_marks']):
        a=root+[rng.uniform(-.25,.25)*width,-rng.uniform(.25,.65)*height];b=a+[rng.uniform(.03,.12)*width,rng.uniform(.15,.3)*height]
        lines.append((resample([a,b],.6),config['rock_grain_width_mm'],'texture'))
    return lines


def clip_object(paths,probability,fixed,identity,source,config):
    result=[];safe=distance_transform_edt(probability>1e-8)
    for i,(p,width,part) in enumerate(paths):
        p=resample(p,.4);gate=np.minimum.reduce([sample(probability,p)-.025,sample(safe,p,order=0)-width/2-1.4,
            p[:,0]-width/2,600-width/2-p[:,0],p[:,1]-width/2,898-width/2-.002-p[:,1]])
        for j,run in enumerate(split_at_gate(p,gate,.5)):
            for s in finalize([run],f'prototype-{identity}-{i}-{j}',width,{'layer':'V','preview_opacity':1,'grammar_part':part}):
                p=profile_vertices(s);r=np.clip(sample(probability,p),0,1);t=arc(p)/max(arc(p)[-1],1e-9)
                taper=(1-.8*t) if part in ['trunk','branch','twig','spray-stem'] else np.ones(len(p))
                s['width_profile_mm']=(width*taper*(.4+.6*r**.3)).round(4).tolist();s['opacity_profile']=(.85*r**.35).round(4).tolist()
                s['expression']={'intensity':.5,'pressure_calibrated':False,'intensity_samples':(.5*r*taper).round(4).tolist()}
                s.update(source_root_id=identity,object_source=source,vegetation_role='near',**source);result.append(s)
    return result


def generate(fixed,current_vegetation,derivative,config,projection=None):
    """Replace only three hero glyphs; introduce three explicitly procedural rocks."""
    c=config['objects'];r=fixed['refined'];base=fixed['base'];heroes=fixed['representatives'];ids={m['id'] for m in heroes}
    kept=[s for s in current_vegetation if s.get('source_root_id') not in ids];trees=[];record=[]
    local=np.divide(fixed['retention'],r['global_retention'],out=np.zeros_like(fixed['retention']),where=r['global_retention']>0)
    for mark in heroes:
        probability=object_retention(base['depth_m'],base['occupied'],mark['forward_depth_m'],local,r['global_retention'],fixed['vegetation_config'])
        source={'source_root_xy_mm':mark['root_pixel_xy'],'source_root_xyz_m':mark['source_xyz_m'],'source_height_mm':mark['height_mm'],'hero':True,'procedural_object':'tree'}
        strokes=clip_object(tree_centerlines(mark,config['seed'],c),probability,fixed,mark['id'],source,c);trees+=strokes
        record.append({'id':mark['id'],**source,'vectors':len(strokes)})
    near=fixed['old']['depth_roles']['near'];score=near*fixed['features']['mound']*fixed['retention']*(.5+.5*r['positive_forms'])
    candidate=(score>.25)&base['occupied']&(base['slope_deg']<35)&(base['slope_deg']>2)
    ys,xs=np.where(candidate);order=np.argsort(-score[ys,xs],kind='stable');anchors=[];rocks=[]
    for k in order:
        point=np.array([xs[k]+.5,ys[k]+.5])
        if point[1]>850 or point[1]<640 or point[0]<30 or point[0]>570:continue
        if any(np.linalg.norm(point-np.array(a['xy_mm']))<c['rock_spacing_mm'] for a in anchors):continue
        yy,xx=ys[k],xs[k];gx,gy=derivative['gx'][yy,xx],derivative['gy'][yy,xx]
        orientation=np.array([gx,-gy])
        if projection is not None:
            xyz=base['xyz'][yy,xx];tangent=np.array([gx,gy,gx*gx+gy*gy]);a,_=projection.project(xyz[None,:],600,900);b,_=projection.project((xyz+5*tangent)[None,:],600,900);orientation=(b-a)[0]
        orientation/=max(np.linalg.norm(orientation),1e-9)
        rng=np.random.default_rng(config['seed']+len(anchors)+201)
        a={'xy_mm':point.tolist(),'source_xyz_m':base['xyz'][yy,xx].tolist(),'slope_deg':float(base['slope_deg'][yy,xx]),'orientation_xy':orientation.tolist(),
           'width_mm':float(rng.uniform(*c['rock_width_range_mm'])),'height_mm':float(rng.uniform(*c['rock_height_range_mm'])),'geographic_claim':'Procedural object at a DEM-supported anchor; not a mapped boulder.'}
        paths=rock_centerlines(a,config['seed']+len(anchors)+301,c);source={'source_root_xy_mm':a['xy_mm'],'source_root_xyz_m':a['source_xyz_m'],'procedural_object':'rock','hero':False}
        rocks+=clip_object(paths,fixed['retention'],fixed,f'rock-{len(anchors)}',source,c);anchors.append(a)
        if len(anchors)>=c['maximum_rocks']:break
    return kept+trees,rocks,{'hero_tree_prototypes':record,'rock_anchors':anchors,'placement':'Original roots/heights for trees; DEM-supported procedural rock anchors, not mapped rocks','upstream_code_ported':False}
