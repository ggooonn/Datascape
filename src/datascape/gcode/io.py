"""Strict JSON input contract for approved artwork centerlines."""
import json
from pathlib import Path
from .models import Point,Stroke


def load_strokes(path: str | Path) -> tuple[Stroke,...]:
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if obj.get('schema')!='datascape.machine_vectors.v0.1':
        raise ValueError('unknown machine vector schema')
    if obj.get('artwork_size_mm')!=[600,900]:
        raise ValueError('expected continuous 600x900 mm artwork')
    strokes=[]
    ids=set()
    for record in obj['strokes']:
        for p in record['points']:
            if any(type(p.get(k)) not in (int,float) for k in ('x','y','pressure')):
                raise ValueError('explicit finite numeric XY and pressure required')
        if any(type(record.get(k,False)) is not bool for k in ('reorderable','reversible')):
            raise ValueError('ordering locks must be booleans')
        pts=tuple(Point(float(p['x']),float(p['y']),float(p['pressure'])) for p in record['points'])
        s=Stroke(stroke_id=record['stroke_id'],points=pts,
                 layer=record['layer'],color_slot=record['color_slot'],medium=record['medium'],
                 order_group=int(record.get('order_group',0)),sequence=int(record.get('sequence',0)),
                 reorderable=record.get('reorderable',False),reversible=record.get('reversible',False))
        if s.stroke_id in ids:raise ValueError(f'duplicate stroke ID: {s.stroke_id}')
        ids.add(s.stroke_id)
        strokes.append(s)
    return tuple(strokes)
