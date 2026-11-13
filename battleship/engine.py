"""Pure game transitions, independent of GitHub and persistence."""

from copy import deepcopy

from .commands import parse
from .placement import FLEET, SIZE


def new_game(number, now):
    return {
        "schema_version": 1,
        "placement_version": 1,
        "game_id": f"game-{number:06d}",
        "status": "active",
        "board_size": SIZE,
        "fleet": list(FLEET),
        "started_at": now,
        "finished_at": None,
        "shots": [],
    }


def fire(state, title, actor, issue_number, now, ships):
    try:
        cell, game_id = parse(title)
    except ValueError as error:
        return state, str(error)
    if game_id != state["game_id"] or state["status"] != "active":
        return state, (
            f"This shot belongs to an inactive or unknown game ({game_id}).\n\n"
            f"Current game: {state['game_id']}. Choose a cell in the current README."
        )
    if cell not in {f"{chr(65 + x)}{y + 1}" for x in range(SIZE) for y in range(SIZE)}:
        return state, "Invalid coordinate. Choose a cell from A1 to H8 in the current README."
    previous = {shot["coordinate"] for shot in state["shots"]}
    if cell in previous:
        return state, f"{cell} has already been fired at. This shot was not counted. Choose another cell."
    ship = next((ship for ship in ships if cell in ship), None)
    sunk = ship is not None and set(ship) <= previous | {cell}
    result = "sunk" if sunk else "hit" if ship else "miss"
    updated = deepcopy(state)
    updated["shots"].append(
        {
            "coordinate": cell,
            "result": result,
            "actor": actor,
            "issue_number": issue_number,
            "processed_at": now,
            "sunk_cells": list(ship) if sunk else [],
        }
    )
    hits = sum(shot["result"] != "miss" for shot in updated["shots"])
    remaining = len(FLEET) - sum(shot["result"] == "sunk" for shot in updated["shots"])
    description = f"sunk a {len(ship)}-cell ship" if sunk else result
    message = (
        f"Shot {cell}: {description}.\n\nGame: {game_id}\nShots: {len(updated['shots'])}\nShips remaining: {remaining}."
    )
    if hits == sum(FLEET):
        updated.update(status="finished", finished_at=now, revealed_fleet=deepcopy(ships))
        message += "\n\nVictory! The fleet is sunk. Results are archived and a new game is ready."
    return updated, message + "\n\nThe board in the README has been updated."
