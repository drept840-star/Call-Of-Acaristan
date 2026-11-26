"""Frame pacing for the 60 Hz fixed-step loop.

The sim advances in whole 1/60 s steps and the renderer does not
interpolate, so a frame that does not span a whole number of steps judders:
a 28 ms 2.5D frame runs 2, 2, 1, 2, 1 steps and the world lurches. And
``pygame.time.Clock.tick(60)`` waits 16 ms (62.5 fps), which drops a step
every 25th frame even in 2D.

The pacer holds a tight 60 fps when frames fit, lets moderate overruns
(~42-59 fps) run free on the accumulator instead of sleeping them down to
30 fps, and only locks to steady 30 fps (2 steps/frame) when sustained frame
times fall into the heavy <41 fps lurch zone, with hysteresis to climb back.
A frame that overruns re-anchors and returns its real duration.
"""
import time

STEP = 1.0 / 60
MAX_N = 2           # never lock below 30 fps; slower frames run free on the accumulator
MARGIN = 0.001      # headroom a frame's work must leave inside its budget
LATE = 0.002        # a wake this far past the deadline counts as an overrun
DROP_WORK = 0.0245  # ~41 fps: only lock to 30 fps once frames enter the heavy 2/1 judder zone
RECOVER_WORK = 0.0215  # ~46.5 fps: hysteresis threshold to climb back out of 30 fps
STALL_WORK = 0.25   # ignore OS stalls / scene loads / window drags in adaptation
SPIN_GUARD = 0.0015 # sleep up to 1.5 ms early and spin the tail for sub-ms wake accuracy
UP = 10.0           # net slow frames (each fast one pays back half) before 30 fps
DOWN = 30           # net fast frames (~1 s at 30 fps) before climbing back
DOWN_COST = 2       # fast frames one slow frame takes back

_REAL_CLOCK = time.perf_counter
_REAL_SLEEP = time.sleep


class Pacer(object):
    def __init__(self, clock=time.perf_counter, sleep=time.sleep):
        self._clock, self._sleep = clock, sleep
        self._precise = (clock is _REAL_CLOCK and sleep is _REAL_SLEEP)
        self.n = 1
        self._t = self._wake = clock()
        self._up = 0.0
        self._down = 0

    def _adapt(self, work):
        if work > STALL_WORK:
            return
        if self.n == 1:
            if work >= DROP_WORK and self.n < MAX_N:
                self._down = 0
                self._up += 1.0
                if self._up >= UP:
                    self.n, self._up = self.n + 1, 0.0
            else:
                # a lone spike every so often never drops the rate
                self._up = max(0.0, self._up - 0.5)
            return
        if work < RECOVER_WORK:
            self._up = 0.0
            self._down += 1
            if self._down >= DOWN:
                self.n, self._down = self.n - 1, 0
        elif work >= DROP_WORK:
            # each slow frame costs two fast ones: recovers quickly once load eases
            self._down = max(0, self._down - DOWN_COST)
        else:
            # inside the 41-46.5 fps hysteresis band: hold steady without flapping
            self._down = max(0, self._down - 1)

    def wait(self):
        """Once per frame, before the update: sleep until the frame is due and
        return its dt in seconds."""
        now = self._clock()
        self._adapt(now - self._wake)
        due = self._t + self.n * STEP
        if now < due:
            rem = due - now
            if self._precise:
                if rem > SPIN_GUARD:
                    self._sleep(rem - SPIN_GUARD)
                    now = self._clock()
                while now < due:
                    now = self._clock()
            else:
                self._sleep(rem)
                now = self._clock()
        if now - due > LATE:
            due = now
        dt, self._t, self._wake = due - self._t, due, now
        return dt
