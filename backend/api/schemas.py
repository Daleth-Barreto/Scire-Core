from pydantic import BaseModel, Field


class NodeOut(BaseModel):
    id: str
    type: str
    title: str
    summary: str | None = None
    properties: dict = {}


class EdgeOut(BaseModel):
    id: str
    source_id: str
    target_id: str
    type: str


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]


class SearchIn(BaseModel):
    query: str
    limit: int = Field(10, ge=1, le=50)
    persist: bool = False


class PaperFetchIn(BaseModel):
    external_id: str
    persist: bool = True


class CandidateOut(BaseModel):
    title: str
    authors: list[str] = []
    url: str = ""
    source: str
    external_id: str
    summary: str = ""
    published: str | None = None


class RepoAddIn(BaseModel):
    owner: str
    repo: str
    limit_files: int = Field(200, ge=1, le=1000)


class RepoAskIn(BaseModel):
    owner: str
    repo: str
    question: str


class NoteIn(BaseModel):
    content: str


class ChatIn(BaseModel):
    message: str
    model: str | None = None


class ConfigOut(BaseModel):
    provider: str
    embed_model: str | None = None
    api_key: str
    github_token: str
    encrypted: bool = False


class ConfigKeysIn(BaseModel):
    passphrase: str
    keys: dict[str, str]


class ConfigUnlockIn(BaseModel):
    passphrase: str


class RankIn(BaseModel):
    query: str
    top_k: int = Field(10, ge=1, le=50)


class RankedOut(BaseModel):
    id: str
    title: str
    score: float
    relevance: float
    citations: float
    method: float
    provenance: float


class DeepResearchIn(BaseModel):
    topic: str
    limit: int = Field(5, ge=1, le=20)


class SourceOut(BaseModel):
    title: str
    url: str
    source: str
    summary: str = ""
    authors: list[str] = []


class DeepResearchOut(BaseModel):
    topic: str
    markdown: str
    sources: list[SourceOut] = []
    verified: bool = False
    issues: list[str] = []


class RepoAuditIn(BaseModel):
    paper_title: str
    owner: str
    repo: str


class AuditVerdictOut(BaseModel):
    claim: str
    verdict: str
    evidence: str = ""
    reason: str = ""


class AuditOut(BaseModel):
    paper_title: str
    repo: str
    verdicts: list[AuditVerdictOut] = []
    summary: dict[str, int] = {}
