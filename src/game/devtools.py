"""RPE6 Phase 10 (§6.19): in-game debug tools.

F3 debug overlay (frame-time graph with spike markers, render-queue
stats, asset cache stats, entity count, scene stack, input context),
click-to-inspect entity panel (component dump + plain legacy attrs),
F4 collision view (solid tiles, colliders, LOS rays).  Everything here
is dev-only and inert unless toggled: the harness never presses F3/F4,
so gameplay parity is untouched.  The existing owner tools
(`core.console`, `core.level_editor`) are extended, not replaced
(see ADR-021).

Data builders (`frame_stats`, `describe`, `pick`) are pure reads and
unit-testable headless; only `draw` touches pixels.
"""
from __future__ import annotations

import collections
from typing import Any, Callable

import pygame

from core.config import WIDTH, HEIGHT, font_terminal_small
from core.state import STATE

__all__ = ["DEV", "DevTools", "FrameSamples"]

SPIKE_MS = 20.0


class FrameSamples:
    """Ring buffer of (total, sim, draw) frame times in milliseconds."""

    def __init__(self, capacity: int = 180):
        self.samples: collections.deque = collections.deque(maxlen=capacity)

    def push(self, total: float, sim: float = 0.0, draw: float = 0.0) -> None:
        self.samples.append((float(total), float(sim), float(draw)))

    def stats(self) -> dict:
        if not self.samples:
            return {"frames": 0, "avg": 0.0, "max": 0.0, "spikes": 0, "fps": 0.0,
                    "sim_avg": 0.0, "draw_avg": 0.0}
        totals = [s[0] for s in self.samples]
        avg = sum(totals) / len(totals)
        return {"frames": len(totals), "avg": avg, "max": max(totals),
                "spikes": sum(1 for t in totals if t > SPIKE_MS),
                "fps": (1000.0 / avg if avg > 0 else 0.0),
                "sim_avg": sum(s[1] for s in self.samples) / len(totals),
                "draw_avg": sum(s[2] for s in self.samples) / len(totals)}


def _plain_attrs(obj: Any, limit: int = 14) -> list[str]:
    out = []
    for k in sorted(vars(obj)):
        if k.startswith("__"):
            continue
        v = getattr(obj, k)
        if callable(v) or not isinstance(v, (int, float, str, bool, tuple, list)):
            continue
        r = repr(v)
        out.append(f"{k}={r[:36]}")
        if len(out) >= limit:
            break
    return out


class DevTools:
    def __init__(self):
        self.overlay = False        # F3
        self.collision = False      # F4
        self.level_view = False     # F5 (P10-M2 level viewer)
        self.timeline_view = False  # F6 (P10-M2 timeline panel)
        self._cutscene_fn: Callable[[], dict | None] | None = None
        self.frames = FrameSamples()
        self.selected: Any = None
        self._scene_stack_fn: Callable[[], list] | None = None
        self._state_fn: Callable[[], str] | None = None
        self._events_fn: Callable[[], list] | None = None
        self._prefab_library = None
        self._cache_fn: Callable[[], str] | None = None

    # -- app bindings -------------------------------------------------
    def bind(self, *, scene_stack=None, state_name=None, events=None, cache=None):
        self._scene_stack_fn = scene_stack or self._scene_stack_fn
        self._state_fn = state_name or self._state_fn
        self._events_fn = events or self._events_fn
        self._cache_fn = cache or getattr(self, "_cache_fn", None)

    def bind_cutscene(self, fn) -> None:
        self._cutscene_fn = fn

    def register_prefab_library(self, library) -> None:
        self._prefab_library = library

    # -- data ----------------------------------------------------------
    def entity_count(self) -> int:
        try:
            import game.world as gw
            if gw.installed():
                return gw.world().count()
        except Exception:
            pass
        return len(getattr(STATE, "enemies", []) or [])

    def render_stats_line(self) -> str:
        try:
            from game import render as _gr
            st = _gr.last_stats()
            return f"drawables={st.submitted} layers={len(st.layers)} custom={st.custom}"
        except Exception:
            return "drawables=n/a"

    def cache_line(self) -> str:
        try:
            return self._cache_fn() if self._cache_fn else "assets=n/a"
        except Exception:
            return "assets=n/a"

    def scene_stack(self) -> list:
        try:
            return list(self._scene_stack_fn()) if self._scene_stack_fn else []
        except Exception:
            return []

    def frame_line(self) -> str:
        st = self.frames.stats()
        return (f"frame avg={st['avg']:.1f}ms max={st['max']:.1f} fps={st['fps']:.0f} "
                f"sim={st['sim_avg']:.1f} draw={st['draw_avg']:.1f} spikes={st['spikes']}")

    def pick(self, world_x: float, world_y: float, radius: float = 48.0):
        """Nearest pickable live object to a world point (enemies, player, doors)."""
        best, best_d = None, radius
        pools = list(getattr(STATE, "enemies", []) or [])
        if getattr(STATE, "player", None) is not None:
            pools.append(STATE.player)
        pools += list(getattr(STATE, "doors", []) or [])
        for obj in pools:
            rect = getattr(obj, "rect", None)
            if rect is None:
                continue
            d = max(abs(rect.centerx - world_x), abs(rect.centery - world_y))
            if d < best_d:
                best, best_d = obj, d
        return best

    def describe(self, obj: Any) -> list[str]:
        if obj is None:
            return ["(no entity selected - click one)"]
        lines = [f"{type(obj).__name__} @ {getattr(getattr(obj, 'rect', None), 'center', '?')}"]
        try:
            import game.world as gw
            if gw.installed():
                eid = gw.roster().eid_for(obj)
                if eid is not None:
                    for name, fields in sorted(gw.world().dump_entity(eid).items()):
                        body = ", ".join(f"{k}={v!r}"[:40] for k, v in list(fields.items())[:6])
                        lines.append(f"[{name}] {body}")
        except Exception:
            pass
        lines += _plain_attrs(obj)
        return lines

    def set_field(self, name: str, value: str) -> str:
        obj = self.selected
        if obj is None:
            return "set: no entity selected (F3, then click one)"
        if not hasattr(obj, name):
            return f"set: {type(obj).__name__} has no field {name!r}"
        cur = getattr(obj, name)
        try:
            if isinstance(cur, bool):
                val = value.lower() in ("1", "true", "on", "yes")
            elif isinstance(cur, int):
                val = int(value)
            elif isinstance(cur, float):
                val = float(value)
            else:
                val = value
        except ValueError:
            return f"set: cannot parse {value!r} as {type(cur).__name__}"
        setattr(obj, name, val)
        return f"set {name} = {val!r} (was {cur!r})"

    def spawn_prefab(self, pid: str, x: float, y: float) -> str:
        lib = self._prefab_library
        if lib is None or pid not in lib:
            return f"spawn: no prefab {pid!r} registered"
        try:
            import game.world as gw
            eid = lib.instantiate(gw.world(), pid)
            return f"spawned prefab {pid!r} -> entity {eid} (components only; host draws it)"
        except Exception as e:
            return f"spawn failed: {e!r}"

    # -- events ---------------------------------------------------------
    def handle_event(self, event, mouse, state_name: str) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.overlay = not self.overlay
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F4:
            self.collision = not self.collision
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F5:
            self.level_view = not self.level_view
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F6:
            self.timeline_view = not self.timeline_view
            return True
        if self.overlay and state_name == "GAME" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cam_x = int(getattr(STATE, "camera_x", 0) or 0)
            cam_y = int(getattr(STATE, "camera_y", 0) or 0)
            self.selected = self.pick(mouse[0] + cam_x, mouse[1] + cam_y)
            return self.selected is not None
        return False

    # -- editors (P10-M2) ------------------------------------------------
    def level_summary(self) -> list[str]:
        """Level viewer data: every data-driven level, its grid and contents."""
        lines = []
        try:
            import os
            from game import levels as _lv
            for fn in sorted(os.listdir(_lv.LEVELS_DIR)):
                if not fn.endswith(".level.json"):
                    continue
                lid = fn[:-len(".level.json")]
                try:
                    lv = _lv.level(lid)
                    if lv is None:
                        continue
                    rows = len(next(iter(lv.layers.values()), []))
                    cols = max((len(r) for layer in lv.layers.values() for r in layer), default=0)
                    lines.append(f"{lid}: '{lv.name}' {cols}x{rows} layers={len(lv.layers)} "
                                 f"objects={len(lv.objects)} triggers={len(lv.triggers)} "
                                 f"paths={len(lv.paths)} lights={len(lv.lights)}")
                except Exception as e:
                    lines.append(f"{lid}: ERROR {e!r}")
        except Exception as e:
            lines.append(f"levels unavailable: {e!r}")
        return lines or ["(no level data)"]

    def timeline_summary(self) -> list[str]:
        info = None
        try:
            info = self._cutscene_fn() if self._cutscene_fn else None
        except Exception:
            info = None
        if not info:
            return ["timeline: no cutscene playing",
                    "console: timeline play <id> [t] | tl_keys <id> | tl_set/nudge/mark"]
        lines = [f"shot {info['idx'] + 1}/{info['count']}  scene={info.get('scene', '?')}"]
        if info.get("speaker"):
            lines.append(f"speaker={info['speaker']}")
        if info.get("text"):
            lines.append(f"text: {info['text'][:58]}")
        lines.append("edit: tl_set <id> <shot> <key> <value> (writes .timeline.json)")
        return lines

    # -- drawing ---------------------------------------------------------
    def draw(self, surface) -> None:
        if self.collision:
            self._draw_collision(surface)
        if not self.overlay:
            return
        cam_x = int(getattr(STATE, "camera_x", 0) or 0)
        cam_y = int(getattr(STATE, "camera_y", 0) or 0)
        panel = pygame.Surface((430, 196), pygame.SRCALPHA)
        panel.fill((6, 10, 8, 205))
        lines = [self.frame_line(),
                 f"entities={self.entity_count()}  {self.render_stats_line()}",
                 self.cache_line(),
                 f"scene: {' > '.join(self.scene_stack()) or (self._state_fn() if self._state_fn else '?')}",
                 f"mission={getattr(STATE, 'active_mission_id', getattr(STATE, 'active_mission', '?'))} "
                 f"state={self._state_fn() if self._state_fn else '?'}"]
        for i, text in enumerate(lines):
            panel.blit(font_terminal_small.render(text, True, (196, 226, 182)), (8, 6 + i * 16))
        # frame graph
        gx, gy, gw_, gh = 8, 92, 414, 60
        pygame.draw.rect(panel, (24, 32, 24), (gx, gy, gw_, gh), 1)
        samples = list(self.frames.samples)
        if samples:
            step = gw_ / max(1, len(samples))
            for i, (total, _s, _d) in enumerate(samples):
                h = min(gh, total / 50.0 * gh)
                col = (226, 84, 64) if total > SPIKE_MS else (120, 200, 120)
                pygame.draw.rect(panel, col, (gx + i * step, gy + gh - h, max(1, step - 0.5), h))
        panel.blit(font_terminal_small.render("frame ms (red > 20ms spike)", True, (150, 160, 140)), (gx, gy + gh + 4))
        surface.blit(panel, (6, 6))
        if self.selected is not None:
            desc = self.describe(self.selected)
            insp = pygame.Surface((430, 18 + 15 * min(11, len(desc))), pygame.SRCALPHA)
            insp.fill((6, 10, 8, 205))
            insp.blit(font_terminal_small.render("INSPECTOR (console: set <field> <value>)", True, (226, 206, 150)), (8, 3))
            for i, text in enumerate(desc[:10]):
                insp.blit(font_terminal_small.render(text[:62], True, (196, 226, 182)), (8, 20 + i * 15))
            surface.blit(insp, (6, 208))
        if self.level_view:
            self._draw_lines_panel(surface, 556, 6, "LEVELS (data: game/content/levels)",
                                   self.level_summary())
        if self.timeline_view:
            self._draw_lines_panel(surface, 556, 250, "TIMELINE", self.timeline_summary())
            r = getattr(self.selected, "rect", None)
            if r is not None:
                pygame.draw.rect(surface, (231, 181, 94),
                                 (r.x - cam_x, r.y - cam_y, r.w, r.h), 2)

    @staticmethod
    def _draw_lines_panel(surface, x, y, title, lines) -> None:
        w = 438
        h = 20 + 15 * (len(lines) + 1)
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((6, 10, 8, 210))
        panel.blit(font_terminal_small.render(title, True, (231, 181, 94)), (8, 4))
        for i, text in enumerate(lines):
            panel.blit(font_terminal_small.render(str(text)[:66], True, (196, 226, 182)),
                       (8, 22 + i * 15))
        surface.blit(panel, (x, y))

    def _draw_collision(self, surface) -> None:
        cam_x = int(getattr(STATE, "camera_x", 0) or 0)
        cam_y = int(getattr(STATE, "camera_y", 0) or 0)
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for wall in list(getattr(STATE, "walls", []) or []):
            r = wall if isinstance(wall, pygame.Rect) else getattr(wall, "rect", None)
            if r is not None:
                pygame.draw.rect(layer, (90, 160, 255, 90),
                                 (r.x - cam_x, r.y - cam_y, r.w, r.h))
        pl = getattr(STATE, "player", None)
        if pl is not None:
            for e in list(getattr(STATE, "enemies", []) or []):
                er = getattr(e, "rect", None)
                if er is not None:
                    pygame.draw.line(layer, (255, 120, 90, 160),
                                     (er.centerx - cam_x, er.centery - cam_y),
                                     (pl.rect.centerx - cam_x, pl.rect.centery - cam_y), 1)
        surface.blit(layer, (0, 0))


DEV = DevTools()
