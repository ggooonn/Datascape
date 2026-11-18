"""Enrich ground dabs around the exact v07 contacts and masks."""
from dataclasses import replace
import json

import numpy as np
from shapely.geometry import LineString

from .color_v03 import project_clip,tint
from .geometry import ROOT,rng
from .ground_attachment_v07 import G,ground_patches

V08=json.loads((ROOT/"config/catalog_v08.json").read_text())


def enrich(key,contacts,frame,solid,seed,preset="checkpoint"):
    setting=V08["ground_presets"][preset]
    baseline,draft,_,audit=ground_patches(key,contacts,frame,solid,seed)
    visible={c.key for c in contacts if c.visible}
    draft=[p for p in draft if p.features["anchors"][0] in visible]
    mask=solid.buffer(.24)
    limit=int(len(baseline)*setting["density"])
    owners=set()
    kept=[]
    centerlines=[]
    for extra in (False,True):
        for source in sorted(draft,key=lambda p:(p.features["row"],p.id)):
            random=rng("ground enrichment v08",seed,source.id)
            x,y=np.asarray(source.xy,float).T
            cx,_=source.features["projected_contact"]
            # Stretch around the original attachment. Interleave lighter passes with separate spacing.
            x=cx+(x-cx)*(setting["stretch"]-random.uniform(0,.029) if extra else setting["stretch"])
            if extra:
                x+=random.uniform(-.74,.74)
                y+=random.uniform(1.25,1.82)
            item=replace(source,id=f"{source.id}/{'extra' if extra else 'wide'}",
                         xy=np.column_stack((x,y)).tolist(),
                         features=dict(source.features,preset=preset,secondary=extra))
            if extra:
                item=tint(item,.71)
            for q in project_clip(item,mask,G["min_path_mm"],"masked"):
                line=LineString(q.xy)
                owner=q.features["anchors"][0]
                # Retain each first eligible contact stripe and reject sustained overlap of secondary rows.
                if (extra or owner in owners) and any(
                    line.intersection(p.buffer(.76)).length>.59*line.length for p in centerlines
                ):
                    continue
                if len(kept)<limit:
                    kept.append(q)
                    centerlines.append(line)
                    owners.add(owner)
    return kept,dict(audit,preset=preset,stretch=setting["stretch"],density_cap=setting["density"],
                     baseline_count=len(baseline),baseline_mm=sum(p.length for p in baseline),
                     v08_count=len(kept),v08_mm=sum(p.length for p in kept))
