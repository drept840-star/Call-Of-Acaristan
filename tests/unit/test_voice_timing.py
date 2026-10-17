"""Voice clip timing must not depend on SDL's decoded length (asset diet, 2026-10-14).

`voice._clip_ms` reproduces what `Sound.get_length()` reported for the original
WAV exports: SDL sizes a resampled WAV as floor(frames * mixer_rate / source_rate)
samples; the radio FX adds int(rate*0.07) + int(rate*0.16) samples of squelch.
Vorbis clips decode 12-33 ms short in SDL, so the header-based value is the one
that keeps subtitles and ducking where they were.
"""
from __future__ import annotations

import array
import io
import os
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

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

    def test_alternate_encodings_do_not_shift_dialogue(self):
        v = self.voice
        lines = [(f"VO_{i:03}", "VASILE", "Move to the next door.") for i in range(1, 4)]
        stems = [f"Generated Audio October 07, 2026 - 9_0{i}PM" for i in range(3)]
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Vasile"
            folder.mkdir()
            names = [stem + ext for stem in stems for ext in (".wav", ".ogg")]
            for name in names:
                (folder / name).touch()
            for order in (names, list(reversed(names))):
                with patch.object(v, "_voice_dir", return_value=root), \
                        patch.object(v, "VOICE_LINES", lines), \
                        patch.object(v, "VOICE_ORDER", {"VASILE": [line[0] for line in lines]}), \
                        patch.object(v, "_duration", return_value=2.0), \
                        patch.object(v.os, "walk", return_value=[(root, ["Vasile"], []),
                                                               (str(folder), [], order)]):
                    v._scan_files()
                self.assertEqual([Path(v._files[line[0]]).stem for line in lines], stems)
                self.assertTrue(all(Path(path).suffix == ".ogg" for path in v._files.values()))

    def test_named_alternate_encodings_have_stable_preference(self):
        v = self.voice
        with tempfile.TemporaryDirectory() as root:
            for name in ("VO_901.wav", "VO_901.ogg"):
                (Path(root) / name).touch()
            for names in (["VO_901.wav", "VO_901.ogg"], ["VO_901.ogg", "VO_901.wav"]):
                with patch.object(v, "_voice_dir", return_value=root), \
                        patch.object(v.os, "walk", return_value=[(root, [], names)]):
                    v._scan_files()
                self.assertEqual(Path(v._files["VO_901"]).name, "VO_901.ogg")

    def test_radio_cache_tracks_source_audio_not_only_voice_id(self):
        v = self.voice

        class Snd:
            def __init__(self, raw):
                self.raw = raw
            def get_raw(self):
                return self.raw

        with tempfile.TemporaryDirectory() as root:
            first = str(Path(root) / "first.wav")
            second = str(Path(root) / "second.wav")
            for path in (first, second):
                Path(path).touch()
            cache = Path(root) / "_radio_cache"
            cache.mkdir()
            legacy = cache / "VO_901.wav"
            legacy.write_bytes(b"old mapping")
            os.utime(legacy, (2000000000, 2000000000))
            sources = {first: Snd(b"\x01\x00" * 4), second: Snd(b"\x02\x00" * 4)}
            processed = Snd(b"processed")
            stale = Snd(b"wrong recording")

            def load(source):
                if isinstance(source, io.BytesIO):
                    return processed
                if source == str(legacy):
                    return stale
                return sources.get(source, processed)

            with patch.object(v, "_voice_dir", return_value=root), \
                    patch.object(v, "_clean", {}), patch.object(v, "_radio", {}), \
                    patch.object(v, "_load_sound", side_effect=load), \
                    patch.object(v.pygame.mixer, "get_init", return_value=(22050, -16, 2)), \
                    patch.object(v, "_radio_samples", return_value=array.array("h", [1, 1])) as render:
                v._files["VO_901"] = first
                self.assertIs(v._load("VO_901", True), processed)
                self.assertEqual(render.call_count, 1)
                v._clean.clear()
                v._radio.clear()
                self.assertIs(v._load("VO_901", True), processed)
                self.assertEqual(render.call_count, 1, "same source was unnecessarily reprocessed")
                v._files["VO_901"] = second
                v._clean.clear()
                v._radio.clear()
                self.assertIs(v._load("VO_901", True), processed)
                self.assertEqual(render.call_count, 2, "changed source reused the old recording")
            self.assertEqual(len(list(cache.glob("VO_901_*.wav"))), 2)


if __name__ == "__main__":
    unittest.main()
