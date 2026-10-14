"""Different near/cluster/far marks with constant-root-depth compositing."""
import hashlib
import numpy as np
from PIL import Image,ImageDraw
from datascape.projection.composition import smoothstep


def vegetation_fields(base,ndvi,counts,reserves,config):
    """Measured evidence plus depth roles and declared composition weights."""
    occ=base['occupied'];h,w=occ.shape;yy,xx=np.mgrid[:h,:w];u=(xx+.5)/w
    current=ndvi[config['season']];n=counts[config['season']]
    a,b=config['observations_min_full'];lo,hi=config['ndvi_range']
    evidence=occ&np.isfinite(current)&np.isfinite(n)&(n>=a)&np.isfinite(base['slope_deg'])
    vigor=smoothstep((np.nan_to_num(current,nan=-1)-lo)/(hi-lo))
    confidence=smoothstep((np.nan_to_num(n,nan=0)-a)/(b-a))
    valid_season=np.isfinite(ndvi['SUMMER'])&np.isfinite(ndvi['WINTER'])&(counts['SUMMER']>=a)&(counts['WINTER']>=a)
    season=np.full((h,w),.9)
    relative=np.clip((current-ndvi['WINTER'])/np.maximum(ndvi['SUMMER']-ndvi['WINTER'],.08),0,1)
    season[valid_season]=.8+.2*np.nan_to_num(relative[valid_season],nan=.5)
    slope=base['slope_deg'];z=np.nan_to_num(base['xyz'][:,:,2],nan=0)
    gentle=.3+.7*(1-smoothstep((np.nan_to_num(slope,nan=90)-5)/25))
    elevation=.65+.35*(1-smoothstep((z-120)/430))
    aspect=.9+.1*np.cos(np.deg2rad(np.nan_to_num(base['aspect_deg'],nan=config['aspect_preference_deg'])-config['aspect_preference_deg']))
    aspect[np.nan_to_num(slope,nan=0)<=1]=1
    balance=config['center_density_floor']+(1-config['center_density_floor'])*smoothstep(np.abs(u-.5)/.42)
    geographic=vigor*confidence*season*gentle*elevation*aspect*evidence
    f=reserves['features'];role=reserves['depth_roles'];classification=np.argmax(np.stack(list(role.values())),axis=0)
    fields={};after={}
    for i,name in enumerate(['near','middle','far']):
        expression=(.55+.45*balance) if name=='near' else (.65+.35*balance)
        if name=='far':expression*=.3+.7*np.maximum(f['ridge'],f['silhouette'])
        value=geographic*role[name]*expression*(classification==i)
        fields[name]=value
        after[name]=value*reserves['terrain_retention']
    return {'before':fields,'after':after,'evidence_valid':evidence}


def glyph(root,kind,height,rng):
    """Three distinct symbolic grammars, not scaled copies of one tree."""
    x,y=root;lines=[]
    if kind=='near':
        lean=float(rng.uniform(-.12,.12))*height
        lines.append([[x,y],[x-.2*lean,y-.45*height],[x+lean,y-height]])
        for t in [.30,.47,.65,.82]:
            ox=x+lean*t;oy=y-height*t;span=height*(1-t)*float(rng.uniform(.28,.48))
            for side in [-1,1]:lines.append([[ox,oy],[ox+side*span*.5,oy-span*.25],[ox+side*span,oy-span*.45]])
        for t,r in [(0.61,.22),(0.79,.18),(0.95,.12)]:
            angle=np.linspace(.10*np.pi,1.90*np.pi,17)
            jitter=rng.uniform(.80,1.1,len(angle));radius=height*r
            lines.append(np.column_stack([x+lean*t+radius*np.cos(angle)*jitter,y-height*t+radius*.7*np.sin(angle)*jitter]).tolist())
    elif kind=='middle':
        # Shared clump silhouette and repeated short marks, without long trunks.
        for offset in [-1.0,-.35,.4,1.05]:
            cx=x+offset*height*.7;cy=y-float(rng.uniform(.05,.35))*height
            angle=np.linspace(0,np.pi,9)
            lines.append(np.column_stack([cx+height*.48*np.cos(angle),cy-height*.65*np.sin(angle)]).tolist())
            for dx in [-.25,0,.25]:lines.append([[cx+dx*height,cy],[cx+(dx+.12)*height,cy-height*.3]])
    else:
        # Sparse leaf dots/short ridge dashes; no miniature branching tree.
        for _ in range(int(rng.integers(3,7))):
            px=x+float(rng.uniform(-2,2))*height;py=y-float(rng.uniform(0,2))*height
            lines.append([[px,py],[px+float(rng.uniform(.3,1))*height,py-float(rng.uniform(.1,.6))*height]])
    return lines


def place_marks(base,vegetation,reserves,config,seed):
    occ=base['occupied'];h,w=occ.shape;marks=[]
    for index,kind in enumerate(['near','middle','far']):
        field=vegetation['before'][kind]*reserves['terrain_retention']
        ids=np.flatnonzero(field>=config['minimum_field'])
        if not len(ids):continue
        probability=field.ravel()[ids];probability/=probability.sum()
        rng=np.random.default_rng(np.random.SeedSequence([seed,501,index]))
        drawing_rng=np.random.default_rng(np.random.SeedSequence([seed,502,index]))
        pc=config['roles'][kind];roots=[];spacing=pc['spacing_mm']*w/600
        for flat in rng.choice(ids,size=config['maximum_proposals'],p=probability):
            row,col=divmod(int(flat),w);root=np.array([col+.5,row+.5])
            if any(np.linalg.norm(root-old)<spacing for old in roots):continue
            xyz=base['xyz'][row,col];q=float(base['depth_m'][row,col]);height=float(drawing_rng.uniform(*pc['height_mm']))
            identity=hashlib.sha256(f'{seed}:{kind}:{xyz[0]:.3f}:{xyz[1]:.3f}'.encode()).hexdigest()[:16]
            marks.append({'id':identity,'kind':kind,'root_pixel_xy':root.tolist(),'source_xyz_m':xyz.tolist(),
                'forward_depth_m':q,'ndvi':float(base['current_ndvi'][row,col]),'effective_observations':float(base['current_observations'][row,col]),
                'slope_deg':float(base['slope_deg'][row,col]),'field_before':float(vegetation['before'][kind][row,col]),
                'root_retention':float(reserves['terrain_retention'][row,col]),'height_mm':height,
                'polylines_pixel_xy':glyph(root,kind,height*h/900,drawing_rng)})
            roots.append(root)
            if len(roots)>=pc['count']:break
    return marks


def object_retention(background_q,occupied,object_q,local_retention,global_retention,config):
    """Foreground marks may cross a reserve belonging to deeper terrain.

    A mark is a screen glyph at its root's forward distance, not a reconstructed
    tree volume. Terrain substantially nearer than that root occludes it.
    Global layout reserves apply regardless of object/source depth.
    """
    delta=background_q-object_q
    match=np.exp(-.5*(delta/config['omission_match_sigma_m'])**2)*occupied
    visibility=(~occupied)|(background_q>=object_q-config['foreground_depth_tolerance_m'])
    return global_retention*(1-match*(1-local_retention))*visibility


def render_marks(marks,base,reserves,config):
    """Composite per-root depth, never apply a background mask blindly."""
    h,w=base['occupied'].shape;ink=np.zeros((h,w));by_kind={k:np.zeros_like(ink) for k in ['near','middle','far']}
    crossing=0;occluded=0;examples=[]
    for mark in sorted(marks,key=lambda x:x['forward_depth_m'],reverse=True):
        points=np.concatenate([np.asarray(p) for p in mark['polylines_pixel_xy']]);pad=3
        x0=max(0,int(np.floor(points[:,0].min()))-pad);x1=min(w,int(np.ceil(points[:,0].max()))+pad)
        y0=max(0,int(np.floor(points[:,1].min()))-pad);y1=min(h,int(np.ceil(points[:,1].max()))+pad)
        if x1<=x0 or y1<=y0:continue
        canvas=Image.new('L',(x1-x0,y1-y0),0);draw=ImageDraw.Draw(canvas)
        for line in mark['polylines_pixel_xy']:
            draw.line([(p[0]-x0,p[1]-y0) for p in line],fill={'near':225,'middle':185,'far':155}[mark['kind']],width=max(1,round(config['line_width_mm']*w/600)))
        coverage=np.asarray(canvas,dtype=float)/255;window=np.s_[y0:y1,x0:x1]
        local=reserves['local_core_retention'][window];global_r=reserves['global_retention'][window]
        background=base['depth_m'][window];occupied=base['occupied'][window]
        retention=object_retention(background,occupied,mark['forward_depth_m'],local,global_r,config)
        effective=coverage*retention
        crossed=int(((coverage>0)&(background>mark['forward_depth_m']+2*config['omission_match_sigma_m'])&(local<.7)&(effective>.05)).sum())
        crossing+=crossed
        if crossed:examples.append({'id':mark['id'],'kind':mark['kind'],'root_forward_depth_m':mark['forward_depth_m'],
            'surviving_mark_pixels':crossed,'bounds_pixel_xy':[x0,y0,x1,y1]})
        occluded+=int(((coverage>0)&occupied&(background<mark['forward_depth_m']-config['foreground_depth_tolerance_m'])).sum())
        ink[window]=1-(1-ink[window])*(1-effective)
        layer=by_kind[mark['kind']];layer[window]=1-(1-layer[window])*(1-effective)
    examples=sorted(examples,key=lambda x:x['surviving_mark_pixels'],reverse=True)[:3]
    return ink,by_kind,{'foreground_mark_pixels_surviving_deeper_omission':crossing,'mark_pixels_occluded_by_nearer_terrain':occluded,
        'foreground_crossing_examples':examples}
