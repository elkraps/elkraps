"""Versioned deterministic placement; never persist seeds or active fleets."""

import hmac

SIZE = 8
FLEET = [3, 2, 2, 1, 1, 1]


def coordinate(x, y):
    return f"{chr(65 + x)}{y + 1}"


def place(secret, repository, game_id, version=1):
    if not secret:
        raise ValueError("BATTLESHIP_MASTER_SECRET is required.")
    if version != 1:
        raise ValueError("Unsupported placement version.")
    seed = hmac.digest(secret.encode(), f"{repository}:{game_id}:{version}".encode(), "sha256")
    candidates = {}
    for length in set(FLEET):
        options = set()
        for y in range(SIZE):
            for x in range(SIZE):
                for dx, dy in ((1, 0), (0, 1)):
                    cells = tuple((x + dx * i, y + dy * i) for i in range(length))
                    if all(cx < SIZE and cy < SIZE for cx, cy in cells):
                        options.add(cells)
        candidates[length] = sorted(options)

    def search(index, blocked, ships):
        if index == len(FLEET):
            return ships
        options = sorted(
            candidates[FLEET[index]],
            key=lambda cells: hmac.digest(seed, f"{index}:{ships}:{cells}".encode(), "sha256"),
        )
        for cells in options:
            if any(cell in blocked for cell in cells):
                continue
            neighbors = {(x + dx, y + dy) for x, y in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            result = search(index + 1, blocked | neighbors, ships + [cells])
            if result is not None:
                return result
        return None

    ships = search(0, set(), [])
    if ships is None:
        raise RuntimeError("Unable to place fleet.")
    return [[coordinate(x, y) for x, y in cells] for cells in ships]
