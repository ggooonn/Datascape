"""Authoritative, machine-independent vector and panel records.

All units are mm; pressure is normalized intent (NOT measured force).
"""
from dataclasses import dataclass
from typing import Literal
import math


def _finite(*values: float) -> None:
    if not all(math.isfinite(v) for v in values):
        raise ValueError('coordinates and numeric attributes must be finite')


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    pressure: float = 0.5

    def __post_init__(self):
        _finite(self.x, self.y, self.pressure)
        if not 0 <= self.pressure <= 1:
            raise ValueError('pressure intent must be in [0, 1]')


@dataclass(frozen=True)
class Stroke:
    stroke_id: str
    points: tuple[Point, ...]
    layer: str
    color_slot: str
    medium: Literal['ink', 'color']
    order_group: int = 0
    sequence: int = 0
    reorderable: bool = False
    reversible: bool = False
    source_id: str | None = None

    def __post_init__(self):
        if not self.stroke_id or not self.layer or not self.color_slot:
            raise ValueError('stroke_id, layer and color_slot are required')
        if len(self.points) < 2:
            raise ValueError('continuous strokes require >=2 points; use a distinct dot primitive later')
        if self.medium not in ('ink', 'color'):
            raise ValueError('medium must be ink or color')
        if self.reversible and not self.reorderable:
            raise ValueError('reversible requires reorderable')

    @property
    def origin_id(self) -> str:
        return self.source_id or self.stroke_id


@dataclass(frozen=True)
class Panel:
    name: str
    x_min: float
    x_max: float
    y_min: float = 0.0
    y_max: float = 900.0

    def __post_init__(self):
        _finite(self.x_min, self.x_max, self.y_min, self.y_max)
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError('invalid panel bounds')


PANELS = (
    Panel('P1', 0.0, 300.0),
    Panel('P2', 300.0, 600.0),
)
