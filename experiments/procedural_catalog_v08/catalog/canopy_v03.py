"""A shared foliage field, sparse continuous ink, and phase-local spatial scheduling."""
from dataclasses import replace
import json

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree
from shapely.geometry import LineString

from .geometry import ROOT, length, resample, rng, stroke
from .refined_vegetation import WOODY, community, specimen

V03 = json.loads((ROOT / "config/catalog_v03.json").read_text())
C = V03["canopy"]


class CanopyField:
    """Canopy support sampled in mm, with owner, density, and direction channels."""

    def __init__(self, pads, logs):
        self.step = C["grid_mm"]
        self.logs = {m["id"]: m for m in logs}
        self.owners = tuple(sorted({p[4] for p in pads}))
        self.pads = pads
        self.index = {k: i for i, k in enumerate(self.owners)}
        if not pads:
            self.origin = np.zeros(2)
            self.end = self.origin.copy()
            self.energy = np.zeros((2, 2))
            self.overlap = np.zeros((2, 2))
            self.slope = np.zeros((2, 2))
            self.owner_fields = np.empty((0, 2, 2))
            return
        array = np.asarray([p[:4] for p in pads], dtype=float)
        self.origin = np.floor((array[:, :2]-2.5*array[:, 2:]).min(axis=0))
        self.end = np.ceil((array[:, :2]+2.5*array[:, 2:]).max(axis=0))
        nx, ny = np.ceil((self.end-self.origin)/self.step).astype(int)+1
        xx, yy = np.meshgrid(self.origin[0]+self.step*np.arange(nx), self.origin[1]+self.step*np.arange(ny))
        owners = np.zeros((len(self.owners), ny, nx))
        direction = owners.copy()
        for (x, y, w, h, owner) in pads:
            m = self.logs[owner]
            sign = m["growth"]["handedness"]
            slope = {"B": .06, "W": .49, "P": -.21, "U": -.10}[m["family"]]*sign
            dx = xx-x
            g = np.exp(-.5*((dx/max(1.0, w))**2+((yy-y-slope*dx)/max(1.1, .86*h))**2))
            i = self.index[owner]
            owners[i] += g
            bend = {"B":.44,"W":.18,"P":.22,"U":.40}[m["family"]]
            sign_bend = sign if m["family"]=="W" else 1
            direction[i] += g*(slope+bend*sign_bend*np.clip(dx/max(1.,w),-1,1))
        self.owner_fields = 1.42*(1-np.exp(-owners/1.42))
        self.energy = self.owner_fields.sum(axis=0)
        self.overlap = (self.owner_fields >= C["owner_level"]).sum(axis=0).astype(float)
        self.slope = gaussian_filter(direction.sum(axis=0)/np.maximum(.25, owners.sum(axis=0)), 1.25)

    def read(self, grid, xy):
        positions = (np.asarray(xy)-self.origin)/self.step
        return map_coordinates(grid, positions[:, ::-1].T, order=1, mode="constant", cval=0.)

    def density(self, xy):
        return self.read(self.energy, xy)

    def crowded(self, xy):
        return self.read(self.overlap, xy) >= 1.65

    def flow(self, xy):
        return self.read(self.slope, xy)


def split_sampled(xy, keep, minimum):
    """Return whole continuous drawable runs from a sampled vector."""
    bounds = np.flatnonzero(np.diff(np.r_[False, keep, False].astype(np.int8)))
    return [q for a, b in zip(bounds[::2], bounds[1::2]) if len(q := xy[a:b]) > 1 and length(q) >= minimum]


def bridge_strokes(key, field, seed):
    """Connect favorable pad edges using both families' local tangents."""
    if len(field.owners) < 2:
        return []
    random = rng("shared crowns v03", key, seed)
    found = []
    pads = sorted(field.pads, key=lambda p: (p[0], p[1], p[4]))
    lo, hi = C["bridge_span_mm"]
    for i, (ax, ay, aw, ah, a) in enumerate(pads):
        for bx, by, bw, bh, b in pads[i+1:]:
            dx = bx-ax
            if dx > hi:
                break
            if a == b or dx < .45*lo or abs(by-ay) > .57*dx+2.4 or dx > aw+bw+4.0:
                continue
            if abs(field.logs[a]["base_xy"][1]-field.logs[b]["base_xy"][1]) > 34:
                continue
            span = min(8.1, aw*.61)+dx+min(8.1, bw*.61)
            if not lo <= span <= hi:
                continue
            start = np.array([ax-min(8.1, aw*.61), ay-.30*ah])
            end = np.array([bx+min(8.1, bw*.61), by-.25*bh])
            slopes = field.flow(np.array([[ax, ay], [bx, by]]))
            d = end-start
            t = np.linspace(0, 1, max(13, int(span/0.65)))[:, None]
            h1 = start + [d[0]*.30, d[0]*.30*slopes[0]-.22]
            h2 = end - [d[0]*.31, d[0]*.31*slopes[1]+.16]
            line = (1-t)**3*start + 3*(1-t)**2*t*h1 + 3*(1-t)*t*t*h2 + t**3*end
            energy = field.density(line)
            if np.quantile(energy, .15) < C["bridge_level"] or field.crowded(line).mean() < .22:
                continue
            families = [field.logs[o]["family"] for o in (a, b)]
            score = float(np.mean(energy))+min(span, 18)*.021+random.uniform(0,.08)
            found.append((score, line, a, b, families))
    paths = []
    visited = []
    for _, line, a, b, families in sorted(found, key=lambda u: -u[0]):
        mid = line[len(line)//2]
        if any(np.linalg.norm(mid-prev) < 4.8 for prev in visited):
            continue
        visited.append(mid)
        paths.append(stroke(f"{key}/shared/{len(paths):03d}", line, "shared_canopy", key, key, layer=len(paths)%2,
                            features={"owners":[a,b], "families":families, "field":"shared growth tangents"}))
    return paths


def sample_crowd(path, field):
    xy=resample(path.xy,C["stroke_sample_mm"])
    crowd=field.crowded(xy)
    groups={}
    for p, ds, active in zip((xy[1:]+xy[:-1])*.5,np.linalg.norm(np.diff(xy,axis=0),axis=1),crowd[1:]|crowd[:-1]):
        if active:
            cell=tuple(np.floor(p/C["crowd_cell_mm"]).astype(int))
            groups[cell]=groups.get(cell,0.)+float(ds)
    return xy,crowd,groups


def filter_crowded(original, shared, field):
    """Limit ink in crowded cells and avoid sustained parallel double strokes."""
    candidates=[]
    old_totals={}
    for path in original:
        xy,crowd,groups=sample_crowd(path,field)
        score=path.length*.021+.65*(1-float(crowd.mean()))
        candidates.append((score,path,xy,crowd,groups))
        for cell,mm in groups.items():
            old_totals[cell]=old_totals.get(cell,0.)+mm
    if shared and max(old_totals.values(),default=0.)<=C["crowd_length_cap_mm"]:
        # A lightly connected crown needs only a few bridges.
        lines=[LineString(p.xy) for p in original]
        scored=[]
        for p in shared:
            line=LineString(p.xy)
            scored.append((sum(line.crosses(q) for q in lines),-p.length,p))
        shared=[p for _,_,p in sorted(scored,key=lambda v:v[:2])[:min(2,len(scored))]]
    for path in shared:
        xy,crowd,groups=sample_crowd(path,field)
        candidates.append((2.+path.length*.021,path,xy,crowd,groups))

    chosen=[]
    lengths={}
    points=[]
    for _, path, xy, crowd, groups in sorted(candidates,key=lambda a:-a[0]):
        if not np.any(crowd):
            chosen.append(path)
            continue
        if any(lengths.get(cell,0.)+mm>C["crowd_length_cap_mm"] for cell,mm in groups.items()):
            continue
        q=xy[crowd]
        if points:
            nearby=cKDTree(np.vstack(points)).query(q,k=1)[0]<C["near_parallel_mm"]
            if np.mean(nearby)>C["near_parallel_max_fraction"]:
                continue
        chosen.append(path)
        points.append(q)
        for cell,mm in groups.items():
            lengths[cell]=lengths.get(cell,0.)+mm
    return chosen,dict(crowd_cell_count=len(lengths),max_crowd_cell_length_mm=max(lengths.values(),default=0.))


def phase_schedule(paths, field):
    """Spread wet neighbors with limited Y lookahead and favour short moves."""
    scheduled=[]
    records=[(s,LineString(s.xy),field.crowded(resample(s.xy,1.25)).any()) for s in paths]
    for phase in ("INK_1","INK_2","INK_3","INK_4"):
        queue=sorted((r for r in records if r[0].phase==phase),key=lambda r:(r[1].bounds[1],r[0].id))
        recent=[]
        last=None
        while queue:
            choices=queue[:C["queue_lookahead"]]
            k=0
            if last is not None:
                start=choices[0][1].bounds[1]
                available=[(i,r) for i,r in enumerate(choices)
                           if all(x is None or r[1].distance(x)>=C["wet_neighbor_mm"] for x in recent)]
                if available:
                    k=min(available,key=lambda a:np.linalg.norm(np.asarray(a[1][0].xy[0])-last)
                          +1.55*(a[1][1].bounds[1]-start)+.16*a[0])[0]
            chosen,line,crowd=queue.pop(k)
            scheduled.append(chosen)
            last=np.asarray(chosen.xy[-1])
            recent.append(line if crowd else None)
            recent=recent[-C["wet_recent"]:]
    return scheduled


def integrated_cluster(key, base, width, depth, height, seed, families, layout="depth",
                       lod="mid", season="spring", seasonal=False):
    before, pads, meta = community(key, base, width, depth, height, seed, families, layout=layout,
                                   lod=lod, season=season, seasonal=seasonal)
    return integrate(key, before, pads, meta, seed, season)


def integrated_specimen(key, family, height, base, seed, lod="near", season="spring", seasonal=False):
    before, pads, m = specimen(key, family, height, base, lod=lod, seed=seed, season=season, seasonal=seasonal)
    return integrate(key, before, [(*p,key) for p in pads], {"specimens":[m]}, seed, season)


def integrate(key, before, pads, meta, seed, season="spring"):
    logs = meta["specimens"]
    field = CanopyField(pads, logs)
    old_canopy = [s for s in before if s.role=="canopy"]
    landmarks = [s for s in before if s.role!="canopy" and s.medium!="COLOR"]
    shared = bridge_strokes(key, field, seed)
    kept, audit = filter_crowded(old_canopy, shared, field)
    adjusted = []
    for s in kept:
        if s.role=="shared_canopy":
            values = field.density(s.xy)
            pressure = np.asarray(s.pressure_mm)*(1-.29*np.clip((values-.9)/1.2,0,1))
            s = replace(s,pressure_mm=pressure.round(6).tolist())
        adjusted.append(s)
    scheduled = phase_schedule(adjusted, field)
    combined = [s for p in ("INK_1","INK_2","INK_3","INK_4")
                for s in [*[t for t in landmarks if t.phase==p],*[t for t in scheduled if t.phase==p]]]
    return before, combined, field, dict(meta, season=season, lod=max((m["lod"] for m in logs),
              key=lambda k:{"far":0,"mid":1,"near":2}[k],default="mid"),
              integration=dict(audit,bridge_candidates=len(shared),
              shared_kept=sum(s.role=="shared_canopy" for s in kept),
              woody_kept=sum(s.role in WOODY for s in landmarks),
              original_canopy=len(old_canopy),scheduled_canopy=len(kept)))
