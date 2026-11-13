"""Small GitHub REST client using only the standard library."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class GitHub:
    def __init__(self, repository, token):
        self.base = f"https://api.github.com/repos/{repository}"
        self.token = token

    def request(self, path, method="GET", data=None):
        request = Request(
            self.base + path,
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"GitHub API request failed (HTTP {error.code}).") from None

    def pages(self, path):
        page = 1
        while True:
            rows = self.request(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
            yield from rows
            if len(rows) < 100:
                return
            page += 1

    def issues(self):
        return self.pages("/issues?state=all&sort=created&direction=asc")

    def reply(self, number, message):
        marker = f"<!-- battleship-result:{number} -->"
        comments = self.pages(f"/issues/{number}/comments")
        if not any(
            marker in comment["body"] and comment["user"]["login"] == "github-actions[bot]" for comment in comments
        ):
            self.request(f"/issues/{number}/comments", "POST", {"body": marker + "\n" + message})
        self.request(f"/issues/{number}", "PATCH", {"state": "closed"})
