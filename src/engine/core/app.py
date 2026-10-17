"""App: explicit boot / run / shutdown (§6.1). The only place that touches the display.

Phase 1 status: kernel only. ``boot()`` builds settings, log, services, clock
and rng, and opens the display. ``run_frames()`` drives a fixed-step loop for
tools and tests. The legacy game is not yet hosted here (LegacyGameScene is the
next step; see STATUS.md).
"""
from __future__ import annotations

from typing import Any, Callable

from .clock import Clock
from .config import Settings
from .errors import write_crash_report
from .events import EventBus
from .log import Log
from .profiling import Profiler
from .rng import LEGACY, LEGACY_RNG, RngStreams
from .services import Services

__all__ = ["App"]

_CURRENT: "App | None" = None


class App:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.log = Log()
        self.services = Services()
        self.clock = Clock(self.settings["step_hz"], self.settings["max_steps"])
        self.rng = RngStreams(self.settings["seed"])
        self.rng.adopt(LEGACY, LEGACY_RNG)   # legacy game code's stream; seeding unchanged
        self.events = EventBus()
        self.profiler = Profiler()
        self.screen = None
        self.booted = False
        self.exit_code: int | None = None

    @staticmethod
    def current() -> "App | None":
        """For tools and the debug console only. Game code receives services explicitly."""
        return _CURRENT

    def boot(self, open_display: bool = True, display_size: tuple[int, int] | None = None,
             display_flags: int = 0, force_mode: bool = False) -> "App":
        """Initialise pygame and open (or adopt) the display.

        ``force_mode=True`` always calls ``set_mode(display_size, display_flags)``.
        The legacy ``core.config`` uses it so its window is created exactly as
        before (ADAPTERS.md A-001). Otherwise an existing display surface is adopted.
        """
        global _CURRENT
        import os
        drv = self.settings.get("video_driver")
        if drv:
            os.environ["SDL_VIDEODRIVER"] = str(drv)   # chosen once, at boot (R7)
        import pygame
        pygame.init()
        for name, obj in (("settings", self.settings), ("log", self.log), ("clock", self.clock),
                          ("rng", self.rng), ("events", self.events), ("profiler", self.profiler)):
            self.services.register(name, obj, replace=True)
        if open_display:
            size = tuple(display_size or (self.settings["width"], self.settings["height"]))
            surf = None if force_mode else pygame.display.get_surface()
            self.screen = surf or pygame.display.set_mode(size, display_flags)
            pygame.display.set_caption(self.settings["window_title"])
            self.services.register("screen", self.screen, replace=True)
        self.booted = True
        _CURRENT = self
        # Anchor the frame-coherent wall clock to the OS clocks at boot (B-001):
        # legacy reads keep their scale (ms since pygame init, epoch seconds).
        import time as _time
        self.clock.set_wall_origin(pygame.time.get_ticks(), _time.time())
        self.log.info("core", f"booted (driver={drv or 'default'}, seed={self.rng.master_seed}, "
                              f"step={self.clock.step_hz} Hz)")
        return self

    def run_frames(self, frame_dts: list[float], fixed_update: Callable[["App", float], Any],
                   draw: Callable[["App", float], Any] | None = None) -> int:
        """Drive the fixed-step loop over given real frame durations (tests/tools)."""
        try:
            for real_dt in frame_dts:
                for dt in self.clock.steps(real_dt):
                    fixed_update(self, dt)
                    self.events.flush()
                if draw is not None:
                    draw(self, self.clock.alpha)
                if self.exit_code is not None:
                    break
        except Exception as e:
            self.crash(e)
            raise
        return self.exit_code or 0

    def run_scene(self, scene: Any) -> int:
        """Host a frame-driven scene until ``scene.done`` (or ``quit()``).

        The scene owns its own timing for now (the legacy loop still calls
        ``clock.tick``). On an uncaught exception a crash report is written,
        then the exception propagates unchanged. ``SystemExit`` and
        ``KeyboardInterrupt`` pass straight through.
        """
        self.services.register("scene", scene, replace=True)
        try:
            while not scene.done and self.exit_code is None:
                scene.frame()
        except Exception as e:
            try:
                self.crash(e)
            except Exception:
                pass   # never mask the real error with a reporting failure
            raise
        return self.exit_code or 0

    def crash(self, exc: BaseException):
        extra = {"seed": self.rng.master_seed, "frame": self.clock.frame,
                 "sim_time": round(self.clock.sim_time, 4), "services": self.services.names()}
        path = write_crash_report(self.settings["crash_dir"], exc, log_lines=self.log.tail(200),
                                  extra=extra, screenshot=self.screen)
        self.log.error("core", f"crash report written: {path}")
        return path

    def set_screen(self, surface) -> None:
        """Re-point the screen service after a legacy display-mode change (A-001)."""
        self.screen = surface
        self.services.register("screen", surface, replace=True)

    def quit(self, code: int = 0) -> None:
        self.exit_code = code

    def shutdown(self) -> None:
        global _CURRENT
        if self.booted:
            import pygame
            pygame.quit()
        self.booted = False
        if _CURRENT is self:
            _CURRENT = None
