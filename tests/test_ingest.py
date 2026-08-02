from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from backend.graph.store import GraphStore
from backend.ingest.chunker import chunk_text
from backend.ingest.parser import extract_text
from backend.ingest.pipeline import IngestPipeline
from tests.conftest import make_embed


def make_pdf(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sample.pdf"
    style = getSampleStyleSheet()["Normal"]
    paragraphs = [Paragraph(p.replace("\n", "<br/>"), style) for p in text.split("\n\n")]
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    doc.build(paragraphs)
    return path


def test_extract_text(tmp_path):
    content = "Attention Is All You Need\n\nTransformers use self-attention."
    pdf = make_pdf(tmp_path, content)

    text = extract_text(pdf)
    assert "Transformers use self-attention." in text


def test_extract_text_txt(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("Plain text body", encoding="utf-8")

    assert extract_text(path) == "Plain text body"


def test_chunk_text_splits_long_paragraphs():
    long_para = "x" * 5000
    chunks = chunk_text(long_para, max_chars=2000)
    assert len(chunks) > 1
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks) == long_para


def test_chunk_text_merges_short_paragraphs():
    chunks = chunk_text("a" * 100 + "\n\n" + "b" * 100, max_chars=2000)
    assert len(chunks) == 1


def test_ingest_pipeline_with_mocked_llm(session, tmp_path, mocker):
    para = (
        "Graph neural networks generalize deep learning to graph-structured data. "
        "We study message passing and its expressive power. "
    )
    content = "Graph Neural Networks\n\n" + para * 12 + "\n\n" + para * 12
    pdf = make_pdf(tmp_path, content)

    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = (
        '{"authors": ["Jane Doe"], "concepts": ["graph neural networks", "deep learning"],'
        ' "claims": ["GNNs are expressive on relational tasks."]}'
    )

    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [
        make_embed(i % 3072) for i in range(len(texts))
    ]

    store = GraphStore(session)
    pipeline = IngestPipeline(store, provider=fake_provider, embedder=fake_embedder)
    counts = pipeline.ingest(pdf, title="GNN Survey")

    assert counts["chunks"] == 2
    assert counts["authors"] == 1
    assert counts["concepts"] == 2
    assert counts["claims"] == 1

    papers = [n for n in store.list_nodes(type="paper")]
    assert len(papers) == 1
    assert papers[0].title == "GNN Survey"
    assert len(store.list_nodes(type="concept")) == 2
    assert len(store.list_nodes(type="claim")) == 1
    authors = store.list_nodes(type="author")
    assert authors[0].title == "Jane Doe"

    neighbors = store.neighbors(papers[0].id)
    assert {n.type for n in neighbors} == {"author", "concept", "claim"}
    assert fake_provider.chat.call_count == 2


def test_ingest_dedups_entities_on_reingest(session, tmp_path, mocker):
    content = "Graph Neural Networks\n\nMessage passing generalizes deep learning."
    pdf = make_pdf(tmp_path, content)

    fake_provider = mocker.MagicMock()
    fake_provider.chat.return_value = (
        '{"authors": ["Jane Doe"], "concepts": ["message passing"], "claims": ["MP expressive"]}'
    )
    fake_embedder = mocker.MagicMock()
    fake_embedder.embed.side_effect = lambda texts: [
        make_embed(i % 3072) for i in range(len(texts))
    ]

    store = GraphStore(session)
    pipeline = IngestPipeline(store, provider=fake_provider, embedder=fake_embedder)
    first = pipeline.ingest(pdf, title="GNN Survey")
    second = pipeline.ingest(pdf, title="GNN Survey")

    assert first["authors"] >= 1
    assert second["authors"] == 0
    assert second["concepts"] == 0
    assert second["claims"] == 0

    assert len(store.list_nodes(type="author")) == 1
    assert len(store.list_nodes(type="concept")) == 1
    assert len(store.list_nodes(type="claim")) == 1
