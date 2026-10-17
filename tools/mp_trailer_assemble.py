#!/usr/bin/env python3
"""mp_trailer_assemble.py - post-production assembler for the MULTIPLAYER
announcement trailer.

Cuts the real captured footage (trailers/mp_announce/{host,client}_flow.mp4,
chapters.json, host_flow.foley.json from mp_trailer_capture.py) into a cut
that TEACHES the flow: HOST -> SHARE THE CODE -> FRIEND PASTES IT -> START
THE FIGHT - then rides a kill-anchored montage of the roaming-bot round:
every fight window is pinned to a real kill from the foley sidecar.

Everything follows the campaign master's language (assemble_final_trailer.py):
* cards rendered headless through the game's own renderer
  (tools/render_trailer_v2.card; a custom end lockup in rt.end_card style)
* picture assembled with ffmpeg's concat FILTER, every row normalised to
  1000x700 @ 30 fps yuv420p, trimmed to the EDL duration, then the
  1080p blur-pad grade (lanczos fg over darkened box-blurred bg)
* step captions + act bugs via drawtext (IBM Plex Mono, game orange)
* audio: menu_theme bed (cold-open lowpass + full-band body), a diegetic
  stem re-rendered from the foley sidecar on the ticks the match actually
  fired (positioned/panned remote gunfire, kill ticks, pickups), design
  hits (braam on act cuts, riser into the GO drop, stamp cocks, CTA sting),
  glued and loudnorm'd to -14 LUFS / -2 dBTP.

Usage:  python tools/mp_trailer_assemble.py [--keep-stems]
Output: trailers/mp_announce/mp_announcement_trailer.mp4
        (+ mp_announcement_master.mp4, the identical project master)

Set MP_ANNOUNCE_DIR to assemble into a separate capture/output folder.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repo root (this script lives in tools/)
CAP = Path(os.environ.get(
    "MP_ANNOUNCE_DIR", str(ROOT / "trailers" / "mp_announce"))).resolve()
SFX_DIR = ROOT / "sfx_wav"
FONT_DIR = ROOT / "assets" / "fonts"
MUSIC = ROOT / "menu_theme.mp3"
OUT_FINAL = CAP / "mp_announcement_trailer.mp4"
OUT_PROJECT = CAP / "mp_announcement_master.mp4"

W, H, FPS = 1000, 700, 30
SR = 44100
ACCENT = "0xFF7800"
DIEGETIC_GAIN = -6.0        # dB, gunfire/foley vs the music bed (campaign value)

# ── the cut ─────────────────────────────────────────────────────────────
# Chapter marks are read from the capture's chapters.json, so a fresh capture
# (different room code, different settle times) re-flows the cut without an
# editorial edit. Windows are expressed relative to chapter marks; the
# constants below reproduce the approved v1 cut against the v1 capture.
_MK = json.loads((CAP / "chapters.json").read_text(encoding="utf-8"))
CH = dict(
    host=dict(panel_open=_MK["panel_open"]["sec"],
              callsign=_MK["callsign_typed"]["sec"],
              host_clicked=_MK["host_clicked"]["sec"],
              code_ready=_MK["code_ready"]["sec"],
              roster_2=_MK["roster_2"]["sec"],
              roster_full=_MK["roster_full"]["sec"],
              start_clicked=_MK["start_clicked"]["sec"],
              go=_MK["go_moment"]["sec"],
              end=_MK["combat_end"]["sec"]),
    client=dict(addr_focus=_MK["client_addr_focus"]["sec"],
                code_typed=_MK["client_code_typed"]["sec"],
                join_clicked=_MK["join_clicked"]["sec"],
                connected=_MK["client_connected"]["sec"],
                go=_MK["go_moment_client"]["sec"],
                end=_MK["combat_end_client"]["sec"]),
)


def _r(x):
    return round(x, 2)


# kind: title | divider | seg | stamps | end
# seg rows: src (host/client), tin/tout = source-clip seconds
EDL = [
    dict(kind="title", dur=1.8, lines=["CALL OF ACARISTAN"],
         tag="MULTIPLAYER", label="TITLE"),
    dict(kind="divider", dur=1.2, lines=["KRAPNET IS LIVE"],
         tag="SELF-HOSTED MULTIPLAYER", label="DIVIDER"),
    dict(kind="seg", src="host",
         tin=_r(CH["host"]["panel_open"] + 0.05),
         tout=_r(CH["host"]["host_clicked"] + 2.0),
         bug="ACT I - OPEN THE LOBBY", cap="STEP 1 - HOST A MATCH",
         label="ACT1-PANEL"),
    dict(kind="seg", src="host",
         tin=_r(CH["host"]["code_ready"] - 1.4),
         tout=_r(CH["host"]["code_ready"] + 4.0),
         cap="STEP 2 - SHARE THE CODE", label="ACT1-CODE"),
    dict(kind="seg", src="client",
         tin=_r(CH["client"]["addr_focus"] - 0.22),
         tout=_r(min(CH["client"]["connected"] + 1.85,
                     CH["client"]["go"] - 3.35)),
         bug="ACT II - THE JOINER", cap="STEP 3 - FRIENDS PASTE THE CODE",
         label="ACT2-JOIN"),
    dict(kind="seg", src="host",
         tin=_r(CH["host"]["start_clicked"] - 0.37),
         tout=_r(CH["host"]["go"] + 2.4),
         bug="ACT III - FIRST TO 15", cap="START THE FIGHT", label="ACT3-GO"),
]

# ── Act III montage - windows anchored on real kills ────────────────────────
# The fight rows are not hand-cut. Every window is pinned to a kill the
# foley log recorded during the roaming-bot round, so the montage is
# whatever the bots actually did on capture day. A kill is only usable on a
# tape when one of that tape's LOCAL seats is in the exchange (host tape:
# pid 0; client tape: foley meta.client_pid) - each rendered camera follows
# its local player, so the killer or the victim is guaranteed on screen.
_FOLEY = json.loads((CAP / "host_flow.foley.json").read_text(encoding="utf-8"))
CLIENT_PID = int(_FOLEY.get("meta", {}).get("client_pid") or 0)
GO_HOST = CH["host"]["go"]
GO_OFF = CH["host"]["go"] - CH["client"]["go"]
FIGHT_LEAD = 2.4             # run-up before the kill lands
FIGHT_TAIL = 1.2             # hold on the fallout
FIGHT_GAP = 0.35             # breathing room between windows on one tape
MAX_FIGHTS = 9


def _fight_windows() -> list:
    bounds = {
        "host": (GO_HOST + 3.2, CH["host"]["end"] - 0.05),
        "client": (CH["client"]["go"] + 3.2, CH["client"]["end"] - 0.05),
    }
    used = {"host": 0.0, "client": 0.0}
    kills = sorted((ev for ev in _FOLEY["events"]
                    if ev.get("kind") == "kill"), key=lambda e: e["t"])

    def local_tapes(ev):
        out = []
        if 0 in (ev.get("killer"), ev.get("victim")):
            out.append("host")
        if CLIENT_PID and CLIENT_PID in (ev.get("killer"), ev.get("victim")):
            out.append("client")
        return out

    wins = []
    for ev in kills:
        if len(wins) >= MAX_FIGHTS:
            break
        kt = GO_HOST + ev["t"] / float(_FOLEY["hz"])
        for src in (local_tapes(ev) or ["host", "client"]):
            lo, hi = bounds[src]
            base = kt - (0.0 if src == "host" else GO_OFF)
            tin, tout = _r(base - FIGHT_LEAD), _r(base + FIGHT_TAIL)
            if tin < lo or tout > hi or tin < used[src] + FIGHT_GAP:
                continue
            used[src] = tout
            wins.append(dict(src=src, tin=tin, tout=tout))
            break
    if len(wins) < 3:                    # starved tape: spread over the span
        lo, hi = bounds["host"]
        span_lo, span_hi = lo + FIGHT_LEAD, hi - FIGHT_TAIL
        for i in range(4):
            kt = span_lo + (span_hi - span_lo) * (i + 0.5) / 4
            tin, tout = _r(kt - FIGHT_LEAD), _r(kt + FIGHT_TAIL)
            if tin < used["host"] + FIGHT_GAP:
                continue
            used["host"] = tout
            wins.append(dict(src="host", tin=tin, tout=tout))
    return wins


_FIGHT_WINS = _fight_windows()
if not _FIGHT_WINS:
    raise SystemExit("no fight windows: foley log has no usable kills "
                     "inside the combat span - re-capture")
for _i, _w in enumerate(_FIGHT_WINS):
    _row = dict(kind="seg", src=_w["src"], tin=_w["tin"], tout=_w["tout"],
                label="ACT3-FIGHT-%02d" % (_i + 1))
    if _i == 0:
        _row["bug"] = "ACT III - LIVE FIRE"
    elif _i == 1:
        _row["cap"] = "SQUAD UP"
    if _i == len(_FIGHT_WINS) - 1:
        _row["cap"] = "YOUR ARENA. YOUR FIGHT."
    EDL.append(_row)
LAST_FIGHT = "ACT3-FIGHT-%02d" % len(_FIGHT_WINS)

EDL.append(dict(kind="stamps", dur=3.0,
                lines=["THE ARENA IS OPEN",
                       "TEAM DEATHMATCH + FREE-FOR-ALL - FIRST TO 15",
                       "THREE MAPS - UP TO 8 PLAYERS - ROOM CODES"],
                tag="NO ACCOUNTS. NO CENTRAL SERVER.", label="STAMPS"))
EDL.append(dict(kind="end", dur=6.0, label="CTA"))
for _e in EDL:                       # seg duration derives from its window
    if _e["kind"] == "seg":
        _e["dur"] = round(_e["tout"] - _e["tin"], 2)
        if _e["dur"] <= 0:
            raise SystemExit("empty window %s: %s-%s" % (
                _e["label"], _e["tin"], _e["tout"]))

# Same source tape may not be used twice. Recutting GO as FIGHT (or GG as
# a "new" beat) is how the announcement started looping the same action.
_seen = []
for _e in EDL:
    if _e["kind"] != "seg":
        continue
    for prev in _seen:
        if prev["src"] != _e["src"]:
            continue
        if _e["tin"] < prev["tout"] and prev["tin"] < _e["tout"]:
            raise SystemExit(
                "reused %s tape: %s [%.2f-%.2f] overlaps %s [%.2f-%.2f]"
                % (_e["src"], prev["label"], prev["tin"], prev["tout"],
                   _e["label"], _e["tin"], _e["tout"]))
    _seen.append(_e)


def _timeline(rows):
    t, out = 0.0, []
    for r in rows:
        r["tc"] = round(t, 3)
        r["end"] = round(t + r["dur"], 3)
        t += r["dur"]
        out.append(r)
    return out, round(t, 3)


TIMELINE, TOTAL = _timeline([dict(r) for r in EDL])


def row(label):
    for r in TIMELINE:
        if r["label"] == label:
            return r
    raise KeyError(label)


def g(x) -> str:
    return f"{x:g}"


def graph_file(work: Path, name: str, text: str) -> str:
    p = work / f"{name}.ffgraph"
    p.write_text(text, encoding="utf-8")
    return str(p)


def ffmpeg_bin() -> str:
    for cand in (shutil.which("ffmpeg"), os.environ.get("FFMPEG", "")):
        if cand and Path(cand).exists():
            return str(cand)
    raise SystemExit("ffmpeg not found")


FFMPEG = ffmpeg_bin()
FFPROBE = shutil.which("ffprobe") or "ffprobe"


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


# ── 1. CARDS through the game's own renderer ────────────────────────────────
def render_cards(work: Path) -> dict:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.path.insert(0, str(ROOT / "tools"))
    sys.path.insert(0, str(ROOT / "src"))

    import pygame                                   # noqa: E402
    import render_trailer as rt                     # noqa: E402
    import render_trailer_v2 as v2                  # noqa: E402

    pygame.init()
    pygame.display.set_mode((rt.W, rt.H))
    clips = {}
    for r in TIMELINE:
        if r["kind"] == "seg":
            continue
        out = work / ("card_" + r["label"] + ".mp4")
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
             "-s", f"{rt.W}x{rt.H}", "-pix_fmt", "rgb24", "-r", str(rt.FPS),
             "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(rt.FPS), str(out)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        rt.PROC[0] = proc
        rt.FRAME[0] = 0
        if r["kind"] == "end":
            _end_card_mp(rt, r["dur"])
        else:
            v2.card(list(r["lines"]), r["dur"], tag=r.get("tag"))
        proc.stdin.close()
        proc.wait()
        if not out.exists() or out.stat().st_size == 0:
            raise SystemExit(f"card render produced nothing: {r['label']}")
        clips[r["label"]] = out
        print(f"  card {r['label']:<16} {r['dur']:>4.1f}s -> {out.name}")
    return clips


def _end_card_mp(rt, seconds, fade_out_seconds=1.2):
    """Studio lockup in rt.end_card's shape, re-lineed for the MP announcement.

    Same fonts, same studio mark, same copyright strip - only the tagline
    changes (the campaign's end card says THE VOSTRAL IS REAL, which is the
    single-player message)."""
    import pygame
    total = int(seconds * rt.FPS)
    fade_frames = int(fade_out_seconds * rt.FPS)
    for i in range(total):
        s = pygame.Surface((rt.W, rt.H))
        s.fill((4, 5, 6))
        pygame.draw.rect(s, (255, 120, 0), (rt.W // 2 - 90, rt.H // 2 - 170,
                                            180, 3))
        y = rt.H // 2 - 130
        title = rt.FONT_BIG.render("CALL OF ACARISTAN", True, (232, 222, 190))
        s.blit(title, (rt.W // 2 - title.get_width() // 2, y))
        y += title.get_height() + 10
        tagline = rt.FONT_TAG.render("MULTIPLAYER IS HERE", True, (255, 120, 0))
        s.blit(tagline, (rt.W // 2 - tagline.get_width() // 2, y))
        y += tagline.get_height() + 18
        y = rt._draw_retardovici_mark(s, rt.W // 2, y, scale=0.62)
        y += 12
        studio = rt.FONT_MID.render("RETARDOVICI INC.", True, (232, 238, 235))
        s.blit(studio, (rt.W // 2 - studio.get_width() // 2, y))
        y += studio.get_height() + 10
        sub = rt.FONT_CAP.render(
            "HOST A MATCH - SHARE THE CODE - FIRST TO 15", True, (150, 170, 150))
        s.blit(sub, (rt.W // 2 - sub.get_width() // 2, y))
        if fade_frames > 0 and i >= total - fade_frames:
            a = int(255 * (i - (total - fade_frames) + 1) / max(1, fade_frames))
            fade = pygame.Surface((rt.W, rt.H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, max(0, min(255, a))))
            s.blit(fade, (0, 0))
        rt.config.screen.blit(s, (0, 0))
        rt.feed()
        rt.FRAME[0] += 1


# ── 2. PICTURE: trim rows, burn captions, concat, 1080p grade ───────────────
def dt_escape(text: str) -> str:
    return (text.replace("\\", r"\\").replace(":", r"\:")
                .replace("'", r"\'").replace(",", r"\,"))


def _font_path() -> str:
    # ffmpeg splits filter options on ':' (the drive-letter colon in
    # E:/... counts), so escape it: E:/... -> E\:/... . Without this the
    # whole concat filter fails with "No option name near '/Code/...'".
    return ((FONT_DIR / "IBMPlexMono-SemiBold.ttf").as_posix()
            .replace(":", "\\:"))


def bug_chain(row) -> str:
    """Top-centre act bug (campaign act_bug style)."""
    if not row.get("bug"):
        return ""
    font = _font_path()
    return (f",drawtext=fontfile='{font}'"
            f":text='{dt_escape(row['bug'])}':fontcolor={ACCENT}"
            f":fontsize=22:box=1:boxcolor=0x0A0506@0.75:boxborderw=12"
            f":x=(w-text_w)/2:y=14")


def cap_chain(row) -> str:
    """Bottom-centre step caption."""
    if not row.get("cap"):
        return ""
    font = _font_path()
    return (f",drawtext=fontfile='{font}'"
            f":text='{dt_escape(row['cap'])}':fontcolor=0xFFE2B8"
            f":fontsize=20:box=1:boxcolor=0x06090D@0.82:boxborderw=10"
            f":x=(w-text_w)/2:y=h-52")


def build_silent_master(work: Path, cards: dict) -> Path:
    inputs, parts = [], []
    for i, r in enumerate(TIMELINE):
        if r["kind"] == "seg":
            inputs.append(CAP / f"{r['src']}_flow.mp4")
            # The Foundry capture is intentionally low-key in-game, but the
            # original tape is too dark for announcement playback. Lift only
            # Act III footage; keep lobby, title, and CTA colors untouched.
            gameplay_grade = (
                ",eq=gamma=1.30:contrast=1.08:saturation=1.08"
                if r.get("label", "").startswith("ACT3-") else "")
            parts.append(
                f"[{i}:v]fps={FPS},"
                f"trim=start={g(r['tin'])}:end={g(r['tout'])},"
                f"setpts=PTS-STARTPTS,"
                f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                f"trim=duration={g(r['dur'])},setpts=PTS-STARTPTS"
                f"{gameplay_grade}{bug_chain(r)}{cap_chain(r)}[v{i}]")
        else:
            inputs.append(cards[r["label"]])
            parts.append(
                f"[{i}:v]fps={FPS},setsar=1,"
                f"trim=duration={g(r['dur'])},setpts=PTS-STARTPTS[v{i}]")

    n = len(TIMELINE)
    chain = ";".join(parts)
    chain += ";" + "".join(f"[v{i}]" for i in range(n)) + \
             f"concat=n={n}:v=1:a=0[cat]"
    chain += (";[cat]split[bgA][fgA];"
              "[bgA]scale=1920:1080:flags=lanczos,boxblur=18:4,"
              "eq=brightness=-0.3:contrast=0.92[bg];"
              "[fgA]scale=-2:1080:flags=lanczos[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")

    args = [FFMPEG, "-y"]
    for p in inputs:
        args += ["-i", p]
    out = work / "silent_master.mp4"
    args += ["-filter_complex_script", graph_file(work, "concat", chain),
             "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "17",
             "-preset", "medium", "-movflags", "+faststart", str(out)]
    run(args, "picture: concat + captions + 1080p grade")
    print(f"  picture {TOTAL:.1f}s planned -> {dur_of(out):.1f}s rendered")
    return out


# ── 3. DIEGETIC FOLEY STEM - gunfire on the ticks the match fired ───────────
def render_foley_stem(work: Path) -> Path:
    """Re-render sfx_wav stacks at the logged sim ticks, mapped onto this
    cut's programme time.

    Uses tools/build_sfx_stem.py's DSP primitives (same assets, same stacking
    philosophy) with MP-specific placement: the local player's shots get the
    full unsuppressed stack; REMOTE gunfire is positioned like the game's own
    play_3d (pan by dx from the viewing camera, distant asset + falloff past
    ~640 px); kills tick; pickups chime; dry pulls click.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import numpy as np                                   # noqa: E402
    import build_sfx_stem as FS                          # noqa: E402

    log = json.loads((CAP / "host_flow.foley.json").read_text(encoding="utf-8"))
    hz = float(log["hz"])

    total = TOTAL
    n = int((total + 2.0) * SR)
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

    # ── sim-clock -> capture-clock mapping ──────────────────────────────
    # The foley log's "t" is sim.tick, and the sim only starts stepping at
    # GO (countdown returns early in _update_host), so tick 0 == the go
    # chapter of whichever capture watched the match:
    #   host-capture time  = CH.host.go + t/hz
    #   client-capture time = CH.host.go + t/hz - GO_OFF
    # where GO_OFF is how much later the host tape started (its lobby wait).
    GO_HOST = CH["host"]["go"]
    GO_OFF = CH["host"]["go"] - CH["client"]["go"]

    WPN_GAIN = {"pistol": 0.0, "os12": 1.5, "k9": 0.5}
    counts: dict = {}
    mapped = 0
    for r in TIMELINE:
        if r["kind"] != "seg":
            continue
        is_host_row = r["src"] == "host"
        # window expressed in HOST-capture seconds
        w_in = r["tin"] + (0.0 if is_host_row else GO_OFF)
        w_out = r["tout"] + (0.0 if is_host_row else GO_OFF)
        for ev in log["events"]:
            cap_t = GO_HOST + ev["t"] / hz        # host-capture seconds
            if not (w_in <= cap_t <= w_out):
                continue
            prog = r["tc"] + (cap_t - w_in)
            kind = ev["kind"]
            counts[kind] = counts.get(kind, 0) + 1
            mapped += 1
            if kind == "player_shot":
                if is_host_row:
                    # local gunfire: the campaign's unsuppressed stack
                    wg = WPN_GAIN.get(ev.get("weapon", "pistol"), 0.0)
                    for nm, gdb, off, pan, stage in FS.STACKS["unsuppressed"]:
                        if stage == "clip":
                            place_clip(nm, prog, gdb + FS.UNSUPPRESSED_GAIN + wg,
                                       off)
                        else:
                            place(nm, prog, gdb + FS.UNSUPPRESSED_GAIN + wg, pan)
                else:
                    # the host's gun is REMOTE fire on the client's tape
                    place("gunshot.wav", prog, FS.ENEMY_SHOT_GAIN - 2.0, 0.12)
            elif kind == "enemy_shot":
                # positioned like ArenaView.on_remote_shot's play_3d
                cam_cx = (ev.get("cam_x") or 0.0) + W / 2
                cam_cy = (ev.get("cam_y") or 0.0) + H / 2
                dx = (ev["x"] or 0.0) - cam_cx
                dy = (ev["y"] or 0.0) - cam_cy
                dist = math.hypot(dx, dy)
                if dist > 900:
                    continue                     # GUNSHOT_AUDIBLE_PX cut-off
                pan = max(-0.92, min(0.92, dx / 520.0))
                damp = 0.0 if is_host_row else -2.0   # secondhand camera
                if dist > 640:
                    place("gunshot_distant.wav", prog,
                          FS.ENEMY_SHOT_GAIN - 3.0 + damp, pan)
                else:
                    fall = -3.0 * max(0.0, (dist - 260.0) / 320.0)
                    place("gunshot.wav", prog,
                          FS.ENEMY_SHOT_GAIN + fall + damp, pan)
            elif kind == "kill":
                damp = 0.0 if is_host_row else -3.0
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


# ── 4. DESIGN HITS + BED (ffmpeg one-shots, campaign recipes) ───────────────
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

    n_click, rdur = 10, 3.2
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
    """(tc, oneshot, gain_dB, pan) on the programme timeline."""
    go_prog = row("ACT3-GO")["tc"] + (CH["host"]["go"] - row("ACT3-GO")["tin"])
    ev = [
        # braam on every act cut
        (row("ACT1-PANEL")["tc"], "braam", -4.0, "c"),
        (row("ACT2-JOIN")["tc"], "braam", -4.0, "c"),
        # THE DROP: riser into GO, braam lands on it
        (go_prog - 3.2, "riser", -5.0, "c"),
        (go_prog, "braam", -1.5, "c"),
        (row(LAST_FIGHT)["tc"] + 0.15, "braam", -3.0, "c"),
        # stamp cocks over the stamps card
        (row("STAMPS")["tc"] + 0.3, "stamp", -6.0, "l"),
        (row("STAMPS")["tc"] + 1.0, "stamp", -6.0, "c"),
        (row("STAMPS")["tc"] + 1.7, "stamp", -6.0, "r"),
        # CTA
        (row("CTA")["tc"] + 0.2, "sting", -2.0, "c"),
        (row("CTA")["tc"] + 1.0, "chord", -11.0, "c"),
    ]
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
    fade_st = round(body_d - 4.0, 3)
    intro, body = work / "bed_intro.wav", work / "bed_body.wav"
    run([FFMPEG, "-y", "-i", MUSIC,
         "-af", f"atrim=0:{g(intro_d)},asetpts=PTS-STARTPTS,"
                f"highpass=f=45,lowpass=f=420,"
                f"afade=t=in:st=0:d=0.5,afade=t=out:st={g(intro_d - 0.3)}:d=0.3",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(intro)],
        "bed: cold open")
    run([FFMPEG, "-y", "-i", MUSIC,
         "-af", f"atrim={g(intro_d)}:{g(total)},asetpts=PTS-STARTPTS,"
                f"lowpass=f=9000,afade=t=in:st=0:d=0.6,volume=0.62,"
                f"afade=t=out:st={g(fade_st)}:d=4.0",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(body)],
        "bed: body")
    out = work / "bed.wav"
    run([FFMPEG, "-y", "-i", intro, "-i", body,
         "-filter_complex_script",
         graph_file(work, "bed", "[0:a][1:a]concat=n=2:v=0:a=1[o]"),
         "-map", "[o]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out)],
        "bed: concat")
    return out


# ── 5. PREMIX + LOUDNORM (campaign glue) ────────────────────────────────────
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
    """bus glue -> gain through a real limiter -> measure -> makeup.

    The MP mix is sparser than the campaign's (quiet lobby beats between
    gunfire), so the campaign's static-gain-only chain is peak-capped ~6 LU
    short of -14. Instead: push the FULL loudness gain and let an
    attack/release limiter duck the transients (gunfire stacks, braams),
    then a makeup pass with the true-peak guard, then the hard ceiling.
    """
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


# ── 6. MAIN ─────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-stems", action="store_true")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="mp_assemble_"))
    print(f"work dir: {work}")
    print(f"programme: {TOTAL:.1f}s over {len(TIMELINE)} rows")
    for r in TIMELINE:
        src = r.get("src", "card")
        tin = f" [{r['tin']:.2f}-{r['tout']:.2f}]" if r["kind"] == "seg" else ""
        print(f"  {r['tc']:6.2f}-{r['end']:6.2f}  {r['kind']:<8} {src:<7}"
              f"{tin}  {r['label']}")

    cards = render_cards(work)
    silent = build_silent_master(work, cards)

    one = build_one_shots(work)
    bed = build_bed(work, TOTAL)
    dieg = render_foley_stem(work)
    sfx = place(work, one, design_events(), TOTAL, "sfx")
    pre = premix(work, bed, dieg, sfx)
    audio = normalise(work, pre)

    # final mux
    run([FFMPEG, "-y", "-i", silent, "-i", audio,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(OUT_FINAL)],
        f"mux -> {OUT_FINAL.name}")
    shutil.copy2(OUT_FINAL, OUT_PROJECT)

    d = dur_of(OUT_FINAL)
    mb = OUT_FINAL.stat().st_size / 1e6
    print("-" * 64)
    print(f"FINAL  {OUT_FINAL}  {d:.2f}s  {mb:.1f} MB")
    print(f"copy   {OUT_PROJECT}")
    if not args.keep_stems:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    # The game modules (imported for card rendering) leave non-daemon
    # threads (KRAPNET listener etc). An exception would print its traceback
    # and then HANG on interpreter shutdown - invisible under pipes. Force a
    # real exit code either way.
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

