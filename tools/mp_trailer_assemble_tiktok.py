#!/usr/bin/env python3
"""9:16 TikTok cut of the multiplayer announcement.

Not a letterbox of the 16:9 master. Each beat is punched out of the
1000x700 retake tapes, then fitted to the 1080 frame WIDTH over a blurred
copy of itself, so nothing is ever cropped off the sides:

  lobby  - 640x700 window holding the ARENA MATCH / MATCH LOBBY plate
  fights - FULL 1000x700 frame. The old 504-wide track-crop sliced the
           top-score bar, the bottom weapon bar, nametags and edge
           players in half on a phone screen, so gameplay read as
           offscreen. Full-frame keeps every HUD element on screen; it
           renders smaller (1080x756 centred) but complete.

Hook-first ~30s. Source: trailers/mp_announce_retake_04 (override with
MP_ANNOUNCE_DIR). Output: mp_announcement_tiktok.mp4

    python tools/mp_trailer_assemble_tiktok.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAP = Path(os.environ.get(
    "MP_ANNOUNCE_DIR", str(ROOT / "trailers" / "mp_announce_retake_04"))
).resolve()
SFX_DIR = ROOT / "sfx_wav"
FONT_DIR = ROOT / "assets" / "fonts"
MUSIC = ROOT / "menu_theme.mp3"
OUT_FINAL = CAP / "mp_announcement_tiktok.mp4"

SRC_W, SRC_H, FPS = 1000, 700, 30
OUT_W, OUT_H = 1080, 1920
SR = 44100
ACCENT = "0xFF7800"
DIEGETIC_GAIN = -6.0
SAFE_TOP = 150
SAFE_BOT = 230

_MK = json.loads((CAP / "chapters.json").read_text(encoding="utf-8"))
_FOLEY = json.loads((CAP / "host_flow.foley.json").read_text(encoding="utf-8"))
HZ = float(_FOLEY["hz"])
GO_HOST = float(_MK["go_moment"]["sec"])
GO_CLIENT = float(_MK["go_moment_client"]["sec"])
HOST_END = float(_MK["combat_end"]["sec"])
CLIENT_END = float(_MK["combat_end_client"]["sec"])
GO_OFF = GO_HOST - GO_CLIENT


def _r(x):
    return round(float(x), 2)


def g(x) -> str:
    return f"{x:g}"


def ffmpeg_bin() -> str:
    for cand in (shutil.which("ffmpeg"), os.environ.get("FFMPEG", ""),
                 r"C:\ffmpeg\bin\ffmpeg.exe"):
        if cand and Path(cand).exists():
            return str(cand)
    raise SystemExit("ffmpeg not found")


FFMPEG = ffmpeg_bin()
FFPROBE = shutil.which("ffprobe") or r"C:\ffmpeg\bin\ffprobe.exe"


def graph_file(work: Path, name: str, text: str) -> str:
    p = work / f"{name}.ffgraph"
    p.write_text(text, encoding="utf-8")
    return str(p)


def run(args, label):
    t0 = time.time()
    r = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, errors="replace")
    if r.returncode != 0:
        sys.stderr.write(f"\n[FAIL] {label}\n$ {' '.join(str(a) for a in args)}\n")
        sys.stderr.write((r.stderr or "")[-4000:] + "\n")
        raise SystemExit(1)
    print(f"  ok   {label}  ({time.time() - t0:.1f}s)")
    return r


def dur_of(path: Path) -> float:
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path], "probe")
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _screen(ev):
    if ev.get("x") is None or ev.get("cam_x") is None:
        return None
    return (float(ev["x"]) - float(ev["cam_x"]),
            float(ev["y"]) - float(ev["cam_y"]))


def _on_tape(ev, margin=40):
    xy = _screen(ev)
    if xy is None:
        return False
    return (-margin < xy[0] < SRC_W + margin
            and -margin < xy[1] < SRC_H + margin)


def _host_kills():
    out = []
    for ev in _FOLEY["events"]:
        if ev.get("kind") != "kill":
            continue
        kt = GO_HOST + ev["t"] / HZ
        if kt < GO_HOST + 0.4 or kt > HOST_END - 0.15:
            continue
        if not _on_tape(ev):
            continue
        out.append((kt, ev))
    return out


def _clamp_win(tin, tout, lo, hi):
    tin = max(lo, tin)
    tout = min(hi, tout)
    if tout - tin < 1.2:
        return None
    return _r(tin), _r(tout)


def _no_overlap(rows):
    seen = []
    for e in rows:
        if e["kind"] != "seg":
            continue
        for prev in seen:
            if prev["src"] != e["src"]:
                continue
            if e["tin"] < prev["tout"] and prev["tin"] < e["tout"]:
                raise SystemExit(
                    "reused %s tape: %s [%.2f-%.2f] overlaps %s [%.2f-%.2f]"
                    % (e["src"], prev["label"], prev["tin"], prev["tout"],
                       e["label"], e["tin"], e["tout"]))
        seen.append(e)


def _build_edl():
    kills = _host_kills()
    if not kills:
        raise SystemExit("no on-screen kills in retake foley")
    hook_t, hook_ev = kills[0]
    for kt, ev in kills:
        if ev.get("killer") == 0:
            hook_t, hook_ev = kt, ev
            break

    hook = _clamp_win(hook_t - 1.7, hook_t + 1.05, GO_HOST + 0.2, HOST_END)
    if hook is None:
        raise SystemExit("hook window empty")

    host_lo, host_hi = 0.05, HOST_END
    client_lo, client_hi = 0.05, CLIENT_END
    panel = _clamp_win(_MK["host_clicked"]["sec"] - 0.35,
                       _MK["host_clicked"]["sec"] + 1.85, host_lo, host_hi)
    code = _clamp_win(_MK["code_ready"]["sec"] - 0.7,
                      _MK["code_ready"]["sec"] + 1.4, host_lo, host_hi)
    join = _clamp_win(_MK["client_addr_focus"]["sec"] - 0.15,
                      min(_MK["client_connected"]["sec"] + 1.35,
                          GO_CLIENT - 0.4),
                      client_lo, client_hi)
    go = _clamp_win(_MK["start_clicked"]["sec"] - 0.25,
                    min(GO_HOST + 0.85, hook[0] - 0.15),
                    host_lo, host_hi)
    if None in (panel, code, join, go):
        raise SystemExit("a lobby window collapsed")

    edl = [
        dict(kind="seg", src="host", tin=hook[0], tout=hook[1],
             punch="fight", kill_t=hook_t, kill=hook_ev,
             bug="KRAPNET IS LIVE", cap="MULTIPLAYER", label="HOOK"),
        dict(kind="divider", dur=0.7, lines=["KRAPNET IS LIVE"],
             tag="SELF-HOSTED", label="DIVIDER"),
        dict(kind="seg", src="host", tin=panel[0], tout=panel[1],
             punch="panel", cap="HOST A MATCH", label="HOST"),
        dict(kind="seg", src="host", tin=code[0], tout=code[1],
             punch="code", cap="SHARE THE CODE", label="CODE"),
        dict(kind="seg", src="client", tin=join[0], tout=join[1],
             punch="join", cap="FRIENDS PASTE IT", label="JOIN"),
        dict(kind="seg", src="host", tin=go[0], tout=go[1],
             punch="go", cap="START THE FIGHT", label="GO"),
    ]

    used_host = hook[1]
    n_fight = 0
    for kt, ev in kills:
        if n_fight >= 4:
            break
        if kt < used_host + 1.6:
            continue
        if ev.get("killer") != 0 and ev.get("victim") != 0 and n_fight > 0:
            if ev.get("killer") not in (0, 2) and ev.get("victim") not in (0, 2):
                continue
        win = _clamp_win(kt - 1.55, kt + 0.85, used_host + 0.2, HOST_END)
        if win is None:
            continue
        n_fight += 1
        row = dict(kind="seg", src="host", tin=win[0], tout=win[1],
                   punch="fight", kill_t=kt, kill=ev,
                   label="FIGHT-%02d" % n_fight)
        if n_fight == 1:
            row["bug"] = "FIRST TO 15"
        if n_fight == 2:
            row["cap"] = "SQUAD UP"
        if n_fight == 4:
            row["cap"] = "YOUR ARENA"
        edl.append(row)
        used_host = win[1]

    if n_fight < 2:
        raise SystemExit("not enough fight windows after the hook")

    edl.append(dict(kind="stamps", dur=1.6,
                    lines=["TEAM DEATHMATCH", "FREE-FOR-ALL",
                           "NO ACCOUNTS. NO SERVER."],
                    tag="UP TO 8 PLAYERS", label="STAMPS"))
    edl.append(dict(kind="end", dur=3.4, label="CTA"))
    for e in edl:
        if e["kind"] == "seg":
            e["dur"] = _r(e["tout"] - e["tin"])
            if e["dur"] <= 0:
                raise SystemExit("empty window " + e["label"])
    _no_overlap(edl)
    return edl


def _timeline(rows):
    t, out = 0.0, []
    for r in rows:
        r["tc"] = round(t, 3)
        r["end"] = round(t + r["dur"], 3)
        t += r["dur"]
        out.append(r)
    return out, round(t, 3)


EDL = _build_edl()
TIMELINE, TOTAL = _timeline([dict(r) for r in EDL])


def row(label):
    for r in TIMELINE:
        if r["label"] == label:
            return r
    raise KeyError(label)


def dt_escape(text: str) -> str:
    return (text.replace("\\", r"\\").replace(":", r"\:")
            .replace("'", r"\'").replace(",", r"\,"))


def _font_path() -> str:
    return ((FONT_DIR / "IBMPlexMono-SemiBold.ttf").as_posix()
            .replace(":", "\\:"))


def bug_chain(r) -> str:
    if not r.get("bug"):
        return ""
    return (f",drawtext=fontfile='{_font_path()}'"
            f":text='{dt_escape(r['bug'])}':fontcolor={ACCENT}"
            f":fontsize=36:box=1:boxcolor=0x0A0506@0.78:boxborderw=14"
            f":x=(w-text_w)/2:y={SAFE_TOP}")


def cap_chain(r) -> str:
    if not r.get("cap"):
        return ""
    return (f",drawtext=fontfile='{_font_path()}'"
            f":text='{dt_escape(r['cap'])}':fontcolor=0xFFE2B8"
            f":fontsize=32:box=1:boxcolor=0x06090D@0.84:boxborderw=12"
            f":x=(w-text_w)/2:y=h-{SAFE_BOT}")


def _events_in(tin, tout):
    out = []
    for ev in _FOLEY["events"]:
        cap_t = GO_HOST + ev["t"] / HZ
        if tin <= cap_t <= tout and ev.get("x") is not None:
            xy = _screen(ev)
            if xy is not None:
                out.append((cap_t, xy[0], xy[1], ev))
    return out


def _fight_crop(r):
    """Full-frame gameplay: no side crop, nothing goes offscreen.

    The previous 504x700 track-crop followed the killer across a 1000px
    tape, which cut the top score bar ("...RST TO 15", "YOU ..."), the
    bottom weapon/HP plate, nametags ("MICUL FU...") and edge players in
    half. On a 1080-wide phone that reads as broken. Returning the full
    1000x700 frame keeps the whole HUD and all four players visible.
    Scaled to 1080 wide it is 1080x756 centred, with captions sitting in
    the blur above/below instead of on top of the action.
    """
    return f"crop={SRC_W}:{SRC_H}:0:0"


def _ui_crop(kind: str) -> str:
    # Full-frame everywhere. The old 640-wide punch-in made the MATCH
    # LOBBY card big, but it sliced the game HUD behind the modal
    # ("...ST TO 15", "YO...") and cut the wide ARENA MATCH panel's edge
    # labels ("MODE"->"ODE", seat 8, BACK/ESC hints). A smaller but
    # complete plate reads better on a phone than a big sliced one.
    return f"crop={SRC_W}:{SRC_H}:0:0"


def _seg_filter(idx, r) -> str:
    punch = r.get("punch", "fight")
    # Every beat stays full-frame so the score bar, weapon plate, nametags,
    # edge players and panel edge labels are never sliced.
    is_gameplay = punch in ("fight", "go")
    grade = (",eq=gamma=1.28:contrast=1.08:saturation=1.10" if is_gameplay
             else "")
    crop = _fight_crop(r) if is_gameplay else _ui_crop(punch)
    # Backdrop is a cover-blur of the same frame. It must stay LIFTED on
    # every beat: the foundry tape averages ~luma 24, and the old
    # brightness=-0.14 under gameplay subtracted ~36/255 and crushed the
    # blur to pure black, so fight beats read as floating gameplay over a
    # black void while lobby beats had a textured grey-green backdrop.
    bg_eq = ("brightness=0.06:gamma=1.20:saturation=1.45" if is_gameplay
             else "brightness=0.10:gamma=1.25:saturation=1.55")
    # The foreground is ALWAYS fitted to the frame WIDTH, then centred. Fitting
    # to height instead would make it wider than 1080 and ffmpeg would silently
    # chop both sides off the plate.
    return (
        f"[{idx}:v]fps={FPS},"
        f"trim=start={g(r['tin'])}:end={g(r['tout'])},"
        f"setpts=PTS-STARTPTS,{crop},setsar=1,split=2[bg{idx}][fg{idx}];"
        f"[bg{idx}]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:"
        f"flags=lanczos,crop={OUT_W}:{OUT_H},"
        f"scale=270:480:flags=area,boxblur=14:3,gblur=sigma=2.4,"
        f"scale={OUT_W}:{OUT_H}:flags=lanczos,"
        f"eq={bg_eq}[bb{idx}];"
        f"[fg{idx}]scale={OUT_W}:-2:flags=lanczos[ff{idx}];"
        f"[bb{idx}][ff{idx}]overlay=x=(W-w)/2:y=(H-h)/2,"
        f"trim=duration={g(r['dur'])},setpts=PTS-STARTPTS,setsar=1"
        f"{grade}{bug_chain(r)}{cap_chain(r)}[v{idx}]"
    )


def render_cards(work: Path) -> dict:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tools"))
    import pygame
    import render_trailer as rt

    pygame.init()
    # Cards are composed on a private 1080x1920 surface. Keep the game
    # display at native size so render_trailer helpers stay valid.
    pygame.display.set_mode((rt.W, rt.H))
    title_f = pygame.font.Font(str(FONT_DIR / "Oswald.ttf"), 92)
    mid_f = pygame.font.Font(str(FONT_DIR / "Oswald.ttf"), 40)
    tag_f = pygame.font.Font(str(FONT_DIR / "IBMPlexMono-SemiBold.ttf"), 28)
    cap_f = pygame.font.Font(str(FONT_DIR / "IBMPlexMono-Regular.ttf"), 22)
    clips = {}

    def feed_frame(surf):
        raw = pygame.image.tobytes(surf, "RGB")
        rt.PROC[0].stdin.write(raw)

    def draw_stack(surf, lines, tag=None):
        surf.fill((4, 5, 6))
        pygame.draw.rect(surf, (255, 120, 0),
                         (OUT_W // 2 - 90, 520, 180, 4))
        y = 580
        for li, ln in enumerate(lines):
            f = title_f if li == 0 else mid_f
            col = (238, 228, 196) if li == 0 else (158, 178, 158)
            t = f.render(ln, True, col)
            sh = f.render(ln, True, (0, 0, 0))
            cx = OUT_W // 2 - t.get_width() // 2
            surf.blit(sh, (cx + 3, y + 3))
            surf.blit(t, (cx, y))
            y += t.get_height() + (28 if li == 0 else 10)
        if tag:
            t = tag_f.render(tag, True, (255, 120, 0))
            surf.blit(t, (OUT_W // 2 - t.get_width() // 2, y + 36))

    def draw_end(surf, i, total, fade_frames):
        surf.fill((4, 5, 6))
        pygame.draw.rect(surf, (255, 120, 0),
                         (OUT_W // 2 - 90, 360, 180, 4))
        y = 420
        title = title_f.render("CALL OF ACARISTAN", True, (232, 222, 190))
        surf.blit(title, (OUT_W // 2 - title.get_width() // 2, y))
        y += title.get_height() + 16
        tagline = tag_f.render("MULTIPLAYER IS HERE", True, (255, 120, 0))
        surf.blit(tagline, (OUT_W // 2 - tagline.get_width() // 2, y))
        y += tagline.get_height() + 28
        y = rt._draw_retardovici_mark(surf, OUT_W // 2, y, scale=0.85)
        y += 18
        studio = mid_f.render("RETARDOVICI INC.", True, (232, 238, 235))
        surf.blit(studio, (OUT_W // 2 - studio.get_width() // 2, y))
        y += studio.get_height() + 16
        sub = cap_f.render("HOST A MATCH  ·  SHARE THE CODE  ·  FIRST TO 15",
                           True, (150, 170, 150))
        surf.blit(sub, (OUT_W // 2 - sub.get_width() // 2, y))
        if fade_frames > 0 and i >= total - fade_frames:
            a = int(255 * (i - (total - fade_frames) + 1) / max(1, fade_frames))
            fade = pygame.Surface((OUT_W, OUT_H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, max(0, min(255, a))))
            surf.blit(fade, (0, 0))

    for r in TIMELINE:
        if r["kind"] == "seg":
            continue
        out = work / ("card_" + r["label"] + ".mp4")
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
             "-s", f"{OUT_W}x{OUT_H}", "-pix_fmt", "rgb24", "-r", str(FPS),
             "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        rt.PROC[0] = proc
        n = int(round(r["dur"] * FPS))
        fade = int(1.1 * FPS) if r["kind"] == "end" else int(0.18 * FPS)
        surf = pygame.Surface((OUT_W, OUT_H))
        for i in range(n):
            if r["kind"] == "end":
                draw_end(surf, i, n, fade)
            else:
                draw_stack(surf, list(r.get("lines") or []), r.get("tag"))
                if fade and (i < fade or i >= n - fade):
                    a = (i + 1) / fade if i < fade else (n - i) / fade
                    black = pygame.Surface((OUT_W, OUT_H))
                    black.fill((0, 0, 0))
                    black.set_alpha(int(255 * (1.0 - max(0.0, min(1.0, a)))))
                    surf.blit(black, (0, 0))
            feed_frame(surf)
        proc.stdin.close()
        proc.wait()
        if not out.exists() or out.stat().st_size == 0:
            raise SystemExit("card render produced nothing: " + r["label"])
        clips[r["label"]] = out
        print(f"  card {r['label']:<16} {r['dur']:>4.1f}s -> {out.name}")
    return clips


def build_silent_master(work: Path, cards: dict) -> Path:
    inputs, parts = [], []
    for i, r in enumerate(TIMELINE):
        if r["kind"] == "seg":
            inputs.append(CAP / f"{r['src']}_flow.mp4")
            parts.append(_seg_filter(i, r))
        else:
            inputs.append(cards[r["label"]])
            parts.append(
                f"[{i}:v]fps={FPS},setsar=1,"
                f"trim=duration={g(r['dur'])},setpts=PTS-STARTPTS[v{i}]")
    n = len(TIMELINE)
    chain = ";".join(parts)
    chain += ";" + "".join(f"[v{i}]" for i in range(n)) + \
             f"concat=n={n}:v=1:a=0,format=yuv420p[v]"
    out = work / "silent_master.mp4"
    args = [FFMPEG, "-y"]
    for p in inputs:
        args += ["-i", p]
    args += ["-filter_complex_script", graph_file(work, "concat", chain),
             "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "17",
             "-preset", "medium", "-movflags", "+faststart", str(out)]
    run(args, "picture: punch-crop concat 1080x1920")
    print(f"  picture {TOTAL:.1f}s planned -> {dur_of(out):.1f}s rendered")
    return out


def render_foley_stem(work: Path) -> Path:
    sys.path.insert(0, str(ROOT / "tools"))
    import numpy as np
    import build_sfx_stem as FS

    n = int((TOTAL + 2.0) * SR)
    bus = np.zeros((n, 2), dtype=np.float32)
    clip_group = np.zeros(n, dtype=np.float32)
    cache: dict = {}

    def asset(name):
        if name not in cache:
            if name in FS.DERIVED:
                src, build = FS.DERIVED[name]
                cache[name] = build(asset(src))
            else:
                cache[name] = FS.resample_2x(FS.read_wav_mono(SFX_DIR / name))
        return cache[name]

    def place(name, t, gain_db, pan=0.0):
        FS.place(bus, asset(name), t, gain_db, pan)

    def place_clip(name, t, gain_db, offset=0.0):
        FS.place_mono(clip_group, asset(name), t, gain_db, offset)

    WPN_GAIN = {"pistol": 0.0, "os12": 1.5, "k9": 0.5}
    counts: dict = {}
    mapped = 0
    for r in TIMELINE:
        if r["kind"] != "seg":
            continue
        is_host = r["src"] == "host"
        w_in = r["tin"] + (0.0 if is_host else GO_OFF)
        w_out = r["tout"] + (0.0 if is_host else GO_OFF)
        for ev in _FOLEY["events"]:
            cap_t = GO_HOST + ev["t"] / HZ
            if not (w_in <= cap_t <= w_out):
                continue
            prog = r["tc"] + (cap_t - w_in)
            kind = ev["kind"]
            counts[kind] = counts.get(kind, 0) + 1
            mapped += 1
            if kind == "player_shot":
                if is_host:
                    wg = WPN_GAIN.get(ev.get("weapon", "pistol"), 0.0)
                    for nm, gdb, off, pan, stage in FS.STACKS["unsuppressed"]:
                        if stage == "clip":
                            place_clip(nm, prog, gdb + FS.UNSUPPRESSED_GAIN + wg,
                                       off)
                        else:
                            place(nm, prog, gdb + FS.UNSUPPRESSED_GAIN + wg, pan)
                else:
                    place("gunshot.wav", prog, FS.ENEMY_SHOT_GAIN - 2.0, 0.12)
            elif kind == "enemy_shot":
                cam_cx = (ev.get("cam_x") or 0.0) + SRC_W / 2
                cam_cy = (ev.get("cam_y") or 0.0) + SRC_H / 2
                dx = (ev["x"] or 0.0) - cam_cx
                dy = (ev["y"] or 0.0) - cam_cy
                dist = math.hypot(dx, dy)
                if dist > 900:
                    continue
                pan = max(-0.92, min(0.92, dx / 520.0))
                damp = 0.0 if is_host else -2.0
                if dist > 640:
                    place("gunshot_distant.wav", prog,
                          FS.ENEMY_SHOT_GAIN - 3.0 + damp, pan)
                else:
                    fall = -3.0 * max(0.0, (dist - 260.0) / 320.0)
                    place("gunshot.wav", prog,
                          FS.ENEMY_SHOT_GAIN + fall + damp, pan)
            elif kind == "kill":
                damp = 0.0 if is_host else -3.0
                place("bullet_snap.wav", prog, -2.0 + damp, 0.0)
                if ev.get("victim") == 0:
                    place("melee_hit.wav", prog, -4.0 + damp, 0.0)
            elif kind == "hit":
                if ev.get("victim") == 0:
                    place("bullet_impact_enemy.wav", prog, -6.0, 0.2)
            elif kind == "pickup":
                place("pickup.wav", prog, -8.0, 0.0)
            elif kind == "dryfire":
                place("empty_click.wav", prog, -6.0, 0.0)

    bus += FS.soft_clip(clip_group, 1.45)[:, None]
    for ch in range(2):
        bus[:, ch] = FS.dc_block(bus[:, ch])
    FS.normalize_tp(bus, FS.TRUE_PEAK_DBTP)
    out = work / "diegetic_foley.wav"
    FS.write_wav24(out, bus)
    print(f"  diegetic {mapped} events mapped {counts} -> {dur_of(out):.1f}s")
    return out


ST = f"aresample={SR},aformat=channel_layouts=stereo"
LIM = "alimiter=limit=0.95:level=disabled"
PAN = {"c": None,
       "l": "pan=stereo|c0=0.92*c0|c1=0.08*c1",
       "r": "pan=stereo|c0=0.08*c0|c1=0.92*c1"}


def build_one_shots(work: Path) -> dict:
    sd = work / "sfx"
    sd.mkdir(exist_ok=True)
    one: dict = {}

    def emit(name, inputs, chain):
        out = sd / f"{name}.wav"
        args = [FFMPEG, "-y"]
        for p in inputs:
            args += ["-i", p]
        args += ["-filter_complex_script",
                 graph_file(work, f"os_{name}", chain), "-map", "[o]",
                 "-c:a", "pcm_s16le", "-ar", str(SR), str(out)]
        run(args, f"oneshot {name}")
        one[name] = out
        return out

    def sfx(name):
        return SFX_DIR / f"{name}.wav"

    emit("braam", [sfx("rig_low_boom"), sfx("explosion")],
         f"[0:a]volume=1.0,{ST}[a];"
         f"[1:a]lowpass=f=90,volume=0.5,{ST}[b];"
         f"aevalsrc='0.55*sin(2*PI*36.7*t)*exp(-1.6*t)':d=1.8:s={SR}"
         f":c=mono,{ST}[s];"
         f"[a][b][s]amix=inputs=3:normalize=0,{LIM},apad=pad_dur=0.3[o]")
    emit("stamp", [sfx("gunshot")],
         f"[0:a]highpass=f=120,lowpass=f=7000,volume=0.90,atrim=0:0.34,{ST}[o]")
    n_click, rdur = 8, 2.4
    parts = [f"[0:a]asplit={n_click}" + "".join(f"[c{i}]" for i in range(n_click))]
    for i in range(n_click):
        parts.append(
            f"[c{i}]atrim=0:0.03,asetpts=PTS-STARTPTS,"
            f"volume={g(0.10 + 0.55 * i / (n_click - 1))},"
            f"adelay={g(i * (rdur / n_click) * 1000)}:all=1,"
            f"aformat=channel_layouts=stereo[k{i}]")
    parts.append("".join(f"[k{i}]" for i in range(n_click)) +
                 f"amix=inputs={n_click}:normalize=0[clicks]")
    parts.append(
        f"aevalsrc='0.30*min(1,t/{g(rdur)})*"
        f"sin(2*PI*(180*t+880*t*t))':d={g(rdur)}:s={SR}:c=mono,{ST}[chirp]")
    parts.append(f"[chirp][clicks]amix=inputs=2:normalize=0,"
                 f"highpass=f=120,{LIM}[o]")
    emit("riser", [sfx("empty_click")], ";".join(parts))
    emit("sting", [sfx("rig_low_boom"), sfx("alarm")],
         f"[0:a]volume=0.90,{ST}[a];"
         f"[1:a]volume=0.45,adelay=120:all=1,{ST}[b];"
         f"aevalsrc='0.62*sin(2*PI*(40*t-2.2*t*t))*exp(-0.7*t)':d=3.0"
         f":s={SR}:c=mono,{ST}[dp];"
         f"[dp][a][b]amix=inputs=3:normalize=0,{LIM},apad=pad_dur=1.6[o]")
    emit("chord", [sfx("mission_complete")],
         f"[0:a]lowpass=f=5200,volume=0.55,{ST}[o]")
    return one


def design_events() -> list:
    go_row = row("GO")
    go_prog = go_row["tc"] + (GO_HOST - go_row["tin"])
    ev = [
        (0.05, "braam", -2.5, "c"),
        (row("JOIN")["tc"], "braam", -4.0, "c"),
        (max(go_row["tc"], go_prog - 2.2), "riser", -5.0, "c"),
        (min(go_prog, go_row["end"] - 0.05), "braam", -1.5, "c"),
        (row("STAMPS")["tc"] + 0.25, "stamp", -6.0, "l"),
        (row("STAMPS")["tc"] + 0.75, "stamp", -6.0, "c"),
        (row("STAMPS")["tc"] + 1.2, "stamp", -6.0, "r"),
        (row("CTA")["tc"] + 0.15, "sting", -2.0, "c"),
        (row("CTA")["tc"] + 0.9, "chord", -11.0, "c"),
    ]
    last_fight = [r for r in TIMELINE if r["label"].startswith("FIGHT-")]
    if last_fight:
        ev.append((last_fight[-1]["tc"] + 0.1, "braam", -3.0, "c"))
    return ev


def place(work: Path, one: dict, events, total: float, stem: str) -> Path:
    out = work / f"{stem}.wav"
    if not events:
        run([FFMPEG, "-y", "-f", "lavfi", "-i",
             f"anullsrc=r={SR}:cl=stereo:d={g(total)}",
             "-c:a", "pcm_s16le", "-ar", str(SR), str(out)], f"{stem}: empty")
        return out
    from collections import Counter
    counts = Counter(e[1] for e in events)
    used = sorted(counts)
    slot = {name: i for i, name in enumerate(used)}
    args = [FFMPEG, "-y"]
    for name in used:
        args += ["-i", one[name]]
    pool: dict = {}
    parts = []
    for name in used:
        i = slot[name]
        k = counts[name]
        pads = [f"{name}_{j}" for j in range(k)]
        pool[name] = pads
        parts.append(f"[{i}:a]aformat=channel_layouts=stereo"
                     + (f",asplit={k}" + "".join(f"[{p}]" for p in pads)
                        if k > 1 else f"[{pads[0]}]"))
    for j, (tc, name, gain, pan) in enumerate(events):
        chain = f"[{pool[name].pop(0)}]volume={g(gain)}dB"
        if PAN.get(pan):
            chain += "," + PAN[pan]
        chain += f",adelay={int(round(tc * 1000))}:all=1[p{j}]"
        parts.append(chain)
    parts.append("".join(f"[p{j}]" for j in range(len(events))) +
                 f"amix=inputs={len(events)}:normalize=0:dropout_transition=0,"
                 f"{LIM},apad,atrim=0:{g(total)}[o]")
    args += ["-filter_complex_script", graph_file(work, f"place_{stem}",
                                                  ";".join(parts)),
             "-map", "[o]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out)]
    run(args, f"{stem}: place {len(events)} events over {total:.1f}s")
    return out


def build_bed(work: Path, total: float) -> Path:
    if not MUSIC.exists():
        raise SystemExit(f"soundtrack missing: {MUSIC}")
    intro_d = TIMELINE[0]["dur"]
    body_d = round(total - intro_d, 3)
    fade_st = max(0.4, round(body_d - 3.2, 3))
    intro, body = work / "bed_intro.wav", work / "bed_body.wav"
    run([FFMPEG, "-y", "-i", MUSIC,
         "-af", f"atrim=0:{g(intro_d)},asetpts=PTS-STARTPTS,"
                f"highpass=f=45,lowpass=f=900,"
                f"afade=t=in:st=0:d=0.15,afade=t=out:st={g(intro_d - 0.2)}:d=0.2",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(intro)],
        "bed: hook")
    run([FFMPEG, "-y", "-i", MUSIC,
         "-af", f"atrim={g(intro_d)}:{g(total)},asetpts=PTS-STARTPTS,"
                f"lowpass=f=9000,afade=t=in:st=0:d=0.4,volume=0.64,"
                f"afade=t=out:st={g(fade_st)}:d=3.2",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(body)],
        "bed: body")
    out = work / "bed.wav"
    run([FFMPEG, "-y", "-i", intro, "-i", body,
         "-filter_complex_script",
         graph_file(work, "bed", "[0:a][1:a]concat=n=2:v=0:a=1[o]"),
         "-map", "[o]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out)],
        "bed: concat")
    return out


BUS_GLUE = "acompressor=threshold=-16dB:ratio=4:attack=12:release=220:knee=8"
SAMPLE_CEIL_DB = -3.5
TP_LIN = 10 ** (SAMPLE_CEIL_DB / 20)
TP_FLOOR = -2.3


def premix(work: Path, bed: Path, dieg: Path, sfx: Path) -> Path:
    chain = (
        f"[0:a]volume=0.9,{LIM}[b];"
        f"[1:a]volume={g(DIEGETIC_GAIN)}dB,{LIM},"
        f"apad,atrim=0:{g(TOTAL)}[d];"
        f"[2:a]{LIM}[s];"
        "[b][d]amix=inputs=2:normalize=0[bd];"
        "[bd][s]amix=inputs=2:normalize=0[pre]")
    out = work / "premix.wav"
    run([FFMPEG, "-y", "-i", bed, "-i", dieg, "-i", sfx,
         "-filter_complex_script", graph_file(work, "premix", chain),
         "-map", "[pre]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out)],
        f"audio: premix (bed + diegetic {DIEGETIC_GAIN:g}dB + design)")
    return out


def measure(path: Path) -> dict:
    r = run([FFMPEG, "-hide_banner", "-nostats", "-i", path,
             "-af", "loudnorm=I=-14:TP=-2:LRA=11:print_format=json",
             "-f", "null", "-"], f"audio: measure {path.name}")
    err = r.stderr
    lo, hi = err.rfind("{"), err.rfind("}")
    if lo < 0 or hi <= lo:
        raise SystemExit("loudnorm returned no JSON - cannot normalise")
    return json.loads(err[lo:hi + 1])


def normalise(work: Path, pre: Path) -> Path:
    def render(src: Path, af: str, name: str) -> Path:
        out = work / name
        run([FFMPEG, "-y", "-i", src, "-af", af,
             "-c:a", "pcm_s16le", "-ar", str(SR), str(out)], f"audio: {name}")
        return out

    glued = render(pre, BUS_GLUE, "glued.wav")
    m1 = measure(glued)
    want = -14.0
    gain = want - float(m1["input_i"])
    lim = (f"alimiter=limit={g(TP_LIN)}:attack=5:release=90"
           f":level=disabled")
    ceil = render(glued, f"volume={g(gain)}dB,{lim}", "ceil.wav")
    m2 = measure(ceil)
    gain2 = want - float(m2["input_i"])
    tp2 = float(m2["input_tp"])
    if gain2 > 0 and tp2 + gain2 > TP_FLOOR:
        gain2 = TP_FLOOR - tp2
    print(f"  loudnorm glue {m1['input_i']} -> {m2['input_i']} "
          f"(TP {m2['input_tp']}), makeup {gain2:+.2f} dB")
    final_a = render(ceil, f"volume={g(gain2)}dB", "audio_final.wav")
    m3 = measure(final_a)
    print(f"  delivered loudness I={m3['input_i']} TP={m3['input_tp']} "
          f"LRA={m3['input_lra']}")
    return final_a


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-stems", action="store_true")
    args = ap.parse_args()

    for need in (CAP / "host_flow.mp4", CAP / "client_flow.mp4"):
        if not need.exists():
            raise SystemExit(f"missing capture: {need}")

    work = Path(tempfile.mkdtemp(prefix="mp_tiktok_"))
    print(f"work dir: {work}")
    print(f"source:   {CAP}")
    print(f"programme: {TOTAL:.1f}s over {len(TIMELINE)} rows  (9:16)")
    for r in TIMELINE:
        src = r.get("src", "card")
        tin = f" [{r['tin']:.2f}-{r['tout']:.2f}]" if r["kind"] == "seg" else ""
        punch = f" {r.get('punch','')}" if r.get("punch") else ""
        print(f"  {r['tc']:6.2f}-{r['end']:6.2f}  {r['kind']:<8} {src:<7}"
              f"{tin}{punch}  {r['label']}")

    cards = render_cards(work)
    silent = build_silent_master(work, cards)
    one = build_one_shots(work)
    bed = build_bed(work, TOTAL)
    dieg = render_foley_stem(work)
    sfx = place(work, one, design_events(), TOTAL, "sfx")
    pre = premix(work, bed, dieg, sfx)
    audio = normalise(work, pre)

    run([FFMPEG, "-y", "-i", silent, "-i", audio,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(OUT_FINAL)],
        f"mux -> {OUT_FINAL.name}")

    info = run([FFPROBE, "-v", "error", "-show_entries",
                "stream=codec_type,width,height,codec_name:"
                "format=duration,size",
                "-of", "json", OUT_FINAL], "probe final")
    meta = json.loads(info.stdout)
    v = next((s for s in meta["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in meta["streams"] if s["codec_type"] == "audio"), {})
    d = float(meta["format"]["duration"])
    mb = int(meta["format"]["size"]) / 1e6
    print("-" * 64)
    print(f"FINAL  {OUT_FINAL}")
    print(f"  {v.get('width')}x{v.get('height')} {v.get('codec_name')}  "
          f"{a.get('codec_name')}  {d:.2f}s  {mb:.1f} MB")
    if v.get("width") != OUT_W or v.get("height") != OUT_H:
        raise SystemExit("output is not 1080x1920")
    if not a:
        raise SystemExit("output has no audio")
    if not args.keep_stems:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
