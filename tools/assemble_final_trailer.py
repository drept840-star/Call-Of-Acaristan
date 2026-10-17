"""assemble_final_trailer.py - Post-production assembler for CALL OF ACARISTAN.

Takes the three clean combat acts captured by Terminal 8
(``trailers/fresh_action/act{1,2,3}.mp4``), splices the game's own title /
divider / stamp / end cards between them, and mixes a trailer audio bed
against the in-repo SFX + radio bank.

Design notes
------------
* Title cards are NOT re-implemented. They are rendered headless through the
  game's existing card renderer (``tools/render_trailer_v2.card`` for the
  PLAN_2 title/divider/stamp finish, ``tools/render_trailer.end_card`` for the
  AI-4 CTA lockup), so the cards match the in-game look (Oswald / IBM Plex
  Mono, 255,120,0 accent, vignette, fade finish) instead of being an ffmpeg
  re-creation that drifts.
* The picture is assembled with ffmpeg's ``concat`` *filter* (not the demuxer)
  so a timebase mismatch in the acts cannot silently desync A/V. Every row is
  normalised to 1000x700 @ 30 fps CFR yuv420p and trimmed to its EDL duration
  before the join.
* Final grade follows ``docs/PLAN_3_AUDIO.md`` §5: 1000x700 blur-padded into
  1920x1080 over a darkened blurred background, audio loudnorm'd to
  -14 LUFS / -2 dBTP.
* Audio arrangement follows ``docs/PLAN_3_AUDIO.md`` §1 (arrangement),
  §2.2 (radio filters), §3 (hit stacks) and §4 (beat-sync map), retimed onto
  this assembly's EDL. 100 BPM grid = 0.6 s; every cut lands on the grid.
* **Gunshots are foley-driven, never hand-placed.** The acts are silent -
  ``tools/record_fresh_action.py`` captures with ``SDL_AUDIODRIVER=dummy`` and
  ``set_master_volume(0)``, so it logs every live shot to an
  ``act<N>.foley.json`` sidecar instead of an audio track. Guessing shot times
  here (the old ``4.2 + i*1.4`` loops) put reports on empty picture and left
  real muzzle flashes dry. ``tools/build_sfx_stem.py`` re-renders the real
  ``sfx_wav/`` stacks at the logged ticks; this script calls it with this EDL's
  act offsets and mixes the result as the diegetic stem.

Usage
-----
    python assemble_final_trailer.py
    python assemble_final_trailer.py --probe          # print the EDL only
    python assemble_final_trailer.py --keep-stems     # keep intermediate wavs

Output
------
    trailer_final_master.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACTS_DIR = ROOT / "trailers" / "fresh_action"
SFX_DIR = ROOT / "sfx_wav"
FONT_DIR = ROOT / "assets" / "fonts"
MUSIC = ROOT / "menu_theme.mp3"
OUT = ROOT / "trailers" / "trailer_final_master.mp4"

W, H, FPS = 1000, 700, 30          # native capture size / rate
SR = 44100                          # delivery sample rate
BEAT = 0.6                          # 100 BPM grid (PLAN_3 §1)
ACCENT = "0xFF7800"                 # game orange, matches bug_tag()
SILENCE = (35.4, 35.8)              # 12-frame M-SILENCE (PLAN_2 §1 S17)

# Diegetic (foley) stem level relative to the design sfx. The stem is
# true-peak normalised to -2.5 dBTP by build_sfx_stem, which measures
# momentary loudness p99 = -13.4 LUFS against the music bed's -28.7 LUFS, so
# -6 dB lands gun transients ~10 LU over the bed (audible over the score)
# while the stem's gated average (-18 LUFS -> -24) stays under the music.
DIEGETIC_GAIN = -6.0                # dB, gunshots/foley vs the music bed


PAN = {
    "c": None,
    "l": "pan=stereo|c0=0.92*c0|c1=0.08*c1",
    "r": "pan=stereo|c0=0.08*c0|c1=0.92*c1",
}


# ──────────────────────────────────────────────────────────────────────
# EDL - the assembled cut
# ──────────────────────────────────────────────────────────────────────
EDL = [
    dict(kind="title", dur=1.8, lines=["CALL OF ACARISTAN"],
         tag="OFFICIAL TRAILER", label="TITLE"),
    dict(kind="act", dur=10.0, src="act1.mp4", label="ACT I - BLACK NOTEBOOK"),
    dict(kind="card", dur=1.8, lines=["TACTICAL ESPIONAGE"],
         tag=None, label="DIVIDER 1"),
    dict(kind="act", dur=10.0, src="act2.mp4",
         label="ACT II - QUIET ON ROUTE 12"),
    dict(kind="card", dur=1.8, lines=["DEEP BEHIND ENEMY LINES"],
         tag=None, label="DIVIDER 2"),
    dict(kind="act", dur=10.0, src="act3.mp4", label="ACT III - THE VOSTRAL"),
    dict(kind="stamps", dur=3.0,
         lines=["M1 // BLACK NOTEBOOK", "M2 // QUIET ON ROUTE 12",
                "M3 // THE VOSTRAL"],
         tag="Every rumor has a record.", label="STAMPS"),
    dict(kind="end", dur=6.0, label="CTA"),
]


def _timeline(rows):
    t, out = 0.0, []
    for r in rows:
        r["tc"] = round(t, 3)
        r["end"] = round(t + r["dur"], 3)
        t += r["dur"]
        out.append(r)
    return out, round(t, 3)


TIMELINE, TOTAL = _timeline([dict(r) for r in EDL])
ACT_TCS = [r["tc"] for r in TIMELINE if r["kind"] == "act"]


# ──────────────────────────────────────────────────────────────────────
# ffmpeg plumbing
# ──────────────────────────────────────────────────────────────────────
def ffmpeg_bin() -> str:
    for cand in (shutil.which("ffmpeg"), r"C:\ffmpeg\bin\ffmpeg.exe",
                 os.environ.get("FFMPEG", "")):
        if cand and (Path(cand).exists() or shutil.which(cand)):
            return cand
    raise SystemExit("ffmpeg not found (PATH, C:\\ffmpeg\\bin, or $FFMPEG)")


FFMPEG = ffmpeg_bin()
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def run(args, label):
    t0 = time.time()
    r = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, errors="replace")
    if r.returncode != 0:
        sys.stderr.write(f"\n[FAIL] {label}\n"
                         f"$ {' '.join(str(a) for a in args)}\n")
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


def graph_file(work: Path, name: str, text: str) -> str:
    p = work / f"{name}.ffgraph"
    p.write_text(text, encoding="utf-8")
    return str(p)


def g(x) -> str:
    """Compact float for a filter argument."""
    return f"{x:g}"


def graph_file_input(path: Path) -> str:
    return path.as_posix().replace(":", r"\:")


# ──────────────────────────────────────────────────────────────────────
# 1. PICTURE - cards via the game's own renderer
# ──────────────────────────────────────────────────────────────────────
def render_card_clips(work: Path) -> dict:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    sys.path.insert(0, str(ROOT / "tools"))

    import pygame                                  # noqa: E402
    import render_trailer as rt                    # noqa: E402
    import render_trailer_v2 as v2                 # noqa: E402

    pygame.display.set_mode((rt.W, rt.H))
    clips = {}
    for row in TIMELINE:
        if row["kind"] == "act":
            clips[row["label"]] = ACTS_DIR / row["src"]
            continue
        out = work / ("card_" + "".join(
            ch for ch in row["label"] if ch.isalnum()) + ".mp4")
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
             "-s", f"{rt.W}x{rt.H}", "-pix_fmt", "rgb24", "-r", str(rt.FPS),
             "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(rt.FPS), str(out)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        rt.PROC[0] = proc
        rt.FRAME[0] = 0
        if row["kind"] == "end":
            rt.end_card(row["dur"], fade_out_seconds=1.0)
        else:
            v2.card(list(row["lines"]), row["dur"], tag=row.get("tag"))
        proc.stdin.close()
        proc.wait()
        if not out.exists() or out.stat().st_size == 0:
            raise SystemExit(f"card render produced nothing: {row['label']}")
        clips[row["label"]] = out
        print(f"  card {row['label']:<26} {row['dur']:>4.1f}s -> {out.name}")
    return clips


def act_bug(row) -> str:
    """Orange act label, styled after render_trailer_v2.bug_tag()."""
    if row["kind"] != "act":
        return "null"
    font = graph_file_input(FONT_DIR / "IBMPlexMono-SemiBold.ttf")
    txt = (row["label"].replace("\\", r"\\").replace(":", r"\:")
           .replace("'", r"\'"))
    return (f"drawtext=fontfile='{font}':text='{txt}':fontcolor={ACCENT}"
            f":fontsize=22:box=1:boxcolor=0x0A0506@0.75:boxborderw=12"
            f":x=(w-text_w)/2:y=14")


def build_silent_master(work: Path, clips: dict) -> Path:
    n = len(TIMELINE)
    args = [FFMPEG, "-y"]
    for row in TIMELINE:
        args += ["-i", clips[row["label"]]]

    parts = []
    for i, row in enumerate(TIMELINE):
        parts.append(
            f"[{i}:v]fps={FPS},"
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"trim=duration={g(row['dur'])},setpts=PTS-STARTPTS,"
            f"{act_bug(row)}[v{i}]")
    chain = ";".join(parts)
    chain += ";" + "".join(f"[v{i}]" for i in range(n)) + \
             f"concat=n={n}:v=1:a=0[cat]"
    chain += (";[cat]split[bgA][fgA];"
              "[bgA]scale=1920:1080:flags=lanczos,boxblur=18:4,"
              "eq=brightness=-0.3:contrast=0.92[bg];"
              "[fgA]scale=-2:1080:flags=lanczos[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")

    out = work / "silent_master.mp4"
    args += ["-filter_complex_script", graph_file(work, "concat", chain),
             "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "17",
             "-preset", "medium", "-movflags", "+faststart", str(out)]
    run(args, "picture: concat + 1080p grade")
    print(f"  picture {TOTAL:.1f}s planned -> {dur_of(out):.1f}s rendered")
    return out


# ──────────────────────────────────────────────────────────────────────
# 2. AUDIO - one-shots, then placement, then the stem mix
# ──────────────────────────────────────────────────────────────────────
ST = f"aresample={SR},aformat=channel_layouts=stereo"
LIM = "alimiter=limit=0.95:level=disabled"


def build_one_shots(work: Path) -> dict:
    """Pre-render every reusable hit to its own wav (PLAN_3 §3 stacks).

    One file per hit keeps the placement pass a trivial adelay+amix and makes
    each stack independently probe-able. No input is referenced twice inside a
    single graph, so no asplit bookkeeping is needed here.
    """
    sd = work / "sfx"
    sd.mkdir(exist_ok=True)
    one: dict[str, Path] = {}

    def emit(name, inputs, chain, dur=None):
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

    # --- squelch head, cut from radio_static (PLAN_3 §2.2) ---------------
    sq = work / "squelch_head.wav"
    run([FFMPEG, "-y", "-i", sfx("radio_static"),
         "-af", f"highpass=f=480,lowpass=f=2350,volume=0.5,atrim=0:0.05,{ST}",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(sq)],
        "oneshot squelch_head")

    # --- BRAAM: rig_low_boom + explosion lp80 + 36.7 Hz sine, exp decay ---
    emit("braam", [sfx("rig_low_boom"), sfx("explosion")],
         f"[0:a]volume=1.0,{ST}[a];"
         f"[1:a]lowpass=f=90,volume=0.5,{ST}[b];"
         f"aevalsrc='0.55*sin(2*PI*36.7*t)*exp(-1.6*t)':d=1.8:s={SR}"
         f":c=mono,{ST}[s];"
         f"[a][b][s]amix=inputs=3:normalize=0,{LIM},apad=pad_dur=0.3[o]")

    # --- suppressed / unsuppressed / sniper stacks ------------------------
    # NOT built here. Those are the diegetic gunshots and they must land on
    # the ticks the capture actually fired on, so they come from the foley
    # sidecars via build_foley_stem() below, not from a guessed loop.

    # --- stamp gun-cock: dry, tight, for the 3x L-C-R hits --------------
    emit("stamp", [sfx("gunshot")],
         f"[0:a]highpass=f=120,lowpass=f=7000,volume=0.90,atrim=0:0.34,"
         f"{ST}[o]")

    # --- RISER: 180 Hz -> ~5.8 kHz chirp + accelerating empty_click ----
    n_click, rdur = 10, 3.2
    parts = [f"[0:a]asplit={n_click}"
             + "".join(f"[c{i}]" for i in range(n_click))]
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

    # --- CTA sting: down-pitch 40 -> 26 Hz braam + low boom + alarm -----
    emit("sting", [sfx("rig_low_boom"), sfx("alarm")],
         f"[0:a]volume=0.90,{ST}[a];"
         f"[1:a]volume=0.45,adelay=120:all=1,{ST}[b];"
         f"aevalsrc='0.62*sin(2*PI*(40*t-2.2*t*t))*exp(-0.7*t)':d=3.0"
         f":s={SR}:c=mono,{ST}[dp];"
         f"[dp][a][b]amix=inputs=3:normalize=0,{LIM},apad=pad_dur=1.6[o]")

    # --- CTA chord: mission_complete under the lockup -------------------
    emit("chord", [sfx("mission_complete")],
         f"[0:a]lowpass=f=5200,volume=0.55,{ST}[o]")

    # --- VO VASILE: VHF van treatment (PLAN_3 §2.2) + squelch head ------
    emit("vo_vasile", [sq, sfx("radio_chatter")],
         f"[0:a]volume=1.0,{ST}[sq];"
         f"[1:a]highpass=f=400,lowpass=f=2800,"
         f"acompressor=threshold=-18dB:ratio=4:attack=5:release=120,"
         f"aecho=0.6:0.6:20:0.3,volume=0.85,{ST}[b];"
         # squelch head PREPENDS to the line (not mixed under it).
         f"[sq][b]concat=n=2:v=0:a=1,apad=whole_dur=2.4[o]")

    # --- VO BALACEANU: diegetic PA horn, large hall ---------------------
    emit("vo_pa", [sfx("pa_mumble")],
         f"[0:a]highpass=f=600,lowpass=f=3200,"
         f"acompressor=threshold=-20dB:ratio=6:attack=10:release=300,"
         f"aecho=0.8:0.8:45|35:0.6|0.55,volume=1.10,{ST}[o]")

    # --- cold-open ambience: 55 Hz drone lowpassed to 300 Hz ------------
    emit("amb_drone", [sfx("ambient_drone")],
         f"[0:a]lowpass=f=300,highpass=f=40,volume=0.55,{ST}[o]")

    return one


def risers() -> list[tuple[float, float]]:
    """(tc, duration) of each riser - the last 3.2 s before a drop."""
    return [(round(tc - 3.2, 3), 3.2) for tc in ACT_TCS[1:]]


def sfx_events() -> list[tuple[float, str, float, str]]:
    """(tc, oneshot, gain_dB, pan) on the programme timeline.

    Design/beat hits only. Every diegetic gunshot comes from the act foley
    logs (see build_foley_stem), so nothing in here may stand in for one.
    """
    ev: list[tuple[float, str, float, str]] = []
    add = ev.append

    # Cold open: drone under the title, no drums (PLAN_3 §1 Intro).
    add((0.0, "amb_drone", -12.0, "c"))

    # BRAAM on every act cut (PLAN_3 §3).
    for tc in ACT_TCS:
        add((tc, "braam", -4.0, "c"))

    # 3x dry gun-cocks L-C-R over the stamps card (PLAN_2 §4 M-STAMPS).
    # Over a card, not over picture: the real gunfire lives in the diegetic
    # stem and stops with Act III at 35.4 s.
    for tc, pan in ((36.0, "l"), (36.7, "c"), (37.4, "r")):
        add((tc, "stamp", -6.0, pan))

    # CTA: down-pitch braam + low-boom tail, then the chord under the lockup.
    add((38.4, "sting", -2.0, "c"))
    add((39.2, "chord", -11.0, "c"))
    return ev


def vo_events() -> list[tuple[float, str, float, str]]:
    return [
        (0.3, "vo_vasile", -3.0, "c"),     # over the cold open
        (20.4, "vo_pa", -4.0, "c"),        # act II, before the act-III riser
    ]


# ──────────────────────────────────────────────────────────────────────
# 2b. DIEGETIC STEM - gunfire on the ticks the capture fired on
# ──────────────────────────────────────────────────────────────────────
def act_rows() -> list:
    return [r for r in TIMELINE if r["kind"] == "act"]


def foley_logs() -> list[Path]:
    """The sidecar each act's clip-maker wrote next to its MP4."""
    out = []
    for row in act_rows():
        out.append(ACTS_DIR / (Path(row["src"]).stem + ".foley.json"))
    return out


def act_offsets() -> tuple[list[int], list[float]]:
    """(act numbers, programme timecodes) read off THIS assembly's EDL.

    Offsets must come from the EDL, not a 0/10/20 assumption: the title and
    divider cards shift every act, and a stem built on the wrong offsets puts
    every gunshot one card-length early - the same desync this fixes.
    """
    acts, offs = [], []
    for row in act_rows():
        stem = Path(row["src"]).stem              # "act2" -> 2
        acts.append(int(stem.replace("act", "")))
        offs.append(float(row["tc"]))
    return acts, offs


def build_foley_stem(work: Path) -> Path:
    """Re-render the real sfx_wav stacks at the logged shot ticks.

    Delegates to tools/build_sfx_stem.py (numpy: per-event suppressed /
    unsuppressed / sniper stacks, soft clip, sniper reverb, DC block, true-peak
    ceiling) because those rules are already owned there; this only supplies
    the offsets so the stem lands on this cut.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import build_sfx_stem as foley                       # noqa: E402

    missing = [p for p in foley_logs() if not p.exists()]
    if missing:
        raise SystemExit(
            "missing foley sidecar(s): " + ", ".join(str(m) for m in missing)
            + "\nrun: python tools/record_fresh_action.py  "
              "(the act clips are silent; these logs ARE the gunfire)")

    acts, offs = act_offsets()
    out = work / "diegetic_foley.wav"
    info = foley.render(acts=acts, offsets=offs, out=out,
                        manifest=work / "diegetic_foley.json",
                        ceiling=foley.TRUE_PEAK_DBTP)
    print(f"  diegetic {info['layers']} layers from "
          f"{len(acts)} foley logs at offsets "
          f"{', '.join(f'{o:g}' for o in offs)} -> {dur_of(out):.1f}s")
    return out



def place(work: Path, one: dict, events, total: float, stem: str) -> Path:
    """adelay+amix every event onto a silent canvas of exactly `total` seconds.

    Reused one-shots are fanned out with asplit - a stream specifier may only
    be consumed once per filtergraph.
    """
    out = work / f"{stem}.wav"
    if not events:
        run([FFMPEG, "-y", "-f", "lavfi", "-i",
             f"anullsrc=r={SR}:cl=stereo:d={g(total)}",
             "-c:a", "pcm_s16le", "-ar", str(SR), str(out)], f"{stem}: empty")
        return out

    used = sorted({e[1] for e in events})
    counts = Counter(e[1] for e in events)
    slot = {name: i for i, name in enumerate(used)}

    args = [FFMPEG, "-y"]
    for name in used:
        args += ["-i", one[name]]

    # Fan-out: allocate one split pad per (file, occurrence).
    pool: dict[str, list[str]] = {}
    parts = []
    for name in used:
        i = slot[name]
        k = counts[name]
        pads = [f"{name.replace('-', '_')}_{j}" for j in range(k)]
        pool[name] = pads
        parts.append(f"[{i}:a]aformat=channel_layouts=stereo"
                     + (f",asplit={k}" + "".join(f"[{p}]" for p in pads)
                        if k > 1 else f"[{pads[0]}]"))

    for j, (tc, name, gain, pan) in enumerate(events):
        chain = (f"[{pool[name].pop(0)}]volume={g(gain)}dB")
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
    """menu_theme split into a lowpassed cold open + full-band body, with the
    12-frame M-SILENCE hard-gated out of the body (PLAN_3 §1, PLAN_2 S17)."""
    if not MUSIC.exists():
        raise SystemExit(f"soundtrack missing: {MUSIC}")
    intro_d = TIMELINE[0]["dur"]
    body_d = round(total - intro_d, 3)
    sil0, sil1 = (round(SILENCE[0] - intro_d, 3),
                  round(SILENCE[1] - intro_d, 3))
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
                f"lowpass=f=9000,afade=t=in:st=0:d=0.6,"
                f"volume='if(between(t,{g(sil0)},{g(sil1)}),0,0.62)':eval=frame,"
                f"afade=t=out:st={g(fade_st)}:d=4.0",
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(body)],
        "bed: body")

    out = work / "bed.wav"
    run([FFMPEG, "-y", "-i", intro, "-i", body,
         "-filter_complex_script",
         graph_file(work, "bed", "[0:a][1:a]concat=n=2:v=0:a=1[o]"),
         "-map", "[o]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out)],
        "bed: concat")
    print(f"  bed    {dur_of(out):.1f}s  cold open lp420Hz -> body lp9000Hz, "
          f"silence {SILENCE[0]}-{SILENCE[1]}s")
    return out


def build_stems(work: Path, one: dict, total: float):
    bed = build_bed(work, total)
    sfx_ev = sfx_events() + [(tc, "riser", -5.0, "c") for tc, _ in risers()]
    sfx = place(work, one, sfx_ev, total, "sfx")
    vo = place(work, one, vo_events(), total, "vo")
    dieg = build_foley_stem(work)
    return bed, sfx, vo, dieg


# ──────────────────────────────────────────────────────────────────────
# 3. FINAL MUX
# ──────────────────────────────────────────────────────────────────────
def premix(work: Path, bed: Path, sfx: Path, vo: Path, dieg: Path,
           total: float) -> Path:
    """Duck + mix the four stems, then gate the M-SILENCE across all of them.

    PLAN_3 §5 requires the 12-frame silence "baked into all three stems", so
    the gate sits on the mixed bus, not just the bed. The 10 ms ramps either
    side keep the hard gate from clicking.

    Bus order is music -> diegetic -> design hits -> VO: the diegetic stem
    rides with the ducked bed so the PA line still reads over the gunfire,
    while the beat-synced hits (braam/riser/sting) stay on top of everything
    but the VO.
    """
    s0, s1 = SILENCE
    ramp = 0.020
    # Ramps live OUTSIDE [s0, s1] so the 12 gated frames are pure digital
    # silence (PLAN_3 §1) and the transitions themselves cannot click.
    gate = (f"if(lt(t,{g(s0 - ramp)}),1,"
            f"if(lt(t,{g(s0)}),1-(t-{g(s0 - ramp)})/{g(ramp)},"
            f"if(lt(t,{g(s1)}),0,"
            f"if(lt(t,{g(s1 + ramp)}),(t-{g(s1)})/{g(ramp)},1))))")
    chain = (
        # Bed + diegetic duck under VO (PLAN_3 §2.3); VO rides on top.
        # The VO pad is consumed twice (sidechain key + mix), so it is split.
        "[0:a]volume=0.9,alimiter=limit=0.95:level=disabled[bed];"
        "[1:a]volume=1.0,alimiter=limit=0.95:level=disabled[sfx];"
        "[2:a]volume=1.0,asplit=2[vokey][vomix];"
        # The foley stem ends at the last act's tail (act_end + 12 s), so it
        # is padded to the programme length before the mix; atrim stops apad.
        f"[3:a]volume={g(DIEGETIC_GAIN)}dB,"
        "alimiter=limit=0.95:level=disabled,"
        f"apad,atrim=0:{g(total)}[dieg];"
        "[bed][vokey]sidechaincompress=threshold=0.02:ratio=8:attack=5"
        ":release=200[ducked];"
        "[ducked][dieg]amix=inputs=2:normalize=0[back];"
        "[back][sfx]amix=inputs=2:normalize=0[pre];"
        "[pre][vomix]amix=inputs=2:normalize=0,"
        f"volume='{gate}':eval=frame,"
        f"apad,atrim=0:{g(total)}[o]")
    out = work / "premix.wav"
    run([FFMPEG, "-y", "-i", bed, "-i", sfx, "-i", vo, "-i", dieg,
         "-filter_complex_script", graph_file(work, "premix", chain),
         "-map", "[o]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out)],
        f"audio: premix (VO duck + {s0}-{s1}s silence gate)")
    return out



def measure(path: Path) -> dict:
    """Loudness analysis pass (PLAN_3 §5 targets: I=-14, TP=-2, LRA=11)."""
    r = run([FFMPEG, "-hide_banner", "-nostats", "-i", path,
             "-af", "loudnorm=I=-14:TP=-2:LRA=11:print_format=json",
             "-f", "null", "-"], f"audio: measure {path.name}")
    err = r.stderr
    lo, hi = err.rfind("{"), err.rfind("}")
    if lo < 0 or hi <= lo:
        raise SystemExit("loudnorm returned no JSON - cannot normalise")
    return json.loads(err[lo:hi + 1])


# Bus glue. The raw premix measures PLR ~13.4 dB, which makes -14 LUFS with a
# -2 dBTP ceiling arithmetically unreachable: hitting -14 would need PLR <= 12.
# A gentle 4:1 above -16 dBFS brings the crest down so the ceiling and the
# integrated target can both be satisfied. Verified after the diegetic foley
# stem landed (gunfire transients raise the crest): premix I=-23.8/TP=-1.5 ->
# glue -24.3/-7.9 -> normalise -14.9/-2.4 (AAC), LRA 10.9. Heavier glue
# (-20/6 and up) recovered ~0.2 LU but cost 1-2 LU of LRA, i.e. exactly the
# gun-transient dynamics this mix is for.
BUS_GLUE = "acompressor=threshold=-16dB:ratio=4:attack=12:release=220:knee=8"
TARGET_I = -14.0
TP_CEIL = -2.0            # plan ceiling, on the DELIVERED (encoded) file
# alimiter clamps SAMPLE peak; on this material the true peak sits ~1.0 dB
# above the sample ceiling and AAC adds up to ~0.4 dB on top, so the sample
# ceiling must be well below -2 for the encoded file to measure under -2.
# -3.5 dBFS measures -2.5 dBTP pre-encode / -2.45 dBTP delivered.
SAMPLE_CEIL_DB = -3.5
TP_LIN = 10 ** (SAMPLE_CEIL_DB / 20)
TP_FLOOR = -2.3           # pre-encode true-peak cap on makeup gain (AAC margin)


def normalise(work: Path, pre: Path, total: float) -> Path:
    """Measured normalisation, iterated to land on -14 LUFS.

    A single loudnorm pass only *aims*: with a source crest this high it falls
    1-2 LU short and its linear mode is silently disabled (target LRA below
    source LRA, target TP below source TP). So: bus glue -> measure -> static
    gain + brickwall ceiling -> re-measure -> residual makeup gain, clamped so
    the true peak keeps encode headroom.
    """
    def render(src: Path, af: str, name: str) -> Path:
        out = work / name
        run([FFMPEG, "-y", "-i", src, "-af", af, "-ar", str(SR), "-ac", "2",
             "-c:a", "pcm_s16le", str(out)], f"audio: {name}")
        return out

    cur = render(pre, BUS_GLUE, "glue.wav")
    for step in range(3):
        st = measure(cur)
        gain = TARGET_I - float(st["input_i"])
        if step == 0:
            af = (f"volume={g(gain)}dB,"
                  f"alimiter=limit={g(TP_LIN)}:level=disabled:attack=3:release=60")
        else:
            head = TP_FLOOR - float(st["input_tp"])
            if gain > head:
                gain = head
            if abs(gain) < 0.05:
                break
            af = f"volume={g(gain)}dB"
        print(f"  pass {step}: I={st['input_i']} TP={st['input_tp']} "
              f"LRA={st['input_lra']} -> gain {g(gain)} dB")
        cur = render(cur, af, f"norm{step}.wav")
    return render(cur, f"alimiter=limit={g(TP_LIN)}:level=disabled,"
                        f"afade=t=out:st={g(max(0.0, total - 1.2))}:d=1.2,"
                        f"apad,atrim=0:{g(total)}", "master_audio.wav")


def final_mux(work: Path, video: Path, audio: Path, out: Path) -> None:
    run([FFMPEG, "-y", "-i", video, "-i", audio,
         "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
         "-movflags", "+faststart", str(out)], "final mux")


def loudness_report(out: Path) -> dict:
    r = run([FFMPEG, "-hide_banner", "-nostats", "-i", out,
             "-af", "loudnorm=I=-14:TP=-2:LRA=11:print_format=json",
             "-f", "null", "-"], "loudness")
    err = r.stderr
    lo = err.rfind("{")
    hi = err.rfind("}")
    try:
        return json.loads(err[lo:hi + 1]) if lo >= 0 and hi > lo else {}
    except Exception:
        return {}


def probe(path: Path) -> dict:
    r = run([FFPROBE, "-v", "error", "-show_entries",
             "stream=codec_name,codec_type,width,height,r_frame_rate,"
             "sample_rate,channels:format=duration,size",
             "-of", "json", path], "probe")
    return json.loads(r.stdout)


# ──────────────────────────────────────────────────────────────────────
def print_edl() -> None:
    print(f"Programme {TOTAL:.1f}s  |  100 BPM grid = {BEAT}s  |  "
          f"native {W}x{H}@{FPS} -> 1920x1080")
    print(f"{'TC':>7} {'END':>7} {'DUR':>5}  SEGMENT")
    for row in TIMELINE:
        print(f"{row['tc']:>7.2f} {row['end']:>7.2f} {row['dur']:>5.1f}  "
              f"{row['label']}")
    print("\nrisers (into every drop after the first):")
    for tc, d in risers():
        print(f"  {tc:>6.2f}s  {d:.1f}s sweep -> drop {tc + d:.2f}s")
    print(f"\nM-SILENCE {SILENCE[0]}-{SILENCE[1]}s "
          f"({int(round((SILENCE[1] - SILENCE[0]) * FPS))} frames) "
          f"- bed gated to 0, no sfx")


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble the final trailer.")
    ap.add_argument("--probe", action="store_true",
                    help="print the EDL and exit without rendering")
    ap.add_argument("--keep-stems", action="store_true",
                    help="keep the intermediate wav stems")
    args = ap.parse_args()

    if args.probe:
        print_edl()
        return 0

    missing = [ACTS_DIR / r["src"] for r in TIMELINE
               if r["kind"] == "act" and not (ACTS_DIR / r["src"]).exists()]
    if missing:
        raise SystemExit("missing combat act(s): " +
                         ", ".join(str(m) for m in missing))
    # The acts are silent by construction; their foley sidecars are the only
    # source of the gunfire, so fail before any rendering, not during it.
    missing_fo = [p for p in foley_logs() if not p.exists()]
    if missing_fo:
        raise SystemExit("missing foley sidecar(s): " +
                         ", ".join(str(m) for m in missing_fo) +
                         "\nrun: python tools/record_fresh_action.py")

    print("=" * 68)
    print("CALL OF ACARISTAN - final trailer assembly")
    print("=" * 68)
    print_edl()
    acts, offs = act_offsets()
    print(f"\ndiegetic foley: acts {acts} at {offs} "
          f"-> {len(foley_logs())} sidecars, gain {DIEGETIC_GAIN:+g} dB")

    work = Path(tempfile.mkdtemp(prefix="coa_final_"))
    t0 = time.time()
    try:
        print("\n[1/4] cards via the in-engine renderer")
        clips = render_card_clips(work)
        silent = build_silent_master(work, clips)

        print("\n[2/4] audio one-shots")
        one = build_one_shots(work)
        print(f"  {len(one)} one-shots rendered")

        print("\n[3/4] stems (bed / design sfx / vo / foley)")
        bed, sfx, vo, dieg = build_stems(work, one, TOTAL)

        print("\n[4/4] audio mix -> final mux")
        pre = premix(work, bed, sfx, vo, dieg, TOTAL)

        master_a = normalise(work, pre, TOTAL)
        final_mux(work, silent, master_a, OUT)
    finally:
        if args.keep_stems:
            print(f"\nstems kept in {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)

    info = probe(OUT)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), {})
    loud = loudness_report(OUT)
    print("\n" + "=" * 68)
    print(f"  video    {v.get('codec_name')} {v.get('width')}x{v.get('height')}"
          f" @ {v.get('r_frame_rate')} fps")
    print(f"  audio    {a.get('codec_name')} {a.get('sample_rate')} Hz"
          f" {a.get('channels')}ch")
    print(f"  length   {float(info['format']['duration']):.2f}s"
          f"   {int(info['format']['size']) // 1024} KB")
    if loud:
        print(f"  loudness I={loud.get('input_i')} LUFS  "
              f"TP={loud.get('input_tp')} dBTP  LRA={loud.get('input_lra')}")
    print(f"  elapsed  {time.time() - t0:.1f}s")
    print("=" * 68)
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

