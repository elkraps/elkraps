import unittest

from battleship.engine import new_game
from battleship.renderer import END, START, board, leaderboard, rankings, replace_block


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
        self.assertIn("| **1** | # | # |", rendered)

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
        self.assertEqual(len(rendered.splitlines()), 3)
