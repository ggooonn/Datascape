"""Compare path geometry and plotting proxies in physical drawing mm."""
from collections import Counter
import numpy as np
from shapely.geometry import LineString
from shapely.strtree import STRtree

from .canopy_v03 import C
from .geometry import resample


def path_audit(paths, spacing=3.2):
    materials = {}
    for material in ("LIGHT_INK","MEDIUM_INK","COLOR"):
        runs = [s for s in paths if s.medium==material]
        materials[material] = dict(paths=len(runs),mm=round(sum(s.length for s in runs),2),
                                   pigments=dict(Counter(s.pigment for s in runs if s.pigment)))
    turns=[]
    for path in paths:
        xy = resample(path.xy, .95)
        v = np.diff(xy,axis=0)
        unit=v/np.maximum(np.linalg.norm(v,axis=1)[:,None],1e-10)
        dots=np.sum(unit[:-1]*unit[1:],axis=1)
        turns.extend(np.rad2deg(np.arccos(np.clip(dots,-1,1))))
    adjacent=0
    travel=0.
    batches={}
    for p in paths:
        batches.setdefault((p.phase,p.pigment),[]).append(p)
    for seq in batches.values():
        for a,b in zip(seq,seq[1:]):
            travel+=np.linalg.norm(np.asarray(a.xy[-1])-b.xy[0])
            adjacent+=LineString(a.xy).distance(LineString(b.xy))<spacing
    return dict(paths=len(paths),mm=round(sum(s.length for s in paths),2),materials=materials,
                short_under_6mm=sum(s.length<6 for s in paths),
                middle_mm=round(float(np.median([s.length for s in paths])),2) if paths else 0.,
                vertices=sum(len(s.xy) for s in paths),
                turn_p95_deg=round(float(np.percentile(turns,95)),2) if turns else 0.,
                interpath_air_mm=round(float(travel),2),same_phase_neighbor_pairs=adjacent)


def canopy_audit(paths, field):
    crown=[s for s in paths if s.role in {"canopy","shared_canopy"}]
    lines=[LineString(s.xy) for s in crown]
    pairs=STRtree(lines).query(lines,predicate="crosses") if lines else np.empty((2,0))
    crossing=int(np.sum(pairs[0]<pairs[1]))
    length_samples={}
    crowded_paths={}
    for s in crown:
        xy=resample(s.xy,C["stroke_sample_mm"])
        crowd=field.crowded(xy)
        if crowd.any():
            crowded_paths[s.id]=LineString(s.xy)
        for p,ds,active in zip((xy[1:]+xy[:-1])*.5,np.linalg.norm(np.diff(xy,axis=0),axis=1),crowd[1:]|crowd[:-1]):
            if active:
                cell=tuple(np.floor(p/C["crowd_cell_mm"]).astype(int))
                length_samples[cell]=length_samples.get(cell,0.)+ds
    for_phase={}
    for s in crown:
        for_phase.setdefault(s.phase,[]).append(s)
    def wet(seq):
        return sum(a.id in crowded_paths and b.id in crowded_paths and
                   crowded_paths[a.id].distance(crowded_paths[b.id])<C["wet_neighbor_mm"]
                   for a,b in zip(seq,seq[1:]))
    starts=lambda s:(min(p[1] for p in s.xy),s.id)
    ordered=sum(wet(seq) for seq in for_phase.values())
    plain=sum(wet(sorted(seq,key=starts)) for seq in for_phase.values())
    shared=[s for s in crown if s.role=="shared_canopy"]
    return dict(canopy_paths=len(crown),shared_paths=len(shared),
                canopy_mm=round(sum(s.length for s in crown),2),crossing_pairs=crossing,
                overlap_cell_max_mm=round(float(max(length_samples.values(),default=0.)),2),
                overlap_cell_p90_mm=round(float(np.percentile(list(length_samples.values()),90)),2) if length_samples else 0.,
                baseline_y_near_pairs=plain,scheduled_near_pairs=ordered,
                shared_color_paths=sum(s.role=="vegetation_color" and s.features["shared_fraction"]>=.30 for s in paths))
