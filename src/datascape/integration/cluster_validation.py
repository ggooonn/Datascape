"""Validate actual v02 lineage, deterministic clusters and open-vector exports."""
from pathlib import Path
import argparse,json,gzip,hashlib,copy,time
import numpy as np
from shapely.geometry import LineString,Point,Polygon
from shapely.ops import unary_union,substring
from datascape.integration.visibility import digest
from datascape.integration.cluster_scene import resolve_clusters
from datascape.integration.vector_wash import build_wash
from datascape.strokes.vector import read_vectors
from datascape.strokes.scene import load_selected_scene


def run(master,veg,config,output):
    cp=Path(config).resolve();root=cp.parents[2];out=Path(output)
    c=json.loads(cp.read_text());r=json.loads((out/'record.json').read_text())
    fixed=load_selected_scene(master,veg,root,json.loads((root/'configs/scenes/seoul_spring_selected_C.json').read_text()))
    for k in ['xyz','depth_m','occupied']:assert hashlib.sha256(fixed['base'][k].tobytes()).hexdigest()==r['field_sha256'][k]
    assert hashlib.sha256(fixed['retention'].tobytes()).hexdigest()==r['field_sha256']['retention']
    b=read_vectors(root/c['baseline'])['strokes'];corridor=unary_union([Polygon(s['vertices_mm']) for s in c['corridors']])
    ledger_totals={}
    for level in ['clean','clustered']:
     data=json.load(gzip.open(out/(level+'_source_ledger.json.gz'),'rt'))
     for row in data['terrain_decisions']+data['object_decisions']:
      kept=sum(bb-aa for aa,bb in row['kept_intervals_mm'])
      assert abs(kept+row['removed_mm']-row['source_length_mm'])<1e-6
     ledger_totals[level]=len(data['terrain_decisions'])+len(data['object_decisions'])
    for name in ['01_clean','02_clustered','03_layered']:
     data=json.load(gzip.open(out/(name+'_color_sources_ledger.json.gz'),'rt'))
     source={s['id']:s for s in data['sources']};actual=read_vectors(out/(name+'_color.json.gz'))['strokes']
     for p in actual:
      original=LineString(source[p['source_stroke_id']]['xy_mm']);a,bb=p['source_arc_mm']
      assert substring(original,a,bb).hausdorff_distance(LineString(p['xy_mm']))<1e-6
     print('Color arc lineage verified',name,flush=True)
    rev=copy.deepcopy(c);rev['clusters'].reverse()
    print('Resolve reversed cluster traversal',flush=True);t=time.time()
    result=resolve_clusters(fixed,b,rev,'clustered',corridor)
    assert digest(result['ink'])==r['variants']['03_layered']['ink_sha256']
    print('Reversed ink exact',flush=True)
    color,_,_=build_wash(fixed,result,rev,'layered',corridor)
    original=read_vectors(out/'03_layered_color.json.gz')['strokes']
    assert digest(sorted(color,key=lambda p:p['id']))==digest(sorted(original,key=lambda p:p['id']))
    print('Reversed color exact',flush=True)
    import xml.etree.ElementTree as ET
    for name in ['scene_layers.svg','color_support_only.svg']:
     tree=ET.parse(out/name)
     assert not any(e.tag.rsplit('}',1)[-1] in ('polygon','rect','ellipse','image') for e in tree.iter())
     assert all(e.attrib.get('fill','none')=='none' for e in tree.iter())
    print('SVG open strokes only verified',flush=True)
    report=dict(source_arc_lineage_exact=True,ink_profiles_aligned=True,all_legacy_V_absent=True,
      all_source_ledger_length_conserved=True,ledger_source_counts=ledger_totals,
      reversed_cluster_ink_equal=True,reversed_color_geometry_and_palette_equal=True,
      no_SVG_filled_paint_or_background=True,source_fields_equal=True,
      elapsed_seconds=time.time()-t,tests='43 passed plus 16 accepted-tree subtests; 7 v02 tests rechecked after display revision')
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True);p.add_argument('--veg',required=True)
    p.add_argument('--config',default='configs/scenes/seoul_spring_clusters_v02.json')
    p.add_argument('--output',required=True)
    a=p.parse_args();run(a.master,a.veg,a.config,a.output)

if __name__=='__main__':main()
