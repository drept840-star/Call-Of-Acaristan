"""quarter.py - Lower Quarter systems (round 2): turns 'run and gun' into a run
with choices.

    init()            after _build_quarter_world (flow._enter_quarter)
    update()          every frame in the QUARTER stage (flow._update_stage)
    on_exit()         entering the Print Works: convoy result radio
    draw_world(...)   searchlight cone, detained civilian (after enemies)
    draw_hud(s)       convoy bar

Systems
  * Convoy clock: the Guard convoy reaches the Print Works in
    M5_CONVOY_FRAMES. Every shot fired is noise: +45 frames and +1 heat.
    If the convoy arrives first, a Guard squad dismounts at the door.
  * Heat (0-100, 5 pips of 20): being SPOTTED (+14), shots a guard can see
    (+3, unseen +1), kills (+6) and the searchlight (+12) raise it; it cools
    off (to a floor) while no guard is hunting you. Heat 40 / 80 sends a
    hunter team to your LAST KNOWN position - not to where you are now.
  * Darkness: guards' sight range scales with how lit Biribel is (street
    lamps, the burning tram, the searchlight, his own muzzle flash). In the
    dark between lamps he is hard to see; the HUD chip says HIDDEN/EXPOSED/
    SPOTTED so the rule is readable.
  * Searchlight at the depot gate sweeps the avenue; being lit alerts
    nearby troopers.
  * Old faces: Kovac and Sandu (east checkpoint) are ex-KRAP. They let
    Biribel walk by - unless he's been killing Guardsmen, or shoots near them.
  * Detained civilian at the south marksman: clear the guards around him
    and he runs; walk past and Vasile notices.
"""
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

from core.config import (TILE_SIZE, font_terminal_small)
from core.state import STATE
from engine.text import T as _T  # T is TILE_SIZE in this module - do not shadow

from missions.m5.meta import C_SYSTEM, C_VASILE, C_GUARD, STAGE_QUARTER
from missions.m5.world import (_radio, _sfx, _spawn_m5_guard, _arm_hunt, _tile_world,
                               _tile_walkable, _solid_walls)
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m5.components import M5Guard as _M5Guard


def _m5g(e):
    """Declared M5 data of an enemy (replaces the ad hoc ``e.m5_*`` attributes)."""
    return _gw.ensure(e, _M5Guard)


T = TILE_SIZE
M5_CONVOY_FRAMES = 12600         # 3.5 min at 60 fps (was 2.5 - too punishing)
SHOT_CONVOY_COST = 20
HEAT_WAVES = (40, 80)            # heat (0-100) that sends hunter teams
HEAT_SPOTTED, HEAT_SHOT_SEEN, HEAT_SHOT, HEAT_KILL, HEAT_LIGHT = 14, 3, 1, 6, 12
HEAT_DECAY = 0.04                # per frame while nobody hunts (2.4 / s)
VIS_DARK = 0.4                   # sight scale in full dark (1.0 = lit)
AWARE_SIGHT = 0.55               # alerted guards' x3 range was map-wide
SEARCH_ORIGIN = (int(9.5 * T), int(13.3 * T))
SEARCH_LEN = 6 * T
SEARCH_HALF = 0.12
OLD_FACES = {"q_31_15": "KOVAC", "q_31_13": "SANDU"}
PATROLS = {
    "q_13_5": [(13, 5), (22, 5), (22, 10), (22, 5), (13, 5), (13, 10)],
    "q_21_17": [(21, 17), (22, 20), (22, 23), (27, 23), (22, 23)],
    "q_23_24": [(23, 24), (32, 24), (32, 19), (32, 24), (23, 24), (13, 24)],
}
CIV_POS = (int(16.3 * T), int(24.5 * T))

_S = {}           # per-run quarter state (owned here; reset in init())
_sprites = {}


def init():
    _S.clear()
    _S.update(convoy=0, heat=0, waves=0, last_shots=_shots(), flash_prev=0,
              late=False, radio50=False, radio80=False, light_cd=0, lit=False,
              civ="held", civ_x=float(CIV_POS[0]), civ_alpha=255, civ_bark=False,
              civ_walked=False, checks=set(), siren=False, faces_spoken=set(),
              faces_cut=False,
              t=0, kills0=int(getattr(STATE, "m5_guard_kills", 0) or 0),
              vis=VIS_DARK, flash_t=0, spotted=False, last_known=None,
              cool=0)
    STATE.m5_convoy_late = False
    STATE.m5_civ_saved = False
    for e in STATE.enemies:
        e.sight_mul = VIS_DARK          # from the very first frame (no 1-frame x1.0 peek)
        lab = _m5g(e).label
        if lab in OLD_FACES:
            _m5g(e).passive = True
            _m5g(e).face = OLD_FACES[lab]
        if lab in PATROLS:
            _apply_patrol(e, PATROLS[lab])


def _apply_patrol(e, tiles):
    pts = [_tile_world(c, r) for c, r in tiles if _tile_walkable(c, r)]
    if len(pts) < 2 or not isinstance(getattr(e, "patrol_points", None), list):
        return
    e.patrol_points = pts
    e.patrol_idx = 0


def _shots():
    return int(getattr(STATE, "shots_fired", 0) or 0)


def _player_c():
    return STATE.player.rect.center if STATE.player is not None else (0, 0)


def _count_shot():
    """Shots fired this frame (stat counter, else muzzle-flash rising edge)."""
    n = _shots()
    d = max(0, n - _S["last_shots"])
    _S["last_shots"] = n
    if d == 0 and not hasattr(STATE, "shots_fired"):
        f = getattr(STATE, "muzzle_flash_timer", 0)
        d = 1 if f > _S["flash_prev"] else 0
        _S["flash_prev"] = f
    return d


def update():
    if not _S or getattr(STATE, "mission5_stage", None) != STAGE_QUARTER or STATE.player is None:
        return
    if getattr(STATE, "m5_dialogue_active", False) or getattr(STATE, "request_m5_cutscene", None) == "old_faces":
        return
    _S["t"] += 1
    px, py = _player_c()
    walls = _solid_walls()
    _update_visibility(px, py)
    shots = _count_shot()
    if shots:
        _S["convoy"] += SHOT_CONVOY_COST * shots
        _S["flash_t"] = 30                       # muzzle flash lights him up
        seen = any(_hunter_sees(e, px, py, walls) for e in _active_guards())
        _add_heat((HEAT_SHOT_SEEN if seen else HEAT_SHOT) * shots, px, py)
        _provoke_faces_by_noise(px, py)
    _update_spotting(px, py, walls)
    kills = int(getattr(STATE, "m5_guard_kills", 0) or 0)
    if kills > _S["kills0"]:
        _add_heat(HEAT_KILL * (kills - _S["kills0"]), px, py)
        _S["kills0"] = kills
    _cool_heat()
    _update_convoy()
    _update_heat(px, py)
    _update_searchlight(px, py)
    _update_faces(px, py)
    if getattr(STATE, "request_m5_cutscene", None):
        return  # cinematic owns the checkpoint beat; no queued barks over it
    _update_civilian(px, py)
    _update_story(px)


def _update_convoy():
    if _S["late"]:
        return
    _S["convoy"] += 1
    frac = _S["convoy"] / M5_CONVOY_FRAMES
    if frac >= 0.5 and not _S["radio50"]:
        _S["radio50"] = True
        _radio("VASILE: Guard convoy just cleared the bridge. Halfway to you. Every shot you "
               "fire, they hear it - and they speed up.", color=C_VASILE, duration=380)
    if frac >= 0.8 and not _S["radio80"]:
        _S["radio80"] = True
        _radio("VASILE: Two streets out. Move, Biribel.", color=C_VASILE, duration=300, priority=1)
    if frac >= 1.0:
        _S["late"] = True
        STATE.m5_convoy_late = True
        _sfx("alarm", 0.3)
        _radio("GUARD RADIO: Convoy on site. Dismount, secure the print works.",
               color=C_GUARD, duration=360)
        for c, r in ((33, 13), (33, 17), (32, 15)):
            if _tile_walkable(c, r):
                _spawn_m5_guard(*_tile_world(c, r), etype="guard", label="convoy", aware=False)


def _far_spawn(px, py):
    best = None
    for c, r in ((3, 4), (12, 4), (22, 4), (31, 4), (3, 25), (12, 25), (22, 25), (31, 25)):
        if not _tile_walkable(c, r):
            continue
        x, y = _tile_world(c, r)
        d = math.hypot(x - px, y - py)
        if d > 700 and (best is None or d < best[0]):
            best = (d, x, y)
    return best


def _active_guards():
    return [e for e in STATE.enemies if e.hp > 0 and not _m5g(e).passive]


def _hunting(e):
    return getattr(e, "state", "") in ("CHASE", "ATTACK")


def _hunter_sees(e, px, py, walls):
    try:
        return e._can_see(px, py, walls)
    except Exception:
        return False


def _add_heat(n, px, py):
    _S["heat"] = min(100.0, _S["heat"] + n)
    _S["last_known"] = (px, py)
    _S["cool"] = 240                              # 4 s before it starts to cool


def _cool_heat():
    if _S["cool"] > 0:
        _S["cool"] -= 1
        return
    if any(_hunting(e) for e in _active_guards()):
        return
    floor = HEAT_WAVES[_S["waves"] - 1] * 0.75 if _S["waves"] else 0.0
    _S["heat"] = max(floor, _S["heat"] - HEAT_DECAY)


def _light_at(px, py):
    """0..1: how lit the player is (lamps / tram fire / searchlight / flash)."""
    if _S["lit"] or _S["flash_t"] > 0:
        return 1.0
    try:
        from missions.m5 import decor as _decor   # lazy: decor is draw-side
        lights = _decor._STAGE_LIGHTS.get(STAGE_QUARTER, ())
    except Exception:
        return 1.0
    best = 0.0
    for lx, ly, r, _col, _kind in lights:
        d = math.hypot(px - lx, py - ly)
        if d < r:
            best = max(best, 1.0 - d / r)
    return min(1.0, best * 1.6)


def _update_visibility(px, py):
    if _S["flash_t"] > 0:
        _S["flash_t"] -= 1
    target = VIS_DARK + (1.0 - VIS_DARK) * _light_at(px, py)
    _S["vis"] += (target - _S["vis"]) * 0.15           # eyes adjust, no popping
    for e in _active_guards():
        aware = e.alerted or getattr(e, "combat_alert_timer", 0) > 0
        e.sight_mul = _S["vis"] * (AWARE_SIGHT if aware else 1.0)


def _update_spotting(px, py, walls):
    """A guard switching to CHASE/ATTACK while he can actually see Biribel
    = SPOTTED: heat, a '!' over him, and the HUD chip turns red."""
    spotted = False
    for e in _active_guards():
        hunting = _hunting(e)
        if hunting and not _m5g(e).hunt_prev and _hunter_sees(e, px, py, walls):
            _add_heat(HEAT_SPOTTED, px, py)
            STATE.floating_texts.append([e.rect.centerx, e.rect.centery - 34, "!",
                                         (236, 70, 56), 50])
        _m5g(e).hunt_prev = hunting
        if hunting and getattr(e, "lost_sight_timer", 99) < 30:
            spotted = True
    _S["spotted"] = spotted


def _investigate(e, pos, spread=None):
    """Send a guard to LOOK at a position (search), not to the live player."""
    spread = T if spread is None else spread
    e.alerted = True
    e.state = "SEARCH"
    e.search_timer = 480
    e.combat_alert_timer = max(getattr(e, "combat_alert_timer", 0), 300)
    e.distraction_target = (pos[0] + _rng_legacy.randint(-spread, spread),
                            pos[1] + _rng_legacy.randint(-spread, spread))
    e.sweep_points = []
    e.path = []
    e.path_timer = 0


def _update_heat(px, py):
    if _S["waves"] >= len(HEAT_WAVES) or _S["heat"] < HEAT_WAVES[_S["waves"]]:
        return
    sp = _far_spawn(px, py)
    if sp is None:
        return
    _S["waves"] += 1
    target = _S["last_known"] or (px, py)
    for k in range(_S["waves"] + 1):     # wave 1 = two guards, wave 2 = three
        e = _spawn_m5_guard(sp[1] + k * 26, sp[2], etype="guard", label="heat", aware=True)
        _investigate(e, target, 2 * T)
    _radio("GUARD RADIO: Shots in the Quarter! Patrol, converge on the avenue."
           if _S["waves"] == 1 else
           "GUARD RADIO: Armed hostile, KRAP uniform. Shoot on sight.",
           color=C_GUARD, duration=320)


def _search_angle():
    return math.pi * 0.0 + 0.75 * math.sin(_S["t"] * 0.011)


def _update_searchlight(px, py):
    if _S["light_cd"] > 0:
        _S["light_cd"] -= 1
    ox, oy = SEARCH_ORIGIN
    dx, dy = px - ox, py - oy
    dist = math.hypot(dx, dy)
    a = _search_angle()
    diff = (math.atan2(dy, dx) - a + math.pi) % (2 * math.pi) - math.pi
    _S["lit"] = 30 < dist < SEARCH_LEN and abs(diff) < SEARCH_HALF
    if _S["lit"] and _S["light_cd"] == 0:
        _S["light_cd"] = 720
        n = 0
        for e in _active_guards():
            if not _hunting(e) and math.hypot(e.rect.centerx - px, e.rect.centery - py) < 380:
                _investigate(e, (px, py))      # they come and LOOK - they don't know
                n += 1
        _add_heat(HEAT_LIGHT, px, py)
        _radio("GATE TOWER: Movement on the avenue - light him up!" if n else
               "GATE TOWER: ...thought I saw something.", color=C_GUARD, duration=240)


def _faces():
    return [e for e in STATE.enemies if _m5g(e).face and e.hp > 0]


def _provoke(e, line=None):
    if not _m5g(e).passive:
        return
    _m5g(e).passive = False
    _arm_hunt(e)
    if line:
        _radio(line, color=C_GUARD, duration=300)


def _provoke_faces_by_noise(px, py):
    for e in _faces():
        if math.hypot(e.rect.centerx - px, e.rect.centery - py) < 450:
            _provoke(e, "%s: You're shooting at OUR people now? Fine!" % _m5g(e).face)


def _update_faces(px, py):
    kills = int(getattr(STATE, "m5_guard_kills", 0) or 0)
    for e in _faces():
        if not _m5g(e).passive:
            continue
        if _m5g(e).hp0 is None:
            _m5g(e).hp0 = e.hp
        if e.hp < _m5g(e).hp0:
            _provoke(e, "%s: Biribel, you bastard!" % _m5g(e).face)
            continue
        if hasattr(e, "angle") and math.hypot(e.rect.centerx - px, e.rect.centery - py) < 300:
            e.angle = math.atan2(py - e.rect.centery, px - e.rect.centerx)
        if math.hypot(e.rect.centerx - px, e.rect.centery - py) < 230 and kills >= 4:
            _S["faces_spoken"].add(_m5g(e).face)
            _provoke(e, "%s: Heard the shooting up the avenue. That was you. "
                     "Sorry, Biribel." % _m5g(e).face)

    # One shared encounter, not two copies of the same radio greeting.
    # Resolve damage/hostility FIRST; never show a friendly dead/provoked actor.
    if _S["faces_cut"] or getattr(STATE, "player_dead", False):
        return
    faces = _faces()
    passive = [e for e in faces if _m5g(e).passive]
    from entities.weapons import _wall_blocks_line  # lazy: collision helper
    walls = _solid_walls()
    near = [e for e in passive if math.hypot(e.rect.centerx - px, e.rect.centery - py) < 230
            and not _wall_blocks_line(px, py, *e.rect.center, walls)]
    if not near or kills >= 4 or getattr(STATE, "request_m5_cutscene", None):
        return
    if any(_hunting(e) and math.hypot(e.rect.centerx - px, e.rect.centery - py) < 450
           for e in _active_guards()):
        return  # don't interrupt a firefight with a friendly conversation
    if any(b.get("owner") == "enemy" and math.hypot(b["x"] - px, b["y"] - py) < 450
           for b in STATE.bullets):
        return
    if len(passive) != 2:
        # A surviving friend gets a truthful, unique line, never the two-person take.
        for e in near:
            if _m5g(e).face not in _S["faces_spoken"]:
                _S["faces_spoken"].add(_m5g(e).face)
                _radio("%s: Keep moving, Biribel. I can't cover you for long." % _m5g(e).face,
                       color=(170, 190, 210), duration=300,
                       mark="old_face_" + _m5g(e).face)
        return
    _S["faces_cut"] = True
    _S["faces_spoken"].update(OLD_FACES.values())
    _S["checks"].add("east")
    from missions.m5 import flow  # lazy: flow loads after quarter
    flow._request_cut("old_faces")


def _update_civilian(px, py):
    st = _S["civ"]
    if st == "held":
        d = math.hypot(px - CIV_POS[0], py - CIV_POS[1])
        if d < 380 and not _S["civ_bark"]:
            _S["civ_bark"] = True
            _radio("DETAINED MAN: I only carried the paper! I don't even read it!",
                   color=(220, 210, 190), duration=300)
        guards_near = any(e.hp > 0 and math.hypot(e.rect.centerx - CIV_POS[0],
                                                  e.rect.centery - CIV_POS[1]) < 260
                          for e in STATE.enemies)
        if not guards_near and d < 300:
            _S["civ"] = "run"
            STATE.m5_civ_saved = True
            _radio("DETAINED MAN: God keep you, soldier. I'm gone - I was never here.",
                   color=(220, 210, 190), duration=320)
        elif px > 27 * T and not _S["civ_walked"]:
            _S["civ_walked"] = True
            _radio("VASILE: They've got a man on his knees by the south lane. ...Keep walking. "
                   "Or don't. Your call.", color=C_VASILE, duration=380)
    elif st == "run":
        _S["civ_x"] -= 2.6
        _S["civ_alpha"] -= 2
        if _S["civ_alpha"] <= 0:
            _S["civ"] = "gone"


def _update_story(px):
    if not _S["siren"] and _S["t"] > 240:
        _S["siren"] = True
        _sfx("alarm", 0.25)
        _radio("LOUDSPEAKER: Curfew is in effect. Citizens found outdoors will be detained. "
               "Report MAG distributors to the Guard.", color=C_SYSTEM, duration=380)
    if px > 15 * T and "mid" not in _S["checks"]:
        _S["checks"].add("mid")
        _radio("VASILE: Tram junction. The shop TV's still running the President. "
               "Don't stop to watch.", color=C_VASILE, duration=320)
    if px > 27 * T and "east" not in _S["checks"]:
        _S["checks"].add("east")
        _radio("VASILE: East checkpoint - that's Kovac and Sandu. Ours, until Monday. "
               "Don't make them choose.", color=C_VASILE, duration=380)


def on_exit():
    if not _S:
        return
    if _S["late"]:
        _radio("VASILE: The convoy beat you. They're already at the doors - find Maru, fast.",
               color=C_VASILE, duration=320)
    else:
        _radio("VASILE: You beat the convoy. Small mercy. Use it.", color=C_VASILE, duration=300)


# ── drawing ──
def _civ_sprite():
    if "civ" not in _sprites:
        s = pygame.Surface((80, 110), pygame.SRCALPHA)
        try:
            from cutscenes import figure_kit  # lazy: heavy cutscene module
            figure_kit.draw_character(s, "civilian", 40, 104, 1.0, False)
        except Exception:
            pygame.draw.circle(s, (200, 170, 140), (40, 30), 10)
            pygame.draw.rect(s, (90, 80, 70), (30, 40, 20, 40))
        _sprites["civ"] = pygame.transform.smoothscale(s, (40, 55))
    return _sprites["civ"]


def draw_world(surface, cam_x, cam_y):
    for d in world_drawables(cam_x, cam_y, surface.get_size()):
        d.draw(surface, 0, 0)


def world_drawables(cam_x, cam_y, size):
    """RPE6 Phase 6: searchlight cone + lamp, the detained civilian - screen-space drawables."""
    if not _S or getattr(STATE, "mission5_stage", None) != STAGE_QUARTER:
        return
    from engine.render2d import (CircleDraw, EllipseDraw, LineDraw, SCREEN,  # lazy: render-only import
                                 SurfaceDraw)
    # searchlight cone
    ox, oy = SEARCH_ORIGIN[0] - cam_x, SEARCH_ORIGIN[1] - cam_y
    a = _search_angle()
    pts = [(ox, oy)] + [(ox + math.cos(a + k) * SEARCH_LEN, oy + math.sin(a + k) * SEARCH_LEN)
                        for k in (-SEARCH_HALF, -SEARCH_HALF / 2, 0, SEARCH_HALF / 2, SEARCH_HALF)]
    cone = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.polygon(cone, (255, 250, 220, 70 if not _S["lit"] else 110), pts)
    yield SurfaceDraw(cone, (0, 0), space=SCREEN)
    yield CircleDraw((int(ox), int(oy)), 7, (255, 250, 230), space=SCREEN)
    # detained civilian
    if _S["civ"] != "gone":
        spr = _civ_sprite()
        x, y = int(_S["civ_x"]) - cam_x, CIV_POS[1] - cam_y
        if _S["civ"] == "held":
            spr = pygame.transform.smoothscale(spr, (40, 40))  # kneeling
            yield EllipseDraw((x - 16, y + 12, 32, 10), (0, 0, 0), space=SCREEN)
            yield SurfaceDraw(spr, (x - 20, y - 24), space=SCREEN)
            yield LineDraw([(x - 6, y - 4), (x + 6, y - 4)], (200, 200, 210), 2, space=SCREEN)  # zip-tie
        else:
            spr = spr.copy()
            spr.set_alpha(max(0, _S["civ_alpha"]))
            yield SurfaceDraw(spr, (x - 20, y - 40), space=SCREEN)


def draw_hud(surface, plate=None):
    """Convoy clock + heat pips. Drawn by m5.draw._draw_hud in the HUD pass
    (after vignette/scanlines) through its shared status-plate helper, so it
    sits in the free top strip instead of hiding under the minimap."""
    if not _S or getattr(STATE, "mission5_stage", None) != STAGE_QUARTER or plate is None:
        return
    frac = min(1.0, _S["convoy"] / M5_CONVOY_FRAMES)
    if _S["late"]:
        title, tcol, fcol, right = (_T("hud.convoy_on_site"), (236, 96, 80),
                                    (220, 60, 50), _T("hud.now"))
    else:
        secs = max(0, int((M5_CONVOY_FRAMES - _S["convoy"]) // 60))
        warn = frac > 0.7
        title = _T("hud.convoy_inbound")
        tcol = (236, 180, 90) if warn else (200, 210, 224)
        fcol = (230, 170, 60) if warn else (120, 220, 170)
        right = _T("hud.clock", m=secs // 60, s="{:02d}".format(secs % 60))
    plate(surface, title, tcol, frac, fcol, right,
          pips=min(5.0, _S["heat"] / 20.0), pips_max=5)
    # Visibility chip under the HOSTILES box: the stealth rule, made readable.
    if _S["spotted"]:
        txt, col, dot = _T("hud.vis_spotted"), (236, 80, 64), False
    elif _S["vis"] > 0.7:
        txt, col, dot = _T("hud.vis_lit"), (232, 184, 96), True
    else:
        txt, col, dot = _T("hud.vis_shadow"), (140, 178, 160), True
    chip = pygame.Surface((180, 22), pygame.SRCALPHA)
    pygame.draw.rect(chip, (0, 0, 0, 120), chip.get_rect())
    surface.blit(chip, (20, 50))
    pygame.draw.circle(surface, col, (32, 61), 5)
    if dot:
        pygame.draw.circle(surface, (10, 12, 14), (32, 61), 2)
    surface.blit(font_terminal_small.render(txt, True, col), (44, 52))
