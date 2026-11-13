from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest

from battleship.github_client import GitHub
from battleship.main import MAX_COMMANDS, fleet, process, run
from battleship.storage import read_json

SECRET = "test-secret"
REPOSITORY = "owner/repo"
NOW = "2026-11-13T08:00:00Z"


def issue(number, cell="A1", game="game-000001"):
    return {
        "number": number,
        "title": f"battleship: fire {cell} {game}",
        "created_at": NOW,
        "user": {"login": f"player-{number}"},
    }


@contextmanager
def workspace():
    old = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        try:
            os.chdir(directory)
            Path("README.md").write_text("Original profile\n", encoding="utf-8")
            yield
        finally:
            os.chdir(old)


class FakeRepository:
    def __init__(self):
        self.remote = {"README.md": b"Original profile\n"}
        self.conflicts = 0
        self.publications = 0

    def refresh(self):
        for path in Path("game").rglob("*.json"):
            path.unlink()
        for name, value in self.remote.items():
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)

    def publish(self):
        self.publications += 1
        if self.conflicts:
            self.conflicts -= 1
            self.remote["README.md"] = b"Concurrent profile edit\n"
            return False
        self.remote = {str(path): path.read_bytes() for path in [Path("README.md"), *Path("game").rglob("*.json")]}
        return True


class FakeClient:
    def __init__(self, issues=()):
        self.queue = list(issues)
        self.comments = {}
        self.closed = set()
        self.fail = False

    def issues(self):
        return iter(self.queue)

    def reply(self, number, message):
        self.comments[number] = message
        if self.fail:
            raise RuntimeError("Simulated delivery failure.")
        self.closed.add(number)


class ProcessingTests(unittest.TestCase):
    def test_bootstrap_is_idempotent_and_does_not_publish_fleet(self):
        with workspace():
            repo, client = FakeRepository(), FakeClient()
            run(client, repo, SECRET, REPOSITORY)
            first = dict(repo.remote)
            run(client, repo, SECRET, REPOSITORY)
            self.assertEqual(first, repo.remote)
            self.assertNotIn("revealed_fleet", read_json("game/current.json"))
            self.assertNotIn(SECRET, b"".join(repo.remote.values()).decode())

    def test_simultaneous_shots_sorted_and_duplicate_rejected(self):
        state, journal, _, _ = process(None, {}, [issue(3, "A1"), issue(2, "B1"), issue(1)], SECRET, REPOSITORY, NOW)
        self.assertEqual([shot["issue_number"] for shot in state["shots"]], [1, 2])
        self.assertIn("already", journal["3"]["message"])

    def test_reprocessing_issue_does_not_add_shot(self):
        state, journal, _, _ = process(None, {}, [issue(1)], SECRET, REPOSITORY, NOW)
        result, second_journal, _, _ = process(state, journal, [issue(1)], SECRET, REPOSITORY, NOW)
        self.assertEqual(result, state)
        self.assertEqual(second_journal, journal)

    def test_victory_archives_and_stale_queue_does_not_touch_next_game(self):
        initial, _, _, _ = process(None, {}, [], SECRET, REPOSITORY, NOW)
        cells = [cell for ship in fleet(initial, SECRET, REPOSITORY) for cell in ship]
        queue = [issue(index + 1, cell) for index, cell in enumerate(cells)] + [issue(11, "H8")]
        with workspace():
            repo, client = FakeRepository(), FakeClient(queue)
            run(client, repo, SECRET, REPOSITORY)
            self.assertEqual(read_json("game/current.json")["game_id"], "game-000002")
            self.assertEqual(read_json("game/current.json")["shots"], [])
            archive = read_json("game/archive/game-000001.json")
            self.assertEqual(archive["status"], "finished")
            self.assertEqual(len(archive["shots"]), 10)
            self.assertIn("revealed_fleet", archive)
            self.assertIn("Victory", client.comments[10])
            readme = Path("README.md").read_text()
            self.assertIn("Previous game: game-000001", readme)
            self.assertIn("game-000002", readme)

    def test_failure_after_commit_recovers_without_second_shot(self):
        with workspace():
            repo, client = FakeRepository(), FakeClient([issue(1)])
            client.fail = True
            with self.assertRaisesRegex(RuntimeError, "delivery"):
                run(client, repo, SECRET, REPOSITORY)
            self.assertEqual(len(read_json("game/current.json")["shots"]), 1)
            self.assertFalse(read_json("game/commands.json")["1"]["delivered"])
            client.fail = False
            run(client, repo, SECRET, REPOSITORY)
            self.assertEqual(len(read_json("game/current.json")["shots"]), 1)
            self.assertTrue(read_json("game/commands.json")["1"]["delivered"])
            self.assertEqual(client.closed, {1})

    def test_conflicting_push_recalculates_and_preserves_new_profile(self):
        with workspace():
            repo, client = FakeRepository(), FakeClient([issue(1)])
            repo.conflicts = 1
            run(client, repo, SECRET, REPOSITORY)
            self.assertTrue(Path("README.md").read_text().startswith("Concurrent profile edit\n"))
            self.assertEqual(len(read_json("game/current.json")["shots"]), 1)
            self.assertEqual(client.closed, {1})

    def test_missing_secret_writes_nothing_and_replies_to_nothing(self):
        with workspace():
            repo, client = FakeRepository(), FakeClient([issue(1)])
            with self.assertRaises(ValueError):
                run(client, repo, "", REPOSITORY)
            self.assertEqual(repo.publications, 0)
            self.assertEqual(client.comments, {})
            self.assertFalse(Path("game/current.json").exists())

    def test_secret_change_stops_before_state_publication(self):
        with workspace():
            repo, client = FakeRepository(), FakeClient()
            run(client, repo, SECRET, REPOSITORY)
            original = dict(repo.remote)
            client.queue.append(issue(1))
            with self.assertRaisesRegex(ValueError, "secret changed"):
                run(client, repo, "different-secret", REPOSITORY)
            self.assertEqual(original, repo.remote)
            self.assertEqual(client.comments, {})

    def test_forced_restart_archives_and_increments(self):
        with workspace():
            repo, client = FakeRepository(), FakeClient()
            run(client, repo, SECRET, REPOSITORY)
            with self.assertRaisesRegex(ValueError, "active game"):
                run(client, repo, SECRET, REPOSITORY, restart=True)
            run(client, repo, SECRET, REPOSITORY, restart=True, force=True)
            self.assertEqual(read_json("game/current.json")["game_id"], "game-000002")
            self.assertEqual(read_json("game/archive/game-000001.json")["status"], "aborted")

    def test_unrelated_issues_and_pull_requests_are_ignored(self):
        other = issue(2)
        other["title"] = "Help with the profile"
        pull = issue(3)
        pull["pull_request"] = {}
        invalid = issue(4)
        invalid["title"] = "battleship: nonsense"
        state, journal, _, _ = process(None, {}, [other, pull, invalid], SECRET, REPOSITORY, NOW)
        self.assertEqual(state["shots"], [])
        self.assertEqual(set(journal), {"4"})

    def test_batch_is_bounded_and_remaining_queue_is_recoverable(self):
        queue = [issue(number) for number in range(1, MAX_COMMANDS + 4)]
        state, journal, _, _ = process(None, {}, queue, SECRET, REPOSITORY, NOW)
        self.assertEqual(len(journal), MAX_COMMANDS)
        state, journal, _, _ = process(state, journal, queue, SECRET, REPOSITORY, NOW)
        self.assertEqual(len(journal), MAX_COMMANDS + 3)
        self.assertEqual(len(state["shots"]), 1)

    def test_github_reply_recovers_comment_posted_before_close_failure(self):
        client = GitHub(REPOSITORY, "unused-test-token")
        calls = []

        def request(path, method="GET", data=None):
            calls.append((path, method, data))
            if method == "GET":
                return [
                    {"body": "<!-- battleship-result:1 -->\nExisting result", "user": {"login": "github-actions[bot]"}}
                ]
            return {"state": "closed"}

        client.request = request
        client.reply(1, "Result")
        self.assertEqual([method for _, method, _ in calls], ["GET", "PATCH"])
