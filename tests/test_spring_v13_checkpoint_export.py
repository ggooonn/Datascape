"""Frozen full-scene export, explicit missing pressure and publication scope."""
from pathlib import Path
import gzip,json,hashlib
import pytest
from datascape.spring_checkpoint import SNAPSHOT,load_snapshot,read,inspect_path,export,verify


MACHINE=SNAPSHOT/'machine/spring_v13.offline.machine_vectors.json.gz'
META=SNAPSHOT/'machine/metadata.json.gz'


def test_approved_snapshot_is_exact_and_provenance_honest():
    rows,_,_=load_snapshot();assert len(rows)==14951
    a=read(SNAPSHOT/'approval.json');assert a['visual_identity']['verified']
    assert a['visual_identity']['reference_filename']=='image(20261019-044435).png'
    assert not a['lost_historical_vector_identity_proven'] and not a['physical_pressure_calibrated']


def test_entire_export_preserves_XY_ID_slot_layer_and_order():
    result=verify(MACHINE,META)
    assert result['counts']=={'ink':3345,'color':11606} and result['all_XY_and_IDs_exact']


def test_missing_pressure_fails_closed_without_explicit_policy(tmp_path):
    with pytest.raises(ValueError,match='lack original normalized pressure'):export(tmp_path/'bad.json',tmp_path/'bad-meta.json')
    assert not (tmp_path/'bad.json').exists()


def test_preview_pressure_requires_offline_acknowledgement(tmp_path):
    with pytest.raises(ValueError,match='require --offline-only'):export(tmp_path/'bad.json',tmp_path/'bad-meta.json',.5,False)


def test_known_pressure_and_missing_pressure_are_distinguished():
    rows,_,_=load_snapshot();machine=read(MACHINE);meta=read(META);known=0;missing=0
    for (_,_,r),s,m in zip(rows,machine['strokes'],meta['per_stroke']):
        if 'pressure_intent_samples' in r:
            assert [p['pressure'] for p in s['points']]==r['pressure_intent_samples'];known+=1
        else:
            assert not m['original_normalized_pressure_present'] and all(p['pressure']==.5 for p in s['points']);missing+=1
    assert (known,missing)==(675,14276)


def test_export_is_byte_deterministic(tmp_path):
    p=tmp_path/'machine.json.gz';m=tmp_path/'metadata.json.gz'
    export(p,m,.5,True)
    assert p.read_bytes()==MACHINE.read_bytes() and m.read_bytes()==META.read_bytes()


def test_actual_point_contacts_are_rejected_not_dropped():
    _,_,palette=load_snapshot()
    with pytest.raises(ValueError,match='point-contact'):inspect_path({'id':'point','xy_mm':[[1,2]]},'ink',palette)


def test_zero_length_and_invalid_color_are_rejected():
    _,_,palette=load_snapshot()
    with pytest.raises(ValueError,match='zero-length'):inspect_path({'id':'zero','xy_mm':[[1,2],[1,2]]},'ink',palette)
    with pytest.raises(ValueError,match='unknown color slot'):inspect_path({'id':'bad-color','xy_mm':[[1,2],[2,3]],'palette_slot':'Z9'},'color',palette)


def test_profiled_SVG_previews_are_native_size_and_not_machine_sources():
    import xml.etree.ElementTree as ET
    for name in ['ink','color','combined']:
        root=ET.fromstring(gzip.decompress((SNAPSHOT/f'review/{name}.svg.gz').read_bytes()))
        assert root.attrib['width']=='600mm' and root.attrib['height']=='900mm'


def test_source_field_parts_preserve_exact_input():
    m=read(SNAPSHOT/'source/fields_manifest.json');parts=[]
    for part in m['parts']:
        b=(SNAPSHOT/'source'/part['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==part['sha256'];parts.append(b)
    assert hashlib.sha256(b''.join(parts)).hexdigest()==m['file_sha256']
