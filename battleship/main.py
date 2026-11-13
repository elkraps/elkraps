"""Drain the issue queue, commit results, then deliver acknowledgements."""

import argparse
import hmac
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path

from .commands import is_game
from .engine import fire, new_game
from .github_client import GitHub
from .placement import place
from .renderer import render, replace_block
from .storage import Repository, read_json, write_json

MAX_COMMANDS = 50
MAX_ATTEMPTS = 3


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fleet(state, secret, repository):
    if not secret:
        raise ValueError("BATTLESHIP_MASTER_SECRET is required.")
    commitment = hmac.digest(secret.encode(), f"verification:{repository}:{state['game_id']}".encode(), "sha256").hex()
    if "secret_commitment" in state and not hmac.compare_digest(state["secret_commitment"], commitment):
        raise ValueError("The master secret changed. Restore the original secret before processing this game.")
    state["secret_commitment"] = commitment
    return place(secret, repository, state["game_id"], state["placement_version"])


def archive(state):
    write_json(f"game/archive/{state['game_id']}.json", state)


def next_game(state, timestamp):
    return new_game(int(state["game_id"].split("-")[1]) + 1 if state else 1, timestamp)


def process(state, journal, issues, secret, repository, timestamp, previous=None):
    """Return state, journal and completed games without network or file writes."""
    state, journal = deepcopy(state), deepcopy(journal)
    completed = []
    if state is None:
        state = next_game(None, timestamp)
    if state["status"] == "finished":
        completed.append(state)
        previous = state
        state = next_game(state, timestamp)
    ships = fleet(state, secret, repository)
    issues = sorted(issues, key=lambda issue: (issue["created_at"], issue["number"]))
    count = 0
    for issue in issues:
        key = str(issue["number"])
        if "pull_request" in issue or not is_game(issue["title"]) or key in journal:
            continue
        if count == MAX_COMMANDS:
            break
        state, message = fire(state, issue["title"], issue["user"]["login"], issue["number"], timestamp, ships)
        journal[key] = {"message": message, "delivered": False, "processed_at": timestamp}
        count += 1
        if state["status"] == "finished":
            completed.append(state)
            previous = state
            state = next_game(state, timestamp)
            ships = fleet(state, secret, repository)
    return state, journal, completed, previous


def collect(client, journal):
    issues = []
    for issue in client.issues():
        if "pull_request" not in issue and is_game(issue["title"]) and str(issue["number"]) not in journal:
            issues.append(issue)
            if len(issues) == MAX_COMMANDS:
                break
    return issues


def run(client, repo, secret, repository, restart=False, force=False):
    if not secret:
        raise ValueError("BATTLESHIP_MASTER_SECRET is required.")
    timestamp = now()
    for attempt in range(MAX_ATTEMPTS):
        repo.refresh()
        state = read_json("game/current.json")
        journal = read_json("game/commands.json", {})
        previous = read_json("game/previous.json")
        if restart and state:
            if state["status"] == "active" and not force:
                raise ValueError("An active game already exists. Set force to replace it.")
            if state["status"] == "active":
                state.update(status="aborted", finished_at=timestamp, revealed_fleet=fleet(state, secret, repository))
            archive(state)
            previous = state
            state = next_game(state, timestamp)
        state, journal, completed, previous = process(
            state, journal, collect(client, journal), secret, repository, timestamp, previous
        )
        for finished in completed:
            archive(finished)
        write_json("game/current.json", state)
        write_json("game/commands.json", journal)
        if previous:
            write_json("game/previous.json", previous)
        path = Path("README.md")
        # Preserve exact bytes outside the markers, including existing line endings.
        readme = path.read_bytes().decode("utf-8")
        path.write_bytes(replace_block(readme, render(state, repository, previous)).encode("utf-8"))
        if repo.publish():
            break
    else:
        raise RuntimeError("Branch changed during all publication attempts. Run queue recovery again.")

    # Results are durable before any external replies. A failure leaves the journal pending.
    delivered = []
    for key, result in journal.items():
        if not result["delivered"]:
            client.reply(int(key), result["message"])
            delivered.append(key)
            if len(delivered) == MAX_COMMANDS:
                break
    if delivered:
        for attempt in range(MAX_ATTEMPTS):
            repo.refresh()
            journal = read_json("game/commands.json")
            for key in delivered:
                journal[key]["delivered"] = True
            write_json("game/commands.json", journal)
            if repo.publish():
                break
        else:
            raise RuntimeError("Replies delivered but acknowledgements could not be committed. Run recovery.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new-game", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    secret = os.environ.get("BATTLESHIP_MASTER_SECRET", "")
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    run(
        GitHub(repository, token),
        Repository(os.environ.get("BATTLESHIP_BRANCH", "main")),
        secret,
        repository,
        args.new_game,
        args.force,
    )


if __name__ == "__main__":
    # Avoid tracebacks containing HTTP responses or data related to placement.
    try:
        main()
    except Exception as error:
        detail = str(error) if type(error) in (ValueError, RuntimeError) else type(error).__name__
        print(f"Battleship processing failed: {detail}", flush=True)
        raise SystemExit(1)
