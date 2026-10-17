import copy
import os
import sys
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["ACARISTAN_RENDERER"] = "software"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
MODE = sys.argv[1]
assert MODE in ("m1", "m3")
sys.argv = ["acaristan.py", "--dev-m1" if MODE == "m1" else "--dev-audio-parade"]

from core import json_store

stores = {}

def save_memory(path, obj, indent=2):
    stores[path] = copy.deepcopy(obj)

def load_memory(path, default):
    return copy.deepcopy(stores[path]) if path in stores else default()

json_store.atomic_write = save_memory
json_store.load_with_backup = load_memory

import pygame
from engine.core import pin_wall
from engine.core.app import App

clock = [100000]
frame = [0]
finished = [False]
captures = set()
seen = []

class Clock:
    def tick(self, fps=0):
        return 16
    def get_time(self):
        return 16
    def get_fps(self):
        return 60.0

pygame.time.Clock = Clock
pin_wall(ms=lambda: clock[0])
get_events = pygame.event.get
flip = pygame.display.flip
run_scene = App.run_scene


def setup(self, scene):
    app = sys.modules["app"]
    from core.state import STATE
    from core import interactions as I
    I.clear_radio()
    I.pump_radio("GAME", False)
    if MODE == "m1":
        STATE.player.rect.center = (14 * 64 + 32, 17 * 64 + 32)
        STATE.civilian_payoff_done = True
        enemy = STATE.enemies[0]
        STATE.enemies[:] = [enemy]
        enemy.alerted = True
        enemy.fire_cooldown = 10000
    else:
        STATE.enemies.clear()
        app.audio.verbose = False
    return run_scene(self, scene)


def scripted_events(*args, **kwargs):
    get_events(*args, **kwargs)
    if finished[0] or frame[0] >= 3600:
        return [pygame.event.Event(pygame.QUIT)]
    if MODE != "m3":
        return []
    app = sys.modules.get("app")
    if app is None:
        return []
    from core.state import STATE
    from missions.m3 import systems
    if frame[0] in (2, 4, 6):
        target = {2: systems._comms_breaker_pos,
                  4: systems._comms_auth_pos,
                  6: systems._relay_pos}[frame[0]]
        STATE.player.rect.center = target()
        return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)]
    if STATE.mission3_stage == systems.STAGE_COMMS and STATE.m3_relay_tuned:
        STATE.player.rect.center = (
            systems._ARCHIVE_EXIT_COL * 64 + 32,
            systems._ARCHIVE_EXIT_ROW * 64 + 32,
        )
    cp = app.active_cutscene
    if cp is not None and app.gsm.current_name == "CUTSCENE":
        shot = cp.current_shot
        if shot and cp.transition_timer == 0 and cp.elapsed_ms >= shot.get("min_ms", 0):
            if cp.char_idx >= len(shot["text"]):
                if shot.get("speaker") != "VOLKOV" or "m3_warning" in captures:
                    return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]
    return []


def screenshot(name):
    if name not in captures:
        pygame.image.save(pygame.display.get_surface(), str(Path(__file__).parent / (name + ".png")))
        captures.add(name)
        print("CAPTURE", name, "frame", frame[0], flush=True)


def capture_flip():
    flip()
    app = sys.modules.get("app")
    if app is not None:
        from core.state import STATE
        from core import interactions as I
        live = I.live_line()
        if live is not None:
            key = (live["speaker"], live["body"], live["start"])
            if key not in seen:
                seen.append(key)
        if MODE == "m1":
            assert not STATE.player_dead
            if live is not None and I.radio_clock() - live["start"] >= max(1250, live["vo_ms"]):
                if live["speaker"] == "VOLKOV":
                    assert live["body"] == "Read it before you hand it over!"
                    screenshot("m1_warning")
                elif "Volkov escaped!" in live["body"]:
                    screenshot("m1_followup")
                    assert STATE.volkov_escaped
                    finished[0] = True
        else:
            cp = app.active_cutscene
            if app.gsm.current_name == "CUTSCENE" and cp is not None:
                assert I.live_line() is None, "radio overlapped cutscene"
                shot = cp.current_shot
                if shot and cp.char_idx >= len(shot["text"]) and cp.transition_timer == 0:
                    if "Your captain's code" in shot["text"]:
                        screenshot("m3_warning")
                    elif shot.get("speaker") == "VASILE":
                        screenshot("m3_followup")
            if "m3_followup" in captures and app.gsm.current_name == "GAME":
                from missions.m3.meta import STAGE_ARCHIVES
                if STATE.mission3_stage == STAGE_ARCHIVES:
                    finished[0] = True
    frame[0] += 1
    clock[0] += 16

App.run_scene = setup
pygame.event.get = scripted_events
pygame.display.flip = capture_flip
try:
    import app
except SystemExit as exc:
    assert exc.code in (None, 0), exc.code
assert finished[0], (MODE, frame[0], captures, seen)
assert {MODE + "_warning", MODE + "_followup"} <= captures
if MODE == "m1":
    assert sum(speaker == "VOLKOV" for speaker, body, start in seen) == 1
print("LIVE VOLKOV", MODE, "OK", "frames", frame[0], flush=True)
