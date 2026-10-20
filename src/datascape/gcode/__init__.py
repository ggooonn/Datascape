"""Datascape offline machine-vector backend, v0.1 compatibility + v0.2 IR.

V0.2 entry point: python -m datascape.gcode.offline.
Legacy plan/PreviewProfile below remain illustrative v0.1 APIs.

NO hardware command execution or production G-code in this release.
"""
from .models import Point, Stroke, Panel, PANELS
from .clipping import clip_all, clip_stroke
from .scheduling import schedule
from .planning import PreviewProfile, Motion, plan
from .export import preview_gcode, preview_svg
from .io import load_strokes

__all__=['Point','Stroke','Panel','PANELS','clip_all','clip_stroke','schedule',
         'PreviewProfile','Motion','plan','preview_gcode','preview_svg','load_strokes']
