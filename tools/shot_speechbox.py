"""Evidence shots for the shared speech box (``ui.speechbox``).

    python tools/shot_speechbox.py OUTDIR

Writes OUTDIR/<scene>.png: M5 Vasile's office conversation (half typed and
fully typed), the walking sim line, a CutscenePlayer film caption mid-reveal,
the M7 farm box and a cutscene dialogue box, plus open.png (the unfold
animation frames). Prints the reveal window for a voiced and an unvoiced line.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402
from core import config  # noqa: E402


def _cam():
    from core.state import STATE
    W, H = config.screen.get_size()
    px, py = STATE.player.rect.center
    return px - W // 2, py - H // 2


def _save(out, name):
    pygame.image.save(config.screen, str(out / (name + ".png")))
    print("saved", name)


def m5_office(out):
    from core import game_core as gc
    from core.state import STATE
    from missions.m5 import flow
    from missions.m5 import draw as d5
    gc.start_mission5_hq_checkpoint()
    STATE.enemies = []
    flow._start_vasile_dialogue()
    STATE.request_m5_cutscene = None
    beat = flow._current_beat()
    for name, n in (("m5_office_typing", len(beat["text"]) // 2),
                    ("m5_office_done", len(beat["text"]))):
        flow._m5_dlg["char_idx"] = n
        gc.game_draw(*_cam())
        d5._draw_dialogue(config.screen)
        _save(out, name)
    flow._dlg_reset()
    STATE.m5_dialogue_active = False


def walking(out):
    from core import game_core as gc
    from missions import walking_sim as ws
    gc.start_walking_sim()
    text = "Harbour is two streets down. Keep your head low and your hands where they can see them."
    ws.set_walk_dialogue("VASILE", text)
    ws.walk_dialogue_char_idx = 58
    ws.draw_walking_sim()
    _save(out, "walk_sim")
    ws.clear_walk_dialogue()


def film_caption(out):
    from core import game_core as gc
    from cutscenes import engine as eng
    shot = next(s for s in gc.cutscene1_shots if s.get("speaker") and s.get("text"))
    eng.draw_cutscene_scene(config.screen, shot, 1200)
    config.draw_letterbox(config.screen)
    eng.draw_film_caption(config.screen, shot["speaker"], shot["text"],
                          typed=int(len(shot["text"]) * 0.6))
    _save(out, "cutscene_caption")
    eng.draw_cutscene_scene(config.screen, shot, 1200)
    config.draw_letterbox(config.screen)
    eng.reset_dialogue_slide()
    eng.draw_dialogue_box(config.screen, shot["speaker"], shot["text"],
                          len(shot["text"]), len(shot["text"]))
    _save(out, "cutscene_box")


def m7_farm(out):
    from core import game_core as gc
    from cutscenes import engine as eng
    gc.start_mission7()
    gc.game_draw(*_cam())
    text = "Goats first, then the generator. The tractor can wait until the light goes."
    eng.reset_dialogue_slide()
    eng.draw_dialogue_box(config.screen, "GABI", text, len(text), len(text),
                          can_continue=True, show_speaker=True)
    _save(out, "m7_farm")


def open_strip(out):
    from engine.core import pin_wall, unpin_wall
    from ui import speechbox as sb
    base = pygame.Surface(config.screen.get_size())
    strip = pygame.Surface((config.screen.get_width(), 5 * 150))
    t = [0]
    pin_wall(ms=lambda: t[0])
    try:
        sb.reset_box()
        text = "Two guards at the gate, one in the tower."
        for i, ms in enumerate((0, 40, 80, 120, 240)):
            t[0] = 100000 + ms
            base.fill((30, 34, 38))
            r = sb.draw_box(base, "MARU", text, sb.reveal_count(text, ms, 2600))
            strip.blit(base, (0, i * 150), r.inflate(0, 150 - r.h).clip(base.get_rect()))
    finally:
        unpin_wall()
    pygame.image.save(strip, str(out / "open.png"))
    print("saved open")


def main(argv):
    out = ROOT / (argv[0] if argv else "shots/speechbox")
    out.mkdir(parents=True, exist_ok=True)
    from ui import speechbox as sb
    print("voiced 3.2 s, 60 chars ->", sb.reveal_window("x" * 60, 3200),
          "| radio ->", sb.reveal_window("x" * 60, 3200, radio=True),
          "| unvoiced ->", sb.reveal_window("x" * 60, 0))
    open_ms = sb.OPEN_MS
    for fn in (m5_office, walking, film_caption, m7_farm, open_strip):
        sb.OPEN_MS = open_ms if fn is open_strip else 0   # stills: fully open
        try:
            fn(out)
        except Exception:  # noqa: BLE001 - evidence only
            import traceback
            traceback.print_exc()
    print("saved to", out)


if __name__ == "__main__":
    main(sys.argv[1:])
