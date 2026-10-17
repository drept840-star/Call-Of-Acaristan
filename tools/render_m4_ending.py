"""Render the real M4 cutscene player safely, without importing app's loop.

Outputs a sound-on MP4 and camera contact sheet. Save/settings/profile paths
are isolated before imports. Uses native game art, captions, timeline and audio.
"""
import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stills-only", action="store_true")
    args = parser.parse_args()
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="acaristan_m4_preview_") as tmp:
        from core import save_system, settings_store, profile_store
        save_system.SAVE_FILE = str(Path(tmp) / "save.json")
        settings_store.SAVE_FILE = str(Path(tmp) / "settings.json")
        profile_store.PROFILE_FILE = str(Path(tmp) / "profile.json")
        import pygame
        import numpy as np
        from core import config, game_core as gc
        from core.state import STATE
        from cutscenes import engine
        from missions.m4.meta import mission4_ending_shots
        from PIL import Image, ImageDraw, ImageFont

        STATE.reduced_motion = False
        W, H = config.WIDTH, config.HEIGHT
        shots = mission4_ending_shots
        audio = config.audio
        # Compile exact production player classes; do not execute application
        # startup, load the user's settings, or enter an interactive main loop.
        names = {"CutscenePlayer", "_CutsceneState", "_set_ambience", "_play_typewriter_tick"}
        tree = ast.parse((ROOT / "src" / "app.py").read_text(encoding="utf-8-sig"))
        nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
        now = [1000]
        saved_ticks = pygame.time.get_ticks
        pygame.time.get_ticks = lambda: now[0]
        from engine.core import pin_wall, unpin_wall   # RPE6 B-001: app.py reads the engine clock
        pin_wall(ms=lambda: now[0])
        namespace = dict(vars(config))
        namespace["_now_ms"] = lambda: now[0]
        done = []
        namespace.update(GameState=type("PreviewState", (), {}), gc=gc, audio=audio,
                         KO_CUT_CUES={}, TEXT_SPEED=4, active_cutscene=None,
                         _current_ambience=set(), _advance_grain=lambda: None,
                         gsm=type("PreviewFSM", (), {"transition": lambda self, target: done.append(target)})(),
                         mission_complete_timer=0, mission_complete_fade=0)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "app_cutscene_preview", "exec"), namespace)
        player_state = namespace["_CutsceneState"]()
        try:
            sheet = Image.new("RGB", (1500, 960), (9, 13, 21))
            draw = ImageDraw.Draw(sheet)
            font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "IBMPlexMono-Regular.ttf"), 15)
            samples = [(0, 500, "01  PUBLIC BROADCAST"), (0, 3300, "02  THE PRESIDENT"),
                       (0, 6000, "03  REALIZATION"), (0, 8100, "04  CUFFS / SLOW INSERT"),
                       (0, 10800, "05  ESCORT"), (0, 14800, "06  POWER REMAINS"),
                       (1, 4200, "07  MARU / WRONG NAME"), (2, 5400, "08  ROOFTOP / FIRST LIGHT"),
                       (3, 5000, "09  THE CHOICE TO STAY")]
            for i, (idx, ms, label) in enumerate(samples):
                cp = namespace["CutscenePlayer"]([shots[idx]], "MISSION4_COMPLETE", use_fades=False)
                namespace["active_cutscene"] = cp
                now[0] = cp.start_time + ms
                cp.char_idx = len(cp.current_shot["text"])
                engine.reset_dialogue_slide()
                player_state.render(config.screen)
                image = Image.frombytes("RGB", (W, H), pygame.image.tobytes(config.screen, "RGB"))
                image.thumbnail((500, 284), Image.Resampling.NEAREST)
                x, y = i % 3 * 500, i // 3 * 320
                sheet.paste(image, (x + (500 - image.width) // 2, y))
                draw.text((x + 17, y + 286), label, fill=(208, 201, 179), font=font)
            sheet.save(out / "ending_camera_sheet.png")
            print("CAMERA SHEET: " + str(out / "ending_camera_sheet.png"))
            if args.stills_only:
                return

            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            video = Path(tmp) / "picture.mp4"
            proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo",
                                     "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30",
                                     "-i", "-", "-an", "-c:v", "libx264", "-preset", "fast",
                                     "-crf", "19", "-pix_fmt", "yuv420p", str(video)], stdin=subprocess.PIPE)
            # Capture the real player's cue/ambience calls and mix the same PCM
            # offline; wall-clock headless speed cannot reliably record SDL audio.
            sr = pygame.mixer.get_init()[0]
            events, active_loops = [], {}
            current_tick = [0]
            original_play, original_stop = audio.play, audio.stop

            def record_play(name, volume=1.0, loops=0, channel=None):
                sound = audio.get_sound(name)
                if sound is not None:
                    pcm = pygame.sndarray.array(sound).astype(np.float64) / 32768
                    if pcm.ndim == 1:
                        pcm = np.repeat(pcm[:, None], 2, axis=1)
                    pcm *= audio._effective_volume(name, volume)
                    event = [current_tick[0] / 60, name, pcm, loops, None]
                    events.append(event)
                    if loops:
                        active_loops[name] = event
                return None

            def record_stop(name=None, channel=None):
                if name in active_loops:
                    active_loops.pop(name)[4] = current_tick[0] / 60
                original_stop(name, channel)

            for shot in shots:
                for _, name, _ in shot.get("cues", ()):
                    audio.get_sound(name)
            for name in ("room_tone", "elec_hum", "m4_roof_air"):
                audio.get_sound(name)
            audio.play, audio.stop = record_play, record_stop
            cp = namespace["CutscenePlayer"](shots, "MISSION4_COMPLETE", use_fades=True)
            namespace["active_cutscene"] = cp
            origin = now[0]
            last_idx, readable_since = -1, None
            frame_count = 0
            space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
            try:
                for tick in range(60 * 120):
                    current_tick[0] = tick
                    now[0] = origin + round(tick * 1000 / 60)
                    pygame.event.pump()
                    player_state.update(1 / 60)
                    player_state.set_ambience()
                    if cp.shot_idx != last_idx:
                        last_idx, readable_since = cp.shot_idx, None
                    if cp.char_idx >= len(cp.current_shot["text"]) and readable_since is None:
                        readable_since = tick
                    if readable_since is not None and tick - readable_since >= 100 and cp.elapsed_ms >= cp.current_shot["min_ms"] and cp.transition_timer == 0:
                        player_state.handle_event(space, 0, 0, {})
                        readable_since = None
                    if done:
                        break
                    if tick % 2 == 0:
                        player_state.render(config.screen)
                        proc.stdin.write(pygame.image.tobytes(config.screen, "RGB"))
                        frame_count += 1
                else:
                    raise RuntimeError("Cutscene did not reach its completion route")
                player_state.exit()
            finally:
                audio.play, audio.stop = original_play, original_stop
                proc.stdin.close()
                code = proc.wait()
                if code:
                    raise RuntimeError("Video encoder failed: " + str(code))
            duration = frame_count / 30
            mix = np.zeros((round(duration * sr), 2), dtype=np.float64)
            for start, name, pcm, loops, stop in events:
                offset = round(start * sr)
                length = min(len(mix) - offset, round(((stop if stop is not None else duration) - start) * sr)) if loops else min(len(pcm), len(mix) - offset)
                if length <= 0:
                    continue
                if loops:
                    data = np.tile(pcm, (int(np.ceil(length / len(pcm))), 1))[:length]
                    edge = min(round(.08 * sr), length // 2)
                    data[:edge] *= np.linspace(0, 1, edge)[:, None]
                    data[-edge:] *= np.linspace(1, 0, edge)[:, None]
                    # Match the production brief ambience duck under cuff contact.
                    if name == "room_tone":
                        a, b = max(0, round(7.6 * sr) - offset), min(length, round(9.4 * sr) - offset)
                        if b > a:
                            data[a:b] *= .16
                else:
                    data = pcm[:length]
                mix[offset:offset + length] += data
            peak = float(np.max(np.abs(mix)))
            if peak > .92:
                mix *= .92 / peak
            wav_path = Path(tmp) / "mix.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(sr)
                wav.writeframes((mix * 32767).astype("<i2").tobytes())
            result = out / "ending_cinematic_preview.mp4"
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav_path),
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(result)], check=True)
            print(f"ENDING PREVIEW: {duration:.2f}s, {frame_count} frames, {len(events)} audio cues/loops, mix peak {peak:.3f}")
            print("VIDEO: " + str(result))
        finally:
            unpin_wall()
            pygame.time.get_ticks = saved_ticks
            pygame.quit()


if __name__ == "__main__":
    main()
