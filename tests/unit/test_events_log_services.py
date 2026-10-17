"""engine.core: EventBus (§6.3), Log (§6.23), Services and Settings (§6.1)."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from tests.unit import _helpers  # noqa: F401

from engine.core import (CHANNELS, DEFAULTS, EventBus, Log, ServiceMissing, Services, Settings,
                         get_log)


@dataclass
class Damage:
    amount: int


@dataclass
class BigDamage(Damage):
    pass


class Events(unittest.TestCase):
    def test_emit_is_deferred_until_flush(self):
        bus, got = EventBus(), []
        bus.subscribe(Damage, got.append)
        bus.emit(Damage(3))
        self.assertEqual(got, [])
        self.assertEqual(bus.pending(), 1)
        self.assertEqual(bus.flush(), 1)
        self.assertEqual(got, [Damage(3)])

    def test_emit_now_is_synchronous(self):
        bus, got = EventBus(), []
        bus.subscribe(Damage, got.append)
        bus.emit_now(Damage(1))
        self.assertEqual(got, [Damage(1)])

    def test_subclass_delivery_and_scope_cleanup(self):
        bus, got = EventBus(), []
        scene = object()
        bus.subscribe(Damage, got.append, scope=scene)
        bus.emit_now(BigDamage(9))          # delivered through the MRO
        self.assertEqual(got, [BigDamage(9)])
        self.assertEqual(bus.unsubscribe_scope(scene), 1)
        bus.emit_now(Damage(2))
        self.assertEqual(got, [BigDamage(9)])

    def test_events_emitted_during_flush_are_delivered(self):
        bus, got = EventBus(), []

        def chain(e):
            got.append(e.amount)
            if e.amount > 0:
                bus.emit(Damage(e.amount - 1))

        bus.subscribe(Damage, chain)
        bus.emit(Damage(2))
        bus.flush()
        self.assertEqual(got, [2, 1, 0])
        self.assertEqual(len(bus.tail(10)), 3)

    def test_unsubscribe(self):
        bus, got = EventBus(), []
        sub = bus.subscribe(Damage, got.append)
        bus.unsubscribe(sub)
        bus.emit_now(Damage(1))
        self.assertEqual(got, [])


class LogTests(unittest.TestCase):
    def test_channels_and_ring_buffer(self):
        out = io.StringIO()
        log = Log(capacity=3, stream=out)
        for i in range(5):
            log.info("core", f"m{i}")
        self.assertEqual(log.tail(10), ["[RPE6][core] INFO: m2", "[RPE6][core] INFO: m3", "[RPE6][core] INFO: m4"])
        self.assertEqual(out.getvalue(), "")        # info is below the echo level
        log.warn("assets", "x")
        self.assertIn("[RPE6][assets] WARN: x", out.getvalue())
        with self.assertRaises(ValueError):
            log.info("not-a-channel", "boom")
        for ch in ("core", "scene", "assets", "render", "render3d", "audio", "input", "world", "ai",
                   "dialogue", "timeline", "save", "tools"):
            self.assertIn(ch, CHANNELS)

    def test_warn_once(self):
        log = Log(stream=io.StringIO())
        self.assertTrue(log.warn_once("audio", "missing:alarm", "missing optional sound"))
        self.assertFalse(log.warn_once("audio", "missing:alarm", "missing optional sound"))
        self.assertEqual(len(log.tail()), 1)

    def test_get_log_singleton(self):
        self.assertIs(get_log(), get_log())


class ServicesTests(unittest.TestCase):
    def test_register_get_errors(self):
        s = Services()
        s.register("clock", 1)
        self.assertEqual(s.get("clock"), 1)
        self.assertEqual(s.clock, 1)
        self.assertTrue(s.has("clock"))
        with self.assertRaises(ValueError):
            s.register("clock", 2)
        s.register("clock", 2, replace=True)
        self.assertEqual(s.names(), ["clock"])
        with self.assertRaises(ServiceMissing):
            s.get("audio")
        with self.assertRaises(AttributeError):
            _ = s._private


class SettingsTests(unittest.TestCase):
    def test_layering(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text(json.dumps({"width": 800, "seed": 5}), encoding="utf-8")
            s = Settings.load(p, env={"ACA_SEED": "9", "ACARISTAN_CUTSCENE3D": "0"}, overrides={"height": 10})
        self.assertEqual(s["width"], 800)
        self.assertEqual(s.source("width"), f"file:{p}")
        self.assertEqual(s["seed"], 9)                   # env beats file
        self.assertEqual(s.source("seed"), "env:ACA_SEED")
        self.assertIs(s["cutscene3d"], False)
        self.assertEqual(s["height"], 10)                 # cli beats all
        self.assertEqual(s["tile_size"], DEFAULTS["tile_size"])
        self.assertEqual(s.get("missing", 42), 42)

    def test_private_keys_ignored(self):
        s = Settings({"_secret": 1, "width": 3})
        self.assertIsNone(s.get("_secret"))
        self.assertEqual(s["width"], 3)


if __name__ == "__main__":
    unittest.main()
