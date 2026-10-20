"""Logical station simulation only; unverified coordinates never become motion."""
from dataclasses import dataclass, field
from math import hypot, isfinite

PALETTE_SLOTS=tuple(f'{letter}{i}' for letter in 'ABCD' for i in range(1,6))


@dataclass(frozen=True)
class StationConfiguration:
    status: str = 'unverified'
    coordinate_frame: str | None = None
    measured_work_xyz: dict = field(default_factory=dict)
    well_mapping: dict = field(default_factory=dict)
    station_clearance_mm: float | None = None
    notes: str = 'No station contact trajectories are implemented in v0.2.'

    def require_measured(self):
        if self.status!='measured' or self.coordinate_frame!='G54' or self.station_clearance_mm is None:
            raise ValueError('station configuration is unverified or frame/clearance unresolved')
        if not isfinite(self.station_clearance_mm) or self.station_clearance_mm<=0:
            raise ValueError('invalid station clearance')
        for role in ('ink','water','sponge',*PALETTE_SLOTS):
            xyz=self.measured_work_xyz.get(role)
            if not isinstance(xyz,(list,tuple)) or len(xyz)!=3 or not all(type(v) in (int,float) and isfinite(v) for v in xyz):
                raise ValueError('missing measured station '+role)
        if not {'ink','water'} <= set(self.well_mapping.values()):
            raise ValueError('well mapping unresolved')
        return self

    def contact_trajectory(self):
        self.require_measured()
        raise ValueError('station contact trajectories deferred, even with measured configuration')


@dataclass(frozen=True)
class ReloadPolicy:
    ink_distance_mm: float = 1200
    color_distance_mm: float = 600
    manual_refill_every_loads: int | None = None
    # Assumptions only, no measured operation times or station route coordinates.
    wash_seconds: float = 20
    wipe_seconds: float = 4
    rewet_seconds: float = 2
    load_seconds: float = 4

    def __post_init__(self):
        if not all(isfinite(v) and v>0 for v in (self.ink_distance_mm,self.color_distance_mm)):
            raise ValueError('positive reload distance required')
        if not all(isfinite(v) and v>=0 for v in (self.wash_seconds,self.wipe_seconds,self.rewet_seconds,self.load_seconds)):
            raise ValueError('invalid assumed duration')
        if self.manual_refill_every_loads is not None and (type(self.manual_refill_every_loads) is not int or self.manual_refill_every_loads<1):
            raise ValueError('invalid manual refill policy')


@dataclass(frozen=True)
class Operation:
    action: str
    station_role: str | None
    slot: str | None
    before_fragment: str
    setup: str
    assumed_seconds: float | None
    work_xyz: None = None
    simulated: bool = True


@dataclass
class BrushState:
    loaded: tuple[str,str] | None = None
    distance_mm: float = 0
    water_condition: str = 'unknown'
    pigment_condition: str = 'unknown'
    interrupted: bool = False
    loads_per_slot: dict = field(default_factory=dict)


class StationSimulator:
    def __init__(self,policy=ReloadPolicy()):
        self.policy=policy; self.state=BrushState(); self.setup=None

    def interrupt(self):
        self.state=BrushState(interrupted=True)

    def before(self,fragment):
        s=fragment.stroke; p=self.policy; ops=[]
        def emit(action,role=None,seconds=None):
            ops.append(Operation(action,role,s.color_slot,s.stroke_id,fragment.setup,seconds))
        if self.setup!=fragment.setup:
            self.setup=fragment.setup; self.state=BrushState(interrupted=True)
            emit('pause_checkpoint')
        state=self.state
        if state.interrupted:
            emit('resume_preparation'); emit('manual_brush_condition_check')
            state.interrupted=False
        target=(s.medium,s.color_slot)
        limit=p.ink_distance_mm if s.medium=='ink' else p.color_distance_mm
        if state.loaded!=target:
            emit('color_tool_request')
            if state.loaded is not None:
                emit('wash','water',p.wash_seconds)
                emit('sponge_wipe','sponge',p.wipe_seconds)
                emit('controlled_rewet','water',p.rewet_seconds)
                state.water_condition='simulated_controlled'
            self._load(fragment,emit)
            state.loaded=target; state.distance_mm=0
        elif state.distance_mm>=limit:
            emit('same_color_replenishment_request')
            self._load(fragment,emit); state.distance_mm=0
        return tuple(ops)

    def _load(self,fragment,emit):
        s=fragment.stroke; p=self.policy
        count=self.state.loads_per_slot.get(s.color_slot,0)+1
        if p.manual_refill_every_loads and s.medium=='color' and count>1 and (count-1)%p.manual_refill_every_loads==0:
            emit('manual_palette_refill_pause',s.color_slot)
            emit('resume_preparation')
        emit('ink_reload' if s.medium=='ink' else 'gouache_load',
             'ink' if s.medium=='ink' else s.color_slot,p.load_seconds)
        self.state.loads_per_slot[s.color_slot]=count
        self.state.pigment_condition='simulated_loaded'

    def after(self,fragment):
        self.state.distance_mm+=sum(hypot(b.x-a.x,b.y-a.y) for a,b in zip(fragment.stroke.points,fragment.stroke.points[1:]))
        # Thresholds defer until the next intact fragment; never split an accepted
        # stroke just to satisfy this placeholder consumption model.


def configuration_template():
    return {'schema':'datascape.stations.v0.2','status':'unverified','coordinate_frame':None,
            'measured_work_xyz':{},'well_mapping':{'WELL_1':None,'WELL_2':None},
            'station_clearance_mm':None,'palette_slots':list(PALETTE_SLOTS),
            'container_height_is_not_dip_depth':True,'station_contact_trajectories_enabled':False}
