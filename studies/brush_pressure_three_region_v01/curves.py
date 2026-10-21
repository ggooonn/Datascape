"""Unmeasured study candidates using the unchanged v0.3 calibration mapper."""
from copy import deepcopy
from datascape.gcode.production.profiles import Profile
from pathlib import Path
import json

BOUNDARIES = (0., .2, .4, .6, .93, 1.)
FRACTIONS = (0., 0., .08, .24, .85, 1.)


def catalog():
    rows=[]
    for maximum in (10,12):
        for model in ('global_linear','anchored_linear','convex_reference','three_region'):
            if model == 'global_linear': knots=((0.,0.),(1.,-maximum))
            elif model == 'anchored_linear': knots=((0.,0.),(.2,-3.),(1.,-maximum))
            elif model == 'convex_reference':
                positions=(0.,.2,.3,.4,.5,.6,.7,.8,.9,.93,1.)
                knots=tuple((p,0. if p==0 else -(3+(maximum-3)*((p-.2)/.8)**2)) for p in positions)
            else:
                knots=tuple((p,0. if p==0 else -(3+(maximum-3)*f)) for p,f in zip(BOUNDARIES,FRACTIONS))
            rows.append({'id':f'{model}_{maximum}', 'model':model,'maximum_compression_mm':maximum,
                         'knots':knots,'status':'unmeasured_offline_candidate',
                         'satisfies_pressure_0_2_compression_3mm':model!='global_linear',
                         'interpolation':'piecewise_linear','extrapolation':'reject'})
    return rows


def offline_profile(base, curve):
    """Ephemeral synthetic analysis profile, never a measured physical profile."""
    if base.data['status']!='synthetic_fixture':raise ValueError('study requires synthetic fixture base')
    d=deepcopy(base.data);d['profile_id']='OFFLINE-ONLY-'+curve['id']
    d['motion']['paper_contact_z_range']=[-curve['maximum_compression_mm'],0.]
    for b in d['brush_profiles'].values():
        b.update(knots=curve['knots'],status='synthetic_preview',observations=[],calibration_date=None,
                 notes='Unmeasured Baegunmo study; never authorization or physical calibration')
    return Profile.from_dict(d)


def load_catalog(path):
    """Read editable knot coordinates; retain unmeasured candidate anchor policy."""
    data=json.loads(Path(path).read_text())
    if data.get('schema')!='datascape.unmeasured_response_candidates.v01':raise ValueError('wrong candidate schema')
    rows=data['curves'];seen=set()
    for c in rows:
        if c['id'] in seen:raise ValueError('duplicate candidate ID')
        seen.add(c['id'])
        if c['status']!='unmeasured_offline_candidate' or c['interpolation']!='piecewise_linear' or c['extrapolation']!='reject':
            raise ValueError('study candidates must remain unmeasured, piecewise-linear and non-extrapolating')
        knots=c['knots'];maximum=c['maximum_compression_mm']
        if list(knots[0])!=[0,0] or list(knots[-1])!=[1,-maximum]:raise ValueError('global calibration anchors changed')
        if c['satisfies_pressure_0_2_compression_3mm'] and [0.2,-3.0] not in [list(k) for k in knots]:
            raise ValueError('anchored candidate requires explicit p=.2 / Z=-3 knot')
        # The backend's unchanged mapper supplies full monotonic/domain validation.
        for (p,z),(q,w) in zip(knots,knots[1:]):
            if not 0<=p<q<=1 or not -maximum<=w<=z<=0:raise ValueError('invalid monotonic knots')
    return rows


def quantile(values, q):
    n=(len(values)-1)*q;i=int(n)
    return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(n-i)


def summary(values):
    v=sorted(values)
    return {'samples':len(v),'min':v[0],'p10':quantile(v,.1),'p25':quantile(v,.25),
            'median':quantile(v,.5),'p75':quantile(v,.75),'p90':quantile(v,.9),'max':v[-1]}
