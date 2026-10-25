"""HANJI v0.10.1 | Rhino 8 / GH Python 3 SCRIPT MODE | millimetres.
600x600 / 9x200. D layered mountains + mixed gentle sea + grid-aligned stipple.
Paste WHOLE file. a -> Mesh. PanelIndex=0 shows nine printable panels.
Optional outputs Panels, LocalPanels, ColoredSurface (UNPAINTED envelope),
DotPreview (colored dot mesh, NOT print geometry), DotPoints, DotPointsLocal,
SurfacePoints, Report, PanelA..I. DotPoints use nominal Z, no display lift.
Inputs (Item): PanelIndex, Pitch, Base, Frame, Strut, RibT, Sample, Gap,
Diagonals, Joint, Clearance, JointHeight, ReliefMax, DiscZ, DiscRelief,
Seed, SeaMix, SeaHeight, DotLocation ('dense'/'node'/'center'), DotEvery, DotDiameter, DotDensity,
PreviewOnly, ExportMaps, ExportFolder. No plugins/numpy needed in GH.
All retained walls start Z=0. No bottom sheet; no arches or separate keys.
Male dovetails fixed Z=0..JointHeight; female sockets remain open above.
Sun/moon dots form circles; optional flat relief envelopes under both groups.
Export CSV+JSON only. NO STL or plotter G-code. Dry-paper calibration pending.
PETG thinner-wall trial: DEFAULT Strut=0.45 mm, RibT=0.60 mm; both allow 0.40 mm.
Frame=1, Base=2, JointHeight=2 retained. OLD input sliders override these defaults.
Orthogonal interior width is max(Strut,RibT) because grid footprints overlap.
For a typical 0.4mm nozzle, do not treat sub-0.4 walls as reliable without testing.
PLA does NOT have a universal 0.8mm minimum: stiffness/toughness are different.
Review slicer single-wall paths, then pulp/dry/contact test before full production.
"""
import math, bisect, os, json, csv
from collections import defaultdict

DEFAULTS=dict(size=200.0,rows=3,cols=3,panel_index=0,pitch=10.0,
    base=2.0,frame=1.0,strut=.45,rib_t=.60,sample=2.5,gap=0.0,
    diagonals=True,joint=True,joint_mode='slide',joint_depth=3.2,
    joint_half_neck=2.4,joint_half_wide=4.2,clearance=.2,joint_height=2.0,
    relief_max=20.0,disc_z=6.0,disc_relief=True,seed=7,sea_mix=1.0,sea_height=4.0,
    dot_location='dense',dot_every=1,dot_diameter=2.2,dot_density=1.0,
    preview_only=False,export_maps=False,export_folder='')

# Exact HEX transcribed from the attached palette, NOT sampled from its chips.
# Spare crimson has no original letter ID, so the default stays literal D4.
INK_HEX={'A3':'#8E9FA9','A4':'#C8A896','B1':'#1E56A0','B2':'#14293D',
         'C2':'#98C245','C4':'#566432','C5':'#173425','D4':'#A2432B'}
INKS={k:tuple(int(v[i:i+2],16)/255.0 for i in (1,3,5)) for k,v in INK_HEX.items()}
DISKS=(('moon',115.0,500.0),('sun',480.0,493.0))
PAPER=(.947,.936,.887)

def check_config(p):
    p=dict(p)
    for k,v in p.items():
        if isinstance(v,(int,float)) and not math.isfinite(v):raise ValueError(k+' must be finite')
    if (p['size'],p['rows'],p['cols'])!=(200,3,3):raise ValueError('Fixed 600x600 / 9x200.')
    for k,lo,hi in [('panel_index',0,9),('seed',0,9999),('dot_every',1,3)]:
        if not float(p[k]).is_integer() or not lo<=p[k]<=hi:raise ValueError(k+' integer out of range')
        p[k]=int(p[k])
    ranges=dict(pitch=(8,14),base=(1.6,3),frame=(.8,1.5),strut=(.4,1.2),
        rib_t=(.4,1.6),sample=(1,3),clearance=(.1,.4),joint_height=(1.6,3),
        relief_max=(8,20),disc_z=(4,8),sea_mix=(0,1.5),sea_height=(0,6),
        dot_diameter=(1,5),dot_density=(.2,1.3))
    for k,(lo,hi) in ranges.items():
        if not lo<=p[k]<=hi:raise ValueError('{} must be {}..{}'.format(k,lo,hi))
    if p['joint_height']>p['base']:raise ValueError('JointHeight <= Base keeps tabs below every surface.')
    if p['disc_z']>p['relief_max']:raise ValueError('DiscZ <= ReliefMax')
    for k in ('diagonals','joint','disc_relief','preview_only','export_maps'):p[k]=bool(p[k])
    p['joint_mode']='slide'
    p['dot_location']=str(p['dot_location']).strip().lower()
    if p['dot_location'] not in ('dense','node','center'):raise ValueError('DotLocation=dense, node or center')
    if p['dot_location']=='center' and not p['diagonals']:
        raise ValueError('Center dots require Diagonals=True for direct lattice backing.')
    if p['gap']<0:raise ValueError('Gap>=0')
    p['cells']=int(math.ceil((200-2*p['frame'])/p['pitch']))
    p['actual_pitch']=(200-2*p['frame'])/p['cells']
    return p

def smooth(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a)));return t*t*(3-2*t)

def raw_field(x,y,p):
    u,v=x/600.0,y/600.0;T=2*math.pi
    a=u+.020*math.sin(T*(1.3*v+.6*u)+1.2)+.008*math.sin(T*(2.1*u-v))
    b=v+.012*math.sin(T*(1.7*u-.4*v))
    mount=0.0
    for center,amp,width,phase,cycles in [(.285,6.0,.051,.1,2.0),
        (.397,9.1,.058,1.7,2.7),(.510,10.1,.066,3.0,2.1),(.612,5.8,.052,4.8,2.4)]:
        backbone=center+.040*math.sin(T*cycles*a+phase)+.017*math.sin(T*4.1*a+.6*phase)
        mass=.65+.35*math.exp(-((a-(.52+.09*math.sin(phase)))/.30)**2)
        mount+=amp*mass*math.exp(-((b-backbone)/width)**2)
    phase=T*(mount/3.5+.16*math.sin(T*a)+.09*math.sin(T*2.2*a))
    contour=(.5+.5*math.cos(phase))**2
    active=smooth(.8,3.0,mount)
    mountain=mount+.8*active*contour
    water=1-smooth(.19,.34,b)
    s=p['sea_mix']
    # Modulated horizontal, oblique and broad curved waves; small relief amplitude.
    yy=y+s*(7*math.sin(T*x/210)+5*math.sin(T*(x/320+y/180)))
    p1=T*(yy/34+.12*math.sin(T*x/150))
    p2=T*((.23*s*x+y)/52+.10*s*math.cos(T*x/280))
    p3=T*(math.hypot(x-460,y+100)/66+.06*math.sin(T*x/230))
    f1=.5+.5*math.cos(p1);f2=.5+.5*math.cos(p2);f3=.5+.5*math.cos(p3)
    sea_intensity=(.47*f1+.28*f2+.20*s*f3)/(.75+.20*s)
    sea=water*(.47*f1+.28*f2+.20*s*f3)*(.78+.22*math.cos(T*(x/270-y/410))**2)
    # Additional PHYSICAL ripples; retain the previous normalization and mountain scale.
    crest=.50*f1*f1+.28*f2*f2+.22*f3*f3
    shore=(1-smooth(.17,.39,b))*(1-.40*active)
    sea_extra=p['sea_height']*shore*crest
    sky=.12*(1-smooth(.12,.32,mount))*(.5+.5*math.cos(T*(2.1*a+3*b)))
    moon=1-smooth(45,51,math.hypot(x-115,y-500))
    sun=1-smooth(45,51,math.hypot(x-480,y-493))
    return dict(raw=mountain+sea+sky,mount=mount,range=active,active=active,
        contour=contour,phase=phase,water=water,sea_intensity=sea_intensity,
        sea_phase=p1,moon=moon,sun=sun,sea_crest=crest,shore=shore,sea_extra=sea_extra,
        side=(math.exp(-((u-.07)/.115)**2)+math.exp(-((u-.93)/.115)**2))*smooth(.20,.35,v)*(1-smooth(.65,.75,v)))

_norm_cache={}
def normalization(p):
    key=p['sea_mix']
    if key not in _norm_cache:
        _norm_cache[key]=max(raw_field(x,y,p)['raw'] for y in range(0,601,5) for x in range(0,601,5))
    return _norm_cache[key]

def height(x,y,p):
    f=raw_field(x,y,p)
    z=min(p['relief_max'],p['base']+(p['relief_max']-p['base'])*min(1.0,f['raw']/normalization(p))+f['sea_extra'])
    if p['disc_relief']:
        t=max(f['moon'],f['sun']);z=z*(1-t)+p['disc_z']*t
    return z

def hash_point(x,y,seed):
    n=(int(round(x*1000))*73856093 ^ int(round(y*1000))*19349663 ^ (seed+1)*83492791)&0xffffffff
    n=((n^(n>>16))*0x7feb352d)&0xffffffff
    n=((n^(n>>15))*0x846ca68b)&0xffffffff
    return (n^(n>>16))/4294967295.0

def dot_style(x,y,p):
    # One touch / one ink per chosen point; no gradients or continuous color fill.
    for name,cx,cy in DISKS:
        if math.hypot(x-cx,y-cy)<=45:
            return ('A4' if name=='moon' else 'D4',name)
    f=raw_field(x,y,p);r=hash_point(x,y,p['seed'])
    sea_w=f['shore'];mount_w=f['active']
    density=p['dot_density']*max(sea_w*(.36+.57*f['sea_crest']),mount_w*(.42+.52*f['contour']))
    if r>=min(1,density):return None
    q=hash_point(x,y,p['seed']+39);pick=hash_point(x,y,p['seed']+81)
    # Smooth probabilistic mixing of mountain/sea color roles, no hard shore cutoff.
    use_sea=pick<sea_w/max(1e-9,sea_w+mount_w)
    if use_sea:
        if f['sea_crest']>.62:ink='A4' if q<.60 else 'A3'
        elif f['sea_crest']>.27:ink='B1' if q<.52 else 'A3' if q<.84 else 'B2'
        else:ink='B2' if q<.76 else 'B1'
        return ink,'shore' if mount_w>.15 else 'sea'
    if f['side']>.25 and q<.44:
        ink='D4' if q<.08 else 'B1' if q<.29 else 'B2'
    elif f['contour']>.64:ink='C2' if q<.72 else 'C4'
    elif f['contour']>.20:ink='C4' if q<.78 else 'C5'
    else:ink='C5' if q<.84 else 'B2'
    return ink,'shore' if sea_w>.15 else 'mountain'

def dot_records(p):
    f,n,e=p['frame'],p['cells'],p['dot_every'];d=p['actual_pitch']
    if p['dot_location']=='dense':indices=[k for k in range(1,2*n) if k%e==0]
    elif p['dot_location']=='node':indices=[2*i for i in range(1,n,e)]
    else:indices=[2*i+1 for i in range(0,n,e)]
    records=[]
    for panel in range(9):
        r,c=panel//3,panel%3
        for ky in indices:
            for kx in indices:
                if kx%2 and ky%2:
                    if not p['diagonals']:continue
                    support='diagonal_strut_midpoint'
                elif kx%2:support='horizontal_rib_midpoint'
                elif ky%2:support='vertical_rib_midpoint'
                else:support='orthogonal_rib_intersection'
                lx,ly=f+kx*d/2,f+ky*d/2
                x,y=c*200+lx,r*200+ly;style=dot_style(x,y,p)
                if style is None:continue
                ink,region=style
                records.append(dict(x=x,y=y,z=height(x,y,p),panel_id=panel+1,
                    local_x=lx,local_y=ly,ink=ink,region=region,support=support,
                    diameter=p['dot_diameter']))
    return records


def panel_rc(index,p):return index//3,index%3


def joint_config(p,index):
    if not p['joint']:return (),()
    r,c=panel_rc(index,p)
    return tuple(s for s,on in [('left',c>0),('bottom',r>0)] if on),tuple(s for s,on in [('right',c<2),('top',r<2)] if on)


def transform_side(poly,side,s):
    if side=='left':return clean(poly)
    if side=='right':return clean([(s+x,y) for x,y in poly])
    if side=='bottom':return clean([(y,x) for x,y in poly])
    return clean([(y,s+x) for x,y in poly])


def joint_polygons(p,side,male=False):
    s=p['size'];d=p['joint_depth'];n=p['joint_half_neck'];w=p['joint_half_wide']
    if male:d-=p['clearance'];n-=p['clearance'];w-=p['clearance']
    return [transform_side([(0,cy-n),(d,cy-w),(d,cy+w),(0,cy+n)],side,s) for cy in (.3*s,.7*s)]


def point2(q): return (round(float(q[0]), 7), round(float(q[1]), 7))

def area(poly): return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))

def clean(poly):
    out = []
    for q in poly:
        q = point2(q)
        if not out or q != out[-1]: out.append(q)
    if len(out) > 1 and out[0] == out[-1]: out.pop()
    if len(out) < 3 or abs(area(out)) < 1e-9: return []
    return out if area(out) > 0 else list(reversed(out))

def clip(poly, a, b, c):
    if not poly: return []
    out = []
    for q, r in zip(poly, poly[1:] + poly[:1]):
        fq, fr = a * q[0] + b * q[1] + c, a * r[0] + b * r[1] + c
        iq, ir = fq >= -1e-9, fr >= -1e-9
        if iq: out.append(q)
        if iq != ir:
            t = fq / (fq - fr)
            out.append((q[0] + t * (r[0] - q[0]), q[1] + t * (r[1] - q[1])))
    return clean(out)

def partition_convex(poly, cutter):
    remain, outside = poly, []
    for q, r in zip(cutter, cutter[1:] + cutter[:1]):
        dx, dy = r[0] - q[0], r[1] - q[1]
        a, b, c = -dy, dx, dy * q[0] - dx * q[1]
        part = clip(remain, -a, -b, -c)
        if part: outside.append(part)
        remain = clip(remain, a, b, c)
        if not remain: break
    return outside, remain

def bbox(poly): return min(q[0] for q in poly), min(q[1] for q in poly), max(q[0] for q in poly), max(q[1] for q in poly)
def overlap(a, b): return a[0] < b[2] - 1e-8 and a[2] > b[0] + 1e-8 and a[1] < b[3] - 1e-8 and a[3] > b[1] + 1e-8



def line_info(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    if ux < -1e-8 or (abs(ux) < 1e-8 and uy < 0): ux, uy = -ux, -uy
    nx, ny = -uy, ux
    return (round(nx, 4), round(ny, 4), round(nx * a[0] + ny * a[1], 4)), ux, uy


def conform_edges(regions):
    groups = {}
    for poly, _ in regions:
        for a, b in zip(poly, poly[1:] + poly[:1]):
            key, ux, uy = line_info(a, b)
            if key not in groups: groups[key] = [ux, uy, set()]
            groups[key][2].update([a, b])
    lines = {}
    for key, (ux, uy, pts) in groups.items():
        ordered = sorted((ux * q[0] + uy * q[1], q) for q in pts)
        lines[key] = (ux, uy, [t for t, q in ordered], [q for t, q in ordered])
    result = []
    for poly, kind in regions:
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            key, _, _ = line_info(a, b)
            ux, uy, ts, qs = lines[key]
            ta, tb = ux * a[0] + uy * a[1], ux * b[0] + uy * b[1]
            lo, hi = sorted([ta, tb])
            chosen = qs[bisect.bisect_right(ts, lo + 1e-6):bisect.bisect_left(ts, hi - 1e-6)]
            if ta > tb: chosen = list(reversed(chosen))
            out.extend([a] + chosen)
        result.append((out, kind))
    return result


class MeshData:
    def __init__(self):
        self.vertices = []; self.faces = []; self._index = {}

    def vertex(self, q):
        q = tuple(round(v, 7) for v in q)
        if q not in self._index:
            self._index[q] = len(self.vertices); self.vertices.append(q)
        return self._index[q]

    def triangle(self, a, b, c):
        ids = tuple(self.vertex(q) for q in (a, b, c))
        if len(set(ids)) == 3: self.faces.append(ids)

    def fan(self, poly, center=None, reverse=False):
        if center is None:
            center = tuple(sum(q[k] for q in poly) / len(poly) for k in range(3))
        for a, b in zip(poly, poly[1:] + poly[:1]):
            self.triangle(center, b, a) if reverse else self.triangle(center, a, b)

    def translated(self, dx, dy, dz=0):
        m = MeshData()
        m.vertices = [(x + dx, y + dy, z + dz) for x, y, z in self.vertices]
        m.faces = list(self.faces)
        return m





def grid_layout(p):
    s,f,n=p['size'],p['frame'],p['cells'];d=(s-2*f)/n
    grid=[f+i*d for i in range(n+1)];ribs=grid[1:-1]
    cuts=[0,s,f,s-f];pad=p['joint_depth']+1.2
    cuts.extend([pad,s-pad])
    for cy in (.3*s,.7*s):cuts.extend([cy-p['joint_half_wide']-.8,cy+p['joint_half_wide']+.8])
    for v in grid:cuts.extend([v-p['strut']/2,v+p['strut']/2])
    for v in ribs:cuts.extend([v-p['rib_t']/2,v+p['rib_t']/2])
    cuts=sorted(set(round(max(0,min(s,v)),7) for v in cuts));dense=[]
    for a,b in zip(cuts,cuts[1:]):
        num=max(1,int(math.ceil((b-a)/p['sample'])))
        dense.extend(a+(b-a)*j/num for j in range(num))
    dense.append(s)
    return grid,ribs,sorted(set(round(v,7) for v in dense)),d




def rect(x0,y0,x1,y1):return clean([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])



def footprint(p,index=0):
    grid,ribs,cuts,d=grid_layout(p);s,f=p['size'],p['frame'];regions=[]
    females,males=joint_config(p,index);sockets=[];arms=[];pads=[]
    sockets=[q for side in females for q in joint_polygons(p,side)]
    pad=p['joint_depth']+1.2
    for side in females+males:
        for cy in (.3*s,.7*s):
            xx0,xx1=(-pad,0) if side in males else (0,pad)
            pads.append(transform_side(rect(xx0,cy-p['joint_half_wide']-.8,xx1,cy+p['joint_half_wide']+.8),side,s))
    arms=[q for side in males for q in joint_polygons(p,side,True)]
    # Exactly include landing / relief rectangle boundaries in the tiling.
    extra=cuts[:]
    for q in sockets+pads:
        for x,y in q:extra.extend([max(0,min(s,x)),max(0,min(s,y))])
    cuts=sorted(set(round(v,7) for v in extra));boxes=[bbox(q) for q in sockets];pb=[bbox(q) for q in pads]
    for x0,x1 in zip(cuts,cuts[1:]):
        for y0,y1 in zip(cuts,cuts[1:]):
            x,y=(x0+x1)/2,(y0+y1)/2;poly=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
            keep=(x<f or x>s-f or y<f or y>s-f
                or any(bb[0]-1e-8<x<bb[2]+1e-8 and bb[1]-1e-8<y<bb[3]+1e-8 for bb in pb)
                or any(abs(x-v)<p['rib_t']/2+1e-8 or abs(y-v)<p['rib_t']/2+1e-8 for v in ribs)
                or any(abs(x-v)<p['strut']/2+1e-8 or abs(y-v)<p['strut']/2+1e-8 for v in grid))
            if not keep:
                if not p['diagonals']:continue
                i=max(0,min(p['cells']-1,int((x-f)/d)));j=max(0,min(p['cells']-1,int((y-f)/d)))
                r,c=panel_rc(index,p)
                if (i+j+c*p['cells']+r*p['cells'])%2==0:a,b,k=-1,1,grid[i]-grid[j]
                else:a,b,k=1,1,-grid[i]-grid[j+1]
                half=p['strut']*math.sqrt(2)/2
                poly=clip(clip(poly,a,b,k+half),-a,-b,-k+half)
                if not poly:continue
            pieces=[poly]
            for cutter,bb in zip(sockets,boxes):
                out=[]
                for q in pieces:
                    if not overlap(bbox(q),bb):out.append(q);continue
                    outside,_=partition_convex(q,cutter);out.extend(outside)
                pieces=out
            regions.extend((q,'deep') for q in pieces)
    regions.extend((q,'joint') for q in arms)
    return conform_edges(regions)



def mesh_regions(p,index,regions,top_override=None):
    """Closed stepped extrusion: fixed-height tabs join taller continuous walls.
    Split external vertical edges at incident top levels to avoid T-junctions.
    """
    m=MeshData();edges=defaultdict(list);levels=defaultdict(set)
    r,c=panel_rc(index,p);gx,gy=c*200,r*200;cache={}
    def top(q,kind):
        key=(q,kind)
        if key not in cache:
            z=(top_override if top_override is not None else
                p['joint_height'] if kind=='joint' else height(q[0]+gx,q[1]+gy,p))
            cache[key]=round(z,7)
        return cache[key]
    for poly,kind in regions:
        mid=(sum(q[0] for q in poly)/len(poly),sum(q[1] for q in poly)/len(poly))
        m.fan([(x,y,top((x,y),kind)) for x,y in poly],(mid[0],mid[1],top(mid,kind)))
        m.fan([(x,y,0) for x,y in poly],(mid[0],mid[1],0),True)
        for q in poly:levels[q].add(top(q,kind))
        for a,b in zip(poly,poly[1:]+poly[:1]):
            edges[tuple(sorted((a,b)))].append((a,b,kind))
    def step_wall(a,b,la,lb,ha,hb):
        poly=[(a[0],a[1],la),(b[0],b[1],lb)]
        poly += [(b[0],b[1],z) for z in sorted(levels[b]) if lb<z<hb]
        poly += [(b[0],b[1],hb),(a[0],a[1],ha)]
        poly += [(a[0],a[1],z) for z in sorted(levels[a],reverse=True) if la<z<ha]
        m.fan(poly)
    for uses in edges.values():
        if len(uses)==1:
            a,b,kind=uses[0];step_wall(a,b,0,0,top(a,kind),top(b,kind))
        elif len(uses)==2:
            a,b,k=uses[0];_,_,k2=uses[1]
            h1a,h1b=top(a,k),top(b,k);h2a,h2b=top(a,k2),top(b,k2)
            if h1a==h2a and h1b==h2b:continue
            # JointHeight <= Base guarantees one region is uniformly lower.
            if h1a>=h2a and h1b>=h2b:step_wall(a,b,h2a,h2b,h1a,h1b)
            elif h2a>=h1a and h2b>=h1b:step_wall(b,a,h1b,h1a,h2b,h2a)
            else:raise ValueError('Crossing top heights at a shared edge.')
        else:raise ValueError('Overlapping planar regions.')
    return m

def make_panel(p,index=0):
    regions=footprint(p,index);return mesh_regions(p,index,regions),regions


def _write_maps_content(p,folder,step=2.0):
    n=int(round(600/step));dots=dot_records(p)
    with open(os.path.join(folder,'surface_map_design_xyz.csv'),'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['x_mm','y_mm','z_design_mm','panel_id','local_x_mm','local_y_mm',
            'mountain_weight','water_weight','contour_intensity','sea_intensity','disc_weight','shore_weight','sea_added_mm'])
        for j in range(n+1):
            y=600*j/n
            for i in range(n+1):
                x=600*i/n;c=min(2,int(x//200));r=min(2,int(y//200));q=raw_field(x,y,p)
                w.writerow([round(x,4),round(y,4),round(height(x,y,p),5),r*3+c+1,
                    round(x-200*c,4),round(y-200*r,4)]+
                    [round(q[k],6) for k in ('active','water','contour','sea_intensity')]+[round(max(q['moon'],q['sun']),6),round(q['shore'],6),round(q['sea_extra'],6)])
    with open(os.path.join(folder,'dot_map_design_xyz.csv'),'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['dot_id','panel_id','x_mm','y_mm','z_design_mm',
            'local_x_mm','local_y_mm','color_id','region','support_kind','preview_diameter_mm','r','g','b'])
        for i,d in enumerate(dots):
            w.writerow([i+1,d['panel_id']]+[round(d[k],5) for k in ('x','y','z','local_x','local_y')]+
                [d['ink'],d['region'],d['support'],d['diameter']]+list(INKS[d['ink']]))
    for panel in range(1,10):
        with open(os.path.join(folder,'dots_P{:02d}_local_and_global.csv'.format(panel)),'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['dot_id_global','panel_id','local_x_mm','local_y_mm','z_design_mm','global_x_mm','global_y_mm','color_id','support_kind','preview_diameter_mm'])
            for i,d in enumerate(dots):
                if d['panel_id']==panel:
                    w.writerow([i+1,panel]+[round(d[k],5) for k in ('local_x','local_y','z','x','y')]+[d['ink'],d['support'],d['diameter']])
    with open(os.path.join(folder,'selected_palette.csv'),'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['palette_id','hex','r_255','g_255','b_255','dot_count'])
        for ink,hexvalue in INK_HEX.items():
            w.writerow([ink,hexvalue]+[int(hexvalue[i:i+2],16) for i in (1,3,5)]+[sum(d['ink']==ink for d in dots)])
    with open(os.path.join(folder,'design_metadata.json'),'w',encoding='utf-8') as f:
        json.dump(dict(version='0.10.1',parameters=p,units='mm',extent=[600,600],
            origin='bottom-left artwork; bed Z=0',panel_order='left-to-right, bottom-to-top P01..P09',
            whole_surface_step_mm=step,dot_count=len(dots),palette=INKS,palette_hex=INK_HEX,
            palette_origin='Exact HEX labels in attached palette screenshots. D4 is literal #A2432B; no spare-color reassignment.',
            candidate_pitch_mm=p['actual_pitch']/2 if p['dot_location']=='dense' else p['actual_pitch'],
            per_panel_files='dots_P01..P09_local_and_global.csv; same Z convention as whole artwork',
            dot_selection='deterministic sparse subset of actual per-panel lattice coordinates',
            circles=dict(moon=[115,500],sun=[480,493],center_radius_mm=45,relief_collar_outer_radius_mm=51),
            joint='Male Z=0..JointHeight, open-through female pocket, NO Z latch.',
            preview='Unpainted nominal paper envelope + colored dot marks. Preview marks lifted 0.08mm only in GH.',
            limitations=['CSV Z is nominal design envelope, not measured dry hanji.',
                'Brush pressure, dry shrinkage, assembly error and machine origin not calibrated.',
                'Palette IDs match the screenshots but are not assigned physical plotter tool coordinates.',
                'Preview diameter is an assumed mark size, not predicted wet ink spread.',
                'Analytic Z may differ from triangulated mesh between vertices.'],
            contains_stl=False,contains_machine_commands=False),f,ensure_ascii=False,indent=2)

def write_maps(p,folder,step=2.0):
    import tempfile
    with tempfile.TemporaryDirectory(prefix='hanji_maps_',dir=folder) as tmp:
        _write_maps_content(p,tmp,step)
        for name in ('surface_map_design_xyz.csv','dot_map_design_xyz.csv','selected_palette.csv')+tuple('dots_P{:02d}_local_and_global.csv'.format(i) for i in range(1,10))+('design_metadata.json',):
            os.replace(os.path.join(tmp,name),os.path.join(folder,name))

def appearance_mesh(p,rg):
    from System.Drawing import Color
    mesh=rg.Mesh();n=200;step=3.0;color=Color.FromArgb(*(int(255*v) for v in PAPER))
    for j in range(n+1):
        for i in range(n+1):
            x,y=i*step,j*step;mesh.Vertices.Add(x,y,height(x,y,p));mesh.VertexColors.Add(color)
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i;mesh.Faces.AddFace(a,a+1,a+n+2,a+n+1)
    mesh.Normals.ComputeNormals();return mesh

def dot_preview_mesh(dots,p,rg):
    from System.Drawing import Color
    mesh=rg.Mesh();n=16
    for d in dots:
        x,y=d['x'],d['y'];radius=d['diameter']/2;start=mesh.Vertices.Count
        color=Color.FromArgb(*(int(255*v) for v in INKS[d['ink']]))
        mesh.Vertices.Add(x,y,d['z']+.08);mesh.VertexColors.Add(color)
        for i in range(n):
            t=2*math.pi*i/n;xx,yy=x+radius*math.cos(t),y+radius*math.sin(t)
            mesh.Vertices.Add(xx,yy,height(xx,yy,p)+.08);mesh.VertexColors.Add(color)
        for i in range(n):mesh.Faces.AddFace(start,start+1+i,start+1+(i+1)%n)
    mesh.Normals.ComputeNormals();return mesh

def to_rhino(m,rg):
    q=rg.Mesh()
    for x,y,z in m.vertices:q.Vertices.Add(x,y,z)
    for a,b,c in m.faces:q.Faces.AddFace(a,b,c)
    q.Normals.ComputeNormals();q.Compact()
    if not q.IsValid or not q.IsClosed:raise ValueError('Rhino invalid/open print mesh.')
    return q

def run_grasshopper(scope,rg):
    p=dict(DEFAULTS)
    inputs=dict(PanelIndex='panel_index',Pitch='pitch',Base='base',Frame='frame',
        Strut='strut',RibT='rib_t',Diagonals='diagonals',Joint='joint',Clearance='clearance',
        JointHeight='joint_height',Sample='sample',Gap='gap',ReliefMax='relief_max',
        DiscZ='disc_z',DiscRelief='disc_relief',Seed='seed',SeaMix='sea_mix',SeaHeight='sea_height',
        DotLocation='dot_location',DotEvery='dot_every',DotDiameter='dot_diameter',
        DotDensity='dot_density',PreviewOnly='preview_only',ExportMaps='export_maps',ExportFolder='export_folder')
    for name,key in inputs.items():
        if scope.get(name) is not None:p[key]=scope[name]
    p=check_config(p);normalization(p)
    selected=list(range(9)) if p['panel_index']==0 else [p['panel_index']-1]
    panels=[];locals=[];ids=[]
    if not p['preview_only']:
        for i in selected:
            m,_=make_panel(p,i);r,c=panel_rc(i,p)
            local=to_rhino(m,rg);assembled=local.DuplicateMesh()
            assembled.Transform(rg.Transform.Translation(c*(200+p['gap']),r*(200+p['gap']),0))
            locals.append(local);panels.append(assembled);ids.append(i)
    all_dots=dot_records(p);dots=[d for d in all_dots if d['panel_id']-1 in selected]
    dot_points=[rg.Point3d(d['x'],d['y'],d['z']) for d in dots]
    dot_points_local=[rg.Point3d(d['local_x'],d['local_y'],d['z']) for d in dots]
    if p['export_maps']:
        folder=str(p['export_folder'])
        if not os.path.isabs(folder) or not os.path.isdir(folder):raise ValueError('ExportFolder must be existing absolute folder.')
        write_maps(p,folder)
    report=['HANJI v0.10.1 / PETG thinner-wall TRIAL / previous composition and dots',
        '600x600 / 9x200 / P01 bottom-left, P09 top-right / PanelIndex=0 shows all.',
        'Bed-to-top ceiling {:.2f} mm; Base {:.2f}; no solid bottom sheet.'.format(p['relief_max'],p['base']),
        'Male dovetail fixed Z=0..{:.2f}; female sockets remain OPEN; no Z lock.'.format(p['joint_height']),
        'Frame {:.2f} each / seam {:.2f} / pitch {:.2f} mm.'.format(p['frame'],2*p['frame'],p['actual_pitch']),
        'Strut {:.2f} / RibT {:.2f} / effective internal orthogonal width {:.2f} mm.'.format(p['strut'],p['rib_t'],max(p['strut'],p['rib_t'])),
        'Thin-wall trial: modeled width is NOT guaranteed sliced extrusion width; inspect every wall path.',
        'DotLocation={} / DotEvery={} / nominal mark diameter {:.2f} mm.'.format(p['dot_location'],p['dot_every'],p['dot_diameter']),
        'Selected dots {} / whole artwork {}. Eight palette IDs; sky mostly unpainted.'.format(len(dots),len(all_dots)),
        'SeaMix={} / SeaHeight={} mm; previous mountain scale retained.'.format(p['sea_mix'],p['sea_height']),
        'Dense candidate pitch {:.2f} mm; ALL marks have rib/strut backing.'.format(p['actual_pitch']/2),
        'Sun/moon circle diameter90; DiscRelief={}; DiscZ={}.'.format(p['disc_relief'],p['disc_z']),
        'Panels/a and LocalPanels/PanelA..I are PRINT geometry.',
        'ColoredSurface is unpainted paper envelope; DotPreview is PAINT DISPLAY only.',
        'DotPoints: GLOBAL nominal XYZ. DotPointsLocal: panel-local XY, overlaps if several panels.',
        'Gap applies to Panels display only; guides/dots/CSV stay at true global coordinates.',
        'PreviewOnly={}. ExportMaps={} saves whole CSV+JSON ONLY.'.format(p['preview_only'],p['export_maps']),
        'No STL/G-code export. Actual paper, ink spread and printer settings still need testing.',
        'Legacy Study/Warp/Detail/Rise/Wave/JointMode/Export inputs ignored.']
    points=[rg.Point3d(x,y,height(x,y,p)) for y in range(0,601,10) for x in range(0,601,10)]
    return (panels,locals,appearance_mesh(p,rg),dot_preview_mesh(dots,p,rg),
        dot_points,dot_points_local,points,'\n'.join(report),ids)

try:import Rhino.Geometry as _rg
except ImportError:_rg=None
if _rg is not None and __name__.split('.')[-1]!='hanji_panel_v101_gh':
    Panels,LocalPanels,ColoredSurface,DotPreview,DotPoints,DotPointsLocal,SurfacePoints,Report,_ids=run_grasshopper(globals(),_rg)
    _named={i:m for i,m in zip(_ids,LocalPanels)}
    PanelA,PanelB,PanelC,PanelD,PanelE,PanelF,PanelG,PanelH,PanelI=[_named.get(i) for i in range(9)]
    a=Panels
    print(Report)
