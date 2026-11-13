"""Parse untrusted issue titles as data."""

import re

PREFIX = re.compile(r"^battleship\s*:", re.IGNORECASE)
FIRE = re.compile(r"battleship: fire ([A-Za-z][0-9]+) (game-[0-9]{6,})")


def is_game(title):
    return bool(PREFIX.match(title.strip()))


def parse(title):
    match = FIRE.fullmatch(title.strip())
    if not match:
        raise ValueError("Invalid command. Choose a cell in the current README to fire.")
    cell, game_id = match.groups()
    return cell.upper(), game_id
