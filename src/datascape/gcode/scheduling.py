"""Deterministic, constraint-aware distance heuristic, NOT global time optimization."""
from .models import Stroke


def schedule(strokes: tuple[Stroke,...]) -> tuple[Stroke,...]:
    indexed=list(enumerate(strokes))
    ordered=sorted(indexed,key=lambda k:(k[1].order_group,k[1].sequence,k[0]))
    out=[]
    last_xy=None
    idx=0
    while idx<len(ordered):
        _,first=ordered[idx]
        key=(first.order_group, first.sequence, first.medium, first.layer, first.color_slot)
        block=[]
        while idx<len(ordered):
            _,s=ordered[idx]
            if (s.order_group,s.sequence,s.medium,s.layer,s.color_slot)!=key:
                break
            block.append(s)
            idx+=1
        j=0
        while j<len(block):
            if not block[j].reorderable:
                s=block[j];out.append(s);last_xy=(s.points[-1].x,s.points[-1].y);j+=1
                continue
            pool=[]
            while j<len(block) and block[j].reorderable:
                pool.append(block[j]);j+=1
            if last_xy is None:
                out.extend(pool);last_xy=(pool[-1].points[-1].x,pool[-1].points[-1].y);continue
            while pool:
                choices=[]
                for n,s in enumerate(pool):
                    start=s.points[0];end=s.points[-1]
                    ds=(start.x-last_xy[0])**2+(start.y-last_xy[1])**2
                    choices.append((ds,n,False))
                    if s.reversible:
                        de=(end.x-last_xy[0])**2+(end.y-last_xy[1])**2
                        choices.append((de,n,True))
                _,n,rev=min(choices)
                chosen=pool.pop(n)
                if rev:
                    chosen=Stroke(stroke_id=chosen.stroke_id,source_id=chosen.source_id,
                                  points=tuple(reversed(chosen.points)),layer=chosen.layer,
                                  color_slot=chosen.color_slot,medium=chosen.medium,
                                  order_group=chosen.order_group,sequence=chosen.sequence,
                                  reorderable=True,reversible=True)
                out.append(chosen)
                last_xy=(chosen.points[-1].x,chosen.points[-1].y)
    return tuple(out)
