"""RPE6 ADAPTER A-005: mirror the legacy GameStateManager onto an engine SceneStack.

The FSM in ``core.fsm`` stays the owner of behaviour (enter/exit/update/render).
This module only *observes* its transitions (``gsm.on_change``) and replays them
as push/pop/replace on an ``engine.scene.SceneStack``, so the scene trace
(``log.channel("scene")``, ``stack.trace``) exists before any state is lifted
into a real scene. Policy:

* a state listed in ``overlay_states`` (pause menu, notebook inspect) is pushed
  on top of the current scene and popped when the FSM leaves it;
* every other state replaces the full-screen scene on top (after popping any
  overlays); re-entering the same state (mission restart) is also a replace;
* the stack is seeded with the FSM's current state when the mirror attaches.

Owner module for the mirror; ``app.py`` wires it (``_LegacyGameScene``).
"""
from __future__ import annotations

from engine.scene import Scene, SceneStack

__all__ = ["LegacyStateScene", "FsmSceneMirror"]


class LegacyStateScene(Scene):
    """One FSM state seen as a scene. Hooks stay empty on purpose (mirror only)."""

    def __init__(self, name: str, overlay: bool) -> None:
        super().__init__(name)
        self.overlay = bool(overlay)


class FsmSceneMirror:
    """``scene_factory(name, overlay) -> Scene | None`` lets the host put a richer
    engine scene on the stack for a state (e.g. a ``CutsceneScene`` carrying the
    take that is playing); ``None`` falls back to a plain ``LegacyStateScene``."""

    def __init__(self, gsm, stack: SceneStack, overlay_states=(), scene_factory=None) -> None:
        self.gsm = gsm
        self.stack = stack
        self.overlay_states = frozenset(overlay_states)
        self.scene_factory = scene_factory
        if gsm.current_name:
            stack.push(self._scene(gsm.current_name, gsm.current_name in self.overlay_states))
        gsm.on_change = self

    def _scene(self, name: str, overlay: bool) -> Scene:
        if self.scene_factory is not None:
            made = self.scene_factory(name, overlay)
            if made is not None:
                return made
        return LegacyStateScene(name, overlay)

    def detach(self) -> None:
        if self.gsm.on_change is self:
            self.gsm.on_change = None

    def __call__(self, prev: str, new: str) -> None:
        stack = self.stack
        if new in self.overlay_states:
            if stack.top is None or stack.top.name.split("[", 1)[0] != new:
                stack.push(self._scene(new, True))
            return
        # Leaving overlays: pop until a full-screen scene is on top.
        while stack.top is not None and stack.top.overlay:
            stack.pop()
        state_of = lambda scene: scene.name.split("[", 1)[0]   # "CUTSCENE[take]" -> "CUTSCENE"
        if stack.top is None:
            stack.push(self._scene(new, False))
        elif state_of(stack.top) != new or prev == new:
            stack.replace(self._scene(new, False))
