import json

import httpx

from backend.core.providers import ChatMessage, OpenRouterProvider


def test_key_sent_via_header_not_in_body():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "sk-secret" not in body
        assert request.headers["Authorization"] == "Bearer sk-secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider("sk-secret", client=client)
    provider.chat([ChatMessage(role="user", content="hi")])


def test_request_body_matches_openai_schema():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenRouterProvider("sk-secret", model="meta-llama/llama-3.3-70b", client=client)
    provider.chat(
        [ChatMessage(role="user", content="hello"), ChatMessage(role="assistant", content="hi")]
    )
    assert captured["body"] == {
        "model": "meta-llama/llama-3.3-70b",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    }
