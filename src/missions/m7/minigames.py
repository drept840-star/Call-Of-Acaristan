"""Mission 7 farm minigames.

Generator:
    Tap E three times to prime.
    Hold E to pull the cord.
    Release inside the green band to build engine momentum.
    Strong, accurate pulls start the engine in about three pulls.
    Misses are recoverable, and repeated misses widen the useful band.

Tractor:
    Hold the displayed direction to accelerate along a manoeuvre.
    Release to coast.
    Hold Space or E to brake.
    Arrive slowly for a smooth stop.
    At the final position, hold Space or E to set the handbrake.

These state machines emit sound events but never access the audio manager.
Animation and simulation use elapsed time, not frame counts.
"""

import math

import pygame

from core.config import WIDTH, font_prompt, font_terminal_small
from engine.core import now_ms as _now_ms

from . import maps as M


CREAM = (238, 228, 198)
DIM = (148, 140, 120)
AMBER = (232, 196, 104)
GREEN = (142, 196, 120)
RED = (206, 86, 66)
BLUE = (122, 172, 183)
PANEL = (30, 26, 22)
TRACK = (52, 44, 36)

CARD_W = min(540, WIDTH - 32)
CARD_H = 190


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def card_rect():
    return pygame.Rect((WIDTH - CARD_W) // 2, 56, CARD_W, CARD_H)


def _text(surface, font, text, color, position, anchor="topleft"):
    image = font.render(text, True, color)
    surface.blit(image, image.get_rect(**{anchor: position}))


def _fit_text(surface, font, text, color, rect, anchor="topleft"):
    """Clip text to its allotted space without changing the font."""
    old_clip = surface.get_clip()
    surface.set_clip(old_clip.clip(rect))
    position = getattr(rect, anchor)
    _text(surface, font, text, color, position, anchor)
    surface.set_clip(old_clip)


def _frame(surface, rect, title, edge, subtitle=""):
    shade = pygame.Surface(rect.size, pygame.SRCALPHA)
    shade.fill((0, 0, 0, 100))
    surface.blit(shade, (rect.x + 5, rect.y + 5))

    pygame.draw.rect(surface, PANEL, rect)
    pygame.draw.rect(surface, edge, rect, 2)
    surface.fill(M.WOOD_D, (rect.x + 2, rect.y + 2, rect.w - 4, 23))
    surface.fill(M.WOOD, (rect.x + 2, rect.y + 24, rect.w - 4, 1))

    _text(surface, font_terminal_small, title, CREAM, (rect.x + 12, rect.y + 5))
    if subtitle:
        _text(
            surface, font_terminal_small, subtitle, AMBER,
            (rect.right - 12, rect.y + 5), "topright"
        )

    for x in (rect.x + 5, rect.right - 7):
        for y in (rect.y + 5, rect.bottom - 7):
            surface.fill((106, 96, 73), (x, y, 2, 2))


def _key_cap(surface, x, y, label, held=False):
    width = max(28, font_prompt.size(label)[0] + 12)
    cap = pygame.Rect(x, y, width, 25)
    pygame.draw.rect(surface, (69, 64, 44) if held else (24, 22, 20), cap)
    pygame.draw.rect(surface, AMBER if held else (176, 168, 148), cap, 1)
    _text(surface, font_prompt, label, CREAM, cap.center, "center")
    return cap.w


def _meter(surface, rect, value, color, segments=0):
    pygame.draw.rect(surface, TRACK, rect)
    amount = int(max(0, rect.w - 4) * _clamp(value))
    if amount:
        pygame.draw.rect(
            surface, color,
            (rect.x + 2, rect.y + 2, amount, max(1, rect.h - 4))
        )
    if segments:
        for i in range(1, segments):
            xx = rect.x + int(rect.w * i / segments)
            pygame.draw.line(surface, PANEL, (xx, rect.y + 1), (xx, rect.bottom - 2), 2)
    pygame.draw.rect(surface, (108, 95, 72), rect, 1)


def _pips(surface, x, y, filled, total, color=AMBER):
    for i in range(total):
        box = pygame.Rect(x + i * 20, y, 14, 14)
        pygame.draw.rect(surface, TRACK, box)
        pygame.draw.rect(surface, (100, 88, 66), box, 1)
        if i < filled:
            pygame.draw.rect(surface, color, box.inflate(-4, -4))


def _feedback(surface, rect, text, color):
    box = pygame.Rect(rect.x + 14, rect.bottom - 25, rect.w - 28, 18)
    _fit_text(surface, font_terminal_small, text, color, box, "midtop")


# -- generator -------------------------------------------------------------

class GenPuzzle:
    """A forgiving physical pull-cord toy, rather than a moving-marker QTE."""

    PRIME_TAPS = 3
    PULLS = 5  # Used by optional world/UI momentum pips.

    PULL_TIME_MS = 1050
    BASE_BAND = (0.57, 0.83)
    PERFECT_HALF_WIDTH = 0.055
    RECOIL_MS = 340
    KICKBACK_MS = 520

    def __init__(self, now=None):
        now = _now_ms() if now is None else now

        self.phase = "prime"
        self.prime = 0
        self.pull = 0
        self.comp = 0.0
        self.tries = 0
        self.streak = 0
        self.perfects = 0

        self.t = now
        self.last_update = now
        self.last_pull = now
        self.pull_started = now
        self.recoil_started = now
        self.recoil_from = 0.0
        self.ready_at = now

        self.holding = False
        self.held = False
        self.wait_release = True  # Opening interaction must not prime the bulb.
        self.locked_band = None

        self.flash = 0.0
        self.feedback = "Release E, then tap it three times."
        self.feedback_color = DIM
        self.events = []
        self.done = False

    def band(self):
        if self.phase not in ("crank", "run"):
            return None
        if self.locked_band is not None:
            return self.locked_band

        # Small mechanical variation, not a twitching target.
        shift = (0.0, 0.035, -0.025, 0.015)[self.pull % 4]
        assist = min(0.085, self.tries * 0.017)
        low = self.BASE_BAND[0] + shift - assist
        high = self.BASE_BAND[1] + shift + assist
        return max(0.40, low), min(0.94, high)

    def strength(self, now):
        if not self.holding:
            return 0.0
        return _clamp((now - self.pull_started) / float(self.PULL_TIME_MS))

    def extension(self, now):
        if self.holding:
            return self.strength(now)
        elapsed = max(0, now - self.recoil_started)
        recoil = _clamp(1.0 - elapsed / float(self.RECOIL_MS))
        return self.recoil_from * recoil * recoil

    def sweep(self, now):
        """Compatibility helper: the displayed marker is now cord extension."""
        return self.extension(now)

    def _message(self, text, color, flash):
        self.feedback = text
        self.feedback_color = color
        self.flash = flash

    def _prime(self, now):
        self.prime += 1
        self.events.append("prime")
        self.t = now
        self.flash = 0.6
        self.feedback_color = AMBER

        if self.prime >= self.PRIME_TAPS:
            self.phase = "crank"
            self.ready_at = now + 180
            self.last_pull = now
            self.events.append("primed")
            self._message("Primed. Hold E, then release in the green.", GREEN, 0.8)
        else:
            remaining = self.PRIME_TAPS - self.prime
            self.feedback = "%d more pump%s." % (remaining, "" if remaining == 1 else "s")

    def _begin_pull(self, now):
        if now < self.ready_at:
            return
        self.locked_band = self.band()
        self.holding = True
        self.pull_started = now
        self.events.append("cord")
        self.feedback = "Pulling... release in the green!"
        self.feedback_color = AMBER

    def _end_pull(self, now, kickback=False):
        if not self.holding:
            return

        strength = self.strength(now)
        low, high = self.locked_band
        center = (low + high) * 0.5
        self.holding = False
        self.recoil_started = now
        self.recoil_from = strength
        self.last_pull = now
        self.locked_band = None
        self.pull += 1

        if kickback or strength > high:
            self.comp = max(0.0, self.comp - 0.065)
            self.tries += 1
            self.streak = 0
            self.ready_at = now + self.KICKBACK_MS
            self.events.append("pull_miss")
            self._message("KICKBACK! Release a little earlier.", RED, -1.0)

        elif strength < low:
            self.tries += 1
            self.streak = 0
            self.ready_at = now + self.RECOIL_MS

            # A nearly-good pull still contributes a little.
            if strength >= low * 0.70:
                self.comp = min(0.95, self.comp + 0.09)
                message = "It coughed! Pull a little farther."
            else:
                message = "Too gentle. Hold E a little longer."

            self.events.append("pull_weak")
            self._message(message, AMBER, -0.35)

        else:
            error = abs(strength - center)
            perfect = error <= self.PERFECT_HALF_WIDTH
            quality = 1.0 - _clamp(error / max(0.01, (high - low) * 0.5))
            self.streak += 1

            gain = 0.29 + quality * 0.08 + min(0.04, (self.streak - 1) * 0.02)
            self.comp = min(1.0, self.comp + gain)
            self.ready_at = now + self.RECOIL_MS
            self.events.append("pull_ok")

            if perfect:
                self.perfects += 1
                message = "BEAUTIFUL PULL! Keep her turning."
            elif self.comp > 0.72:
                message = "Almost there! One more good pull."
            else:
                message = "Good pull! The engine is waking up."

            self._message(message, GREEN, 1.0)

            if self.comp >= 0.999:
                self.phase = "run"
                self.comp = 1.0
                self.done = True
                self.events.append("run")
                self._message("SHE'S ALIVE!", GREEN, 1.0)

    def update(self, now):
        elapsed = max(0, now - self.last_update)
        dt = elapsed / 1000.0
        self.last_update = now

        self.flash *= math.exp(-5.0 * dt)
        if abs(self.flash) < 0.02:
            self.flash = 0.0

        if self.done:
            return self.events

        if self.phase == "crank":
            if self.holding and now - self.pull_started >= self.PULL_TIME_MS:
                self._end_pull(now, kickback=True)
                self.wait_release = True

            # Momentum only leaks after a generous thinking/resting period.
            # Priming never resets, and there is no terminal failure state.
            if not self.holding:
                decay_start = max(self.last_pull + 4000, now - elapsed)
                decay_seconds = max(0.0, (now - decay_start) / 1000.0)
                self.comp = max(0.0, self.comp - decay_seconds * 0.018)

        return self.events

    def set_input(self, held, now):
        self.update(now)
        held = bool(held)

        if self.done:
            self.held = held
            return self.events

        if self.wait_release:
            self.held = held
            if not held:
                self.wait_release = False
                if self.phase == "prime":
                    self.feedback = "Tap E three times to fill the fuel bulb."
            return self.events

        pressed = held and not self.held
        released = self.held and not held
        self.held = held

        if self.phase == "prime":
            if pressed:
                self._prime(now)
        elif self.phase == "crank":
            if released and self.holding:
                self._end_pull(now)

            # A held button can start once recoil finishes; no lost inputs.
            if held and not self.holding and now >= self.ready_at:
                self._begin_pull(now)

        return self.events

    def press(self, now):
        """Optional discrete-input adapter.

        Prime: one call pumps the bulb.
        Crank: alternate calls start and release the cord.
        The farmyard uses set_input() for actual hold/release input.
        """
        self.update(now)
        self.wait_release = False
        if self.done:
            return self.events
        if self.phase == "prime":
            self._prime(now)
        elif self.holding:
            self._end_pull(now)
        else:
            self._begin_pull(now)
        return self.events

    def take_events(self):
        events = self.events
        self.events = []
        return events


# -- tractor ---------------------------------------------------------------

class TractorPuzzle:
    """Guided route with throttle, inertia, braking and graded stops.

    The map provides the same route tuples as before:
        x0, y0, x1, y1, angle0, angle1, key, label

    Progress follows that safe route. The player controls its speed.
    There are no timeouts and no route resets.
    """

    ACCELERATION = 1.45
    COAST_DECELERATION = 1.55
    BRAKE_DECELERATION = 3.3
    MAX_SPEED = 1.0
    SMOOTH_SPEED = 0.52
    STALL_MS = 650
    STOP_MS = 380
    HANDBRAKE_SECONDS = 0.75

    def __init__(self, route, now=None):
        self.route = tuple(tuple(step) for step in route)
        if not self.route:
            raise ValueError("Tractor route must contain at least one step.")
        if any(len(step) != 8 for step in self.route):
            raise ValueError("Each tractor route step must contain eight values.")
        if any(step[6] not in ("w", "a", "s", "d") for step in self.route):
            raise ValueError("Tractor route controls must be w, a, s or d.")

        now = _now_ms() if now is None else now
        self.i = 0
        self.state = "prompt"
        self.t = now
        self.last_update = now
        self.progress = 0.0
        self.speed = 0.0
        self.brake_progress = 0.0
        self.held = set()
        self.braking = False
        self.park_armed = False

        self.tries = 0
        self.smooth = 0
        self.clean = False
        self.flash = 0.0
        self.feedback = "Hold the shown direction. Release to coast."
        self.feedback_color = DIM
        self.events = []
        self.done = False

    def step(self):
        return self.route[min(self.i, len(self.route) - 1)]

    @property
    def duration(self):
        x0, y0, x1, y1, a0, a1, *_ = self.step()
        distance = math.hypot(x1 - x0, y1 - y0)
        # Long enough to feel the machine's weight without crawling.
        return max(1100, int(distance / 105.0 * 1000), int(abs(a1 - a0) * 11))

    def pose(self, now):
        x0, y0, x1, y1, a0, a1, _, _ = self.step()
        u = _clamp(self.progress)
        angle_u = u * u * (3.0 - 2.0 * u)
        return (
            x0 + (x1 - x0) * u,
            y0 + (y1 - y0) * u,
            a0 + (a1 - a0) * angle_u,
        )

    def window(self, now):
        """Compatibility helper; there is deliberately no prompt countdown."""
        return 1.0 if self.state == "prompt" else 0.0

    def _stall(self, now):
        self.state = "stall"
        self.t = now
        self.speed = 0.0
        self.tries += 1
        self.flash = -1.0
        self.feedback = "Wrong gear. Let go, then use the shown control."
        self.feedback_color = RED
        self.events.append("stall")

    def _arrive(self, now):
        self.clean = self.speed <= self.SMOOTH_SPEED
        self.progress = 1.0
        self.speed = 0.0
        self.t = now
        self.events.append("arrive")

        if self.clean:
            self.smooth += 1
            self.flash = 1.0
            self.feedback = "SMOOTH STOP. Bodi would approve."
            self.feedback_color = GREEN
            self.events.append("smooth")
        else:
            self.flash = -0.35
            self.feedback = "A bit lurchy! Ease off earlier next time."
            self.feedback_color = AMBER
            self.events.append("bump")

        if self.i == len(self.route) - 1:
            self.state = "park"
            self.park_armed = False
            self.brake_progress = 0.0
        else:
            self.state = "settle"

    def _next_step(self, now):
        self.i += 1
        self.progress = 0.0
        self.speed = 0.0
        self.state = "prompt"
        self.t = now

    def _tick(self, now, dt):
        self.flash *= math.exp(-5.5 * dt)
        if abs(self.flash) < 0.02:
            self.flash = 0.0

        if self.done:
            return

        if self.state == "stall":
            if now - self.t >= self.STALL_MS and not self.held:
                self.state = "prompt"
                self.t = now
            return

        if self.state == "settle":
            if now - self.t >= self.STOP_MS:
                self._next_step(now)
            return

        if self.state == "park":
            self.speed = 0.0

            # Require a deliberate brake press, not a carried-over hold.
            if not self.braking:
                self.park_armed = True

            if self.park_armed and self.braking:
                self.brake_progress = min(
                    1.0, self.brake_progress + dt / self.HANDBRAKE_SECONDS
                )
            else:
                self.brake_progress = max(0.0, self.brake_progress - dt * 1.5)

            if self.brake_progress >= 1.0:
                self.done = True
                self.state = "done"
                self.flash = 1.0
                self.feedback = "PARKED. That should stop a truck."
                self.feedback_color = GREEN
                self.events.append("park")
            return

        expected = self.step()[6]
        throttle = expected in self.held and not self.braking

        if self.state == "prompt":
            if self.braking:
                return
            if throttle:
                self.state = "drive"
                self.t = now
                self.events.append("drive")
            elif self.held:
                self._stall(now)
                return
            else:
                return

        if self.state != "drive":
            return

        # Wrong controls while moving don't teleport/reset the tractor.
        # They simply stop supplying power.
        old_speed = self.speed
        if self.braking:
            self.speed = max(0.0, self.speed - self.BRAKE_DECELERATION * dt)
        elif throttle:
            self.speed = min(self.MAX_SPEED, self.speed + self.ACCELERATION * dt)
        else:
            self.speed = max(0.0, self.speed - self.COAST_DECELERATION * dt)

        distance = (old_speed + self.speed) * 0.5 * dt
        self.progress += distance / (self.duration / 1000.0)

        if self.progress >= 1.0:
            self._arrive(now)

    def update(self, now):
        # Use small simulation steps so stops grade consistently at low FPS.
        elapsed_ms = max(0, now - self.last_update)
        start = self.last_update
        self.last_update = now

        # Do not simulate seconds of unattended driving after a debugger stall.
        remaining = min(elapsed_ms, 150)
        simulation_time = now - remaining if elapsed_ms > 150 else start

        while remaining > 0:
            step_ms = min(remaining, 16)
            simulation_time += step_ms
            self._tick(simulation_time, step_ms / 1000.0)
            remaining -= step_ms

        return self.events

    def set_input(self, held, brake, now):
        # Advance using the previous input, then latch this frame's input.
        self.update(now)
        self.held = set(held)
        self.braking = bool(brake)

        # Zero-time tick makes newly pressed controls respond immediately.
        self._tick(now, 0.0)
        return self.events

    def press(self, now, key):
        """Compatibility adapter: latch one direction until set_input changes it."""
        return self.set_input({key}, False, now)

    def take_events(self):
        events = self.events
        self.events = []
        return events


# -- generator card --------------------------------------------------------

def _draw_fuel_bulb(surface, rect, puzzle, now):
    cx, cy = rect.right - 62, rect.y + 83
    squeeze = 3 if now - puzzle.t < 120 and puzzle.prime else 0

    pygame.draw.line(
        surface, (138, 117, 73),
        (cx - 32, cy + 4), (cx - 16, cy + 4), 4
    )
    pygame.draw.line(
        surface, (138, 117, 73),
        (cx + 16, cy + 4), (cx + 30, cy + 4), 4
    )

    bulb = pygame.Rect(cx - 18, cy - 17 + squeeze, 36, 36 - squeeze * 2)
    pygame.draw.ellipse(surface, M.INK, bulb.inflate(4, 4))
    pygame.draw.ellipse(surface, (81, 70, 48), bulb)

    fill = puzzle.prime / float(puzzle.PRIME_TAPS)
    inner = bulb.inflate(-8, -8)
    old_clip = surface.get_clip()
    fuel_clip = pygame.Rect(
        inner.x, inner.bottom - int(inner.h * fill),
        inner.w, int(inner.h * fill)
    )
    surface.set_clip(old_clip.clip(fuel_clip))
    pygame.draw.ellipse(surface, AMBER, inner)
    surface.set_clip(old_clip)
    pygame.draw.arc(surface, (202, 181, 126), bulb.inflate(-7, -7), 1.1, 2.5, 2)


def _draw_cord(surface, rect, puzzle, now):
    start_x = rect.x + 25
    end_x = rect.right - 29
    y = rect.y + 68
    extension = puzzle.extension(now)
    handle_x = start_x + 32 + int(extension * max(1, end_x - start_x - 32))

    pygame.draw.circle(surface, M.INK, (start_x, y), 15)
    pygame.draw.circle(surface, (92, 88, 72), (start_x, y), 11)
    pygame.draw.circle(surface, M.METAL_D, (start_x, y), 7)

    angle = extension * math.tau * 2
    pygame.draw.line(
        surface, AMBER,
        (start_x, y),
        (start_x + int(math.cos(angle) * 8), y + int(math.sin(angle) * 8)),
        2,
    )
    pygame.draw.line(
        surface, (202, 185, 137),
        (start_x + 14, y), (handle_x, y), 2
    )
    pygame.draw.rect(surface, M.INK, (handle_x - 4, y - 10, 9, 20))
    pygame.draw.rect(surface, (137, 92, 53), (handle_x - 2, y - 8, 5, 16))
    pygame.draw.rect(surface, (184, 131, 74), (handle_x - 2, y - 8, 2, 16))


def draw_generator(surface, puzzle, now):
    rect = card_rect()
    edge = GREEN if puzzle.flash > 0.2 else RED if puzzle.flash < -0.2 else M.WOOD_L
    subtitle = "1 / 2  PRIME" if puzzle.phase == "prime" else "2 / 2  PULL"
    _frame(surface, rect, "GENERATOR", edge, subtitle)

    if puzzle.phase == "prime":
        _key_cap(surface, rect.x + 16, rect.y + 39, "E", puzzle.held)
        _text(
            surface, font_terminal_small, "TAP TO PRIME",
            CREAM, (rect.x + 58, rect.y + 45)
        )
        _text(
            surface, font_terminal_small, "Three pumps of the fuel bulb.",
            DIM, (rect.x + 16, rect.y + 78)
        )
        _pips(
            surface, rect.x + 18, rect.y + 108,
            puzzle.prime, puzzle.PRIME_TAPS, AMBER
        )
        _text(
            surface, font_terminal_small, "FUEL",
            DIM, (rect.x + 94, rect.y + 108)
        )
        _draw_fuel_bulb(surface, rect, puzzle, now)

        _text(
            surface, font_terminal_small, "Next: hold E and release the pull cord.",
            DIM, (rect.x + 16, rect.y + 140)
        )
    else:
        _key_cap(surface, rect.x + 16, rect.y + 32, "E", puzzle.held)
        _text(
            surface, font_terminal_small, "HOLD TO PULL - RELEASE IN GREEN",
            CREAM, (rect.x + 58, rect.y + 37)
        )

        _draw_cord(surface, rect, puzzle, now)

        bar = pygame.Rect(rect.x + 18, rect.y + 91, rect.w - 36, 17)
        pygame.draw.rect(surface, TRACK, bar)
        low, high = puzzle.band()

        useful = pygame.Rect(
            bar.x + int(low * bar.w),
            bar.y + 1,
            max(2, int((high - low) * bar.w)),
            bar.h - 2,
        )
        pygame.draw.rect(surface, (81, 119, 66), useful)
        pygame.draw.rect(surface, GREEN, useful, 1)

        center = (low + high) * 0.5
        perfect = pygame.Rect(
            bar.x + int((center - puzzle.PERFECT_HALF_WIDTH) * bar.w),
            bar.y + 2,
            max(2, int(puzzle.PERFECT_HALF_WIDTH * 2 * bar.w)),
            bar.h - 4,
        )
        pygame.draw.rect(surface, (199, 222, 139), perfect)

        strength = puzzle.extension(now)
        marker_x = bar.x + int(strength * (bar.w - 4))
        marker_color = CREAM
        if puzzle.holding:
            marker_color = GREEN if low <= strength <= high else RED if strength > high else AMBER
        pygame.draw.rect(surface, marker_color, (marker_x, bar.y - 3, 4, bar.h + 6))
        pygame.draw.rect(surface, (108, 95, 72), bar, 1)

        _text(
            surface, font_terminal_small, "GENTLE",
            DIM, (bar.left, rect.y + 113)
        )
        _text(
            surface, font_terminal_small, "KICKBACK",
            DIM, (bar.right, rect.y + 113), "topright"
        )
        if puzzle.holding and low <= strength <= high:
            _text(
                surface, font_terminal_small, "RELEASE!",
                GREEN, (bar.centerx, rect.y + 113), "midtop"
            )

        _text(
            surface, font_terminal_small, "ENGINE",
            DIM, (rect.x + 18, rect.y + 140)
        )
        momentum = pygame.Rect(rect.x + 92, rect.y + 140, rect.w - 112, 13)
        _meter(surface, momentum, puzzle.comp, GREEN, segments=5)

    _feedback(surface, rect, puzzle.feedback, puzzle.feedback_color)


# -- tractor card ----------------------------------------------------------

def _draw_speed_gauge(surface, rect, speed):
    center = (rect.right - 50, rect.y + 88)
    radius = 26

    pygame.draw.circle(surface, M.INK, center, radius + 3)
    pygame.draw.circle(surface, TRACK, center, radius)
    for i in range(7):
        angle = math.radians(150 + i * 40)
        inner = (
            center[0] + int(math.cos(angle) * 19),
            center[1] + int(math.sin(angle) * 19),
        )
        outer = (
            center[0] + int(math.cos(angle) * 23),
            center[1] + int(math.sin(angle) * 23),
        )
        pygame.draw.line(surface, GREEN if i < 3 else AMBER, inner, outer, 2)

    angle = math.radians(150 + _clamp(speed) * 240)
    endpoint = (
        center[0] + int(math.cos(angle) * 18),
        center[1] + int(math.sin(angle) * 18),
    )
    pygame.draw.line(surface, CREAM, center, endpoint, 2)
    pygame.draw.circle(surface, AMBER, center, 3)
    _text(
        surface, font_terminal_small, "SPEED",
        DIM, (center[0], center[1] + 30), "midtop"
    )


def draw_tractor(surface, puzzle, now):
    rect = card_rect()
    edge = GREEN if puzzle.flash > 0.2 else RED if puzzle.flash < -0.2 else M.WOOD_L
    total = len(puzzle.route)
    subtitle = "%d / %d" % (puzzle.i + 1, total)
    _frame(surface, rect, "TRACTOR", edge, subtitle)

    step = puzzle.step()
    label_rect = pygame.Rect(rect.x + 16, rect.y + 32, rect.w - 32, 22)
    _fit_text(surface, font_terminal_small, step[7], CREAM, label_rect)

    if puzzle.state == "park":
        _key_cap(surface, rect.x + 16, rect.y + 64, "SPACE", puzzle.braking)
        _text(
            surface, font_terminal_small, "HOLD TO SET THE HANDBRAKE",
            CREAM, (rect.x + 104, rect.y + 69)
        )
        _text(
            surface, font_terminal_small, "E works too. Release first if held.",
            DIM, (rect.x + 16, rect.y + 103)
        )
        _meter(
            surface,
            pygame.Rect(rect.x + 16, rect.y + 132, rect.w - 32, 16),
            puzzle.brake_progress,
            GREEN,
        )
        _feedback(
            surface, rect,
            "%d/%d smooth stops. Now make it stay put." % (puzzle.smooth, total),
            AMBER,
        )
        return

    if puzzle.state == "done":
        _text(
            surface, font_prompt, "PARKED",
            GREEN, (rect.centerx, rect.y + 80), "midtop"
        )
        _feedback(surface, rect, puzzle.feedback, GREEN)
        return

    expected = step[6]
    _key_cap(
        surface, rect.x + 16, rect.y + 61,
        expected.upper(), expected in puzzle.held and not puzzle.braking,
    )
    _text(
        surface, font_terminal_small, "HOLD TO DRIVE",
        CREAM, (rect.x + 58, rect.y + 67)
    )
    _text(
        surface, font_terminal_small, "Release: coast",
        DIM, (rect.x + 16, rect.y + 97)
    )
    _text(
        surface, font_terminal_small, "Space / E: brake",
        DIM, (rect.x + 16, rect.y + 117)
    )
    _draw_speed_gauge(surface, rect, puzzle.speed)

    route_bar = pygame.Rect(rect.x + 16, rect.y + 143, rect.w - 32, 12)
    pygame.draw.rect(surface, TRACK, route_bar)

    # Last 22% is a visual braking hint, not another timed target.
    slow_zone = pygame.Rect(
        route_bar.x + int(route_bar.w * 0.78),
        route_bar.y,
        max(1, int(route_bar.w * 0.22)),
        route_bar.h,
    )
    pygame.draw.rect(surface, (81, 105, 61), slow_zone)

    fill = int(route_bar.w * _clamp(puzzle.progress))
    if fill:
        pygame.draw.rect(
            surface, M.TRACTOR,
            (route_bar.x, route_bar.y + 2, fill, route_bar.h - 4)
        )

    pygame.draw.rect(surface, (108, 95, 72), route_bar, 1)
    marker = route_bar.x + int((route_bar.w - 3) * _clamp(puzzle.progress))
    pygame.draw.rect(surface, CREAM, (marker, route_bar.y - 2, 3, route_bar.h + 4))

    if puzzle.state == "stall":
        message, color = puzzle.feedback, RED
    elif puzzle.state == "settle":
        message, color = puzzle.feedback, puzzle.feedback_color
    elif puzzle.progress >= 0.78 and puzzle.speed > puzzle.SMOOTH_SPEED:
        message, color = "EASE OFF - aim for a gentle stop.", AMBER
    elif puzzle.state == "drive" and puzzle.speed < 0.03:
        message, color = "Hold %s to keep moving." % expected.upper(), DIM
    else:
        message = "No time limit. Slow stops earn a clean manoeuvre."
        color = DIM

    _feedback(surface, rect, message, color)
