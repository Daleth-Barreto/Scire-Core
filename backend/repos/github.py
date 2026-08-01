import base64
from dataclasses import dataclass

import httpx

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".rb",
    ".php",
    ".sh",
    ".sql",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".md",
    ".txt",
    ".css",
    ".html",
}
SKIP_DIRS = {"node_modules", "vendor", "dist", "build", ".git", "target", "__pycache__"}


@dataclass
class FileInfo:
    path: str
    sha: str
    kind: str


def is_source_file(path: str) -> bool:
    parts = path.split("/")
    if any(part in SKIP_DIRS for part in parts):
        return False
    return any(path.endswith(ext) for ext in SOURCE_EXTENSIONS)


class GitHubAdapter:
    def __init__(self, token: str = "", client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "scire",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def repo_info(self, owner: str, repo: str) -> dict:
        response = self._client.get(
            f"https://api.github.com/repos/{owner}/{repo}", headers=self._headers
        )
        response.raise_for_status()
        return response.json()

    def fetch_tree(self, owner: str, repo: str, ref: str) -> list[FileInfo]:
        response = self._client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1",
            headers=self._headers,
        )
        response.raise_for_status()
        return [
            FileInfo(path=item.get("path", ""), sha=item.get("sha", ""), kind=item.get("type", ""))
            for item in response.json().get("tree", [])
            if item.get("type") in ("blob", "tree")
        ]

    def fetch_blob(self, owner: str, repo: str, sha: str) -> str:
        response = self._client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}",
            headers=self._headers,
        )
        response.raise_for_status()
        data = response.json()
        raw = base64.b64decode(data.get("content", ""))
        return raw.decode("utf-8", errors="replace")
