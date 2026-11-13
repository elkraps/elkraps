import unittest

from battleship.placement import FLEET, place


class PlacementTests(unittest.TestCase):
    def test_version_one_golden_board(self):
        # A fixed vector protects active games against placement algorithm changes.
        self.assertEqual(place("test-secret", "owner/repo", "game-000001"), GOLDEN)

    def test_valid_fleets_across_games(self):
        for number in range(1, 101):
            ships = place("test-secret", "owner/repo", f"game-{number:06d}")
            self.assertEqual([len(ship) for ship in ships], FLEET)
            coords = [[(ord(cell[0]) - 65, int(cell[1:]) - 1) for cell in ship] for ship in ships]
            for index, ship in enumerate(coords):
                self.assertTrue(all(0 <= x < 8 and 0 <= y < 8 for x, y in ship))
                self.assertTrue(len({x for x, _ in ship}) == 1 or len({y for _, y in ship}) == 1)
                for a, b in zip(ship, ship[1:]):
                    self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)
                for other in coords[index + 1 :]:
                    self.assertTrue(all(max(abs(x - ox), abs(y - oy)) > 1 for x, y in ship for ox, oy in other))

    def test_missing_secret_and_unknown_version_fail(self):
        with self.assertRaises(ValueError):
            place("", "owner/repo", "game-000001")
        with self.assertRaises(ValueError):
            place("secret", "owner/repo", "game-000001", 2)


GOLDEN = [["C2", "C3", "C4"], ["F7", "G7"], ["B8", "C8"], ["E3"], ["G5"], ["E5"]]
