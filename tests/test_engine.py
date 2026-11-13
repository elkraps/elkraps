import unittest

from battleship.engine import fire, new_game

NOW = "2026-11-13T08:00:00Z"
SHIPS = [["A1", "B1", "C1"], ["E1", "F1"], ["A4", "B4"], ["D4"], ["F4"], ["H4"]]


class EngineTests(unittest.TestCase):
    def shot(self, state, cell, number=1):
        return fire(state, f"battleship: fire {cell} {state['game_id']}", "player", number, NOW, SHIPS)

    def test_miss_does_not_mutate_input(self):
        state = new_game(1, NOW)
        result, message = self.shot(state, "H8")
        self.assertEqual(state["shots"], [])
        self.assertEqual(result["shots"][0]["result"], "miss")
        self.assertIn("miss", message)
        self.assertNotIn("revealed_fleet", result)

    def test_hit_then_sunk(self):
        state, _ = self.shot(new_game(1, NOW), "E1")
        self.assertEqual(state["shots"][0]["result"], "hit")
        state, _ = self.shot(state, "F1", 2)
        self.assertEqual(state["shots"][-1]["result"], "sunk")
        self.assertEqual(state["shots"][-1]["sunk_cells"], ["E1", "F1"])

    def test_duplicate_is_rejected(self):
        state, _ = self.shot(new_game(1, NOW), "A1")
        result, message = self.shot(state, "A1", 2)
        self.assertEqual(result, state)
        self.assertIn("already", message)

    def test_invalid_and_stale_commands_do_not_change_state(self):
        state = new_game(2, NOW)
        for title in (
            "battleship: fire A1 game-000001",
            "battleship: fire I1 game-000002",
            "battleship: fire A0 game-000002",
            "battleship: wrong",
        ):
            with self.subTest(title=title):
                result, _ = fire(state, title, "player", 1, NOW, SHIPS)
                self.assertEqual(result, state)

    def test_last_hit_finishes_and_reveals(self):
        state = new_game(1, NOW)
        for number, cell in enumerate(cell for ship in SHIPS for cell in ship):
            state, message = self.shot(state, cell, number + 1)
        self.assertEqual(state["status"], "finished")
        self.assertEqual(state["finished_at"], NOW)
        self.assertEqual(state["revealed_fleet"], SHIPS)
        self.assertIn("Victory", message)
