import unittest

from battleship.engine import new_game
from battleship.renderer import END, START, board, fleet_status, leaderboard, rankings, render, replace_block, summary


class RendererTests(unittest.TestCase):
    def test_all_time_totals_count_finished_and_current_games_once(self):
        finished = new_game(1, "now")
        finished.update(
            status="finished", shots=[{"actor": "veteran", "result": "sunk", "coordinate": "B1", "sunk_cells": ["B1"]}]
        )
        current = new_game(2, "now")
        current["shots"] = [
            {"actor": "newcomer", "result": "miss", "coordinate": "A1", "sunk_cells": [], "issue_number": 1}
        ]
        output = render(current, "owner/repo", finished, archives=[finished, finished])
        hall = output.split(">Hall of Fame</h3>", 1)[1].split("</details>", 1)[0]
        self.assertIn("Games completed: <strong>1</strong>", hall)
        self.assertIn("Shots: <strong>2</strong>", hall)
        self.assertIn("Players: <strong>2</strong>", hall)
        self.assertIn('href="https://github.com/veteran"', hall)
        self.assertIn('href="https://github.com/newcomer"', hall)

    def test_aborted_games_do_not_affect_all_time_stats(self):
        aborted = new_game(1, "now")
        aborted.update(status="aborted", shots=[{"actor": "cancelled-player", "result": "hit"}])
        output = render(new_game(2, "now"), "owner/repo", archives=[aborted])
        hall = output.split(">Hall of Fame</h3>", 1)[1].split("</details>", 1)[0]
        self.assertIn("Games completed: <strong>0</strong>", hall)
        self.assertIn("Shots: <strong>0</strong>", hall)
        self.assertNotIn("cancelled-player", hall)

    def test_hall_of_fame_limits_display_to_ten_without_losing_player_count(self):
        finished = new_game(1, "now")
        finished.update(status="finished", shots=[{"actor": f"player-{i:02d}", "result": "hit"} for i in range(12)])
        output = render(new_game(2, "now"), "owner/repo", archives=[finished])
        hall = output.split(">Hall of Fame</h3>", 1)[1].split("</details>", 1)[0]
        self.assertEqual(hall.count('href="https://github.com/player-'), 10)
        self.assertIn("Players: <strong>12</strong>", hall)
        self.assertIn("@player-00", hall)
        self.assertNotIn("@player-10", hall)

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
        self.assertIn('<a href="https://github.com/winner">@winner</a>', leaderboard(state))

    def test_external_text_cannot_inject_table_rows(self):
        state = new_game(1, "now")
        state["shots"] = [{"actor": "<script>|[x]\nnew", "result": "hit"}]
        rendered = leaderboard(state)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("[x]", rendered)
        self.assertEqual(rendered.count("<tr>"), 2)
