"""Assumption-driven offline estimates, with no stroke-order optimization."""
from dataclasses import dataclass, asdict
from math import hypot, sqrt, isfinite
from collections import Counter
from .motion import Action


@dataclass(frozen=True)
class EstimateAssumptions:
    draw_mm_min: float = 1200
    travel_mm_min: float = 6000
    z_mm_min: float = 600
    xy_accel_mm_s2: float = 100
    z_accel_mm_s2: float = 50

    def __post_init__(self):
        if not all(isfinite(v) and v>0 for v in asdict(self).values()):
            raise ValueError('all estimator assumptions must be finite and positive')


def rest_to_rest_seconds(distance,feed,accel):
    if not distance: return 0
    speed=feed/60
    return 2*sqrt(distance/accel) if distance<speed*speed/accel else distance/speed+speed/accel


class Estimator:
    def __init__(self,assumptions=EstimateAssumptions()):
        self.a=assumptions; self.setup=None; self.xy=None; self.z=None
        self.counts=Counter(); self.draw_mm=0.; self.travel_mm=0.; self.z_mm=0.
        self.nominal_seconds=0.; self.stop_each_segment_seconds=0.; self.unresolved_z_moves=0

    def add(self,e):
        self.counts[e.action.value]+=1
        if e.setup!=self.setup:
            self.setup=e.setup; self.xy=None; self.z=None
        xy_distance=0; dz=0
        if e.work_xy is not None and self.xy is not None:
            xy_distance=hypot(e.work_xy[0]-self.xy[0],e.work_xy[1]-self.xy[1])
        if e.work_xy is not None: self.xy=e.work_xy
        if e.preview_z_mm is not None:
            if self.z is not None: dz=abs(e.preview_z_mm-self.z)
            self.z=e.preview_z_mm
        else:
            self.unresolved_z_moves+=1; self.z=None
        if e.action==Action.DRAW: self.draw_mm+=xy_distance; feed=self.a.draw_mm_min
        else: self.travel_mm+=xy_distance; feed=self.a.travel_mm_min
        self.z_mm+=dz
        self.nominal_seconds+=max(xy_distance/feed*60,dz/self.a.z_mm_min*60)
        self.stop_each_segment_seconds+=max(rest_to_rest_seconds(xy_distance,feed,self.a.xy_accel_mm_s2),
                                            rest_to_rest_seconds(dz,self.a.z_mm_min,self.a.z_accel_mm_s2))

    def result(self):
        return {'assumptions_not_measured':asdict(self.a),'counts':dict(self.counts),
                'drawing_mm':self.draw_mm,'non_drawing_xy_mm':self.travel_mm,
                'illustrative_z_mm':self.z_mm,'unresolved_z_moves':self.unresolved_z_moves,
                'nominal_feed_seconds_excluding_stations':self.nominal_seconds,
                'stop_each_segment_seconds_excluding_stations':self.stop_each_segment_seconds,
                'station_travel_mm':None,'machine_bounds_verified':False,
                'excluded':['first positioning in each setup','setup/panel replacement','station routes',
                            'manual checks/refills','drying','controller lookahead and junction behavior'],
                'interpretation':'two simplified models, not guaranteed bounds or measured job time'}
