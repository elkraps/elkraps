"""Render the public view, preserving all text outside the game markers."""

import html
from urllib.parse import urlencode

START = "<!-- BATTLESHIP:START -->"
END = "<!-- BATTLESHIP:END -->"


def escape(value):
    return (
        html.escape(value)
        .replace("|", "&#124;")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
    )


def rankings(state):
    users = {}
    for shot in state["shots"]:
        row = users.setdefault(shot["actor"], {"shots": 0, "hits": 0, "sunk": 0})
        row["shots"] += 1
        row["hits"] += shot["result"] != "miss"
        row["sunk"] += shot["result"] == "sunk"
    return sorted(users.items(), key=lambda item: (-item[1]["hits"], -item[1]["sunk"], item[1]["shots"], item[0]))


def summary(state):
    hits = sum(shot["result"] != "miss" for shot in state["shots"])
    sunk = sum(shot["result"] == "sunk" for shot in state["shots"])
    return f"Shots: **{len(state['shots'])}** · Hits: **{hits}/10** · Ships sunk: **{sunk}/6** · Players: **{len(rankings(state))}**"


def board(state, repository):
    shots = {shot["coordinate"]: shot for shot in state["shots"]}
    sunk = {cell for shot in state["shots"] for cell in shot["sunk_cells"]}
    revealed = {cell for ship in state.get("revealed_fleet", []) for cell in ship}
    lines = ["| | A | B | C | D | E | F | G | H |", "| --- |" + " --- |" * 8]
    for y in range(1, 9):
        row = []
        for letter in "ABCDEFGH":
            cell = f"{letter}{y}"
            if cell in sunk:
                value = "#"
            elif cell in shots:
                value = "○" if shots[cell]["result"] == "miss" else "×"
            elif cell in revealed:
                value = "■"
            elif state["status"] == "active":
                query = urlencode(
                    {
                        "title": f"battleship: fire {cell} {state['game_id']}",
                        "body": f"Submit this issue to fire at {cell}. Return to the profile and refresh after processing.",
                    }
                )
                value = f"[·](https://github.com/{repository}/issues/new?{query})"
            else:
                value = "·"
            row.append(value)
        lines.append(f"| **{y}** | " + " | ".join(row) + " |")
    return "\n".join(lines)


def leaderboard(state):
    rows = ["| Player | Hits | Ships sunk | Shots |", "| --- | --- | --- | --- |"]
    rows += [
        f"| @{escape(actor)} | {stats['hits']} | {stats['sunk']} | {stats['shots']} |"
        for actor, stats in rankings(state)[:10]
    ]
    return "\n".join(rows) if len(rows) > 2 else "No shots yet. Be the first to play!"


def render(state, repository, previous=None):
    lines = [
        "## Community Battleship",
        f"**{state['game_id']} · {state['status']}**",
        "Click a cell and create an issue to fire. Refresh this page after processing.",
        "One shared fleet. Everyone can play, and you can fire more than once.",
        board(state, repository),
        "Legend: · untried · ○ miss · × hit · # sunk · ■ revealed ship",
        summary(state),
        "### Last five shots",
    ]
    lines += [
        f"- `{shot['coordinate']}` — {shot['result']} by @{escape(shot['actor'])} ([#{shot['issue_number']}](https://github.com/{repository}/issues/{shot['issue_number']}))"
        for shot in reversed(state["shots"][-5:])
    ]
    if not state["shots"]:
        lines.append("No shots yet.")
    lines += ["### Current game leaders", leaderboard(state)]
    if previous:
        lines += [
            f"### Previous game: {previous['game_id']} ({previous['status']})",
            summary(previous),
            leaderboard(previous),
            "<details><summary>Final board</summary>\n",
            board(previous, repository),
            "\n</details>",
            f"[Game archive](https://github.com/{repository}/tree/main/game/archive)",
        ]
    return "\n\n".join(lines)


def replace_block(readme, block):
    if START not in readme and END not in readme:
        return readme + f"\n\n{START}\n{block}\n{END}\n"
    if readme.count(START) != 1 or readme.count(END) != 1 or readme.index(START) > readme.index(END):
        raise ValueError("README must contain one correctly ordered pair of Battleship markers.")
    before, rest = readme.split(START)
    _, after = rest.split(END)
    return before + START + "\n" + block + "\n" + END + after
