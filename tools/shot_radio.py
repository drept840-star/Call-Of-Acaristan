"""Polish pass Task 6 evidence: the radio transmission widget in every mission.

    python tools/shot_radio.py OUTDIR            # current build (after)
    ACA_POLISH_SRC=archive/before_T8/src python tools/shot_radio.py OUTDIR
                                                 # old pinned-text radio (before)

Writes OUTDIR/<scene>.png for M1 / M2 / M3 / M4 / M5 HQ (day) / M5 Quarter
(night, rain) / M5 tunnel with two transmissions on air (the previous one
fading in the history row, the current one half typed), plus letterbox.png
(M2 sniper-sequence anchor). The current build also writes variants.png:
small / large text, speaker names off, subtitles off with VO, long line
scrolled, critical pulse + queued pips. Prints the widget rect per scene so
overlaps with the HUD are easy to spot.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SRC = os.environ.get("ACA_POLISH_SRC", str(ROOT / "src"))
sys.path.insert(0, SRC)

import pygame  # noqa: E402
from core import config  # noqa: E402

SCENES = [
    ("m1", "start_mission",
     'VASILE: "Gate guard is looking the other way. Go now, stay off the lit side."',
     'KRAP COMMAND: "Bravo, depot patrol rotates in ninety seconds. Do not get seen."'),
    ("m2", "start_mission2_checkpoint",
     'GABI: "Second floor is clear. Stairwell next, watch the windows."',
     'VASILE: "Keep moving. The upload terminal is in the back office, past the archive shelves."'),
    ("m3", "start_mission3_breakout_checkpoint",
     'PA SYSTEM: "Cell block C, lockdown in effect. All staff to stations."',
     'MARU: "I have the doors on a loop for two minutes. Do not waste them, Biribel."'),
    ("m4", "start_mission4",
     'IPA DISPATCH: "All units, a stolen service van heading north on route twelve."',
     'VASILE: "That is us. Ditch the van at the station and go in on foot."'),
    ("m5_hq", "start_mission5_hq_checkpoint",
     'GUARD NET: "Convoy two, report position."',
     'VASILE: "Stay in the column, Biribel. Salute when they salute and keep your eyes down."'),
    ("m5_quarter", "start_mission5_quarter_checkpoint",
     'MARU: "Curfew sweep is two streets east. Rain covers your footsteps."',
     'VASILE: "The Print Works is past the market arcade. Do not stop for anyone."'),
    ("m5_tunnel", "start_mission5_tunnel_checkpoint",
     'MARU: "Signal is bad down here. Follow the cable trays."',
     'VASILE: "Thirty metres to the drain. Lights out when you hear the pumps."'),
]

RECTS = []


def _after():
    try:
        import ui.radio  # noqa: F401
        return True
    except ImportError:
        return False


def _live(I, text, start, vo=0, pri=0.5):
    speaker, body = I._split_radio(text)
    from core.config import SPEAKER_COLORS
    col = SPEAKER_COLORS.get(speaker, (150, 170, 190))
    end = start + I.subtitle_ms(text, vo)
    return {"text": text, "speaker": speaker, "body": body, "color": col,
            "start": start, "end": end, "vo_ms": vo, "priority": pri}


def _frame(cam):
    from core import game_core as gc
    gc.game_draw(*cam)


def scene(out, name, start_fn, line_a, line_b):
    from core import game_core as gc
    from core.state import STATE
    from core import interactions as I
    getattr(gc, start_fn)()
    STATE.enemies = []
    for flag in ("mission2_card", "m5_dialogue_active"):
        if hasattr(STATE, flag):
            setattr(STATE, flag, None if flag.endswith("card") else False)
    W, H = config.screen.get_size()
    px, py = STATE.player.rect.center
    cam = (px - W // 2, py - H // 2)
    STATE.camera_x, STATE.camera_y = cam
    STATE.floating_texts[:] = [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]
    if _after():
        from ui import radio as R
        R.TRANSMISSION.reset()
        I._app_state, I._app_transitioning = "GAME", False
        I.radio_allowed = lambda *a, **k: True
        I.queue_depth = lambda: 1
        a = _live(I, line_a, 0)
        b = _live(I, line_b, a["end"] + 600, pri=1)
        for live, clk in ((a, 50), (a, a["end"] - 10), (b, b["start"]), (b, b["start"] + 1400)):
            I._radio_live, I._radio_clock = live, clk
            _frame(cam)
    else:
        x, y = STATE.player.rect.center
        STATE.floating_texts.append([x, y + 20, line_a, (150, 170, 190), 40, "pin"])
        STATE.floating_texts.append([x, y + 20, line_b, (150, 170, 190), 220, "pin"])
        for _ in range(2):
            _frame(cam)
    pygame.image.save(config.screen, str(out / (name + ".png")))
    print("%-11s widget=%s" % (name, RECTS[-1] if RECTS else "-"))
    return config.screen.copy()


def letterbox(out, base):
    from missions.m2 import draw as d2
    surf = base.copy()
    bar = 86
    pygame.draw.rect(surf, (0, 0, 0), (0, 0, surf.get_width(), bar))
    pygame.draw.rect(surf, (0, 0, 0), (0, surf.get_height() - bar, surf.get_width(), bar))
    d2._draw_sniper_subtitles(surf, bar)
    pygame.image.save(surf, str(out / "letterbox.png"))


def variants(out, base_scene):
    from core import interactions as I
    from ui import radio as R
    base = base_scene
    long_text = ('VASILE: "Listen carefully, because I will only say this once: the convoy '
                 'stops at the checkpoint, the guard counts heads, you answer to the name on '
                 'the plate, and you do not, under any circumstance, look at the press."')
    cases = [
        ("small text", dict(radio_text_size=0), 'MARU: "Two guards at the gate, one in the tower."', 0, 0.5, 1500, 0),
        ("large text", dict(radio_text_size=2), 'MARU: "Two guards at the gate, one in the tower."', 0, 0.5, 1500, 0),
        ("names off", dict(radio_speaker_names=False), 'VASILE: "Keep your eyes down."', 0, 0.5, 1500, 0),
        ("subs off, voiced", dict(subtitles=False), 'VASILE: "Keep your eyes down."', 3200, 0.5, 900, 0),
        ("long line scrolled", {}, long_text, 0, 0.5, 6200, 0),
        ("critical + queue", {}, 'KRAP COMMAND: "ABORT. Guard net is onto you."', 0, 1, 320, 3),
    ]
    tiles = []
    for label, prefs, text, vo, pri, age, queued in cases:
        saved = dict(R.PREFS)
        R.PREFS.update(prefs)
        R.TRANSMISSION.reset()
        live = _live(I, text, 0, vo=vo, pri=pri)
        R.TRANSMISSION.draw(base.copy(), live=live, clock=10, queued=queued)
        s = base.copy()
        rect = R.TRANSMISSION.draw(s, live=live, clock=age, queued=queued)
        R.PREFS.clear()
        R.PREFS.update(saved)
        crop = rect.inflate(40, 40).clip(s.get_rect()) if rect else s.get_rect()
        tile = pygame.Surface((560, 200))
        tile.fill((20, 20, 20))
        sub = s.subsurface(crop)
        k = min(560 / crop.w, 176 / crop.h, 1.0)
        tile.blit(pygame.transform.scale(sub, (int(crop.w * k), int(crop.h * k))), (0, 24))
        f = R._label_font(2) if hasattr(R, "_label_font") else R._font("bold", 14)
        tile.blit(f.render(label.upper(), True, (240, 200, 90)), (6, 4))
        tiles.append(tile)
        print("variant %-20s rect=%s" % (label, rect))
    sheet = pygame.Surface((560 * 2, 200 * 3))
    for i, t in enumerate(tiles):
        sheet.blit(t, ((i % 2) * 560, (i // 2) * 200))
    pygame.image.save(sheet, str(out / "variants.png"))


def main(argv):
    out = ROOT / argv[0]
    out.mkdir(parents=True, exist_ok=True)
    if _after():
        from ui import radio as R
        real = R.draw_radio

        def spy(*a, **k):
            r = real(*a, **k)
            RECTS.append(r)
            return r
        R.draw_radio = spy
    base = None
    for name, fn, a, b in SCENES:
        try:
            frame = scene(out, name, fn, a, b)
        except Exception as e:  # noqa: BLE001 - evidence only
            import traceback
            traceback.print_exc()
            print("scene %s skipped: %s" % (name, e))
            continue
        if name == "m5_hq":
            base = frame
    if base is not None:
        letterbox(out, base)
        if _after():
            from core import interactions as I
            from core import game_core as gc
            I._radio_live = None
            from ui import radio as R
            R.TRANSMISSION.reset()
            gc.start_mission5_hq_checkpoint()
            from core.state import STATE
            W, H = config.screen.get_size()
            px, py = STATE.player.rect.center
            _frame((px - W // 2, py - H // 2))
            variants(out, config.screen.copy())
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1:])
