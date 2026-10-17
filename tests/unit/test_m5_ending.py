"""M5 finale regressions. Run: python -m unittest tests.unit.test_m5_ending -v.

Executes the production player classes without starting app or touching saves.
Covers the current single-shot finale (``meta.mission5_ending_shots`` =
``m5_shadow_finale``, one 42 s auto-advance take) plus generic shot-contract
cases with synthetic shots, and the ``m5ending3d`` blocking geometry still
used by the ``m5martial3d`` takes.
"""
import ast
import importlib.util
import math
from pathlib import Path
import sys
import types
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def load_file(name, path):
    """Load a file inside a synthetic package so relative imports resolve."""
    path = Path(path)
    pkg = types.ModuleType(name + "_pkg")
    pkg.__path__ = [str(path.parent)]
    sys.modules[pkg.__name__] = pkg
    full = pkg.__name__ + "." + path.stem
    spec = importlib.util.spec_from_file_location(full, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


def _load_meta():
    """Load meta.py without its scene-registration side effect: the real
    package import in test_m5_finale_audio must be the only registration."""
    import core.cutscene_registry as registry
    original = registry.register_scene_renderer
    registry.register_scene_renderer = lambda *a, **kw: None
    try:
        return load_file('m5_test_meta', ROOT / 'src/missions/m5/meta.py')
    finally:
        registry.register_scene_renderer = original


meta = _load_meta()


def player_harness(shots, fades=True):
    now, routes, ambience, cues = [1000], [], [], []
    pygame = SimpleNamespace(
        KEYDOWN=1, K_ESCAPE=27, K_RETURN=13, K_SPACE=32,
        time=SimpleNamespace(get_ticks=lambda: now[0]),
        event=SimpleNamespace(Event=lambda typ, **kw: SimpleNamespace(type=typ, **kw)),
        mouse=SimpleNamespace(set_visible=lambda value: None))
    ns = dict(pygame=pygame, GameState=object, KO_CUT_CUES={}, TEXT_SPEED=4,
              _text_speed_interval=lambda: 4,   # RPE6 P9: production helper, seeded like TEXT_SPEED
              _now_ms=lambda: now[0],
              audio=SimpleNamespace(play=lambda *a, **kw: cues.append(a)),
              voice=SimpleNamespace(stop=lambda: None, pause=lambda: None,
                                    resume=lambda: None),
              gc=SimpleNamespace(reset_dialogue_slide=lambda: None),
              gsm=SimpleNamespace(transition=routes.append),
              _set_ambience=lambda names: ambience.append(names),
              _play_typewriter_tick=lambda *a, **kw: None,
              mission_complete_timer=0, mission_complete_fade=0)
    tree = ast.parse((ROOT / 'src/app.py').read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)
             and n.name in ('CutscenePlayer', '_CutsceneState')]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'production_player', 'exec'), ns)
    cp = ns['CutscenePlayer'](shots, 'MISSION5_COMPLETE', use_fades=fades)
    ns['active_cutscene'] = cp
    return cp, ns['_CutsceneState'](), now, routes, ambience, cues


class PlaybackTests(unittest.TestCase):
    def test_finale_gate_advances_once_at_authored_end(self):
        cp, state, now, routes, _, _ = player_harness(meta.mission5_ending_shots)
        shot = cp.current_shot
        now[0] = cp.start_time + shot['min_ms'] - 1
        with patch('audio.voice.play_line', return_value=0):
            state.update(1/60)
            self.assertFalse(cp.completed)
            self.assertEqual(routes, [])
            now[0] += 1
            state.update(1/60)
            self.assertTrue(cp.completed)
            self.assertEqual(routes, ['MISSION_COMPLETE'])
            state.update(1/60)
            self.assertEqual(routes, ['MISSION_COMPLETE'])

    def test_entire_finale_reaches_completion(self):
        cp, state, now, routes, _, _ = player_harness(meta.mission5_ending_shots)
        with patch('audio.voice.play_line', return_value=0):
            for _ in range(600):
                now[0] += 100
                state.update(1/60)
                if routes:
                    break
        self.assertEqual(routes, ['MISSION_COMPLETE'])
        self.assertTrue(cp.completed)
        self.assertGreaterEqual(now[0] - cp.start_time, cp.current_shot['min_ms'])

    def test_dialogue_shots_remain_manual(self):
        shot = dict(scene='m5_river_gate', text='Line one.', speaker='VASILE', min_ms=100)
        cp, state, now, routes, _, _ = player_harness([shot, dict(shot)], fades=False)
        now[0] += 20000
        with patch('audio.voice.play_line', return_value=0):
            state.update(1/60)
            self.assertEqual(routes, [])
            self.assertEqual(cp.shot_idx, 0)
            state.handle_event(SimpleNamespace(type=1, key=32), 0, 0, {})
            self.assertEqual(cp.char_idx, len(shot['text']))
            state.handle_event(SimpleNamespace(type=1, key=32), 0, 0, {})
        self.assertEqual(cp.shot_idx, 1)

    def test_faded_auto_shot_does_not_skip_successor(self):
        shot = dict(scene='silent', text='', speaker='', min_ms=100,
                    auto_advance=True, quiet_ui=True)
        cp, state, now, routes, _, _ = player_harness([shot, dict(shot, auto_advance=False)])
        now[0] += 100
        state.update(1/60)
        self.assertEqual(cp.transition_timer, 15)
        for _ in range(20):
            now[0] += 17
            state.update(1/60)
        self.assertEqual(cp.shot_idx, 1)
        self.assertEqual(cp.transition_timer, 0)
        self.assertEqual(routes, [])

    def test_finale_ambience_uses_dedicated_stem(self):
        cp, state, _, _, ambience, _ = player_harness(meta.mission5_ending_shots)
        state.set_ambience()
        self.assertEqual(ambience[-1], {'rain', 'wind'})   # generic loops, no stem yet
        cp.finale_audio = object()
        state.set_ambience()
        self.assertEqual(ambience[-1], set())              # stem owns rain/wind now
        shot = meta.mission5_ending_shots[0]
        self.assertTrue(shot['quiet_ui'] and shot['cinematic_controls'])


class BlockingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The helper imports only engine3d geometry, not the game's cutscene facade.
        cls.s = load_file('m5_test_blocking', ROOT / 'src/cutscenes/m5ending3d.py')

    def test_maru_turn_is_planted(self):
        s = self.s
        positions = [s.maru_block(t)[0] for t in (3100, 3200, 3300, 3400, 3500)]
        self.assertTrue(all(math.dist(p, positions[0]) < 1e-9 for p in positions))
        self.assertEqual(s.maru_yaw(3100), 90)
        self.assertEqual(s.maru_yaw(3500), 180)
        self.assertEqual(s.maru_move_weight(3300), 0)
        self.assertLess(s.maru_block(5350)[0][2], -2.5)

    def test_ucilev_feet_match_treads_for_entire_exit(self):
        s = self.s
        sniper = (-16, 9.2, 37)
        for t in range(0, 6801, 10):
            pos, _, distance, _ = s.ucilev_block(t, sniper, 156)
            first = s.ROOF_DOOR_Z + .5 - s.STAIR_RUN / 2
            i = max(0, min(s.STAIR_COUNT-1, math.floor((distance-first)/s.STAIR_RUN)))
            self.assertAlmostEqual(pos[1], sniper[1] - i * s.STAIR_DROP)
        self.assertAlmostEqual(s.ucilev_block(6200, sniper, 156)[0][1], 9.2-1.68)

    def test_gait_is_zero_during_holds(self):
        s = self.s
        for t in (0, 650, 3300, 3900, 4300, 6200, 6800):
            self.assertEqual(max(s.move_weight(t,650,2650), s.move_weight(t,4300,1900)), 0)


if __name__ == '__main__':
    unittest.main()
