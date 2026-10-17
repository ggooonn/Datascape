"""Audit original arc geometry, deterministic traversal and footprint sensitivity."""
import json,gzip,copy
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,Polygon,Point
from shapely.ops import unary_union,substring
from datascape.rendering.spring_integration import resolve
from datascape.strokes.vector import read_vectors,resample,sample
from datascape.integration.visibility import digest,object_gate,clip_source
from datascape.strokes.scene import load_selected_scene
import argparse

def run(master,veg,config,output):
    out=Path(output);cp=Path(config).resolve();root=cp.parents[2]
    c=json.load(open(cp))
    baseline=read_vectors(root/c['baseline'])['strokes']
    fixed=load_selected_scene(master,veg,root,json.load(open(root/'configs/scenes/seoul_spring_selected_C.json')))
    corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']])
    report=dict(variants={},policy='Derived diagnostic validation; no production certification')
    for key in ['B','C']:
     print('Validate',key,flush=True)
     vectors=read_vectors(out/(key+'_vectors.json.gz'))['strokes']
     ledger=json.load(gzip.open(out/(key+'_sources_and_ledger.json.gz'),'rt'))
     sources={r['id']:r for r in baseline+ledger['new_sources']}
     assert len({r['id'] for r in vectors})==len(vectors)
     for r in vectors:
      p=np.asarray(r['xy_mm']);assert np.isfinite(p).all()
      for name in ['width_profile_mm','opacity_profile']:
       if name in r:assert len(r[name])==len(p)
      if 'intensity_samples' in r.get('expression',{}):assert len(r['expression']['intensity_samples'])==len(p)
      if r['origin_kind']=='new-catalog':assert LineString(p).length>=2.8-1e-7
      assert p[:,0].min()>=0 and p[:,0].max()<=600
      assert p[:,1].max()<898
      original=sources[r['source_stroke_id']];line=LineString(original['xy_mm'])
      aa,bb=r['source_arc_mm'];assert -1e-7<=aa<bb<=line.length+1e-7
      exact=substring(line,aa,bb)
      assert exact.hausdorff_distance(LineString(p))<1e-6
     for row in ledger['terrain_decisions']+ledger['object_decisions']:
      kept=sum(b-a for a,b in row['kept_intervals_mm'])
      assert abs(kept+row['removed_mm']-row['source_length_mm'])<1e-6
     # Reversed construction traversal on real, full scene geometry.
     reversed_config=copy.deepcopy(c);reversed_config['trees'].reverse();reversed_config['rocks'].reverse()
     print('Resolve reversed traversal',key,flush=True)
     reverse=resolve(fixed,baseline,reversed_config,key,corridor)
     reference=[{k:v for k,v in r.items() if k!='preview_palette_slot'} for r in vectors]
     assert digest(reverse['strokes'])==digest(reference)
     # Wider nominal footprints as a bounded diagnostic, using the same original
     # object sources and the same exact global/depth policy. No geometry reroll.
     actual_final=sum(LineString(r['xy_mm']).length for r in reverse['new'])
     normal=0.;widened=0.
     for obj in reverse['objects']:
      control=object_gate(fixed,obj,reverse['objects'])
      gate=object_gate(fixed,obj,reverse['objects'],footprint_extra_mm=.30)
      for source in obj['records']:
       original,_=clip_source(source,control)
       normal+=sum(LineString(r['xy_mm']).length for r in original)
       parts,_=clip_source(source,gate)
       widened+=sum(LineString(r['xy_mm']).length for r in parts)
     assert widened<=normal+1e-7
     report['variants'][key]=dict(unique_ids=True,profiles_aligned=True,original_arc_geometry_exact=True,
       length_conserved=True,canvas_bottom_guard=True,new_minimum_2_8mm=True,
       reversed_traversal_vectors_equal=True,actual_final_new_length_mm=actual_final,
       matched_visible_mask_control_mm=normal,
       wider_footprint_new_length_mm=widened,
       footprint_test='Same original sources/resolved masks, 0.30 mm widening; not measured wet ink')
     print('passed',key,flush=True)
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True);p.add_argument('--veg',required=True)
    p.add_argument('--config',default='configs/scenes/seoul_spring_integration_v01.json')
    p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
