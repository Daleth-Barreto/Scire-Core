from collections.abc import Callable, Iterable

from backend.core.providers import ChatMessage, LLMProvider, get_provider
from backend.graph.db import session_scope
from backend.graph.store import GraphStore

HELP_TEXT = """Scire shell
  <question>            ask the LLM (logged as an action)
  /help                 show this help
  /note <text>          save a thought as a note
  /search <query>       semantic search over the graph
  /graph [node_id]      render the graph as an ASCII tree
  /gaps                 detect research gaps
  /export <path>        export graph to JSON
  /import <path>        import graph from JSON
  /quit                 leave the shell"""


def _stdin_lines() -> Iterable[str]:
    while True:
        try:
            line = input("scire> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        yield line


def _ask_chat(provider: LLMProvider, question: str) -> str:
    reply = provider.chat([ChatMessage(role="user", content=question)])
    with session_scope() as session:
        from backend.memory.actions import log_action

        log_action(GraphStore(session), "chat", details=question)
    return reply


def repl(
    lines: Iterable[str] | None = None,
    *,
    provider: LLMProvider | None = None,
    output: Callable[[str], None] | None = None,
) -> None:
    provider = provider or get_provider()
    echo = output or print
    iterator = iter(lines) if lines is not None else _stdin_lines()

    for line in iterator:
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            try:
                _handle_slash(provider, line, echo)
            except SystemExit:
                return
            continue
        echo(_ask_chat(provider, line))


def _handle_slash(provider: LLMProvider, line: str, echo: Callable[[str], None]) -> None:
    parts = line.split(maxsplit=1)
    command = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if command in {"/quit", "/exit"}:
        raise SystemExit(0)
    if command == "/help":
        echo(HELP_TEXT)
        return

    if command == "/note":
        if not arg:
            echo("usage: /note <text>")
            return
        with session_scope() as session:
            from backend.memory.notes import add_note

            node = add_note(GraphStore(session), arg)
            echo(f"note saved {node.id}")
        return

    if command == "/search":
        from backend.core.providers import get_embedder

        if not arg:
            echo("usage: /search <query>")
            return
        embedding = get_embedder().embed([arg])[0]
        with session_scope() as session:
            store = GraphStore(session)
            results = store.search(embedding, top_k=8)
            if not results:
                echo("no results")
                return
            for node, distance in results:
                echo(f"{distance:.4f}  {node.type:<11}  {node.title}")
        return

    if command == "/graph":
        from backend.graph.ascii import find_hub, render_tree

        with session_scope() as session:
            store = GraphStore(session)
            root = arg or find_hub(store)
            if root is None:
                echo("graph is empty")
                return
            echo(render_tree(store, root))
        return

    if command == "/gaps":
        from backend.memory.gaps import detect_gaps

        with session_scope() as session:
            hypotheses = detect_gaps(GraphStore(session))
            if not hypotheses:
                echo("no gaps detected")
                return
            for h in hypotheses:
                echo(f"hypothesis: {h}")
        return

    if command == "/export":
        import json
        from pathlib import Path

        from backend.graph.json_export import export_graph

        if not arg:
            echo("usage: /export <path>")
            return
        with session_scope() as session:
            data = export_graph(GraphStore(session))
            Path(arg).write_text(json.dumps(data, indent=2), encoding="utf-8")
            echo(f"exported {len(data['nodes'])} nodes, {len(data['edges'])} edges")
        return

    if command == "/import":
        import json
        from pathlib import Path

        from backend.graph.json_export import import_graph

        if not arg:
            echo("usage: /import <path>")
            return
        path = Path(arg)
        if not path.is_file():
            echo(f"file not found: {path}")
            return
        with session_scope() as session:
            counts = import_graph(GraphStore(session), json.loads(path.read_text(encoding="utf-8")))
            echo(f"imported {counts['nodes']} nodes, {counts['edges']} edges")
        return

    echo(f"unknown command: {command} (try /help)")
