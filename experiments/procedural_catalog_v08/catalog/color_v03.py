"""Color passes following shared crown direction and native projected surface domains."""
from dataclasses import replace
import numpy as np
from shapely.geometry import LineString, Point

from .canopy_v03 import V03, split_sampled
from .geometry import poly_parts, resample, rng, stroke


def tint(s, factor):
    return replace(s,pressure_mm=(np.asarray(s.pressure_mm)*factor).round(6).tolist())


def project_clip(s, region, minimum, tag, inside=False):
    """Preserve material, pressure profile and direction through a screen-space cut."""
    line = LineString(s.xy)
    if inside and region.covers(line) or not inside and not region.intersects(line):
        return [s]
    shape = line.intersection(region) if inside else line.difference(region)
    distances = np.r_[0,np.cumsum(np.linalg.norm(np.diff(s.xy,axis=0),axis=1))]
    output = []
    for i,q in enumerate(poly_parts(shape,minimum)):
        positions = np.array([line.project(Point(p)) for p in q])
        if positions[0]>positions[-1]:
            q,positions=q[::-1],positions[::-1]
        pressure = np.interp(positions,distances,s.pressure_mm)
        taper = np.clip(np.minimum(positions-positions[0],positions[-1]-positions)/1.8,.55,1)
        output.append(replace(s,id=f"{s.id}/{tag}/{i}",xy=q.tolist(),
                              pressure_mm=(pressure*taper).round(6).tolist(),
                              features=dict(s.features,source=s.id)))
    return output


def follow_growth(field, points, y0, phase):
    """Integrate a bounded flow inside one lobe; softly restore separation between passes."""
    center = len(points)//2
    x,y = points[center]
    output=[None]*len(points)
    output[center]=points[center]
    for sign in (-1,1):
        py=y
        direction=range(center+sign,-1 if sign<0 else len(points),sign)
        for j in direction:
            target=points[j,0]
            flow=field.flow([[target,py]])[0]
            slope=np.clip(.98*flow+.093*(y0-py)+.07*np.cos(target*.23+phase),-.50,.50)
            py+=float(target-points[j-sign,0])*slope
            output[j]=[target,py]
    return np.asarray(output)


def vegetation_color(key, field, season, lod, seed):
    """Use one directional color field over the full cluster, preserving open pockets."""
    if not field.owners:
        return []
    cfg = V03["vegetation_color"]
    step = cfg["spacing_mm"][lod]
    inside=cfg["winter_inside_level"] if season=="winter" else cfg["inside_level"]
    min_segment=cfg["winter_min_mm"] if season=="winter" else cfg["min_segment_mm"]
    palette = V03["color"][f"vegetation_{season}"]
    random = rng("cluster color v03", key, seed)
    x = np.linspace(field.origin[0], field.end[0], max(8,int(field.end[0]-field.origin[0])+1))
    result = []
    height = field.end[1]-field.origin[1]
    y0 = field.origin[1] + step*.28
    for layer in range(2 if lod!="far" and season!="winter" else 1):
        y = y0 + (step*.76 if layer else 0)
        row = 0
        while y < field.end[1]:
            phase = random.uniform(-np.pi,np.pi)
            nominal = np.c_[x,y+(.36+.42*random.random())*np.sin((x-x[0])*.12+phase)]
            mid_y = (y-field.origin[1])/max(height,1)
            support=field.density(nominal)>=inside-.27
            runs=[]
            for seedline in split_sampled(nominal,support,min_segment*.74):
                path=resample(follow_growth(field,seedline,y,phase),.78)
                density = field.density(path)
                core = field.crowded(path)
                edge = density + .11*np.sin(path[:,0]*.39 + row*.71)+.12*np.sin(path[:,1]*.54)
                keep = edge >= inside
                if layer:
                    keep &= core & (edge >= cfg["shadow_level"])
                    keep &= np.sin(path[:,0]*.16 + y*.17)>-.28
                runs.extend(split_sampled(path,keep,min_segment))
            for i,q in enumerate(runs):
                value = field.density(q)
                factor = np.interp(value,[inside,2.1],cfg["relative_pressure"])
                tone = 1 if layer else 2 if mid_y<.42 and (row+i)%3==0 else 0
                p=stroke(f"{key}/crown_color/{layer}.{row}.{i}",q,"vegetation_color",key,key,
                         pigment=palette[tone],features={"layer":layer,"tone":tone,"season":season,
                         "shared_fraction":round(float(field.crowded(q).mean()),3)})
                result.append(tint(p,factor*(.83 if season=="winter" else 1.)))
            y += step*random.uniform(.82,1.31)*(2.32 if layer else 1)
            row += 1
    return sorted(result,key=lambda p:(p.features["layer"],p.features["tone"]))
