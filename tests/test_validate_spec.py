import json
from pathlib import Path

import pytest

from pipeline.validate_spec import validate_spec

FIXTURE = Path(__file__).parent / "fixtures" / "sample_spec.json"


@pytest.fixture()
def spec():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_golden_spec_is_valid(spec):
    assert validate_spec(spec) == []


def test_first_scene_must_be_hook(spec):
    spec["scenes"][0]["type"] = "payoff"
    assert any("hook" in e for e in validate_spec(spec))


def test_long_code_line_fails(spec):
    code_scene = next(s for s in spec["scenes"] if s["type"] == "code")
    code_scene["code"]["content"] += "\nconst veryLongVariableName = doSomethingVerbose(aaa, bbb);"
    errors = validate_spec(spec)
    assert any("exceed" in e for e in errors)


def test_highlight_out_of_range_fails(spec):
    code_scene = next(s for s in spec["scenes"] if s["type"] == "code")
    code_scene["code"]["highlights"][0]["end_line"] = 99
    assert any("out of" in e for e in validate_spec(spec))


def test_unknown_diagram_node_fails(spec):
    diagram = next(s for s in spec["scenes"] if s["type"] == "diagram")["diagram"]
    diagram["edges"][0]["to"] = "nonexistent"
    assert any("unknown node" in e for e in validate_spec(spec))


def test_missing_disclosure_fails(spec):
    spec["metadata"]["description"] = (
        "شرح مبسط لمفهوم مهم في البرمجة للمطورين العرب بدون أي تفاصيل إضافية عن الإنتاج."
    )
    assert any("disclosure" in e for e in validate_spec(spec))


def test_total_duration_out_of_range_fails(spec):
    for scene in spec["scenes"]:
        scene["target_duration_s"] = 30
        scene["vo_text"] = scene["vo_text"] + " " + scene["vo_text"]
    assert any("total target duration" in e for e in validate_spec(spec))


def test_schema_rejects_extra_keys(spec):
    spec["surprise"] = True
    assert any("schema" in e for e in validate_spec(spec))
