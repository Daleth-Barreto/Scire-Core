import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.core.config import get_settings

EMBED_DIM = get_settings().embed_dim

NODE_TYPES = {"paper", "author", "concept", "hypothesis", "repo", "note", "claim"}
EDGE_TYPES = {"cites", "authored_by", "supports", "refutes", "gap_in", "extends", "mentions"}


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (UniqueConstraint("source_id", "target_id", "type", name="uq_edge"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(Text, ForeignKey("nodes.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(Text, ForeignKey("nodes.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
