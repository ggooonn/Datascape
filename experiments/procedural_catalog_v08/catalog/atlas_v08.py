"""Regenerate a thematic selection from the previous procedural catalogs."""
import importlib
import json

from .geometry import ROOT
from .render import export_png,svg_sheet

INDEX=json.loads((ROOT/"config/atlas_v08.json").read_text())


def build():
    folder=ROOT/"atlas"
    folder.mkdir(exist_ok=True)
    for version in sorted({row[1] for row in INDEX}):
        suffix=f"v{version:02}"
        source=importlib.import_module(f".sheets_{suffix}",__package__)
        if version==1:
            renderer=svg_sheet
        else:
            renderer=importlib.import_module(f".catalog_{suffix}",__package__).plate
        sheets={getattr(s,"key",getattr(s,"id",None)):s for s in source.assemble()}
        for _,v,key,_ in INDEX:
            if v==version:
                file=folder/f"{suffix}_{key}.svg"
                file.write_text(renderer(sheets[key]),encoding="utf-8")
                export_png(file,file.with_suffix(".png"))
        print(suffix,flush=True)


if __name__=="__main__":
    build()
