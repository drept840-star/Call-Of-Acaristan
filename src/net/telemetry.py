"""Lightweight client-side telemetry for arena matches.

The values describe what this client observes, not an authoritative network
loss measurement. TCP repairs lost segments, so ``snapshot_gaps`` means that
expected simulation snapshots were absent from the application stream; it is
not a raw packet-loss percentage.
"""

import time
from collections import deque


class NetworkTelemetry(object):
    """Track ping, jitter, snapshot cadence, and input volume for one client."""

    PING_INTERVAL = 2.0
    PING_TIMEOUT = 10.0
    SNAPSHOT_EVERY = 3

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._nonce = 0
        self._pending = {}
        self._last_ping = None
        self._rtt = None
        self._jitter = None
        self._last_rtt_sample = None
        self._last_pong_at = None
        self._last_snapshot_tick = None
        self._last_snapshot_at = None
        self._snapshot_samples = deque(maxlen=32)
        self.snapshots_received = 0
        self.snapshot_gaps = 0
        self.inputs_sent = 0
        self.pongs_received = 0

    def ping_due(self, now=None):
        now = self._clock() if now is None else float(now)
        return self._last_ping is None or now - self._last_ping >= self.PING_INTERVAL

    def begin_ping(self, now=None):
        """Return a fresh uint32 nonce and remember its send time."""
        now = self._clock() if now is None else float(now)
        nonce = self._nonce
        self._nonce = (self._nonce + 1) & 0xFFFFFFFF
        self._pending[nonce] = now
        self._last_ping = now
        # Bound memory if a host stops answering without closing the socket.
        while len(self._pending) > 8:
            del self._pending[next(iter(self._pending))]
        for key, sent in list(self._pending.items()):
            if now - sent > self.PING_TIMEOUT:
                del self._pending[key]
        return nonce

    def accept_pong(self, nonce, now=None):
        """Record a matching pong. Returns False for stale/unknown responses."""
        now = self._clock() if now is None else float(now)
        sent = self._pending.pop(nonce, None)
        if sent is None or now < sent:
            return False
        sample = max(0.0, (now - sent) * 1000.0)
        if self._rtt is None:
            self._rtt = sample
        else:
            self._rtt = self._rtt * 0.8 + sample * 0.2
        if self._last_rtt_sample is not None:
            delta = abs(sample - self._last_rtt_sample)
            self._jitter = delta if self._jitter is None else self._jitter * 0.8 + delta * 0.2
        else:
            self._jitter = 0.0
        self._last_rtt_sample = sample
        self._last_pong_at = now
        self.pongs_received += 1
        return True

    def note_input(self):
        self.inputs_sent += 1

    def note_snapshot(self, tick, now=None):
        """Record a valid snapshot tick and count missing cadence slots."""
        now = self._clock() if now is None else float(now)
        tick = int(tick) & 0xFFFFFFFF
        if self._last_snapshot_tick is not None:
            delta = (tick - self._last_snapshot_tick) & 0xFFFFFFFF
            # Ignore duplicate or stale/out-of-order ticks. A forward jump
            # larger than half the sequence space is interpreted as old data.
            if 0 < delta < 0x80000000:
                cadence_steps = delta // self.SNAPSHOT_EVERY
                if cadence_steps > 1:
                    self.snapshot_gaps += cadence_steps - 1
                self._snapshot_samples.append((now, tick))
            elif delta == 0:
                return False
            else:
                return False
        else:
            self._snapshot_samples.append((now, tick))
        self._last_snapshot_tick = tick
        self._last_snapshot_at = now
        self.snapshots_received += 1
        return True

    def stats(self, now=None):
        now = self._clock() if now is None else float(now)
        age = None if self._last_snapshot_at is None else max(
            0.0, (now - self._last_snapshot_at) * 1000.0)
        samples = list(self._snapshot_samples)
        snapshot_hz = None
        if len(samples) >= 2 and samples[-1][0] > samples[0][0]:
            snapshot_hz = round((len(samples) - 1) /
                                (samples[-1][0] - samples[0][0]), 1)
        return {
            "rtt_ms": None if self._rtt is None else round(self._rtt, 1),
            "snapshot_hz": snapshot_hz,
            "jitter_ms": None if self._jitter is None else round(self._jitter, 1),
            "snapshot_age_ms": None if age is None else round(age, 1),
            "snapshots_received": self.snapshots_received,
            "snapshot_gaps": self.snapshot_gaps,
            "inputs_sent": self.inputs_sent,
            "pongs_received": self.pongs_received,
            "quality": self.quality(now),
        }

    def quality(self, now=None):
        """Coarse display category; ``unknown`` until a pong has arrived."""
        if self._rtt is None:
            return "unknown"
        if now is None:
            now = self._clock()
        if self._last_pong_at is None or now - self._last_pong_at > 6.0:
            return "poor"
        if self._rtt <= 100.0 and (self._jitter or 0.0) <= 25.0:
            return "good"
        if self._rtt <= 200.0 and (self._jitter or 0.0) <= 60.0:
            return "fair"
        return "poor"
