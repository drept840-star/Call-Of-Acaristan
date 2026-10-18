"""Mission-specific failure terminals with bespoke procedural illustrations.

Pure presentation: state and existing button objects are supplied by ui.system.
No mission imports, save writes, RNG consumption, or gameplay-state mutations.
Original schematics remain as a missing-art / legacy-tier fallback only.
"""
import math
import os
from functools import lru_cache

import pygame
from core.config import resource_path
from core import mission_meta
from core import artpack as _artpack

# Each mission has its own visual vocabulary, not just a new subtitle.
PROFILES = {
    "MISSION1": ((237, 169, 87), "WAREHOUSE RAID", "BLACK NOTEBOOK", "EVIDENCE LOCKER", "RECOVERY ABORTED", "notebook"),
    "MISSION2": ((126, 188, 228), "ROUTE 12", "QUIET ON ROUTE 12", "SQUAD UPLINK", "CONNECTION SEVERED", "route"),
    "MISSION3": ((156, 198, 157), "THE STABILIZATION CENTER", "THE VOSTRAL", "BLOCK SURVEILLANCE", "ESCAPE TERMINATED", "cells"),
    "MISSION4": ((167, 187, 233), "THE CAPITAL", "48H CURFEW", "TRANSMITTER ARRAY", "CARRIER LOST", "tower"),
    "MISSION5": ((235, 125, 103), "THE CAPITAL", "EMERGENCY RULE", "PRINTWORKS CONTROL", "PUBLICATION HALTED", "press"),
    "MISSION6": ((225, 180, 104), "KIM KIM BORDER", "BLACK NOTEBOOK", "FINAL TRANSMISSION", "SIGNAL LOST", "tower"),
}
INK = (235, 234, 225)
MUTED = (164, 172, 177)
ERROR = (242, 113, 101)


@lru_cache(maxsize=20)
def _font(size, display=False, bold=False):
    name = "Oswald.ttf" if display else ("IBMPlexMono-Bold.ttf" if bold else "IBMPlexMono-Regular.ttf")
    path = resource_path(os.path.join("assets", "fonts", name))
    if os.path.exists(path):
        return pygame.font.Font(path, size)
    return pygame.font.SysFont("Impact" if display else "Consolas", size, bold=bold)


def _text(surf, text, x, y, size=14, color=INK, display=False, bold=False):
    image = _font(size, display, bold).render(str(text), True, color)
    surf.blit(image, (x, y))
    return image.get_rect(topleft=(x, y))


def _wrap(text, width, size=16):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if line and _font(size).size(trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def _paragraph(surf, text, x, y, width, size=16, color=MUTED):
    for line in _wrap(text, width, size):
        _text(surf, line, x, y, size, color)
        y += size + 7
    return y


def checkpoint_label(state):
    """Mirror restart_current_mission's deepest-checkpoint priority."""
    key = mission_meta.mission_key(state)
    ladders = {
        "MISSION2": [("mission2_checkpoint_reached", "ROUTE 12 CHECKPOINT")],
        "MISSION3": [("mission3_" + part + "_checkpoint_reached", label) for part, label in
                     [("broadcast", "BROADCAST WING"), ("kill_order", "KILL ORDER"),
                      ("archives", "ARCHIVES"), ("comms", "COMMS WING"), ("breakout", "BREAKOUT")]],
        "MISSION4": [("mission4_tower_checkpoint_reached", "TRANSMITTER TOWER"),
                     ("mission4_station_checkpoint_reached", "STATION")],
        "MISSION5": [("mission5_tunnel_checkpoint_reached", "TUNNEL"),
                     ("mission5_printworks_checkpoint_reached", "PRINTWORKS"),
                     ("mission5_quarter_checkpoint_reached", "LOWER QUARTER")],
        "MISSION6": [("m6_train_checkpoint_reached", "TRAIN")],
    }
    for flag, label in ladders.get(key, []):
        if getattr(state, flag, False):
            return label
    return "HQ" if key == "MISSION5" else "MISSION START"


def failure_copy(state):
    key = mission_meta.mission_key(state)
    if key == "MISSION6" and getattr(state, "m6_train_result", None) == "failed":
        return ("VOLKOV NEVER REACHED THE TRAIN",
                "VASILE: You didn't clear the platform. They cut him down "
                "before the carriage.")
    if key == "MISSION5" and getattr(state, "m5_maru_dead", False):
        return "MARU DID NOT MAKE IT OUT", "VASILE: ...Biribel? Tell me that wasn't Maru."
    return mission_meta.fail_text(state)


def stat_rows(state, now):
    start = getattr(state, "mission_start_time", 0)
    end = getattr(state, "mission_end_time", 0) or now
    seconds = max(0, (end - start) // 1000) if start else 0
    shots = getattr(state, "shots_fired", 0)
    accuracy = int(100 * getattr(state, "shots_hit", 0) / shots) if shots else 0
    key = mission_meta.mission_key(state)
    fourth = ("SHOTS FIRED", str(shots))
    if key == "MISSION2":
        found = sum(bool(item.get("done")) for item in getattr(state, "mission2_evidence", []))
        fourth = ("EVIDENCE FOUND", f"{found}/3")
    elif key == "MISSION3":
        weapon = getattr(state, "mission3_weapon", "none")
        fourth = ("LAST WEAPON", str(weapon).replace("_", " ").upper())
    elif key == "MISSION4":
        fourth = ("JAMMER", "INSTALLED" if getattr(state, "m4_jammer_installed", False) else "NOT INSTALLED")
    elif key == "MISSION5":
        fourth = ("MARU", "LOST" if getattr(state, "m5_maru_dead", False) else
                  ("CONTACT MADE" if getattr(state, "m5_maru_found", False) else "NOT REACHED"))
    elif key == "MISSION6":
        recovered = (bool(getattr(state, "m6_volkov_dead", False))
                     or getattr(state, "mission6_stage", None) in ("boxcar", "train"))
        fourth = ("NOTEBOOK", "RECOVERED" if recovered else "NOT RECOVERED")
    return [("ELAPSED", f"{seconds // 60:02d}:{seconds % 60:02d}"),
            ("HOSTILES DOWN", str(getattr(state, "hostiles_killed", 0))),
            ("ACCURACY", f"{accuracy}%"), fourth]


def _cross(s, x, y, c, r=8):
    pygame.draw.line(s, c, (x-r, y-r), (x+r, y+r), 2)
    pygame.draw.line(s, c, (x-r, y+r), (x+r, y-r), 2)


def _illustrated_art(surface, state, kind):
    """Use the artpack cache; native-size artwork, no per-frame image scaling."""
    frame_key = "maru_lost" if (kind == "press" and getattr(state, "m5_maru_dead", False)) else kind
    image = _artpack.frame("spr_mission_failed", frame_key)
    if image is None:
        return False
    surface.blit(image, (626, 166))
    pygame.draw.rect(surface, (74, 82, 88), (625, 165, 322, 252), 1)
    return True


def _diagram(s, kind, a, t):
    """Editable technical illustrations in a fixed 320x250 plotting area."""
    d = pygame.Surface((320, 250), pygame.SRCALPHA)
    dim = tuple(int(v * .32) for v in a)
    grid = tuple(int(v * .12) for v in a)
    for x in range(0, 320, 20):
        pygame.draw.line(d, grid, (x, 0), (x, 250))
    for y in range(0, 250, 20):
        pygame.draw.line(d, grid, (0, y), (320, y))
    if kind == "notebook":
        book = pygame.Rect(79, 28, 162, 193)
        pygame.draw.rect(d, (22, 24, 27), book)
        pygame.draw.rect(d, a, book, 2)
        pygame.draw.line(d, dim, (100, 29), (100, 218), 2)
        for y in range(44, 210, 25):
            pygame.draw.line(d, a, (70, y), (87, y), 3)
        _text(d, "BLACK", 118, 58, 24, a, True)
        _text(d, "NOTEBOOK", 118, 91, 24, a, True)
        for y, w in [(142, 97), (154, 73), (166, 86)]:
            pygame.draw.rect(d, dim, (118, y, w, 4))
        _cross(d, 215, 196, ERROR, 13)
        for x, y, dx, dy in [(55, 12, 1, 1), (263, 12, -1, 1), (55, 236, 1, -1), (263, 236, -1, -1)]:
            pygame.draw.line(d, dim, (x, y), (x + dx*18, y), 2)
            pygame.draw.line(d, dim, (x, y), (x, y + dy*18), 2)
    elif kind == "route":
        pts = [(18, 205), (75, 179), (102, 125), (166, 125), (209, 71), (299, 39)]
        pygame.draw.lines(d, dim, False, pts, 12)
        pygame.draw.lines(d, a, False, pts[:4], 2)
        for x, y in pts:
            pygame.draw.circle(d, a, (x, y), 5, 1)
        _cross(d, 188, 98, ERROR, 13)
        pygame.draw.circle(d, dim, (188, 98), 34, 1)
        _text(d, "12", 20, 18, 56, a, True)
        _text(d, "VASILE", 213, 166, 14, a)
        _text(d, "NO RESPONSE", 213, 190, 12, ERROR)
        pygame.draw.line(d, ERROR, (212, 215), (299, 215), 2)
    elif kind == "cells":
        for row in range(2):
            for col in range(4):
                x, y = 15 + col*77, 26 + row*112
                pygame.draw.rect(d, dim, (x, y, 60, 88), 1)
                for bx in range(x+12, x+56, 12):
                    pygame.draw.line(d, a, (bx, y+10), (bx, y+76), 2)
        pygame.draw.rect(d, (16, 24, 21), (42, 91, 236, 64))
        pygame.draw.rect(d, ERROR, (42, 91, 236, 64), 2)
        _text(d, "SUBJECT LOST", 64, 107, 24, ERROR, True)
    elif kind == "tower":
        pygame.draw.line(d, a, (160, 45), (104, 213), 3)
        pygame.draw.line(d, a, (160, 45), (216, 213), 3)
        pygame.draw.line(d, a, (95, 216), (226, 216), 3)
        for y in [103, 135, 167, 199]:
            half = int((y-45)/3)
            pygame.draw.line(d, dim, (160-half, y), (160+half, y), 2)
            pygame.draw.line(d, dim, (160-half, y), (160+half-10, y-26), 1)
        pygame.draw.circle(d, ERROR, (160, 42), 6)
        for radius in [37, 63, 89]:
            pygame.draw.arc(d, dim, (160-radius, 42-radius, radius*2, radius*2), -.42, .42, 2)
            pygame.draw.arc(d, dim, (160-radius, 42-radius, radius*2, radius*2), math.pi-.42, math.pi+.42, 2)
        _cross(d, 267, 104, ERROR, 10)
    elif kind == "press":
        pygame.draw.rect(d, a, (57, 17, 206, 218), 2)
        _text(d, "EMERGENCY", 73, 29, 28, a, True)
        _text(d, "RULE", 73, 65, 42, a, True)
        pygame.draw.line(d, a, (73, 119), (246, 119), 2)
        for col in range(3):
            for y in range(133, 213, 9):
                pygame.draw.line(d, dim, (73+col*59, y), (119+col*59, y), 3)
        stamp = pygame.Surface((250, 48), pygame.SRCALPHA)
        stamp.fill((18, 20, 23, 245))
        pygame.draw.rect(stamp, ERROR, stamp.get_rect(), 2)
        _text(stamp, "SUPPRESSED", 43, 6, 26, ERROR, True)
        stamp = pygame.transform.rotate(stamp, -13)
        d.blit(stamp, (31, 140))
    # Slow deterministic scan sweep; meaning never depends on motion.
    scan = int(t * .025) % 250
    pygame.draw.line(d, (*a, 35), (0, scan), (320, scan))
    s.blit(d, (634, 169))


def draw(surface, state, buttons, elapsed, now, mouse):
    key = mission_meta.mission_key(state)
    accent, location, operation, plate, status, kind = PROFILES[key]
    w, h = surface.get_size()
    train_death = (getattr(state, "m6_train_death", False)
                   or (getattr(state, "m6_train_active", False)
                       and getattr(state, "m6_train_result", None) == "dead"))
    if train_death:
        # Keep the frozen 3D death frame behind the terminal: the player just
        # watched Biribel fall in-engine, so an opaque menu would cut away.
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((10, 14, 18, 198))
        surface.blit(veil, (0, 0))
    else:
        surface.fill((10, 14, 18))
    # Restrained terminal framing, opaque enough to remove gameplay HUD bleed.
    pygame.draw.rect(surface, (15, 20, 25), (606, 97, 362, 400))
    pygame.draw.line(surface, (49, 58, 63), (32, 72), (w-32, 72))
    pygame.draw.rect(surface, accent, (32, 32, 4, 22))
    _text(surface, "KRAPNET / AFTER-ACTION RECORD", 48, 32, 14, MUTED)
    _text(surface, f"{key.replace('MISSION', 'MISSION 0')} / SIGNAL LOST", 704, 32, 14, accent)

    # The typography is the verdict; no rapid flashes or random jitter.
    _text(surface, "MISSION", 44, 88, 82, INK, True)
    _text(surface, "FAILED", 44, 164, 92, ERROR, True)
    _text(surface, location, 48, 294, 14, accent)
    _text(surface, operation, 46, 314, 32, INK, True)
    subtitle, flavor = failure_copy(state)
    _paragraph(surface, subtitle, 48, 368, 524, 16, accent)
    pygame.draw.line(surface, (49, 58, 63), (48, 418), (568, 418))
    _paragraph(surface, flavor, 48, 431, 518, 14, MUTED)

    _text(surface, plate, 626, 112, 14, accent, bold=True)
    _text(surface, "OPERATION LOST / LINK TERMINATED", 626, 138, 12, MUTED)
    if not _illustrated_art(surface, state, kind):
        _diagram(surface, kind, accent, elapsed)
    pygame.draw.line(surface, (49, 58, 63), (626, 435), (948, 435))
    _text(surface, "// " + status, 626, 452, 14, ERROR)
    _text(surface, mission_meta.radio_channel(state), 626, 477, 12, MUTED)

    # All values are from the current run. No inherited walking-sim stats.
    pygame.draw.rect(surface, (19, 25, 30), (32, 516, w-64, 78))
    for i, (label, value) in enumerate(stat_rows(state, now)):
        x = 48 + i*232
        if i:
            pygame.draw.line(surface, (49, 58, 63), (x-16, 532), (x-16, 578))
        _text(surface, label, x, 528, 12, MUTED)
        _text(surface, value, x, 548, 23, INK, True)

    # Reuse the existing event targets: no second restart implementation.
    ready = elapsed >= 1200
    for i, button in enumerate(buttons):
        button.x, button.y = 48 + i*328, h-78
        button.rect = pygame.Rect(button.x, button.y if ready else h+200, 300, 44)
        button.is_selected = False
        if not ready:
            button.is_hovered = False
            continue
        button.check_hover(mouse)
        hot = button.is_hovered
        box = pygame.Rect(button.x, button.y, 300, 44)
        pygame.draw.rect(surface, accent if hot else (26, 33, 39), box)
        pygame.draw.rect(surface, accent if i == 0 or hot else (95, 106, 115), box, 1)
        _text(surface, "> " + button.text, box.x+16, box.y+12, 14,
              (10, 14, 18) if hot else INK, bold=True)
    _text(surface, "REDEPLOY / " + checkpoint_label(state), 48, h-25, 12, MUTED)
    _text(surface, "CALL OF ACARISTAN", 836, h-25, 12, MUTED)

    # One short fade, no strobing. Input stays disabled until it has finished.
    if elapsed < 500:
        fade = pygame.Surface((w, h))
        fade.fill((0, 0, 0))
        fade.set_alpha(int(255 * (1 - max(0, elapsed)/500)))
        surface.blit(fade, (0, 0))
