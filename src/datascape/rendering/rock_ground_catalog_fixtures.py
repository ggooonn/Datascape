"""The accepted v04 shared-ground comparison fixture, without historical runners."""
from shapely.geometry import LineString,box
from shapely.ops import unary_union
from shapely import affinity
from datascape.ground.grammar import path_record
from datascape.ground.structure_v02 import StructuralField,make_mass
from datascape.ground.surface_ground_v02 import ground_source
from datascape.ground.refinement_v03 import rhythm
from datascape.ground.patch_system_v04 import patch_system,distribution_cases
from datascape.ground.interaction import plan,replacement_intervals,Corridor
from datascape.rendering.rock_ground_catalog_support import tree_fixture,body_regions,_paths

def shared_ground_fixture():
    soil_masses=[make_mass('patch-scene/parent',StructuralField('patch-scene/field','layered',-12,5,(0,0),.6,1.2),anchor=(57,84),width=70,height=48,form='angular',burial=.25,depth=3.),
                 make_mass('patch-scene/medium',StructuralField('patch-scene/field','rounded',77,7,(0,0),.6,1.2,local_rotation_deg=5),anchor=(108,95),width=25,height=19,form='compact',burial=.2,depth=2.8),
                 make_mass('patch-scene/stone',anchor=(131,95),width=14,height=11,form='angular',burial=.3,depth=2.6),
                 make_mass('patch-scene/fragment',anchor=(145,99),width=8,height=6,form='compact',burial=.4,depth=2.4)]
    for m in soil_masses:m.surface.paths,_=rhythm(m.surface.paths,'interruption',structural_gaps=[g['geometry'] for g in m.gaps if g['reason'].startswith('fracture')])
    _,tree,tr,meta=tree_fixture(root=(22,77),height=45,identity='v04/patch-tree',depth=2.2)
    ac=ground_source(184,'v04/patch-AC',base_y=89);host=ac[2];cross=next(p for p in ac if p['grammar_part']=='C-like')
    contact=path_record('v04/protected-ground',[(15,79.3),(22,79),(24,79.3)],'v04/contact','protected-root-support',.6,4.5,'terrain-ink')
    fixed=ac+tree+_paths(soil_masses)+[contact]
    corridor=Corridor('v04/open-corridor',box(153,61,165,108))
    key,label,specs,c,white=next(row for row in distribution_cases() if row[0]=='shared')
    white=affinity.translate(white,yoff=-8) if white is not None else None
    g=patch_system('v04/soil',host,specs,c,corridor,white,cross_flow_record=cross)
    case_corridor=Corridor(corridor.identity+'/'+key,corridor.geometry.union(white) if white is not None else corridor.geometry)
    rep=replacement_intervals(ac,g.surface.support.buffer(.5))
    for p in fixed+g.surface.paths:
        if p['layer']=='rock-ink':p['assumed_footprint_mm']=max(.6,p['width_mm'])
    final,audit=plan(fixed+g.surface.paths,[*body_regions(soil_masses),*tr],case_corridor,rep,protected={contact['id']:[[0,LineString(contact['xy_mm']).length]]})
    g.pigment_support=g.pigment_support.difference(unary_union([r.geometry for r in [*body_regions(soil_masses),*tr] if r.role=='opaque-body']))
    return g,soil_masses,case_corridor,fixed+g.surface.paths,final,meta
