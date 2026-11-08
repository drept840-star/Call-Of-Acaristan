"""M3 must not create un-simulated molotovs from the shared input handler."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401
import pygame
from entities import weapons


class M3MolotovGateTests(unittest.TestCase):
    def test_m3_rejects_throws_with_inventory_and_any_equipped_weapon(self):
        for weapon in ("none", "chair_leg", "shiv", "sidearm", "k9_smg"):
            with self.subTest(weapon=weapon):
                state = SimpleNamespace(
                    active_mission="MISSION3", mission3_weapon=weapon,
                    player_disarmed=False, weapons_locked=False, player_dead=False,
                    player=SimpleNamespace(rect=pygame.Rect(100, 100, 24, 24)),
                    player_bottles=2, thrown_bottles=[], floating_texts=[])
                with patch.object(weapons, "STATE", state), \
                        patch.object(weapons.audio, "play") as play, \
                        patch("game.topdown3d.mouse_world") as mouse:
                    weapons.handle_throw_bottle()
                    self.assertEqual(state.player_bottles, 2)
                    self.assertEqual(state.thrown_bottles, [])
                    self.assertEqual(state.floating_texts, [])
                    play.assert_not_called()
                    mouse.assert_not_called()

    def test_other_action_missions_keep_their_throw(self):
        for mission in ("MISSION1", "MISSION2", "MISSION6"):
            with self.subTest(mission=mission):
                state = SimpleNamespace(
                    active_mission=mission, mission3_weapon="none",
                    player_disarmed=False, weapons_locked=False, player_dead=False,
                    player=SimpleNamespace(rect=pygame.Rect(100, 100, 24, 24)),
                    player_bottles=2, thrown_bottles=[], floating_texts=[])
                with patch.object(weapons, "STATE", state), \
                        patch.object(weapons.audio, "play") as play, \
                        patch("game.topdown3d.mouse_world", return_value=(220, 160)):
                    weapons.handle_throw_bottle()
                    self.assertEqual(state.player_bottles, 1)
                    self.assertEqual(len(state.thrown_bottles), 1)
                    play.assert_called_once_with("molotov_throw", volume=0.6)


if __name__ == "__main__":
    unittest.main()
