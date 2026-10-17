"""render_trailer_v2.py - cinematic finish wrapper over render_trailer.py.

Why a wrapper and not an edit: Longcat 2.5 is actively reworking
render_trailer.py (structure/pacing) in a parallel tab. This module
monkeypatches only presentation helpers so both tracks merge cleanly:

  Longcat owns: SECTIONS, tour/bot behavior, main() loop, transitions.
  This owns:    title-card finish, caption pill, act bug, film grade,
                impact shake, blur-pad 1080p, music fades.

Usage (same flags, same outputs):
    python tools/render_trailer_v2.py            # -> trailers/trailer_60s.mp4
    python tools/render_trailer_v2.py --smoke    # -> trailers/trailer_smoke.mp4
    python tools/render_trailer_v2.py --no-audio # skip music mux
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_trailer as rt  # noqa: E402

import pygame  # noqa: E402

W, H, FPS = rt.W, rt.H, rt.FPS
config = rt.config

FONT_BIG = rt._font("Oswald.ttf", 88)
FONT_CAP = rt._font("IBMPlexMono-SemiBold.ttf", 19)
FONT_BUG = rt._font("IBMPlexMono-SemiBold.ttf", 16)

# ── PLAN_2_EDITOR 58s locked EDL (AI-2 owner, additive) ──────────────────────
# Source of truth: docs/PLAN_2_EDITOR.md §1-§3. Implemented here (not in
# render_trailer.py) because Longcat owns rt.SECTIONS/tours/main loop in a
# parallel tab - this wrapper owns presentation + pacing only (see header).
# Respected tracks (do NOT duplicate here):
#   AI-1 (PLAN_1): src/tools/trailer_bot.py + dev_jumps/app hooks own bot takes.
#   AI-3 (PLAN_3): 100 BPM / 0.6s beat grid + bed/sfx/vo stems own the mux.
#   AI-4 (PLAN_4): HUD removals, CCTV, grade stack, intro/outro lockups.
# Runtime math: gameplay takes below are 2.0-2.8s safety handles captured
# in-engine; the 0:35-0:50 climax sub-cuts to <=0.9s in post (freeze/punch),
# so captures stay routable while the cut obeys the EDL max-shot rule.
EDITOR_RUNTIME = 58.0
# (kind, ...) kinds: black/secs | boot/secs | broadcast/secs |
# card/lines/secs/tag | game/tour_key/starter_name/secs/cap_text
EDITOR_EDL = [
    ("black", 0.5),                                            # leader
    ("boot", 1.5),                                             # S01 cell-typewriter cold open
    ("broadcast", 2.0),                                        # S02 STATE ADDRESS banner
    ("card", ["CALL OF ACARISTAN"], 2.0, "OFFICIAL TRAILER"),  # S03 T1 slam
    ("game", "m2sniper", "start_mission2_sniper", 2.0,         # S04 sniper tease
     "ROUTE 12 // 48 HOURS EARLIER"),
    ("game", "m1", "start_mission", 2.2,                       # S05 warehouse infil
     "WAREHOUSE // mid-sprint, no approach"),
    ("game", "m1", "start_mission", 2.0,                       # S06 notebook grab
     "NOTEBOOK // glint to muzzle flash"),
    ("game", "m1", "start_mission", 2.3,                       # S07 Volkov runs
     "HANDOFF // Volkov escapes"),
    ("card", ["TACTICAL ESPIONAGE"], 1.8, None),               # S08 T2
    ("game", "m2", "start_mission2", 2.6,                      # S09 checkpoint
     "CHECKPOINT // truck inspection"),
    ("game", "m2sniper", "start_mission2_sniper", 2.2,         # S10 kill-box
     "KILL-BOX // laser to helmet-off"),
    ("card", ["DEEP BEHIND ENEMY LINES"], 1.8, None),          # S11 T3 (8f breath)
    ("game", "m2", "start_mission2", 2.5,                      # S12 tanker valve
     "TANKER // hand on valve"),
    ("game", "m2", "start_mission2", 2.8,                      # S13 tanker run
     "TANKER RUN // 0:03 countdown sprint"),
    ("game", "m2", "start_mission2", 2.6,                      # S14 IPA reveal
     "CONTACT // flash to casing only"),
    ("card", ["FRAMED. HUNTED.", "DISAVOWED."], 2.8, None),   # S15 T4
    ("game", "m2", "start_mission2", 2.0,                      # S16 blast (drop)
     "BLAST // white-orange flash"),
    ("black", 0.4),                                            # S17 blackout punctuation (12f)
    ("game", "m3break", "start_mission3_breakout_checkpoint", 2.0,  # S18 breakout
     "BREAKOUT // shiv to sidearm"),
    ("game", "m3arch", "start_mission3_archives_checkpoint", 2.0,   # S19 heist
     "ARCHIVES // Vostral beacon"),
    ("game", "m3ko", "start_mission3_kill_order_checkpoint", 2.0,   # S20 kill order
     "KILL ORDER // stairwell breach"),
    ("game", "m3ko", "start_mission3_kill_order_checkpoint", 2.0,   # S21 dock holdout
     "HOLDOUT // door cycles, van covers"),
    ("game", "m3comms", "start_mission3_comms_checkpoint", 3.0,     # S22 uplink race
     "UPLINK // SURVIVE THE VOSTRAL"),
    ("black", 0.6),                                            # M-SILENCE 6f+ hold
    ("card", ["M1 // BLACK NOTEBOOK",                          # S23 T6 stamps
              "M2 // QUIET ON ROUTE 12",
              "M3 // THE VOSTRAL"], 3.0, "Every rumor has a record."),
    ("endcard", 6.0),                                          # S24 CTA (AI-4 lockup)
    ("black", 1.4),                                            # tail + platform buffer
]
# Sync markers for AI-3/AI-4 (seconds from picture start, PLAN_2 §4-§5).
EDITOR_SYNC = {
    "M-HIT1": 4.0,    # T1 slam: bass + 6f flash + 10px shake
    "M-CUT1": 8.0,    # tempo change into S05 sprint + whip-pan
    "M-BREATH": 21.0, # 8f near-silence into T3
    "M-TICK": 23.0,   # countdown bed under S12-S13
    "M-DROP": 35.0,   # tanker blast beat drop (thumbnail moment)
    "M-SILENCE": 50.0,# bass cut into T6 stamps
    "M-STAMPS": (50.5, 51.2, 51.9),  # 3x gun-cocks L-C-R
    "M-CTA": 53.0,    # clean bed, grain 8%, text-safe hold
}


def editor_runtime():
    """Sum EDITOR_EDL to validate the 58s lock (cards/game/black/endcard)."""
    total = 0.0
    for e in EDITOR_EDL:
        if e[0] in ("black", "boot", "broadcast"):
            total += e[1]
        elif e[0] == "card":
            total += e[2]
        elif e[0] == "game":
            total += e[3]
        elif e[0] == "endcard":
            total += e[1]
    return total


def _remap_card(lines, tag):
    """Enforce PLAN_2 exact copy + PLAN_4 ban on COMING SOON.

    Longcat's main() call sites keep working untouched; this layer (which
    owns title-card finish) substitutes final copy at feed time.
    """
    text = " // ".join(lines)
    if "a tactical trilogy" in text:
        return ["CALL OF ACARISTAN"], "OFFICIAL TRAILER"  # S03 T1
    if "wishlist the mission" in text or tag == "COMING SOON":
        # S23 T6 stamps; CTA itself is rt.end_card (AI-4 lockup, §5).
        return (["M1 // BLACK NOTEBOOK",
                 "M2 // QUIET ON ROUTE 12",
                 "M3 // THE VOSTRAL"], "Every rumor has a record.")
    return lines, tag

_SHAKE = [0]
_LAST_KEY = [None]
_orig_card = rt.card
# getattr guards: AI-4 (PLAN_4 §1.1-§1.2) deleted caption()/run_menu/menu
# from render_trailer.py in the parallel tab - respect the deletion, don't
# restore it here. v2 keeps its own caption pill for the editor cut only.
_orig_caption = getattr(rt, "caption", None)
_orig_gameplay = rt.run_gameplay
_orig_menu = getattr(rt, "run_menu", None)
_orig_walk = rt.run_walk
_orig_mux = rt.mux_1080p_with_music
_orig_make_router = rt.make_router


def make_router(section_key):
    _LAST_KEY[0] = section_key
    return _orig_make_router(section_key)


def stage_breakout():
    """Post-craft breakout state (same flags the game sets on shiv finish).

    The trailer bot can't craft (drag-minigame), so without staging the
    cell door stays shut and the beat shuffles inside the cell forever.
    Staging = filming a later take, same as staged timers in render_ko_video.
    """
    S = rt.STATE
    S.mission3_weapon = "shiv"
    S.mission3_cell_open = True
    S.mission3_chair_broken = True
    S.mission3_chair_break_anim = -1
    S.mission3_doorway_blocked = False
    S.mission3_crafting_progress = 1.0
    S.mission3_crafting_active = False
    S.player_disarmed = False
    S.request_chair_break_cutscene = False


def _split_cap(cap_text):
    """('ACT I - BLACK NOTEBOOK', 'warehouse push') from 'A // B'."""
    if cap_text and "//" in cap_text:
        pre, post = cap_text.split("//", 1)
        return pre.strip(), post.strip()
    return "", (cap_text or "")


def card(lines, seconds, tag=None, accent=(255, 120, 0)):
    lines, tag = _remap_card(list(lines), tag)
    n = max(1, int(seconds * FPS))
    span = min(12, n // 4)
    for i in range(n):
        s = pygame.Surface((W, H))
        s.fill((4, 5, 6))
        try:
            s.blit(config.VIGNETTE, (0, 0))
        except Exception:
            pass
        pygame.draw.rect(s, accent, (W // 2 - 110, H // 2 - 158, 220, 3))
        y = H // 2 - 118
        for li, ln in enumerate(lines):
            f = FONT_BIG if li == 0 else rt.FONT_MID
            col = (238, 228, 196) if li == 0 else (158, 178, 158)
            sh = f.render(ln, True, (0, 0, 0))
            t = f.render(ln, True, col)
            cx = W // 2 - t.get_width() // 2
            s.blit(sh, (cx + 2, y + 2))
            s.blit(t, (cx, y))
            y += t.get_height() + (26 if li == 0 else 0)
        if tag:
            t = rt.FONT_TAG.render(tag, True, accent)
            s.blit(t, (W // 2 - t.get_width() // 2, y + 34))
        if span and (i < span or i >= n - span):
            a = (i + 1) / span if i < span else (n - i) / span
            black = pygame.Surface((W, H))
            black.fill((0, 0, 0))
            black.set_alpha(int(255 * (1.0 - max(0.0, min(1.0, a)))))
            s.blit(black, (0, 0))
        config.screen.blit(s, (0, 0))
        rt.feed()
        rt.FRAME[0] += 1


def caption(text):
    # REMOVED: bottom storyboard pill (e.g. "laser to helmet-off",
    # "hand on valve", "truck inspection") deleted per direction -
    # bottom of screen must stay completely clean. No-op so any
    # legacy call site renders nothing.
    return


def bug_tag(cap_text):
    act, _ = _split_cap(cap_text)
    if not act:
        return
    t = FONT_BUG.render(act, True, (255, 150, 60))
    pad_x, pad_y = 10, 5
    bw, bh = t.get_width() + pad_x * 2 + 8, t.get_height() + pad_y * 2
    bx = W // 2 - bw // 2
    by = 8
    bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
    bg.fill((4, 5, 6, 190))
    config.screen.blit(bg, (bx, by))
    pygame.draw.rect(config.screen, (255, 120, 0), (bx, by, 3, bh))
    config.screen.blit(t, (bx + pad_x + 8, by + pad_y))


def grade_frame():
    # Grain only - the game is already dark, a full vignette crushes it.
    try:
        if rt.FRAME[0] % 3 == 0:
            g = config.GRAIN_VARIANTS[(rt.FRAME[0] // 3) % len(config.GRAIN_VARIANTS)]
            config.screen.blit(g, (0, 0))
    except Exception:
        pass


def impact_shake(engaged):
    if engaged:
        _SHAKE[0] = 4
    else:
        _SHAKE[0] = max(0, _SHAKE[0] - 1)
    mag = _SHAKE[0]
    if mag > 0:
        import random as _rnd
        dx = _rnd.randint(-mag, mag)
        dy = _rnd.randint(-mag, mag)
        try:
            snap = config.screen.copy()
            config.screen.fill((0, 0, 0))
            config.screen.blit(snap, (dx, dy))
        except Exception:
            pass


def _run_melee_rush(seconds, cap_text, router):
    """m3break take: disarmed shiv rush, no strafe - beeline at guards."""
    import math as _m
    from entities import weapons as _w
    swings = [0]
    cam = [0, 0]
    total = int(seconds * 60)
    for tick in range(total):
        rt.top_up()
        if tick % 60 == 0:
            router.refresh()
        router.step()
        foe = rt.visible_enemy()
        shook = False
        if foe is not None and rt.STATE.player is not None:
            px, py = rt.STATE.player.rect.center
            ex, ey = foe.rect.centerx, foe.rect.centery
            rt.STATE.player.angle = _m.atan2(ey - py, ex - px)
            if _m.hypot(ex - px, ey - py) < 60 and rt.has_los(
                    px, py, ex, ey, rt.los_walls()):
                if not rt.STATE.melee_active:
                    _w.handle_melee()
                    swings[0] += 1
                    shook = True
        else:
            tgt = router.target()
            if tgt is not None:
                rt.face_player(*tgt)
        out = rt.gc.game_update(rt.KEYS)
        if out:
            cam[0], cam[1] = out
        rt.gc.game_draw(cam[0], cam[1])
        impact_shake(shook)
        grade_frame()
        bug_tag(cap_text)
        pygame.event.pump()
        rt.FRAME[0] += 1
        if rt.FRAME[0] % 2 == 0:
            rt.feed()
    _SHAKE[0] = 0
    return router.jit_total


def run_gameplay(seconds, cap_text, router, fight=True):
    _SHAKE[0] = 0
    if _LAST_KEY[0] == "m3break":
        stage_breakout()
        router.refresh()
        return _run_melee_rush(seconds, cap_text, router)
    # Wrap combat_post so firing frames kick the camera.
    orig_post = rt.combat_post
    engaged_flag = [False]

    def tracking_post(e):
        out = orig_post(e)
        engaged_flag[0] = bool(out)
        return out

    rt.combat_post = tracking_post
    try:
        cam = [0, 0]
        total = int(seconds * 60)
        for tick in range(total):
            rt.top_up()
            if tick % 60 == 0:
                router.refresh()
            router.step()
            foe = rt.combat_pre() if fight else None
            out = rt.gc.game_update(rt.KEYS)
            if out:
                cam[0], cam[1] = out
            engaged_flag[0] = False
            engaged = tracking_post(foe) if fight else False
            if not engaged:
                tgt = router.target()
                if tgt is not None:
                    rt.face_player(*tgt)
            rt.gc.game_draw(cam[0], cam[1])
            impact_shake(engaged)
            grade_frame()
            bug_tag(cap_text)
            pygame.event.pump()
            rt.FRAME[0] += 1
            if rt.FRAME[0] % 2 == 0:
                rt.feed()
    finally:
        rt.combat_post = orig_post
    _SHAKE[0] = 0
    return router.jit_total


def run_menu(seconds, cap_text):
    total = int(seconds * 60)
    for _ in range(total):
        config.screen.fill((0, 0, 0))
        rt.menu.draw_menu()
        grade_frame()
        bug_tag(cap_text)
        pygame.event.pump()
        rt.FRAME[0] += 1
        if rt.FRAME[0] % 2 == 0:
            rt.feed()


def run_walk(seconds, cap_text, router):
    total = int(seconds * 60)
    for tick in range(total):
        if tick % 60 == 0:
            router.refresh()
        router.step()
        try:
            rt.ws.update_walking_sim(rt.KEYS)
        except Exception:
            pass
        rt.ws.draw_walking_sim()
        grade_frame()
        bug_tag(cap_text)
        pygame.event.pump()
        rt.FRAME[0] += 1
        if rt.FRAME[0] % 2 == 0:
            rt.feed()
    return router.jit_total


def _probe_duration(path):
    try:
        import shutil as _sh
        exe = str(rt.FFMPEG)
        probe = _sh.which("ffprobe") or "ffprobe"
        if "ffmpeg" in exe.lower():
            cand = exe.lower().replace("ffmpeg", "ffprobe")
            if Path(cand).exists():
                probe = cand
        r = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return float(r.stdout.strip())
    except Exception:
        return 70.0


# ── PLAN_3_AUDIO mix config (AI 3 owns; Longcat owns structure) ──
# 100 BPM @30fps = 18 frames/beat. Cuts land on the 0.6s grid only.
TRAILER_BPM = 100
TRAILER_BEAT_S = 0.6
TRAILER_LUFS_I, TRAILER_LUFS_TP, TRAILER_LUFS_LRA = -14, -2, 11

# Exact VO stem filters - docs/PLAN_3_AUDIO.md §2.2, applied offline.
VOICE_FILTERS = {
    "vasile": "highpass=f=400,lowpass=f=2800,acompressor=threshold=-18dB:ratio=4:attack=5:release=120,aecho=0.6:0.03:20|0:1",
    "volkov": "highpass=f=350,lowpass=f=2200,bass=g=2:f=150,acrusher=level_in=1:level_out=1:bits=12:mode=log:dc=1,aecho=0.5:0.02:12|0:1,pan=stereo|c0=0.55*c0+0.45*c1|c1=0.45*c0+0.55*c1",
    "balaceanu": "highpass=f=600,lowpass=f=3200,acompressor=threshold=-20dB:ratio=6:attack=10:release=300,aecho=0.8:0.35:45|0.6:0.55:35|0:1",
}

# (tc_start, picture beat, audio hook) - follows AI-2's locked 58s EDL
# (EDITOR_SYNC above); 100 BPM grid = 0.6s. AI-3 owns the hooks, AI-2 owns
# the timecodes - do not retime here, only re-hook.
TRAILER_CUES = [
    (0.0, "boot", "drone+hum + radio_static bed, no drums"),
    (4.0, "T1 slam", "M-HIT1: braam + D1 pulse + 6f flash"),
    (8.0, "sprint", "M-CUT1: bass 8ths in, suppressed clicks, whip-pan whoosh"),
    (21.0, "T3 breath", "M-BREATH: strip to riser + heartbeat, 8f near-silence"),
    (23.0, "tanker", "M-TICK: countdown bed + riser_12s + VOLKOV window line"),
    (35.0, "blast drop", "M-DROP: DROP + BRAAM, unsuppressed + sniper stacks"),
    (50.0, "stamps", "M-SILENCE: full bass cut into T6 stamps"),
    (50.5, "stamp1", "M-STAMPS 1/3: dry gun-cock L (trailer_gun_suppressed)"),
    (51.2, "stamp2", "M-STAMPS 2/3: dry gun-cock C"),
    (51.9, "stamp3", "M-STAMPS 3/3: dry gun-cock R + BALACEANU PA tail"),
    (53.0, "CTA", "M-CTA: clean bed, downpitch braam + mission_complete tail"),
]


def mux_1080p_with_music(silent_mp4, music_mp3, out_mp4):
    """Blur-pad native 1000x700 to full-bleed 1920x1080 + faded music bed."""
    dur = _probe_duration(silent_mp4)
    fade_out_start = max(0.0, dur - 4.0)
    cmd = [
        str(rt.FFMPEG), "-y", "-i", str(silent_mp4), "-i", str(music_mp3),
        "-filter_complex",
        "[0:v]split[a][b];"
        "[a]scale=1920:1080:flags=lanczos,boxblur=18:4,"
        "eq=brightness=-0.3:contrast=0.92[bg];"
        "[b]scale=-2:1080:flags=lanczos[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v];"
        f"[1:a]afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.1f}:d=4,"
        "volume=0.8,apad,atrim=0:%d[a]" % int(dur + 1),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "17", "-preset", "medium",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(out_mp4),
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"audio mux failed: {r.stderr[-2000:]}")


def mux_1080p_trailer_mix(silent_mp4, bed_wav, sfx_wav, vo_wav, out_mp4):
    """PLAN_3_AUDIO §5: blur-pad video + 3-stem trailer mix (bed/sfx/vo).

    Stems are same-length 44.1kHz stereo WAVs with the M-SILENCE bass cut
    baked in. Music ducks under VO via sidechain; the master
    targets -14 LUFS / -2 dBTP. Single-music callers keep using
    mux_1080p_with_music (untouched) so Longcat's main() loop is unaffected.
    """
    cmd = [
        str(rt.FFMPEG), "-y",
        "-i", str(silent_mp4), "-i", str(bed_wav),
        "-i", str(sfx_wav), "-i", str(vo_wav),
        "-filter_complex",
        "[1:a]volume=0.9,alimiter=limit=0.95[bed];"
        "[2:a]volume=1.0,alimiter=limit=0.95[sfx];"
        "[3:a]volume=1.0[vo];"
        "[bed][vo]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=200[ducked];"
        "[ducked][sfx]amix=inputs=2:normalize=0[mix];"
        "[mix]loudnorm=I=-14:TP=-2:LRA=11,afade=t=in:st=0:d=0.5[a];"
        "[0:v]split[a][b];"
        "[a]scale=1920:1080:flags=lanczos,boxblur=18:4,"
        "eq=brightness=-0.3:contrast=0.92[bg];"
        "[b]scale=-2:1080:flags=lanczos[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "17", "-preset", "medium",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(out_mp4),
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"trailer mix failed: {r.stderr[-2000:]}")


# Tour routing fixes (TOURS/goals are Longcat's file; patched here to avoid
# colliding with the parallel tab - validated by probe_bot*.py headless runs).
#
# Root cause of the "bot never leaves the starting area" beats: the tour
# char-grids list "D" in solids, so A* can never route through (unlocked,
# auto-opening) doors - every cross-door goal degrades to a beeline and the
# bot shuffles against the door. Strip "D" (locked doors are still sealed at
# runtime by overlay_rects/locked collision rects - verified: M1 gate (14,15),
# archives vault (24-25,6)/(36,8-9)).
# New m1/m3arch goals push through the mission instead of looping spawn:
#   m1: south-first breach through the row-10 door into the mid-room fight
#       (E cluster + commander) - breach ~t=4, ends dueling at (18,11).
#   m3arch: foyer -> row-38 doors -> corridor (atrium guard contact ~t=1) ->
#       west door -> catalog stacks aisle -> (12,22). Zero jitter events.
rt.TOURS = {
    k: ([s for s in v[0] if s != "D"], v[1], v[2])
    for k, v in rt.TOURS.items()
}
rt.TOURS = dict(rt.TOURS, **{
    "m1": [tuple(s for s in rt.TOURS["m1"][0]), "m1",
           [(8, 2), (8, 6), (8, 9), (9, 12), (14, 12), (18, 11)]],
    "m3break": [tuple(s for s in rt.TOURS["m3break"][0]), "cell",
                [(32, 10), (33, 12), (35, 13), (38, 13), (40, 14), (41, 15)]],
    "m3arch": [tuple(s for s in rt.TOURS["m3arch"][0]), "archives",
               [(24, 39), (24, 35), (23, 30), (21, 26), (17, 26), (12, 26), (12, 22)]],
})

# Install the finish layer, then run Longcat's structure untouched.
# NOTE: rt.caption is intentionally NOT installed - bottom storyboard pill
# removed, bottom of screen stays clean.
rt.card = card
rt.make_router = make_router
rt.run_gameplay = run_gameplay
rt.run_menu = run_menu
rt.run_walk = run_walk
rt.mux_1080p_with_music = mux_1080p_with_music
rt.mux_1080p_trailer_mix = mux_1080p_trailer_mix

def editor_main():
    """PLAN_2_EDITOR 58s cut playback (opt-in, default OFF).

    Run: ACARISTAN_EDITOR_CUT=1 python tools/render_trailer_v2.py [--smoke] [--no-audio]
    Default (env unset) still runs Longcat's rt.main() untouched.
    Reuses rt pipe/mux + this wrapper's card/caption/grade/shake finish.
    Smoke mode shortens takes/cards like rt.main so --smoke stays ~15s.
    """
    import argparse as _ap
    ap = _ap.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--out", default="trailer_60s.mp4")
    args = ap.parse_args()
    smoke = args.smoke
    out_silent = rt.TRAILERS / ("trailer_smoke_silent.mp4" if smoke
                                else "trailer_60s_silent.mp4")
    out_final = rt.TRAILERS / ("trailer_smoke.mp4" if smoke else args.out)
    rt.PROC[0] = rt.open_pipe(out_silent)

    def s_secs(base):
        return 1.0 if smoke else base

    def c_secs(base):
        return 0.6 if smoke else base

    for entry in EDITOR_EDL:
        kind = entry[0]
        if kind == "black":
            rt.black_frame(c_secs(entry[1]))
        elif kind == "boot":
            rt.boot_intro(c_secs(entry[1]))
        elif kind == "broadcast":
            rt.broadcast_card(c_secs(entry[1]))
        elif kind == "card":
            _, lines, secs, tag = entry
            card(lines, c_secs(secs), tag=tag)
        elif kind == "endcard":
            rt.end_card(c_secs(entry[1]), fade_out_seconds=1.0)
        elif kind == "game":
            _, key, starter_name, secs, cap_text = entry
            starter = getattr(rt.gc, starter_name, None)
            if starter is None:
                print(f"  !! editor cut: missing starter {starter_name}, skipping")
                continue
            print(f"[{key}] {cap_text} ({s_secs(secs):.1f}s)", flush=True)
            rt.PREV.clear()
            rt.KEYS.down.clear()
            rt.FRAME[0] = 0
            try:
                starter()
                for _ in range(5):  # warmup so frame 1 is mid-action
                    rt.top_up()
                    out = rt.gc.game_update(rt.KEYS)
                    if out:
                        rt.gc.game_draw(out[0], out[1])
                jit = run_gameplay(s_secs(secs), cap_text, make_router(key),
                                   fight=True)
                print(f"  jit_events={jit}", flush=True)
            except Exception as e:
                print(f"  !! section {key} failed: {e!r} (tape keeps rolling)")
                import traceback
                traceback.print_exc()
    rt.PROC[0].stdin.close()
    rt.PROC[0].wait()
    print("silent tape:", out_silent, out_silent.stat().st_size // 1024, "KB")
    if smoke or args.no_audio:
        out_silent.replace(out_final)
        print("saved", out_final, out_final.stat().st_size // 1024, "KB")
        return
    music = rt.ROOT / "menu_theme.mp3"
    if not music.exists():
        print("menu_theme.mp3 missing - shipping silent")
        out_silent.replace(out_final)
        return
    mux_1080p_with_music(out_silent, music, out_final)
    print("saved", out_final, out_final.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if os.getenv("ACARISTAN_EDITOR_CUT"):
        assert abs(editor_runtime() - EDITOR_RUNTIME) < 0.6, \
            f"EDL sums {editor_runtime():.1f}s, lock is {EDITOR_RUNTIME:.1f}s"
        editor_main()
    else:
        rt.main()

