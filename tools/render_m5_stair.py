"""Export the complete updated M5 stair shot with its production sound cues."""
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
os.environ.setdefault('ACARISTAN_RENDERER', 'gl')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    import numpy as np
    import pygame
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg is required')
    output = ROOT / 'outputs' / 'Biribel_Maru_Stairwell.mp4'
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='m5_stair_export_') as tmp:
        from core import save_system, settings_store, profile_store
        save_system.SAVE_FILE = str(Path(tmp) / 'save.json')
        settings_store.SAVE_FILE = str(Path(tmp) / 'settings.json')
        profile_store.PROFILE_FILE = str(Path(tmp) / 'profile.json')
        from core import config
        from cutscenes import m5mid3d as mid, m5martial3d as film
        from missions.m5.meta import M5_MID_CUTSCENES
        shot = M5_MID_CUTSCENES['descent'][0]
        duration = shot['min_ms'] / 1000
        fps = 30
        frames = math.ceil(duration * fps)
        screen = pygame.Surface(config.screen.get_size())
        w, h = screen.get_size()
        raw = Path(tmp) / 'picture.mp4'
        encoder = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', str(raw)], stdin=subprocess.PIPE)
        try:
            for i in range(frames):
                pygame.event.pump()
                mid.M5X_SCENES[shot['scene']](screen, round(i * 1000 / fps))
                encoder.stdin.write(pygame.image.tobytes(screen, 'RGB'))
        finally:
            encoder.stdin.close()
            code = encoder.wait()
        if code:
            raise RuntimeError('Picture encoding failed')
        sr = pygame.mixer.get_init()[0]
        mix = np.zeros((round(duration * sr), 2), np.float64)
        for ms, name, gain in shot.get('cues', []):
            sound = config.audio.get_sound(name)
            if sound is None:
                raise RuntimeError('Missing production sound: ' + name)
            pcm = pygame.sndarray.array(sound).astype(np.float64) / 32768
            if pcm.ndim == 1:
                pcm = np.repeat(pcm[:, None], 2, axis=1)
            pcm *= config.audio._effective_volume(name, gain)
            start = round(ms * sr / 1000)
            n = min(len(pcm), len(mix) - start)
            if n > 0:
                mix[start:start+n] += pcm[:n]
        peak = float(np.abs(mix).max())
        if peak > .97:
            mix *= .97 / peak
        wav = Path(tmp) / 'sound.wav'
        with wave.open(str(wav), 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(sr)
            audio.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes())
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', str(raw), '-i', str(wav), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', str(duration), '-movflags', '+faststart', str(output)], check=True)
        print(f'RENDER OK: {frames} frames, {duration:.1f}s, {w}x{h}, {fps}fps, {type(film._rend()[0]).__name__}, {len(shot.get("cues", []))} production sound cues')
        print(output)
    pygame.quit()


if __name__ == '__main__':
    main()
