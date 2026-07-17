import json

from pipeline import topics


def write_queue(tmp_path, yaml_text, state=None):
    topics_file = tmp_path / "topics.yaml"
    topics_file.write_text(yaml_text, encoding="utf-8")
    state_file = tmp_path / "state.json"
    if state is not None:
        state_file.write_text(json.dumps(state), encoding="utf-8")
    return topics_file, state_file


def test_next_pending_skips_done_and_failed(tmp_path):
    topics_file, state_file = write_queue(
        tmp_path,
        "topics:\n  - id: a\n    title: A\n  - id: b\n    title: B\n  - id: c\n    title: C\n",
        {"done": ["a"], "failed": {"b": {"reason": "x"}}},
    )
    picked = topics.next_pending(topics.load_topics(topics_file), topics.load_state(state_file))
    assert picked["id"] == "c"


def test_next_pending_empty_queue(tmp_path):
    topics_file, state_file = write_queue(tmp_path, "topics: []\n", {"done": [], "failed": {}})
    assert topics.next_pending(topics.load_topics(topics_file), topics.load_state(state_file)) is None


def test_mark_done_clears_failed(tmp_path):
    _, state_file = write_queue(tmp_path, "topics: []\n",
                                {"done": [], "failed": {"x": {"reason": "boom"}}})
    topics.mark_done("x", state_file)
    state = topics.load_state(state_file)
    assert state["done"] == ["x"]
    assert state["failed"] == {}


def test_slugify_ascii():
    assert topics.slugify("Hello, World! JS") == "hello-world-js"


def test_slugify_non_ascii_falls_back():
    assert topics.slugify("مقدمة").startswith("topic-")


def test_real_topics_file_loads():
    loaded = topics.load_topics()
    assert len(loaded) >= 5
    ids = [t["id"] for t in loaded]
    assert len(ids) == len(set(ids)), "topic ids must be unique"
