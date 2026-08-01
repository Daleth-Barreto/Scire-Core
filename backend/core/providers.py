from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

from backend.core.config import Settings


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[ChatMessage], model: str | None = None) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(f"{type(self).__name__} does not support embeddings")


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        chat_path: str,
        default_model: str,
        request_stream: bool | None = None,
        embed_path: str | None = None,
        embed_model: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._chat_url = f"{base_url}{chat_path}"
        self._embed_url = f"{base_url}{embed_path}" if embed_path else None
        self._embed_model = embed_model
        self.default_model = default_model
        self._request_stream = request_stream
        self._client = client or httpx.Client(timeout=120.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def chat(self, messages: list[ChatMessage], model: str | None = None) -> str:
        payload: dict[str, object] = {
            "model": model or self.default_model,
            "messages": [m.model_dump() for m in messages],
        }
        if self._request_stream is not None:
            payload["stream"] = self._request_stream
        response = self._client.post(
            self._chat_url,
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if self._embed_url is None:
            raise NotImplementedError(f"{type(self).__name__} does not support embeddings")
        response = self._client.post(
            self._embed_url,
            headers=self._headers(),
            json={"model": model or self._embed_model, "input": texts},
        )
        response.raise_for_status()
        return [item["embedding"] for item in response.json()["data"]]


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "openrouter/auto",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key,
            base_url="https://openrouter.ai/api/v1",
            chat_path="/chat/completions",
            default_model=model,
            client=client,
        )


class OmniRouteProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "auto",
        embed_model: str = "gemini/gemini-embedding-001",
        base_url: str = "http://localhost:20128/v1",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key,
            base_url=base_url,
            chat_path="/chat/completions",
            default_model=model,
            request_stream=False,
            embed_path="/embeddings",
            embed_model=embed_model,
            client=client,
        )


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4o-mini",
        embed_model: str = "text-embedding-3-small",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            api_key,
            base_url="https://api.openai.com/v1",
            chat_path="/chat/completions",
            default_model=model,
            embed_path="/embeddings",
            embed_model=embed_model,
            client=client,
        )


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-sonnet-4-20250514",
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self.default_model = model
        self._client = client or httpx.Client(timeout=120.0)
        self._url = "https://api.anthropic.com/v1/messages"

    def chat(self, messages: list[ChatMessage], model: str | None = None) -> str:
        system = "\n".join(m.content for m in messages if m.role == "system")
        non_system = [m for m in messages if m.role != "system"]
        response = self._client.post(
            self._url,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model or self.default_model,
                "max_tokens": 1024,
                "system": system,
                "messages": [m.model_dump() for m in non_system],
            },
        )
        response.raise_for_status()
        data = response.json()
        return "".join(
            block["text"] for block in data.get("content", []) if block.get("type") == "text"
        )


def get_provider(
    settings: Settings | None = None, *, client: httpx.Client | None = None
) -> LLMProvider:
    from backend.core.config import get_settings

    settings = settings or get_settings()
    return create_provider(
        settings.llm_provider,
        settings.provider_api_key.get_secret_value(),
        model=settings.llm_model,
        client=client,
    )


def get_embedder(
    settings: Settings | None = None, *, client: httpx.Client | None = None
) -> LLMProvider:
    from backend.core.config import get_settings

    settings = settings or get_settings()
    return create_provider(
        settings.embed_provider,
        settings.embed_api_key_for_provider.get_secret_value(),
        model=settings.embed_model,
        client=client,
    )


def create_provider(
    name: str,
    api_key: str,
    *,
    model: str = "",
    client: httpx.Client | None = None,
) -> LLMProvider:
    providers = {
        "openrouter": ("OpenRouterProvider", "openrouter/auto"),
        "openai": ("OpenAIProvider", "gpt-4o-mini"),
        "anthropic": ("AnthropicProvider", "claude-sonnet-4-20250514"),
        "omniroute": ("OmniRouteProvider", "auto"),
    }
    if name not in providers:
        raise ValueError(f"Unknown provider: {name}")
    provider_cls, default_model = providers[name]
    selected = model or default_model
    if provider_cls == "OpenRouterProvider":
        return OpenRouterProvider(api_key, model=selected, client=client)
    if provider_cls == "OpenAIProvider":
        return OpenAIProvider(api_key, model=selected, client=client)
    if provider_cls == "OmniRouteProvider":
        return OmniRouteProvider(api_key, model=selected, client=client)
    return AnthropicProvider(api_key, model=selected, client=client)
