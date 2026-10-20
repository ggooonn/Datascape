"""Brush-specific measurement records and nonlinear mappings, offline only."""
from dataclasses import dataclass, field
from math import isfinite, sin, cos, pi
from .models import Point, Stroke


def finite(value):
    return type(value) in (int,float) and isfinite(value)


@dataclass(frozen=True)
class CalibrationObservation:
    tested_z_mm: float
    stroke_width_mm: float | None
    feed_mm_min: float
    water_loading: str
    pigment_loading: str
    quality: str = 'unrecorded'
    continuity: str = 'unrecorded'
    notes: str = ''

    def __post_init__(self):
        if not finite(self.tested_z_mm) or not finite(self.feed_mm_min) or self.feed_mm_min <= 0:
            raise ValueError('invalid calibration observation')
        if self.stroke_width_mm is not None and (not finite(self.stroke_width_mm) or self.stroke_width_mm < 0):
            raise ValueError('invalid measured width')


@dataclass(frozen=True)
class BrushCalibration:
    brush_id: str
    family: str
    brush_type: str
    dimensions_mm: dict
    mounting: str
    medium: str
    substrate: str
    substrate_surface_height_mm: float | None
    calibration_date: str | None
    hardware_version: str
    knots: tuple[tuple[float,float], ...]
    observations: tuple[CalibrationObservation, ...] = ()
    status: str = 'synthetic_preview'
    notes: str = ''

    def __post_init__(self):
        if self.status not in ('synthetic_preview','unverified','measured'):
            raise ValueError('unknown calibration status')
        if not self.brush_id or len(self.knots)<2:
            raise ValueError('brush ID and >=2 knots required')
        for (p,z),(q,w) in zip(self.knots,self.knots[1:]):
            if not all(finite(v) for v in (p,z,q,w)) or not 0<=p<q<=1 or z>0 or w>z:
                raise ValueError('knots require increasing pressure, nonincreasing nonpositive Z')
        if self.substrate_surface_height_mm is not None and not finite(self.substrate_surface_height_mm):
            raise ValueError('invalid substrate height')
        if self.status == 'measured' and (not self.observations or not self.calibration_date
                                         or self.substrate_surface_height_mm is None):
            raise ValueError('measured profile needs observations, date and surface height')

    def z_for(self, pressure):
        if not finite(pressure) or not self.knots[0][0] <= pressure <= self.knots[-1][0]:
            raise ValueError('pressure outside supported calibration domain; no extrapolation')
        for (p,z),(q,w) in zip(self.knots,self.knots[1:]):
            if p <= pressure <= q:
                return z+(pressure-p)/(q-p)*(w-z)
        raise ValueError('unmapped pressure')


def synthetic_profile():
    # Explicitly invented visual scale. NOT a tested brush, safe limit, or -12mm mapping.
    return BrushCalibration('SYNTHETIC-NOT-A-BRUSH','synthetic','illustration',{},
                            'unmeasured','unspecified','unspecified',None,None,'unverified',
                            ((0,0),(.2,-.08),(.5,-.3),(.8,-.65),(1,-1)))


@dataclass(frozen=True)
class Benchmark:
    name: str
    stroke: Stroke
    mode: str
    constant_z_mm: float | None
    feed_mm_min: float
    water_loading: str = 'record_required'
    pigment_loading: str = 'record_required'


def benchmarks():
    """Deterministic calibration sheet; depths/feedrates are TEST DESIGN ONLY.

    Includes 10 pattern families; no spline fitting, smoothing, or Spring edits.
    Constant-depth tests do not reinterpret artistic pressure as compression.
    """
    result=[]
    def add(name, xy, pressures, mode='variable', depth=None, feed=1200, medium='ink', water='record_required', pigment='record_required'):
        i=len(result); y=20+i*18
        pts=tuple(Point(x+20,v+y,p) for (x,v),p in zip(xy,pressures))
        stroke=Stroke(name,pts,'CALIBRATION','INK' if medium=='ink' else 'A1',medium,sequence=i)
        result.append(Benchmark(name,stroke,mode,depth,feed,water,pigment))
    line=[(i*2,0) for i in range(41)]
    for depth in (-.1,-.3,-.6): add(f'constant-line-{depth}',line,[.5]*41,'constant',depth)
    curve=[(i*2,5*sin(i*pi/20)) for i in range(41)]
    add('constant-curve',curve,[.5]*41,'constant',-.3)
    add('gradual-ramp',line,[.2+.73*i/40 for i in range(41)])
    add('entry-exit-artistic-taper',line,[.22+.65*sin(pi*i/40) for i in range(41)])
    add('alternating-pressure',line,[.25 if i%2==0 else .8 for i in range(41)])
    for length in (.1,.5,2): add(f'short-{length}',[(0,0),(length,0)],[.3,.6])
    add('long-continuous',[(i*2,3*sin(i/15)) for i in range(181)],[.5]*181)
    for feed in (600,1200,2400): add(f'feed-{feed}',line,[.5]*41,feed=feed)
    for medium in ('ink','color'): add(f'medium-{medium}',curve,[.5]*41,medium=medium)
    for water,pigment in (('low','low'),('ordinary','ordinary'),('high','high')):
        add(f'loading-{water}',line,[.5]*41,water=water,pigment=pigment)
    return tuple(result)


def recording_template():
    return {'schema':'datascape.brush_calibration_record.v0.2', 'status':'unverified',
            'brush_id':None,'brush_family':None,'brush_type':None,'dimensions_mm':{},
            'mounting':None,'medium':None,'substrate':None,'substrate_surface_height_mm':None,
            'hardware_version':None,'calibration_date':None,'knots':[],
            'observations':[{'benchmark_id':b.name,'feed_mm_min_candidate':b.feed_mm_min,
                'tested_z_mm':None,'resulting_width_mm':None,'water_loading':b.water_loading,
                'pigment_loading':b.pigment_loading,'mark_quality':None,'continuity':None,'notes':''}
                for b in benchmarks()]}
