"""Render the public view, preserving all text outside the game markers."""

import html
from collections import Counter
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
    return (
        '<p align="center">'
        f"Shots: <strong>{len(state['shots'])}</strong> &nbsp; · &nbsp; "
        f"Hits: <strong>{hits}/{sum(state['fleet'])}</strong> &nbsp; · &nbsp; "
        f"Players: <strong>{len(rankings(state))}</strong>"
        "</p>"
    )


def fleet_status(state):
    total = Counter(state["fleet"])
    sunk = Counter(len(shot["sunk_cells"]) for shot in state["shots"] if shot["result"] == "sunk")
    counts = [f"{length}-cell × {total[length] - sunk[length]}" for length in sorted(total, reverse=True)]
    remaining = sum(total.values()) - sum(sunk.values())
    return (
        f'<h2 align="center">Ships left: {remaining}</h2>\n'
        '<p align="center">' + " &nbsp; · &nbsp; ".join(counts) + "</p>"
    )


def board(state, repository):
    shots = {shot["coordinate"]: shot for shot in state["shots"]}
    sunk = {cell for shot in state["shots"] for cell in shot["sunk_cells"]}
    revealed = {cell for ship in state.get("revealed_fleet", []) for cell in ship}
    header = "<tr><th></th>" + "".join(f'<th scope="col">{letter}</th>' for letter in "ABCDEFGH") + "</tr>"
    lines = [
        '<div align="center">',
        '<table align="center" style="display: table; width: auto; margin-left: auto; margin-right: auto;">',
        "<thead>" + header + "</thead>",
        "<tbody>",
    ]
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
                url = html.escape(f"https://github.com/{repository}/issues/new?{query}", quote=True)
                value = f'<a href="{url}" title="Fire at {cell}">·</a>'
            else:
                value = "·"
            row.append(f'<td align="center">{value}</td>')
        lines.append(f'<tr><th scope="row">{y}</th>' + "".join(row) + "</tr>")
    lines += ["</tbody>", "</table>", "</div>"]
    return "\n".join(lines)


def leaderboard(state):
    rows = [
        f"<tr><td>@{escape(actor)}</td><td>{stats['hits']}</td><td>{stats['sunk']}</td><td>{stats['shots']}</td></tr>"
        for actor, stats in rankings(state)[:10]
    ]
    if not rows:
        return '<p align="center">No shots yet. Be the first to play!</p>'
    return (
        '<table align="center" style="display: table; width: auto; margin-left: auto; margin-right: auto;">\n'
        "<tr><th>Player</th><th>Hits</th><th>Ships sunk</th><th>Shots</th></tr>\n" + "\n".join(rows) + "\n</table>"
    )


def render(state, repository, previous=None):
    lines = [
        "<hr />",
        '<h1 align="center">Community Battleship</h1>',
        f'<p align="center"><sub>{escape(state["game_id"])} · {escape(state["status"])}</sub></p>',
        '<p align="center">\n'
        "  Click a cell → submit the issue → refresh to see your shot.<br />\n"
        "  One shared fleet on an 8×8 board. Sink every ship. Play as often as you like.\n"
        "</p>",
        "<br />",
        fleet_status(state),
        board(state, repository),
        '<p align="center"><sub>· untried &nbsp; ○ miss &nbsp; × hit &nbsp; # sunk &nbsp; ■ revealed ship</sub></p>',
        "<br />",
        summary(state),
        "<br />",
        "<details>\n<summary><strong>Game activity</strong></summary>",
        '<h3 align="center">Last five shots</h3>',
    ]
    lines += [
        f'<p align="center"><code>{escape(shot["coordinate"])}</code> — {escape(shot["result"])} '
        f'by @{escape(shot["actor"])} (<a href="https://github.com/{repository}/issues/{shot["issue_number"]}">'
        f"#{shot['issue_number']}</a>)</p>"
        for shot in reversed(state["shots"][-5:])
    ]
    if not state["shots"]:
        lines.append('<p align="center">No shots yet.</p>')
    lines += ['<h3 align="center">Current game leaders</h3>', leaderboard(state)]
    lines.append("</details>")
    if previous:
        lines += [
            "<hr />",
            f'<h3 align="center">Previous game: {escape(previous["game_id"])} ({escape(previous["status"])})</h3>',
            summary(previous),
            leaderboard(previous),
            "<details><summary>Final board</summary>\n",
            board(previous, repository),
            "\n</details>",
            f'<p align="center"><a href="https://github.com/{repository}/tree/main/game/archive">Game archive</a></p>',
        ]
    return '<div align="center">\n\n' + "\n\n".join(lines) + "\n\n</div>"


def replace_block(readme, block):
    if START not in readme and END not in readme:
        return readme + f"\n\n{START}\n{block}\n{END}\n"
    if readme.count(START) != 1 or readme.count(END) != 1 or readme.index(START) > readme.index(END):
        raise ValueError("README must contain one correctly ordered pair of Battleship markers.")
    before, rest = readme.split(START)
    _, after = rest.split(END)
    return before + START + "\n" + block + "\n" + END + after
