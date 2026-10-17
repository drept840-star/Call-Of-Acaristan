"""engine.core.rng: named streams are independent, seeded, snapshot-able (R6, B-002)."""
from __future__ import annotations

import random
import unittest

from tests.unit import _helpers  # noqa: F401

from engine.core import LEGACY, LEGACY_RNG, RngStreams, derive_seed


class DeriveSeed(unittest.TestCase):
    def test_stable_and_distinct(self):
        self.assertEqual(derive_seed(0, "ai"), derive_seed(0, "ai"))
        self.assertNotEqual(derive_seed(0, "ai"), derive_seed(0, "fx"))
        self.assertNotEqual(derive_seed(0, "ai"), derive_seed(1, "ai"))

    def test_known_value(self):
        # Pins the derivation (sha256 of "master:name", first 8 bytes big-endian).
        # If this ever changes, every seeded replay changes with it (ADR-004/R6).
        import hashlib
        h = hashlib.sha256(b"7:world").digest()
        self.assertEqual(derive_seed(7, "world"), int.from_bytes(h[:8], "big"))


class Streams(unittest.TestCase):
    def test_same_name_same_object(self):
        r = RngStreams(1)
        self.assertIs(r.stream("ai"), r.stream("ai"))

    def test_streams_are_independent(self):
        """Adding a consumer to one stream never shifts another (the point of B-002)."""
        a = RngStreams(5)
        seq_a = [a.stream("ai").random() for _ in range(5)]
        b = RngStreams(5)
        b.stream("fx").random()          # extra consumer on a different stream
        b.stream("fx").random()
        seq_b = [b.stream("ai").random() for _ in range(5)]
        self.assertEqual(seq_a, seq_b)

    def test_master_seed_changes_sequences(self):
        a = [RngStreams(1).stream("ai").random() for _ in range(3)]
        b = [RngStreams(2).stream("ai").random() for _ in range(3)]
        self.assertNotEqual(a, b)

    def test_reseed_resets_derived_but_not_adopted(self):
        r = RngStreams(9)
        first = r.stream("ai").random()
        adopted = random.Random(123)
        r.adopt("legacy_test", adopted)
        adopted.random()
        state_before = adopted.getstate()
        r.reseed(9)
        self.assertEqual(r.stream("ai").random(), first)
        self.assertEqual(adopted.getstate(), state_before)   # untouched

    def test_snapshot_restore(self):
        r = RngStreams(3)
        r.stream("ai").random()
        snap = r.snapshot()
        expected = [r.stream("ai").random() for _ in range(4)]
        r.restore(snap)
        self.assertEqual([r.stream("ai").random() for _ in range(4)], expected)
        self.assertEqual(snap["master_seed"], 3)
        self.assertIn("ai", r.names())

    def test_legacy_stream_is_the_module_global(self):
        """LEGACY_RNG is the instance behind random.random(): legacy seeding unchanged (R2)."""
        self.assertIs(LEGACY_RNG, random._inst)  # type: ignore[attr-defined]
        state = random.getstate()
        try:
            random.seed(777)
            via_module = random.random()
            random.seed(777)
            via_stream = LEGACY_RNG.random()
            self.assertEqual(via_module, via_stream)
        finally:
            random.setstate(state)
        r = RngStreams(0)
        r.adopt(LEGACY, LEGACY_RNG)
        self.assertIs(r.stream(LEGACY), LEGACY_RNG)


if __name__ == "__main__":
    unittest.main()
