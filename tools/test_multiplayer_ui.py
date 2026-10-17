"""Small presentation regression suite; no live networking or external service."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import settings_store, profile_store
_TMP = tempfile.TemporaryDirectory(prefix='mp_ui_')
settings_store.SAVE_FILE = str(Path(_TMP.name) / 'settings.json')
profile_store.PROFILE_FILE = str(Path(_TMP.name) / 'profile.json')
import pygame
from core import config
from missions import arena as AR
from ui import mp
from ui.match_screen import MatchScreen, PANEL_X, PANEL_Y, PANEL_W, PANEL_H


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.ui = MatchScreen()
        self.ui.open_panel()
        self.screen = config.screen
        self.panel = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)

    def test_setup_targets_and_map_data(self):
        before = {name: tuple(rows) for name, rows in AR.ARENAS.items()}
        for name in self.ui.maps():
            self.ui.map_name = name
            self.ui.draw_panel(self.screen)
            targets = list(self.ui._map_rects.values()) + list(self.ui._mode_rects.values()) + list(self.ui._pl_rects.values()) + list(self.ui._btn_rects.values())
            targets += [self.ui._name_rect, self.ui._addr_rect]
            self.assertTrue(all(self.panel.contains(r) for r in targets))
            self.assertEqual(len(self.ui._pl_rects), self.ui.max_players() - 1)
        self.assertEqual(before, {name: tuple(rows) for name, rows in AR.ARENAS.items()})

    def lobby(self, host=True, empty_side=False):
        self.ui.mode = 'hosting' if host else 'playing'
        self.ui.players = 8
        teams = {i: 0 if empty_side else i % 2 for i in range(8)}
        self.ui._match_state = {'roster': [(i, 'OPERATOR_%d' % i) for i in range(8)], 'teams': teams, 'mode': AR.MODE_TDM, 'room_capacity': 8}
        if host:
            self.ui.sim = SimpleNamespace(
                players={i: {'nick': 'OPERATOR_%d' % i} for i in range(8)},
                rules=SimpleNamespace(mode=AR.MODE_TDM, teams=teams,
                    team_counts=lambda: {t: list(teams.values()).count(t) for t in (0, 1)}))
        self.ui.room_code = 'ACAR-A974P-K39GWZ'
        self.ui.join_token = '12345678'
        self.ui.share_host = '192.168.0.5'
        self.ui.share_port = 27017
        self.ui._draw_waiting(self.screen)

    def test_host_controls_and_full_roster(self):
        self.lobby()
        self.assertIn('start', self.ui._lobby_rects)
        self.assertIn('copy', self.ui._wait_rects)
        self.assertIn('balance', self.ui._lobby_rects)
        self.assertEqual(sum(k.startswith('swap_') for k in self.ui._lobby_rects), 7)
        self.assertTrue(all(self.panel.contains(r) for r in self.ui._lobby_rects.values()))

    def test_unbalanced_team_disables_start(self):
        self.lobby(empty_side=True)
        self.assertNotIn('start', self.ui._lobby_rects)
        self.assertEqual(sum(k.startswith('swap_') for k in self.ui._lobby_rects), 7)

    def test_joiner_has_no_admin_targets(self):
        self.lobby(host=False)
        self.assertEqual(set(self.ui._lobby_rects), {'team_0', 'team_1'})
        self.assertEqual(self.ui._wait_rects, {})
        self.assertTrue(self.ui.input_frozen())

    def test_arena_entry_and_keyboard_contract(self):
        mp.draw_server_browser(-1, False, '')
        self.assertTrue(pygame.Rect(mp.SERVER_PANEL_X, mp.SERVER_PANEL_Y, mp.SERVER_PANEL_W, mp.SERVER_PANEL_H).contains(mp.enter_arena_rect()))
        self.assertTrue(mp.enter_arena_hit(mp.enter_arena_rect().center))
        self.ui.draw_panel(self.screen)
        before = self.ui.selected_field
        self.assertTrue(self.ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB), (0, 0)))
        self.assertNotEqual(before, self.ui.selected_field)


if __name__ == '__main__':
    unittest.main()
