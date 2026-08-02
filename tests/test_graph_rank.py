
from backend.graph.rank import RankedPaper, rank_papers
from backend.graph.store import GraphStore
from tests.conftest import make_embed


def _seed_paper(
    store: GraphStore,
    title: str,
    axis: int,
    source: str = "arxiv",
    cited_by_count: int = 0,
) -> str:
    node = store.upsert_node(
        type="paper",
        title=title,
        embedding=make_embed(axis),
        properties={"source": source, "external_id": f"T:{title}", "cited_by_count": cited_by_count},
    )
    return node.id


def test_rank_empty_graph_returns_empty(session):
    store = GraphStore(session)
    assert rank_papers(store, make_embed(0)) == []


def test_rank_relevance_sorts_closest_first(session):
    store = GraphStore(session)
    _seed_paper(store, "Far paper", 3)
    _seed_paper(store, "Close paper", 0)
    session.commit()

    results = rank_papers(store, make_embed(0), top_k=5)
    assert [r.node.title for r in results] == ["Close paper", "Far paper"]
    assert results[0].score > results[1].score


def test_rank_citations_boost_score(session):
    store = GraphStore(session)
    cited = _seed_paper(store, "Highly cited", 0, source="arxiv", cited_by_count=500)
    obscure = _seed_paper(store, "Obscure paper", 0, source="arxiv", cited_by_count=2)
    session.commit()

    results = rank_papers(store, make_embed(0), top_k=5)
    by_title = {r.node.title: r for r in results}
    assert by_title["Highly cited"].citations > by_title["Obscure paper"].citations
    assert by_title["Highly cited"].score > by_title["Obscure paper"].score
    assert cited and obscure


def test_rank_cites_edges_count_as_citations(session):
    store = GraphStore(session)
    a = _seed_paper(store, "Paper A", 0)
    b = _seed_paper(store, "Paper B", 0)
    store.upsert_edge(source_id=b, target_id=a, type="cites")
    session.commit()

    results = rank_papers(store, make_embed(0), top_k=5)
    by_title = {r.node.title: r for r in results}
    assert by_title["Paper A"].citations > by_title["Paper B"].citations


def test_rank_method_evidence_boosts_repo_and_claims(session):
    store = GraphStore(session)
    with_repo = _seed_paper(store, "Reproducible paper", 0)
    _seed_paper(store, "Bare paper", 0)
    repo = store.upsert_node(type="repo", title="github.com/foo/bar")
    claim = store.upsert_node(type="claim", title="claim X")
    store.upsert_edge(source_id=with_repo, target_id=repo.id, type="mentions")
    store.upsert_edge(source_id=with_repo, target_id=claim.id, type="supports")
    session.commit()

    results = rank_papers(store, make_embed(0), top_k=5)
    by_title = {r.node.title: r for r in results}
    assert by_title["Reproducible paper"].method > by_title["Bare paper"].method
    assert by_title["Reproducible paper"].score > by_title["Bare paper"].score


def test_rank_provenance_prefers_trusted_sources(session):
    store = GraphStore(session)
    arxiv = _seed_paper(store, "From arxiv", 0, source="arxiv")
    web = _seed_paper(store, "From web", 0, source="web")
    session.commit()

    results = rank_papers(store, make_embed(0), top_k=5)
    by_title = {r.node.title: r for r in results}
    assert by_title["From arxiv"].provenance > by_title["From web"].provenance
    assert by_title["From arxiv"].score > by_title["From web"].score
    assert arxiv and web


def test_rank_returns_rankedpaper_objects_with_breakdown(session):
    store = GraphStore(session)
    _seed_paper(store, "Solo paper", 0)
    session.commit()

    results = rank_papers(store, make_embed(0), top_k=5)
    assert len(results) == 1
    paper = results[0]
    assert isinstance(paper, RankedPaper)
    assert 0.0 <= paper.score <= 1.0
    for component in ("relevance", "citations", "method", "provenance"):
        assert 0.0 <= getattr(paper, component) <= 1.0
