"""Player interactions with the world: doors, safe, NPCs, alarms."""
import math
import pygame
from core.config import (
    TILE_SIZE, audio, Particle, C_BIRIBEL, C_VOLKOV,
    DOOR_INTERACT_RANGE, DOOR_MANUAL_OVERRIDE, DOOR_OPEN_RANGE,
)
from core.state import STATE
from fx.effects import shake
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
class Door:
    def __init__(self, x, y, is_bay=False):
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.is_bay = is_bay
        self.anim_progress = 0.0
        self.anim_speed = 0.03 if is_bay else 0.1
        self.target_open = False
        self.manual_timer = 0
        self.collision_rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.is_gate = False
        self.locked = False
        self.collision_disabled = False
    @property
    def is_open(self):
        return self.anim_progress >= 1.0
    def toggle(self):
        if self.locked:
            return
        self.target_open = not self.target_open
        self.manual_timer = DOOR_MANUAL_OVERRIDE
    def update(self, player_rect, enemies=None):
        if self.manual_timer > 0:
            self.manual_timer -= 1
        elif not self.is_bay and not self.locked:
            dist = math.hypot(
                player_rect.centerx - self.rect.centerx,
                player_rect.centery - self.rect.centery,
            )
            opened = dist <= DOOR_OPEN_RANGE
            # Chasing guards push through unlocked doors too - otherwise the
            # whole sweep stacks up on a closed panel while the player walks
            # through, which reads as broken AI.
            if not opened and enemies:
                for e in enemies:
                    try:
                        ex, ey = e.rect.centerx, e.rect.centery
                    except Exception:
                        continue
                    if math.hypot(ex - self.rect.centerx,
                                  ey - self.rect.centery) <= DOOR_OPEN_RANGE:
                        opened = True
                        break
            self.target_open = opened
        if self.target_open and self.anim_progress < 1.0:
            self.anim_progress = min(1.0, self.anim_progress + self.anim_speed)
        elif not self.target_open and self.anim_progress > 0.0:
            self.anim_progress = max(0.0, self.anim_progress - self.anim_speed)
        if self.collision_disabled:
            self.collision_rect = None
        else:
            h = max(0, int(TILE_SIZE * (1.0 - self.anim_progress)))
            if h > 0:
                self.collision_rect = pygame.Rect(
                    self.rect.x, self.rect.y, TILE_SIZE, h
                )
            else:
                self.collision_rect = None
def dismiss_note():
    STATE.active_read_note = None
    pygame.mouse.set_visible(False)
def interact_door():
    if not STATE.player or STATE.player_dead:
        return
    closest, closest_dist = None, float("inf")
    for d in STATE.doors:
        dist = math.hypot(
            STATE.player.rect.centerx - d.rect.centerx,
            STATE.player.rect.centery - d.rect.centery,
        )
        if dist <= DOOR_INTERACT_RANGE and dist < closest_dist:
            closest, closest_dist = d, dist
    if closest:
        if closest.locked:
            if closest.is_bay:
                STATE.floating_texts.append([
                    closest.rect.centerx,
                    closest.rect.centery - 20,
                    "BAY DOOR SEALED",
                    (220, 140, 80),
                    70,
                ])
            return
        closest.toggle()
        audio.play(
            "door_open" if closest.is_bay else "door_creak", volume=0.5
        )
        if closest.is_bay:
            for o in STATE.doors:
                if o is not closest and o.is_bay:
                    o.target_open = closest.target_open
                    o.manual_timer = DOOR_MANUAL_OVERRIDE
def handle_interact():
    if not STATE.player or STATE.player_dead:
        return
    for desk in STATE.desks:
        if math.hypot(
            STATE.player.rect.centerx - desk["x"],
            STATE.player.rect.centery - desk["y"],
        ) < 80:
            STATE.active_read_note = desk["clue"]
            desk["read"] = True
            audio.play("pickup", volume=0.5)
            return
    if not STATE.notebook_collected and STATE.NOTEBOOK_POS:
        dist = math.hypot(
            STATE.player.rect.centerx - STATE.NOTEBOOK_POS[0],
            STATE.player.rect.centery - STATE.NOTEBOOK_POS[1],
        )
        if dist < 96:
            if STATE.breach_stage > 0:
                STATE.floating_texts.append([
                    STATE.NOTEBOOK_POS[0], STATE.NOTEBOOK_POS[1] - 20,
                    "BREACH IN PROGRESS!", (255, 100, 30), 90,
                ])
                return
            nearby = [
                e for e in STATE.enemies
                if math.hypot(
                    e.rect.centerx - STATE.NOTEBOOK_POS[0],
                    e.rect.centery - STATE.NOTEBOOK_POS[1],
                ) < 300
            ]
            if not nearby:
                STATE.safe_keypad_active = True
                STATE.safe_keypad_code = ""
                STATE.safe_keypad_target = "742"
                STATE.safe_keypad_callback = _on_safe_opened
                pygame.mouse.set_visible(True)
                audio.play("menu_click", volume=0.5)
            else:
                STATE.floating_texts.append([
                    STATE.NOTEBOOK_POS[0], STATE.NOTEBOOK_POS[1] - 20,
                    "CLEAR HOSTILES FIRST", (220, 60, 60), 90,
                ])
            return
    interact_door()
def _on_safe_opened(success):
    if success:
        STATE.notebook_collected = True
        STATE.floating_texts.append([
            STATE.player.rect.centerx,
            STATE.player.rect.centery - 40,
            "NOTEBOOK ACQUIRED", (50, 200, 100), 120,
        ])
        audio.play("pickup", volume=0.6)
        STATE.request_notebook_inspect = True
        # Lock bay doors - breach will force them open
        for d in STATE.doors:
            if d.is_bay:
                d.locked = True
                d.target_open = False
        # Subtle twist
        trigger_radio_chatter(
            'VASILE: "\u2026Some of this was already in our files."'
        )
        # Start staged breach (not instant - builds over ~6 seconds)
        STATE.breach_stage = 1
        STATE.breach_stage_timer = 0
        STATE.mission_phase = "escape"
        STATE.firefight_triggered = True
        # Make sure all enemies are alert
        for e in STATE.enemies:
            e.alerted = True
            e.state = "CHASE"
    else:
        STATE.floating_texts.append([
            STATE.player.rect.centerx,
            STATE.player.rect.centery - 40,
            "WRONG CODE", (220, 60, 60), 90,
        ])
        # Escalating hints: each failed attempt Biribel thinks a little
        # harder out loud, so puzzle fans still solve it themselves but no
        # one is stuck guessing at the safe forever. The 3rd line and every
        # one after it gives the code outright.
        STATE.safe_keypad_wrong_attempts = (
            getattr(STATE, "safe_keypad_wrong_attempts", 0) + 1)
        n = STATE.safe_keypad_wrong_attempts
        if n == 1:
            line = 'VASILE: "The memos said something about a shipment number\u2026"'
        elif n == 2:
            line = 'BIRIBEL: "Shipment 7742. Only the last three digits."'
        else:
            line = 'BIRIBEL: "7\u2026 4\u2026 2. Has to be."'
        trigger_radio_chatter(line, color=C_BIRIBEL, duration=300, priority=1)
# ── Radio director ────────────────────────────────────────────────
# Transmissions enqueue instead of firing instantly. The per-frame pump
# releases the next message only once the previous one has been on air for
# RADIO_MIN_GAP_MS, so two broadcasts can never be born in the same instant
# (which used to stack HUD bubbles AND stack static/chatter/typing sfx into
# mush). priority=1 lines (objective chain, alarms) jump ahead of priority=0
# flavour (Volkov mag throws, PA chatter).
RADIO_MIN_GAP_MS = 2500
RADIO_QUEUE_MAX = 4
# Breath between a cutscene / dialogue ending and the first held line, so a
# transmission never lands on the same frame control comes back.
RADIO_RESUME_BREATH_MS = (600, 900)
# Subtitle sizing. Recorded lines show for the clip + a short tail; text-only
# lines get a reading time of ~55 ms per character (2.2 s floor).
RADIO_TEXT_MS_PER_CHAR = 55
RADIO_TEXT_MIN_MS = 2200
RADIO_SUBTITLE_TAIL_MS = 450
RADIO_CUT_FADE_MS = 120
_radio_queue = []
_radio_seq = 0
# All radio timing runs on a private clock that only advances while radio is
# allowed. Pause / settings freeze it (VO is paused with them), so a line
# never "finishes" while the game is frozen, and the gap after it is real.
_radio_clock = 0
_radio_last_tick = None
_radio_live_until = 0        # _radio_clock ms; channel busy until then
# The single on-air transmission (or None). ui/radio.py draws from this.
# keys: text, speaker, body, color, start, end, vo_ms, priority
_radio_live = None
_radio_block = None          # current blocker string (None = on air allowed)
_app_state = ""              # FSM state name, fed by app.py each frame
_app_transitioning = False

# FSM states where transmissions may play. Everything else (menus, slot
# select, settings, shop, loading, briefing, every cutscene, notebook,
# pause, death, mission complete) blocks the radio.
RADIO_STATES = ("GAME", "WALK")
# Blocked states that FREEZE the live line instead of cutting it.
RADIO_FREEZE_STATES = ("PAUSED", "SETTINGS")
# In-GAME handoffs: a cutscene has been requested but the FSM has not
# switched yet (the M5 old-faces handoff freezes combat on this flag).
_CUTSCENE_REQUEST_FLAGS = (
    "request_m5_cutscene", "request_escape_cutscene",
    "request_archives_transition_cutscene", "request_broadcast_transition_cutscene",
    "request_chair_break_cutscene", "request_k9_pickup_cutscene",
    "request_ko_transition_cutscene", "request_mission3_fail_cutscene",
    "request_seby_pickup_cutscene", "request_service_transition_cutscene",
    "request_vent_cutscene", "request_volkov_mags_cutscene",
    "request_vostral_pickup_cutscene",
)
# In-GAME conversations / cinematics drawn inside the GAME state.
_DIALOGUE_FLAGS = (
    "walk_dialogue_active", "m4_dialogue_active", "m5_dialogue_active",
    "mission2_evidence_cinematic_active",
)


def radio_blocker(state=None):
    """Why the radio may not speak right now (None = it may)."""
    st = _app_state if state is None else state
    if st and st not in RADIO_STATES:
        return "state:" + st
    if _app_transitioning:
        return "transition"
    for flag in _CUTSCENE_REQUEST_FLAGS:
        if getattr(STATE, flag, None):
            return flag
    for flag in _DIALOGUE_FLAGS:
        if getattr(STATE, flag, False):
            return flag
    if getattr(STATE, "mission_phase", "") == "m3_interrogation":
        return "m3_interrogation"
    if getattr(STATE, "mission2_flank_cutscene_timer", 0) > 0:
        return "mission2_flank_cutscene"
    if getattr(STATE, "player_dead", False):
        return "player_dead"
    import sys
    ws = sys.modules.get("missions.walking_sim")
    if ws is not None and getattr(ws, "walk_dialogue_active", False):
        return "walk_dialogue_active"
    return None


def _is_freeze(blocker):
    return bool(blocker) and blocker.startswith("state:") and \
        blocker[6:] in RADIO_FREEZE_STATES


def radio_allowed(state=None):
    """True when a transmission may start (or keep playing) right now.

    False during every cutscene (2D engine, the *3d sets, m5mid3d, m5martial,
    route12, m3, m4aftermath, oil_rig_3d all run in the CUTSCENE /
    ESCAPE_CUTSCENE states), a pending cutscene handoff, dialogue boxes /
    interrogation, death / fail / complete screens and every menu."""
    return radio_blocker(state) is None


def _split_radio(text):
    try:
        from audio.voice import _split_speaker
        sp, body = _split_speaker(text or "")
    except Exception:
        sp, body = "", text or ""
    return sp, body.strip().strip('"').strip()


def subtitle_ms(text, vo_ms=0):
    """How long a transmission stays on screen."""
    if vo_ms:
        return int(vo_ms) + RADIO_SUBTITLE_TAIL_MS
    _sp, body = _split_radio(text)
    return max(RADIO_TEXT_MIN_MS, RADIO_TEXT_MS_PER_CHAR * len(body))


def _remove_radio_pins():
    STATE.floating_texts[:] = [
        ft for ft in STATE.floating_texts
        if not (len(ft) >= 6 and ft[5] == "pin")]


def _cut_live_line(squelch=True):
    """Kill the on-air line: ~120 ms VO fade, squelch tail, UI gone."""
    global _radio_live, _radio_live_until
    live = _radio_live
    _radio_live = None
    _radio_live_until = _radio_clock
    _remove_radio_pins()
    if live is None:
        return
    if live.get("vo_ms"):
        try:
            from audio import voice
            voice.fade_out(RADIO_CUT_FADE_MS)
        except Exception:
            pass
    try:
        audio.scheduled[:] = [s for s in audio.scheduled
                              if s.get("name") != "type_tick"]
        audio.stop("radio_chatter")
    except Exception:
        pass
    if squelch:
        try:
            audio.play("squelch_tail", volume=0.3)
        except Exception:
            pass


def _drop_flavour():
    _radio_queue[:] = [e for e in _radio_queue if e[0] > 0]


def radio_cutscene_cut():
    """Every cutscene entry calls this (app.start_cutscene, and the pump's
    blocked edge as a safety net): cut the live line, hold critical lines,
    drop flavour."""
    _cut_live_line()
    _drop_flavour()


def clear_radio():
    """Drop queued transmissions (mission start / restart / death)."""
    global _radio_live_until, _radio_live
    _radio_queue.clear()
    _radio_live = None
    _radio_live_until = _radio_clock
    _remove_radio_pins()


def queue_depth():
    return len(_radio_queue)


def live_line():
    """The transmission currently on air (dict) or None."""
    return _radio_live


def radio_clock():
    return _radio_clock


def _radio_release(text, color, duration, priority=0):
    """Put one transmission on air. Returns the voice clip length in ms
    (0 if the line has no recording yet)."""
    global _radio_live
    # Recorded line? Play it through the radio filter. Otherwise fall back
    # to the procedural static + mumble so unvoiced lines still sound like
    # radio. When a voice plays, the static drops way down: the radio filter
    # already adds its own squelch, and a 0.4 static burst on top of it
    # buried the actor.
    vo_ms = 0
    try:
        from audio import voice
        vo_ms = voice.play_line(None, text, radio=True)
    except Exception as exc:
        print(f"[voice] radio VO skipped: {exc}")
    if vo_ms:
        try:
            from audio.voice import RADIO_STATIC_UNDER_VO
        except Exception:
            RADIO_STATIC_UNDER_VO = 0.12
        audio.play("radio_static", volume=RADIO_STATIC_UNDER_VO)
    else:
        audio.play("radio_static", volume=0.4)
        audio.play("radio_chatter", volume=0.3)
    # The widget types the line out, so fake the terminal typing audio
    # with scheduled ticks. Limit count so long radio lines do not become noisy.
    tick_i = 0
    for ch in text:
        if ch and not ch.isspace():
            if tick_i < 34 and (tick_i % 2 == 0 or ch in ".!?"):
                audio.schedule(8 + tick_i * 2, "type_tick", volume=0.085)
            tick_i += 1
    show_ms = subtitle_ms(text, vo_ms)
    speaker, body = _split_radio(text)
    _radio_live = {
        "text": text, "speaker": speaker, "body": body, "color": color,
        "start": _radio_clock, "end": _radio_clock + show_ms,
        "vo_ms": vo_ms, "priority": priority,
    }
    # No floating-text "pin" any more (T6): ui.radio.RadioTransmission reads
    # live_line() and runs on the radio clock, so the on-screen time is
    # subtitle_ms() and the caller's legacy frame duration is ignored (it
    # was why long recorded lines vanished mid-sentence).
    return vo_ms


def trigger_radio_chatter(text, color=(100, 160, 220), duration=360, priority=0):
    """Enqueue a transmission. Back-compatible: priority is optional.

    While the radio is blocked (cutscene, dialogue, menus...) priority 0
    flavour is dropped on the floor and priority > 0 lines are held until
    the block lifts."""
    global _radio_seq
    if priority <= 0:
        blocker = radio_blocker()
        # Fades and pause only hold; cutscenes / dialogue / menus drop flavour.
        if blocker and blocker != "transition" and not _is_freeze(blocker):
            return
    if len(_radio_queue) >= RADIO_QUEUE_MAX:
        for i, entry in enumerate(_radio_queue):
            if entry[0] == 0:          # drop oldest droppable flavour line
                del _radio_queue[i]
                break
        else:                          # queue is all critical: drop oldest
            del _radio_queue[0]
    _radio_seq += 1
    _radio_queue.append((priority, _radio_seq, text, color, duration))
    pump_radio()


def clear_radio_queue():
    """Drop every queued transmission and silence the live one.

    Used when a cutscene takes over: queued barks from the previous beat
    must not type over cutscene captions (KO handoff on the checkpoint
    path hit exactly this).
    """
    _radio_queue.clear()
    _cut_live_line()


def pump_radio(state=None, transitioning=False):
    """Advance the radio clock and release at most one queued transmission.

    Call once per frame with the FSM state name (app.py does). Tests may
    call it bare: the last state given sticks."""
    global _radio_clock, _radio_last_tick, _radio_live_until, _radio_live
    global _radio_block, _app_state, _app_transitioning
    if state is not None:
        _app_state = state
        _app_transitioning = bool(transitioning)
    now = _now_ms()
    dt = 0 if _radio_last_tick is None else max(0, min(250, now - _radio_last_tick))
    _radio_last_tick = now
    blocker = radio_blocker()
    if blocker is not None:
        # Entering a hard block (from on-air or from a freeze, e.g. pause ->
        # quit to menu) cuts the live line; a freeze just stops the clock.
        if not _is_freeze(blocker) and (_radio_block is None
                                        or _is_freeze(_radio_block)
                                        or _radio_block == "transition"):
            _cut_live_line()
            if blocker != "transition":
                _drop_flavour()
        _radio_block = blocker
        return
    if _radio_block is not None:
        was_freeze = _is_freeze(_radio_block)
        _radio_block = None
        if not was_freeze:
            lo, hi = RADIO_RESUME_BREATH_MS
            breath = lo + (_radio_seq * 97) % (hi - lo + 1)
            _radio_live_until = max(_radio_live_until, _radio_clock + breath)
    _radio_clock += dt
    if _radio_live is not None and _radio_clock >= _radio_live["end"]:
        _radio_live = None
    if _radio_clock < _radio_live_until or not _radio_queue:
        return
    _radio_queue.sort(key=lambda e: (-e[0], e[1]))
    pri, _seq, text, color, duration = _radio_queue.pop(0)
    vo_ms = _radio_release(text, color, duration, pri) or 0
    # Hold the channel for the entire subtitle, not just the VO/minimum gap.
    # Unvoiced lines used to be replaced while the widget was still typing.
    readable_until = _radio_live["end"] if _radio_live else _radio_clock
    _radio_live_until = max(_radio_clock + RADIO_MIN_GAP_MS,
                            _radio_clock + vo_ms + 350, readable_until + 650)


def trigger_alarm_early():
    if STATE.stealth_failed:
        return
    STATE.stealth_failed = True
    STATE.firefight_triggered = True
    STATE.mission_phase = "firefight"
    STATE.quiet_entry = False
    # Cancel any active sighting
    if STATE.volkov_sighting_timer > 0:
        STATE.volkov_sighting_timer = 0
    # Start Volkov escape if he hasn't left yet
    if not STATE.volkov_escaped and STATE.volkov_pos:
        STATE.volkov_escape_pos = list(STATE.volkov_pos)
        STATE.volkov_escape_timer = 90
        trigger_radio_chatter(
            'VOLKOV: "Read it before you hand it over!"',
            color=C_VOLKOV, priority=1,
        )
    STATE.volkov_escaped = False
    STATE.commander_escaped = False
    shake(12)
    audio.play("alarm", volume=0.5, loops=0)
    for e in STATE.enemies:
        e.alerted = True
        e.state = "CHASE"
    STATE.floating_texts.append([
        STATE.player.rect.centerx,
        STATE.player.rect.centery - 40,
        "ALARM TRIGGERED!", (220, 60, 60), 120,
    ])
    STATE.radio_chatter_stage = 1
    trigger_radio_chatter(
        'VASILE: "Biribel, they spotted you! Alarm is active!"'
    )
def trigger_mag_ambush():
    """Execute the actual breach - spawn MAG enemies, blow bay doors."""
    from entities.enemy_ai import Enemy
    STATE.radio_chatter_stage = 6
    shake(28)
    audio.play("explosion", volume=0.8)
    audio.play("breach", volume=0.7)
    # Block the stairs
    STATE.walls.append(pygame.Rect(
        2 * TILE_SIZE, 23 * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    STATE.walls.append(pygame.Rect(
        3 * TILE_SIZE, 23 * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    # Force bay doors open
    for d in STATE.doors:
        if d.is_bay:
            d.locked = False
            d.target_open = True
            d.anim_progress = 1.0
            d.collision_disabled = True
            d.manual_timer = 9999
    # Spawn MAG enemies
    spawns = [
        (14 * TILE_SIZE + 16, 25 * TILE_SIZE + 16),
        (16 * TILE_SIZE + 16, 25 * TILE_SIZE + 16),
    ]
    # Stealth penalty: extra enemy if alarm was triggered early
    if not STATE.quiet_entry:
        spawns.append((15 * TILE_SIZE + 16, 25 * TILE_SIZE + 16))
    for mx, my in spawns:
        e = Enemy(mx, my)
        e.alerted = True
        e.state = "CHASE"
        e.last_seen_pos = (14 * TILE_SIZE + 32, 22 * TILE_SIZE + 32)
        e.is_ambush_enemy = True
        e.hp = 80
        e.fire_cooldown = 90
        STATE.enemies.append(e)
        for _ in range(25):
            STATE.particles.append(Particle(mx, my, (180, 180, 180)))
        for _ in range(15):
            STATE.particles.append(Particle(mx, my, (255, 120, 30)))
        STATE.breach_markers.append([mx, my, 180])
    trigger_radio_chatter(
        'VASILE: "They blocked the stairs! Hotwire the delivery truck!"'
    )
