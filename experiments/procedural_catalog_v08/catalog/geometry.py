"""Native-mm vector records, interpolation and documented environmental inputs."""
from dataclasses import dataclass, field, asdict, replace
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config/catalog.json").read_text())

def rng(*labels):
    raw = json.dumps([CFG["seed_root"], *labels], ensure_ascii=False).encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(raw).digest()[:8], "big"))

@dataclass
class Stroke:
    id: str
    xy: list
    role: str
    medium: str
    group: str
    owner: str
    pressure_mm: list
    phase: str
    pigment: str = ""
    features: dict = field(default_factory=dict)

    @property
    def length(self):
        return length(self.xy)

def length(points):
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())

def curve(points, bend=.75, step=.68):
    """Cubic interpolation with endpoint tangents and bounded handle length."""
    p = np.asarray(points, float)
    segments = []
    for i, (a, b) in enumerate(zip(p, p[1:])):
        d = np.linalg.norm(b-a)
        if d < 1e-7:
            continue
        tangent_a = b - (p[i-1] if i else a)
        tangent_b = (p[i+2] if i+2 < len(p) else b) - a
        h1 = a + tangent_a / max(np.linalg.norm(tangent_a), 1e-7) * d * .29 * bend
        h2 = b - tangent_b / max(np.linalg.norm(tangent_b), 1e-7) * d * .29 * bend
        t = np.linspace(0, 1, max(2, int(np.ceil(d/step))+1))[:,None]
        seg = (1-t)**3*a+3*(1-t)**2*t*h1+3*(1-t)*t*t*h2+t**3*b
        segments.extend(seg[:-1])
    return np.asarray([*segments,p[-1]])

def resample(points, step=1.2):
    xy = np.asarray(points)
    d = np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    t = np.linspace(0,d[-1],max(2,int(np.ceil(d[-1]/step))+1))
    return np.column_stack([np.interp(t,d,xy[:,i]) for i in range(2)])

def poly_parts(geom, minimum):
    """Keep useful polyline parts, ordered along the original calling segment."""
    if geom.is_empty:
        return []
    parts = [geom] if geom.geom_type=="LineString" else list(getattr(geom,"geoms",[]))
    return [np.asarray(g.coords) for g in parts if g.geom_type=="LineString" and g.length >= minimum]

def stroke(key, xy, role, group, owner, strong=False, layer=0, pigment="", features=None):
    p = np.asarray(xy,float)
    # Remove coincident consecutive samples before planning physical motion.
    p = p[np.r_[True,np.linalg.norm(np.diff(p,axis=0),axis=1)>1e-6]]
    u = np.linspace(0,1,len(p))
    yy = np.minimum(1,np.minimum(u,1-u)*8)
    mat = "COLOR" if pigment else "MEDIUM_INK" if strong else "LIGHT_INK"
    phase = "COLOR" if pigment else f"INK_{(3 if strong else 1)+int(layer)%2}"
    base = CFG["plot_intent"]["base_compression_mm"][mat]
    pressure = base * (.55+.45*yy)
    return Stroke(key,p.tolist(),role,mat,group,owner,pressure.round(6).tolist(),phase,pigment,features or {})

def move(strokes, dx,dy):
    return [replace(s,xy=(np.asarray(s.xy)+[dx,dy]).tolist()) for s in strokes]

class Environment:
    """Registered regular grid. Elevations inform slope, cover informs occurrence."""
    def __init__(self, grid):
        self.tag = grid["provenance"]
        self.origin = np.array(grid["origin_mm"],float)
        self.spacing = float(grid["spacing_mm"])
        self.z = np.asarray(grid["z"],float)
        self.cover = np.asarray(grid["cover_proxy"],float)
        if self.z.ndim!=2 or min(self.z.shape)<2 or self.z.shape!=self.cover.shape or self.spacing<=0:
            raise ValueError("Use matching rectangular elevation and cover grids with positive spacing.")
        if not np.isfinite(self.z).all() or not np.isfinite(self.cover).all() or (self.cover<0).any() or (self.cover>1).any():
            raise ValueError("Use finite elevations and cover values normalized to [0,1].")
        self.z_to_horizontal = float(grid.get("z_to_horizontal_unit_factor",1.0))
        if not np.isfinite(self.z_to_horizontal) or self.z_to_horizontal<=0:
            raise ValueError("Vertical-to-horizontal unit factor must be positive.")
        self.gy,self.gx = np.gradient(self.z*self.z_to_horizontal,self.spacing)

    def sample(self,x,y):
        a = np.clip((np.array([x,y])-self.origin)/self.spacing,[0,0],[self.z.shape[1]-1,self.z.shape[0]-1])
        x0,y0 = np.floor(a).astype(int)
        tx,ty=a-[x0,y0]
        x1,y1=min(x0+1,self.z.shape[1]-1),min(y0+1,self.z.shape[0]-1)
        def interp(f):
            return float((1-ty)*((1-tx)*f[y0,x0]+tx*f[y0,x1])+ty*((1-tx)*f[y1,x0]+tx*f[y1,x1]))
        gx,gy=interp(self.gx),interp(self.gy)
        return {"provenance":self.tag,"elevation":interp(self.z),"slope_dx":gx,"slope_dy":gy,
                "slope_degrees":float(np.degrees(np.arctan(np.hypot(gx,gy)))),"cover_proxy":interp(self.cover)}
