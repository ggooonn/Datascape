"""Provisional configurations: unknown physical values remain null."""
from pathlib import Path
from copy import deepcopy
import json,re
from datascape.gcode.production.profiles import Profile


def historical_xy(path):
    result={};name=None
    for line in Path(path).read_text().splitlines():
        m=re.match(r'^  ([A-Z][A-Z_0-9]*):\s*$',line)
        if m:name=m[1];result[name]={}
        m=re.match(r'^    (x|y|y_start|y_end):\s*([0-9.]+)',line)
        if m and name:result[name][m[1]]=float(m[2])
    return result


def curve_knots(preload):
    return [(0.,0.),(.2,-preload),(.4,-(preload+.08*(10-preload))),
            (.6,-(preload+.24*(10-preload))),(.93,-(preload+.85*(10-preload))),(1.,-10.)]


def candidate_profile(root):
    d=json.loads((root/'config/plotter_v03/profile.unmeasured.json').read_text());xy=historical_xy(root/'hardware/fluidnc/tool_coordinates.yaml')
    d['profile_id']='UNMEASURED-LOCAL-HOVER-STATION-CANDIDATES'
    d['motion']['local_hover']={'enabled':False,'height_mm':5,'max_distance_mm':10}
    d['motion']['paper_contact_z_range']=[-10,0]
    for medium,b in d['brush_profiles'].items():
        b.update(brush_id='UNMEASURED-BAEGUNMO',knots=curve_knots(2),status='unverified',observations=[],notes='Provisional .2 -> -2 mm / 1 -> -10 mm; no physical calibration')
    for role,st in d['stations'].items():
        st['coordinate_frame']=None
        if role=='sponge':st.update(compression_mm=2,surface_z=None,wipe_xy_mm=[0,0],repetitions=1)
        elif role in ('water','ink'):
            h=xy['WELL_1' if role=='water' else 'WELL_2']
            st.update(liquid_reference_z=15,immersion_mm=5,center_xy=[h['x'],(h['y_start']+h['y_end'])/2],
                      deep_surface_xyz=None,shallow_surface_xyz=None)
            if role=='water':st['rewet_immersion_mm']=3
        else:
            st.update(center_xy=[xy[role]['x'],xy[role]['y']],liquid_reference_z=10,immersion_mm=3,
                      bottom_z=-1,bottom_gap_mm=2)
    d['notes']='All coordinates/depths provisional. Nominal well center derives only from historical XY range; never supplies deep/shallow slope points. No G54 machine offset, contact box, sponge height or stone slope is invented.'
    return Profile.from_dict(d)
