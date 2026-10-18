"""Datascape offline machine-vector and brush-motion prototype, v0.1.

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
