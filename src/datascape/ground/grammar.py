"""Mass-led directional paths in output mm, independent of scene extraction.

Only low-dimensional anchors vary by seed. A plane's repeated paths share its
rulings, bend and local spacing schedule. Support polygons never plot.
"""
from dataclasses import dataclass, field
import hashlib
import numpy as np
from scipy.interpolate import PchipInterpolator
from shapely.geometry import LineString, Polygon
from datascape.strokes.vector import resample

VERSION = 'rock-ground-candidate-0.1'


def rng_for(seed, key):
    digest = hashlib.sha256(f'{seed}/{key}'.encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], 'big'))


def path_record(key, points, owner, part, width=.55, depth=None, layer='rock-ink'):
    p = np.asarray(points, float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 2 or not np.isfinite(p).all():
        raise ValueError('finite Nx2 path required')
    length = float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
    return dict(id=key, source_stroke_id=key, source_arc_mm=[0., length],
                xy_mm=p.tolist(), owner_id=owner, grammar_part=part, layer=layer,
                width_mm=width, forward_depth=depth, depth_provider='synthetic-local-rank-v1',
                depth_units='ordinal fixture rank; larger is farther',
                geographic_depth_m=None, geometry_revision=VERSION,
                footprint_status='assumed constant width, not measured', synthetic=True)


@dataclass
class Surface:
    identity: str
    support: object
    paths: list
    planes: list = field(default_factory=list)
    opaque: bool = False
    depth: float | None = None
    info: dict = field(default_factory=dict)


def _curve(knots, smooth, step=.6):
    p = np.asarray(knots, float)
    if not smooth: return resample(p, step)
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, arc[-1], max(8, int(arc[-1]/step)+1))
    return PchipInterpolator(arc, p, axis=0)(t)


def _ruling(face, u, t, bow):
    a,b,c,d = np.asarray(face)
    top = a*(1-u) + b*u
    bottom = d*(1-u) + c*u
    p = top[None,:]*(1-t[:,None]) + bottom[None,:]*t[:,None]
    tangent = bottom-top; n = np.array([-tangent[1], tangent[0]])
    n /= max(np.linalg.norm(n), 1e-9)
    p += n[None,:] * (bow*np.sin(np.pi*t)*np.sin(np.pi*u))[:,None]
    return p


def rock(identity='rock-0', anchor=(60,85), width=65, height=38,
         form='compact', seed=20261017, depth=2., detail='foreground',
         burial=.08, lean=0., texture=True, surface_profile=None, surface_source_id=None):
    """Two related mass scaffolds, three coherent ruled faces, broken contour.

    width/height are scaffold dimensions before optional lean; no vertex noise.
    Middle-ground changes path budgets, gaps and fracture count before drawing.
    """
    if form not in ('compact','angular','bedrock') or detail not in ('foreground','middle'):
        raise ValueError('unknown form or detail')
    if not np.isfinite([width,height,burial,lean]).all() or min(width,height)<12 or not 0<=burial<=.4 or abs(lean)>.35:
        raise ValueError('invalid dimensions, burial or lean')
    rng = rng_for(seed, identity+'/anchors')
    if form == 'compact':
        shape=np.array([[-.49,-.08],[-.43,-.48],[-.23,-.88],[.08,-1.], [.34,-.78],[.49,-.30],[.44,.00],[-.36,.04]])
    else:
        shape=np.array([[-.46,0],[-.40,-.57],[-.28,-.91],[.04,-1.], [.34,-.85],[.47,-.33],[.36,.02],[-.33,.05]])
    # Four shared anchor offsets, smoothly bounded by silhouette construction.
    shape[2:6] += rng.uniform(-.035,.035,(4,2))
    shape[:,1] += burial
    shape[:,0] += -shape[:,1]*lean
    shape *= [width,height]; shape += anchor
    if form=='bedrock':
        if surface_profile is None:
            xx=np.linspace(anchor[0]-width,anchor[0]+width,80)
            surface_profile=np.c_[xx,anchor[1]-height*.13*np.sin((xx-anchor[0])/width*np.pi)]
            surface_source_id='declared-synthetic-slope'
        host=np.asarray(surface_profile,float)
        if host.ndim!=2 or host.shape[1]!=2 or not np.all(np.diff(host[:,0])>0):
            raise ValueError('host surface must be monotone in screen x')
        support_y=PchipInterpolator(host[:,0],host[:,1],extrapolate=True)
        shape[:,1]+=support_y(shape[:,0])-anchor[1]
    contour=_curve(np.vstack([shape,shape[0]]),form=='compact')
    support=Polygon(contour).buffer(0)
    top0,top1=shape[2],shape[3]
    ridge0=top0*.70+top1*.30
    ridge1=shape[7]*.48+shape[6]*.52 + [width*.04,-height*.24]
    faces=[np.array([shape[1],ridge0,ridge1,shape[7]]),
           np.array([ridge0,shape[4],shape[5],ridge1]),
           np.array([ridge1,shape[5],shape[6],shape[7]])]
    paths=[]
    def add(key,xy,part,width_mm=.55):
        # Clip interior construction to semantic support; no fill is emitted.
        from datascape.vegetation.tree_occlusion_proof import line_parts
        geometry=LineString(xy) if part=='contour' else LineString(xy).intersection(support)
        for j,g in enumerate(line_parts(geometry)):
            if part=='grain' and any(other['id'].startswith(f'{identity}/{key.split(chr(47))[0]}/') and
                other['grammar_part']=='grain' and g.distance(LineString(other['xy_mm']))<.8
                for other in paths): continue
            if g.length>=2.8:
                paths.append(path_record(f'{identity}/{key}/{j}',g.coords,identity,part,width_mm,depth))
    # Deliberate gaps at crown shoulder and buried base, not a dark closed loop.
    ring=LineString(contour)
    from shapely.ops import substring
    contour_runs=[(.02,.23),(.29,.46),(.52,.68),(.80,.88)] if form!='bedrock' else [(.03,.20),(.29,.40),(.48,.55)]
    for i,(a,b) in enumerate(contour_runs):
        add(f'contour-{i}',substring(ring,a,b,normalized=True).coords,'contour',.65)
    add('ridge',_curve([ridge0,ridge0*.43+ridge1*.57+[width*.025,0],ridge1],form=='compact'),'structure',.6)
    if detail=='foreground':
        add('cross-break',_curve([shape[1]*.25+ridge0*.75,ridge0*.35+ridge1*.65,shape[5]*.7+ridge1*.3],False),'fracture',.5)
    if texture:
        for f,face in enumerate(faces):
            # Concentrate ruled paths at selected plane shoulders, leave a broad
            # open center. This is a spacing schedule, not a random hatch fill.
            count=max(3,round(width/3.8)) if detail=='foreground' else max(2,round(width/9))
            if f==2: count=4 if detail=='foreground' else 2
            q=(np.arange(count)+.5)/count
            us=np.where(q<.55,.08+.30*(q/.55)**1.4,.62+.32*(np.maximum(q-.55,0)/.45)**.8)
            for i,u in enumerate(us):
                if f==2 and i%2: continue
                phase=.5+.5*np.sin(i*1.7+f*1.2)
                t0=.10+.12*phase
                t1=(.77+.12*np.sin(i*.9+f)) if detail=='foreground' else .73
                if f==2: t0=.18; t1=.67
                t=np.linspace(t0,t1,32)
                xy=_ruling(face,float(u),t,width*(.035 if form=='compact' else .008))
                add(f'plane-{f}/run-{i}',xy,'grain',.5)
    for p in paths:
        p.update(generator_seed=seed,catalog_version=VERSION,object_form=form,
                 semantic_opaque=form!='bedrock',surface_source_id=surface_source_id,
                 placement_uncertainty='synthetic fixture; geographic correspondence unknown')
    return Surface(identity,support,paths,faces,form!='bedrock',depth,
                   dict(version=VERSION,form=form,seed=seed,width_mm=width,height_mm=height,
                        detail=detail,burial=burial,lean=lean,
                        evidence='pictorial synthetic mass; not observed geology',
                        silhouette='nonplotting body boundary',texture='shared ruled planes',
                        surface_source_id=surface_source_id,
                        surface_relation='host-profile warped exposure' if form=='bedrock' else 'independent mass',
                        assumed_same_plane_grain_centerline_gap_mm=.8))


def soil(identity='soil-0', origin=(10,45), width=100, height=35, seed=20261017,
         slope=-.10, mound=.5, detail='foreground', depth=3.):
    """Surface-following sweeps; bundles follow a shared mound and oblique flow.

    No opaque body and no stippling. Short tails dissolve by path-length/budget
    changes; digital opacity and width fading are deliberately absent.
    """
    if min(width,height)<=0 or detail not in ('foreground','middle') or not 0<=mound<=1:
        raise ValueError('invalid soil geometry')
    paths=[]; x0,y0=origin
    n=17 if detail=='foreground' else 8
    rng=rng_for(seed,identity+'/surface'); phase=float(rng.uniform(-.18,.18))
    for i in range(n):
        # A smaller spacing near the shoulder, opening toward lower ground.
        v=(i/(n-1))**1.42
        for side,(a,b) in enumerate([(0.02,.48),(.59,.99)]):
            # Dissolve outer/low rows by coherent shortened runs.
            a+=.07*v + .016*np.sin(i*.85+side)
            b-=.13*v + .03*np.sin(i*.7+side)
            u=np.linspace(a,b,52)
            xx=x0+width*u
            yy=y0+height*v+slope*width*u-mound*height*.55*np.sin(np.pi*u)**2
            xx+=height*v*.16
            yy+=height*.018*np.sin(2*np.pi*u+phase)*(1-v)
            p=np.column_stack([xx,yy])
            if LineString(p).length>=2.8:
                paths.append(path_record(f'{identity}/bundle-{side}/run-{i}',p,identity,'soil-flow',.5,depth,'soil-ink'))
    support=Polygon([(x0,y0-height*.6),(x0+width*1.1,y0-height*.6+slope*width),
                     (x0+width*1.1,y0+height*1.1+slope*width),(x0,y0+height*1.1)])
    for p in paths:
        p.update(generator_seed=seed,catalog_version=VERSION,object_form='soil',semantic_opaque=False,
                 surface_source_id=identity,placement_uncertainty='synthetic supporting surface only')
    return Surface(identity,support,paths,[],False,depth,
                   dict(version=VERSION,seed=seed,detail=detail,slope=slope,mound=mound,
                        evidence='synthetic supporting surface',surface_ownership=identity))


def synthetic_terrain(width=120, identity='fixture-AC', depth=5.):
    """A/C-like proxy only; never load, rename or regenerate accepted vectors."""
    out=[]
    for i,y in enumerate(np.arange(31.,91.,4.8)):
        x=np.linspace(4,width-4,130)
        p=np.c_[x,y-7*np.exp(-((x-37)/25)**2)+2*np.sin(x/33+i*.13)]
        out.append(path_record(f'{identity}/A/{i}',p,identity,'A-like',.55,depth,'terrain-ink'))
    for i,x in enumerate(np.arange(18.,width-6,15.)):
        t=np.linspace(0,1,60); p=np.c_[x+12*t,44+38*t-5*np.sin(np.pi*t)]
        out.append(path_record(f'{identity}/C/{i}',p,identity,'C-like',.45,depth,'terrain-ink'))
    return out
