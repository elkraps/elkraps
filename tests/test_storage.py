import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from battleship.main import run
from battleship.storage import Repository, read_json
from test_processing import FakeClient, issue


def git(directory, *args):
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(directory, message):
    git(directory, "add", ".")
    git(directory, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", message)


class StorageIntegrationTests(unittest.TestCase):
    def test_real_git_conflict_recomputes_state_then_publishes_reply_receipt(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, worker, owner = (root / name for name in ("remote.git", "worker", "owner"))
            git(root, "init", "--bare", "--initial-branch=main", str(remote))
            git(root, "clone", str(remote), str(worker))
            (worker / "README.md").write_text("Profile before concurrent edit\n")
            commit(worker, "Initial profile")
            git(worker, "push", "origin", "main")
            git(root, "clone", str(remote), str(owner))
            repo = Repository("main")
            publish = repo.publish
            conflict_pending = True

            def conflicting_publish():
                nonlocal conflict_pending
                if conflict_pending:
                    conflict_pending = False
                    (owner / "README.md").write_text("Profile after concurrent edit\n")
                    commit(owner, "Owner edits profile")
                    git(owner, "push", "origin", "main")
                return publish()

            repo.publish = conflicting_publish
            client = FakeClient([issue(1)])
            try:
                os.chdir(worker)
                run(client, repo, "test-secret", "owner/repo")
                self.assertEqual(len(read_json("game/current.json")["shots"]), 1)
                self.assertTrue(read_json("game/commands.json")["1"]["delivered"])
                self.assertTrue(Path("README.md").read_text().startswith("Profile after concurrent edit\n"))
                self.assertEqual(git(worker, "rev-parse", "HEAD"), git(remote, "rev-parse", "main"))
                self.assertEqual(client.closed, {1})
            finally:
                os.chdir(previous)
