"""Artwork -> panel local -> G54 work -> optional measured machine frame.

G54 origin is front-left; Y is rearward. No machine home or 40-mm exhibition
spacing is inferred. All offsets and rotations are explicit registration input.
"""
from dataclasses import dataclass
from math import cos, sin, radians, isfinite
from .models import Panel, PANELS

FULL = Panel('FULL', 0, 600)


@dataclass(frozen=True)
class Registration:
    panel: str
    x_mm: float = 0
    y_mm: float = 0
    rotation_deg: float = 0

    def __post_init__(self):
        if not all(isfinite(v) for v in (self.x_mm,self.y_mm,self.rotation_deg)):
            raise ValueError('non-finite registration')


@dataclass(frozen=True)
class Layout:
    mode: str = 'A'
    gap_mm: float = 0
    registrations: tuple[Registration, ...] = ()

    def __post_init__(self):
        if self.mode not in ('A','B','C','D'):
            raise ValueError('layout must be A/B/C/D')
        if not isfinite(self.gap_mm) or self.gap_mm < 0:
            raise ValueError('gap must be finite and nonnegative')
        if self.mode != 'C' and self.gap_mm != 0:
            raise ValueError('physical gap applies only to layout C')
        names = [r.panel for r in self.registrations]
        if len(set(names)) != len(names) or any(n not in {p.name for p in self.panels} for n in names):
            raise ValueError('invalid/duplicate registration panel')

    @property
    def panels(self):
        return (FULL,) if self.mode == 'D' else PANELS

    def setup(self, panel):
        return panel.name if self.mode == 'A' else 'SHARED'

    def registration(self, panel):
        given = next((r for r in self.registrations if r.panel == panel.name),None)
        if given is not None: return given
        x = 0 if self.mode == 'A' else panel.x_min
        if self.mode == 'C' and panel.name == 'P2': x += self.gap_mm
        return Registration(panel.name,x,0)

    def local_xy(self, panel, x_artwork, y_artwork):
        return x_artwork-panel.x_min, panel.y_max-y_artwork

    def work_xy(self, panel, x_artwork, y_artwork):
        x,y = self.local_xy(panel,x_artwork,y_artwork)
        reg = self.registration(panel); theta = radians(reg.rotation_deg)
        return (reg.x_mm+x*cos(theta)-y*sin(theta),
                reg.y_mm+x*sin(theta)+y*cos(theta))

    def footprint(self, panel):
        corners = [self.work_xy(panel,x,y) for x in (panel.x_min,panel.x_max)
                   for y in (panel.y_min,panel.y_max)]
        return [min(p[0] for p in corners),min(p[1] for p in corners),
                max(p[0] for p in corners),max(p[1] for p in corners)]


@dataclass(frozen=True)
class WorkToMachine:
    """Measured G54 offset only; never infer this from nominal homing values."""
    offset_xyz: tuple[float,float,float]
    verified: bool = False

    def xyz(self, work_xyz):
        if not self.verified or not all(isfinite(v) for v in (*self.offset_xyz,*work_xyz)):
            raise ValueError('verified finite G54-to-machine measurement required')
        return tuple(a+b for a,b in zip(self.offset_xyz,work_xyz))
