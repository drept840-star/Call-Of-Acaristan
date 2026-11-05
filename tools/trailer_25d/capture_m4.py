"""Mission 4 2.5D clip for the announcement trailer: the m4_gameplay_video
bot run with its captions and title cards switched off.

    python tools/trailer_25d/capture_m4.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import m4_gameplay_video as v  # noqa: E402

v.Recorder.set_caption = lambda self, *a, **k: None
v.Recorder.card = lambda self, *a, **k: None
sys.argv = [sys.argv[0], os.path.join(ROOT, "trailers", "announce_25d", "clips", "m4_3d.mp4")]
v.main()
