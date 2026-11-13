"""Public JSON persistence and atomic Git publication."""

import json
from pathlib import Path
import subprocess


def read_json(path, default=None):
    file = Path(path)
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else default


def write_json(path, value):
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


class Repository:
    """Used only inside the disposable Actions checkout."""

    def __init__(self, branch):
        self.branch = branch

    def refresh(self):
        git("fetch", "origin", self.branch)
        git("reset", "--hard", f"origin/{self.branch}")

    def publish(self):
        git("add", "--", "README.md", "game")
        if not git("diff", "--cached", "--quiet", check=False).returncode:
            return True
        git(
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "Update community Battleship",
        )
        result = git("push", "origin", f"HEAD:refs/heads/{self.branch}", check=False)
        if result.returncode == 0:
            return True
        git("fetch", "origin", self.branch)
        parent = git("rev-parse", "HEAD^").stdout.strip()
        remote = git("rev-parse", f"origin/{self.branch}").stdout.strip()
        if parent == remote:
            raise RuntimeError("Unable to push game state. Check workflow permissions and branch rules.")
        return False
