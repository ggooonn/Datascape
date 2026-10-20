"""Verify outputs of PR25's adapter; never regenerate or substitute pressure.

Spring-specific pins live at this integration boundary, not in motion modules.
"""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from .io import load_strokes

PRESSURE_COMMIT='d30ac7be302e1cbfcd2cf66de9087e35ea091b6c'
SPRING_COMMIT='67ba146b1213644d40bc9dabed9d52024d2bbe58'
SIDECAR_SHA='0b8d59b7ca9268c70378b7a78df3f8825763b2b43e5667785459b2838d2b0b4e'
PAYLOAD_SHA='6586df2ea3c48ee45de7df10926a2845172f39203ec805f61724f0c7e504ff2b'
PROVENANCE_SHA='c8baa3e46ce773a8752f488c889dc422e34d2ab9ba0ee87582efd9126c7e88d4'


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def bind_with_accepted_adapter(checkout, machine_path, provenance_path, backend_directory):
    """Run the EXISTING adapter in a separate pinned, read-only source checkout."""
    import os
    root=Path(checkout).resolve()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if sha != PRESSURE_COMMIT: raise ValueError('pressure source must be the exact pinned checkout')
    # Adapter validates canonical input bytes and refuses existing/protected output.
    env=dict(os.environ,PYTHONPATH=str(root/'src'))
    subprocess.run([sys.executable,'-m','datascape.spring_pressure_intent',
                    '--output',str(Path(machine_path).resolve()),
                    '--provenance',str(Path(provenance_path).resolve()),
                    '--backend-directory',str(Path(backend_directory).resolve())],
                   cwd=root,env=env,check=True)


def load_bound_spring(machine_path, provenance_path):
    obj=json.loads(Path(machine_path).read_text())
    provenance=json.loads(Path(provenance_path).read_text())
    core={k:v for k,v in provenance.items() if k!='backend_check'}
    if digest(obj)!=PAYLOAD_SHA or digest(core)!=PROVENANCE_SHA:
        raise ValueError('canonical bound machine/provenance checksum mismatch; rerun PR25 adapter')
    strokes=load_strokes(machine_path)
    if len(strokes)!=14951 or sum(len(s.points) for s in strokes)!=240974:
        raise ValueError('Spring completeness mismatch')
    if provenance['pressure_sidecar_sha256']!=SIDECAR_SHA or provenance['fallback_permitted'] is not False:
        raise ValueError('unapproved pressure provenance')
    for s,binding in zip(strokes,provenance['per_stroke']):
        if s.stroke_id!=binding['stroke_id'] or s.sequence!=binding['sequence'] or s.reorderable or s.reversible:
            raise ValueError('source order or direction mismatch')
    return tuple(replace(s,pressure_sidecar_sha256=SIDECAR_SHA) for s in strokes),provenance
