from unittest.mock import Mock, patch

import pytest

from pipeline.script_agent import call_gemini, normalize_spec, parse_spec_text


def test_parses_raw_json():
    assert parse_spec_text(' {"a": 1} ') == {"a": 1}


def test_parses_fenced_json():
    assert parse_spec_text('```json\n{"a": 1}\n```') == {"a": 1}


def test_rejects_non_object():
    with pytest.raises(ValueError):
        parse_spec_text("[1, 2, 3]")


def test_normalize_forces_untrusted_fields():
    spec = {
        "topic_id": "whatever-the-llm-said",
        "metadata": {"ai_disclosure": False, "privacy_status": "public"},
    }
    normalized = normalize_spec(spec, {"id": "real-topic"})
    assert normalized["topic_id"] == "real-topic"
    assert normalized["spec_version"] == "1.0"
    assert normalized["metadata"]["ai_disclosure"] is True
    assert normalized["metadata"]["privacy_status"] == "private"


@patch("pipeline.script_agent.requests.post")
def test_gemini_uses_stable_api(mock_post):
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
    }
    mock_post.return_value = response

    assert call_gemini("prompt", api_key="test-key") == "{}"
    assert "/v1/models/gemini-3.5-flash:generateContent" in mock_post.call_args.args[0]
    generation_config = mock_post.call_args.kwargs["json"]["generationConfig"]
    assert generation_config == {"temperature": 0.8, "maxOutputTokens": 16384}


@patch("pipeline.script_agent.requests.post")
def test_gemini_error_includes_api_detail(mock_post):
    response = Mock(status_code=404, ok=False, text="")
    response.json.return_value = {"error": {"message": "model unavailable for this project"}}
    mock_post.return_value = response

    with pytest.raises(RuntimeError, match="model unavailable for this project"):
        call_gemini("prompt", api_key="test-key")
