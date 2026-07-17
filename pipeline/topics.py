"""Topic queue management.

topics.yaml is human-edited only. Processing status lives in state/queue_state.json
(machine-owned), so the bot never rewrites — and never clobbers — the human file.
"""

import json
import re
import time
from pathlib import Path

import yaml

from . import config


def load_topics(path: Path | None = None) -> list[dict]:
    path = path or config.TOPICS_FILE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    topics = data.get("topics") or []
    for topic in topics:
        if not isinstance(topic, dict) or "id" not in topic or "title" not in topic:
            raise ValueError(f"Malformed topic entry (needs id + title): {topic!r}")
    return topics


def load_state(path: Path | None = None) -> dict:
    path = path or config.STATE_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"done": [], "failed": {}}


def save_state(state: dict, path: Path | None = None) -> None:
    path = path or config.STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_pending(topics: list[dict] | None = None, state: dict | None = None) -> dict | None:
    topics = topics if topics is not None else load_topics()
    state = state if state is not None else load_state()
    skip = set(state.get("done", [])) | set(state.get("failed", {}))
    for topic in topics:
        if topic["id"] not in skip:
            return topic
    return None


def mark_done(topic_id: str, path: Path | None = None) -> None:
    state = load_state(path)
    if topic_id not in state["done"]:
        state["done"].append(topic_id)
    state["failed"].pop(topic_id, None)
    save_state(state, path)


def mark_failed(topic_id: str, reason: object, path: Path | None = None) -> None:
    state = load_state(path)
    state["failed"][topic_id] = {
        "reason": str(reason)[:300],
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_state(state, path)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:60]
    if len(slug) < 3:
        slug = "topic-" + time.strftime("%Y%m%d-%H%M%S")
    return slug


def resolve_topic(topic_id: str | None = None, adhoc_title: str | None = None) -> dict | None:
    """Pick the topic to produce: ad-hoc title > explicit id > next pending in queue."""
    if adhoc_title:
        return {"id": slugify(adhoc_title), "title": adhoc_title}
    if topic_id:
        for topic in load_topics():
            if topic["id"] == topic_id:
                return topic
        raise LookupError(f"topic id {topic_id!r} not found in topics.yaml")
    return next_pending()
