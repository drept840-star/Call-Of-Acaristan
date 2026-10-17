"""cutscenes.figure_kit - deprecated path (RPE6 Phase 2, A-006): the kit is ``engine.anim``.

Old private names stay available for the existing callers (``_REF_H`` in
cutscenes.m3cell, ``_face``/``_Pen``/``_mix``/``_dark``/``_lite`` in tools/sprites).
"""
import warnings as _warnings

from engine.anim import HEIGHT, SPECS, draw_character  # noqa: F401
from engine.anim import REF_H as _REF_H, Pen as _Pen, face as _face, mix as _mix, dark as _dark, lite as _lite, STUBBLE as _STUBBLE  # noqa: F401,E501

_warnings.warn("cutscenes.figure_kit moved to engine.anim (RPE6 A-006)", DeprecationWarning, stacklevel=2)
