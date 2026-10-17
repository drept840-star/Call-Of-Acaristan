"""cast.py - cutscene cast sprites.

Restyled to the "Balaceanu Arrest" look: every figure is now drawn by
``figure_kit`` (angular faces with key/rim light, tailored torsos, articulated
limbs, hands, ground shadow) instead of circle-head + rectangle-limb primitives.

Signatures, ``in_silhouette`` handling and the ``_pose_cached`` render-once
cache are unchanged, so no shot code (m3ko, m3ending, m3cell, m4aftermath,
route12, ...) needs to change.

The rest of the cast sheet - Balaceanu, President Retardovici and the extras
(IPA agents, KRAP squad, civilians) - is exposed here too, so no cutscene has
a reason to hand-draw a person.  Static poses go through these cached
wrappers; animated staging (seated/reach/bow/expressions that change per
frame) calls ``figure_kit.draw_character`` directly so the pose cache does
not grow every frame.
"""
import functools
import math

import pygame
import core.config  # noqa: F401  boot side effect (A-001/B-007); removed in P4-1
from core import artpack

from .figure_kit import draw_character


def _pose_cached(fn):
    """Render a cutscene cast figure once per (pose args) into a cached
    SRCALPHA surface; blit afterwards. Procedural fallback when art tier off."""
    @functools.wraps(fn)
    def wrapper(surface, cx, foot_y, *args, **kw):
        act_t = kw.pop("act_t", None)
        if not artpack.enabled():
            return fn(surface, cx, foot_y, *args, **kw)
        key = (fn.__name__, tuple(args), tuple(sorted(kw.items())))
        W, H = 320, 480
        spr = artpack.pose(key, (W, H),
                           lambda s: fn(s, W // 2, H - 30, *args, **kw))
        dy = int(math.sin(act_t * 2.2) * 1.5) if act_t is not None else 0
        surface.blit(spr, (int(cx - W // 2), int(foot_y - (H - 30) + dy)))
    return wrapper


@_pose_cached
def draw_volkov(surface, cx, foot_y, scale=1.0, facing_right=True):
    draw_character(surface, "volkov", cx, foot_y, scale, facing_right)


@_pose_cached
def draw_vasile(surface, cx, foot_y, scale=1.0, facing_right=True):
    draw_character(surface, "vasile", cx, foot_y, scale, facing_right)


@_pose_cached
def draw_biribel(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "biribel", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_old_fisherman(surface, cx, foot_y, scale=1.0, facing_right=True):
    draw_character(surface, "fisherman", cx, foot_y, scale, facing_right)


@_pose_cached
def draw_commander(surface, cx, foot_y, scale=1.0, facing_right=True):
    draw_character(surface, "commander", cx, foot_y, scale, facing_right)


@_pose_cached
def draw_balaceanu(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "balaceanu", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_president(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "president", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_maru(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "maru", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_bodi(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "bodi", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_alex(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "alex", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_ucilev(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "ucilev", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_ipa_agent(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "ipa", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_krap_soldier(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "krap", cx, foot_y, scale, facing_right, silhouette=in_silhouette)


@_pose_cached
def draw_civilian(surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False):
    draw_character(surface, "civilian", cx, foot_y, scale, facing_right, silhouette=in_silhouette)
