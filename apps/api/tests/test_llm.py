"""Exercise the HTTP boundary without transmitting data to an external provider."""

import json
from pathlib import Path

import httpx
import pytest
from safer import llm

BLOCKS = [
    {
        "id": "b0",
        "title": "Amount",
        "facts": {"Status": "mismatch"},
        "text": "Values differ.",
        "citations": [],
    }
]


def reply(blocks=None, **changes):
    result = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "blocks": blocks
                                    or [
                                        {
                                            "id": "b0",
                                            "text": "Check the recorded evidence before resolving the mismatch.",
                                        }
                                    ]
                                }
                            )
                        }
                    ]
                },
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 200,
            "candidatesTokenCount": 30,
            "totalTokenCount": 230,
        },
        "modelVersion": "gemini-3.5-flash-lite",
    }
    result.update(changes)
    return result


def test_adapter_returns_only_bound_plain_text_and_usage():
    captured = []

    def respond(request):
        captured.append(request)
        return httpx.Response(200, json=reply())

    result = llm.Gemini("x" * 30, transport=httpx.MockTransport(respond)).generate(BLOCKS)
    assert result.texts == {"b0": "Check the recorded evidence before resolving the mismatch."}
    assert result.tokens == 230
    request = captured[0]
    assert (
        str(request.url)
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    )
    assert request.headers["x-goog-api-key"] == "x" * 30
    body = json.loads(request.content)
    assert "tools" not in body and "cachedContent" not in body
    assert body["generationConfig"]["maxOutputTokens"] == 2048
    assert "citations" not in body["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize(
    "blocks",
    [
        [{"id": "foreign", "text": "Invented source"}],
        [{"id": "b0", "text": "One"}, {"id": "b0", "text": "Two"}],
        [{"id": "b0", "text": "<script>send()</script>"}],
        [{"id": "b0", "text": "Visit https://attacker.invalid"}],
        [{"id": "b0", "text": "Fine", "approve": True}],
        [{"id": "b0", "text": " "}],
    ],
)
def test_invalid_or_foreign_model_blocks_fail_closed(blocks):
    provider = llm.Gemini(
        "x" * 30, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=reply(blocks)))
    )
    with pytest.raises(llm.LlmFailure, match="invalid_output"):
        provider.generate(BLOCKS)


@pytest.mark.parametrize(
    "content",
    [
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]},
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"functionCall": {"name": "approve"}}]},
                }
            ]
        },
        {"promptFeedback": {"blockReason": "SAFETY"}},
        [],
    ],
)
def test_truncation_tools_and_refusals_fall_back(content):
    provider = llm.Gemini(
        "x" * 30, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=content))
    )
    with pytest.raises(llm.LlmFailure, match="invalid_output"):
        provider.generate(BLOCKS)


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_provider_errors_do_not_leak_body_or_follow_redirect(status):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            status, text="secret provider error", headers={"Location": "https://other.invalid"}
        )

    with pytest.raises(llm.LlmFailure) as error:
        llm.Gemini("x" * 30, transport=httpx.MockTransport(respond)).generate(BLOCKS)
    assert "secret" not in str(error.value) and len(calls) == 1


def test_timeout_and_oversized_inputs_outputs_are_bounded():
    def timeout(request):
        raise httpx.ReadTimeout("secret", request=request)

    with pytest.raises(llm.LlmFailure, match="provider_unavailable"):
        llm.Gemini("x" * 30, transport=httpx.MockTransport(timeout)).generate(BLOCKS)
    with pytest.raises(llm.LlmFailure, match="input_too_large"):
        llm.Gemini("x" * 30, transport=httpx.MockTransport(timeout)).generate(
            [{**BLOCKS[0], "text": "x" * 21000}]
        )
    with pytest.raises(llm.LlmFailure, match="invalid_output"):
        llm.Gemini(
            "x" * 30,
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 70000)),
        ).generate(BLOCKS)


def test_secret_file_must_be_private_and_outside_checkout(tmp_path):
    path = tmp_path / "key"
    path.write_text("x" * 30)
    path.chmod(0o600)
    assert llm.private_text(path) == "x" * 30
    path.chmod(0o644)
    with pytest.raises(llm.LlmFailure, match="configuration_unavailable"):
        llm.private_text(path)
    with pytest.raises(llm.LlmFailure, match="configuration_unavailable"):
        llm.private_text(Path(__file__))


@pytest.mark.parametrize("usage", [[], "invalid", None, {"totalTokenCount": True}])
def test_malformed_usage_metadata_does_not_escape_fallback(usage):
    provider = llm.Gemini(
        "x" * 30,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=reply(usageMetadata=usage))
        ),
    )
    with pytest.raises(llm.LlmFailure, match="invalid_output"):
        provider.generate(BLOCKS)
