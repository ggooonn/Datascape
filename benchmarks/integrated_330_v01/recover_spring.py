"""Restore exact canonical backend inputs from pinned PR25 binding resources.

Calls the original, byte-verified apply_profiles adapter; never synthesizes
artwork or pressure. Unused terrain/render archives are not claimed verified.
Final machine/provenance must match the backend's existing canonical SHA256s.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json

from datascape.gcode.binding import (digest,load_bound_spring,PAYLOAD_SHA,
    PROVENANCE_SHA,SIDECAR_SHA,PRESSURE_COMMIT)
from datascape.gcode.production.exporter import _atomic_output,save_json

ADAPTER_BLOB='ef19c0ce30495342d5444ff311cbbbd4f48750ad'


def recover(source,output):
    root=Path(source);snapshot=root/'artworks/spring_v13'
    def read(path):
        raw=path.read_bytes()
        return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    adapter=root/'src/datascape/spring_pressure_intent.py';raw=adapter.read_bytes()
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=ADAPTER_BLOB:
        raise ValueError('original pinned PR25 adapter bytes differ')
    acceptance=read(root/'artworks/spring_v13_pressure_intent_v01/acceptance.json')
    manifest_path=snapshot/'MANIFEST_SHA256.json';manifest=read(manifest_path)
    if sha(manifest_path)!=acceptance['baseline_manifest_sha256']:raise ValueError('baseline manifest checksum')
    essential=('machine/spring_v13.offline.machine_vectors.json.gz','visible_ink.json.gz','visible_color.json.gz','ordering.json')
    for name in essential:
        if sha(snapshot/name)!=manifest[name]:raise ValueError('frozen essential bytes differ: '+name)
    side_path=root/'artworks/spring_v13_pressure_intent_v01/spring_v13.pressure_intent_v01.json.gz'
    side=read(side_path);config_path=root/'studies/spring_pressure_full_v01/config.json';config=read(config_path)
    if sha(side_path)!=SIDECAR_SHA or SIDECAR_SHA!=acceptance['sidecar_sha256'] or digest(side)!=acceptance['sidecar_payload_sha256']:
        raise ValueError('accepted pressure checksum')
    if sha(config_path)!=acceptance['config_sha256'] or sha(config_path)!=side['config_sha256']:
        raise ValueError('accepted coefficient bytes differ')
    rows=[r for medium in ('ink','color') for r in read(snapshot/f'visible_{medium}.json.gz')['strokes']]
    if digest(rows)!=acceptance['source_rich_records_sha256']:raise ValueError('frozen rich record aggregate')
    spec=importlib.util.spec_from_file_location('_pinned_pressure_adapter',adapter)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    machine,provenance=module.apply_profiles(read(snapshot/essential[0]),rows,read(snapshot/'ordering.json')['phases'],side,config['limits'])
    provenance.update(frozen_machine_sha256=sha(snapshot/essential[0]),
        baseline_manifest_sha256=acceptance['baseline_manifest_sha256'],rich_source_sha256=digest(rows),
        config_sha256=side['config_sha256'],derived_machine_payload_sha256=digest(machine))
    if digest(machine)!=PAYLOAD_SHA or digest(provenance)!=PROVENANCE_SHA:
        raise ValueError('recovered inputs do not match existing canonical backend checksums')
    def write(out):
        save_json(out/'spring.machine.json',machine);save_json(out/'spring.provenance.json',provenance)
        strokes,_=load_bound_spring(out/'spring.machine.json',out/'spring.provenance.json')
        report=dict(source_commit=PRESSURE_COMMIT,adapter_git_blob=ADAPTER_BLOB,
            canonical_machine_payload_sha256=PAYLOAD_SHA,canonical_provenance_payload_sha256=PROVENANCE_SHA,
            pressure_sidecar_sha256=SIDECAR_SHA,original_strokes=len(strokes),
            accepted_pressure_samples=sum(len(s.points) for s in strokes),
            essential_frozen_files_verified=list(essential),all_unused_render_terrain_archive_files_verified=False,
            original_adapter_apply_profiles_reused=True,artwork_or_pressure_generated=False,
            hardware_mapping_or_authorization_inferred=False)
        save_json(out/'recovery.json',report);return report
    return _atomic_output(output,write)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();print(json.dumps(recover(a.source,a.output),indent=2))
