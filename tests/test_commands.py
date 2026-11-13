import unittest

from battleship.commands import is_game, parse


class CommandTests(unittest.TestCase):
    def test_coordinate_case_and_outer_whitespace(self):
        self.assertEqual(parse("  battleship: fire d5 game-000042\n"), ("D5", "game-000042"))

    def test_strict_structure(self):
        for title in (
            "battleship: fire D5 game-1",
            "battleship: fire D5 game-000001; echo x",
            "battleship:  fire D5 game-000001",
            "battleship: fire Д5 game-000001",
        ):
            with self.subTest(title=title), self.assertRaises(ValueError):
                parse(title)

    def test_unrelated_title_is_ignored(self):
        self.assertFalse(is_game("Fix the README"))
        self.assertTrue(is_game(" Battleship: wrong"))
