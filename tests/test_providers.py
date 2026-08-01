import json

import httpx
import pytest

from backend.core.providers import (
    AnthropicProvider,
    ChatMessage,
    OmniRouteProvider,
    OpenAIProvider,
    OpenRouterProvider,
    create_provider,
)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_factory_returns_expected_adapter():
    assert isinstance(create_provider("openrouter", "sk-x"), OpenRouterProvider)
    assert isinstance(create_provider("openai", "sk-x"), OpenAIProvider)
    assert isinstance(create_provider("anthropic", "sk-x"), AnthropicProvider)
    assert isinstance(create_provider("omniroute", "sk-x"), OmniRouteProvider)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider("unknown", "sk-x")


def test_openrouter_chat_openai_compatible_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test-123"
        body = json.loads(request.content)
        assert "sk-test-123" not in request.content.decode()
        assert body["model"] == "openrouter/auto"
        assert body["messages"] == [{"role": "user", "content": "hola"}]
        return _chat_response("respuesta")

    provider = OpenRouterProvider("sk-test-123", client=_mock_client(handler))
    result = provider.chat([ChatMessage(role="user", content="hola")])
    assert result == "respuesta"


def test_openai_chat_and_embed():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if str(request.url) == "https://api.openai.com/v1/embeddings":
            assert body["model"] == "text-embedding-3-small"
            assert body["input"] == ["a", "b"]
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]},
            )
        assert request.url == "https://api.openai.com/v1/chat/completions"
        return _chat_response("ok")

    provider = OpenAIProvider("sk-test-123", client=_mock_client(handler))
    assert provider.chat([ChatMessage(role="user", content="hi")]) == "ok"
    assert provider.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]


def test_anthropic_chat_uses_own_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == "sk-test-123"
        body = json.loads(request.content)
        assert body["system"] == "be brief"
        assert body["messages"] == [{"role": "user", "content": "hola"}]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "adios"}]})

    provider = AnthropicProvider("sk-test-123", client=_mock_client(handler))
    result = provider.chat(
        [
            ChatMessage(role="system", content="be brief"),
            ChatMessage(role="user", content="hola"),
        ]
    )
    assert result == "adios"


def test_omniroute_sends_stream_false():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:20128/v1/chat/completions"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["model"] == "auto"
        return _chat_response("ok")

    provider = OmniRouteProvider("sk-test-123", client=_mock_client(handler))
    assert provider.chat([ChatMessage(role="user", content="hi")]) == "ok"


def test_provider_default_timeout_is_long():
    from backend.repos.github import GitHubAdapter
    from backend.search.arxiv import ArxivAdapter

    provider = OpenRouterProvider("sk-test-123")
    assert provider._client.timeout.read == 120.0
    provider._client.close()

    github = GitHubAdapter()
    assert github._client.timeout.read == 30.0
    github._client.close()

    arxiv = ArxivAdapter()
    assert arxiv._client.timeout.read == 30.0
    arxiv._client.close()
