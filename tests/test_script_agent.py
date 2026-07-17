import pytest

from pipeline.script_agent import normalize_spec, parse_spec_text


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
