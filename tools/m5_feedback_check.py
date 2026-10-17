"""Focused M5 feedback regressions and visual evidence, without touching saves."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


class Keys:
    def __getitem__(self, key):
        return False


def main():
    with tempfile.TemporaryDirectory(prefix="m5_feedback_") as tmp:
        from core import save_system, settings_store, profile_store
        save_system.SAVE_FILE = str(Path(tmp) / "save.json")
        settings_store.SAVE_FILE = str(Path(tmp) / "settings.json")
        profile_store.PROFILE_FILE = str(Path(tmp) / "profile.json")
        import pygame
        import numpy as np
        from core import config, interactions as radio
        from core.state import STATE
        from missions import m5
        from missions.m5 import flow, world, water
        from missions.m5.meta import M5_MID_CUTSCENES, mission5_ending_shots
        from cutscenes import m5martial3d as film, m5mid3d as mid
        from audio import voice
        out = ROOT / "outputs" / "m5_feedback"
        out.mkdir(parents=True, exist_ok=True)
        screen = config.screen

        # Arrival does not reveal Maru, and the real search is still required.
        m5.start_mission5_printworks_checkpoint()
        assert not STATE.m5_maru_found and not STATE.m5_dialogue_active
        with patch.object(mid, "_person") as actors:
            r, _ = film._rend()
            r.begin()
            mid._pw_interior(r, 2600, 1.0)
            assert not any(c.args[1] == "maru" for c in actors.call_args_list)
        mid._arrival_door(screen, 3000)
        pygame.image.save(screen, str(out / "arrival_empty_hall.png"))
        print("arrival_search_continuity: OK")

        # Stair handoff waits for the film; combat cannot progress while pending.
        STATE.m5_maru_found = STATE.m5_dialogue_done = True
        m5._begin_raid()
        STATE.m5_raid_active = False
        STATE.player.rect.center = m5._stair_pos()
        STATE.m5_maru["x"], STATE.m5_maru["y"] = map(float, m5._stair_pos())
        flow._update_stage()
        assert STATE.request_m5_cutscene == "descent" and STATE.mission5_stage == m5.STAGE_RAID
        old_map, old_pos, old_hp = m5.MISSION5_MAP, STATE.player.rect.center, STATE.player.hp
        for _ in range(8):
            m5.game_update(Keys())
        assert m5.MISSION5_MAP is old_map and STATE.player.rect.center == old_pos and STATE.player.hp == old_hp
        flow.on_m5_cutscene_done("descent")
        assert STATE.mission5_stage == m5.STAGE_TUNNEL and STATE.mission5_tunnel_checkpoint_reached
        assert not STATE.request_m5_cutscene
        for ms in (300, 2000, 3700):
            mid._basement_descent(screen, ms)
            pygame.image.save(screen, str(out / ("descent_%04d.png" % ms)))
        mid._basement_descent_2d(screen, 2200)
        pygame.image.save(screen, str(out / "descent_2d_fallback.png"))
        print("descent_handoff_and_freeze: OK")

        # Radio: an unvoiced line is NEVER preempted while typing/reading.
        now = [1000]
        STATE.m5_dialogue_active = False
        with patch.object(pygame.time, "get_ticks", side_effect=lambda: now[0]), patch.object(voice, "play_line", return_value=0):
            radio.clear_radio_queue()
            radio._radio_clock = 0
            radio._radio_last_tick = None
            radio._radio_live_until = 0
            radio._radio_block = None
            radio.pump_radio("GAME", False)
            radio.trigger_radio_chatter("MARU: Follow the tunnel. Stay close; the river is ahead.", priority=1)
            first = radio.live_line()
            assert first is not None
            radio.trigger_radio_chatter("VASILE: Second transmission.", priority=1)
            while radio.radio_clock() < first["end"]:
                now[0] += 100
                radio.pump_radio("GAME", False)
                if radio.radio_clock() < first["end"]:
                    assert radio.live_line() is first
            while radio.radio_clock() < first["end"] + 700:
                now[0] += 100
                radio.pump_radio("GAME", False)
            assert radio.live_line()["text"] == "VASILE: Second transmission."
        with patch.object(radio, "trigger_radio_chatter") as send:
            m5._radio_marks.clear()
            world._radio("LOUDSPEAKER: Filler.", mark="incidental")
            assert not send.called
            world._radio("MARU: Take the stairs.", mark="raid_over")
            world._radio("MARU: Take the stairs.", mark="raid_over")
            assert send.call_count == 1
        print("radio_readability_and_curation: OK")

        # Connected water is clipped to W, deterministic, animated, motion-safe.
        t = config.TILE_SIZE
        grid = ["CCCCC", "CWW.C", "CWW.C", "CCCCC"]
        surf = pygame.Surface((5 * t, 4 * t))
        def pixels(ms, reduced=False):
            surf.fill((70, 65, 58))
            water.draw(surf, grid, 0, 0, ms, reduced_motion=reduced)
            return pygame.surfarray.array3d(surf).copy()
        a, b = pixels(1000), pixels(2500)
        assert np.array_equal(a[:t], np.full_like(a[:t], (70, 65, 58)))
        assert not np.array_equal(a[t:3*t, t:3*t], b[t:3*t, t:3*t])
        assert np.array_equal(pixels(1000, True), pixels(9000, True))
        water._CACHE.clear()
        assert np.array_equal(a, pixels(1000))
        # Draw native gameplay with the improved flooded chamber.
        m5.start_mission5_tunnel_checkpoint()
        STATE.player.rect.center = m5._tile_world(18, 6)
        STATE.m5_maru["x"], STATE.m5_maru["y"] = m5._tile_world(17, 6)
        m5.game_draw(850, 0)
        pygame.image.save(screen, str(out / "flooded_chamber.png"))
        t0 = time.perf_counter()
        for i in range(20):
            water.draw(screen, m5.MISSION5_MAP, 850, 0, 1200 + i * 16)
        print("connected_water: OK (%.2f ms/frame)" % ((time.perf_counter() - t0) * 50))

        # Maru's filmed route stays on dry quay, and the shot reaches its dot beat.
        assert mission5_ending_shots[0]["min_ms"] >= 7200
        assert mission5_ending_shots[3]["min_ms"] >= 6200
        r, _ = film._rend()
        original = r.add_humanoid
        positions = []
        def record(hum, pose, pos, yaw, **kw):
            if hum is film._hum("maru"):
                positions.append(pos)
            return original(hum, pose, pos, yaw, **kw)
        with patch.object(r, "add_humanoid", side_effect=record):
            for ms in (250, 1800, 3200):
                film._river(screen, ms)
        assert len(positions) == 3 and all(0 <= p[2] <= 2.6 for p in positions)
        assert positions[0][0] < 6.9 < positions[-1][0]
        assert not film._cache.get("failed"), repr(film._cache.get("err"))
        print("river_path_and_shot_timing: OK; backend=" + str(getattr(r, "backend", "?")))
        print("M5 FEEDBACK CHECK: OK")
        print("Visual evidence: " + str(out))
        from PIL import Image, ImageDraw
        sheet = Image.new("RGB", (1500, 960), (12, 16, 22))
        labels = [("arrival_empty_hall.png", "ARRIVAL: EMPTY HALL / SEARCH STILL REQUIRED"),
                  ("descent_0300.png", "BASEMENT: UPPER LANDING"),
                  ("descent_2000.png", "BASEMENT: DESCENT"),
                  ("descent_3700.png", "BASEMENT: LOWER LANDING"),
                  ("flooded_chamber.png", "TUNNEL: CONNECTED FLOODWATER"),
                  ("descent_2d_fallback.png", "BASEMENT: 2D FALLBACK")]
        painter = ImageDraw.Draw(sheet)
        for i, (name, label) in enumerate(labels):
            image = Image.open(out / name).convert("RGB")
            image.thumbnail((500, 440), Image.Resampling.NEAREST)
            x, y = i % 3 * 500, i // 3 * 480
            sheet.paste(image, (x + (500 - image.width) // 2, y))
            painter.text((x + 12, y + 449), label, fill=(215, 211, 190))
        sheet.save(out / "review_sheet.jpg", quality=90)
        pygame.quit()


if __name__ == "__main__":
    main()
