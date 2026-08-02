import pytest

from backend.graph.store import GraphStore
from backend.repos.audit import audit_paper
from tests.conftest import make_embed


def _seed_repo(session, mocker) -> tuple[GraphStore, str]:
    store = GraphStore(session)
    repo = store.upsert_node(
        type="repo",
        title="demo/repo",
        properties={"summary": "A demo repository."},
    )
    store.upsert_node(
        type="chunk",
        title="src/app.py",
        summary="def attention(q, k, v):\n    return softmax(q @ k.T / sqrt(d)) @ v",
        embedding=make_embed(0),
        properties={"repo": repo.id, "path": "src/app.py", "start_line": 10},
    )
    return store, repo.id


def _seed_paper_with_claim(session, store: GraphStore, claim: str = "Attention scales as QK^T") -> str:
    paper = store.upsert_node(
        type="paper",
        title="Attention Paper",
        embedding=make_embed(1),
        properties={"source": "arxiv", "external_id": "T:attention"},
    )
    claim_node = store.upsert_node(type="claim", title=claim, embedding=make_embed(0))
    store.upsert_edge(source_id=paper.id, target_id=claim_node.id, type="mentions")
    return paper.id


def _fake_llm(mocker, verdict: str = "supported", evidence: str = "src/app.py:10"):
    provider = mocker.MagicMock()
    import json

    provider.chat.return_value = json.dumps(
        {"claim": "x", "verdict": verdict, "evidence": evidence, "reason": "found in code"}
    )
    embedder = mocker.MagicMock()
    embedder.embed.side_effect = lambda texts: [make_embed(0) for _ in texts]
    return provider, embedder


def test_audit_returns_supported_verdict(session, mocker):
    store, _ = _seed_repo(session, mocker)
    _seed_paper_with_claim(session, store)
    provider, embedder = _fake_llm(mocker)

    report = audit_paper(
        store,
        "Attention Paper",
        "demo",
        "repo",
        provider=provider,
        embedder=embedder,
    )

    assert report.paper_title == "Attention Paper"
    assert report.repo == "demo/repo"
    assert len(report.verdicts) == 1
    v = report.verdicts[0]
    assert v.claim == "Attention scales as QK^T"
    assert v.verdict == "supported"
    assert v.evidence == "src/app.py:10"


def test_audit_multiple_claims_with_mixed_verdicts(session, mocker):
    store, _ = _seed_repo(session, mocker)
    paper = store.upsert_node(type="paper", title="P", embedding=make_embed(1))
    for claim in ("Claim one", "Claim two"):
        node = store.upsert_node(type="claim", title=claim, embedding=make_embed(0))
        store.upsert_edge(source_id=paper.id, target_id=node.id, type="mentions")
    provider, embedder = _fake_llm(mocker, verdict="refuted", evidence="src/util.py:3")

    report = audit_paper(store, "P", "demo", "repo", provider=provider, embedder=embedder)

    assert len(report.verdicts) == 2
    assert all(v.verdict == "refuted" for v in report.verdicts)
    assert report.summary()["refuted"] == 2


def test_audit_paper_not_found_raises(session, mocker):
    store, _ = _seed_repo(session, mocker)
    provider, embedder = _fake_llm(mocker)
    with pytest.raises(ValueError, match="paper not found"):
        audit_paper(store, "Missing Paper", "demo", "repo", provider=provider, embedder=embedder)


def test_audit_paper_without_claims_raises(session, mocker):
    store, _ = _seed_repo(session, mocker)
    store.upsert_node(type="paper", title="No Claims", embedding=make_embed(1))
    provider, embedder = _fake_llm(mocker)
    with pytest.raises(ValueError, match="no claims"):
        audit_paper(store, "No Claims", "demo", "repo", provider=provider, embedder=embedder)


def test_audit_repo_not_indexed_raises(session, mocker):
    store = GraphStore(session)
    paper = store.upsert_node(type="paper", title="P", embedding=make_embed(1))
    claim = store.upsert_node(type="claim", title="C", embedding=make_embed(0))
    store.upsert_edge(source_id=paper.id, target_id=claim.id, type="mentions")
    provider, embedder = _fake_llm(mocker)
    with pytest.raises(ValueError, match="repo not indexed"):
        audit_paper(store, "P", "missing", "repo", provider=provider, embedder=embedder)


def test_audit_passes_claim_and_chunks_to_provider(session, mocker):
    store, _ = _seed_repo(session, mocker)
    _seed_paper_with_claim(session, store)
    provider, embedder = _fake_llm(mocker)

    audit_paper(store, "Attention Paper", "demo", "repo", provider=provider, embedder=embedder)

    sent = provider.chat.call_args.args[0]
    prompt = " ".join(m.content for m in sent)
    assert "Attention scales as QK^T" in prompt
    assert "--- src/app.py:10 ---" in prompt
