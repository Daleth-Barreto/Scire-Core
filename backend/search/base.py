from abc import ABC, abstractmethod

from pydantic import BaseModel


class CandidateNode(BaseModel):
    title: str
    authors: list[str] = []
    url: str = ""
    source: str
    external_id: str
    summary: str = ""
    published: str | None = None
    cited_by_count: int = 0


class SearchAdapter(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[CandidateNode]: ...

    @abstractmethod
    def fetch(self, external_id: str) -> CandidateNode | None: ...
