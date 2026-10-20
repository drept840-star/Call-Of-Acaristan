"""Mission 2 - "Route 12 Kill-Box": the sniper ambush as a low-poly 3D film.

Triggered exactly where the old in-engine sequence was (the blue toll
barrier marker after the clues). Plays full-screen, then hands back to the
existing aftermath (get-to-cover fight) and Seby's OS-12 pickup cutscene.

SYNC MODEL
    The whole film is one timeline built at start-up. Every dialogue line
    is placed with a cursor and lasts exactly as long as its recorded VO
    clip (header-read, + radio squelch tail), or a reading-time estimate
    when the line isn't recorded yet. Kills, cuts and camera moves are
    anchored to those line ends - so "Vasile, I have-" is cut off by the
    round on the actual last syllable, whatever take you drop in.
    Lines bypass the in-game radio director (no queue, no muffling):
    in-person lines play clean, Vasile is on the radio.
"""
import math
import random

import pygame

from core.config import WIDTH, HEIGHT, audio, font_dialogue, font_speaker, font_prompt
from engine3d import (Humanoid, POSES, Renderer, blend, box, clamp, disc_xz,
                      ease_in_out, ease_out, lerp, m_apply, m_mul, mix_col,
                      os12_mesh, pose_crawl, pose_drag, pose_run, rifle_mesh, rot_x, rot_y,
                      rot_z, smooth, v_add, v_lerp, v_sub, v_len, v_norm)
from missions.m2 import sniper3d_set as SET
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

RES_DIV = 2                    # internal render = WIDTH/2 x HEIGHT/2, nearest upscale
BAR_H = 74                     # letterbox bars (final pixels)

C_VASILE = (100, 160, 220)
SPEAKER_COL = {"VASILE": C_VASILE, "GABI": (220, 175, 70), "SEBY": (85, 170, 225),
               "DARIUS": (110, 220, 145)}

KRAP_JACKET = (55, 65, 80)
KRAP_PANTS = (35, 42, 55)
KRAP_VEST = (44, 50, 50)

SPECS = {
    "gabi": dict(skin=(196, 156, 122), hair=(58, 38, 28), jacket=KRAP_JACKET, vest=KRAP_VEST,
                 pants=KRAP_PANTS, boots=(16, 16, 18), accent=(220, 175, 70),
                 glove=(30, 32, 34), stubble=True, rifle="rifle"),
    "seby": dict(skin=(178, 138, 108), hair=(30, 26, 22), jacket=KRAP_JACKET, vest=KRAP_VEST,
                 pants=KRAP_PANTS, boots=(16, 16, 18), accent=(85, 170, 225),
                 glove=(30, 32, 34), beanie=(38, 42, 50), rifle="os12"),
    "darius": dict(skin=(150, 112, 86), hair=(18, 16, 15), jacket=KRAP_JACKET, vest=KRAP_VEST,
                   pants=KRAP_PANTS, boots=(16, 16, 18), accent=(110, 220, 145),
                   glove=(30, 32, 34), pack=(54, 62, 46), rifle="rifle"),
    "biribel": dict(skin=(190, 150, 116), hair=(25, 30, 28), jacket=(40, 50, 45),
                    vest=(28, 35, 30), pants=(30, 35, 40), boots=(12, 12, 14),
                    accent=(35, 65, 110), glove=None,
                    # face/hair kept in sync with cutscenes.figure_kit SPECS["biribel"]
                    hair_style="curly", iris=(35, 45, 55), ears=True, brow_t=3,
                    stubble=True, stubble_t=.18, pouches=True, belt=(14, 16, 18),
                    buckle=(174, 155, 106)),
    "sniper": dict(skin=(120, 100, 84), hair=(10, 10, 10), jacket=(34, 38, 30), vest=(30, 34, 26),
                   pants=(32, 34, 28), boots=(12, 12, 12), accent=(30, 34, 26),
                   glove=(14, 14, 14), hood=(30, 34, 26), ghillie=(40, 44, 32), rifle="sniper"),
}

# ── line lengths ────────────────────────────────────────────────────────


def _line_seconds(speaker, text, radio):
    """Real clip length when recorded, else a reading-time estimate."""
    try:
        from audio import voice
        vo = voice.find_line(speaker, text)
        if vo and voice.has_file(vo):
            d = voice._duration(voice._files[vo])
            if d:
                return d + (0.23 if radio else 0.0)
    except Exception:
        pass
    return 0.55 + 0.062 * len(text)


SHOT_LEAD = 0.12      # round lands this long before a recorded scream starts


def _kill_at(line, who):
    """When the round hits a speaker cut off mid-line.

    Normally the last syllable of the clip. If the actor's scream was
    recorded onto the end of the clip, the shot lands where the scream
    starts instead (otherwise they'd scream BEFORE being hit). A separate
    death-scream file always plays on the hit itself."""
    try:
        from audio import voice
        if voice.death_file(who) is None:
            cut = voice.scream_onset(line.speaker, line.text)
            if cut is not None:
                return line.start + max(0.2, cut - SHOT_LEAD)
    except Exception:
        pass
    return line.end - 0.03


def _prewarm(lines):
    """Decode / radio-process every clip in the background so playback
    starts on the exact frame (the radio filter is pure Python)."""
    def work():
        try:
            from audio import voice
            for sp, tx, radio in lines:
                vo = voice.find_line(sp, tx)
                if vo and voice.has_file(vo):
                    voice._load(vo, radio)
        except Exception:
            pass
    try:
        import threading
        threading.Thread(target=work, daemon=True).start()
    except Exception:
        work()


# ── small helpers ───────────────────────────────────────────────────────

def seg(t, a, b):
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def path_at(pts, u):
    """Point along a polyline (x, z) at fraction u, plus heading yaw."""
    if len(pts) == 1:
        return pts[0], 0.0
    L = [0.0]
    for i in range(1, len(pts)):
        L.append(L[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    d = clamp(u) * L[-1]
    for i in range(1, len(pts)):
        if d <= L[i] or i == len(pts) - 1:
            k = 0.0 if L[i] == L[i - 1] else (d - L[i - 1]) / (L[i] - L[i - 1])
            k = clamp(k)
            a, b = pts[i - 1], pts[i]
            p = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            yaw = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
            return p, yaw
    return pts[-1], 0.0


def path_len(pts):
    return sum(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
               for i in range(1, len(pts)))


def lerp_yaw(a, b, t):
    d = (b - a + 180) % 360 - 180
    return a + d * t


def pose_walk(phase, base="ready"):
    s = math.sin(phase)
    c = math.cos(phase)
    p = dict(POSES[base])
    p.update(lhip_p=22 * s + 3, rhip_p=-22 * s + 3, lkn=8 + 30 * max(0.0, -c),
             rkn=8 + 30 * max(0.0, c), lift=0.0)
    return p


def keyed_pose(keys, t):
    """keys: [(time, pose_name_or_dict)] -> blended pose at t."""
    if t <= keys[0][0]:
        k = keys[0][1]
        return dict(POSES[k]) if isinstance(k, str) else dict(k)
    for i in range(1, len(keys)):
        if t <= keys[i][0]:
            t0, a = keys[i - 1]
            t1, b = keys[i]
            return blend(a, b, ease_in_out((t - t0) / (t1 - t0)))
    k = keys[-1][1]
    return dict(POSES[k]) if isinstance(k, str) else dict(k)


# ── timeline ────────────────────────────────────────────────────────────

class _Line:
    __slots__ = ("speaker", "text", "radio", "start", "end", "played")

    def __init__(self, speaker, text, radio, start, dur):
        self.speaker, self.text, self.radio = speaker, text, radio
        self.start, self.end = start, start + dur
        self.played = False


# Darius radios it in lying flat, propped on his right elbow, handset to his ear
DARIUS_REACH = dict(body_p=86, spine=-6, head_p=-40, lsh_p=170, lsh_r=14, lel=10,
                    rsh_p=150, rsh_r=24, rel=60, lhip_p=8, lhip_r=14, lkn=24, rhip_p=4,
                    rhip_r=14, rkn=36, rifle_p=0)
DARIUS_MAYDAY = dict(body_p=80, spine=-10, head_p=-46, head_y=-16, lsh_p=160, lsh_r=62, lel=150,
                     rsh_p=105, rsh_r=10, rel=85, lhip_p=6, lhip_r=12, lkn=16, rhip_p=4,
                     rhip_r=14, rkn=34, rifle_p=0)
DARIUS_DEAD = dict(body_p=89, spine=-2, head_p=-12, head_y=65, lsh_p=12, lsh_r=26, lel=12,
                   rsh_p=165, rsh_r=36, rel=12, lhip_p=4, lhip_r=10, lkn=10, rhip_p=-2,
                   rhip_r=16, rkn=28, rifle_p=0)

OS12_GRIP = (0, -0.09, 0.0)              # pistol grip / handguard on os12_mesh()
OS12_FORE = (0, -0.02, 0.29)

FPV_SHOTS = ("pk_body", "pk_reach", "pk_raise")


class SniperCinematic:
    def __init__(self):
        self.t = 0.0
        self.done = False
        self._last_ms = _now_ms()
        self._skip_hold = 0.0
        self._rng = random.Random(7)
        self.w, self.h = WIDTH // RES_DIV, HEIGHT // RES_DIV
        self.r = Renderer(self.w, self.h, fog=(88, 90, 98), fog_start=14.0, fog_end=190.0)
        self.handles = SET.build(self.r)
        self.sky, self.sky_hy = SET.sky(self.w, 1200)
        self.actors = {k: Humanoid(v) for k, v in SPECS.items()}
        self.loose_rifle = rifle_mesh(scope=False)
        self.loose_os12 = os12_mesh()
        self.vm_os12 = os12_mesh()
        self.parts = []          # particles
        self.tracers = []        # (t0, a, b)
        self.flash_t = -9.0
        self.shake_t, self.shake_amp = -9.0, 0.0
        self._fired = set()
        self._rain = [(self._rng.random(), self._rng.random(), self._rng.uniform(.6, 1.0))
                      for _ in range(170)]
        self._vign = self._make_vignette()
        self._gabi_rest_c = None
        self._build_timeline()
        sn = self._actor_state("sniper", 0.0)
        _, j, _ = self.actors["sniper"].pose_world(sn["pose"], sn["pos"], sn["yaw"])
        self.muzzle_pt = j["muzzle"]
        self.scope_pt = (j["rhand"][0], j["rhand"][1] + 0.16, j["rhand"][2] + 0.25)
        _prewarm([(l.speaker, l.text, l.radio) for l in self.lines])

    # ── schedule ──────────────────────────────────────────────────────
    def _build_timeline(self):
        self.lines = []

        def line(sp, tx, at, radio=False):
            l = _Line(sp, tx, radio, at, _line_seconds(sp, tx, radio))
            self.lines.append(l)
            return l

        T = {}
        # M6 plant (docs/MISSION8_PLOT.md "Foreshadowing to Retrofit"): Vasile
        # clears the lane himself.  The voice that says "I checked it myself"
        # is the voice the convoy route went out on.
        L0 = line("VASILE", "Route's clean. I checked it myself.", 0.35, radio=True)
        L1 = line("VASILE", "Form up at the barrier. Eyes up.", L0.end + 0.45, radio=True)
        L2 = line("GABI", "Nobody likes this lane.", L1.end + 0.5)
        L3 = line("SEBY", "West side's clear. Just burned-out cars.", L2.end + 0.4)
        L4 = line("GABI", "Vasile, I have-", L3.end + 1.0)
        K1 = _kill_at(L4, "gabi")                              # round lands on the cut-off
        L5 = line("VASILE", "Everybody DOWN. Do not move.", K1 + 4.0, radio=True)
        L6 = line("SEBY", "GABI! NO!", L5.end + 0.75)
        L7 = line("VASILE", "Seby - stay low - do NOT go out there.", L6.end + 0.3, radio=True)
        grab = max(L6.end + 1.75, L7.end - 0.4)
        L8 = line("SEBY", "Hold on - I got you - I GOT YOU-", max(L7.end + 0.2, grab + 0.1))
        K2 = _kill_at(L8, "seby")
        L9 = line("VASILE", "Biribel. Stay behind the barrier. Do not look up.", K2 + 1.7, radio=True)
        crawl0 = L9.end - 0.4
        crawl1 = crawl0 + 2.4
        L10 = line("DARIUS", "Mayday, mayday, this is-", crawl1 + 0.55)
        K3 = _kill_at(L10, "darius")
        K4 = K3 + 3.9
        L11 = line("VASILE", "Biribel - MOVE!", K4 + 0.35, radio=True)
        # Biribel takes Seby's OS-12 (was the old 2D pickup cutscene)
        P0 = L11.end + 0.55                    # crawl to the gap
        P1 = P0 + 2.15                         # FPV: Seby's body
        P2 = P1 + 2.2                          # FPV: reach for the rifle
        G = P2 + 1.35                          # hands close on it
        P3 = P2 + 1.9                          # FPV: raise + inspect
        END = P3 + 4.0
        T.update(P0=P0, P1=P1, P2=P2, P3=P3, G=G)
        T.update(L0=L0, L1=L1, L2=L2, L3=L3, L4=L4, L5=L5, L6=L6, L7=L7, L8=L8, L9=L9, L10=L10, L11=L11,
                 K1=K1, K2=K2, K3=K3, K4=K4, grab=grab, crawl0=crawl0, crawl1=crawl1, END=END,
                 glint=K1 + 3.4, dive=L5.start + 0.55, seby_go=L6.end + 0.12)
        T["seby_arrive"] = grab - 0.25
        self.T = T
        self.duration = END
        # Shots: (start, end, name)
        S = []
        S.append((0.0, L1.end + 0.4, "establish"))
        S.append((L1.end + 0.4, L2.end + 0.2, "gabi_lane"))
        S.append((L2.end + 0.2, L3.end + 0.5, "seby_west"))
        S.append((L3.end + 0.5, K1 + 1.5, "gabi_radio"))
        S.append((K1 + 1.5, T["glint"] - 0.5, "dead_air"))
        S.append((T["glint"] - 0.5, T["dive"], "glint"))
        S.append((T["dive"], L5.end + 0.65, "dive"))
        S.append((L5.end + 0.65, T["seby_go"] + 0.08, "seby_close"))
        S.append((T["seby_go"] + 0.08, grab + 0.2, "sprint"))
        # scope on Seby for a clear 1.6 s before the shot (shorter only if he
        # dies very early in his line; the drag always gets a beat first)
        sc0 = K2 - 1.6
        if sc0 < grab + 0.8:
            sc0 = max(grab + 0.45, K2 - 0.9)
        S.append((grab + 0.2, sc0, "drag"))
        S.append((sc0, K2 + 0.1, "scope_seby"))
        S.append((K2 + 0.1, K2 + 2.0, "seby_down"))
        S.append((K2 + 2.0, crawl0 + 0.5, "biribel_cover"))
        S.append((crawl0 + 0.5, K3 + 1.6, "darius"))
        S.append((K3 + 1.6, K4 + 0.06, "scope_biribel"))
        S.append((K4 + 0.06, P0, "near_miss"))
        S.append((P0, P1, "pk_crawl"))
        S.append((P1, P2, "pk_body"))
        S.append((P2, P3, "pk_reach"))
        S.append((P3, END - 0.6, "pk_raise"))
        S.append((END - 0.6, END + 1.0, "black"))
        self.shots = S

    # ── public API ──────────────────────────────────────────────────────
    def skip(self):
        try:
            from audio import voice
            voice.stop()
        except Exception:
            pass
        self.t = self.duration
        self.done = True

    def update(self):
        now = _now_ms()
        dt = clamp((now - self._last_ms) / 1000.0, 0.0, 0.1)
        self._last_ms = now
        if self.done:
            return
        try:
            keys = pygame.key.get_pressed()
            held = keys[pygame.K_SPACE] or keys[pygame.K_RETURN]
        except Exception:
            held = False
        self._skip_hold = self._skip_hold + dt if held else 0.0
        if self._skip_hold > 0.9:
            self.skip()
            return
        prev = self.t
        self.t += dt
        self._events(prev, self.t)
        self._update_particles(dt)
        if self.t >= self.duration:
            self.done = True

    # ── events / audio ───────────────────────────────────────────────────
    def _once(self, name, prev, now, at):
        if prev < at <= now and name not in self._fired:
            self._fired.add(name)
            return True
        return False

    def _events(self, prev, now):
        T = self.T
        for l in self.lines:
            if not l.played and now >= l.start:
                l.played = True
                ms = 0
                try:
                    from audio import voice
                    ms = voice.play_line(l.speaker, l.text, radio=l.radio)
                except Exception:
                    pass
                if l.radio and not ms:          # recorded radio clips carry their own squelch
                    audio.play("squelch_head", volume=0.25)
        if self._once("static", prev, now, 0.6):
            audio.play("radio_static", volume=0.18)
        # M6 plant: Vasile's channel dies for half a second in the gap before
        # the first round lands.  The player hears the shooter on his
        # frequency; in M6 they learn the convoy route went out on it too.
        if self._once("vasile_dead_air", prev, now, T["L3"].end + 0.05):
            audio.play("radio_static", volume=0.22)
        for who, k in (("gabi", "K1"), ("seby", "K2"), ("darius", "K3")):
            if self._once("scream_" + who, prev, now, T[k] + 0.06):
                try:
                    from audio import voice
                    voice.play_death(who)
                except Exception:
                    pass
        if self._once("k1", prev, now, T["K1"]):
            self._kill_fx("gabi", near=True)
            audio.play("bullet_snap", volume=0.9)
            audio.duck_for_radio(frames=240, factor=0.10)
        if self._once("k1_report", prev, now, T["K1"] + 0.2):
            audio.play("sniper_crack", volume=0.75)
        if self._once("k1_tinnitus", prev, now, T["K1"] + 0.3):
            audio.play("tinnitus", volume=0.45)
        if self._once("dive", prev, now, T["dive"] + 0.55):
            audio.play("melee_hit", volume=0.35)
        if self._once("k2", prev, now, T["K2"]):
            self._kill_fx("seby", near=False)
            audio.play("trailer_sniper_stack", volume=0.85)
        if self._once("k2_snap", prev, now, T["K2"] + 0.12):
            audio.play("bullet_snap", volume=0.5)
        if self._once("k3", prev, now, T["K3"]):
            self._kill_fx("darius", near=True)
            audio.play("bullet_snap", volume=0.85)
        if self._once("k3_report", prev, now, T["K3"] + 0.2):
            audio.play("sniper_crack", volume=0.7)
        if self._once("k3_hiss", prev, now, T["K3"] + 0.45):
            audio.play("radio_static", volume=0.32)
        if self._once("k4", prev, now, T["K4"]):
            audio.play("trailer_sniper_stack", volume=0.9)
            self.flash_t = now
        if self._once("k4_hit", prev, now, T["K4"] + 0.07):
            audio.play("concrete_impact", volume=1.0)
            audio.play("bullet_snap", volume=0.7)
            self._impact_fx((self.BIRIBEL_HOME[0] + 0.15, 0.84, SET.BARRIER_Z + 0.05))
            self.shake_t, self.shake_amp = now, 0.20
        if self._once("k4_heart", prev, now, T["K4"] + 0.5):
            audio.play("heartbeat", volume=0.6)
        for i in range(3):
            if self._once("pk_crawl%d" % i, prev, now, T["P0"] + 0.5 + i * 0.65):
                audio.play("footstep_walk", volume=0.18)
        if self._once("pk_heart", prev, now, T["P1"] + 0.2):
            audio.play("heartbeat", volume=0.75)
        if self._once("pk_grab", prev, now, T["G"]):
            audio.play("melee_hit", volume=0.22)
        if self._once("pk_heart2", prev, now, T["P3"] + 0.1):
            audio.play("heartbeat", volume=0.5)
        if self._once("pk_check", prev, now, T["P3"] + 1.0):
            audio.play("rifle_handle", volume=0.6)

    def _kill_fx(self, who, near):
        t = self.t
        self.flash_t = t
        self.shake_t, self.shake_amp = t, 0.09 if near else 0.04
        st = self._actor_state(who, t + 0.01)
        _, j, _ = self.actors[who].pose_world(st["pose"], st["pos"], st["yaw"], rifle_on=False)
        hit = j["chest"]
        self.tracers.append((t, self.muzzle_pt, hit))
        rng = self._rng
        d = v_norm(v_sub(hit, self.muzzle_pt))
        for _ in range(34):
            v = (d[0] * rng.uniform(1, 4) + rng.uniform(-1.2, 1.2), rng.uniform(-0.3, 2.2),
                 d[2] * rng.uniform(1, 4) + rng.uniform(-1.2, 1.2))
            self.parts.append(dict(p=hit, v=v, life=rng.uniform(0.35, 0.9), age=0.0,
                                   col=(rng.randint(110, 160), 10, 12), size=rng.uniform(.025, .06),
                                   g=6.0))
        for _ in range(8):
            self.parts.append(dict(p=hit, v=(d[0] * 1.5, rng.uniform(0, .5), d[2] * 1.5),
                                   life=0.5, age=0.0, col=(150, 30, 30), size=0.09, g=0.0,
                                   mist=True))

    def _impact_fx(self, p):
        rng = self._rng
        for _ in range(46):
            v = (rng.uniform(-2.5, 2.5), rng.uniform(1.0, 4.5), rng.uniform(-3.5, -0.5))
            c = rng.randint(120, 175)
            self.parts.append(dict(p=p, v=v, life=rng.uniform(0.5, 1.2), age=0.0,
                                   col=(c, c - 4, c - 12), size=rng.uniform(.02, .07), g=9.0))
        for _ in range(10):
            self.parts.append(dict(p=p, v=(rng.uniform(-.6, .6), rng.uniform(.3, 1.2), rng.uniform(-1, .2)),
                                   life=1.4, age=0.0, col=(150, 146, 136), size=0.12, g=0.0,
                                   mist=True))
        self.parts.append(dict(p=p, v=(0, 0, 0), life=0.09, age=0.0, col=(255, 240, 200),
                               size=0.5, g=0.0, spark=True))

    def _update_particles(self, dt):
        keep = []
        for q in self.parts:
            q["age"] += dt
            if q["age"] >= q["life"]:
                continue
            v = q["v"]
            p = q["p"]
            v = (v[0] * (1 - 0.8 * dt), v[1] - q["g"] * dt, v[2] * (1 - 0.8 * dt))
            p = (p[0] + v[0] * dt, max(0.01, p[1] + v[1] * dt), p[2] + v[2] * dt)
            q["v"], q["p"] = v, p
            keep.append(q)
        self.parts = keep

    # ── actors ──────────────────────────────────────────────────────────
    # Positions (x, z) in metres - see sniper3d_set for the layout.
    GABI_HOME = (-1.6, 10.6)
    SEBY_HOME = (2.2, 9.9)
    DARIUS_HOME = (5.2, 9.4)
    BIRIBEL_HOME = (-5.0, 5.15)
    SEBY_COVER = (3.4, 5.2)
    DARIUS_COVER = (6.6, 5.2)
    GABI_TURN = 212.0                 # he turns back toward Biribel to call it in

    PK_KNEEL = (-0.6, 4.45)               # Biribel kneels here, at the gap edge
    PK_EYE = (-0.52, 1.0, 4.42)
    PK_RIFLE = (0.42, 0.04, 4.98)         # Seby's OS-12, slid off his sling
    PK_RIFLE_YAW = 200

    def _actor_state(self, who, t):
        """-> dict(pos, yaw, pose, rifle, dead?, handset?) for one actor at t."""
        T = self.T
        if who == "gabi":
            walk = [(-2.2, -3.0), (-2.0, 3.6), self.GABI_HOME]
            if t < 5.0:
                u = seg(t, 0.2, 5.0)
                (x, z), yaw = path_at(walk, ease_out(u))
                pose = pose_walk(path_len(walk) * ease_out(u) * 4.2) if u < 0.97 else POSES["ready"]
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=True)
            x, z = self.GABI_HOME
            if t < T["L4"].start - 0.5:
                return dict(pos=(x, 0, z), yaw=4 + 4 * math.sin(t * .7), pose=POSES["ready"], rifle=True)
            if t < T["K1"]:
                u = smooth(seg(t, T["L4"].start - 0.5, T["L4"].start + 0.2))
                return dict(pos=(x, 0, z), yaw=lerp_yaw(4, self.GABI_TURN, u),
                            pose=blend("ready", "talk_turn", u), rifle=True)
            k = t - T["K1"]
            if t < T["grab"]:
                # hit from behind (north): pitched forward onto his face
                pose = keyed_pose([(0, "talk_turn"),
                                   (0.10, dict(POSES["talk_turn"], spine=-12, head_p=-30, lsh_r=80, rsh_r=60)),
                                   (0.75, dict(POSES["kneel_over"], head_p=40, lsh_p=10, rsh_p=0, lel=10, rel=10)),
                                   (1.45, "dead_front")], k)
                fwd = 0.75 * smooth(seg(k, 0.6, 1.45))
                yr = math.radians(self.GABI_TURN)
                return dict(pos=(x + math.sin(yr) * fwd, 0, z + math.cos(yr) * fwd),
                            yaw=self.GABI_TURN, pose=pose, rifle=k < 0.35, dead=True)
            # Seby has him: flipped onto his back, head toward Seby
            sb = self._actor_state("seby", t)
            sy = math.radians(sb["yaw"])
            px = sb["pos"][0] + math.sin(sy) * 1.5
            pz = sb["pos"][2] + math.cos(sy) * 1.5
            u = seg(t, T["grab"], T["grab"] + 0.45)
            pose = blend("dead_front", "carried", smooth(u))
            if t > T["K2"] + 0.25:
                pose = blend("carried", "dead_back", seg(t, T["K2"] + 0.25, T["K2"] + 1.2))
            return dict(pos=(px, 0, pz), yaw=sb["yaw"], pose=pose, rifle=False, dead=True)

        if who == "seby":
            walk = [(1.2, -4.0), (1.0, 3.6), self.SEBY_HOME]
            hx, hz = self.SEBY_HOME
            if t < 5.3:
                u = seg(t, 0.35, 5.3)
                (x, z), yaw = path_at(walk, ease_out(u))
                pose = pose_walk(path_len(walk) * ease_out(u) * 4.0) if u < 0.97 else POSES["ready"]
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=True)
            L3 = T["L3"]
            if t < T["K1"]:
                u = seg(t, L3.start - 0.6, L3.start)
                yaw = lerp_yaw(0, -72, smooth(u))
                aiming = u > 0.5 and t < L3.end + 0.3
                if t > L3.end + 0.3:
                    yaw = lerp_yaw(-72, -10, smooth(seg(t, L3.end + 0.3, L3.end + 1.0)))
                return dict(pos=(hx, 0, hz), yaw=yaw, pose=POSES["aim" if aiming else "ready"], rifle=True)
            dv = T["dive"]
            cx, cz = self.SEBY_COVER
            if t < dv:
                u = seg(t, T["K1"] + 0.3, T["K1"] + 1.0)
                return dict(pos=(hx, 0, hz), yaw=lerp_yaw(-10, -120, smooth(u)),
                            pose=blend("ready", "stand", u), rifle=True)
            if t < dv + 0.7:
                u = seg(t, dv, dv + 0.7)
                x, z = lerp(hx, cx, ease_out(u)), lerp(hz, cz, ease_out(u))
                pose = keyed_pose([(0, "ready"), (0.25, "dive"), (0.7, "cover_tight")], t - dv)
                return dict(pos=(x, 0, z), yaw=lerp_yaw(-120, 175, u), pose=pose, rifle=True)
            go = T["seby_go"]
            if t < go:
                peek = t > T["L6"].start - 0.3
                return dict(pos=(cx, 0, cz),
                            yaw=lerp_yaw(175, -20, smooth(seg(t, T["L6"].start - 0.3, T["L6"].start + 0.2))),
                            pose=POSES["cover" if peek else "cover_tight"], rifle=True)
            gx, gz = self._gabi_rest()
            kneel_at = (gx - 0.4, gz - 1.6)
            run = [(cx, cz), (1.6, 5.3), (1.6, 7.0), kneel_at]
            arrive = T["seby_arrive"]
            if t < arrive:
                u = seg(t, go, arrive)
                (x, z), yaw = path_at(run, u)
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose_run(path_len(run) * u * 3.2, lean=22),
                            rifle=False)
            face = math.degrees(math.atan2(gx - kneel_at[0], gz - kneel_at[1]))
            if t < T["grab"]:
                u = smooth(seg(t, arrive, T["grab"]))
                return dict(pos=(kneel_at[0], 0, kneel_at[1]), yaw=lerp_yaw(path_at(run, 1)[1], face, u),
                            pose=blend("kneel", "kneel_over", u), rifle=False)
            drag_path = [kneel_at, (1.4, 6.9), (1.6, 5.2)]
            span = T["K2"] + 1.4                     # he never makes it
            if t < T["K2"]:
                u = seg(t, T["grab"], span)
                (x, z), _ = path_at(drag_path, ease_in_out(u) * 0.95)
                yaw = lerp_yaw(face, 20, smooth(seg(t, T["grab"], T["grab"] + 1.0)))
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose_drag((t - T["grab"]) * 5.0), rifle=False)
            (x, z), _ = path_at(drag_path, ease_in_out(seg(T["K2"], T["grab"], span)) * 0.95)
            k = t - T["K2"]
            pose = keyed_pose([(0, pose_drag((T["K2"] - T["grab"]) * 5.0)),
                               (0.12, dict(POSES["drag"], spine=-20, head_p=-40, lsh_p=40, rsh_p=50)),
                               (0.9, dict(POSES["slump"], spine=-30, head_p=-40)),
                               (1.7, "dead_back")], k)
            back = 0.6 * smooth(seg(k, 0.4, 1.7))
            yr = math.radians(20)
            return dict(pos=(x - math.sin(yr) * back, 0, z - math.cos(yr) * back), yaw=20,
                        pose=pose, rifle=False, dead=True)

        if who == "darius":
            walk = [(4.4, -4.5), (3.6, 3.6), self.DARIUS_HOME]
            hx, hz = self.DARIUS_HOME
            if t < 5.6:
                u = seg(t, 0.5, 5.6)
                (x, z), yaw = path_at(walk, ease_out(u))
                pose = pose_walk(path_len(walk) * ease_out(u) * 4.0) if u < 0.97 else POSES["radio"]
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=True)
            dv = T["dive"]
            cx, cz = self.DARIUS_COVER
            if t < dv:
                yaw = 10 if t < T["K1"] else lerp_yaw(10, -140, smooth(seg(t, T["K1"] + 0.5, T["K1"] + 1.2)))
                return dict(pos=(hx, 0, hz), yaw=yaw, pose=POSES["radio" if t < T["K1"] else "stand"], rifle=True)
            if t < dv + 0.8:
                u = seg(t, dv + 0.1, dv + 0.8)
                x, z = lerp(hx, cx, ease_out(u)), lerp(hz, cz, ease_out(u))
                pose = keyed_pose([(0, "stand"), (0.35, "dive"), (0.8, "cover_tight")], t - dv)
                return dict(pos=(x, 0, z), yaw=lerp_yaw(-140, 185, u), pose=pose, rifle=True)
            c0, c1 = T["crawl0"], T["crawl1"]
            if t < c0:
                return dict(pos=(cx, 0, cz), yaw=185, pose=POSES["cover_tight"], rifle=True)
            crawl = [(cx, cz - 0.6), (9.3, 4.9), (9.4, 7.6), (8.4, 8.0)]
            if t < c1:
                u = seg(t, c0, c1)
                (x, z), yaw = path_at(crawl, ease_in_out(u))
                pose = blend("cover_tight", pose_crawl(u * 14), seg(t, c0, c0 + 0.35))
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=False)
            x, z = crawl[-1]
            yaw = lerp_yaw(path_at(crawl, 1)[1], -60, smooth(seg(t, c1, c1 + 0.3)))
            if t < T["K3"]:
                pose = keyed_pose([(0, pose_crawl(14)), (0.35, DARIUS_REACH), (0.6, DARIUS_MAYDAY)], t - c1)
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=False, handset=t > c1 + 0.5)
            k = t - T["K3"]
            # stays flat on the deck: propped on one elbow -> face down. (The old
            # kneel-up 'mayday' pose and an arm hanging under the body made him
            # hop up and then hover above the road.)
            pose = keyed_pose([(0, DARIUS_MAYDAY),
                               (0.08, dict(DARIUS_MAYDAY, head_p=-20, spine=-20, body_r=-8)),
                               (0.6, DARIUS_DEAD)], k)
            return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=False, dead=True, handset=k < 0.5)

        if who == "biribel":
            walk = [(-4.6, -6.0), (-5.2, 0.0), self.BIRIBEL_HOME]
            if t < 6.0:
                u = seg(t, 0.8, 6.0)
                (x, z), yaw = path_at(walk, ease_out(u))
                pose = pose_walk(path_len(walk) * ease_out(u) * 4.0, base="stand") if u < 0.97 else POSES["cover"]
                return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=False)
            x, z = self.BIRIBEL_HOME
            if t >= T["P0"] - 0.25:
                return self._biribel_pickup(t)
            if t < T["dive"]:
                return dict(pos=(x, 0, z), yaw=8, pose=POSES["cover"], rifle=False)
            s0 = T["K2"] + 0.9                   # turns and puts his back to the concrete
            if t < s0:
                u = seg(t, T["dive"], T["dive"] + 0.5)
                return dict(pos=(x, 0, z), yaw=8, pose=blend("cover", "cover_tight", u), rifle=False)
            u = smooth(seg(t, s0, s0 + 0.8))
            sit = dict(POSES["cover_tight"], spine=-6, head_p=8, lhip_p=110, rhip_p=96, lkn=140, rkn=120,
                       lsh_p=50, lel=100, rsh_p=30, rel=60)
            hit = T["K4"] + 0.07
            if t > hit:
                k = t - hit
                flinch = dict(sit, spine=30, head_p=44, spine_r=-18, lsh_p=150, lel=150, rsh_p=140, rel=150)
                sit = blend(sit, flinch, k / 0.12) if k < 0.12 else blend(flinch, sit, 0.35 * smooth(seg(k, 0.4, 2.0)))
            pose = blend("cover_tight", sit, u) if u < 1 else sit
            return dict(pos=(x, 0, z - 0.1 * u), yaw=lerp_yaw(8, 182, u), pose=pose, rifle=False)

        if who == "sniper":
            pose = dict(POSES["prone"], head_p=-10, lsh_p=160, rsh_p=150, rifle_p=2)
            return dict(pos=SET.SNIPER_POS, yaw=180, pose=pose, rifle=True)
        return None

    def _biribel_pickup(self, t):
        T = self.T
        P0 = T["P0"] - 0.25                  # lunges flat right as the shot cuts
        sit = self._actor_state("biribel", P0 - 1e-3)
        x0, z0 = sit["pos"][0], sit["pos"][2]
        path = [(x0 + 0.3, z0 - 0.15), (-2.4, 4.85), self.PK_KNEEL]
        c0, c1 = P0 + 0.15, P0 + 2.35
        if t < c1:
            u = seg(t, c0, c1)
            (x, z), yaw = path_at(path, ease_in_out(u))
            crawl = pose_crawl(u * 16)
            pose = blend(sit["pose"], crawl, smooth(seg(t, P0, P0 + 0.3)))
            yaw = lerp_yaw(sit["yaw"], yaw, smooth(seg(t, P0, P0 + 0.3)))
            return dict(pos=(x, 0, z), yaw=yaw, pose=pose, rifle=False)
        x, z = self.PK_KNEEL
        u = smooth(seg(t, c1, c1 + 0.45))
        return dict(pos=(x, 0, z), yaw=lerp_yaw(90, 70, u),
                    pose=blend(pose_crawl(16), "kneel_over", u), rifle=False)

    def _joints(self, who, t):
        st = self._actor_state(who, t)
        _, j, _ = self.actors[who].pose_world(st["pose"], st["pos"], st["yaw"], rifle_on=False)
        return j

    def _gabi_rest(self):
        if self._gabi_rest_c is None:
            T = self.T
            st = self._actor_state("gabi", T["K1"] + 1.6)
            self._gabi_rest_c = (st["pos"][0], st["pos"][2])
        return self._gabi_rest_c

    def _emit_actor(self, who, t, yoff=0.0):
        st = self._actor_state(who, t)
        if st is None:
            return None
        hum = self.actors[who]
        j = self.r.add_humanoid(hum, st["pose"], (st["pos"][0], st["pos"][1] + yoff, st["pos"][2]),
                                st["yaw"], rifle_on=st.get("rifle", False))
        st["joints"] = j
        if st.get("handset"):
            hb = box(0.06, 0.16, 0.06, (20, 20, 20))
            hv = [v_add(p, j["lhand"]) for p in hb.verts]
            self.r.add_dynamic(hv, [(i, c, l, d, None, e) for i, c, l, d, e in hb.faces])
        return st

    # ── drawing ─────────────────────────────────────────────────────────
    def _shot_at(self, t):
        for a, b, name in self.shots:
            if a <= t < b:
                return a, b, name
        return self.shots[-1]

    def _camera(self, name, u, t, a, b):
        """-> (pos, target, fov, roll, focus) for a shot at progress u."""
        T = self.T
        hand = (math.sin(t * 1.3) * 0.03, math.sin(t * 1.9 + 1) * 0.025, 0.0)
        if name == "establish":
            k = ease_in_out(u)
            pos = v_lerp((-8.0, 12.0, -42.0), (-6.2, 2.3, -11.5), k)
            tgt = v_lerp((0.0, 4.0, 30.0), (-1.0, 1.5, 10.0), k)
            return pos, tgt, lerp(54, 46, k), lerp(-3, 0, k), None
        if name == "gabi_lane":
            gx, gz = self.GABI_HOME
            pos = v_add((gx + 1.5 - 0.3 * u, 1.3, gz + 2.7 - 0.4 * u), hand)
            return pos, (gx - 0.1, 1.55, gz), 40, 1.5, ("far", 7.0)
        if name == "seby_west":
            sx, sz = self.SEBY_HOME
            pos = v_add((sx + 1.5, 1.72, sz + 0.6 - 0.25 * u), hand)
            return pos, (-14.0, 1.0, sz + 6.0 + 2 * u), 44, -1.0, ("near", 2.2)
        if name == "gabi_radio":
            gx, gz = self.GABI_HOME
            yr = math.radians(self.GABI_TURN)
            fx, fz = math.sin(yr), math.cos(yr)
            px, pz = -fz, fx                      # perpendicular
            k = smooth(seg(t, a, T["K1"]))
            back = smooth(seg(t, T["K1"] + 0.3, T["K1"] + 1.4))
            dist = lerp(3.6, 3.0, k) + 0.9 * back
            pos = v_add((gx + fx * dist + px * 0.55, lerp(1.5, 1.25, back), gz + fz * dist + pz * 0.55), hand)
            tgt = (gx + fx * 1.2 * back, lerp(1.5, 0.35, back), gz + fz * 1.2 * back)
            return pos, tgt, lerp(36, 32, k) + 10 * back, 0.0, ("far", 7.0)
        if name == "dead_air":
            pos = v_add((-6.9, 1.3, 3.8), v_mul3(hand, 0.5))
            return pos, (-1.8, 0.35, 10.0), 50, 0.0, None
        if name == "glint":
            k = ease_in_out(u)
            tgt = v_lerp((-1.8, 0.4, 10.0), self.scope_pt, k)
            fov = lerp(50, 9.0, ease_in_out(seg(u, 0.2, 1.0)))
            return (-5.9, 1.3, 4.6), tgt, fov, 0.0, ("near", 12.0) if u > 0.35 else None
        if name == "dive":
            return v_add((-14.0, 1.6, 9.0), hand), (2.0, 0.5, 7.4), 46, 0.0, None
        if name == "seby_close":
            hd = self._joints("seby", min(t, T["seby_go"] - 0.01))["head"]
            return v_add((hd[0] - 1.25, hd[1] - 0.05, hd[2] + 0.75), hand), (hd[0], hd[1] - 0.08, hd[2]), 46, 0.0, ("far", 3.2)
        if name == "sprint":
            sb = self._actor_state("seby", t)["pos"]
            gx, gz = self._gabi_rest()
            return v_add((-1.4 + 0.5 * u, 2.3, 3.0), hand), ((sb[0] + gx) / 2, 0.5, (sb[2] + gz) / 2), 52, 0.0, None
        if name == "drag":
            sb = self._actor_state("seby", t)["pos"]
            return v_add((-6.0, 0.5, 7.4 + 0.4 * u), hand), (sb[0] - 0.2, 0.65, sb[2] + 0.5), 38, 0.0, None
        if name == "scope_seby":
            st = self._actor_state("seby", t)
            ch = (st["pos"][0], 1.0, st["pos"][2] + 0.1)
            k = smooth(seg(t, a, T["K2"] - 0.3))
            sway = (math.sin(t * 2.1) * 0.35 * (1 - k) + 0.6 * (1 - k), math.sin(t * 2.9) * 0.18 * (1 - k), 0)
            kick = max(0.0, 1 - (t - T["K2"]) / 0.12) * 1.6 if t > T["K2"] else 0.0
            return self.scope_pt, v_add(ch, (sway[0], sway[1] + kick, 0)), 4.6, 0.0, "scope"
        if name == "seby_down":
            sb = self._actor_state("seby", t)["pos"]
            return (sb[0] - 2.6, 0.62, sb[2] + 2.6), (sb[0] + 0.1, 0.35, sb[2] - 0.5), 42, 0.0, None
        if name == "biribel_cover":
            hd = self._joints("biribel", t)["head"]
            pos = v_add((hd[0] + 0.25, hd[1] - 0.12, hd[2] - 1.55 + 0.25 * u), v_mul3(hand, 0.6))
            return pos, (hd[0], hd[1] - 0.18, hd[2]), 44, 0.0, ("far", 2.6)
        if name == "darius":
            d = self._actor_state("darius", t)["pos"]
            return v_add((5.4, 0.55, 10.9), hand), (d[0] + 0.2, 0.3, d[2] - 0.2), 44, 0.0, None
        if name == "scope_biribel":
            k = ease_in_out(seg(t, a, T["K4"] - 0.5))
            dp = self._actor_state("darius", t)["pos"]
            tgt = v_lerp((dp[0], 0.3, dp[2]), (self.BIRIBEL_HOME[0] + 0.15, 0.86, SET.BARRIER_Z), k)
            sway = (math.sin(t * 2.3) * 0.12, math.sin(t * 3.1) * 0.06, 0)
            kick = max(0.0, 1 - (t - T["K4"]) / 0.1) * 1.4 if t > T["K4"] else 0.0
            return self.scope_pt, v_add(tgt, (sway[0], sway[1] + kick, 0)), lerp(7.5, 3.8, k), 0.0, "scope"
        if name == "near_miss":
            hd = self._joints("biribel", a)["head"]
            k = ease_out(seg(t, a, a + 2.0))
            pos = v_add((hd[0] + 1.6 - 0.3 * k, hd[1] - 0.15, hd[2] - 2.5 + 0.4 * k), hand)
            return pos, (hd[0] + 0.1, hd[1] - 0.1, hd[2] + 0.3), lerp(56, 44, k), lerp(4, 0, k), None
        if name == "pk_crawl":
            b_ = self._actor_state("biribel", t)["pos"]
            k = ease_in_out(u)
            pos = v_add((lerp(2.9, 2.4, k), 0.5, lerp(3.0, 2.8, k)), v_mul3(hand, 0.5))
            return pos, (b_[0] + 0.2, 0.32, b_[2] + 0.1), 44, lerp(-2, 0, k), None
        breath = (math.sin(t * 2.4) * 0.012, math.sin(t * 4.8) * 0.01, 0.0)
        ex, ey, ez = self.PK_EYE
        if name == "pk_body":
            k = ease_in_out(u)
            pos = v_add((ex + 0.12 * k, ey - 0.05 * k, ez + 0.1 * k), breath)
            tgt = v_lerp((1.0, 0.3, 4.9), (0.95, 0.28, 5.15), k)
            return pos, tgt, lerp(54, 48, k), lerp(3, 1, k), None
        if name == "pk_reach":
            k = ease_in_out(seg(u, 0.0, 0.6))
            pos = v_add((ex + 0.12 + 0.08 * k, ey - 0.05 - 0.1 * k, ez + 0.1 + 0.06 * k), breath)
            rx, _, rz = self.PK_RIFLE
            tgt = v_lerp((0.95, 0.28, 5.15), (rx + 0.25, 0.05, rz + 0.12), k)
            return pos, tgt, 52, 1.0, None
        if name == "pk_raise":
            k = ease_in_out(seg(u, 0.0, 0.35))
            pos = v_add((ex + 0.2, lerp(ey - 0.15, ey + 0.02, k), ez + 0.16), breath)
            tgt = v_lerp((self.PK_RIFLE[0] + 0.25, 0.05, self.PK_RIFLE[2] + 0.12), (1.7, 0.72, 6.3), k)
            return pos, tgt, 52, 0.0, None
        return (0, 2, -10), (0, 1, 0), 60, 0.0, None

    # ── first-person pickup (Biribel's hands + Seby's OS-12) ────────────
    def _rifle_ground_M(self):
        return m_mul(rot_y(self.PK_RIFLE_YAW), rot_z(90))

    def _cam_pt(self, lp):
        r = self.r
        return v_add(r.cam, v_add(v_add(v_mul3(r.right, lp[0]), v_mul3(r.up, lp[1])), v_mul3(r.fwd, lp[2])))

    def _rifle_inspect(self, t):
        """-> (world_fn, M_local) of the OS-12 held up in front of the camera."""
        T = self.T
        k = t - T["P3"]
        lift = ease_out(seg(k, 0.0, 0.7))
        turn = ease_in_out(seg(k, 0.5, 2.6))
        sway = math.sin(t * 1.7) * 2.0
        R = m_mul(rot_y(lerp(122, 98, turn) + sway), m_mul(rot_x(lerp(-24, -6, lift)), rot_z(lerp(70, 10, turn))))
        org = (lerp(-0.2, -0.28, turn), lerp(-0.75, -0.1, lift) + math.sin(t * 2.4) * 0.008, 1.4)
        return R, org

    def _emit_fpv(self, name, t):
        T = self.T
        r = self.r
        skin, sleeve = SPECS["biribel"]["skin"], SPECS["biribel"]["jacket"]
        mesh = self.loose_os12 if name == "pk_reach" else self.vm_os12
        if name == "pk_reach":
            M = self._rifle_ground_M()
            lift = 0.22 * ease_in_out(seg(t, T["G"] + 0.05, T["P3"])) if t > T["G"] else 0.0
            base = v_add(self.PK_RIFLE, (0, lift, 0))
            to_w = lambda v: v_add(m_apply(M, v), base)
            grip_r, grip_l = to_w(OS12_GRIP), to_w(OS12_FORE)
            if t <= T["G"]:
                kr = ease_in_out(seg(t, T["P2"] + 0.35, T["G"]))
                kl = ease_in_out(seg(t, T["P2"] + 0.5, T["G"] + 0.12))
                grip_r = v_lerp(self._cam_pt((0.16, -0.32, 0.30)), grip_r, kr)
                grip_l = v_lerp(self._cam_pt((-0.16, -0.32, 0.30)), grip_l, kl)
            verts = [to_w(v) for v in mesh.verts]
            r.add_dynamic(verts, [(i, c, 3, d, None, e) for i, c, l, d, e in mesh.faces])
        else:
            R, org = self._rifle_inspect(t)
            to_w = lambda v: self._cam_pt(v_add(m_apply(R, v), org))
            verts = [to_w(v) for v in mesh.verts]
            r.add_dynamic(verts, [(i, c, 3, d, None, e) for i, c, l, d, e in mesh.faces])
            grip_r, grip_l = to_w(OS12_GRIP), to_w(OS12_FORE)
        if name == "pk_reach":
            arms = ((grip_r, self._cam_pt((0.26, -0.5, 0.12))), (grip_l, self._cam_pt((-0.26, -0.5, 0.18))))
        else:                                # elbows hang below the frame
            arms = ((grip_r, to_w((0, -0.75, -0.25))), (grip_l, to_w((0, -0.7, 0.2))))
        for hand, el in arms:
            wrist = v_lerp(el, hand, 0.86)
            self._seg_box(el, wrist, 0.085, sleeve)
            self._seg_box(v_lerp(el, hand, 0.8), hand, 0.07, skin, h=0.045)

    def _seg_box(self, a, b, w, col, h=None):
        d = v_sub(b, a)
        L = v_len(d)
        if L < 1e-4:
            return
        f = v_mul3(d, 1.0 / L)
        ref = self.r.up if abs(f[1]) < 0.9 else self.r.fwd
        sx = v_norm((ref[1] * f[2] - ref[2] * f[1], ref[2] * f[0] - ref[0] * f[2], ref[0] * f[1] - ref[1] * f[0]))
        sy = (f[1] * sx[2] - f[2] * sx[1], f[2] * sx[0] - f[0] * sx[2], f[0] * sx[1] - f[1] * sx[0])
        m = box(w, h or w, L, col, center=(0, 0, L / 2))
        vs = [v_add(a, v_add(v_add(v_mul3(sx, x), v_mul3(sy, y)), v_mul3(f, z))) for x, y, z in m.verts]
        self.r.add_dynamic(vs, [(i, c, 3, dd, None, e) for i, c, l, dd, e in m.faces])

    def _make_vignette(self):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.w / 2, self.h / 2
        for i in range(24):
            k = i / 23
            a = int(150 * k ** 2.4)
            rx, ry = self.w * (0.78 - 0.30 * k), self.h * (0.84 - 0.30 * k)
            rx, ry = self.w * (1.05 - 0.45 * (1 - k)), self.h * (1.05 - 0.45 * (1 - k))
        # cheap radial vignette by drawing concentric dark rings from outside in
        s.fill((0, 0, 0, 0))
        steps = 18
        for i in range(steps):
            k = i / steps
            a = int(10 + 7 * i)
            rect = pygame.Rect(0, 0, int(self.w * (1.5 - 0.62 * k)), int(self.h * (1.5 - 0.62 * k)))
            rect.center = (int(cx), int(cy))
        out = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for y in range(0, self.h, 2):
            for x in range(0, self.w, 2):
                dx = (x - cx) / cx
                dy = (y - cy) / cy
                d = dx * dx * 0.8 + dy * dy
                a = int(clamp((d - 0.35) / 1.2) ** 1.5 * 190)
                if a:
                    out.fill((0, 0, 0, a), (x, y, 2, 2))
        return out

    def draw(self, screen):
        t = self.t
        a, b, name = self._shot_at(t)
        if name == "black" or self.done:
            screen.fill((0, 0, 0))
            return
        u = seg(t, a, b)
        pos, tgt, fov, roll, focus = self._camera(name, u, t, a, b)
        # shake
        st = t - self.shake_t
        if st < 0.6 and self.shake_amp:
            amp = self.shake_amp * (1 - st / 0.6) ** 2
            pos = v_add(pos, (math.sin(t * 61) * amp, math.sin(t * 47 + 2) * amp, 0))
        scope = focus == "scope"
        r = self.r
        r.set_camera(pos, tgt, fov, roll)
        surf = r.surface
        hy = r.horizon_y()
        surf.blit(self.sky, (0, int(hy) - self.sky_hy))
        r.begin()
        r.add_static()
        for who in ("gabi", "seby", "darius", "biribel", "sniper"):
            if who == "sniper" and scope:
                continue                     # we ARE the sniper
            if who == "biribel" and name in FPV_SHOTS:
                continue                     # we ARE Biribel
            self._emit_actor(who, t)
        self._emit_props(t)
        self._emit_fx(t)
        if name in FPV_SHOTS:
            self._emit_fpv(name, t)
        if focus in (None, "scope"):
            r.flush(surf)
        elif focus[0] == "far":
            r.flush_split(surf, focus[1], lambda s: _blur(s, 3.0))
        else:
            _flush_near_blur(r, surf, focus[1])
        self._draw_rain(surf, t, scope)
        if name == "glint":
            self._draw_glint(surf, t, u)
        if not scope:
            surf.blit(self._vign, (0, 0))
        # dead air: desaturate + darken right after the first kill
        if name in ("gabi_radio", "dead_air") and t > self.T["K1"]:
            k = clamp(1 - (t - self.T["K1"] - 2.5) / 2.0) * 0.55
            _desat(surf, k)
        if name in FPV_SHOTS:
            beat = (t * 1.25) % 1.0
            _desat(surf, 0.2 + 0.2 * max(0.0, 1 - beat / 0.18))
        if scope:
            self._draw_scope(surf, t)
        big = pygame.transform.scale(surf, (WIDTH, HEIGHT))
        screen.blit(big, (0, 0))
        ft = t - self.flash_t
        if 0 <= ft < 0.12:
            fl = pygame.Surface((WIDTH, HEIGHT))
            fl.fill((255, 250, 235))
            fl.set_alpha(int(170 * (1 - ft / 0.12)))
            screen.blit(fl, (0, 0))
        self._draw_bars(screen, t)
        if name == "pk_raise":
            try:
                from missions.m2.draw import _draw_weapon_stat_card
                _draw_weapon_stat_card(screen, t - self.T["P3"] - 0.9, weapon_name="OS-12",
                                       weapon_class="ASSAULT RIFLE", caliber="5.56 x 45 mm",
                                       magazine="25 rounds", role="Mid-range, sustained automatic fire",
                                       flavor="Lower per-shot damage than the pistol. Spray to suppress.",
                                       stamp_text="SEBY'S OS-12 - ACQUIRED")
            except Exception:
                pass

    def _emit_props(self, t):
        T = self.T
        r = self.r
        # dropped rifles
        drops = []
        if t > T["K1"] + 0.35:
            g = self._gabi_rest()
            drops.append((self.loose_rifle, (g[0] + 0.7, 0.04, g[1] + 0.2), 120))
        if T["K2"] + 0.5 < t < T["G"]:       # slid off Seby's sling as he fell
            drops.append((self.loose_os12, self.PK_RIFLE, self.PK_RIFLE_YAW))
        if t > T["crawl0"]:
            drops.append((self.loose_rifle, (self.DARIUS_COVER[0] - 0.3, 0.04, self.DARIUS_COVER[1] - 0.6), -30))
        for mesh, p, yaw in drops:
            M = m_mul(rot_y(yaw), rot_z(90))
            vs = [v_add(m_apply(M, v), p) for v in mesh.verts]
            r.add_dynamic(vs, [(i, c, l, d, None, e) for i, c, l, d, e in mesh.faces])
        # blood pools
        pools = []
        if t > T["K1"] + 1.3:
            gx, gz = self._gabi_rest()
            yr = math.radians(self.GABI_TURN)
            pools.append(((gx + math.sin(yr) * 0.5, gz + math.cos(yr) * 0.5), seg(t, T["K1"] + 1.3, T["K1"] + 8), 0.75))
        if t > T["K2"] + 1.5:
            s = self._actor_state("seby", t)["pos"]
            pools.append(((s[0], s[2] + 0.1), seg(t, T["K2"] + 1.5, T["K2"] + 7), 0.7))
        if t > T["K3"] + 0.6:
            d = self._actor_state("darius", t)["pos"]
            pools.append(((d[0] - 0.2, d[2] + 0.2), seg(t, T["K3"] + 0.6, T["K3"] + 6), 0.6))
        for (x, z), k, rad in pools:
            m = disc_xz(x, z, 0.12 + rad * k, 0.018, (70, 8, 10), n=9,
                        wobble=[1.0, .8, 1.1, .9, 1.2, .85, 1.0, .9, 1.1])
            r.add_dynamic(m.verts, [(i, c, 1, True, None, True) for i, c, l, d, e in m.faces])
        # fires on burned cars + smoke
        for i, fp in enumerate(self.handles["fire_cars"]):
            fl = 0.5 + 0.5 * math.sin(t * 13 + i * 2) * math.sin(t * 7.3 + i)
            r.add_sprite(fp, _fire_sprite(fl), bias=-0.5)
            for k in range(5):
                age = (t * 0.35 + k / 5 + i * 0.3) % 1.0
                sp = (fp[0] + age * 2.2, fp[1] + 0.4 + age * 9.0, fp[2] + age * 1.0)
                r.add_sprite(sp, _smoke_sprite(age))

    def _emit_fx(self, t):
        r = self.r
        for (t0, a, b) in self.tracers:
            if 0 <= t - t0 < 0.07:
                r.add_line3d(a, b, (255, 236, 170), 1)
        if any(0 <= t - k < 0.06 for k in (self.T["K1"], self.T["K2"], self.T["K3"], self.T["K4"])):
            r.add_sprite(self.muzzle_pt, _muzzle_sprite, layer=3)
        for q in self.parts:
            k = q["age"] / q["life"]
            if q.get("spark"):
                r.add_sprite(q["p"], _spark_sprite(1 - k), layer=3)
            elif q.get("mist"):
                r.add_sprite(q["p"], _mist_sprite(q["col"], q["size"] * (1 + 2 * k), 1 - k))
            else:
                r.add_sprite(q["p"], _chip_sprite(q["col"], q["size"]))

    def _draw_rain(self, surf, t, scope):
        w, h = self.w, self.h
        n = 60 if scope else len(self._rain)
        col = (128, 136, 150)
        for i in range(n):
            x0, y0, s = self._rain[i]
            y = (y0 + t * (1.4 + s)) % 1.0
            x = (x0 + t * 0.12 * s) % 1.0
            px, py = x * w, y * h
            ln = 5 + 6 * s
            pygame.draw.line(surf, mix_col(col, (70, 74, 84), 1 - s), (px, py), (px - ln * 0.22, py - ln))

    def _draw_glint(self, surf, t, u):
        if u < 0.45:
            return
        p = self.r.project(self.scope_pt)
        if not p:
            return
        sx, sy, _ = p
        pulse = 0.5 + 0.5 * math.sin(t * 9.0)
        k = clamp((u - 0.45) / 0.15) * (0.55 + 0.45 * pulse)
        g = pygame.Surface((60, 60))
        g.fill((0, 0, 0))
        for rr, a in ((16, 30), (8, 70), (3, 200), (1, 255)):
            v = int(a * k)
            pygame.draw.circle(g, (v, v, int(v * .9)), (30, 30), rr)
        v = int(150 * k)
        pygame.draw.line(g, (v, v, int(v * .9)), (0, 30), (59, 30), 1)
        surf.blit(g, (sx - 30, sy - 30), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_scope(self, surf, t):
        w, h = self.w, self.h
        cx, cy = w // 2, h // 2
        rad = int(h * 0.46)
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 255))
        pygame.draw.circle(mask, (0, 0, 0, 0), (cx, cy), rad)
        for i in range(8):
            pygame.draw.circle(mask, (0, 0, 0, 40 + i * 18), (cx, cy), rad - i, 1)
        surf.blit(mask, (0, 0))
        col = (12, 12, 12)
        pygame.draw.line(surf, col, (cx - rad, cy), (cx - 10, cy), 2)
        pygame.draw.line(surf, col, (cx + 10, cy), (cx + rad, cy), 2)
        pygame.draw.line(surf, col, (cx, cy - rad), (cx, cy - 10), 2)
        pygame.draw.line(surf, col, (cx, cy + 10), (cx, cy + rad), 2)
        pygame.draw.line(surf, col, (cx - 9, cy), (cx + 9, cy), 1)
        pygame.draw.line(surf, col, (cx, cy - 9), (cx, cy + 9), 1)
        for k in range(1, 5):
            pygame.draw.line(surf, col, (cx - 3, cy + k * 12), (cx + 3, cy + k * 12), 1)
            pygame.draw.line(surf, col, (cx - k * 12, cy - 2), (cx - k * 12, cy + 2), 1)
            pygame.draw.line(surf, col, (cx + k * 12, cy - 2), (cx + k * 12, cy + 2), 1)
        pygame.draw.circle(surf, (190, 30, 20), (cx, cy), 1)

    def _draw_bars(self, screen, t):
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, WIDTH, BAR_H))
        pygame.draw.rect(screen, (0, 0, 0), (0, HEIGHT - BAR_H, WIDTH, BAR_H))
        # fade from black at the start
        if t < 0.9:
            f = pygame.Surface((WIDTH, HEIGHT))
            f.fill((0, 0, 0))
            f.set_alpha(int(255 * (1 - t / 0.9)))
            screen.blit(f, (0, 0))
        if t < 5.0:
            a = int(255 * clamp(min((t - 1.2) / 0.6, (5.0 - t) / 0.8)))
            if a > 0:
                for i, (txt, fnt, col) in enumerate((("ROUTE 12 - TOLL PLAZA", font_speaker, (220, 214, 196)),
                                                     ("19:42  -  RAIN", font_prompt, (160, 160, 150)))):
                    s = fnt.render(txt, True, col)
                    s.set_alpha(a)
                    screen.blit(s, (46, BAR_H + 26 + i * 32))
        # subtitles
        for l in self.lines:
            if l.start <= t < l.end + 0.45:
                col = SPEAKER_COL.get(l.speaker, (230, 230, 230))
                tag = l.speaker + (" (RADIO)" if l.radio else "")
                nm = font_prompt.render(tag, True, col)
                tx = font_dialogue.render(l.text, True, (236, 234, 226))
                y = HEIGHT - BAR_H + 10
                screen.blit(nm, ((WIDTH - nm.get_width()) // 2, y))
                screen.blit(tx, ((WIDTH - tx.get_width()) // 2, y + 22))
                break
        if self._skip_hold > 0:
            k = clamp(self._skip_hold / 0.9)
            s = font_prompt.render(_T("sniper3d.skipping"), True, (200, 200, 190))
            screen.blit(s, (WIDTH - s.get_width() - 24, 26))
            pygame.draw.rect(screen, (200, 200, 190), (WIDTH - 124, 50, int(100 * k), 3))
        elif t < 4.0:
            s = font_prompt.render(_T("sniper3d.hold_space_to_skip"), True, (110, 110, 104))
            screen.blit(s, (WIDTH - s.get_width() - 24, 26))


# ── sprites & post ──────────────────────────────────────────────────────

def v_mul3(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _fire_sprite(fl):
    def draw(surf, sx, sy, scale, z):
        r = max(2, int(0.55 * scale * (0.85 + 0.3 * fl)))
        if r > 120:
            return
        g = pygame.Surface((r * 4, r * 5))
        g.fill((0, 0, 0))
        cx, cy = r * 2, r * 3
        pygame.draw.circle(g, (34, 14, 4), (cx, cy), int(r * 1.9))
        pygame.draw.circle(g, (60, 26, 6), (cx, cy), int(r * 1.2))
        h = int(r * (2.0 + fl))
        pygame.draw.polygon(g, (190, 70, 14), [(cx - r, cy + r // 2), (cx - r // 3, cy - h // 2), (cx, cy - h), (cx + r // 2, cy - h // 2), (cx + r, cy + r // 2)])
        pygame.draw.polygon(g, (230, 150, 50), [(cx - r // 2, cy + r // 2), (cx, cy - int(h * .6)), (cx + r // 2, cy + r // 2)])
        surf.blit(g, (sx - cx, sy - cy), special_flags=pygame.BLEND_RGB_ADD)
    return draw


def _smoke_sprite(age):
    def draw(surf, sx, sy, scale, z):
        r = max(2, int((0.6 + age * 2.4) * scale))
        if r > 260:
            return
        a = int(110 * (1 - age))
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (34, 33, 34, a), (r, r), r)
        surf.blit(g, (sx - r, sy - r))
    return draw


def _muzzle_sprite(surf, sx, sy, scale, z):
    r = max(3, int(0.6 * scale))
    if r > 60:
        return
    g = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
    pygame.draw.circle(g, (255, 200, 120, 120), (r * 2, r * 2), r * 2)
    pygame.draw.circle(g, (255, 250, 220, 255), (r * 2, r * 2), r)
    surf.blit(g, (sx - r * 2, sy - r * 2), special_flags=pygame.BLEND_RGBA_ADD)


def _spark_sprite(k):
    def draw(surf, sx, sy, scale, z):
        r = max(2, int(0.5 * scale * k))
        if r > 120:
            return
        g = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (255, 240, 200, int(255 * k)), (r + 1, r + 1), r)
        surf.blit(g, (sx - r, sy - r), special_flags=pygame.BLEND_RGBA_ADD)
    return draw


def _mist_sprite(col, size, k):
    def draw(surf, sx, sy, scale, z):
        r = max(1, int(size * scale))
        if r > 200:
            return
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (*col, int(90 * k)), (r, r), r)
        surf.blit(g, (sx - r, sy - r))
    return draw


def _chip_sprite(col, size):
    def draw(surf, sx, sy, scale, z):
        r = max(1, min(40, int(size * scale)))
        pygame.draw.rect(surf, col, (int(sx) - r // 2, int(sy) - r // 2, r, r))
    return draw


def _blur(surf, k):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, int(w / k)), max(1, int(h / k))))
    surf.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))


def _flush_near_blur(r, surf, split):
    """Sharp background, blurred foreground (rack focus to the distance)."""
    def blur(tmp):
        w, h = tmp.get_size()
        return pygame.transform.smoothscale(pygame.transform.smoothscale(tmp, (w // 4, h // 4)), (w, h))
    r.flush_near_blur(surf, split, blur)


def _desat(surf, k):
    if k <= 0.01:
        return
    g = pygame.transform.grayscale(surf)
    g.set_alpha(int(255 * k))
    surf.blit(g, (0, 0))
