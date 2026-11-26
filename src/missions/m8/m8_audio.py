"""Mission 8 sound design: Route 12, the catwalk, the chase.

Builds on ``missions.m7.m7_audio``: ``M8Audio`` is an ``M7Audio`` whose gun,
impact and body sounds are M8's own (close and distant layers with open-road
tails, three or four takes each), plus an ambience bed that ducks under shots.
Every take is synthesised with numpy; the M7 names stay as the fallback when a
take cannot be built.

Scenes never start playback themselves: they call ``bed(cue)`` and
``update(dt)`` every frame (the same contract as ``m7_audio.music``) and the
named one-shot methods through ``_snd``.  The films use the same beds
(``film(scene, dt)``) and name their one-shots as timeline cues.

The score is the OST (``MUSIC``, streamed through ``m7_audio.music``): Route 12
at dawn for the meet, Not Tonight for the trap, Old Friends from the catwalk
into the kill, then wind alone from the shot on, Fallow
Ground on the tractor, then Head of State, Gabi Seby Darius and the title theme
across the epilogue.
"""
from functools import lru_cache
import math
import random
import time

import numpy as np

from missions.m7.m7_audio import (
    RATE, M7Audio, _done, _highpass, _lowpass, _noise, _place, _sweep, _t, _wav,
)

# pool -> number of takes; a pool of one is a plain sound with that name.
POOLS = {
    "m8_shot": 4,          # Biribel's shotgun, close
    "m8_lmg": 4,           # his LMG on the tractor chase, short so the bursts stay clean
    "m8_rifle": 3,         # their rifles, across the road
    "m8_rifle_far": 3,     # the same, from the far lane
    "m8_sniper": 2,        # overwatch crack from the gantry / watchtower
    "m8_hit": 3,           # round into a body, close
    "m8_hit_far": 2,
    "m8_head": 2,
    "m8_dirt": 3,          # asphalt and concrete
    "m8_ric": 3,           # steel: the gantry and the wrecks
    "m8_flesh": 3,
    "m8_cloth": 2,
    "m8_hurt": 3,          # a round into Biribel
    "m8_rung": 3,          # the gantry ladder
    "m8_hull": 3,          # rounds on the tractor's steel
    "m8_pickup": 2,        # resupply crate latch and shells
    "m8_elec_arc": 3,      # high-voltage cabinet arc crackles
}
SINGLES = ("m8_shot_slow", "m8_fall_light", "m8_fall_heavy",
           "m8_horn", "m8_bell", "m8_creak", "m8_crash", "m8_rocket",
           "m8_barrel_boom", "m8_spark_pop", "m8_pa_squelch", "m8_smoke",
           "m8_breaker_pop", "m8_pistol_shot", "m8_door_kick",
           "m8_missile_warn", "m8_overheat", "m8_flare", "m8_klaxon", "m8_flak",
           "m8_rotor_pass", "m8_subsys_boom",
           "m8_bolt_cycle", "m8_safety_click", "m8_exhale", "m8_heartbeat",
           "m8_ridge_echo", "m8_dead_carrier")
LOOPS = ("m8_drone", "m8_road_wind", "m8_engine", "m8_train", "m8_heli", "m8_radio_hiss")

# cue -> ((loop, gain), ...). Add a cue here; scenes only name it.  Any
# registered loop works; only LOOPS duck under shots.
BEDS = {
    "trap": (("m8_drone", 0.16), ("m8_road_wind", 0.15)),
    "mansion": (("m8_drone", 0.15), ("wind", 0.14)),
    "helipad": (("m8_drone", 0.12), ("wind", 0.16), ("m8_heli", 0.30)),
    "gantry": (("m8_drone", 0.10), ("m8_road_wind", 0.24)),
    "chase": (("m8_drone", 0.13), ("m8_road_wind", 0.20), ("m8_engine", 0.20)),
    "chase_x": (("m8_drone", 0.12), ("m8_road_wind", 0.16), ("m8_engine", 0.20),
                ("m8_train", 0.10)),
    "chase_heli": (("m8_drone", 0.12), ("m8_road_wind", 0.18), ("m8_engine", 0.18),
                   ("m8_heli", 0.22)),
    "chase_end": (("m8_road_wind", 0.14), ("m8_engine", 0.12), ("m8_train", 0.28)),
    # films
    "f_dawn": (("m8_drone", 0.09), ("m8_road_wind", 0.15)),
    "f_truck": (("m8_drone", 0.08), ("m8_road_wind", 0.12), ("m8_engine", 0.10)),
    "kill_wind": (("m8_road_wind", 0.24),),
    "f_catwalk": (("m8_drone", 0.08), ("m8_road_wind", 0.24)),
    "f_train": (("m8_train", 0.24), ("m8_road_wind", 0.12)),
    "f_tv": (("elec_hum", 0.05), ("room_tone", 0.10)),
    "f_night": (("m8_drone", 0.09), ("wind", 0.12)),
    "f_title": (("m8_train", 0.07), ("m8_road_wind", 0.12)),
    "f_heli": (("m8_drone", 0.12), ("m8_road_wind", 0.20), ("m8_engine", 0.14), ("m8_heli", 0.30)),
    "flight": (("m8_drone", 0.12), ("m8_road_wind", 0.22), ("m8_heli", 0.34)),
    "ridge": (("wind", 0.22), ("m8_drone", 0.08)),
    "ridge_radio": (("wind", 0.18), ("m8_drone", 0.07), ("m8_radio_hiss", 0.14)),
    "ridge_standoff": (("wind", 0.16), ("m8_radio_hiss", 0.11)),
    "ridge_wind_only": (("wind", 0.24),),
    "f_fire": (("wind", 0.14), ("m8_drone", 0.10)),
    "f_dawn_crowd": (("m8_road_wind", 0.10), ("room_tone", 0.06)),
}

# film scene -> (score cue, bed cue).
FILM = {
    "m8_meet_dawn": ("meet", "f_truck"),
    "m8_meet_drive": ("meet", "f_truck"),
    "m8_meet_gantry": ("meet", "f_dawn"),
    "m8_meet_walk": ("meet", "f_dawn"),
    "m8_friends_catwalk": ("friends", "f_catwalk"),
    "m8_friends_four": ("friends", "f_catwalk"),
    "m8_friends_desk": ("friends", "f_catwalk"),
    "m8_friends_matter": ("friends", "f_catwalk"),
    "m8_friends_taught": ("friends", "f_catwalk"),
    "m8_friends_chose": ("friends", "f_catwalk"),
    "m8_friends_raise": ("friends_low", "f_catwalk"),
    "m8_descent_body": (None, "kill_wind"),
    "m8_descent_ladder": (None, "kill_wind"),
    "m8_descent_geton": (None, "f_truck"),
    "m8_descent_pullout": ("chase", "chase"),
    "m8_epi_radio": (None, "f_train"),
    "m8_epi_president": ("state", "f_tv"),
    "m8_epi_estate": ("state", "f_night"),
    "m8_epi_casket": ("state", "f_night"),
    "m8_epi_commander": ("state", "f_tv"),
    "m8_epi_crossing": ("names", "f_train"),
    "m8_epi_ucilev": ("names", "f_train"),
    "m8_epi_names": ("names", "f_train"),
    "m8_epi_volkov": ("names", "f_train"),
    "m8_epi_title": ("title", "f_title"),
    "m8_heli_road": ("chase", "f_truck"),
    "m8_heli_retardovici": ("state", "f_tv"),
    "m8_heli_flyby": ("chase", "f_heli"),
    "m8_heli_lockon": ("chase", "chase_heli"),
    "m8d_approach_aerial": ("approach", "f_night"),
    "m8d_approach_gate": ("approach", "f_night"),
    "m8d_liftoff_study": ("flight", "f_heli"),
    "m8d_liftoff_window": ("flight", "f_heli"),
    "m8d_liftoff_maru": ("flight", "f_heli"),
    "m8d_crash_spin": ("flight", "f_heli"),
    "m8d_crash_black": (None, "f_fire"),
    "m8d_crash_fire": (None, "f_fire"),
    "m8d_crash_promise": (None, "f_fire"),
    "m8d_crash_better": (None, "f_fire"),
    "m8d_inauguration": ("state", "f_tv"),
    "m8d_vasile_speech": ("state", "f_dawn_crowd"),
    "m8d_crowd": ("names", "f_dawn_crowd"),
    "m8d_eyes": ("names", "f_dawn_crowd"),
    "m8d_biribel_vo": ("names", "f_dawn_crowd"),
    "m8d_title_card": ("title", "f_title"),
}

# -- score (assets/music/ost, streamed) ---------------------------------------
# cue -> (file, volume, fade-in ms), the m7_audio.music spec.  A cue that
# names the track already playing only moves its level, so Old Friends runs
# unbroken from the catwalk through the film into the kill.
OST_DIR = "assets/music/ost/"
# Dark cello horror bed from the trailer pack: slow, low and sparse for the standoff.
DREAD = "assets/music/newtrailer/Dark Cello Horror Trailer Music Free Music For Video Creators.mp3"
MUSIC = {
    "meet": (OST_DIR + "03_quiet_on_route_12.mp3", 0.36, 2500),
    "approach": (OST_DIR + "17_cold_marble.mp3", 0.30, 2500),
    "trap": (OST_DIR + "13_wet_concrete.mp3", 0.40, 1200),
    "mansion": (OST_DIR + "17_cold_marble.mp3", 0.38, 1200),
    "gantry": (OST_DIR + "11_old_friends.mp3", 0.24, 3000),
    "friends": (OST_DIR + "11_old_friends.mp3", 0.34, 2000),
    "friends_low": (OST_DIR + "11_old_friends.mp3", 0.20, 800),
    "kill": (OST_DIR + "11_old_friends.mp3", 0.18, 800),
    "standoff": (DREAD, 0.20, 1500),
    "road": (OST_DIR + "08_i_chose_the_many.mp3", 0.28, 2500),
    "chase": (OST_DIR + "18_to_the_crossing.mp3", 0.44, 1200),
    "flight": (OST_DIR + "10_head_of_state.mp3", 0.42, 1200),
    "flight_boss": (OST_DIR + "10_head_of_state.mp3", 0.50, 900),
    "state": (OST_DIR + "10_head_of_state.mp3", 0.32, 1800),
    "names": (OST_DIR + "12_gabi_seby_darius.mp3", 0.40, 2500),
    "title": (OST_DIR + "01_call_of_acaristan.mp3", 0.48, 1500),
}


def music(manager, cue):
    """Drive the score toward ``cue`` (None = silence); call every frame."""
    from missions.m7 import m7_audio as _m7
    _m7.music(manager, cue, MUSIC)

FAR_M = 26.0               # past this a rifle is the distant layer
SOUND_MPS = 340.0
DUCK_RELEASE_S = 0.55      # bed climbs back this long after a shot


def _names(pool):
    return tuple("%s_%d" % (pool, i + 1) for i in range(POOLS[pool]))


ONE_SHOTS = tuple(n for p in POOLS for n in _names(p)) + SINGLES
WARM = LOOPS + ONE_SHOTS


# ── synth ───────────────────────────────────────────────────────────────────
def _decay(n, tau):
    return np.exp(-_t(n) / tau)


def _burst(n, seed, tau, lo=None, hi=None):
    x = _noise(n, seed)
    if hi is not None:
        x = _lowpass(x, hi, 2)
    if lo is not None:
        x = _highpass(x, lo)
    pk = float(np.max(np.abs(x))) or 1.0
    return x / pk * _decay(n, tau)


def _tone(n, f0, f1, tau):
    return np.sin(2 * math.pi * _sweep(n, f0, f1)) * _decay(n, tau)


def _tail(n, seed, cutoff, tau, taps):
    """Open-road tail: a dull decay plus slap echoes off the wrecks and pillars."""
    x = _burst(n, seed, tau, hi=cutoff)
    out = x.copy()
    for at, gain in taps:
        _place(out, x, at, gain)
    return out


def _fin(x, peak=0.85, stereo=0.14):
    pk = float(np.max(np.abs(x))) or 1.0
    return _done(x * (peak / pk), stereo)


def _take(name):
    """('m8_shot_3') -> ('m8_shot', 3, pitch factor, seed)."""
    base, _, idx = name.rpartition("_")
    i = int(idx)
    return base, i, (1.0, 0.94, 1.06, 0.98)[(i - 1) % 4], 8000 + sum(map(ord, base)) * 7 + i * 13


def _shot_mono(i, p, seed):
    n = int(1.5 * RATE)
    crack = _burst(n, seed, 0.012 / p, lo=1800.0) * 0.9
    body = _burst(n, seed + 1, 0.07, hi=900.0 * p) * 1.1
    thump = np.zeros(n)
    k = int(0.25 * RATE)
    _place(thump, _tone(k, 150.0 * p, 42.0 * p, 0.07), 0.0, 0.9)
    tail = _tail(n, seed + 3, 1400.0 * p, 0.33,
                 ((0.11, 0.35), (0.19 + 0.012 * i, 0.22), (0.34, 0.12)))
    return np.tanh((crack + body + thump) * 1.6) * 0.8 + tail * 0.34


def _rifle_mono(i, p, seed, far):
    n = int((1.5 if far else 1.1) * RATE)
    crack = _burst(n, seed, 0.006 / p, lo=900.0) * 0.9
    body = _burst(n, seed + 1, 0.035, hi=2200.0 * p) * 0.8
    thump = np.zeros(n)
    k = int(0.12 * RATE)
    _place(thump, _tone(k, 220.0 * p, 70.0 * p, 0.03), 0.0, 0.5)
    tail = _tail(n, seed + 3, 1800.0 * p, 0.25, ((0.09, 0.30), (0.21 + 0.015 * i, 0.16)))
    x = np.tanh((crack + body + thump) * 1.4) * 0.8 + tail * 0.28
    if far:
        # distance: the top goes, the echo off the far barrier stays
        x = _lowpass(x, 1100.0 * p, 2) * 2.0
        _place(x, x.copy(), 0.27 + 0.02 * i, 0.38)
    return x


def _lmg_mono(i, p, seed):
    """One LMG round: a heavier, lower crack than their rifles, cut short."""
    n = int(0.42 * RATE)
    crack = _burst(n, seed, 0.004 / p, lo=700.0) * 0.8
    body = _burst(n, seed + 1, 0.028, hi=1700.0 * p) * 0.9
    thump = np.zeros(n)
    _place(thump, _tone(int(0.09 * RATE), 150.0 * p, 55.0 * p, 0.025), 0.0, 0.7)
    tail = _tail(n, seed + 3, 1500.0 * p, 0.12, ((0.07, 0.22),))
    return np.tanh((crack + body + thump) * 1.6) * 0.8 + tail * 0.22


def _partials(n, f0, parts):
    """Struck metal: ((ratio, gain, tau), ...) over ``f0``."""
    t = _t(n)
    x = np.zeros(n)
    for ratio, gain, tau in parts:
        x += np.sin(2 * math.pi * f0 * ratio * t) * np.exp(-t / tau) * gain
    return x


def _horn():
    """The diesel's two-tone horn, off the plain and back."""
    n = int(3.2 * RATE)
    t = _t(n)
    env = np.clip(t / 0.07, 0.0, 1.0) * np.clip((1.75 - t) / 0.35, 0.0, 1.0)
    x = np.zeros(n)
    for f in (277.0, 349.0):
        ph = 2 * math.pi * _sweep(n, f, f * 0.985)
        for h in range(1, 7):
            x += np.sin(ph * h) / h * (0.5 if h > 1 else 1.0)
    x = _lowpass(x * env, 2600.0, 2)
    x += _lowpass(_noise(n, 8931), 900.0, 2) * env * 0.6
    out = x.copy()
    for at, gain in ((0.42, 0.30), (0.86, 0.14)):
        _place(out, _lowpass(x, 1200.0, 2), at, gain)
    return out


def _creak():
    """Steel working in the wind: a slow stick-slip groan."""
    dur = 1.7
    n = int(dur * RATE)
    t = _t(n)
    f = 74.0 + 16.0 * np.sin(2 * math.pi * 1.1 * t) + 6.0 * np.sin(2 * math.pi * 3.7 * t)
    ph = np.cumsum(f) / RATE
    x = (ph % 1.0 < 0.06).astype(np.float64)
    x = _highpass(_lowpass(x, 1700.0, 2), 260.0)
    return x * np.sin(math.pi * t / dur) ** 2


def _bell():
    """One toll of a chapel bell across the grounds."""
    n = int(5.0 * RATE)
    x = _partials(n, 196.0, ((0.5, 0.55, 4.2), (1.0, 1.0, 2.8), (1.19, 0.45, 2.1),
                             (1.5, 0.38, 1.6), (2.0, 0.32, 1.2), (2.74, 0.18, 0.8),
                             (3.0, 0.12, 0.6)))
    x += _burst(n, 8941, 0.006, lo=1500.0) * 0.4
    return _lowpass(x, 3200.0, 2)


def _crash():
    """A car going over: the hit, the steel folding, glass and bits after."""
    n = int(1.6 * RATE)
    x = _burst(n, 8951, 0.16, hi=700.0) * 1.2
    _place(x, _tone(int(0.5 * RATE), 90.0, 38.0, 0.12), 0.0, 1.0)
    x += _partials(n, 143.0, ((1.0, 0.35, 0.30), (1.62, 0.25, 0.22), (2.37, 0.18, 0.15),
                              (3.9, 0.10, 0.10)))
    rng = np.random.default_rng(8952)
    for _ in range(14):
        k = int(0.03 * RATE)
        _place(x, _burst(k, int(rng.integers(1, 99999)), 0.006, lo=2600.0),
               float(rng.uniform(0.08, 0.9)), float(rng.uniform(0.06, 0.22)))
    return np.tanh(x * 1.4)


def _sniper_mono(i, p, seed):
    """Supersonic crack + deep bolt report + long valley tail off the toll booths."""
    n = int(1.9 * RATE)
    whip = _burst(n, seed, 0.005 / p, lo=2200.0) * 1.1
    boom = _burst(n, seed + 1, 0.06, hi=1400.0 * p) * 0.9
    thump = _tone(n, 165.0 * p, 48.0 * p, 0.09) * 0.8
    tail = _tail(n, seed + 3, 1500.0 * p, 0.42, ((0.14, 0.36), (0.31 + 0.02 * i, 0.22), (0.56, 0.12)))
    return np.tanh((whip + boom + thump) * 1.55) * 0.82 + tail * 0.36


def _barrel_boom():
    """Fuel drum detonation: sub punch, fuel whoosh, steel ring, highway echo."""
    n = int(2.2 * RATE)
    sub = _tone(n, 118.0, 26.0, 0.26) * 1.25
    roar = _burst(n, 8954, 0.24, hi=950.0) * 1.15
    crack = _burst(n, 8955, 0.015, lo=1600.0) * 0.9
    ring = _partials(n, 238.0, ((1.0, 0.26, 0.22), (1.72, 0.16, 0.14)))
    out = np.tanh((sub + roar + crack + ring) * 1.5)
    _place(out, _lowpass(out.copy(), 650.0, 2), 0.28, 0.32)
    _place(out, _lowpass(out.copy(), 480.0, 2), 0.58, 0.16)
    return out


def _spark_pop():
    """Transformer / floodlight shatter: electrical arc snap, glass, dying hum."""
    n = int(0.85 * RATE)
    t = _t(n)
    arc = _burst(n, 8957, 0.018, lo=1800.0) * 1.0
    buzz = np.sin(2 * math.pi * 100.0 * t) * np.exp(-t / 0.14) * 0.55
    glass = _burst(n, 8958, 0.06, lo=3000.0) * 0.5
    rng = np.random.default_rng(8959)
    out = arc + buzz + glass
    for _ in range(6):
        k = int(0.025 * RATE)
        _place(out, _burst(k, int(rng.integers(1, 99999)), 0.004, lo=2400.0),
               float(rng.uniform(0.04, 0.38)), float(rng.uniform(0.12, 0.28)))
    return np.tanh(out * 1.35)


def _pa_squelch():
    """Toll-plaza loudspeaker key-up: relay click, bandpass hiss, horn resonance."""
    n = int(0.32 * RATE)
    click = _tone(int(0.03 * RATE), 980.0, 420.0, 0.007) * 0.7
    hiss = _highpass(_lowpass(_noise(n, 8960), 2600.0, 2), 680.0) * _decay(n, 0.08) * 0.55
    x = hiss.copy()
    _place(x, click, 0.0, 0.9)
    _place(x, _tone(int(0.025 * RATE), 1420.0, 1180.0, 0.006), 0.02, 0.45)
    return x


def _smoke_hiss():
    """A smoke canister: the clink, then the charge burning itself out."""
    n = int(0.95 * RATE)
    t = _t(n)
    clink = _partials(int(0.14 * RATE), 1480.0, ((1.0, 0.6, 0.03), (1.82, 0.35, 0.02)))
    hiss = _highpass(_lowpass(_noise(n, 8963), 5200.0, 2), 1400.0) * np.clip(t / 0.08, 0.0, 1.0) * _decay(n, 0.34)
    out = hiss * 0.75
    _place(out, clink, 0.0, 0.7)
    return out


def _elec_arc_mono(i, p, seed):
    """Sharp mains buzz plus crackling plasma snaps from an overloaded rack."""
    n = int(0.24 * RATE)
    t = _t(n)
    hum = (np.sin(2 * math.pi * 100.0 * p * t) * 0.55
           + np.sin(2 * math.pi * 200.0 * p * t) * 0.30) * np.exp(-t / 0.14)
    snap = np.zeros(n)
    rng = np.random.default_rng(seed)
    for at in (0.0, 0.045 + 0.01 * i, 0.11):
        k = int(0.032 * RATE)
        _place(snap, _burst(k, int(rng.integers(1, 99999)), 0.005, lo=2100.0), at, 0.9)
    return np.tanh((hum + snap * 1.15) * 1.4)


def _breaker_pop():
    """Heavy relay clack, transformer thud and dying cap whine."""
    n = int(0.75 * RATE)
    t = _t(n)
    clack = _burst(int(0.04 * RATE), 8966, 0.005, lo=1600.0) * 1.1
    thud = _tone(n, 132.0, 38.0, 0.11) * 1.0
    whine = np.sin(2 * math.pi * _sweep(n, 420.0, 85.0)) * np.exp(-t / 0.18) * 0.35
    out = thud + whine
    _place(out, clack, 0.0, 1.0)
    return np.tanh(out * 1.45)


def _pistol_shot():
    """Sharp indoor sidearm crack with quick wall slap."""
    n = int(0.95 * RATE)
    crack = _burst(n, 8968, 0.008, lo=1400.0) * 1.0
    punch = _tone(int(0.14 * RATE), 260.0, 74.0, 0.038) * 0.75
    out = crack.copy()
    _place(out, punch, 0.0, 1.0)
    _place(out, _lowpass(crack, 1500.0, 2), 0.05, 0.32)
    _place(out, _lowpass(crack, 1100.0, 2), 0.11, 0.18)
    return np.tanh(out * 1.45)


def _door_kick():
    """Heavy boot slam, mahogany panel crack, sheared brass latch & hall echo."""
    n = int(1.05 * RATE)
    thump = _tone(int(0.24 * RATE), 128.0, 38.0, 0.06) * 1.25
    crack = _burst(int(0.18 * RATE), 8971, 0.014, lo=1100.0) * 1.15
    splinter = _burst(int(0.34 * RATE), 8972, 0.035, lo=650.0, hi=3200.0) * 0.90
    latch = _partials(int(0.22 * RATE), 1640.0, ((1.0, 0.45, 0.025), (1.71, 0.28, 0.018)))
    out = np.zeros(n)
    _place(out, thump, 0.0, 1.0)
    _place(out, crack, 0.008, 0.95)
    _place(out, latch, 0.012, 0.65)
    _place(out, splinter, 0.018, 0.85)
    _place(out, _lowpass(out[:int(0.26 * RATE)].copy(), 1200.0, 2), 0.11, 0.34)
    _place(out, _lowpass(out[:int(0.26 * RATE)].copy(), 800.0, 2), 0.23, 0.18)
    _place(out, _tone(int(0.16 * RATE), 82.0, 44.0, 0.045), 0.19, 0.42)
    return np.tanh(out * 1.45)


def _flak_pop():
    """Mid-air anti-aircraft flak airburst: sharp hollow bark, low thump, open-sky tail."""
    n = int(0.85 * RATE)
    crack = _burst(n, 8983, 0.011, lo=900.0, hi=3800.0) * 1.1
    thump = _tone(int(0.28 * RATE), 148.0, 44.0, 0.065) * 1.05
    tail = _tail(n, 8984, 980.0, 0.24, ((0.12, 0.28), (0.27, 0.14)))
    out = crack + tail * 0.36
    _place(out, thump, 0.0, 1.0)
    return np.tanh(out * 1.45)


@lru_cache(maxsize=64)
def shot_pcm(name):
    if name == "m8_shot_slow":
        # the sixth round, heard at the picture's speed: same take, an octave down
        src = _shot_mono(1, 1.0, _take("m8_shot_1")[3])
        n = int(len(src) / 0.5)
        x = np.interp(np.linspace(0.0, len(src) - 1.0, n), np.arange(len(src)), src)
        x = _lowpass(x, 2400.0, 2)
        k = int(1.2 * RATE)
        _place(x, _tone(k, 58.0, 34.0, 0.45), 0.0, 0.5)
        return _fin(x, stereo=0.22)
    if name == "m8_fall_light":
        # a knee on the grating
        n = int(0.6 * RATE)
        t = _t(n)
        x = _tone(n, 110.0, 80.0, 0.05) * 0.8 + _burst(n, 8801, 0.04, lo=1500.0) * 0.25
        for f, g in ((310.0, 0.16), (487.0, 0.11), (733.0, 0.07)):
            x += np.sin(2 * math.pi * f * t) * np.exp(-t / 0.12) * g
        return _fin(x, 0.7)
    if name == "m8_fall_heavy":
        # the body, then the slump against the rail
        n = int(1.6 * RATE)
        x = _burst(n, 8811, 0.12, lo=1400.0, hi=5000.0) * 0.18       # cloth, going down
        for at, gain in ((0.10, 1.0), (0.48, 0.6)):
            k = int(0.9 * RATE)
            tt = _t(k)
            hit = _tone(k, 95.0, 48.0, 0.11) + _burst(k, 8812 + int(at * 100), 0.09, hi=500.0) * 0.8
            for f, g in ((205.0, 0.20), (331.0, 0.14), (512.0, 0.09), (790.0, 0.05)):
                hit += np.sin(2 * math.pi * f * tt) * np.exp(-tt / 0.35) * g
            _place(x, hit, at, gain)
        for at in (0.2, 0.3, 0.62):
            k = int(0.06 * RATE)
            _place(x, _burst(k, 8820 + int(at * 100), 0.012, lo=2000.0), at, 0.16)
        return _fin(x, stereo=0.18)
    if name == "m8_horn":
        return _fin(_horn(), 0.8, 0.3)
    if name == "m8_bell":
        return _fin(_bell(), 0.75, 0.35)
    if name == "m8_creak":
        return _fin(_creak(), 0.6, 0.3)
    if name == "m8_crash":
        return _fin(_crash(), 0.85, 0.25)
    if name == "m8_barrel_boom":
        return _fin(_barrel_boom(), 0.90, 0.22)
    if name == "m8_spark_pop":
        return _fin(_spark_pop(), 0.78, 0.20)
    if name == "m8_pa_squelch":
        return _fin(_pa_squelch(), 0.55, 0.12)
    if name == "m8_smoke":
        return _fin(_smoke_hiss(), 0.70, 0.22)
    if name == "m8_breaker_pop":
        return _fin(_breaker_pop(), 0.80, 0.18)
    if name == "m8_pistol_shot":
        return _fin(_pistol_shot(), 0.76, 0.16)
    if name == "m8_door_kick":
        return _fin(_door_kick(), 0.88, 0.22)
    if name == "m8_missile_warn":
        n = int(0.24 * RATE)
        t = _t(n)
        p1 = ((t >= 0.0) & (t < 0.065)).astype(np.float64) * np.sin(2 * math.pi * 920.0 * t)
        p2 = ((t >= 0.10) & (t < 0.18)).astype(np.float64) * np.sin(2 * math.pi * 1240.0 * t)
        x = _highpass(_lowpass(p1 + p2, 3200.0, 2), 400.0)
        return _fin(x, 0.48, 0.05)
    if name == "m8_overheat":
        n = int(0.42 * RATE)
        t = _t(n)
        clack = _burst(int(0.04 * RATE), 8994, 0.006, lo=1500.0) * 0.9
        hiss = _highpass(_lowpass(_noise(n, 8995), 4800.0, 2), 1400.0) * np.clip(t / 0.04, 0.0, 1.0) * _decay(n, 0.16)
        out = hiss * 0.65
        _place(out, clack, 0.0, 0.9)
        return _fin(out, 0.62, 0.14)
    if name == "m8_flare":
        n = int(0.48 * RATE)
        t = _t(n)
        pop = _burst(int(0.03 * RATE), 8996, 0.005, lo=320.0) * 1.1
        sizzle = _highpass(_lowpass(_noise(n, 8997), 6200.0, 2), 2100.0) * np.clip(t / 0.02, 0.0, 1.0) * _decay(n, 0.20)
        out = sizzle * 0.55
        _place(out, pop, 0.0, 1.0)
        return _fin(out, 0.68, 0.16)
    if name == "m8_klaxon":
        n = int(0.36 * RATE)
        t = _t(n)
        b1 = ((t >= 0.0) & (t < 0.12)).astype(np.float64) * np.sin(2 * math.pi * 680.0 * t)
        b2 = ((t >= 0.16) & (t < 0.28)).astype(np.float64) * np.sin(2 * math.pi * 510.0 * t)
        x = _highpass(_lowpass(b1 + b2, 2800.0, 2), 280.0)
        return _fin(x, 0.54, 0.08)
    if name == "m8_flak":
        return _fin(_flak_pop(), 0.78, 0.24)
    if name == "m8_rotor_pass":
        n = int(1.25 * RATE)
        t = _t(n)
        env = np.sin(math.pi * np.clip(t / 1.25, 0.0, 1.0)) ** 1.6
        # Doppler blade-slap pulse sweeping ~14 Hz down to ~9 Hz across the pass
        phase = 2.0 * math.pi * (14.5 * t - 2.2 * (t ** 2))
        slap = (0.5 + 0.5 * np.sin(phase)) ** 3.2
        whoosh = _highpass(_lowpass(_noise(n, 8986), 920.0, 2), 90.0) * (0.45 + 1.35 * slap)
        turbine = _tone(n, 290.0, 165.0, 0.75) * 0.28
        x = (whoosh + turbine) * env
        return _fin(np.tanh(x * 1.4), 0.78, 0.32)
    if name == "m8_subsys_boom":
        n = int(1.35 * RATE)
        shear = _burst(n, 8988, 0.018, lo=1500.0) * 1.15
        ring = _partials(int(0.45 * RATE), 1180.0, ((1.0, 0.42, 0.06), (1.62, 0.28, 0.045)))
        thump = _tone(int(0.55 * RATE), 145.0, 34.0, 0.16) * 1.3
        body = _burst(n, 8989, 0.16, lo=110.0, hi=1400.0) * 1.0
        echo = _tail(n, 8990, 880.0, 0.38, ((0.16, 0.34), (0.34, 0.18))) * 0.42
        out = shear + body + echo
        _place(out, thump, 0.0, 1.0)
        _place(out, ring, 0.005, 0.85)
        return _fin(np.tanh(out * 1.45), 0.92, 0.26)
    if name == "m8_rocket":
        n = int(1.3 * RATE)
        t = _t(n)
        env = np.clip(t / 0.05, 0.0, 1.0) * np.exp(-t / 0.45)
        x = _highpass(_lowpass(_noise(n, 8991), 2400.0, 2), 260.0) * env
        x += _tone(n, 380.0, 140.0, 0.28) * 0.5
        return _fin(x, 0.85, 0.24)
    if name == "m8_bolt_cycle":
        n = int(0.78 * RATE)
        x = np.zeros(n, dtype=np.float64)

        def _snap(seed, body_f0, body_f1, body_tau, click_lo, click_tau, g_body, g_click):
            k = int(0.06 * RATE)
            kt = _t(k)
            body = _lowpass(_tone(k, body_f0, body_f1, body_tau), 650.0, 2) * g_body
            click = _highpass(_lowpass(_noise(k, seed), 7200.0, 2), click_lo)
            click *= np.exp(-kt / click_tau) * g_click
            return body + click

        def _slide(dur, seed, f_lo, f_hi, mod_hz, gain):
            k = int(dur * RATE)
            kt = _t(k)
            env = np.sin(np.pi * np.clip(kt / max(dur, 1e-4), 0.0, 1.0)) ** 0.75
            # Machined steel-on-steel rail texture (narrower band + subtle grain)
            grain = 0.72 + 0.28 * np.sin(2.0 * np.pi * mod_hz * kt)
            s = _highpass(_lowpass(_noise(k, seed), f_hi, 2), f_lo) * env * grain
            return s * gain

        # 1. Unlock cam + handle lift (dry steel snap + receiver thump)
        _place(x, _snap(8992, 260.0, 115.0, 0.016, 2400.0, 0.0032, 0.75, 0.95), 0.01, 1.0)
        # 2. Pull bolt back along receiver rails + bolt-stop clack
        _place(x, _slide(0.15, 8993, 1200.0, 4200.0, 62.0, 0.42), 0.08, 1.0)
        _place(x, _snap(8994, 195.0, 88.0, 0.020, 1900.0, 0.0040, 0.90, 0.85), 0.22, 1.0)
        # 3. Subtle dry brass eject tick
        k_br = int(0.035 * RATE)
        br = _partials(k_br, 4350.0, ((1.0, 0.35, 0.006), (1.47, 0.22, 0.004)))
        br += _highpass(_noise(k_br, 8995), 3800.0) * np.exp(-_t(k_br) / 0.0025) * 0.30
        _place(x, br, 0.27, 0.45)
        # 4. Push bolt forward + strip next round from magazine
        _place(x, _slide(0.16, 8996, 950.0, 3400.0, 54.0, 0.46), 0.43, 1.0)
        _place(x, _snap(8997, 320.0, 160.0, 0.010, 2800.0, 0.0025, 0.45, 0.60), 0.50, 0.8)
        # 5. Lugs engage + handle locks down (heavy receiver chunk-klik)
        _place(x, _snap(8998, 220.0, 82.0, 0.022, 2100.0, 0.0035, 1.05, 0.90), 0.60, 1.0)
        _place(x, _snap(8999, 280.0, 125.0, 0.014, 2700.0, 0.0028, 0.70, 1.00), 0.635, 1.0)
        return _fin(np.tanh(x * 1.15), 0.78, 0.04)
    if name == "m8_safety_click":
        n = int(0.14 * RATE)
        x = _partials(n, 2400.0, ((1.0, 0.5, 0.010), (1.88, 0.28, 0.008)))
        x += _burst(n, 8993, 0.004, lo=2200.0) * 0.75
        return _fin(x, 0.58, 0.08)
    if name == "m8_exhale":
        n = int(0.60 * RATE)
        t = _t(n)
        env = np.clip(t / 0.08, 0.0, 1.0) * np.exp(-t / 0.20)
        x = _highpass(_lowpass(_noise(n, 8998), 1600.0, 2), 260.0) * env
        return _fin(x, 0.42, 0.10)
    if name == "m8_heartbeat":
        n = int(0.75 * RATE)
        x = np.zeros(n, dtype=np.float64)
        _place(x, _tone(int(0.16 * RATE), 68.0, 34.0, 0.045), 0.0, 1.0)
        _place(x, _tone(int(0.14 * RATE), 58.0, 30.0, 0.040), 0.21, 0.72)
        return _fin(_lowpass(x, 180.0, 2), 0.68, 0.06)
    if name == "m8_ridge_echo":
        n = int(1.9 * RATE)
        taps = ((0.0, 0.72), (0.28, 0.44), (0.64, 0.26), (1.08, 0.14))
        x = _tail(n, 8999, 980.0, 0.45, taps)
        x += _lowpass(_tone(n, 110.0, 42.0, 0.28), 340.0, 2) * 0.45
        return _fin(x, 0.72, 0.34)
    if name == "m8_dead_carrier":
        n = int(0.26 * RATE)
        t = _t(n)
        pop = _burst(int(0.03 * RATE), 9001, 0.006, lo=900.0) * 1.1
        tail = _highpass(_lowpass(_noise(n, 9002), 3400.0, 2), 1100.0) * np.exp(-t / 0.05) * 0.65
        x = tail.copy()
        _place(x, pop, 0.0, 1.0)
        return _fin(x, 0.66, 0.12)
    base, i, p, seed = _take(name)
    if base == "m8_hurt":
        # felt more than heard: the thump through the chest, a dull ear
        n = int(0.45 * RATE)
        x = _tone(n, 95.0 * p, 48.0 * p, 0.08) * 1.0
        x += _burst(n, seed, 0.05, hi=650.0 * p) * 0.8
        x += _burst(n, seed + 1, 0.004, lo=1800.0) * 0.18
        return _fin(np.tanh(x * 1.5), 0.8, 0.1)
    if base == "m8_rung":
        n = int(0.4 * RATE)
        x = _partials(n, 610.0 * p, ((1.0, 0.5, 0.09), (2.32, 0.3, 0.06), (3.9, 0.15, 0.04)))
        x += _burst(n, seed, 0.003, lo=2000.0) * 0.5
        x += _tone(n, 125.0 * p, 80.0, 0.03) * 0.6
        return _fin(x, 0.7, 0.2)
    if base == "m8_hull":
        n = int(0.55 * RATE)
        x = _partials(n, 182.0 * p, ((1.0, 0.6, 0.13), (1.47, 0.4, 0.10), (2.31, 0.25, 0.07),
                                     (3.1, 0.12, 0.05)))
        x += _burst(n, seed, 0.03, hi=1200.0) * 0.7
        x += _burst(n, seed + 1, 0.004, lo=2500.0) * 0.35
        return _fin(np.tanh(x * 1.3), 0.75, 0.2)
    if base == "m8_pickup":
        n = int(0.32 * RATE)
        latch = _tone(int(0.08 * RATE), 420.0 * p, 220.0 * p, 0.025) * 0.65
        shells = _burst(n, seed, 0.04, lo=1700.0, hi=4200.0) * 0.5
        x = shells.copy()
        _place(x, latch, 0.0, 0.9)
        _place(x, _tone(int(0.05 * RATE), 660.0 * p, 520.0 * p, 0.015), 0.11, 0.45)
        return _fin(x, 0.65, 0.12)
    if base == "m8_shot":
        return _fin(_shot_mono(i, p, seed), stereo=0.16)
    if base == "m8_lmg":
        return _fin(_lmg_mono(i, p, seed), stereo=0.12)
    if base == "m8_rifle":
        return _fin(_rifle_mono(i, p, seed, False))
    if base == "m8_rifle_far":
        return _fin(_rifle_mono(i, p, seed, True), 0.7, 0.3)
    if base == "m8_sniper":
        return _fin(_sniper_mono(i, p, seed), 0.88, 0.22)
    if base in ("m8_hit", "m8_hit_far"):
        n = int(0.35 * RATE)
        x = _tone(n, 130.0 * p, 60.0 * p, 0.05) * 0.9
        x += _burst(n, seed, 0.03, lo=400.0, hi=2400.0 * p) * 0.7
        x += _burst(n, seed + 1, 0.06, hi=1200.0) * np.sin(2 * math.pi * 35.0 * _t(n)) * 0.4
        if base == "m8_hit_far":
            x = _lowpass(x, 1200.0, 2)
        return _fin(x, 0.8 if base == "m8_hit" else 0.6)
    if base == "m8_head":
        n = int(0.4 * RATE)
        x = _burst(n, seed, 0.004, lo=2500.0) * 0.9 + _tone(n, 520.0 * p, 260.0 * p, 0.03) * 0.6
        k = n - int(0.02 * RATE)
        _place(x, _burst(k, seed + 1, 0.05, hi=1800.0), 0.02, 0.7)
        return _fin(x, 0.8)
    if base == "m8_dirt":
        n = int(0.4 * RATE)
        x = _burst(n, seed, 0.02, hi=1500.0 * p) + _tone(n, 170.0 * p, 120.0, 0.03) * 0.5
        rng = np.random.default_rng(seed + 2)
        for _ in range(7):                                     # grit coming back down
            k = int(0.012 * RATE)
            _place(x, _burst(k, int(rng.integers(1, 99999)), 0.003, lo=2200.0),
                   float(rng.uniform(0.05, 0.3)), float(rng.uniform(0.05, 0.16)))
        return _fin(x, 0.75)
    if base == "m8_ric":
        n = int(0.6 * RATE)
        f0 = 2900.0 * p
        x = _tone(n, f0, f0 * 0.6, 0.09) * 0.5 + _tone(n, f0 * 1.48, f0 * 0.9, 0.06) * 0.25
        x += _burst(n, seed, 0.004, lo=2400.0) * 0.8
        x += _burst(n, seed + 1, 0.05, lo=600.0, hi=3000.0) * 0.3
        return _fin(x, 0.75, 0.25)
    if base == "m8_flesh":
        n = int(0.3 * RATE)
        x = _burst(n, seed, 0.025, hi=700.0 * p) + _tone(n, 85.0 * p, 60.0 * p, 0.06) * 0.8
        x += _burst(n, seed + 1, 0.003, lo=2000.0) * 0.25
        return _fin(x, 0.8)
    if base == "m8_cloth":
        n = int(0.35 * RATE)
        t = _t(n)
        x = _highpass(_lowpass(_noise(n, seed), 5000.0, 1), 1500.0)
        x *= np.exp(-((t - 0.05) ** 2) / 0.0012) + 0.6 * np.exp(-((t - 0.16 * p) ** 2) / 0.003)
        return _fin(x, 0.5)
    if base == "m8_elec_arc":
        return _fin(_elec_arc_mono(i, p, seed), 0.76, 0.24)
    raise ValueError("Unknown M8 sound: " + name)


@lru_cache(maxsize=4)
def loop_pcm(name):
    """Seamless loops: whole cycles only, and noise filtered circularly (FFT)."""
    if name == "m8_drone":
        dur = 8.0
        n = int(RATE * dur)
        t = _t(n)
        x = (np.sin(2 * math.pi * 55.0 * t) * 0.30 + np.sin(2 * math.pi * 55.25 * t) * 0.28
             + np.sin(2 * math.pi * 82.5 * t) * 0.14 + np.sin(2 * math.pi * 110.125 * t) * 0.07)
        x *= 0.78 + 0.22 * np.sin(2 * math.pi * t / dur)
        x += _lowpass(_noise(n, 8901), 140.0, 2) * 1.6
        stereo = 0.30
    elif name == "m8_road_wind":
        dur = 8.0
        n = int(RATE * dur)
        t = _t(n)
        gust = 0.60 + 0.25 * np.sin(2 * math.pi * t / dur * 2.0 + 0.7) \
            + 0.15 * np.sin(2 * math.pi * t / dur * 5.0)
        x = _lowpass(_noise(n, 8911), 420.0, 2) * gust * 2.2
        whistle = _highpass(_lowpass(_noise(n, 8912), 1900.0, 2), 1300.0)
        x += whistle * (0.5 + 0.5 * np.sin(2 * math.pi * t / dur * 3.0 + 2.0)) * 1.1
        stereo = 0.36
    elif name == "m8_engine":
        dur = 2.0
        n = int(RATE * dur)
        t = _t(n)
        lope = 0.62 + 0.38 * np.sin(2 * math.pi * 9.5 * t)
        x = (np.sin(2 * math.pi * 38.0 * t) * 0.34 + np.sin(2 * math.pi * 76.0 * t) * 0.20
             + np.sin(2 * math.pi * 114.0 * t) * 0.10 + np.sin(2 * math.pi * 152.0 * t) * 0.05) * lope
        x += _lowpass(_noise(n, 8921), 380.0, 2) * 1.4 * lope
        x += np.sin(2 * math.pi * 684.0 * t) * 0.018              # gearbox whine
        stereo = 0.16
    elif name == "m8_train":
        # the diesel under the cars, and the wheel-sets over the rail joints
        dur = 4.0
        n = int(RATE * dur)
        t = _t(n)
        lope = 0.8 + 0.2 * np.sin(2 * math.pi * 4.0 * t)
        x = (np.sin(2 * math.pi * 30.0 * t) * 0.30 + np.sin(2 * math.pi * 60.0 * t) * 0.18
             + np.sin(2 * math.pi * 90.0 * t) * 0.08) * lope
        # filter the noise twice round so the loop point carries the filter state
        nz = np.tile(_noise(n, 8961), 2)
        x += _lowpass(nz, 160.0, 2)[n:] * 1.8
        nz = np.tile(_noise(n, 8962), 2)
        x += _highpass(_lowpass(nz, 2400.0, 2), 900.0)[n:] * 0.08
        k = int(0.05 * RATE)
        for beat in range(4):
            for at, gain in ((0.0, 0.5), (0.12, 0.42), (0.52, 0.38), (0.64, 0.32)):
                click = _burst(k, 8970 + beat * 7 + int(at * 100), 0.006, lo=700.0, hi=4200.0)
                click += _tone(k, 820.0, 560.0, 0.012) * 0.4
                _place(x, click, beat + at + 0.1, gain)
        stereo = 0.28
    elif name == "m8_heli":
        dur = 2.0
        n = int(RATE * dur)
        t = _t(n)
        slap = (0.5 + 0.5 * np.sin(2 * math.pi * 12.0 * t)) ** 3
        x = np.sin(2 * math.pi * 24.0 * t) * slap * 0.7
        nz = np.tile(_noise(n, 8981), 2)
        x += _lowpass(nz, 420.0, 2)[n:] * (0.4 + 1.4 * slap)
        x += np.sin(2 * math.pi * 410.0 * t) * 0.025
        stereo = 0.26
    elif name == "m8_radio_hiss":
        dur = 4.0
        n = int(RATE * dur)
        t = _t(n)
        nz = np.tile(_noise(n, 9003), 2)
        x = _highpass(_lowpass(nz, 2800.0, 2), 950.0)[n:] * (0.45 + 0.15 * np.sin(2 * math.pi * 1.5 * t))
        x += np.sin(2 * math.pi * 60.0 * t) * 0.025
        stereo = 0.08
    else:
        raise ValueError("Unknown M8 loop: " + name)
    pk = float(np.max(np.abs(x))) or 1.0
    x = x * (0.8 / pk)
    # the delayed side wraps round the seam, so the loop point stays silent
    pcm = np.column_stack((x, (1.0 - stereo) * x + stereo * np.roll(x, int(0.011 * RATE))))
    pcm.setflags(write=False)
    return pcm


GENERATORS = [(name, lambda name=name: _wav(loop_pcm(name))) for name in LOOPS]
GENERATORS += [(name, lambda name=name: _wav(shot_pcm(name))) for name in ONE_SHOTS]


# ── manager ─────────────────────────────────────────────────────────────────
class M8Audio(M7Audio):
    """M7Audio with M8's own guns, hits and bed.  Silent-safe everywhere."""

    def __init__(self, manager):
        super().__init__(manager)
        try:
            manager.register_lazy_generators(GENERATORS)
        except Exception:
            pass
        self._rng = random.Random()
        self._last = {}
        self._pending = []           # [seconds left, pool, volume, pan]
        self._bed = None
        self._drive = 1.0
        self._duck = 1.0
        self._duck_hold = 0.0
        self._applied = {}
        self._clock = 0.0
        self._gate = {}
        self._film = None
        self._film_at = 0.0

    def warm(self):
        super().warm()
        for name in WARM:
            try:
                self.manager.get_sound(name)
            except Exception:
                pass

    # pools ----------------------------------------------------------------
    def _pool(self, pool, volume, pan=None, fallback=None):
        """One take from ``pool``, never the one just heard, with a little gain
        jitter; ``fallback`` (an M7 name) plays when the take is missing."""
        if self.closed:
            return
        count = POOLS.get(pool, 0)
        name = pool
        if count > 1:
            last = self._last.get(pool, -1)
            pick = self._rng.randrange(count - 1)
            if last >= 0 and pick >= last:
                pick += 1
            self._last[pool] = pick
            name = "%s_%d" % (pool, pick + 1)
        try:
            have = self.manager.get_sound(name) is not None
        except Exception:
            have = False
        if not have:
            if fallback:
                self._one(fallback, volume)
            return
        try:
            ch = self.manager.play(name, volume=volume * self._rng.uniform(0.9, 1.0))
        except Exception:
            return
        if ch is None:
            return
        if pan:
            pan = max(-1.0, min(1.0, float(pan)))
            try:
                ch.set_volume(min(1.0, 1.0 - pan), min(1.0, 1.0 + pan))
            except Exception:
                pass
        self.one_shots.append((ch, ch.get_sound()))
        if len(self.one_shots) > 24:
            self.one_shots = [(c, s) for c, s in self.one_shots
                              if c.get_busy() and c.get_sound() is s]

    def _later(self, delay, pool, volume, pan=None):
        if delay <= 0.0:
            self._pool(pool, volume, pan)
        elif len(self._pending) < 16:
            self._pending.append([float(delay), pool, volume, pan])

    # bed ------------------------------------------------------------------
    def bed(self, cue, drive=1.0):
        """Drive the ambience bed toward ``cue`` (None = off); call every frame.
        ``drive`` (0..1) is how hard the engine layer is working."""
        if cue != self._bed:
            for name, _gain in BEDS.get(self._bed, ()):
                self.stop_loop(name)
            self._bed = cue
        for name, gain in BEDS.get(cue, ()):
            if name not in self.loops:      # also retries a layer the mixer had no channel for
                self.start_loop(name, gain)
        self._drive = max(0.0, min(1.0, float(drive)))

    def duck(self, depth=0.35, hold=0.2):
        self._duck = min(self._duck, depth)
        self._duck_hold = max(self._duck_hold, hold)

    def update(self, dt):
        """Bed ducking and delayed layers; call every frame the scene updates."""
        if self.closed or self.paused:
            return
        self._clock += dt
        if self._duck_hold > 0.0:
            self._duck_hold -= dt
        elif self._duck < 1.0:
            self._duck = min(1.0, self._duck + dt / DUCK_RELEASE_S)
        if self._pending:
            due = []
            for item in self._pending:
                item[0] -= dt
                if item[0] <= 0.0:
                    due.append(item)
            self._pending = [item for item in self._pending if item[0] > 0.0]
            for _left, pool, volume, pan in due:
                self._pool(pool, volume, pan)
        for name in self.loops:
            self._apply(name)

    def _apply(self, name):
        ch = self.loops.get(name)
        if ch is None:
            return
        gain = self.gains.get(name, 0.2)
        if name in LOOPS:
            gain *= self._duck
            if name == "m8_engine":
                gain *= 0.35 + 0.65 * self._drive
        master = float(getattr(self.manager, "master_volume", 0.8))
        sfx = float(getattr(self.manager, "sfx_volume", 1.0))
        vol = round(max(0.0, min(1.0, master * sfx * gain)), 3)
        if self._applied.get(name) == (ch, vol):
            return
        self._applied[name] = (ch, vol)
        try:
            ch.set_volume(vol)
        except Exception:
            pass

    def stop_loops(self):
        super().stop_loops()
        self._bed = None
        self._applied.clear()
        self._duck, self._duck_hold = 1.0, 0.0

    def stop(self):
        self._pending.clear()
        super().stop()

    def _ready(self, key, gap):
        """Rate limit: True at most once per ``gap`` seconds of update time."""
        if self._clock - self._gate.get(key, -9.0) < gap:
            return False
        self._gate[key] = self._clock
        return True

    def film(self, scene):
        """Per frame while an M8 film shot plays: its score cue and bed."""
        now = time.monotonic()
        dt = min(0.1, max(0.0, now - self._film_at)) if self._film_at else 0.0
        self._film_at = now
        spec = FILM.get(scene)
        if spec is not None:
            self._film = spec
        if self._film is None:
            return
        music(self.manager, self._film[0])
        self.bed(self._film[1], 0.0)
        self.update(dt)

    def film_end(self):
        self._film = None
        self._film_at = 0.0
        self.bed(None)

    def trac_off(self):
        # M7's version stops every loop; here the bed belongs to the scene.
        self.stop_loop("m7_trac_idle")
        self.stop_loop("m7_trac_move")
        self._one("m7_trac_off", 0.45)

    # guns -----------------------------------------------------------------
    def shot(self, _suppressed=True, slow=False):
        """Biribel's shotgun.  ``slow``: the last round, pitched down with its tail."""
        if slow:
            self.duck(0.15, 1.2)
            self._pool("m8_shot_slow", 0.72, fallback="shotgun_blast")
        else:
            self.duck(0.30, 0.22)
            self._pool("m8_shot", 0.62, fallback="shotgun_blast")

    def lmg_shot(self):
        """Biribel's LMG on the chase: a light duck so a long burst does not pump the bed."""
        self.duck(0.55, 0.12)
        self._pool("m8_lmg", 0.5, fallback="m6_rifle_crack")

    def rifle_shot(self):
        """Biribel's OS-12 in the trap: fast, heavy, and it ducks the bed hard."""
        self.duck(0.55, 0.10)
        self._pool("m8_lmg", 0.52, fallback="m6_rifle_crack")

    def guard_shot(self, pan=0.0, dist=18.0):
        """Their rifles: thinner than the shotgun, placed left/right, far ones dull."""
        self.duck(0.60, 0.10)
        vol = 0.16 + 0.34 * max(0.0, 1.0 - dist / 60.0)
        self._pool("m8_rifle_far" if dist > FAR_M else "m8_rifle", vol, pan,
                   fallback="m6_rifle_crack")

    def sniper_shot(self, pan=0.0, dist=40.0):
        """Overwatch: the crack comes first, the bolt report after it."""
        self.duck(0.28, 0.35)
        vol = 0.42 + 0.26 * max(0.0, 1.0 - dist / 95.0)
        self._pool("m8_sniper", vol, pan, fallback="m6_rifle_crack")

    def impact(self, on_enemy=False, dist=0.0, pan=0.0):
        delay = dist / SOUND_MPS if dist > 6.0 else 0.0
        if on_enemy:
            self._later(delay, "m8_hit_far" if dist > FAR_M else "m8_hit", 0.5, pan)
        else:
            self._later(delay, "m8_dirt", 0.34 * max(0.4, 1.0 - dist / 90.0), pan)

    def headshot(self, dist=0.0, pan=0.0):
        self._later(dist / SOUND_MPS if dist > 6.0 else 0.0, "m8_head", 0.55, pan)

    def metal(self, pan=0.0, volume=0.38):
        self._pool("m8_ric", volume, pan, fallback="m6_tink")

    # plaza hazards & PA ---------------------------------------------------
    def barrel_boom(self, pan=0.0, dist=15.0):
        """A fuel drum going up: the plaza ducks, the echo comes back off the booths."""
        self.duck(0.20, 0.55)
        vol = 0.60 + 0.25 * max(0.0, 1.0 - dist / 55.0)
        self._pool("m8_barrel_boom", vol, pan, fallback="explosion")

    def spark_pop(self, pan=0.0):
        """A floodlight fuse letting go: an arc, then glass."""
        self.duck(0.55, 0.18)
        self._pool("m8_spark_pop", 0.58, pan, fallback="m6_tink")

    def pa_squelch(self):
        """The plaza loudspeaker keying up."""
        self._pool("m8_pa_squelch", 0.42, fallback="squelch_head")

    def smoke_hiss(self, pan=0.0):
        """A smoke canister burning off on the asphalt."""
        self._pool("m8_smoke", 0.56, pan, fallback="m6_tink")

    def elec_arc(self, pan=0.0):
        """Sustained high-voltage arc crackle."""
        if self._ready("elec_arc", 0.09):
            self._pool("m8_elec_arc", 0.54, pan, fallback="m8_spark_pop")

    def breaker_pop(self, pan=0.0):
        """Main security-room breaker blowing out."""
        self.duck(0.42, 0.35)
        self._pool("m8_breaker_pop", 0.72, pan, fallback="m8_spark_pop")

    def pistol_shot(self, pan=0.0):
        """Indoor pistol misfire crack."""
        self.duck(0.35, 0.22)
        self._pool("m8_pistol_shot", 0.64, pan, fallback="m8_rifle_1")

    def body_fall(self, pan=0.0, dist=8.0):
        """Heavy body thud onto the floor."""
        vol = 0.56 * max(0.3, 1.0 - dist / 35.0)
        self._pool("m8_fall_heavy", vol, pan, fallback="m6_body_thud")

    def door_kick(self):
        """Boot slamming through the study double doors."""
        self.duck(0.34, 0.30)
        self._pool("m8_door_kick", 0.78, fallback="m8_fall_heavy")

    def pickup(self):
        """The supply crate latch and the shells going into the pocket."""
        self._pool("m8_pickup", 0.55, fallback="reload")

    def rifle_handle(self):
        """Mechanical catch/bolt handling tick for the OS-12 reload."""
        self._one("rifle_handle", 0.42)

    # the ridge ------------------------------------------------------------
    def safety_click(self):
        self._one("m8_safety_click", 0.34)

    def bolt_cycle(self):
        self._one("m8_bolt_cycle", 0.54)

    def exhale(self):
        if self._ready("exhale", 0.45):
            self._one("m8_exhale", 0.34)

    def heartbeat(self):
        if self._ready("heartbeat", 0.80):
            self._one("m8_heartbeat", 0.42)

    def ridge_echo(self):
        self._one("m8_ridge_echo", 0.64)

    def dead_carrier(self):
        self._one("m8_dead_carrier", 0.50)

    def ridge_kill_silence(self):
        """Cut all ridge loops to dead vacuum silence, then roll the cliff echo."""
        self.stop_loops()
        self._pending.clear()
        self._later(0.42, "m8_ridge_echo", 0.64)

    # Biribel ---------------------------------------------------------------
    def hurt(self, dmg=10.0):
        if not self._ready("hurt", 0.12):
            return
        self.duck(0.5, 0.15)
        self._pool("m8_hurt", 0.32 + 0.25 * min(1.0, float(dmg) / 30.0),
                   fallback="bullet_impact_enemy")

    def down(self):
        """Biribel goes down: everything drops away under the ring."""
        self.duck(0.08, 2.2)
        self._pool("m8_fall_heavy", 0.5)
        self._one("tinnitus", 0.22)

    def step(self, i, grate=False):
        if grate:
            self._one("footstep_grate_%d" % (int(i) % 2 + 1), 0.16)
        else:
            self._one("footstep", 0.12)

    def rung(self):
        self._pool("m8_rung", 0.30, fallback="footstep_metal_1")

    def enemy_down(self, dist=12.0, pan=0.0):
        vol = 0.42 * max(0.25, 1.0 - dist / 50.0)
        self._later(0.45 + dist / SOUND_MPS, "m6_body_thud", vol, pan)

    # the tractor -----------------------------------------------------------
    def hull_hit(self):
        if self._ready("hull", 0.09):
            self._pool("m8_hull", 0.34, self._rng.uniform(-0.4, 0.4), fallback="m6_tink")

    def crash(self, pan=0.0):
        self.duck(0.4, 0.3)
        self._pool("m8_crash", 0.55, pan, fallback="explosion")

    def rocket(self):
        self.duck(0.45, 0.25)
        self._pool("m8_rocket", 0.68, fallback="explosion")

    def missile_warn(self):
        if self._ready("mwarn", 1.1):
            self._pool("m8_missile_warn", 0.44)

    def overheat(self):
        self._pool("m8_overheat", 0.56, fallback="m8_smoke")

    def flare_pop(self):
        self._pool("m8_flare", 0.62, fallback="m8_smoke")

    def klaxon(self):
        if self._ready("klaxon", 0.55):
            self._pool("m8_klaxon", 0.48, fallback="m8_missile_warn")

    def flak_pop(self, pan=0.0, dist=24.0):
        if self._ready("flak", 0.14):
            vol = 0.30 + 0.34 * max(0.0, 1.0 - dist / 75.0)
            self._pool("m8_flak", vol, pan, fallback="m8_barrel_boom")

    def rotor_pass(self, pan=0.0):
        """Close-range gunship flyby Doppler rotor slap."""
        if self._ready("rotor_pass", 1.1):
            self.duck(0.68, 0.25)
            self._pool("m8_rotor_pass", 0.68, pan, fallback="m8_heli")

    def subsys_boom(self, pan=0.0, dist=35.0):
        """Armored subsystem blowout on Ucilev's gunship."""
        self.duck(0.18, 0.60)
        vol = 0.72 + 0.20 * max(0.0, 1.0 - dist / 80.0)
        self._pool("m8_subsys_boom", vol, pan, fallback="m8_barrel_boom")

    def horn(self, volume=0.45):
        if self._ready("horn", 2.5):
            self._pool("m8_horn", volume)

    # the catwalk ----------------------------------------------------------
    def body_hit(self, n, head=False, final=False, fall_in=0.55):
        """Round ``n`` (1..6) into Vasile: slap, cloth, and what the hit does to him.
        ``fall_in``: real seconds until the body lands after the final round."""
        weight = min(1.0, 0.5 + 0.06 * n)
        if head:
            self._pool("m8_head", 0.6, fallback="m6_headshot")
        self._pool("m8_flesh", weight * (0.6 if head else 0.85), fallback="bullet_impact_enemy")
        self._later(0.04, "m8_cloth", 0.30)
        if final:
            self._pool("m8_hit", 0.6)
            self._later(fall_in, "m8_fall_heavy", 0.75)
        elif n == 3:
            self._later(0.40, "m8_fall_light", 0.45)      # the knee goes down

    def miss(self, pan=0.0, steel=True):
        """A round that went past him: the rail or the road beyond, a beat later."""
        if steel:
            self._later(0.03, "m8_ric", 0.40, pan)
        self._later(0.07, "m8_dirt", 0.26, pan)


AUDIO = None


def instance(manager):
    """The mission singleton; a stopped one is replaced on next use."""
    global AUDIO
    if AUDIO is None or AUDIO.closed:
        AUDIO = M8Audio(manager)
    return AUDIO
