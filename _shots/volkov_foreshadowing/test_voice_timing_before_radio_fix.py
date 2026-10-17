"""Voice clip timing must not depend on SDL's decoded length (asset diet, 2026-10-14).

`voice._clip_ms` reproduces what `Sound.get_length()` reported for the original
WAV exports: SDL sizes a resampled WAV as floor(frames * mixer_rate / source_rate)
samples; the radio FX adds int(rate*0.07) + int(rate*0.16) samples of squelch.
Vorbis clips decode 12-33 ms short in SDL, so the header-based value is the one
that keeps subtitles and ducking where they were.
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class ClipTiming(unittest.TestCase):
    def setUp(self):
        from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)
        from audio import voice
        self.voice = voice
        self.saved = voice._files            # None until the first scan
        voice._files = dict(self.saved or {})

    def tearDown(self):
        self.voice._files = self.saved

    def _wav(self, frames, rate):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(b"\x00\x00" * frames)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_wav_era_length_rule(self):
        v = self.voice
        # pin the mixer rate the rule is stated for (another test may have booted the mixer at 44.1 kHz)
        import pygame
        real_get_init = pygame.mixer.get_init
        pygame.mixer.get_init = lambda: None          # -> voice falls back to its 22050 Hz mixer rate
        self.addCleanup(lambda: setattr(pygame.mixer, "get_init", real_get_init))
        v._files["T"] = self._wav(218881, 24000)      # 9.1200416 s at 24 kHz
        # SDL: floor(218881 * 22050 / 24000) = 201096 samples -> 9120 ms
        self.assertEqual(v._clip_ms("T", False, None), 9120)
        # radio: + int(22050*0.07) + int(22050*0.16) = 1543 + 3528 samples
        self.assertEqual(v._clip_ms("T", True, None), int((201096 + 5071) / 22050.0 * 1000))

    def test_ogg_header_reader_matches_shipped_assets(self):
        v = self.voice
        oggs = sorted((ROOT / "assets" / "voice").rglob("*.ogg"))
        if not oggs:
            self.skipTest("no ogg voice assets")
        n, rate = v._ogg_frames(str(oggs[0]))
        self.assertEqual(rate, 24000)
        self.assertGreater(n, 24000 // 4)             # at least a quarter second
        self.assertAlmostEqual(v._duration(str(oggs[0])), n / 24000.0)
        v._files["O"] = str(oggs[0])
        self.assertEqual(v._clip_ms("O", False, None), int((n * 22050 // 24000) / 22050.0 * 1000))

    def test_falls_back_to_decoded_length_without_a_header(self):
        class Snd:
            def get_length(self):
                return 1.234
        self.voice._files.pop("missing", None)
        self.assertEqual(self.voice._clip_ms("missing", False, Snd()), 1234)


if __name__ == "__main__":
    unittest.main()
