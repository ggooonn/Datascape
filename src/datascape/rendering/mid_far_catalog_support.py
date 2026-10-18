"""Small review helpers extracted without geometry changes from v03-v05."""
from copy import deepcopy
import html
import numpy as np
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from datascape.integration.visibility import burn
from datascape.vegetation.mid_far import digest, resample
from datascape.vegetation.territorial_mid_far_v04 import generate, visibility, vegetation_overlap, colorize


def footprint_metrics(records,width=.8,gap=.5):
    groups={}
    for r in records:
        if r['grammar_part']!='directional-foliage':continue
        groups.setdefault(r['unit_id'],[]).append(LineString(r['xy_mm']))
    shapes=[unary_union(v) for v in groups.values()]
    nearest=[min([s.distance(other) for j,other in enumerate(shapes) if j!=i],default=1e6) for i,s in enumerate(shapes)]
    return dict(units=len(shapes),minimum_interunit_centerline_mm=min(nearest,default=None),
        footprint_mm=width,desired_free_gap_mm=gap,
        units_below_requested_clearance=sum(d<width+gap for d in nearest),
        unit_join_policy='Within-unit ray merging is intentional; cross-unit ink spacing only, not cross-channel calibration')

def geometry_digest(rows):
    return digest([{k:r[k] for k in ['id','xy_mm','owner_id','source_forward_m','source_arc_mm','width_mm','width_profile_mm'] if k in r} for r in rows])

def occupation(case,bounds,evidence):
    roots=np.array([s['root_xy_mm'] for s in case['sites']]);rootmask=np.zeros((900,600),bool)
    for p in roots:rootmask|=burn(Point(p).buffer(5.))
    domain=burn(box(*bounds))&evidence.occupied&(evidence.protected_clearance>1.4)
    nn=[min(np.linalg.norm(p-roots[j]) for j in range(len(roots)) if i!=j) for i,p in enumerate(roots)] if len(roots)>1 else []
    tile=np.zeros((90,60),bool)
    for r in case['color']:
        p=resample(r['xy_mm'],1.);x=np.clip((p[:,0]/10).astype(int),0,59);y=np.clip((p[:,1]/10).astype(int),0,89);tile[y,x]=True
    xmin,ymin,xmax,ymax=bounds
    valid_tiles=np.zeros_like(tile)
    for y in range(max(0,int(ymin//10)),min(90,int(np.ceil(ymax/10)))):
        for x in range(max(0,int(xmin//10)),min(60,int(np.ceil(xmax/10)))):
            valid_tiles[y,x]=bool(domain[y*10:(y+1)*10,x*10:(x+1)*10].any())
    return dict(territorial_root_5mm_support_fraction=float((rootmask&domain).sum()/max(1,domain.sum())),
        territorial_10mm_tiles_with_visible_color_fraction=float((tile&valid_tiles).sum()/max(1,valid_tiles.sum())),
        cluster_root_nearest_p10_p50_p90_mm=np.quantile(nn,[.1,.5,.9]).tolist() if nn else [],
        raw_foliage_paths_per_supported_body=len(case['raw_color'])/max(1,len(roots)),
        visible_foliage_paths_per_supported_body=len(case['color'])/max(1,len(roots)),
        support_radius_mm=5.,eligible_crop_cells=int(domain.sum()),
        note='Authored root support and coarse occupied tiles, not measured canopy cover or stem density')

def make_case(sites,mode,family,config,evidence):
    graphs,ri,rc,links=generate(sites,mode,family,config)
    vi,li=visibility(ri,evidence,config);vc,lc=visibility(rc,evidence,config)
    ink,color,lo=vegetation_overlap(vi,vc,config)
    return dict(sites=sites,graphs=graphs,raw_ink=ri,raw_color=rc,ink=ink,color=colorize(color,config),
        links=links,visibility_ledger=li+lc,overlap_ledger=lo)

def fixed_scene(baseline,oldink,oldcolor,config):
    replaced=set()
    for r in oldink:
        if r.get('source_family')!='tree':continue
        xy=r.get('source_root_xy_mm')
        if xy and any(box(*b['bounds_mm']).covers(Point(xy)) for b in config['regions'].values()):replaced.add(r['owner_id'])
    objects=[r for r in oldink if r.get('source_family') in ['tree','rock','Soil'] and r.get('owner_id') not in replaced]
    terrain=[r for r in baseline if r['layer'] in ['A','B','D']]
    color=[r for r in oldcolor['caseC'] if r.get('owner_id') not in replaced and r.get('catalog_object_id') not in replaced]
    return terrain+objects,color,sorted(replaced)

def preview_svg(ink,color,palette,bounds=(0,0,600,900)):
    x0,y0,x1,y1=bounds
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{x1-x0}mm" height="{y1-y0}mm" viewBox="{x0} {y0} {x1-x0} {y1-y0}">',
        '<title>Artwork millimeters; experimental dots require physical contact calibration</title>',
        f'<defs><clipPath id="crop"><rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}"/></clipPath></defs><g clip-path="url(#crop)" fill="none" stroke-linecap="round" stroke-linejoin="round">']
    for rows,col in [(ink,False),(color,True)]:
        for r in rows:
            rgb=palette['slots'][r['palette_slot']]['preview_hex'] if col else '#101812';a=float(np.mean(r.get('opacity_profile',[r.get('preview_opacity',1.)])))
            p=r['xy_mm'];ident=html.escape(r['id'],quote=True)
            if r.get('primitive')=='tap':parts.append(f'<circle cx="{p[0][0]}" cy="{p[0][1]}" r="{r["diameter_mm"]/2}" fill="{rgb}" stroke="none" opacity="{a}" data-source="{ident}"/>')
            else:
                d='M'+' L'.join(f'{x:.5f},{y:.5f}' for x,y in p);width=float(np.mean(r.get('width_profile_mm',[r.get('width_mm',.3)])))
                parts.append(f'<path d="{d}" stroke="{rgb}" stroke-width="{width}" opacity="{a}" data-source="{ident}"/>')
    parts.append('</g></svg>');return '\n'.join(parts)
