"""Extract actual local transfers and unresolved material operations for review."""
import gzip,json
from pathlib import Path
from datascape.gcode.production.trajectory import Command


def generate(root):
    root=Path(root);lines=[]
    for name in ('SHARED_INK','SHARED_COLOR'):
        with gzip.open(root/(name+'.trajectory.jsonl.gz'),'rt') as f:
            commands=[Command(**c) for c in map(json.loads,f)]
        links=json.loads(gzip.decompress((root/(name+'.transitions.json.gz')).read_bytes()))
        link=next(x for x in links if x['eligible_without_clearance'] and x['distance_mm']<=10)
        sample=commands[max(0,link['previous_retract_index']-2):max(link['entry_indices'])+5]
        lines.append('; '+name+' ACTUAL LOCAL TRANSFER EXCERPT; gap '+str(link['distance_mm'])+' mm; REVIEW ONLY')
        for c in sample:
            lines.append('; '+c.action+' source='+str(c.source_id)+' accepted_pressure='+str(c.artistic_pressure))
            if c.kind=='move':lines.append('; G1 '+' '.join(k+f'{v:.9f}' for k,v in zip('XYZ',c.xyz))+f' F{c.feed_mm_min:.9f}')
        for action in ('wash','absorbent_contact','controlled_rewet','same_material_reload'):
            c=next((x for x in commands if x.kind=='unresolved' and x.action==action),None)
            if c:lines.append('; UNRESOLVED '+c.action+' '+c.message)
        lines+=['; G1 X800.000000000 Y900.000000000 Z32.000000000 ; nominal final park, reachability unverified','; M2']
    (root/'FOCUSED_EXAMPLES.txt').write_text('\n'.join(lines)+'\n')
