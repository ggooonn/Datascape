"""Seeded schematic foreground marks; not a tree inventory or plotter output."""
import hashlib
import numpy as np
from PIL import Image,ImageDraw


def place_plants(fields,config):
    """Sample one common set for B/C; C omits/attenuates these same marks."""
    v=fields['vegetation_before'];h,w=v.shape;pc=config['plants']
    candidates=np.flatnonzero(v>=pc['minimum_field'])
    if not len(candidates):return []
    probability=v.ravel()[candidates];probability/=probability.sum()
    rng=np.random.default_rng(np.random.SeedSequence([config['seed'],202]))
    glyph_rng=np.random.default_rng(np.random.SeedSequence([config['seed'],303]))
    roots=[];plants=[];spacing=pc['minimum_spacing_mm']*w/600
    for index in rng.choice(candidates,size=pc['maximum_proposals'],p=probability):
        row,col=divmod(int(index),w);root=np.array([col+.5,row+.5])
        if any(np.linalg.norm(root-old)<spacing for old in roots):continue
        xyz=fields['xyz'][row,col];q=fields['depth_m'][row,col]
        height=float(glyph_rng.uniform(*pc['height_mm'])*np.clip(1-q/2200,.5,1))
        height_px=height*h/900;lean=float(glyph_rng.uniform(-.17,.17))*height_px
        trunk=np.array([root,root+[-lean*.15,-height_px*.45],root+[lean,-height_px]])
        lines=[trunk.tolist()]
        # Deliberately generic branching strokes: no species or observed tree.
        for t in [.30,.46,.62,.78,.89]:
            origin=root+np.array([lean*t,-height_px*t])
            span=height_px*(1-t)*float(glyph_rng.uniform(.35,.55))
            for side in [-1,1]:
                endpoint=origin+np.array([side*span,-span*.42])
                lines.append(np.array([origin,(origin+endpoint)/2+[0,-span*.16],endpoint]).tolist())
                lines.append(np.array([endpoint-[side*span*.15,-span*.25],endpoint,endpoint+[side*span*.1,-span*.18]]).tolist())
        thinning=float(rng.random());retention=float(fields['vegetation_retention'][row,col])
        identity=hashlib.sha256(f'{config["seed"]}:{xyz[0]:.3f}:{xyz[1]:.3f}'.encode()).hexdigest()[:16]
        plants.append({'id':identity,'root_pixel_xy':root.tolist(),'source_xyz_m':xyz.tolist(),
            'forward_depth_m':float(q),'ndvi':float(fields['current_ndvi'][row,col]),
            'effective_observations':float(fields['current_observations'][row,col]),
            'slope_deg':float(fields['slope_deg'][row,col]),'aspect_deg':float(fields['aspect_deg'][row,col]),
            'field_before':float(v[row,col]),'retention_at_root':retention,'thinning_uniform':thinning,
            'keep_C':bool(thinning<retention),'height_mm':height,'polylines_pixel_xy':lines})
        roots.append(root)
        if len(plants)>=pc['maximum_count']:break
    return plants


def plant_coverage(plants,width,height,line_width_mm,variant='B'):
    """Rasterize schematic black mark coverage, without a white paint pass."""
    canvas=Image.new('L',(width,height),0);draw=ImageDraw.Draw(canvas)
    line_width=max(1,round(line_width_mm*width/600))
    for plant in plants:
        if variant=='C' and not plant['keep_C']:continue
        for line in plant['polylines_pixel_xy']:
            draw.line([tuple(p) for p in line],fill=210,width=line_width)
    return np.asarray(canvas,dtype=float)/255


def combine_ink(shade,plant_B,plant_C,fields):
    """Add mark coverage in B; attenuate contributions before compositing C.

    Continuous density attenuation is a preview proxy for future thinning of
    strokes/layers. Hard reserve has exactly zero terrain and plant coverage.
    """
    terrain=np.clip(1-shade,0,1)
    b_ink=1-(1-terrain)*(1-plant_B)
    c_terrain=terrain*fields['terrain_retention']
    c_plants=plant_C*fields['vegetation_retention']
    c_plants[fields['reserve']]=0;c_terrain[fields['reserve']]=0
    c_ink=1-(1-c_terrain)*(1-c_plants)
    return {'A':shade.copy(),'B':1-b_ink,'C':1-c_ink,
            'terrain_ink_C':c_terrain,'plant_ink_C':c_plants}
