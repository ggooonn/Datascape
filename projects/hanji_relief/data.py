"""Immutable C artwork data, finite settings, and explicit mounting scenarios."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(__file__).resolve().parent
PIN = 'eda6069b12c8785d458a0e8a567a9a86980bc394'
BASE_BRANCH = 'spring/large-baegunmo-z10-hover20-v01'
COLOR_ORDER = ('C2','A4','A3','D4','C4','B1','C5','B2')
PANEL_MAP = {1:7,2:8,3:9,4:4,5:5,6:6,7:1,8:2,9:3}
INPUT_SHA = 'bf9d2fa2b693f9ad1174c7126eaff6a1cd777babc78125c5cfe4f03cfc45be9a'


def number(value, name, low=None, high=None):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError(name+' must be a finite number')
    if (low is not None and value<low) or (high is not None and value>high):
        raise ValueError(name+' is outside the valid range')
    return value


def integer(value,name,low=0):
    if type(value) is not int or value<low: raise ValueError(name+' must be an integer >= '+str(low))
    return value


def load_json(path):
    def invalid(v): raise ValueError('nonfinite JSON: '+v)
    return json.loads(Path(path).read_text(),parse_constant=invalid)


def settings(path=None):
    p=load_json(path or PROJECT/'config/stipple.json')
    if p.get('schema')!='hanji.stipple.v01': raise ValueError('unknown stipple schema')
    for key in ('compression_depth_mm','dwell_at_depth_s','required_surface_clearance_mm'):
        number(p.get(key),key,0)
    for key in ('noncontact_z_feed_mm_min','contact_feed_mm_min','release_feed_mm_min','approach_clearance_mm','preview_diameter_mm'):
        number(p.get(key),key,1e-9)
    integer(p.get('refill_every_contacts'),'refill_every_contacts',1)
    if p.get('refill_policy')!='contact_count': raise ValueError('Hanji requires contact_count refill policy')
    if p.get('first_row_start') not in ('left','right'): raise ValueError('first row must start left or right')
    if tuple(p.get('color_order',[]))!=COLOR_ORDER: raise ValueError('preserve the explicit Hanji eight-color extension')
    mapping=p.get('color_station_map')
    if not isinstance(mapping,dict) or set(mapping)!=set(COLOR_ORDER) or any(not isinstance(v,str) or not v for v in mapping.values()):
        raise ValueError('explicit eight-color station mapping required')
    if len(set(mapping.values()))!=8: raise ValueError('each selected pigment requires its own station')
    return p


@dataclass(frozen=True)
class Dot:
    study_dot_id: int
    physical_panel_id: int
    source_panel_id: int
    global_x_mm: float
    global_y_mm: float
    z_design_mm: float
    local_x_mm: float
    local_y_mm: float
    color_id: str
    row_global: Decimal
    row_local: Decimal
    original: dict


def load_dots(path=None):
    source=Path(path or PROJECT/'input/C_dots.csv')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=INPUT_SHA: raise ValueError('source C CSV hash differs from accepted handoff')
    with source.open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    dots=[]
    for r in rows:
        a=[int(r[k]) for k in ('study_dot_id','physical_panel_id','source_panel_id')]
        for v in a: integer(v,'point/panel ID',1)
        if a[1] not in PANEL_MAP or PANEL_MAP[a[1]]!=a[2]: raise ValueError('physical/source panel mismatch')
        v=[float(r[k]) for k in ('global_x_mm','global_y_mm','z_design_mm','local_x_mm','local_y_mm')]
        for key,x in zip(('global_x','global_y','z_design','local_x','local_y'),v): number(x,key,0,600 if 'global' in key else 20 if key=='z_design' else 200)
        if r['color_id'] not in COLOR_ORDER: raise ValueError('unknown source color')
        if abs(v[0]-v[3]-200*((a[2]-1)%3))>1e-6 or abs(v[1]-v[4]-200*((a[2]-1)//3))>1e-6: raise ValueError('source coordinate-frame mismatch')
        dots.append(Dot(*a,*v,r['color_id'],Decimal(r['global_y_mm']),Decimal(r['local_y_mm']),dict(r)))
    if len({d.study_dot_id for d in dots})!=len(dots): raise ValueError('duplicate study_dot_id')
    expected=load_json(PROJECT/'input/accepted_C_counts.json')
    p4=[d for d in dots if d.physical_panel_id==4]
    for selected,key in ((dots,'full'),(p4,'panel04')):
        if len(selected)!=expected[key]['dots'] or Counter(d.color_id for d in selected)!=expected[key]['colors']: raise ValueError('source C count/color mismatch')
    return tuple(dots)


def mount_for(scenario,panel=None):
    if scenario.get('status') not in ('explicit_nominal_scenario_NOT_MEASURED','measured_registration'):
        raise ValueError('numeric review needs an explicit nominal scenario or measured registration; missing values are not zero')
    base=scenario.get('full' if panel is None else 'individual_mount')
    if panel is not None: base=scenario.get('per_panel_overrides',{}).get(str(panel),base)
    if not isinstance(base,dict): raise ValueError('missing mounting configuration')
    p=deepcopy(base)
    for k in ('g54_x_mm','g54_y_mm','hanji_surface_offset_z_mm','fixed_hover_g54_z_mm'): number(p.get(k),k)
    if not 0<p['fixed_hover_g54_z_mm']<=35: raise ValueError('fixed hover must fit current G54 Z35 candidate envelope')
    return p


def surface_delta(dot,scenario):
    entry=scenario.get('local_surface_corrections',{}).get(str(dot.study_dot_id))
    if entry is None:
        if scenario['status']=='measured_registration': raise ValueError('missing dry surface correction for '+str(dot.study_dot_id))
        return 0.,'nominal_review_zero_NOT_MEASURED'
    number(entry.get('surface_delta_mm'),'surface_delta_mm')
    number(entry.get('uncertainty_mm'),'uncertainty_mm',0)
    if not entry.get('measurement_record'): raise ValueError('surface correction requires provenance')
    return entry['surface_delta_mm'],'measured_correction'
