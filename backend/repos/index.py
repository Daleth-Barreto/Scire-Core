from typing import TypedDict

import httpx

from backend.core.providers import ChatMessage, LLMProvider, get_embedder, get_provider
from backend.graph.store import GraphStore
from backend.repos.github import GitHubAdapter, is_source_file


class RepoCounts(TypedDict):
    files: int
    chunks: int
    skipped: int
    repo_id: str


SUMMARY_PROMPT = """You are analyzing a GitHub repository. Below is its file tree.
Write a short explainer (max 150 words) describing what this project does, its main
components, and how a newcomer should navigate it.

Repository: {owner}/{repo}
File tree:
{tree}"""


def chunk_file_with_lines(content: str, *, max_lines: int = 80) -> list[tuple[str, int]]:
    lines = content.splitlines()
    chunks: list[tuple[str, int]] = []
    for start in range(0, len(lines), max_lines):
        chunk = "\n".join(lines[start : start + max_lines])
        if chunk.strip():
            chunks.append((chunk, start + 1))
    return chunks


class RepoIndexer:
    def __init__(
        self,
        store: GraphStore,
        adapter: GitHubAdapter,
        *,
        provider: LLMProvider | None = None,
        embedder: LLMProvider | None = None,
    ) -> None:
        self._store = store
        self._adapter = adapter
        self._provider = provider or get_provider()
        self._embedder = embedder or get_embedder()

    def _existing_in_repo(self, title: str, type: str, repo_id: str):
        for node in self._store.find_by_title(title, type=type):
            if node.properties.get("repo") == repo_id:
                return node
        return None

    def add_repo(
        self,
        owner: str,
        repo: str,
        *,
        limit_files: int = 200,
        max_bytes: int = 100_000,
    ) -> RepoCounts:
        info = self._adapter.repo_info(owner, repo)
        default_branch = info.get("default_branch", "main")
        tree = self._adapter.fetch_tree(owner, repo, default_branch)
        files = [f for f in tree if f.kind == "blob" and is_source_file(f.path)][:limit_files]

        repo_matches = self._store.find_by_title(f"{owner}/{repo}", type="repo")
        repo_node = (
            repo_matches[0]
            if repo_matches
            else self._store.upsert_node(
                type="repo",
                title=f"{owner}/{repo}",
                properties={"owner": owner, "repo": repo, "branch": default_branch},
            )
        )

        counts: RepoCounts = {"files": 0, "chunks": 0, "skipped": 0, "repo_id": repo_node.id}
        for file in files:
            content = self._adapter.fetch_blob(owner, repo, file.sha)
            if len(content.encode("utf-8")) > max_bytes:
                counts["skipped"] += 1
                continue
            file_node = self._existing_in_repo(
                file.path, "file", repo_node.id
            ) or self._store.upsert_node(
                type="file",
                title=file.path,
                summary=content[:2000],
                properties={"path": file.path, "sha": file.sha, "repo": repo_node.id},
            )
            self._store.upsert_edge(source_id=repo_node.id, target_id=file_node.id, type="contains")
            counts["files"] += 1

            for chunk, start_line in chunk_file_with_lines(content):
                title = f"{file.path}:{start_line}"
                chunk_node = self._existing_in_repo(title, "chunk", repo_node.id)
                if chunk_node is None:
                    embedding = self._embed_safe(chunk)
                    chunk_node = self._store.upsert_node(
                        type="chunk",
                        title=title,
                        summary=chunk[:2000],
                        embedding=embedding,
                        properties={
                            "path": file.path,
                            "start_line": start_line,
                            "repo": repo_node.id,
                        },
                    )
                self._store.upsert_edge(
                    source_id=file_node.id, target_id=chunk_node.id, type="has_chunk"
                )
                counts["chunks"] += 1

        tree_text = "\n".join(f.path for f in files[:100])
        summary = ""
        try:
            summary = self._provider.chat(
                [
                    ChatMessage(
                        role="user",
                        content=SUMMARY_PROMPT.format(owner=owner, repo=repo, tree=tree_text),
                    )
                ]
            )
        except (httpx.HTTPError, ValueError):
            summary = ""
        self._store.upsert_node(
            node_id=repo_node.id,
            type="repo",
            title=repo_node.title,
            properties={"summary": summary},
        )
        return counts

    def _embed_safe(self, text: str) -> list[float] | None:
        try:
            return self._embedder.embed([text])[0]
        except (NotImplementedError, ValueError, httpx.HTTPError):
            return None
