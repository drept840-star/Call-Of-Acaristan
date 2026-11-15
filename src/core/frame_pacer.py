"""Frame pacing for the 60 Hz fixed-step loop.

The sim advances in whole 1/60 s steps and the renderer does not
interpolate, so a frame that does not span a whole number of steps judders:
a 28 ms 2.5D frame runs 2, 2, 1, 2, 1 steps and the world lurches. And
``pygame.time.Clock.tick(60)`` waits 16 ms (62.5 fps), which drops a step
every 25th frame even in 2D.

The pacer picks the smallest step count the recent frames fit in (60 or
30 fps, with hysteresis), sleeps to an absolute deadline and returns exactly
``n / 60`` s while it keeps up, so every frame runs the same number of steps.
A frame that overruns re-anchors and returns its real duration.
"""
import time

STEP = 1.0 / 60
MAX_N = 2           # never lock below 30 fps; slower frames run free on the accumulator
MARGIN = 0.001      # headroom a frame's work must leave inside its budget
LATE = 0.002        # a wake this far past the deadline counts as an overrun
UP = 6.0            # net over-budget frames (each in-budget one pays back half) before 30 fps
DOWN = 90           # net in-budget frames before climbing back
DOWN_COST = 3       # in-budget frames one over-budget frame takes back


class Pacer(object):
    def __init__(self, clock=time.perf_counter, sleep=time.sleep):
        self._clock, self._sleep = clock, sleep
        self.n = 1
        self._t = self._wake = clock()
        self._up = 0.0
        self._down = 0

    def _adapt(self, work):
        need = min(MAX_N, int((work + MARGIN) / STEP) + 1)
        if need > self.n:
            self._down = 0
            self._up += 1.0
            if self._up >= UP:
                self.n, self._up = self.n + 1, 0.0
            return
        self._up = max(0.0, self._up - 0.5)   # a lone spike every so often never drops the rate
        if need < self.n:
            self._down += 1
            if self._down >= DOWN:
                self.n, self._down = self.n - 1, 0
        else:
            # each over-budget frame costs three in-budget ones: a frame mix that
            # fits 60 fps ~90% of the time climbs back; a straight-run reset kept
            # it at 30 fps for good once a load spike dropped it
            self._down = max(0, self._down - DOWN_COST)

    def wait(self):
        """Once per frame, before the update: sleep until the frame is due and
        return its dt in seconds."""
        now = self._clock()
        self._adapt(now - self._wake)
        due = self._t + self.n * STEP
        if now < due:
            self._sleep(due - now)
            now = self._clock()
        if now - due > LATE:
            due = now
        dt, self._t, self._wake = due - self._t, due, now
        return dt
