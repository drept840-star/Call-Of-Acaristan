"""Mission 8 - 3D beats: the stage's lines as caption plates over the Route 12
set.  ENTER steps the lines; after the last one the stage advances.  Old Friends
is staged shot / reverse-shot on the catwalk (one camera per line, the speaker's
mouth moving); the meet cuts between the truck and the catwalk; the epilogue is one shot per
line on the chase set (``epilogue3d``).
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small
from core.outfits import OUTFIT_GUARD
from cutscenes import m6world3d as _w
from engine3d import POSES
from missions.m7 import raid3d as R

from .. import meta as M
from . import epilogue3d as E
from . import set3d as S3

PLATE_H = 104
SPEAKER_COL = {"BODI": (226, 170, 98), "VASILE": (196, 196, 214), "BIRIBEL": (228, 230, 222),
               "ALEX": (150, 200, 150), "PRESIDENT": (220, 150, 140), "ANCHOR": (176, 186, 206)}

_S = {"stage": None, "line": 0, "t": 0.0, "line_t": 0.0, "enter": True, "done": None}


def _cat(x):
    return (x, S3.CATWALK_Y, S3.CATWALK_Z)


_TX, _TZ, _TYAW = S3.TRUCK_AT

# stage -> (eye at t=0, eye drift per second, target, fov)
SHOTS = {
    M.STAGE_MEET: ((_TX + 7.7, 1.7, _TZ - 5.0), (-0.08, 0.0, 0.10), (_TX + 0.7, 1.2, _TZ + 1.0), 50.0),
    M.STAGE_FRIENDS: ((8.6, 7.9, 54.2), (-0.05, 0.0, 0.0), (3.6, 7.9, 57.0), 46.0),
}


_Y = S3.CATWALK_Y
VASILE_POS = S3.VASILE_AT
BIRIBEL_POS = _cat(6.2)
BODI_MEET = (_TX + 1.4, 0.0, _TZ + 0.6)

# The meet, one shot per line: the plaza wide, Bodi at the truck, up at the catwalk.
MEET_SHOTS = (
    ((_TX + 7.7, 1.7, _TZ - 5.0), (_TX + 0.7, 1.2, _TZ + 1.0), 50.0, (-0.08, 0.0, 0.10)),
    ((_TX + 1.0, 1.62, _TZ + 3.8), (BODI_MEET[0], 1.55, BODI_MEET[2]), 34.0, (0.02, 0.0, 0.0)),
    ((_TX + 2.6, 1.5, _TZ + 2.8), (VASILE_POS[0], _Y + 1.2, VASILE_POS[2]), 40.0, (0.0, 0.01, 0.0)),
)

# Old Friends, one shot per line: (eye, target, fov, eye drift per second).
FRIENDS_SHOTS = (
    ((7.4, _Y + 1.75, 57.62), (3.6, _Y + 1.5, 57.0), 38.0, (-0.03, 0.0, 0.0)),    # over Biribel
    ((2.35, _Y + 1.75, 57.55), (6.2, _Y + 1.5, 57.1), 38.0, (0.03, 0.0, 0.0)),    # over Vasile
    ((4.9, _Y + 1.2, 52.6), (4.9, _Y + 1.0, 57.0), 50.0, (0.0, 0.0, 0.04)),       # wide, south
    ((5.4, _Y + 1.6, 56.3), (3.6, _Y + 1.55, 57.0), 30.0, (-0.02, 0.0, 0.0)),     # close on Vasile
    ((6.95, _Y + 1.72, 57.5), (3.6, _Y + 1.5, 57.0), 32.0, (-0.04, 0.0, 0.0)),    # tight over Biribel
)


def begin(stage, on_done):
    _S.update(stage=stage, line=0, t=0.0, line_t=0.0, enter=True, done=on_done)


def current():
    """Stage the beats were last begun for (None before the first)."""
    return _S["stage"]


def update(keys=None, dt=1.0 / 60.0):
    _S["t"] += dt
    down = bool(keys is not None and keys[pygame.K_RETURN])
    if down and not _S["enter"]:
        lines = M.BEATS.get(_S["stage"], ())
        _S["line"] += 1
        _S["line_t"] = _S["t"]
        if _S["line"] >= len(lines) and _S["done"] is not None:
            done, _S["done"] = _S["done"], None
            done()
    _S["enter"] = down
    return (0, 0)


def _cast(r, stage, tm):
    def put(key, pose, pos, yaw, **kw):
        _w.actor(r, key, pose, pos, yaw, tm, amp=0.5, mouth=0.0, **kw)

    if stage == M.STAGE_MEET:
        talk = _mouth("BODI", M.STAGE_MEET)
        _w.actor(r, ("ally", "bodi"), dict(POSES["stand"]), BODI_MEET, _TYAW + 20, tm, seed=61,
                 amp=0.5, mouth=talk)
        put(("biribel", OUTFIT_GUARD), dict(POSES["stand"], head_p=-10 if _S["line"] == 2 else 0),
            (_TX + 2.9, 0.0, _TZ + 0.5), _TYAW - 60, seed=93, flags=("shotgun",))
        if _S["line"] == 2:
            put("vasile", dict(POSES["stand"]), VASILE_POS, 180.0, seed=71)
    elif stage == M.STAGE_FRIENDS:
        _friends_cast(r, tm)


def _speaker(stage=M.STAGE_FRIENDS):
    lines = M.BEATS.get(stage, ())
    return lines[min(_S["line"], len(lines) - 1)][0] if lines else ""


def _mouth(who, stage=M.STAGE_FRIENDS):
    if _speaker(stage) != who or _S["t"] - _S["line_t"] > 3.2:
        return 0.0
    return abs(math.sin((_S["t"] - _S["line_t"]) * 11.0)) * 0.8


def _friends_cast(r, tm):
    line = _S["line"]
    vp = dict(POSES["stand"])
    if line == 2:
        vp.update(head_y=-38, head_p=6)          # looks down at the road: "does it matter to them?"
    elif line >= 3:
        vp.update(head_p=-4, lsh_p=6, rsh_p=6)
    _w.actor(r, "vasile", vp, VASILE_POS, 90.0, tm, seed=71, amp=0.35, mouth=_mouth("VASILE"))
    key = ("biribel", OUTFIT_GUARD)
    hum = _w.hum(key, flags=("shotgun",))
    bp = R._held(hum, POSES["ready"], "shotgun", "ready", ("m7player", "ready"))
    _w.actor(r, key, bp, BIRIBEL_POS, 270.0, tm, seed=93, amp=0.3, rifle_on=True,
             flags=("shotgun",), expression="angry", mouth=_mouth("BIRIBEL"))


def draw(surface):
    stage = _S["stage"] or M.STAGE_MEET
    if stage == M.STAGE_EPILOGUE:
        lines = M.BEATS[stage]
        line = min(_S["line"], len(lines) - 1)
        E.draw(surface, line, _S["t"] - _S["line_t"])
        _plate(surface, stage, title=line == len(lines) - 1)
        return
    if stage in (M.STAGE_FRIENDS, M.STAGE_MEET):
        shots = FRIENDS_SHOTS if stage == M.STAGE_FRIENDS else MEET_SHOTS
        eye0, tgt, fov, drift = shots[min(_S["line"], len(shots) - 1)]
        t = min(_S["t"] - _S["line_t"], 20.0)
    else:
        eye0, drift, tgt, fov = SHOTS.get(stage, SHOTS[M.STAGE_MEET])
        t = min(_S["t"], 40.0)
    eye = tuple(eye0[i] + drift[i] * t for i in range(3))
    r = S3.frame(eye, tgt, fov)
    del _w.LAST[:]
    _cast(r, stage, int(_S["t"] * 1000.0))
    S3.present(r, surface)
    _plate(surface, stage)


def _plate(surface, stage, title=False):
    bar = pygame.Surface((WIDTH, PLATE_H), pygame.SRCALPHA)
    bar.fill((6, 8, 10, 200))
    surface.blit(bar, (0, HEIGHT - PLATE_H))
    label = font_terminal_small.render(M.STAGE_LABELS.get(stage, stage.upper()), True, (150, 190, 110))
    surface.blit(label, (40, HEIGHT - PLATE_H + 10))
    lines = M.BEATS.get(stage, ())
    if lines and not title:
        who, text = lines[min(_S["line"], len(lines) - 1)]
        col = SPEAKER_COL.get(who, (214, 206, 182))
        msg = (who + ":  " + text) if who else text
        img = font_terminal.render(msg, True, col)
        if img.get_width() > WIDTH - 80:
            img = font_terminal_small.render(msg, True, col)
        surface.blit(img, (40, HEIGHT - PLATE_H + 36))
    a = 0.55 + 0.45 * math.sin(_S["t"] * 3.0)
    hint = font_terminal_small.render("[ENTER] CONTINUE", True,
                                      tuple(int(c * a) for c in (180, 172, 150)))
    surface.blit(hint, (WIDTH - 40 - hint.get_width(), HEIGHT - 28))
