import unittest

from battleship.engine import new_game
from battleship.renderer import END, START, board, fleet_status, leaderboard, rankings, replace_block, summary


class RendererTests(unittest.TestCase):
    def test_preserves_text_outside_markers(self):
        readme = f"Привет\r\n{START}\nold\n{END}\r\nFooter\n"
        self.assertEqual(replace_block(readme, "new"), f"Привет\r\n{START}\nnew\n{END}\r\nFooter\n")

    def test_invalid_markers_fail(self):
        for readme in (START, END, END + START, START + START + END):
            with self.subTest(readme=readme), self.assertRaises(ValueError):
                replace_block(readme, "new")

    def test_empty_board_has_64_game_scoped_links(self):
        rendered = board(new_game(42, "now"), "owner/repo")
        self.assertEqual(rendered.count("https://github.com/owner/repo/issues/new?"), 64)
        self.assertIn("battleship%3A+fire+A1+game-000042", rendered)
        self.assertIn("battleship%3A+fire+H8+game-000042", rendered)

    def test_sunk_cells_and_finished_board_have_no_links(self):
        state = new_game(1, "now")
        state.update(status="finished", revealed_fleet=[["A1", "B1"]])
        state["shots"] = [{"coordinate": "B1", "result": "sunk", "sunk_cells": ["A1", "B1"]}]
        rendered = board(state, "owner/repo")
        self.assertNotIn("issues/new", rendered)
        self.assertIn('<th scope="row">1</th><td align="center">#</td><td align="center">#</td>', rendered)

    def test_initial_fleet_and_remaining_totals(self):
        state = new_game(1, "now")
        self.assertIn("Shots: <strong>0</strong>", summary(state))
        self.assertIn("Hits: <strong>0/10</strong>", summary(state))
        remaining = fleet_status(state)
        self.assertIn("Ships left: 6", remaining)
        for length, count in ((3, 1), (2, 2), (1, 3)):
            self.assertIn(f"{length}-cell × {count}", remaining)

    def test_only_sunk_ships_reduce_remaining_fleet(self):
        state = new_game(1, "now")
        state["shots"] = [
            {"actor": "player", "result": "hit", "sunk_cells": []},
            {"actor": "player", "result": "sunk", "sunk_cells": ["A1", "B1"]},
            {"actor": "player", "result": "sunk", "sunk_cells": ["D4"]},
            {"actor": "player", "result": "miss", "sunk_cells": []},
        ]
        self.assertIn("Shots: <strong>4</strong>", summary(state))
        self.assertIn("Hits: <strong>3/10</strong>", summary(state))
        remaining = fleet_status(state)
        self.assertIn("Ships left: 4", remaining)
        self.assertIn("3-cell × 1", remaining)
        self.assertIn("2-cell × 1", remaining)
        self.assertIn("1-cell × 2", remaining)

    def test_ranking_tiebreaks_and_sunk_counts_as_hit(self):
        state = new_game(1, "now")
        state["shots"] = [
            {"actor": actor, "result": result}
            for actor, result in [("b", "hit"), ("a", "hit"), ("winner", "sunk"), ("b", "miss")]
        ]
        self.assertEqual([actor for actor, _ in rankings(state)], ["winner", "a", "b"])
        self.assertEqual(rankings(state)[0][1], {"hits": 1, "sunk": 1, "shots": 1})

    def test_external_text_cannot_inject_table_rows(self):
        state = new_game(1, "now")
        state["shots"] = [{"actor": "<script>|[x]\nnew", "result": "hit"}]
        rendered = leaderboard(state)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("[x]", rendered)
        self.assertEqual(rendered.count("<tr>"), 2)
