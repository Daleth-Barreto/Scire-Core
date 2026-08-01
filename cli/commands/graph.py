from pathlib import Path

import typer

from backend.graph.db import session_scope
from backend.graph.store import GraphStore

node_app = typer.Typer(help="Knowledge graph nodes.")
edge_app = typer.Typer(help="Knowledge graph edges.")
graph_app = typer.Typer(help="Knowledge graph queries.")

NODE_TYPES = {"paper", "author", "concept", "hypothesis", "repo", "note", "claim", "file", "chunk"}
EDGE_TYPES = {
    "cites",
    "authored_by",
    "supports",
    "refutes",
    "gap_in",
    "extends",
    "mentions",
    "contains",
    "has_chunk",
}


@node_app.command("add")
def node_add(
    type: str = typer.Option(..., "--type", "-t", help="Node type"),
    title: str = typer.Option(..., "--title", help="Node title"),
    summary: str | None = typer.Option(None, "--summary", "-s", help="Optional summary"),
    embed: bool = typer.Option(True, "--embed/--no-embed", help="Generate an embedding"),
) -> None:
    if type not in NODE_TYPES:
        raise typer.BadParameter(
            f"invalid type '{type}'; choose one of {', '.join(sorted(NODE_TYPES))}"
        )
    text = title if not summary else f"{title}\n{summary}"
    embedding = None
    if embed:
        from backend.core.providers import get_embedder

        try:
            embedding = get_embedder().embed([text])[0]
        except ValueError as exc:
            typer.echo(
                f"warning: no embedder available, storing without embedding: {exc}", err=True
            )
    with session_scope() as session:
        store = GraphStore(session)
        node = store.upsert_node(type=type, title=title, summary=summary, embedding=embedding)
        typer.echo(f"created node {node.id} ({node.type}: {node.title})")


@node_app.command("list")
def node_list(type: str | None = None) -> None:
    with session_scope() as session:
        store = GraphStore(session)
        nodes = store.list_nodes(type=type)
        if not nodes:
            typer.echo("no nodes")
            return
        for node in nodes:
            typer.echo(f"{node.id}  {node.type:<11}  {node.title}")


@edge_app.command("add")
def edge_add(
    source_id: str = typer.Option(..., "--source", "-s", help="Source node id"),
    target_id: str = typer.Option(..., "--target", "-t", help="Target node id"),
    type: str = typer.Option(..., "--type", "-k", help="Edge type"),
) -> None:
    if type not in EDGE_TYPES:
        raise typer.BadParameter(
            f"invalid edge type '{type}'; choose one of {', '.join(sorted(EDGE_TYPES))}"
        )
    with session_scope() as session:
        store = GraphStore(session)
        source = store.get_node(source_id)
        target = store.get_node(target_id)
        if source is None or target is None:
            missing = source_id if source is None else target_id
            raise typer.BadParameter(f"node not found: {missing}")
        edge = store.upsert_edge(source_id=source_id, target_id=target_id, type=type)
        typer.echo(f"created edge {edge.id} ({source.title} -[{type}]-> {target.title})")


@graph_app.command("init")
def graph_init() -> None:
    from backend.graph.db import get_engine
    from backend.graph.models import Base

    Base.metadata.create_all(get_engine())
    typer.echo("graph schema created")


@graph_app.command("search")
def graph_search(query: str, top_k: int = 10) -> None:
    from backend.core.providers import get_embedder

    try:
        embedding = get_embedder().embed([query])[0]
    except ValueError as exc:
        raise typer.BadParameter(f"no embedder available: {exc}") from exc
    with session_scope() as session:
        store = GraphStore(session)
        results = store.search(embedding, top_k=top_k)
        if not results:
            typer.echo("no results")
            return
        for node, distance in results:
            typer.echo(f"{distance:.4f}  {node.type:<11}  {node.title}")


@graph_app.command("gaps")
def graph_gaps() -> None:
    from backend.memory.gaps import detect_gaps

    with session_scope() as session:
        store = GraphStore(session)
        hypotheses = detect_gaps(store)
        if not hypotheses:
            typer.echo("no gaps detected")
            return
        for h in hypotheses:
            typer.echo(f"hypothesis: {h}")


@graph_app.command("export")
def graph_export(path: Path) -> None:
    import json

    from backend.graph.json_export import export_graph

    with session_scope() as session:
        data = export_graph(GraphStore(session))
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"exported {len(data['nodes'])} nodes, {len(data['edges'])} edges -> {path}")


@graph_app.command("import")
def graph_import(path: Path) -> None:
    import json

    from backend.graph.json_export import import_graph

    if not path.is_file():
        raise typer.BadParameter(f"file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    with session_scope() as session:
        counts = import_graph(GraphStore(session), data)
        typer.echo(f"imported {counts['nodes']} nodes, {counts['edges']} edges")


@graph_app.command("show")
def graph_show(node_id: str | None = None) -> None:
    from backend.graph.ascii import find_hub, render_tree

    with session_scope() as session:
        store = GraphStore(session)
        root = node_id or find_hub(store)
        if root is None:
            typer.echo("graph is empty")
            return
        typer.echo(render_tree(store, root))
